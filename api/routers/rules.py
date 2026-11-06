"""Cataloghi delle regole di classe (sola lettura)."""
from __future__ import annotations

import random
from typing import Annotated, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_lang, get_current_user
from api.database import get_db
from api.schemas.session import TurnBlock
from api.routers._helpers import unarmed_attack_profile, weapon_attack_profile
from api.routers._helpers import retouch_concentration
from api.routers.characters import _add_history, close_pending_save, open_failed_save
from api.routers.hp import _get_owned_full, death_state, retouch_death_save
from api.routers.items import close_grazed_attack, retouch_pending_attack
from api.routers.encounters import _notify_saves
from api.routers.sessions import _touch, active_encounter_row
from api.services.rules_targets import apply_target_effect, pending_target_effect
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from api.schemas.common import OptionResult
from api.services.d20 import d20_records, resolve_applied
from api.services.dice_stats import record_dice
from api.services.rules_states import remove_state, use_feature
from api.services.wild_shape import STATE_KEY as WILD_SHAPE_STATE, get_active_form, return_to_normal
from api.services.session_allies import attach_party_auras, seated_allies
from core.rules.states import is_target_immune
from api.services.turn_start import apply_turn_start
from api.services.rules_turn import clear_once_per_turn, get_turn, refuse_if_incapacitated, release, reset_turn, spend
from api.services.durations import is_concentrating
from core.db.models import Character, Combatant, Encounter, GameSession
from api.schemas.rules import (
    LastRollBody,
    LastRollRefund,
    LastRollResult,
    ProficiencyGrantRead,
    RollOptionRead,
    SubclassRead,
    TargetCandidate,
    TargetEffectBody,
    TargetEffectPreview,
    TargetEffectRead,
    TargetEffectResult,
)
from api.services.rules_options import list_options, merge_options, option_result, roll_option_dice, use_options
from core.data.damage_types import canonical_damage_type
from core.data.skills import SKILL_ABILITY_MAP
from core.data.spell_slots import normalize_class_name
from core.rules.modifiers import modifiers_for
from core.rules.proficiencies import class_proficiencies, grant_to_dict
from core.rules.roll_options import AppliedOptions, refund_spent
from core.rules.subclasses import subclasses_for
from core.rules.types import BARDIC_DIE, Edition

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("/subclasses", response_model=list[SubclassRead])
async def list_subclasses(
    edition: Edition, class_key: str, _user: Annotated[int, Depends(get_current_user)],
) -> list[SubclassRead]:
    class_key = normalize_class_name(class_key) or class_key  # accetta anche i nomi italiani (`Mago`)
    return [SubclassRead(key=s.key, name=s.name, choice_level=s.choice_level) for s in subclasses_for(edition, class_key)]


@router.get("/proficiencies", response_model=ProficiencyGrantRead)
async def class_proficiency_grant(
    edition: Edition, class_key: str, as_multiclass: bool,
    _user: Annotated[int, Depends(get_current_user)], lang: Annotated[str, Depends(get_current_lang)],
) -> ProficiencyGrantRead:
    """Competenze che dà la classe (con elenco e numero delle abilità da scegliere)."""
    class_key = normalize_class_name(class_key) or class_key
    return ProficiencyGrantRead(**grant_to_dict(class_proficiencies(edition, class_key, as_multiclass), lang))


# ---------------------------------------------------------------------------
# Stato del turno
# ---------------------------------------------------------------------------

turn_router = APIRouter(prefix="/characters", tags=["rules"])


class TurnUse(BaseModel):
    slot: Literal["action", "bonus", "reaction", "free_interaction", "spell_slot", "bonus_spell", "attack"]
    used: bool = True  # False = annulla (correzione manuale)


async def _owned_char(db: AsyncSession, char_id: int, user_id: int) -> Character:
    char = await db.get(Character, char_id)
    if char is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Character not found")
    if char.user_id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return char


@turn_router.post("/{char_id}/turn/use", response_model=TurnBlock)
async def turn_use(
    char_id: int, body: TurnUse, user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    char = await _owned_char(db, char_id, user_id)
    return (spend if body.used else release)(char, body.slot)


@turn_router.post("/{char_id}/turn/new", response_model=TurnBlock)
async def turn_new(
    char_id: int, user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    char = await _owned_char(db, char_id, user_id)
    in_encounter = await active_encounter_row(db, char_id) is not None
    turn = reset_turn(char, keep_surprise=in_encounter, advances=not in_encounter)
    if not in_encounter:  # in un incontro l'inizio del turno lo dà il passaggio di turno, non questo pulsante
        await apply_turn_start(db, char)
        turn = get_turn(char)  # con l'avviso della cura d'inizio turno
    return turn


@turn_router.post("/{char_id}/turn/other", response_model=TurnBlock)
async def turn_other(
    char_id: int, user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Fuori da un incontro: è il turno di un altro, tornano gli effetti «una volta per turno»."""
    char = await _owned_char(db, char_id, user_id)
    clear_once_per_turn(char)
    return get_turn(char)


@turn_router.get("/{char_id}/roll-options", response_model=list[RollOptionRead])
async def roll_options(
    char_id: int,
    roll: Literal["attack", "spell_damage", "weapon_damage", "skill", "ability", "save", "initiative", "death_save",
                  "damage_taken", "cast", "spell_healing"],
    user_id: Annotated[int, Depends(get_current_user)],
    lang: Annotated[str, Depends(get_current_lang)],
    db: Annotated[AsyncSession, Depends(get_db)],
    item_id: int | None = None,
    spell_id: int | None = None,
    ability: str | None = None,
    skill: str | None = None,
    damage_type: str | None = None,
    attack_mode: Literal["melee", "thrown", "offhand"] = "melee",
    grip: Literal["one", "two"] = "one",
    casting_level: int | None = None,
    damage: int | None = None,
) -> list[RollOptionRead]:
    """Opzioni da chiedere al giocatore per questo tiro. Sola lettura: il server le riconvalida al tiro."""
    char = await _get_owned_full(char_id, user_id, db)
    item = next((i for i in char.items if i.id == item_id), None)
    spell = next((s for s in char.spells if s.id == spell_id), None)
    if (item_id is not None and item is None) or (spell_id is not None and spell is None):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    if roll == "initiative":
        ability = "dexterity"
    if roll in ("save", "death_save", "damage_taken"):
        await attach_party_auras(db, char)  # le aure dei compagni di serata (conferma al tiro)
    # Stesso contesto del tiro: un'opzione legata a caratteristica o modalità non deve sparire solo dall'elenco.
    attack: dict = {}
    if roll == "attack" and spell is None:
        if item is None:
            throw = attack_mode == "thrown"  # il lancio a distanza senz'armi (Deviare Proiettili)
            _, _, ability = unarmed_attack_profile(char, throw)
            attack = {"attack_mode": "ranged" if throw else "melee", "grip": "one"}
        else:
            _, ability, resolved_mode = weapon_attack_profile(char, item, attack_mode, ability)
            attack = {"attack_mode": resolved_mode, "grip": grip, "offhand": attack_mode == "offhand"}
    return list_options(char, roll, lang, item=item, spell=spell, skill=skill, casting_level=casting_level, **attack,
                        ability=ability or SKILL_ABILITY_MAP.get(skill), damage_type=canonical_damage_type(damage_type),
                        damage=damage if roll == "damage_taken" else None)


def _refuse(code: str, **extra: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail={"code": code, **extra})


_HISTORY_EVENT = {"skill": "skill_roll", "ability": "skill_roll", "save": "saving_throw", "attack": "attack_roll", "initiative": "dice_roll",
                  "death_save": "death_save"}


@turn_router.post("/{char_id}/last-roll/options", response_model=LastRollResult)
async def last_roll_options(
    char_id: int, user_id: Annotated[int, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)],
    body: Annotated[LastRollBody | None, Body()] = None,
) -> LastRollResult:
    """Privilegi usati dopo aver visto il d20. Il tiro è quello salvato dal server, non quello del client."""
    char = await _get_owned_full(char_id, user_id, db)
    body = body or LastRollBody()
    turn = get_turn(char)
    last, pending = turn.get("last_roll"), turn.get("pending_attack")
    is_attack = bool(last) and last["roll"] == "attack"
    weapon_attack = is_attack and last["spell_id"] is None
    if not last or (weapon_attack and not pending):  # il danno è già stato tirato
        raise _refuse("no_last_roll")
    if last["auto_fail"]:
        raise _refuse("option_unavailable", key=(body.options or [""])[0])
    if used := set(body.options) & set(last.get("after_used", [])):  # un rimborso non la riapre: il bonus resta sul totale
        raise _refuse("option_unavailable", key=sorted(used)[0])
    save = await open_failed_save(db, char, last["pending_save_id"]) if last["pending_save_id"] else None
    conc, death = last.get("concentration"), last.get("death")
    if (conc and conc["lost"] and is_concentrating(char)) or (death and death_state(char) != death["after"]):
        raise _refuse("not_rerollable")  # lo stato è andato avanti
    combatant = await db.get(Combatant, last["combatant_id"]) if last.get("combatant_id") else None
    encounter = await db.get(Encounter, combatant.encounter_id) if combatant else None
    if last.get("combatant_id") and (encounter is None or encounter.status == "ended"):
        raise _refuse("no_last_roll")

    where = {"skill": last["skill"], "ability": last["ability"],
             "item": next((i for i in char.items if i.id == last["item_id"]), None),
             "spell": next((s for s in char.spells if s.id == last["spell_id"]), None)}
    grip = ({"attack_mode": pending["attack_mode"], "grip": pending["grip"], "offhand": pending.get("offhand", False)}
            if weapon_attack else {})
    await attach_party_auras(db, char)  # le aure dei compagni di serata (anche per il TS di concentrazione già tirato)
    opts = use_options(db, char, last["roll"], body, phase="after_roll", **where, **grip)

    applied = modifiers_for(char, last.get("modifier_roll") or last["roll"], **where,
                            **({"attack_mode": pending["attack_mode"]} if weapon_attack else {}))
    merge_options(applied, opts)
    die, dice, mode, bonus, total = last["die"], last["dice"], last["mode"], last["bonus"], last["total"]
    if opts.reroll:
        outcome = resolve_applied(body.mode, body.dice, None, applied)
        total += outcome.kept - die
        die, dice, mode = outcome.kept, outcome.dice, outcome.mode
        record_dice(char, d20_records(outcome))
    rolls, extra = roll_option_dice(char, opts)
    bonus += opts.bonus
    total += opts.bonus + extra
    forced_hit = last["forced_hit"] or (opts.succeed and is_attack)
    if opts.succeed and not is_attack:
        total += 20 - die
        die = 20
    raw_total = total  # il tiro salvato non porta il minimo (Potenza Indomabile): si rimette ogni volta sul totale
    if applied.min_total is not None:
        total = max(total, applied.min_total)
    is_fumble = die == 1 and not forced_hit
    is_critical = (die >= applied.crit_min or (AppliedOptions(**last["applied"]).force_crit and not is_fumble)
                   if is_attack else die == 20)
    notes = [*last["notes"], *(n for n in applied.notes if n not in last["notes"])]
    previous = OptionResult(**last["option_result"]) if last.get("option_result") else None
    block = option_result(opts, rolls, extra, previous=previous)
    refundable = {**last["refundable"], **opts.refundable}
    if opts.keys:
        _add_history(db, char.id, "concentration_save" if conc else _HISTORY_EVENT[last["roll"]],
                     f"Dopo il tiro ({', '.join(opts.keys)}): d20={die} {bonus:+d} = {total}")

    closed: dict = {}
    failed: bool | None = None  # noto al server: il rimborso non va chiesto
    if save:
        ps, effect = save
        read, passed = await close_pending_save(db, char, ps, effect, {
            "die": die, "dice": dice, "bonus": bonus, "total": total, "mode": mode, "auto_fail": False, "notes": notes})
        closed = {"save": read, "passed": passed, "condition_removed": passed}
        failed = not passed
    elif conc:
        closed["concentration"], conc = await retouch_concentration(db, char, conc, {
            "die": die, "dice": dice, "mode": mode, "mode_applied": mode, "bonus": bonus, "total": total, "notes": notes,
            "is_critical": is_critical, "is_fumble": is_fumble, "option_result": block})
        failed = not closed["concentration"].success
    elif death:
        closed["death"], death = await retouch_death_save(db, char, death, {
            "die": die, "dice": dice, "mode": mode, "total": total, "notes": notes, "option_result": block})
        failed = closed["death"].outcome in ("failure", "nat1")
    elif combatant:
        combatant.initiative, combatant.initiative_die = total, die
        _touch(await db.get(GameSession, encounter.session_id))
    if failed is not None:
        if failed:
            refund_spent(char, [token for spent in refundable.values() for token in spent])
        refundable = {}

    attack = None
    if weapon_attack:
        attack = retouch_pending_attack(char, pending, last["applied"], {
            "die": die, "dice": dice, "mode": mode, "total": total, "is_critical": is_critical, "is_fumble": is_fumble,
            "forced_hit": forced_hit, "notes": notes, "option_result": block})
        if opts.miss_damage is not None:  # dichiarato mancato: si rimborsa ciò che si paga solo se il tiro riesce
            attack = close_grazed_attack(char, attack, opts.miss_damage)
            refund_spent(char, [token for spent in refundable.values() for token in spent])
            refundable = {}

    turn = get_turn(char)  # pagamenti e attacco in sospeso hanno riscritto il turno
    turn["last_roll"] = {**last, "die": die, "dice": dice, "mode": mode, "bonus": bonus, "total": raw_total, "notes": notes,
                         "forced_hit": forced_hit, "refundable": refundable, "concentration": conc, "death": death,
                         "after_used": [*last.get("after_used", []), *opts.keys],
                         "option_result": block.model_dump(mode="json") if block else None}
    char.turn_state = turn
    result = LastRollResult(
        die=die, dice=dice, mode=mode, mode_applied=mode, notes=notes, bonus=bonus, total=total,
        is_critical=is_critical, is_fumble=is_fumble, description=last["description"], option_result=block,
        refundable=list(refundable) or None, forced_hit=forced_hit or None, attack=attack, **closed,
    )
    await db.commit()  # get_db chiude dopo la risposta: il client rilegge subito il turno per la domanda sul rimborso
    return result


@turn_router.post("/{char_id}/last-roll/refund", response_model=TurnBlock)
async def last_roll_refund(
    char_id: int, user_id: Annotated[int, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)],
    body: Annotated[LastRollRefund | None, Body()] = None,
) -> dict:
    """Il giocatore dichiara l'esito: se è fallito tornano le opzioni che si pagano solo se riesce."""
    char = await _get_owned_full(char_id, user_id, db)
    last = get_turn(char).get("last_roll") or {}
    refundable = last.get("refundable")
    if not refundable:
        raise _refuse("nothing_to_refund")
    if not (body and body.succeeded):
        refund_spent(char, [token for spent in refundable.values() for token in spent])
        _add_history(db, char.id, _HISTORY_EVENT[last["roll"]], f"Tiro fallito, rimborsato: {', '.join(refundable)}")
    turn = {**get_turn(char), "last_roll": {**last, "refundable": {}}}
    char.turn_state = turn
    await db.commit()  # come sopra: una rilettura immediata non deve riproporre la domanda
    return turn


# ---------------------------------------------------------------------------
# Uso dei privilegi e stati attivi
# ---------------------------------------------------------------------------

class FeatureUse(BaseModel):
    amount: int = Field(1, ge=1)
    params: dict | None = None


class FeatureUseResult(BaseModel):
    rolls: list[int] = []
    healed: int = 0
    state: dict | None = None
    notes: list[str] = []
    targets: list[str] = []
    given: int | None = None  # valore da dare a un altro (PF temporanei di Incoraggiamento), mai scritto sulla scheda
    received: dict | None = None  # chi ha ricevuto una cura dal privilegio (Imposizione delle Mani): name, healed


@turn_router.post("/{char_id}/features/{feature_key}/use", response_model=FeatureUseResult)
async def feature_use(
    char_id: int, feature_key: str, body: FeatureUse, user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FeatureUseResult:
    char = await _get_owned_full(char_id, user_id, db)
    res = await use_feature(db, char, feature_key, body.amount, body.params)
    return FeatureUseResult(rolls=res.rolls, healed=res.healed, state=res.state, notes=res.notes, targets=res.targets,
                            given=res.given, received=res.received)


class PreserveLifeBody(BaseModel):
    allocations: list[dict[str, int]] = Field(min_length=1, max_length=12)  # [{character_id, amount}]
    confirm_living: bool = False  # il giocatore dichiara che nessuno è un costrutto né un non morto


class PreserveLifeResult(BaseModel):
    pool: int
    spent: int
    healed: list[dict]


@turn_router.post("/{char_id}/preserve-life", response_model=PreserveLifeResult)
async def preserve_life_endpoint(
    char_id: int, body: PreserveLifeBody, user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PreserveLifeResult:
    """Preservare Vita (R42): distribuisce 5 × livello PF fra chi usa il privilegio e gli altri partecipanti della serata."""
    from dataclasses import asdict
    from api.services.preserve_life import preserve_life
    char = await _get_owned_full(char_id, user_id, db)
    try:
        allocations = [(int(a["character_id"]), int(a["amount"])) for a in body.allocations]
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "bad_allocation"})
    pool, done = await preserve_life(db, char, allocations, body.confirm_living)
    return PreserveLifeResult(pool=pool, spent=sum(a for _, a in allocations), healed=[asdict(h) for h in done])


class PreserveTarget(BaseModel):
    id: int
    name: str
    cap: int  # PF ancora curabili (metà dei massimi), mai oltre la riserva
    self: bool


class PreserveLifeInfo(BaseModel):
    pool: int
    uses_left: int | None
    targets: list[PreserveTarget]


@turn_router.get("/{char_id}/preserve-life", response_model=PreserveLifeInfo)
async def preserve_life_info(
    char_id: int, user_id: Annotated[int, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)],
) -> PreserveLifeInfo:
    """Per il pannello di Preservare Vita: la riserva e il tetto di ciascun destinatario, calcolati dal server e solo
    per chi può usare il privilegio adesso."""
    from dataclasses import asdict
    from api.services.preserve_life import info
    res = await info(db, await _get_owned_full(char_id, user_id, db))
    return PreserveLifeInfo(pool=res.pool, uses_left=res.uses_left, targets=[asdict(t) for t in res.targets])


class SurgeBody(BaseModel):
    die: int | None = Field(default=None, ge=1, le=20)  # il d20, se l'ha già tirato il client
    percentile: list[int] | None = Field(default=None, max_length=2)  # i d100, se già tirati
    tides: bool = False  # il GM fa tirare la tabella dopo Onde di Caos: niente d20


class SurgeChoose(BaseModel):
    index: int = Field(ge=0, le=1)


class SurgeResult(BaseModel):
    die: int | None
    triggered: bool
    pending: bool  # Caos Controllato: due risultati, il giocatore sceglie
    options: list[dict]
    applied: dict | None
    tides_restored: bool


@turn_router.post("/{char_id}/wild-magic/surge", response_model=SurgeResult)
async def wild_magic_surge(
    char_id: int, body: SurgeBody, user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Impulso di Magia Selvaggia: d20 una volta per turno e, con 1, la tabella dei 50 impulsi."""
    from api.services.wild_magic import roll_surge
    if body.percentile is not None and any(not 1 <= p <= 100 for p in body.percentile):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "bad_percentile"})
    char = await _get_owned_full(char_id, user_id, db)
    return await roll_surge(db, char, body.die, body.percentile, body.tides)


@turn_router.post("/{char_id}/wild-magic/surge/choose", response_model=SurgeResult)
async def wild_magic_choose(
    char_id: int, body: SurgeChoose, user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Caos Controllato: il giocatore sceglie fra i due risultati tirati."""
    from api.services.wild_magic import choose_surge
    char = await _get_owned_full(char_id, user_id, db)
    return await choose_surge(db, char, body.index)


class AllyRead(BaseModel):
    id: int
    name: str
    die: int | None = None  # il dado di Ispirazione che ha già: darne un altro lo sostituisce


@turn_router.get("/{char_id}/session-allies", response_model=list[AllyRead])
async def session_allies(
    char_id: int, user_id: Annotated[int, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AllyRead]:
    """Gli altri personaggi seduti alla stessa serata attiva: a chi dare il dado di Ispirazione. Vuoto fuori serata."""
    char = await _owned_char(db, char_id, user_id)
    def held(a: Character) -> int | None:
        state = next((s for s in a.active_states or [] if s.get("key") == BARDIC_DIE), None)
        die = ((state or {}).get("data") or {}).get("die")
        return die if isinstance(die, int) else None

    return [AllyRead(id=a.id, name=a.name, die=held(a))
            for a in await seated_allies(db, char)]


class BardicDieAc(BaseModel):
    die: int
    roll: int


@turn_router.post("/{char_id}/bardic-die/ac", response_model=BardicDieAc)
async def bardic_die_ac(
    char_id: int, user_id: Annotated[int, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)],
) -> BardicDieAc:
    """Ispirazione in Combattimento (Collegio del Valore): in reazione, il dado ricevuto si somma alla CA contro un attacco.
    Spende la reazione e il dado; il valore da sommare lo dice la risposta. Con la reazione già spesa non perde il dado."""
    char = await _get_owned_full(char_id, user_id, db)
    refuse_if_incapacitated(char)
    state = next((s for s in char.active_states or [] if s.get("key") == BARDIC_DIE), None)
    if state is None or not (state.get("data") or {}).get("combat"):
        raise _refuse("not_available")
    spend(char, "reaction")
    die = int(state["data"]["die"])
    roll = random.randint(1, die)
    record_dice(char, [(f"d{die}", roll)])
    remove_state(char, BARDIC_DIE)
    _add_history(db, char.id, "dice_roll", f"Ispirazione in Combattimento: +{roll} alla CA (d{die})")
    return BardicDieAc(die=die, roll=roll)


@turn_router.delete("/{char_id}/active-states/{key}", response_model=list[dict])
async def end_active_state(
    char_id: int, key: str, user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    char = await _get_owned_full(char_id, user_id, db)
    form = await get_active_form(db, char.id) if key == WILD_SHAPE_STATE else None
    if form is not None:  # il ritorno alla forma normale ha un solo percorso, con il suo costo (come «Termina» da Extra)
        return_to_normal(char, form)
        return char.active_states
    remove_state(char, key, by_player=True)
    return char.active_states


# ---------------------------------------------------------------------------
# Effetti su altri combattenti (D1)
# ---------------------------------------------------------------------------

async def _active_encounter(db: AsyncSession, char_id: int) -> tuple[Encounter, Combatant] | None:
    row = await active_encounter_row(db, char_id)
    if row is None:
        return None
    enc = (await db.execute(select(Encounter).options(selectinload(Encounter.combatants))
                            .where(Encounter.id == row[0].id))).scalar_one()
    return enc, next(c for c in enc.combatants if c.id == row[1])


@turn_router.get("/{char_id}/target-effects/{effect_key}", response_model=TargetEffectPreview)
async def target_effect_preview(
    char_id: int, effect_key: str, user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TargetEffectPreview:
    char = await _owned_char(db, char_id, user_id)
    found = await _active_encounter(db, char_id)
    effect = pending_target_effect(char, effect_key)
    return TargetEffectPreview(
        result=TargetEffectRead(**effect),
        combatants=[TargetCandidate(id=c.id, name=c.name, kind=c.kind,
                                    immune=bool(effect.get("immune_on_success")) and is_target_immune(char, effect_key, c))
                    for c in sorted(found[0].combatants, key=lambda c: c.sort_order or 0) if not c.is_dead] if found else [],
    )


@turn_router.post("/{char_id}/target-effects", response_model=TargetEffectResult)
async def target_effect_apply(
    char_id: int, body: TargetEffectBody, user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TargetEffectResult:
    """Applica al combattente scelto l'effetto confermato col tiro. Fuori da un incontro attivo restituisce solo l'esito."""
    char = await _owned_char(db, char_id, user_id)
    result = TargetEffectRead(**pending_target_effect(char, body.effect_key))
    found = await _active_encounter(db, char_id)
    if found is None:
        return TargetEffectResult(applied=False, result=result)
    enc, mine = found
    target = next((c for c in enc.combatants if c.id == body.combatant_id), None)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Combatant not found")
    applied, save = await apply_target_effect(db, char, enc, mine, target, body.effect_key)
    _touch(await db.get(GameSession, enc.session_id))
    await db.flush()
    if save is not None:
        await _notify_saves(db, [save.id])
    return TargetEffectResult(applied=applied, result=result, target_name=target.name,
                              pending_save_id=save.id if save else None)

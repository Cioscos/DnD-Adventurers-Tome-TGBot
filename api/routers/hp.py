"""HP, rest, and death save endpoints."""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.services.history import add_history
from api.auth import get_current_lang, get_current_user
from api.database import get_db
from api.services.d20 import d20_records, resolve_applied, resolve_body
from api.services.dice_stats import record_dice
from api.services.effects import apply_conditions, apply_heal, cap_current_hp, end_knock_out, sync_zero_hp
from api.services.item_charges import plan_item_recharges, set_item_charges
from api.services.beast_companion import drop_primal_beast, long_rest_beast
from api.services.wild_shape import long_rest_familiar
from api.services.durations import end_concentration, is_concentrating
from api.services.memorize import memorize
from api.services.natural_recovery import ARCANE_FEATURE, recover as recover_slots, restore_points
from core.rules.arcane_ward import absorb as absorb_ward
from core.rules.roll_options import set_saved_dice
from core.rules.school_hooks import concentration_safe
from api.services.rules_states import end_states_on_rest, on_damage
from api.services.song_of_rest import roll_song_of_rest
from api.services.spell_slots import clear_created_slots
from api.services.rules_turn import get_turn, set_damaged
from api.services.session_allies import load_receiver, attach_party, attach_party_auras, attach_spell_auras, refund_donor_tokens, spend_donor_tokens
from api.services import ally_reactions
from api.services.condition_effects import release_concentration_effects
from api.services.spell_effects import regrant_spells
from core.rules.catalog.spells.hitpoints import DEATH_WARD_HOLD
from api.services.spell_hp import drop_orphan_spell_states, foreign_spell_clocks, reopen_spell_clocks, spell_damage_effects
from api.services.wild_shape import absorb_damage, deactivate_other_forms, end_form, form_own_hp, get_active_form
from api.services.telegram_notify import notify_party_emergency
from api.services.homebrew.dispatcher import dispatch
from api.services.homebrew.passive import get_passive_modifiers
from core.db.models import Character, CharacterHistory, Companion
from api.schemas.character import CharacterFull
from api.schemas.common import (
    D20RollSubmission,
    DeathSaveRollResult,
    DeathSaveUpdate,
    DeathSaveAction,
    HPOp,
    HPUndoRequest,
    HPUpdate,
    ItemChargePreview,
    RestPreview,
    RestRequest,
)
from core.data.damage_types import LABELS_IT, apply_damage_mode, canonical_damage_type
from api.services.hp_rolls import stored_rolls
from core.game.stats import total_base_hp
from core.rules.edition import character_edition
from core.rules.modifiers import damage_taken_mode, effective_hp_max, exhaustion_level, modifiers_for
from core.rules.roll_options import refund_spent, run_zero_damage_hooks, scale_damage
from api.services.rules_options import (
    merge_options,
    option_result,
    reaction_offers,
    remember_roll,
    roll_option_dice,
    use_options,
)
from api.routers._helpers import (
    collect_homebrew_notifications, effective_con_mod, roll_concentration_save, saving_throw_bonus,
)
from api.schemas.common import ConcentrationSaveResult, OptionResult, ZeroHpSaveResult
from core.rules.catalog import active_features
from core.rules.states import (
    SPELL_GIVEN, TEMP_GIVEN, ZERO_HP_USES, begin_state, forget_spell_temp_drop, has_state, reset_target_immunity, reset_zero_hp_uses, restore_exhaustion,
)
from core.rules.types import RuleContext, StateSpec
from api.services.character_response import build_character_response
from api.services.character_load import get_owned_full_with_resources


class HitDiceSpendRequest(BaseModel):
    class_id: int
    count: int
    # Facce lette dai dadi 3D; senza, tira il server.
    rolls: list[int] | None = None


class HitDiceSpendResult(BaseModel):
    rolls: list[int]
    con_bonus: int
    healed: int
    new_current_hp: int
    homebrew_notifications: Optional[list[dict]] = None
    # Canto di Riposo di un bardo al tavolo: il dado extra (già compreso in `healed`)
    song_die: Optional[int] = None
    song_rolls: list[int] = []

router = APIRouter(prefix="/characters", tags=["hp"])


def _utcnow() -> datetime:
    return datetime.utcnow()


def _now() -> str:
    return _utcnow().isoformat(timespec="seconds")


_CONC_SETTINGS = ("concentration_rounds_left", "concentration_item_spell", ZERO_HP_USES, TEMP_GIVEN, SPELL_GIVEN)  # + il conteggio di Ira Implacabile


def _hp_state(char: Character, form=None) -> dict:
    """Campi toccati da un'operazione PF (forma selvatica inclusa), per lo snapshot di annullamento."""
    return {
        "form": None if form is None else {
            "form_id": form.id, "current_hp": form.current_hp,
            "temp_hp": form.temp_hp, "is_active": form.is_active,
        },
        "current_hit_points": char.current_hit_points,
        "hit_points": char.hit_points,
        "temp_hp": char.temp_hp,
        "death_saves": dict(char.death_saves or {}),
        "is_dead": char.is_dead,
        "concentrating_spell_id": char.concentrating_spell_id,
        # lo stato della forma sta a parte: attivare un'altra forma dopo l'operazione non impedisce l'annullamento
        "active_states": [s for s in char.active_states or [] if s["key"] != "wild_shape"],
        "form_state": next((s for s in char.active_states or [] if s["key"] == "wild_shape"), None),
        "damaged": get_turn(char)["damaged"],
        **{k: (char.settings or {}).get(k) for k in _CONC_SETTINGS},
    }


def _zero_conditions(char: Character) -> dict:
    """Ciò che i PF a 0 scrivono da soli: l'annullamento lo rimette com'era."""
    conditions = char.conditions or {}
    return {"unconscious": bool(conditions.get("unconscious")), "prone": bool(conditions.get("prone")),
            "knocked_out": bool((char.settings or {}).get("knocked_out")),
            "exhaustion": exhaustion_level(char)}  # lo addebita la fine di uno stato (Frenesia)


# ---------------------------------------------------------------------------
# HP update
# ---------------------------------------------------------------------------

async def _zero_hp_save(session: AsyncSession, char: Character) -> ZeroHpSaveResult | None:
    """Sceso a 0 PF senza morire sul colpo: il privilegio con ``zero_hp_save`` (Ira Implacabile) tira il suo TS.
    Se riesce i PF tornano al valore del privilegio e il personaggio non è né a terra né privo di sensi."""
    found = next(((s, r) for s, r in active_features(char) if s.zero_hp_save and has_state(char, s.zero_hp_save.state)), None)
    if found is None:
        return None
    spec, row = found
    rule = spec.zero_hp_save
    uses = dict((char.settings or {}).get(ZERO_HP_USES) or {})
    done = uses.get(spec.key, 0)
    dc = rule.base_dc + rule.step * done
    bonus = await saving_throw_bonus(session, char, rule.ability)
    applied = modifiers_for(char, "save", ability=rule.ability)
    outcome = resolve_applied("normal", None, None, applied)
    record_dice(char, d20_records(outcome))
    total = outcome.kept + bonus
    success = total >= dc and not applied.auto_fail
    char.settings = {**(char.settings or {}), ZERO_HP_USES: {**uses, spec.key: done + 1}}
    hp = max(1, rule.hp(RuleContext(char=char, edition=character_edition(char), class_row=row, class_level=row.level)))
    if success:
        char.current_hit_points = min(hp, effective_hp_max(char))
    name = spec.name["it"]
    add_history(session, char.id, "death_save",
                 f"{name}: TS {rule.ability} CD {dc}, {outcome.kept}{bonus:+d} = {total} "
                 f"({'riuscito: resta in piedi' if success else 'fallito'})")
    return ZeroHpSaveResult(feature_key=spec.key, ability=rule.ability, die=outcome.kept, bonus=bonus, total=total,
                            dc=dc, success=success, hp=char.current_hit_points if success else 0)


@router.patch("/{char_id}/hp", response_model=CharacterFull)
async def update_hp(
    char_id: int,
    body: HPUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
    lang: Annotated[str, Depends(get_current_lang)],
) -> CharacterFull:
    char = await get_owned_full_with_resources(char_id, user_id, session)
    return await apply_hp_update(session, char, body, lang)


async def apply_hp_update(session: AsyncSession, char: Character, body: HPUpdate, lang: str,
                          shared_from: str | None = None, shared_out: dict | None = None) -> CharacterFull | None:
    """Un'operazione PF su ``char`` (già verificato). ``shared_from``: il danno è quello che un incantesimo gira a ``char``
    (Legame di Protezione): stessa strada del danno, ma senza rigirarlo e senza risposta (``None``); il testo va nello storico,
    il TS di concentrazione di ``char`` in ``shared_out["concentration_save"]``."""
    # Da morto ogni operazione PF è inerte (solo /revive riporta in vita).
    if char.is_dead:
        return None if shared_from else await build_character_response(session, char)
    if (body.options or body.ally_reaction_id is not None) and body.op != HPOp.DAMAGE:
        raise HTTPException(status_code=422, detail={"code": "options_only_on_damage"})
    form = await get_active_form(session, char.id)  # the form involved in this op, if any
    if form is not None and not form_own_hp(char):
        form = None  # 2024: la forma non ha PF propri, i danni vanno ai temporanei e ai PF del druido
    before = _hp_state(char, form)
    zero_before = _zero_conditions(char)
    option_block = None
    ally_req = None
    conc_result: ConcentrationSaveResult | None = None
    zero_save: ZeroHpSaveResult | None = None
    notifications: list[dict] = []
    clocks: list[dict] = []
    shared_info: list[dict] = []  # il danno girato al lanciatore e il suo TS di concentrazione, per la risposta del bersaglio
    damage_taken: int | None = None  # danno dopo resistenze, per il toast del client
    shared_log: list[dict] = []  # lo stato che il danno condiviso ha lasciato sui lanciatori: l'annullo lo rimette

    was_at_zero = char.current_hit_points == 0

    if body.op == HPOp.DAMAGE:
        # Danno applicato dopo resistenza/immunità/vulnerabilità, PRIMA di PF temporanei
        # e tiri salvezza morte (tutto il resto usa `applied`).
        slug = canonical_damage_type(body.damage_type)
        mod = body.damage_modifier
        raw = body.raw_value if body.raw_value is not None else body.value
        applied = body.value
        opts = None
        ally_req = await ally_reactions.consume(session, char, body.ally_reaction_id) if body.ally_reaction_id is not None else None
        ally_cut = ally_reactions.total_reduction(ally_req) if ally_req is not None else 0
        ally_block = await ally_reactions.donors_of(session, ally_req) if ally_req is not None else []
        if any(s.get("key") == "spell:death_ward" for s in char.active_states or []) and DEATH_WARD_HOLD not in body.options:
            # Interdizione alla Morte è automatica nel manuale: la conferma la dà il server (se il colpo non porta a 0 l'uso non si spende)
            body = body.model_copy(update={"options": [*body.options, DEATH_WARD_HOLD]})
        if body.options:
            # Moltiplicatori e riduzioni vengono prima di resistenza e vulnerabilità (ordine del manuale).
            await attach_party(session, char)  # aure e Dono dei Protettori dei compagni della serata
            clocks = await foreign_spell_clocks(session, char)  # prima della spesa: uno stato speso chiude l'orologio di chi l'ha lanciato
            opts = use_options(session, char, "damage_taken", body, phase="damage_in", damage_type=slug, damage_in=raw)
            rolls, reduction = roll_option_dice(char, opts)
            # dadi e bonus riducono il danno insieme: se il totale è negativo (Parata con Destrezza bassa) non lo aumenta
            option_after = max(0, scale_damage(raw, opts.multiplier) - max(0, reduction + opts.bonus) - ally_cut)  # con le riduzioni degli alleati
            option_block = option_result(opts, rolls, reduction, damage_before=raw, damage_after=option_after, allies=ally_block)
            # L'annotazione del client (`value` già dimezzato o raddoppiato) si ricalcola sul nuovo danno.
            raw = option_after
            applied = apply_damage_mode(raw, mod)
            if option_after == 0:  # il proiettile deviato si afferra (Deviare Proiettili)
                run_zero_damage_hooks(session, char, opts.keys)
        elif ally_cut:  # solo gli alleati: stesso punto, prima di resistenza e vulnerabilità
            option_after = max(0, raw - ally_cut)
            option_block = OptionResult(damage_before=raw, damage_after=option_after, allies=ally_block)
            raw = option_after
            applied = apply_damage_mode(raw, mod)
        if mod is None:
            await attach_spell_auras(session, char)  # la resistenza di un'aura viva dei compagni (Aura di Vita)
            # Senza tipo conta solo una resistenza a tutti i danni (Pietrificato).
            mod = damage_taken_mode(char, slug)
            if slug is not None or mod != "none":
                if not body.options and not ally_cut:
                    raw = body.value
                applied = apply_damage_mode(raw, mod)
        elif mod == "immune":
            applied = 0
        if opts is not None and opts.resistance and mod != "immune":
            # La resistenza conta una volta: quella di un'opzione (Aura di Interdizione) non si somma a una già presente.
            mod = {"none": "half", "double": "half_double"}.get(mod, mod)
            applied = apply_damage_mode(raw, mod)
            option_block.damage_after = applied
        # Wild shape: the form soaks the (already resistance-adjusted, using the
        # character's modifiers) damage first; only the overflow reaches the character
        # through the normal path below (temp HP, death rules, one concentration save).
        conc_damage = applied
        form_absorbed = False
        pre_form = damage_taken = applied
        form_overflow = 0
        if form is not None and applied > 0:
            overflow = absorb_damage(form, applied)
            if overflow > 0:
                form_overflow = overflow
                end_form(char, form)
                add_history(session, char.id, "companion_hp",
                             f"Forma selvatica terminata: {form.name} (danno in eccesso {overflow})")
                applied = conc_damage = overflow
            else:
                form_absorbed = True
                applied = 0
                add_history(session, char.id, "companion_hp",
                             f"{form.name}: -{conc_damage} → PF {form.current_hp}/{form.max_hp}, temp {form.temp_hp}")
                if form.current_hp == 0:  # 5e: the form ends at 0 HP, even with no overflow
                    end_form(char, form)
                    add_history(session, char.id, "companion_hp",
                                 f"Forma selvatica terminata: {form.name} (PF a 0)")
        amount = applied
        warded = absorb_ward(char, amount)  # l'Interdizione Arcana prende il danno al posto del mago, prima dei PF temporanei
        if warded:
            amount -= warded
            conc_damage -= warded  # il danno è andato alla interdizione: la concentrazione non è toccata
        had_temp = char.temp_hp > 0
        # Absorb temp HP first
        if char.temp_hp > 0:
            absorbed = min(char.temp_hp, amount)
            char.temp_hp -= absorbed
            amount -= absorbed
        old = char.current_hit_points
        held_at_one, held_by = False, []
        if opts is not None and opts.holds_at_one:  # Sentinella Imperitura: la conferma vale solo se il danno porta a 0 senza uccidere
            massive = not opts.holds_vs_massive and amount - old >= effective_hp_max(char, await get_passive_modifiers(session, char, "character.hit_points_max"))
            if old > 0 and amount >= old and not massive:
                kept = min(1 + opts.held_heal, effective_hp_max(char, await get_passive_modifiers(session, char, "character.hit_points_max")))
                amount, held_at_one = old - kept, True
                held_by = await spend_donor_tokens(session, char, opts.spent)  # l'uso del donatore, una volta sola
            else:  # il danno non arriva a 0 (o uccide sul colpo): l'uso non si spende
                paid = [token for tokens in opts.refundable.values() for token in tokens]
                refund_spent(char, paid)
                option_block.spent = [token for token in option_block.spent if token not in paid]
        char.current_hit_points = max(0, char.current_hit_points - amount)
        if option_block is not None and option_block.damage_before == option_block.damage_after:
            option_block.damage_before = option_block.damage_after = None  # nessuna riduzione (resta a 1 PF): niente «Danno 20 → 20»
        lost = old - char.current_hit_points if old > 0 else pre_form  # i PF davvero persi (non il colpo: temporanei, Interdizione, tenuto a 1)
        if held_at_one and option_block is not None:
            option_block.hp_lost = lost  # il toast dice quanti PF si sono persi, non il colpo intero
        knocked = False  # 2024: il tramortito resta a 1 PF, non è «sceso a 0»
        if slug is not None and mod in ("half", "double", "half_double", "immune"):
            word = {"half": "resistenza", "double": "vulnerabilità", "half_double": "resistenza e vulnerabilità",
                    "immune": "immunità"}[mod]
            desc = (f"Danno {raw} {LABELS_IT[slug]} → {pre_form} ({word}): -{lost} HP "
                    f"({old} → {char.current_hit_points})")
        else:
            note = ""
            if body.raw_value is not None and mod in ("half", "double", "half_double"):
                word = {"half": "dimezzati", "double": "raddoppiati", "half_double": "dimezzati e raddoppiati"}[mod]
                note = f" ({body.raw_value} {word})"
            desc = f"Danni: -{lost} HP{note} ({old} → {char.current_hit_points})"
        if form_overflow:
            desc += f" — forma assorbe {pre_form - form_overflow}, eccesso {form_overflow}"
        if warded:
            desc += f" — Interdizione Arcana assorbe {warded}"
        if ally_block:
            desc += " — ridotto da " + ", ".join(f"{d['name']} -{d['reduction']}" for d in ally_block)
        if shared_from:
            desc += f" — {shared_from}"
        if held_at_one:
            desc += (f" — resta a 1 PF grazie a {', '.join(d.name for d in held_by)}" if held_by
                     else " — Interdizione alla Morte: resta a 1 PF" if any(k.startswith("spell:") for k in opts.keys)
                     else " — Sentinella Imperitura: resta a 1 PF")
        if not form_absorbed:
            add_history(session, char.id, "hp_change", desc,
                         meta={"op": "DAMAGE", "amount": lost,  # come la riga di storico e il riepilogo di serata: PF persi, non il colpo
                               "to_zero": old > 0 and char.current_hit_points == 0})

        # --- Morte & tiri salvezza (D&D 5e RAW) ---
        if char.current_hit_points == 0 and amount > 0 and not char.is_dead:
            hb_max_bonus = await get_passive_modifiers(session, char, "character.hit_points_max")
            effective_max = effective_hp_max(char, hb_max_bonus)
            # sforamento = danno oltre quello che porta a 0
            overflow = (amount - old) if old > 0 else amount
            ds = dict(char.death_saves or {"successes": 0, "failures": 0, "stable": False})
            if overflow >= effective_max:
                char.is_dead = True
                await drop_primal_beast(session, char)
                add_history(session, char.id, "death_save", "Morte istantanea (danno massiccio)")
            elif old == 0:
                # Danno a una creatura stabile: torna morente con conteggio
                # fresco (RAW: i conteggi si azzerano quando si diventa stabili,
                # quindi i fallimenti pre-stabilizzazione non si sommano).
                if ds.get("stable", False):
                    ds = {"successes": 0, "failures": 0, "stable": False}
                # danno subìto già a 0 PF -> fallimenti (2 se colpo critico)
                inc = 2 if body.was_critical_hit else 1
                ds["failures"] = min(3, ds.get("failures", 0) + inc)
                ds["stable"] = False
                if ds["failures"] >= 3:
                    char.is_dead = True
                    await drop_primal_beast(session, char)
                    add_history(session, char.id, "death_save", "Morto — 3 fallimenti (danno a 0 PF)",
                                 meta={"ds": "failure", "n": inc})
                else:
                    add_history(session, char.id, "death_save",
                                 f"Danno a 0 PF: +{inc} fallimento ({ds['failures']}/3)",
                                 meta={"ds": "failure", "n": inc})
                char.death_saves = ds
            elif (zero_save := await _zero_hp_save(session, char)) is not None and zero_save.success:
                pass  # Ira Implacabile: resta in piedi, nessuna morte da tracciare
            else:
                # old>0 ridotto a 0 senza sforamento massiccio -> privo di sensi/
                # morente con tracker fresco. L'azzeramento esplicito ripulisce
                # anche un eventuale "stable" stantio (RAW: chi scende a 0 HP
                # ricomincia a morire da capo).
                char.death_saves = {"successes": 0, "failures": 0, "stable": False}
                if body.knock_out:
                    knocked = True
                    if character_edition(char) == "2024":
                        char.current_hit_points = 1
                        char.settings = {**(char.settings or {}), "knocked_out": True}
                        await apply_conditions(session, char, {"unconscious": True, "prone": True})
                    else:
                        char.death_saves = {"successes": 0, "failures": 0, "stable": True}
                    add_history(session, char.id, "hp_change", "Tramortito: non muore, è privo di sensi")

        await sync_zero_hp(session, char, was_at_zero)

        # Notifica best-effort ai compagni di sessione (categoria party_emergency)
        if char.current_hit_points == 0 and amount > 0:
            if char.is_dead:
                await notify_party_emergency(session, char, f"💀 {char.name} è morto!")
            elif old > 0:
                await notify_party_emergency(
                    session, char, f"🩸 {char.name} è a terra (0 PF)!")

        # Privo di sensi (0 PF) => fine concentrazione (RAW)
        if char.current_hit_points == 0:
            end_concentration(char)

        on_damage(char, applied)
        notifications.extend(await spell_damage_effects(session, char, applied, had_temp, lang, share=shared_from is None, shared_log=shared_log, shared_info=shared_info))  # ritorsione, danno condiviso, fine degli incantesimi

        # Auto concentration save — only if still conscious and concentrating
        if (
            conc_damage > 0
            and is_concentrating(char)
            and char.current_hit_points > 0
            and not concentration_safe(char)
        ):
            conc_result = await roll_concentration_save(
                char, conc_damage, session,
                "advantage" if (char.settings or {}).get("war_caster") else "normal",
            )
        await release_concentration_effects(session, char)

        # Emit homebrew events: damage_taken (always) + dropped_to_zero (when HP crossed 0).
        # event.amount is the GROSS damage requested (applied, before temp-HP
        # absorption); the actual HP lost is current_hp_before - current_hp_after. This
        # is the canonical semantics — actions.execute_damage_character matches it (#29).
        if applied > 0:
            firing = await dispatch(
                session, char, "damage_taken",
                {
                    "amount": applied,
                    "was_critical_hit": body.was_critical_hit,
                    "current_hp_before": old,
                    "current_hp_after": char.current_hit_points,
                },
            )
            notifications.extend(collect_homebrew_notifications(firing))
        if old > 0 and char.current_hit_points == 0 and not knocked:
            firing = await dispatch(
                session, char, "dropped_to_zero",
                {
                    "damage_amount": applied,
                    "from_critical": body.was_critical_hit,
                },
            )
            notifications.extend(collect_homebrew_notifications(firing))

    elif body.op == HPOp.HEAL:
        # Shared applier (see api/services/effects.py). The bottom-of-function
        # death-save reset block stays as an idempotent no-op: apply_heal already
        # zeroed the saves, so its guard finds nothing to reset and won't double-log.
        if form is not None:  # while transformed, healing goes to the form
            form.current_hp = min(form.max_hp, form.current_hp + body.value)
            add_history(session, char.id, "companion_hp",
                         f"{form.name}: +{body.value} → PF {form.current_hp}/{form.max_hp}")
        else:
            result = await apply_heal(session, char, body.value)
            notifications.extend(collect_homebrew_notifications(result["firing"]))

    elif body.op == HPOp.SET_MAX:
        old = char.hit_points
        char.hit_points = max(0, body.value)
        await cap_current_hp(session, char, always=True)  # taglia al massimo effettivo, non a quello base
        add_history(session, char.id, "hp_change",
                     f"HP max impostati: {old} → {char.hit_points}",
                     meta={"op": "SET_MAX"})

    elif body.op == HPOp.SET_CURRENT:
        old = char.current_hit_points
        hb_max_bonus = await get_passive_modifiers(session, char, "character.hit_points_max")
        char.current_hit_points = max(0, min(effective_hp_max(char, hb_max_bonus), body.value))
        add_history(session, char.id, "hp_change",
                     f"HP correnti impostati: {old} → {char.current_hit_points}",
                     meta={"op": "SET_CURRENT"})
        if char.current_hit_points > old:
            await end_knock_out(session, char)  # il tramortito 2024 sta a 1 PF: salire lo sveglia

    elif body.op == HPOp.SET_TEMP:
        char.temp_hp = max(0, body.value)

    if (
        body.op in (HPOp.SET_MAX, HPOp.SET_CURRENT)
        and char.current_hit_points == 0
        and form is not None
        and form.is_active
    ):
        end_form(char, form)
        add_history(session, char.id, "companion_hp",
                     f"Forma selvatica terminata: {form.name} (PF a 0)")

    if body.op == HPOp.SET_CURRENT:  # SET_MAX non tocca i PF correnti: un personaggio appena creato non è «a terra»
        await sync_zero_hp(session, char, was_at_zero)

    # Auto-reset death saves when rising from 0 HP
    if was_at_zero and char.current_hit_points > 0:
        ds = dict(char.death_saves or {})
        if ds.get("successes", 0) > 0 or ds.get("failures", 0) > 0 or ds.get("stable", False):
            char.death_saves = {"successes": 0, "failures": 0, "stable": False}
            add_history(session, char.id, "death_save",
                         "Tiri salvezza morte azzerati (HP risaliti sopra 0)")

    # Nuovo dict (non mutazione in place): la colonna JSON non è tracciata.
    op_id = uuid.uuid4().hex
    char.hp_undo = {"op_id": op_id, "before": before, "after": _hp_state(char, form),
                    "spent": option_block.spent if option_block else [], "ally_reaction_id": ally_req.id if ally_req is not None else None, "zero_before": zero_before,
                    "zero_after": _zero_conditions(char), "shared": shared_log,
                    "clocks": [c for c in clocks if any(t.startswith(f"state:{c['key']}:") for t in (option_block.spent if option_block else []))]}
    if shared_from:
        if shared_out is not None:
            shared_out["concentration_save"] = conc_result
        return None

    result = await build_character_response(session, char)
    result.hp_undo_id = op_id
    result.damage_taken = damage_taken
    if body.op == HPOp.DAMAGE and char.current_hit_points > 0:  # privo di sensi non si reagisce
        result.reactions = reaction_offers(char, lang)
    result.option_result = option_block
    if conc_result is not None:
        result.concentration_save = conc_result
    if shared_info:
        result.shared_damage = shared_info[0]
    if zero_save is not None:
        result.zero_hp_save = zero_save
    if notifications:
        result.homebrew_notifications = notifications
    return result


async def _undo_form(session: AsyncSession, char: Character, snap: dict | None):
    """La forma selvatica coinvolta nell'operazione da annullare, se c'è."""
    if snap and (snap.get("after") or {}).get("form"):
        return (await session.execute(select(Companion).where(
            Companion.id == snap["after"]["form"]["form_id"], Companion.character_id == char.id,
        ))).scalar_one_or_none()
    return None


def _undo_applies(char: Character, snap: dict, form) -> bool:
    return {**_hp_state(char, form), "form_state": None} == {**snap.get("after", {}), "form_state": None}


async def undo_op_id(session: AsyncSession, char: Character) -> str | None:
    """L'``op_id`` annullabile ora (stessa condizione di ``POST /hp/undo``), altrimenti None."""
    snap = char.hp_undo
    if snap and _undo_applies(char, snap, await _undo_form(session, char, snap)):
        return snap.get("op_id")
    return None


async def _restore_hp(session: AsyncSession, char: Character, snap: dict, form, note: str | None = None) -> None:
    """Rimette ``char`` com'era prima dell'operazione descritta da ``snap``."""
    before = snap["before"]
    if before.get("form"):
        form.current_hp = before["form"]["current_hp"]
        form.temp_hp = before["form"]["temp_hp"]
        form.is_active = before["form"]["is_active"]
        if form.is_active:  # at most one active form
            await deactivate_other_forms(session, char.id, form.id)
    old = char.current_hit_points
    char.current_hit_points = before["current_hit_points"]
    char.hit_points = before["hit_points"]
    await cap_current_hp(session, char)  # la spossatezza può essere cambiata dopo l'operazione
    char.temp_hp = before["temp_hp"]
    char.death_saves = dict(before["death_saves"])
    char.is_dead = before["is_dead"]
    spell_id = before["concentrating_spell_id"]
    # L'incantesimo può essere stato eliminato nel frattempo.
    if spell_id is not None and not any(s.id == spell_id for s in char.spells):
        spell_id = None
    char.concentrating_spell_id = spell_id
    now_form_state = next((s for s in char.active_states or [] if s["key"] == "wild_shape"), None)
    char.active_states = list(before.get("active_states") or [])
    if before.get("form_state"):  # anche nel 2024, dove `form` è None: la forma torna con lo stato e i PF temporanei
        char.active_states = [*char.active_states, before["form_state"]]
        restored = await session.get(Companion, before["form_state"]["data"].get("companion_id"))
        if restored is not None and restored.character_id == char.id:
            restored.is_active = True
            await deactivate_other_forms(session, char.id, restored.id)
    elif now_form_state is not None:  # un'altra forma attivata dopo l'operazione resta
        char.active_states = [*char.active_states, now_form_state]
    set_damaged(char, before.get("damaged", False))
    await release_concentration_effects(session, char)
    returned: list[str] = []
    refund_spent(char, snap.get("spent") or [])
    await refund_donor_tokens(session, char, snap.get("spent") or [])
    if snap.get("ally_reaction_id"):  # reazione e usi dei donatori tornano con il danno annullato
        ally_req = await session.get(ally_reactions.Req, snap["ally_reaction_id"])
        if ally_req is not None:
            returned = await ally_reactions.refund(session, ally_req, "annullo")
    await reopen_spell_clocks(session, snap.get("clocks") or [])  # lo stato di un incantesimo altrui è tornato: torna l'orologio di chi l'ha lanciato
    settings = dict(char.settings or {})
    still_given = settings.get(TEMP_GIVEN) or {}
    for key, entries in (before.get(TEMP_GIVEN) or {}).items():  # l'Ira chiusa dal danno riapre: tornano i PF temporanei dati con essa
        if key in still_given or not has_state(char, key):
            continue
        for entry in entries:
            receiver = await session.get(Character, entry["id"])
            if receiver is not None and (receiver.temp_hp or 0) < entry["amount"]:
                add_history(session, receiver.id, "hp_change", f"PF temporanei tornati: il danno di {char.name} è stato annullato ({receiver.temp_hp or 0} → {entry['amount']})",
                             meta={"op": "TEMP_HP", "amount": entry["amount"], "restored": True})
                receiver.temp_hp = entry["amount"]
    await regrant_spells(session, char, before.get(SPELL_GIVEN))  # gli effetti degli incantesimi dati ad altri tornano con l'orologio
    settings = dict(char.settings or {})
    for k in _CONC_SETTINGS:
        if k not in before or k == SPELL_GIVEN:  # snapshot salvato prima che la chiave esistesse: non la tocca; SPELL_GIVEN lo riscrive ``regrant_spells`` (solo i bersagli ancora esistenti)
            continue
        if before[k] is None:
            settings.pop(k, None)
        else:
            settings[k] = before[k]
    char.settings = settings
    zero, zero_after = snap.get("zero_before"), snap.get("zero_after")
    if zero and zero_after:  # solo ciò che l'operazione ha scritto torna com'era; il resto è di chi l'ha messo
        changed = {k for k in zero if zero[k] != zero_after.get(k, zero[k])}
        conditions = dict(char.conditions or {})
        for k in changed & {"unconscious", "prone"}:
            conditions[k] = zero[k]
        char.conditions = conditions
        if "exhaustion" in changed:  # si toglie solo ciò che l'operazione ha addebitato
            restore_exhaustion(char, max(0, exhaustion_level(char) - (zero_after["exhaustion"] - zero["exhaustion"])))
        if "knocked_out" in changed:
            settings = {k: v for k, v in (char.settings or {}).items() if k != "knocked_out"}
            char.settings = {**settings, "knocked_out": True} if zero["knocked_out"] else settings
    char.hp_undo = None

    add_history(session, char.id, "hp_change",
                 (note or f"Annullata ultima operazione PF ({old} → {char.current_hit_points})")
                 + (f" — reazioni rimborsate a {', '.join(returned)}" if returned else ""),
                 meta={"op": "UNDO"})


@router.post("/{char_id}/hp/undo", response_model=CharacterFull)
async def undo_hp(
    char_id: int,
    body: HPUndoRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CharacterFull:
    """Annulla l'ultima operazione PF, solo se nulla è cambiato dopo di essa. Il danno condiviso da un incantesimo
    (Legame di Protezione) si annulla anche sulla scheda del lanciatore, se è ancora com'era dopo il danno."""
    char = await get_owned_full_with_resources(char_id, user_id, session)
    snap = char.hp_undo
    form = await _undo_form(session, char, snap)
    if not snap or snap.get("op_id") != body.op_id or not _undo_applies(char, snap, form):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="hp_undo_not_applicable")
    shared = snap.get("shared") or []
    await _restore_hp(session, char, snap, form)
    await drop_orphan_spell_states(session, char)  # il lanciatore cancellato: il suo stato non torna
    for entry in shared:
        try:
            caster = await load_receiver(session, entry["id"])
        except NoResultFound:  # il lanciatore è stato cancellato: si annulla solo la parte del bersaglio
            continue
        caster_form = await _undo_form(session, caster, entry)
        if _undo_applies(caster, entry, caster_form):
            await _restore_hp(session, caster, entry, caster_form, f"Annullato il danno condiviso con {char.name}")
    return await build_character_response(session, char)


# ---------------------------------------------------------------------------
# Rest
# ---------------------------------------------------------------------------

def _restores_ability(ability, rest_type: str) -> bool:
    if ability.max_uses is None:
        return False
    if rest_type == "short" and ability.short_rest_recovers:
        return True
    # A long rest includes short-rest benefits; le ex-risorse di classe sono Ability.
    types = ("long_rest", "short_rest") if rest_type == "long" else ("short_rest",)
    return ability.restoration_type in types


def _restore_ability(ability, rest_type: str) -> None:
    if rest_type == "short" and ability.short_rest_recovers:
        ability.uses = min(ability.max_uses, (ability.uses or 0) + ability.short_rest_recovers)
    else:
        ability.uses = ability.max_uses


def _restores_resource(resource, rest_type: str) -> bool:
    types = ("long_rest", "short_rest") if rest_type == "long" else ("short_rest",)
    return resource.restoration_type in types


def _short_rest_exhaustion(char: Character) -> bool:
    exh = (char.conditions or {}).get("exhaustion", 0)
    return (isinstance(exh, int) and not isinstance(exh, bool) and exh > 0
            and any(spec.short_rest_exhaustion for spec, _row in active_features(char)))


def _apply_exhaustion_change(session: AsyncSession, char: Character, change: int, kind: str) -> None:
    conditions = dict(char.conditions or {})  # int mai False/None: il bug F04 del serializzatore dello storico
    old_exh = conditions["exhaustion"]
    conditions["exhaustion"] = old_exh + change
    char.conditions = conditions
    add_history(session, char.id, "condition_change", f"Spossatezza: livello {old_exh} → {old_exh + change} ({kind})",
                 meta={"slug": "exhaustion", "active": change > 0})


def compute_rest_effects(char: Character, rest_type: str, hp_max_bonus: int = 0,
                         ate_and_drank: bool = True) -> RestPreview:
    """Pure: cosa cambierebbe un riposo. Usata da /rest (che poi applica) e dall'anteprima."""
    fx = RestPreview()
    if char.is_dead:  # un riposo non rianima un personaggio morto
        return fx
    long = rest_type == "long"
    fx.ends_concentration = long and is_concentrating(char)  # D8: solo il riposo lungo
    fx.pact_slots = sum(s.used for s in char.spell_slots if s.is_pact and s.used > 0)
    if long:
        for s in char.spell_slots:
            if not s.is_pact and s.used > 0:
                fx.slots[s.level] = fx.slots.get(s.level, 0) + s.used
        # Dadi vita: 2014 fino a metà del totale (min 1), 2024 tutti quelli spesi;
        # dal dado più grande in caso di multiclasse (spec 2026-07-17).
        hd_budget = (sum(c.level for c in char.classes) if character_edition(char) == "2024"
                     else max(1, sum(c.level for c in char.classes) // 2))
        for cls in sorted(char.classes, key=lambda c: (c.hit_die or 8), reverse=True):
            if hd_budget <= 0:
                break
            spent = min(cls.hit_dice_used or 0, cls.level)
            back = min(spent, hd_budget)
            if back > 0:
                fx.hit_dice_regain[cls.id] = back
                hd_budget -= back
        # Spossatezza -1 livello; nel 2014 solo se ci si è anche nutriti.
        exh = (char.conditions or {}).get("exhaustion", 0)
        fed = ate_and_drank or character_edition(char) == "2024"
        if fed and isinstance(exh, int) and not isinstance(exh, bool) and exh > 0:
            fx.exhaustion_change = -1
        # Il massimo vale per il livello di spossatezza a riposo finito.
        hp_max = effective_hp_max(char, hp_max_bonus, exhaustion_level(char) + fx.exhaustion_change)
        fx.hp_gain = max(0, hp_max - char.current_hit_points)
    elif _short_rest_exhaustion(char):  # Instancabile: ogni riposo breve toglie un livello di Sfinimento
        fx.exhaustion_change = -1
    fx.abilities = [a.name for a in char.abilities
                    if _restores_ability(a, rest_type) and a.uses != a.max_uses]
    fx.homebrew_resources = [r.name for r in char.homebrew_resources
                             if _restores_resource(r, rest_type) and r.current != r.max]
    for r in plan_item_recharges(char.items, rest_type, roll=False):
        full = r.after is not None
        fx.item_charges.append(ItemChargePreview(
            name=r.item.name, gain=r.after - r.before if full else None,
            formula=None if full else r.formula, full=full))
    return fx


@router.get("/{char_id}/rest/preview", response_model=RestPreview)
async def rest_preview(
    char_id: int,
    rest_type: str,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> RestPreview:
    if rest_type not in ("long", "short"):
        raise HTTPException(status_code=400, detail="rest_type must be 'long' or 'short'")
    char = await get_owned_full_with_resources(char_id, user_id, session)
    bonus = await get_passive_modifiers(session, char, "character.hit_points_max")
    return compute_rest_effects(char, rest_type, bonus)


def _rest_ally_temp_hp(char, edition) -> tuple[int, int]:
    """Quante creature e quanti PF temporanei ciascuna: il massimo fra i privilegi di riposo del personaggio (Resilienza Celestiale)."""
    best = (0, 0)
    for spec, row in active_features(char):
        if spec.rest_temp_hp_ally:
            best = max(best, spec.rest_temp_hp_ally(RuleContext(char=char, edition=edition, class_row=row, class_level=row.level)), key=lambda t: t[1])
    return best


def _rest_resistance(char, damage_type: str | None) -> tuple | None:
    """La resistenza scelta finendo il riposo (Resilienza Immonda): ``(privilegio, chiave dello stato, tipo)``; 422 se non si può."""
    if damage_type is None:
        return None
    for spec, _row in active_features(char):
        if spec.rest_damage_choice:
            key, allowed = spec.rest_damage_choice
            if damage_type not in allowed:
                raise HTTPException(status_code=422, detail={"code": "invalid_damage_type"})
            return spec, key, damage_type
    raise HTTPException(status_code=422, detail={"code": "no_resistance_choice"})


async def _rest_temp_receivers(session: AsyncSession, char, edition, wanted: list[int]) -> list:
    if not wanted:
        return []
    from api.services.session_allies import temp_hp_receivers  # import locale: la serata non serve agli altri endpoint
    return await temp_hp_receivers(session, char, wanted, _rest_ally_temp_hp(char, edition)[0])


async def _deliver_rest_temp_hp(session: AsyncSession, char, edition, receivers: list) -> list[dict]:
    """Consegna i PF temporanei di fine riposo, riletti i riceventi; il valore lo calcola il server. Il maggiore fra i loro e i nuovi."""
    from api.services.effects import grant_temp_hp  # import locale, come sopra
    from api.services.session_allies import load_receiver
    value, out = _rest_ally_temp_hp(char, edition)[1], []
    for target in receivers:
        receiver = await load_receiver(session, target.id)
        if receiver.is_dead:
            raise HTTPException(status_code=409, detail={"code": "target_dead"})
        given = grant_temp_hp(session, receiver, value)
        out.append({"name": receiver.name, "given": value, "temp_hp": given["new"], "applied": given["applied"]})
    return out


@router.post("/{char_id}/rest", response_model=CharacterFull)
async def rest(
    char_id: int,
    body: RestRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CharacterFull:
    char = await get_owned_full_with_resources(char_id, user_id, session)
    if body.rest_type not in ("long", "short"):
        raise HTTPException(status_code=400, detail="rest_type must be 'long' or 'short'")
    # Un riposo non rianima un personaggio morto.
    if char.is_dead:
        return await build_character_response(session, char)
    edition = character_edition(char)
    rest_type = body.rest_type
    receivers = await _rest_temp_receivers(session, char, edition, body.temp_hp_allies)  # prima di ogni scrittura del riposo
    chosen_resistance = _rest_resistance(char, body.fiendish_resilience)
    if (body.natural_recovery or body.arcane_recovery or body.sorcerous_restoration or body.memorize_spell) and rest_type != "short":
        raise HTTPException(status_code=422, detail={"code": "natural_recovery_short_only"})
    if rest_type == "long" or edition == "2024":
        # Un personaggio senza massimo (nessuna classe) non è «a 0 PF»: non c'è nulla da proteggere.
        if char.current_hit_points <= 0 and char.hit_points > 0:
            raise HTTPException(status_code=409, detail="rest_needs_hp")
    if body.interrupted and (rest_type == "long" or edition == "2024"):
        if rest_type == "short" or edition == "2014":
            # Nessun beneficio (2014: lungo da ricominciare; 2024: breve interrotto).
            add_history(session, char.id, "rest", "Riposo interrotto: nessun beneficio",
                         meta={"kind": rest_type, "interrupted": True})
            return await build_character_response(session, char)
        rest_type = "short"  # 2024: il lungo interrotto dopo almeno un'ora vale un riposo breve
    if rest_type == "long" and not body.confirm_early and char.last_long_rest_at:
        gap = timedelta(hours=16 if edition == "2024" else 24)
        if _utcnow() - datetime.fromisoformat(char.last_long_rest_at) < gap:
            raise HTTPException(status_code=409, detail="long_rest_too_soon")
    notifications: list[dict] = []
    if body.reopen_tome:  # Patto del Tomo: dopo ogni controllo che può rifiutare il riposo
        from api.services.choices import reopen_tome  # import locale: choices importa i modelli del riposo
        await reopen_tome(session, char)
    if body.natural_recovery:  # convalida ed effetto prima di ogni altra scrittura del riposo
        back = await recover_slots(session, char, body.natural_recovery)
        add_history(session, char.id, "rest",
                     "Recupero Naturale: " + ", ".join(f"slot di livello {lv} ×{n}" for lv, n in sorted(back.items())),
                     meta={"kind": "natural_recovery", "slots": {str(lv): n for lv, n in back.items()}})
    if body.memorize_spell:  # Memorizzare Incantesimo: si convalida prima del Recupero Arcano, che spende un uso
        swapped = memorize(char, body.memorize_spell.out, body.memorize_spell.into)
        add_history(session, char.id, "rest", f"Memorizzare Incantesimo: {swapped[0]} → {swapped[1]}",
                     meta={"kind": "memorize_spell", "out": body.memorize_spell.out, "into": body.memorize_spell.into})
    if body.arcane_recovery:  # come il Recupero Naturale: convalida ed effetto prima di ogni altra scrittura del riposo
        back = await recover_slots(session, char, body.arcane_recovery, ARCANE_FEATURE)
        add_history(session, char.id, "rest",
                     "Recupero Arcano: " + ", ".join(f"slot di livello {lv} ×{n}" for lv, n in sorted(back.items())),
                     meta={"kind": "arcane_recovery", "slots": {str(lv): n for lv, n in back.items()}})
    if body.sorcerous_restoration:  # Ripristino Stregonesco: i punti tornano nel riposo breve, convalidati dal server
        gained = await restore_points(session, char, body.sorcerous_restoration)
        add_history(session, char.id, "rest", f"Ripristino Stregonesco: {gained} punti stregoneria",
                     meta={"kind": "sorcerous_restoration", "points": gained})
    hb_hp_bonus = await get_passive_modifiers(session, char, "character.hit_points_max")
    fx = compute_rest_effects(char, rest_type, hb_hp_bonus, body.ate_and_drank)
    for r in plan_item_recharges(char.items, rest_type):
        set_item_charges(r.item, r.after)
        add_history(session, char.id, "item_charges",
                     f"Cariche ricaricate: {r.item.name} ({r.before} → {r.after})")

    reset_zero_hp_uses(char)
    if rest_type == "long":
        char.last_long_rest_at = _now()
        char.temp_hp = 0
        reset_target_immunity(char)  # le «24 ore» di un effetto su altri
        forget_spell_temp_drop(char)  # i PF temporanei tolti da un incantesimo finito non tornano più con un annullo
        # Break concentration
        end_concentration(char)
        end_states_on_rest(char, "long")
        await long_rest_beast(session, char)
        await long_rest_familiar(session, char)
        # Reset all spell slots
        for slot in char.spell_slots:
            slot.used = 0
        clear_created_slots(char)  # gli slot creati con Incantesimi Flessibili svaniscono
        hd_regained = sum(fx.hit_dice_regain.values())
        for cls in char.classes:
            if cls.id in fx.hit_dice_regain:
                cls.hit_dice_used = min(cls.hit_dice_used or 0, cls.level) - fx.hit_dice_regain[cls.id]
        if hd_regained:
            add_history(session, char.id, "hit_dice",
                         f"Dadi vita recuperati: {hd_regained} (riposo lungo)")
        # Restore long-rest AND short-rest abilities (long rest includes short rest
        # benefits). Le ex-risorse di classe sono ora Ability e rientrano qui.
        for ability in char.abilities:
            if _restores_ability(ability, "long"):
                _restore_ability(ability, "long")
        # Homebrew resources auto-restore on rest by restoration_type (D3),
        # mirroring abilities: a long rest restores both long_rest and short_rest.
        for resource in char.homebrew_resources:
            if _restores_resource(resource, "long"):
                resource.current = resource.max
        # Reset death saves
        char.death_saves = {"successes": 0, "failures": 0, "stable": False}
        if fx.exhaustion_change:
            _apply_exhaustion_change(session, char, fx.exhaustion_change, "riposo lungo")
        # Dopo la spossatezza: il massimo effettivo dipende dal livello appena sceso.
        char.current_hit_points = effective_hp_max(char, hb_hp_bonus)
        add_history(session, char.id, "rest", "Riposo lungo completato",
                     meta={"kind": "long"})
        for spec, row in active_features(char):  # alla fine del riposo lungo certi privilegi avviano un loro stato (Tranquillità)
            if spec.long_rest_state:
                started = spec.long_rest_state(RuleContext(char=char, edition=edition, class_row=row, class_level=row.level))
                if started is not None:
                    begin_state(char, started, spec.key, spec.name["it"])

        for spec, row in active_features(char):  # Portento: i d20 nuovi prendono il posto di quelli non usati
            if spec.long_rest_dice:
                key, count = spec.long_rest_dice
                rolled = [random.randint(1, 20) for _ in range(count(RuleContext(char=char, edition=edition, class_row=row, class_level=row.level)))]
                set_saved_dice(char, key, rolled)
                record_dice(char, [("d20", v) for v in rolled])

        firing = await dispatch(session, char, "long_rest_taken", {})
        notifications.extend(collect_homebrew_notifications(firing))

    else:
        # D8: il riposo breve non interrompe la concentrazione.
        end_states_on_rest(char, "short")
        if fx.exhaustion_change:
            _apply_exhaustion_change(session, char, fx.exhaustion_change, "riposo breve")
        # Warlock Pact Magic slots recover on a short rest (unlike regular slots).
        for slot in char.spell_slots:
            if slot.is_pact:
                slot.used = 0
        # Restore short-rest abilities (le ex-risorse di classe sono ora Ability).
        for ability in char.abilities:
            if _restores_ability(ability, "short"):
                _restore_ability(ability, "short")
        # Homebrew resources: a short rest restores only short_rest resources (D3).
        for resource in char.homebrew_resources:
            if _restores_resource(resource, "short"):
                resource.current = resource.max
        add_history(session, char.id, "rest",
                     "Riposo breve completato",
                     meta={"kind": "short"})

        firing = await dispatch(session, char, "short_rest_taken", {})
        notifications.extend(collect_homebrew_notifications(firing))
    for spec, row in active_features(char):  # Resilienza Celestiale: a ogni riposo concluso PF temporanei (non si sommano)
        if spec.rest_temp_hp:
            char.temp_hp = max(char.temp_hp or 0, spec.rest_temp_hp(RuleContext(char=char, edition=edition, class_row=row, class_level=row.level)))
    if chosen_resistance is not None:  # Resilienza Immonda: dopo la fine degli stati del riposo, che non toglie questo
        spec, key, damage_type = chosen_resistance
        begin_state(char, StateSpec(key, ends_on=("manual",), data={"damage_type": damage_type}), spec.key, spec.name["it"])
    temp_received = await _deliver_rest_temp_hp(session, char, edition, receivers)
    await end_knock_out(session, char)  # 2024: il riposo in corso del tramortito è questo
    await release_concentration_effects(session, char)

    result = await build_character_response(session, char)
    result.temp_received = temp_received
    if notifications:
        result.homebrew_notifications = notifications
    return result


# ---------------------------------------------------------------------------
# Death saves
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Hit dice spending (during short rest)
# ---------------------------------------------------------------------------

@router.post("/{char_id}/hit_dice/spend", response_model=HitDiceSpendResult)
async def spend_hit_dice(
    char_id: int,
    body: HitDiceSpendRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> HitDiceSpendResult:
    char = await get_owned_full_with_resources(char_id, user_id, session)

    # Find the class
    cls = next((c for c in char.classes if c.id == body.class_id), None)
    if cls is None:
        raise HTTPException(status_code=404, detail="Class not found")
    if body.count < 1:
        raise HTTPException(status_code=400, detail="count must be >= 1")

    # Pool residuo per classe (spec 2026-07-17): level - hit_dice_used.
    remaining = max(0, cls.level - (cls.hit_dice_used or 0))
    if body.count > remaining:
        raise HTTPException(status_code=409, detail="hit_dice_exhausted")

    hit_die = cls.hit_die or 8

    con_mod = effective_con_mod(char)

    if body.rolls is not None:
        if len(body.rolls) != body.count:
            raise HTTPException(
                status_code=400,
                detail=f"rolls length {len(body.rolls)} != expected {body.count}",
            )
        if any(v < 1 or v > hit_die for v in body.rolls):
            raise HTTPException(status_code=400, detail=f"rolls values must be in [1, {hit_die}]")
        rolls = list(body.rolls)
    else:
        rolls = [random.randint(1, hit_die) for _ in range(body.count)]
    # Ogni dado cura tiro + COS: minimo 0 nel 2014, 1 nel 2024.
    floor = 1 if character_edition(char) == "2024" else 0
    total_healed = sum(max(floor, r + con_mod) for r in rolls)
    song_die, song_rolls = await roll_song_of_rest(session, char)  # Canto di Riposo: un dado extra a testa per riposo
    total_healed += sum(song_rolls)

    old_hp = char.current_hit_points
    # apply_heal: tetto con bonus homebrew e azzeramento dei tiri contro morte risalendo da 0 PF.
    healed = await apply_heal(session, char, total_healed)
    actual_healed = healed["healed"]

    cls.hit_dice_used = (cls.hit_dice_used or 0) + body.count

    add_history(session, char.id, "hit_dice",
                 f"Dado vita {body.count}d{hit_die}+{con_mod}: "
                 f"tiri={rolls}, curati={actual_healed} HP ({old_hp} → {char.current_hit_points})"
                 + (f", Canto di Riposo d{song_die}={song_rolls}" if song_rolls else ""),
                 meta={"healed": actual_healed})
    record_dice(char, [(f"d{hit_die}", r) for r in rolls] + [(f"d{song_die}", r) for r in song_rolls])

    notifications = collect_homebrew_notifications(healed["firing"])
    return HitDiceSpendResult(
        rolls=rolls,
        con_bonus=con_mod,
        healed=actual_healed,
        new_current_hp=char.current_hit_points,
        homebrew_notifications=notifications or None,
        song_die=song_die,
        song_rolls=song_rolls,
    )


@router.patch("/{char_id}/death_saves", response_model=CharacterFull)
async def update_death_saves(
    char_id: int,
    body: DeathSaveUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CharacterFull:
    char = await get_owned_full_with_resources(char_id, user_id, session)
    if char.is_dead:
        return await build_character_response(session, char)
    ds = dict(char.death_saves or {"successes": 0, "failures": 0, "stable": False})

    if body.action == DeathSaveAction.SUCCESS:
        ds["successes"] = min(3, ds.get("successes", 0) + 1)
        if ds["successes"] >= 3:
            ds["stable"] = True
            add_history(session, char.id, "death_save", "Stabilizzato (3 successi)",
                         meta={"ds": "success", "n": 1})
        else:
            add_history(session, char.id, "death_save",
                         f"Tiro morte: successo ({ds['successes']}/3)",
                         meta={"ds": "success", "n": 1})

    elif body.action == DeathSaveAction.FAILURE:
        ds["failures"] = min(3, ds.get("failures", 0) + 1)
        add_history(session, char.id, "death_save",
                     f"Tiro morte: fallimento ({ds['failures']}/3)",
                     meta={"ds": "failure", "n": 1})
        if ds["failures"] >= 3:
            char.is_dead = True
            await drop_primal_beast(session, char)
            add_history(session, char.id, "death_save", "Morto — 3 fallimenti")
            await notify_party_emergency(session, char, f"💀 {char.name} è morto!")

    elif body.action == DeathSaveAction.STABILIZE:
        # RAW: stabilizzare (Medicina CD 10, Risparmiare i Morenti) non cura —
        # la creatura resta a 0 HP, priva di sensi ma stabile. La risalita a
        # HP positivi passa solo da cure/riposo, che azzerano il tracker.
        ds["stable"] = True
        add_history(session, char.id, "death_save", "Stabilizzato")

    elif body.action == DeathSaveAction.RESET:
        ds = {"successes": 0, "failures": 0, "stable": False}

    elif body.action == DeathSaveAction.ROLL:
        # Handled by the dedicated roll endpoint below
        pass

    char.death_saves = ds
    return await build_character_response(session, char)


# ---------------------------------------------------------------------------
# Death save roll (d20 with special D&D 5e rules)
# ---------------------------------------------------------------------------

@router.post("/{char_id}/death_saves/roll", response_model=DeathSaveRollResult)
async def roll_death_save(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
    body: Annotated[D20RollSubmission | None, Body()] = None,
) -> DeathSaveRollResult:
    char = await get_owned_full_with_resources(char_id, user_id, session)
    if char.is_dead:
        return DeathSaveRollResult(
            die=0, outcome="failure",
            successes=(char.death_saves or {}).get("successes", 0),
            failures=(char.death_saves or {}).get("failures", 0),
            stable=(char.death_saves or {}).get("stable", False),
            revived=False, current_hp=char.current_hit_points,
        )
    ds = dict(char.death_saves or {"successes": 0, "failures": 0, "stable": False})
    before = {"death_saves": dict(ds), "hp": char.current_hit_points}

    applied = modifiers_for(char, "death_save")
    await attach_party_auras(session, char)
    opts = use_options(session, char, "death_save", body)
    merge_options(applied, opts)
    if opts.self_heal:  # Vendetta Ardente: la cura viene prima del TS, e se risale sopra 0 PF il tiro non si fa
        await apply_heal(session, char, opts.self_heal)
        if char.current_hit_points > 0:
            ds = char.death_saves or {}
            return DeathSaveRollResult(
                die=0, outcome="revived", successes=ds.get("successes", 0), failures=ds.get("failures", 0), stable=False, revived=True,
                current_hp=char.current_hit_points, option_result=option_result(opts, [], 0))
    d20 = resolve_body(body, applied)
    die = d20.kept
    record_dice(char, d20_records(d20))
    option_rolls, option_total = roll_option_dice(char, opts)
    bonus = applied.flat + opts.bonus
    outcome, revived = await _apply_death_roll(session, char, ds, die, bonus + option_total, nat20_min=applied.crit_min)

    block = option_result(opts, option_rolls, option_total)
    remember_roll(char, "death_save", opts, {
        "die": die, "dice": d20.dice, "mode": d20.mode, "bonus": bonus, "total": die + bonus + option_total,
        "notes": applied.notes, "auto_fail": False, "description": "",
        "option_result": block.model_dump(mode="json") if block else None,
    }, death={"before": before, "after": death_state(char)})

    ds = char.death_saves
    return DeathSaveRollResult(
        die=die,
        dice=d20.dice,
        mode=d20.mode,
        mode_applied=d20.mode,
        notes=applied.notes,
        outcome=outcome,
        successes=ds["successes"],
        failures=ds["failures"],
        stable=ds.get("stable", False),
        revived=revived,
        current_hp=char.current_hit_points,
        option_result=block,
    )


def death_state(char: Character) -> dict:
    """Ciò che un TS contro la morte ha lasciato: se cambia dopo, il tiro non si ritocca più."""
    return {"death_saves": char.death_saves, "hp": char.current_hit_points, "is_dead": char.is_dead}


async def retouch_death_save(
    session: AsyncSession, char: Character, death: dict, roll: dict,
) -> tuple[DeathSaveRollResult, dict]:
    """Il tiro è cambiato dopo un privilegio: si riparte dallo stato di prima, 1 e 20 naturali compresi."""
    was_dead = death["after"]["is_dead"]
    rows = (await session.execute(select(CharacterHistory).where(
        CharacterHistory.character_id == char.id, CharacterHistory.event_type == "death_save",
    ).order_by(CharacterHistory.id.desc()))).scalars()
    counted = next((r for r in rows if (r.meta or {}).get("ds")), None)
    if counted is not None:  # il riepilogo della serata conta l'esito finale, non quello corretto
        counted.meta = None
    char.current_hit_points = death["before"]["hp"]
    char.is_dead = False
    await sync_zero_hp(session, char, False)  # un 20 corretto aveva tolto Privo di sensi
    die, total = roll["die"], roll["total"]
    outcome, revived = await _apply_death_roll(session, char, dict(death["before"]["death_saves"]), die, total - die,
                                               notify=not was_dead, nat20_min=modifiers_for(char, "death_save").crit_min)
    if was_dead and not char.is_dead:
        add_history(session, char.id, "death_save", "Correzione: il nuovo tiro evita la morte")
    ds = char.death_saves
    return DeathSaveRollResult(
        die=die, dice=roll["dice"], mode=roll["mode"], mode_applied=roll["mode"], notes=roll["notes"], outcome=outcome,
        successes=ds["successes"], failures=ds["failures"], stable=ds.get("stable", False), revived=revived,
        current_hp=char.current_hit_points, option_result=roll["option_result"],
    ), {**death, "after": death_state(char)}


async def _apply_death_roll(
    session: AsyncSession, char: Character, ds: dict, die: int, modifier: int, notify: bool = True, nat20_min: int = 20,
) -> tuple[str, bool]:
    """Applica l'esito a ``char``: (esito, rianimato)."""
    revived = False

    if die >= nat20_min:  # Sfidare la Morte: 18-20 valgono come un 20
        # Natural 20: revive with 1 HP
        ds = {"successes": 0, "failures": 0, "stable": False}
        char.current_hit_points = 1
        await sync_zero_hp(session, char, True)
        revived = True
        outcome = "nat20"
        add_history(session, char.id, "death_save",
                     f"Tiro morte d20={die}: Naturale 20! Rianimato con 1 HP",
                     meta={"ds": "success", "n": 1})

    elif die == 1:
        # Natural 1: counts as 2 failures
        ds["failures"] = min(3, ds.get("failures", 0) + 2)
        outcome = "nat1"
        add_history(session, char.id, "death_save",
                     f"Tiro morte d20={die}: Naturale 1! 2 fallimenti ({ds['failures']}/3)",
                     meta={"ds": "failure", "n": 2})

    elif die + modifier >= 10:
        # 10+: 1 success (Esaurimento 2024 e bonus di classe contano; 20 e 1 naturali no)
        ds["successes"] = min(3, ds.get("successes", 0) + 1)
        outcome = "success"
        if ds["successes"] >= 3:
            ds["stable"] = True
            add_history(session, char.id, "death_save",
                         f"Tiro morte d20={die}: Successo! Stabilizzato (3/3)",
                         meta={"ds": "success", "n": 1})
        else:
            add_history(session, char.id, "death_save",
                         f"Tiro morte d20={die}: Successo ({ds['successes']}/3)",
                         meta={"ds": "success", "n": 1})

    else:
        # 2-9: 1 failure
        ds["failures"] = min(3, ds.get("failures", 0) + 1)
        outcome = "failure"
        add_history(session, char.id, "death_save",
                     f"Tiro morte d20={die}: Fallimento ({ds['failures']}/3)",
                     meta={"ds": "failure", "n": 1})

    char.death_saves = ds

    if ds.get("failures", 0) >= 3:
        char.is_dead = True
        await drop_primal_beast(session, char)
        add_history(session, char.id, "death_save", "Morto — 3 fallimenti")
        if notify:
            await notify_party_emergency(session, char, f"💀 {char.name} è morto!")

    return outcome, revived


# ---------------------------------------------------------------------------
# HP recalculation from D&D 5e fixed formula
# ---------------------------------------------------------------------------

@router.post("/{char_id}/hp/recalc", response_model=CharacterFull)
async def recalc_hp(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CharacterFull:
    """Recalculate hit_points from D&D 5e fixed formula.

    Computes total_base_hp using character's current classes (with first
    class owning level 1), current CON mod (effective with equipped items),
    then sets hit_points to that value. current_hit_points is clamped:
    - If new_max > old_max: current += (new_max - old_max)
    - Otherwise current stays, capped to the effective max
    """
    char = await get_owned_full_with_resources(char_id, user_id, session)

    con_mod = effective_con_mod(char)
    new_max = total_base_hp(char.classes, con_mod, stored_rolls(char))

    old_max = char.hit_points
    was_at_zero = char.current_hit_points == 0
    char.hit_points = new_max
    if new_max > old_max:  # se cala, i PF correnti restano e il tetto lo mette cap_current_hp (Aiuto supera il massimo base)
        char.current_hit_points += new_max - old_max
    await cap_current_hp(session, char, always=True)
    await sync_zero_hp(session, char, was_at_zero)

    add_history(session, char.id, "hp_change",
                 f"HP ricalcolati da formula: {old_max} → {new_max}",
                 meta={"op": "SET_MAX"})

    await session.commit()
    await session.refresh(char)
    return await build_character_response(session, char)


# ---------------------------------------------------------------------------
# Revive (manual revival — represents off-app revival magic)
# ---------------------------------------------------------------------------

@router.post("/{char_id}/revive", response_model=CharacterFull)
async def revive(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CharacterFull:
    """Bring a dead character back with 1 HP. No-op if not dead (idempotent)."""
    char = await get_owned_full_with_resources(char_id, user_id, session)
    if char.is_dead:
        char.is_dead = False
        char.current_hit_points = 1
        char.death_saves = {"successes": 0, "failures": 0, "stable": False}
        if exhaustion_level(char) >= 6:  # altrimenti resterebbe al livello che uccide
            char.conditions = {**(char.conditions or {}), "exhaustion": 5}
        end_concentration(char)
        await release_concentration_effects(session, char)
        await sync_zero_hp(session, char, True)
        add_history(session, char.id, "death_save", "Riportato in vita (1 PF)")
    return await build_character_response(session, char)

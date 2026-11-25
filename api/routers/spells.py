"""Spell management endpoints."""

from __future__ import annotations

import random
import re
import uuid
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.services.history import add_history
from api.services.game_sessions import utc_now_iso
from api.auth import get_current_lang, get_current_user
from api.database import get_db
from core.db.models import Ability, Character, CharacterClass, Spell, SpellSlot
from api.schemas.character import CharacterFull, SpellAttackResult
from api.schemas.common import ConcentrationSaveResult, D20Dice, OptionResult, RollMode
from api.schemas.spell import (
    ConcentrationUpdate,
    LastDamageBody,
    RollDamageRequest,
    RollDamageResult,
    RollHealingRequest,
    RollHealingResult,
    SpellAttackRequest,
    SpellCopyCost,
    SpellCopyRequest,
    SpellCreate,
    SpellRead,
    SpellUpdate,
    SpellUseRequest,
)
from api.services.durations import end_concentration, is_concentrating, start_concentration
from core.data.damage_types import LABELS_IT, canonical_damage_type
from api.services.effects import casts_verbally, end_hide
from api.services.rules_states import end_on_action
from api.services.condition_removal import apply_removal, plan, resolve_targets
from api.services.session_allies import ally_target, deliver_temp_gifts, load_receiver
from api.services.spell_effects import apply_spell_effects, cast_level, cast_damage_type, cast_upcast_type, chosen_damage_type, validate_spell_targets
from core.rules.condition_removal import NOT_RECOGNIZED, looks_like_removal, spell_removal
from api.services.condition_effects import release_concentration_effects
from core.game.actions import parse_duration_rounds
from api.routers._helpers import collect_homebrew_notifications, refuse_null, roll_concentration_save
from api.routers.sessions import active_encounter_row
from api.services.character_response import build_character_response
from api.services.d20 import d20_records, d20_history_label, resolve_applied, resolve_body, spend_inspiration_attack
from core.rules.catalog.y2014.cleric import BLESSED_HEALER
from core.rules.catalog.y2014.sorcerer import AFFINITY_USED, QUICKENED_KEY, SP, SUBTLE_KEY, TWINNED_TURN_KEY
from core.rules.catalog.y2014.wizard_schools_c import EMPOWERED_USED, _empowered
from core.rules.catalog.y2024.ranger_subclasses import FEY_NO_CONCENTRATION_KEY
from core.rules.catalog.y2024.sorcerer_subclasses import NO_CONCENTRATION_KEY
from core.rules.catalog.y2024.warlock_subclasses import PSYCHIC_SILENT, THRALL_CAST
from core.rules.modifiers import modifiers_for
from core.rules.types import RuleContext
from api.schemas.companion import CompanionAttackResult
from api.schemas.item import WeaponAttackResult
from api.services.last_damage import damage_parts, last_damage_total, pairs, regroup
from core.rules.roll_options import option_names, scale_damage
from api.services.rules_options import merge_options, option_result, remember_roll, roll_option_dice, use_options
from api.services.rules_states import _spend_atomically, remove_state
from api.services.wild_magic import mark_tides_due
from api.services.rules_turn import get_turn, refuse_if_incapacitated, spend
from core.rules.catalog import active_features
from core.rules.catalog.spells import hurled_lit, spell_effect
from core.rules.spell_effects import SPELL_CLOCK_PREFIX
from core.rules.catalog.y2024.paladin import STEED, make_steed
from core.rules.edition import character_edition
from core.rules.pact_casts import FREE_CASTS, pact_cast, spent_free_casts
from core.rules.school_hooks import after_cast
from core.rules.spellbook import MODES, book_refusal, change_needs_rest, copy_cost, prepare_refusal, wizard_row
from core.rules.states import begin_state, free_cast_state, has_state, item_spell_held
from core.rules.types import StateSpec
from api.services.choices import consume_spell_pick, ensure_new_spell, release_spell_pick, spell_pick_target
from core.rules.level_choices import reconcile_choices
from api.services.dice_stats import record_dice
from api.services.homebrew.dispatcher import dispatch
from api.services.spellcasting import build_spellcasting_info, fill_spell_stats, prepared_class_room
from core.game.stats import cantrip_dice_multiplier, effective_ability_mod
from core.rules.spell_healing import healing_dice, healing_fixed, healing_spec
from core.rules.spellcasting import (
    at_will, bonus_cast, can_ritual, champion_bonus_cast, LONG_CASTING as _LONG_CASTING, cast_warnings, caster_stats, casting_kind, ki_cast_info, spell_stats,
)
from api.services.character_load import get_owned_full
from api.services.dice_notation import DICE_RE, roll_dice


class ConcentrationSaveRequest(BaseModel):
    damage: int = Field(ge=0)
    mode: RollMode = "normal"
    dice: D20Dice | None = None

router = APIRouter(prefix="/characters", tags=["spells"])
SPELL_ATTACK_DICE = "spell_attack_dice"  # turn_state: i dadi extra confermati su un attacco con incantesimo, per il suo danno


def _prepared_cap_error(count: int, cap: int, per_class: bool) -> HTTPException:
    return HTTPException(status_code=400, detail={"code": "prepared_cap", "n": count, "cap": cap, "per_class": per_class})


def _ensure_prepare_capacity(char: Character, class_id: int | None = None) -> None:
    """400 se il PG ha classi preparanti e il tetto, o quello della classe dell'incantesimo, è già raggiunto.

    Grandfathering: lo stato over-cap legacy resta valido — qui si bloccano
    solo i NUOVI prepare (count >= cap), mai gli unprepare.
    """
    room = prepared_class_room(char, class_id) if class_id else None
    if room and room[0] >= room[1]:
        raise _prepared_cap_error(room[0], room[1], True)
    info = build_spellcasting_info(char)
    if info.has_preparing_class and info.prepared_count >= (info.prepared_cap or 0):
        raise _prepared_cap_error(info.prepared_count, info.prepared_cap or 0, False)


def _check_rest_window(char: Character, spell: Spell, confirm: bool) -> None:
    """D-020: fuori dalla finestra del riposo lungo o della salita di livello il cambio va confermato."""
    if not confirm and change_needs_rest(char, spell):
        raise HTTPException(status_code=409, detail={"code": "change_after_long_rest"})


def _check_class(char: Character, class_id: int | None) -> None:
    if class_id is not None and all(c.id != class_id for c in char.classes):
        raise HTTPException(status_code=400, detail={"code": "bad_class"})


def _pick_slot(char: Character, spell: Spell, slot_id: int | None, slot_level: int | None,
               pact_only: bool = False) -> SpellSlot:
    """``slot_id`` sceglie il pool. Col solo livello: la prima riga con posto, gli slot normali prima del patto.
    ``pact_only``: solo uno slot di Patto (le suppliche «una volta con uno slot da warlock»), 409 ``pact_slot_required``."""
    if slot_id is not None:
        slot = next((s for s in char.spell_slots if s.id == slot_id), None)
        if slot is None:
            raise HTTPException(status_code=400, detail="Slot not found")
        if pact_only and not slot.is_pact:
            raise HTTPException(status_code=409, detail={"code": "pact_slot_required"})
        slot_level = slot.level
    elif slot_level is None:
        raise HTTPException(status_code=400, detail="slot_level is required")
    if slot_level < spell.level:
        raise HTTPException(status_code=400, detail={"code": "slot_too_low"})
    if slot_id is None:
        rows = sorted((s for s in char.spell_slots if s.level == slot_level and (s.is_pact or not pact_only)),
                      key=lambda s: bool(s.is_pact))
        if not rows:
            raise HTTPException(status_code=400, detail=f"No slot configured for level {slot_level}")
        slot = next((s for s in rows if s.available > 0), rows[0])
    if slot.available == 0:
        raise HTTPException(status_code=400, detail=f"No slots available at level {slot_level}")
    return slot


def _cast_kind(char: Character, spell: Spell) -> str:
    """Il slot di turno del lancio. Campione degli Antichi 2024 (Incantesimi Rapidi): finché dura, un incantesimo da un'azione
    si lancia con un'azione bonus."""
    kind = casting_kind(spell)
    if champion_bonus_cast(char, spell):
        return "bonus"
    if kind == "action" and bonus_cast(char, spell):  # Rompi-Incantesimi: Dissolvi Magie come azione bonus
        return "bonus"
    return kind


_SLOT_MARKS = ("action_used", "bonus_used", "reaction_used", "action_attacks", "extra_actions")


def _slot_marks(char: Character) -> tuple:
    turn = get_turn(char)
    return tuple(turn[k] for k in _SLOT_MARKS)


def _mark_turn_slot(char: Character, spell: Spell, before: tuple, in_encounter: bool, kind: str | None = None) -> None:
    """Il lancio con slot o il trucchetto segna azione, azione bonus o reazione del suo tempo di lancio (B4), dopo le opzioni
    di lancio: se una ha già pagato il suo slot o preso il posto di un attacco (Incantesimo Rapido, trucchetto al posto di un
    attacco) il turno è cambiato da ``before`` e non si segna altro. Ki, Arcanum, lanci gratuiti e rituali pagano il turno da sé.

    In uno scontro attivo (il turno si azzera da solo a inizio turno) lo slot già usato rifiuta: 409 ``turn_slot_used``, e
    la richiesta annulla anche lo slot speso. Fuori dallo scontro il segno è morbido: il turno non si azzera da solo."""
    if _LONG_CASTING.search(spell.casting_time or "") or _slot_marks(char) != before:
        return
    try:
        spend(char, kind or _cast_kind(char, spell))
    except HTTPException:
        if in_encounter:
            raise
        # fuori scontro: già segnata, nessun costo in più


def _mark_cast(char: Character, spell: Spell, spent_slot: bool, ritual: bool) -> None:
    """Turno salvato per le regole sugli incantesimi nello stesso turno; le reazioni possono cadere fuori dal proprio."""
    kind = _cast_kind(char, spell)
    if spell.srd_index:  # Abiurazione Migliorata: la prova dopo controincantesimo o dissolvi magie, anche se lanciato in reazione
        turn = get_turn(char)
        turn["last_cast_spell"] = spell.srd_index
        char.turn_state = turn
    if kind == "reaction":
        return
    turn = get_turn(char)
    # Incantesimo Rapido 2024: cosa era già stato lanciato prima di questo lancio; conta ogni incantesimo di 1° livello o più,
    # anche pagato a punti stregoneria o gratis (``leveled_cast``), non solo con uno slot
    turn["cast_prior_slot"] = turn["spell_slot_cast"] or bool(turn.get("leveled_cast"))
    # 2014: un rituale (10 minuti in più) non è un incantesimo del turno
    turn["leveled_cast"] = bool(turn.get("leveled_cast")) or (spell.level >= 1 and not (ritual and character_edition(char) == "2014"))
    turn["spell_slot_cast"] = turn["spell_slot_cast"] or spent_slot
    turn["bonus_spell_cast"] = turn["bonus_spell_cast"] or kind == "bonus"
    # Magia da Battaglia: quale classe ha lanciato con l'azione (l'ultimo lancio vale). Un rituale o un tempo di 1 minuto o più
    # non è un lancio con l'azione (2014 pag. 55 e 201-202; 2024 pag. 67 e 236: «Tempi lunghi, Rituali compresi»)
    if kind == "action" and not ritual and not _LONG_CASTING.search(spell.casting_time or ""):
        casters = caster_stats(char)
        turn["action_spell_class"] = spell.class_id or (casters[0].class_id if len(casters) == 1 else None)
        turn["action_spell_level"] = spell.level  # Magia da Guerra: 0 è un trucchetto
    char.turn_state = turn


WAR_MAGIC_KEYS = {"fighter.war_magic", "fighter.improved_war_magic"}

# Concentrazione che cambia con lo slot e che la riga non dice: (edizione -> slot da cui non serve più, slot -> round).
# Immagine Maggiore 2014 pag. 242, 2024 pag. 295; Scagliare Maledizione 2014 pag. 273, 2024 pag. 245 (10 minuti con lo slot del 4°);
# Dominare Bestie / Persone / Mostri 2014 pag. 231-232, 2024 pag. 265-266 (10 minuti, 1 ora, 8 ore)
_SLOT_CONCENTRATION = {"major-image": ({"2014": 6, "2024": 4}, {}), "bestow-curse": ({"2014": 5, "2024": 5}, {4: 100}),
                       "dominate-beast": ({}, {5: 100, 6: 600, 7: 4800, 8: 4800, 9: 4800}),
                       "dominate-person": ({}, {6: 100, 7: 600, 8: 4800, 9: 4800}),
                       "dominate-monster": ({}, {9: 4800})}
# la riga senza srd_index (scritta a mano, homebrew, import vecchi) si riconosce dal nome it/en, come per gli effetti del lancio
_SLOT_CONCENTRATION_NAMES = {n.lower(): k for k, names in {
    "major-image": ("Immagine Maggiore", "Major Image"), "bestow-curse": ("Scagliare Maledizione", "Maledizione", "Bestow Curse"),
    "dominate-beast": ("Dominare Bestie", "Dominate Beast"), "dominate-person": ("Dominare Persone", "Dominate Person"),
    "dominate-monster": ("Dominare Mostri", "Dominate Monster")}.items() for n in names}


def _slot_concentration(char: Character, spell: Spell, level: int) -> tuple[bool, int | None]:
    """Se il lancio a questo livello chiede concentrazione e per quanti round: quelli dello slot (la tabella sopra, Sortilegio
    e Marchio del Cacciatore dal catalogo degli effetti), altrimenti la durata scritta sulla riga."""
    edition = character_edition(char)
    key = spell.srd_index if spell.srd_index in _SLOT_CONCENTRATION else next(
        (_SLOT_CONCENTRATION_NAMES[n] for p in (spell.name or "").split("/") if (n := p.strip().lower()) in _SLOT_CONCENTRATION_NAMES), "")
    until, rounds = _SLOT_CONCENTRATION.get(key, ({}, {}))
    if level >= until.get(edition, 10):
        return False, None
    if level in rounds:
        return True, rounds[level]
    found = spell_effect(edition, spell.srd_index, spell.name)
    if found and found[1].concentration and found[1].rounds_by_slot:
        return True, found[1].rounds_by_slot(level)
    rounds = parse_duration_rounds(spell.duration)
    if rounds == 1 and found and found[1].concentration:  # Colpo Accurato 2014 (pag. 222): serve nel turno dopo, il «Nuovo turno» non lo chiude
        rounds = found[1].rounds or rounds
    return True, rounds


def _ki_payment(char: Character, spell: Spell, ritual: bool, free_cast: bool, extra: int) -> tuple[Any, int]:
    """Lancio coi punti ki: la riserva e quanto costa. Ogni rifiuto viene prima di spendere qualcosa."""
    info = ki_cast_info(char, spell)
    if info is None or ritual or free_cast:
        raise HTTPException(status_code=409, detail={"code": "ki_cast_unavailable"})
    if extra and not info.upcast:
        raise HTTPException(status_code=409, detail={"code": "ki_extra_not_allowed"})
    if extra > info.max_extra and info.ki_left >= info.cost + extra:
        raise HTTPException(status_code=409, detail={"code": "ki_cap", "max_extra": info.max_extra})
    pool = next(a for a in char.abilities if a.feature_key == info.pool)
    total = info.cost + extra
    if (pool.uses or 0) < total:
        raise HTTPException(status_code=409, detail={"code": "no_uses"})
    return pool, total


def _refuse_surge_magic(char: Character) -> None:
    """Azione Impetuosa 2024: l'azione in più non può essere Magia. L'azione Attacco già iniziata (attacchi o lancio fatti) è
    l'azione spesa; la Magia da Guerra fa parte dell'Attacco (non passa di qui)."""
    turn = get_turn(char)
    spent_action = turn["action_used"] or turn["action_attacks"] > 0 or turn.get("action_spell_level") is not None
    if spent_action and turn["extra_actions"] > 0:
        raise HTTPException(status_code=409, detail={"code": "surge_no_magic"})


def _consume_cast(
    session, char: Character, spell: Spell, slot_id: int | None, slot_level: int | None, ritual: bool,
    confirm: list[str] | None = None, free_cast: bool = False, ki: bool = False, ki_extra: int = 0,
    silent: bool = False, war_magic: bool = False, no_concentration_option: bool = False, quickened: bool = False,
) -> Ability | None:
    """Consuma il lancio (slot o rituale) e attiva la concentrazione. Un trucchetto non consuma nulla.

    Condiviso da /use e /attack. Una regola violata e non confermata risponde 409 ``cast_confirm`` prima di spendere.
    Restituisce la riga del privilegio il cui uso il lancio spende (Arcanum Mistico, suppliche a uso singolo): lo spende
    il chiamante con ``_charge_pact_use``, con un UPDATE condizionato.
    """
    ki_pool, ki_total = _ki_payment(char, spell, ritual, free_cast, ki_extra) if ki else (None, 0)
    # Stregoneria Psionica 2024 pag. 146: coi punti stregoneria l'incantesimo non ha componenti, il nascondiglio resta
    silent = silent or (ki_pool is not None and ki_pool.feature_key == SP)
    free_state = None
    free_at_will = False
    no_concentration = no_concentration_option  # Compagno Draconico (l'opzione è convalidata da use_options); Benedizione del Dio della Guerra: il lancio gratuito non chiede Concentrazione
    pact = pact_cast(char, spell) if not ritual and not ki and spell.level >= 1 else None
    arcanum = None  # Arcanum Mistico: senza slot, spende l'uso della sua riga
    if free_cast:  # R43: serve uno stato attivo (o un privilegio a volontà) per questo incantesimo; costa l'azione, non uno slot
        free_state = free_cast_state(char, spell)
        free_at_will = free_state is None and at_will(char, spell)
        arcanum = pact if pact is not None and pact.kind == "arcanum" and free_state is None and not free_at_will else None
        if (free_state is None and not free_at_will and arcanum is None) or ritual:
            raise HTTPException(status_code=409, detail={"code": "free_cast_unavailable"})
    # Suppliche a uso singolo: lo slot è di Patto e il lancio spende l'uso. Tutti i rifiuti vengono prima di spendere.
    invocation = pact if pact is not None and pact.kind == "invocation" and not free_cast else None
    pact_row = None
    if arcanum is not None or invocation is not None:
        used = arcanum or invocation
        pact_row = next((a for a in char.abilities if (a.id == used.ability_id if used.ability_id is not None
                                                        else a.feature_key == used.feature_key)), None)
        if pact_row is None or (pact_row.uses or 0) < 1 or (used.free_key is not None and not used.uses_left):
            raise HTTPException(status_code=409, detail={"code": "no_uses"})  # il lancio gratuito di questo incantesimo è già speso
    if ritual:
        # Lancio rituale: +10 min, nessuno slot. Richiede il tag ritual e chi può celebrarlo per edizione.
        if not spell.is_ritual:
            raise HTTPException(status_code=400, detail="Spell is not a ritual")
        if not can_ritual(char, spell):
            raise HTTPException(
                status_code=400, detail="No class with Ritual Casting"
            )
    slot = None if ritual or free_cast or ki or spell.level == 0 else _pick_slot(
        char, spell, slot_id, slot_level, pact_only=invocation is not None)
    missing = [w for w in cast_warnings(char, spell, ritual, slotless=free_cast or ki, quickened=quickened) if w not in (confirm or [])]
    if missing:
        raise HTTPException(status_code=409, detail={"code": "cast_confirm", "warnings": missing})

    if (not ritual and character_edition(char) == "2024" and _cast_kind(char, spell) == "action"
            and not _LONG_CASTING.search(spell.casting_time or "") and not war_magic):
        _refuse_surge_magic(char)
    if ki_pool is not None:
        if not _LONG_CASTING.search(spell.casting_time or ""):  # un lancio di minuti o ore non è un'azione del turno
            spend(char, _cast_kind(char, spell))  # 409 turn_slot_used: nulla è ancora scritto
        ki_pool.uses = (ki_pool.uses or 0) - ki_total
        add_history(session, char.id, "spell_cast", f"Lanciato {spell.name} con {ki_total} ki",
                     meta={"ki": ki_total, "slot_level": spell.level + ki_extra})
    elif arcanum is not None:
        spend(char, _cast_kind(char, spell))  # 409 turn_slot_used: nulla è ancora scritto
        if arcanum.free_key is not None:  # prima dell'UPDATE degli usi (_charge_pact_use), che lo porta con sé
            pact_row.options = {**(pact_row.options or {}), FREE_CASTS: [*spent_free_casts(pact_row), arcanum.free_key]}
        add_history(session, char.id, "spell_cast", f"Lanciato {spell.name} (Arcanum Mistico)",
                     meta={"slot_level": spell.level, "arcanum": True})
    elif free_at_will:
        spend(char, _cast_kind(char, spell))  # 409 turn_slot_used: nulla è ancora scritto
        add_history(session, char.id, "spell_cast", f"Lanciato {spell.name} a volontà")
    elif free_state is not None:
        data = free_state.get("data") or {}
        if (turn_slot := data.get("free_cast_slot", "action")) is not None:  # ``None``: parte di un'altra azione (Magia Stregata)
            spend(char, turn_slot)  # 409 turn_slot_used: nulla è ancora scritto
        if not data.get("free_cast_keep"):  # il Mantello di Maestà ripete il lancio finché dura
            remove_state(char, free_state["key"])
        no_concentration = no_concentration or bool(data.get("no_concentration"))  # l'opzione al lancio vale anche qui (Rinforzi Fatati)
        if data.get("then"):  # lo stato che il lancio avvia al posto della concentrazione (durata propria)
            begin_state(char, StateSpec(**data["then"]), free_state.get("feature_key") or free_state["key"], free_state.get("name"))
        add_history(session, char.id, "spell_cast", f"Lanciato {spell.name} senza slot ({free_state.get('name') or free_state['key']})")
    elif ritual:
        add_history(
            session, char.id, "spell_ritual_cast",
            f"Lancio rituale: {spell.name}",
            meta={"ritual": True},
        )
    elif slot is not None:
        slot.use_slot()
        add_history(session, char.id, "spell_cast",
                     f"Lanciato {spell.name} (slot {slot.level})",
                     meta={"slot_level": slot.level, **({"is_pact": True} if slot.is_pact else {})})
    else:
        add_history(session, char.id, "spell_cast", f"Lanciato {spell.name}")
    _mark_cast(char, spell, slot is not None, ritual)
    if slot is not None and spell.srd_index:  # Rompi-Incantesimi: lo slot dell'ultimo lancio del turno, da rendere a lancio concluso
        turn = get_turn(char)
        turn["last_slot_cast"] = {"spell": spell.srd_index, "level": slot.level, "pact": bool(slot.is_pact)}
        char.turn_state = turn
    if slot is not None:
        mark_tides_due(char, spell)  # Maree del Caos 2024 spese: il lancio con slot apre la tabella
    end_on_action(char, "cast", spell)
    after_cast(char, spell, slot.level if slot is not None else None)  # i privilegi delle scuole del Mago (dopo end_on_action: le finestre nuove restano)
    if casts_verbally(spell) and not silent:  # Incantesimo Celato: nessuna componente verbale, il nascondiglio resta
        end_hide(session, char)

    level = slot.level if slot is not None else spell.level
    needs_concentration, rounds = _slot_concentration(char, spell, level) if spell.is_concentration else (False, None)
    if needs_concentration and not no_concentration:
        start_concentration(char, spell.id, rounds, level=level)
    return pact_row


async def _charge_pact_use(session: AsyncSession, row: Ability | None) -> None:
    """Spende l'uso del privilegio con un UPDATE condizionato: due lanci insieme non spendono lo stesso uso (409 ``no_uses``,
    e l'errore annulla tutto il lancio)."""
    if row is not None:
        await _spend_atomically(session, row, 1)


@router.get("/{char_id}/spells", response_model=list[SpellRead])
async def list_spells(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
    q: str | None = None,
) -> list[SpellRead]:
    char = await get_owned_full(char_id, user_id, session)
    spells = char.spells
    if q:
        try:
            from rapidfuzz import process, fuzz
            names = [s.name for s in spells]
            matches = process.extract(q, names, scorer=fuzz.partial_ratio, limit=20, score_cutoff=40)
            matched_names = {m[0] for m in matches}
            spells = [s for s in spells if s.name in matched_names]
        except ImportError:
            spells = [s for s in spells if q.lower() in s.name.lower()]
    out = [SpellRead.model_validate(s) for s in spells]
    fill_spell_stats(char, out)
    return out


@router.post("/{char_id}/spells", response_model=SpellRead, status_code=201)
async def add_spell(
    char_id: int,
    body: SpellCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
    confirm: bool = False,
) -> Spell:
    char = await get_owned_full(char_id, user_id, session)
    _check_class(char, body.class_id)
    pick = None
    if body.pick_id:  # Segreti Magici: l'incantesimo è di qualsiasi classe e passa alla classe del bardo
        pick = spell_pick_target(char, body.pick_id, body.level, body.class_id, body.name, body.srd_index, body.is_ritual, body.school)
        body.class_id = pick[0].id
    else:
        ensure_new_spell(char, body.name, body.srd_index)
    spell = Spell(character_id=char_id, **body.model_dump(exclude={"pick_id"}))
    spell.in_spellbook = bool(pick and pick[1].spell_pick == "book")  # la scelta del Libro lo scrive gratis; il resto si copia
    if body.is_prepared and body.level >= 1 and not body.always_prepared:
        if (refusal := prepare_refusal(char, spell)) is not None:
            raise HTTPException(status_code=refusal[0], detail={"code": refusal[1]})
        _ensure_prepare_capacity(char, body.class_id)
        _check_rest_window(char, spell, confirm)
    spell.is_prepared = spell.is_prepared or body.always_prepared
    session.add(spell)
    await session.flush()
    if pick:
        consume_spell_pick(session, char, *pick, spell)
    elif spell.level == 0:  # un trucchetto aggiunto a mano riempie la scelta dei trucchetti di classe
        if spell not in char.spells:
            char.spells.append(spell)
        reconcile_choices(char)
    return spell


@router.patch("/{char_id}/spells/{spell_id}", response_model=SpellRead)
async def update_spell(
    char_id: int,
    spell_id: int,
    body: SpellUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
    confirm: bool = False,
) -> Spell:
    char = await get_owned_full(char_id, user_id, session)
    result = await session.execute(
        select(Spell).where(Spell.id == spell_id, Spell.character_id == char_id)
    )
    spell = result.scalar_one_or_none()
    if spell is None:
        raise HTTPException(status_code=404, detail="Spell not found")
    data = body.model_dump(exclude_unset=True)
    _check_class(char, data.get("class_id"))
    if data.get("always_prepared") is None:
        data.pop("always_prepared", None)
    refuse_null(Spell, data)
    new_always = data.get("always_prepared", spell.always_prepared)
    if new_always:
        if data.get("is_prepared") is False:
            raise HTTPException(status_code=400, detail={"code": "always_prepared"})
        data["is_prepared"] = True
    new_level = data.get("level", spell.level)
    if data.get("is_prepared") is True and not spell.is_prepared and new_level >= 1 and not new_always:
        if (refusal := prepare_refusal(char, spell)) is not None:
            raise HTTPException(status_code=refusal[0], detail={"code": refusal[1]})
        _ensure_prepare_capacity(char, data.get("class_id", spell.class_id))
    if data.get("is_prepared") in (True, False) and data["is_prepared"] != bool(spell.is_prepared) and new_level >= 1 and not new_always:
        _check_rest_window(char, spell, confirm)
    for field, value in data.items():
        setattr(spell, field, value)
    return spell


@router.delete("/{char_id}/spells/{spell_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_spell(
    char_id: int,
    spell_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
    confirm: bool = False,
) -> None:
    char = await get_owned_full(char_id, user_id, session)
    result = await session.execute(
        select(Spell).where(Spell.id == spell_id, Spell.character_id == char_id)
    )
    spell = result.scalar_one_or_none()
    if spell is None:
        raise HTTPException(status_code=404, detail="Spell not found")
    if spell.level == 0 or spell.is_prepared:
        _check_rest_window(char, spell, confirm)
    if char.concentrating_spell_id == spell_id:
        end_concentration(char)
        await session.flush()
        await release_concentration_effects(session, char)
    if release_spell_pick(char, spell):
        if spell in char.spells:  # altrimenti la scelta dei trucchetti di classe lo riconterebbe
            char.spells.remove(spell)
        reconcile_choices(char)  # la scelta torna in coda: un errore di battitura si recupera
    await session.delete(spell)


@router.get("/{char_id}/spellbook/cost", response_model=SpellCopyCost)
async def spellbook_cost(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
    level: int = 1,
    school: str | None = None,
    mode: str = "copy",
) -> SpellCopyCost:
    """Tempo e oro per copiare nel Libro un incantesimo di ``level`` e ``school`` (dimezzati da un «Sapiente»)."""
    char = await get_owned_full(char_id, user_id, session)
    if mode not in MODES or not 1 <= level <= 9:
        raise HTTPException(status_code=422, detail={"code": "bad_copy_mode"})
    cost = copy_cost(char, level, school, mode)
    return SpellCopyCost(hours=cost.hours, gold=cost.gold, halved=cost.halved)


@router.post("/{char_id}/spells/{spell_id}/copy", response_model=CharacterFull)
async def copy_spell_to_book(
    char_id: int,
    spell_id: int,
    body: SpellCopyRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CharacterFull:
    """Copia l'incantesimo nel Libro del Mago (o nella copia di riserva) pagando l'oro: ogni rifiuto viene prima di spendere."""
    from api.services.containers import withdraw  # import locale: containers importa il modello degli oggetti
    char = await get_owned_full(char_id, user_id, session)
    spell = next((s for s in char.spells if s.id == spell_id), None)
    if spell is None:
        raise HTTPException(status_code=404, detail="Spell not found")
    if (refusal := book_refusal(char, spell, body.mode)) is not None:
        raise HTTPException(status_code=refusal[0], detail={"code": refusal[1]})
    cost = copy_cost(char, spell.level, spell.school, body.mode)
    withdraw(char, "gold", cost.gold)  # 409 insufficient_funds
    if body.mode == "backup":
        spell.in_backup = True
    else:
        spell.in_spellbook = True
    add_history(session, char.id, "spellbook",
                 f"Libro degli Incantesimi: {spell.name} ({body.mode}), {cost.hours:g} h e {cost.gold} mo",
                 meta={"mode": body.mode, "spell_id": spell.id, "hours": cost.hours, "gold": cost.gold})
    return await build_character_response(session, char)


@router.post("/{char_id}/spellbook/lost", response_model=CharacterFull)
async def lose_spellbook(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CharacterFull:
    """Il libro è perso: resta ciò che c'è nella copia di riserva (che diventa il libro); il resto si ritrascrive se preparato."""
    char = await get_owned_full(char_id, user_id, session)
    if not any(wizard_row(char, SimpleNamespace(class_id=c.id)) is not None for c in char.classes):
        raise HTTPException(status_code=422, detail={"code": "no_spellbook"})
    for spell in char.spells:
        if spell.level >= 1 and wizard_row(char, spell) is not None:
            spell.in_spellbook, spell.in_backup = bool(spell.in_backup), False
    add_history(session, char.id, "spellbook", "Libro degli Incantesimi perso")
    return await build_character_response(session, char)


@router.post("/{char_id}/spells/{spell_id}/use", response_model=CharacterFull)
async def use_spell(
    char_id: int,
    spell_id: int,
    body: SpellUseRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CharacterFull:
    char = await get_owned_full(char_id, user_id, session)

    # Verify the spell belongs to this character
    result = await session.execute(
        select(Spell).where(Spell.id == spell_id, Spell.character_id == char_id)
    )
    spell = result.scalar_one_or_none()
    if spell is None:
        raise HTTPException(status_code=404, detail="Spell not found")
    refuse_if_incapacitated(char)  # ogni lancio costa un'azione, un'azione bonus o una reazione (2014 pag. 189-190, 291; 2024 pag. 369)
    if spell.srd_index == "divine-smite" and character_edition(char) == "2024":  # si sceglie dopo un colpo, mai da elenco
        raise HTTPException(status_code=409, detail={"code": "smite_on_hit"})

    removal = None  # Task 48: cosa toglie il lancio e a chi, tutto controllato prima di spendere lo slot
    rule = spell_removal(character_edition(char), spell.srd_index, spell.name)  # per srd_index o, in mancanza, per nome
    if body.removal is not None:
        if rule is None:
            raise HTTPException(status_code=422, detail={"code": "not_a_removal_spell"})
        picked = plan(rule, body.removal.conditions, rule.conditions)
        removal = (rule, picked, await resolve_targets(session, char, rule, body.removal.targets), body.removal.conditions is not None)

    fx_level = cast_level(char, spell, body.slot_id, body.slot_level)
    await validate_spell_targets(session, char, spell, fx_level, body.targets, body.choices, body.options or [])  # prima di spendere
    if (character_edition(char) == "2024" and not (body.free_cast or body.ki or body.as_ritual)
            and (found := spell_effect("2024", spell.srd_index, spell.name)) and found[1].on_hit):
        spend(char, "bonus")  # punizione 2024 lanciata da elenco: costa l'azione bonus, 409 turn_slot_used prima di spendere lo slot
    # lo stato del lancio gratuito, letto prima che il lancio lo chiuda: senza Concentrazione, con la durata del suo «then»
    free = ((free_cast_state(char, spell) or {}).get("data") or {}) if body.free_cast else {}
    await _charge_pact_use(session, _consume_cast(
        session, char, spell, body.slot_id, body.slot_level, body.as_ritual, body.confirm, body.free_cast,
        body.ki, body.ki_extra, silent=bool({SUBTLE_KEY, PSYCHIC_SILENT} & set(body.options or [])),
        war_magic=bool(WAR_MAGIC_KEYS & set(body.options or [])), quickened=QUICKENED_KEY in (body.options or []),
        no_concentration_option=bool({NO_CONCENTRATION_KEY, THRALL_CAST, FEY_NO_CONCENTRATION_KEY} & set(body.options or []))))
    spell_fx = await apply_spell_effects(session, char, spell, fx_level, body.targets, body.choices, body.options or [],
                                         no_concentration=bool({NO_CONCENTRATION_KEY, THRALL_CAST, FEY_NO_CONCENTRATION_KEY} & set(body.options or []))
                                         or bool(free.get("no_concentration")), lasts=free.get("then"))
    if spell.srd_index == "find-steed" and not (body.free_cast or body.as_ritual) and any(
            s.key == STEED for s, _row in active_features(char)):  # Destriero Fedele: il lancio con slot crea il destriero del suo livello
        await session.refresh(char, attribute_names=["companions"])
        make_steed(char, "", fx_level)
    _close_twinned(char)  # un nuovo lancio: il segno di Raddoppiato di uno precedente non vale più
    marks = _slot_marks(char)
    opts = use_options(session, char, "cast", body, spell=spell, casting_level=_cast_level(spell, body.slot_level, body.as_ritual),
                       slotless=bool(body.free_cast or body.as_ritual), damage_type=cast_damage_type(char, spell, body.choices))
    if not (body.free_cast or body.ki or body.as_ritual):
        _mark_turn_slot(char, spell, marks, await active_encounter_row(session, char.id) is not None)
    await deliver_temp_gifts(session, char, opts)  # Passo Rinfrescante su un altro PG della serata
    removal_lines = None
    if removal is not None:  # stessa transazione del lancio: o paga e toglie, o nulla
        rule, (conds, untracked), targets, explicit = removal
        removal_lines = await apply_removal(session, char, rule, conds, untracked, targets, explicit=explicit)
    _end_cast(char, opts)
    rolls, total = roll_option_dice(char, opts)
    await release_concentration_effects(session, char)
    response = await build_character_response(session, char)
    response.option_result = option_result(opts, rolls, total)
    response.spell_effects = spell_fx
    if rule is None and looks_like_removal(spell.name):  # mai in silenzio: l'app non sa cosa toglie
        removal_lines = [NOT_RECOGNIZED]
    response.removal_result = removal_lines
    # Dadi che il server non sa tirare: l'incantesimo si lancia lo stesso, senza danno, e la scheda lo dice
    response.damage_unrollable = any(d and not DICE_RE.match(d.strip()) for d in (spell.damage_dice, spell.extra_damage_dice))
    return response


@router.get("/{char_id}/spells/{spell_id}/cast-check", response_model=list[str])
async def cast_check(
    char_id: int,
    spell_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
    ritual: bool = False,
    slotless: bool | None = None,
    quickened: bool = False,
) -> list[str]:
    """Le regole che questo lancio violerebbe, da confermare prima di tirare i dadi. Il lancio le ricontrolla.
    ``slotless`` non indicato: come si paga non è ancora scelto, e chi può lanciare senza slot non conferma il secondo."""
    char = await get_owned_full(char_id, user_id, session)
    spell = next((s for s in char.spells if s.id == spell_id), None)
    if spell is None:
        raise HTTPException(status_code=404, detail="Spell not found")
    if slotless is None:
        pact = pact_cast(char, spell)
        slotless = (free_cast_state(char, spell) is not None or at_will(char, spell) or ki_cast_info(char, spell) is not None
                    or (pact is not None and pact.kind == "arcanum"))
    return cast_warnings(char, spell, ritual, slotless=slotless, quickened=quickened)


@router.post("/{char_id}/spells/{spell_id}/attack", response_model=SpellAttackResult)
async def spell_attack(
    char_id: int,
    spell_id: int,
    body: SpellAttackRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> SpellAttackResult:
    char = await get_owned_full(char_id, user_id, session)
    spell = next((s for s in char.spells if s.id == spell_id), None)
    if spell is None:
        raise HTTPException(status_code=404, detail="Spell not found")
    if (spell.attack_save or "").strip().upper() != "ATK":
        raise HTTPException(status_code=400, detail="Spell is not an attack spell")
    refuse_if_incapacitated(char)

    cast_block = spell_fx = None
    lit = hurled_lit(char, spell.srd_index, spell.name)
    if body.with_inspiration:
        spend_inspiration_attack(char, spell_id=spell.id)
    elif lit is not None:  # Produrre Fiamma 2024: non è un lancio, si scaglia la fiamma accesa con un'azione Magia
        if not lit:
            raise HTTPException(status_code=409, detail={"code": "flame_not_lit"})
        _refuse_surge_magic(char)
        _mark_turn_slot(char, spell, _slot_marks(char), await active_encounter_row(session, char.id) is not None, kind="action")
    else:
        fx_level = cast_level(char, spell, body.slot_id, body.slot_level)
        await validate_spell_targets(session, char, spell, fx_level, body.targets, body.choices, body.cast_options)  # prima di spendere
        await _charge_pact_use(session, _consume_cast(session, char, spell, body.slot_id, body.slot_level, body.ritual, body.confirm,
                                                      silent=bool({SUBTLE_KEY, PSYCHIC_SILENT} & set(body.cast_options or [])),
                                                      war_magic=bool(WAR_MAGIC_KEYS & set(body.cast_options or [])), quickened=QUICKENED_KEY in (body.cast_options or []),
                                                      no_concentration_option=bool({NO_CONCENTRATION_KEY, THRALL_CAST, FEY_NO_CONCENTRATION_KEY} & set(body.cast_options or []))))
        spell_fx = await apply_spell_effects(session, char, spell, fx_level, body.targets, body.choices, body.cast_options,
                                             no_concentration=bool({NO_CONCENTRATION_KEY, THRALL_CAST, FEY_NO_CONCENTRATION_KEY} & set(body.cast_options)))
        cast_body = SimpleNamespace(options=body.cast_options, option_inputs=body.cast_option_inputs)
        _close_twinned(char)
        marks = _slot_marks(char)
        cast_opts = use_options(session, char, "cast", cast_body, spell=spell,
                                casting_level=_cast_level(spell, body.slot_level, body.ritual), slotless=bool(body.ritual),
                                damage_type=cast_damage_type(char, spell, body.choices))
        if not body.ritual:
            _mark_turn_slot(char, spell, marks, await active_encounter_row(session, char.id) is not None)
        await deliver_temp_gifts(session, char, cast_opts)
        _end_cast(char, cast_opts)
        cast_rolls, cast_total = roll_option_dice(char, cast_opts)
        cast_block = option_result(cast_opts, cast_rolls, cast_total)
    await release_concentration_effects(session, char)

    caster = spell_stats(char, spell)
    applied = modifiers_for(char, "attack", spell=spell)
    opts = use_options(session, char, "attack", body, spell=spell)
    merge_options(applied, opts)
    bonus = (caster.attack_bonus if caster else char.proficiency_bonus) + applied.flat + opts.bonus
    outcome = resolve_body(body, applied)
    die = outcome.kept
    total = die + bonus
    is_fumble = die == 1
    is_critical = die >= applied.crit_min or (opts.force_crit and not is_fumble)
    # I dadi che il giocatore ha confermato prima del tiro (Sortilegio, Marchio del Cacciatore) valgono per il danno di questo attacco
    option_rolls, option_total = roll_option_dice(char, opts, is_critical)
    attack_block = option_result(opts, option_rolls, option_total)
    carry = get_turn(char)
    carry.pop(SPELL_ATTACK_DICE, None)
    if option_rolls:
        carry[SPELL_ATTACK_DICE] = {"spell_id": spell.id, "dice": pairs(opts.rolled_dice), "block": attack_block.model_dump(mode="json")}
    char.turn_state = carry

    text = f"Attacco incantesimo {spell.name}: {d20_history_label(outcome)}+{bonus}={total}" + (
        " (CRITICO!)" if is_critical else " (FUMBLE!)" if is_fumble else ""
    )
    if body.with_inspiration:
        text = f"Reroll ispirazione: {text}"
    add_history(session, char_id, "spell_attack", text)
    end_hide(session, char)
    end_on_action(char, "attack")
    record_dice(char, d20_records(outcome), total)

    firing = await dispatch(
        session, char, "attack_rolled",
        {
            "spell_id": spell.id,
            "to_hit_die": die,
            "to_hit_total": total,
            "is_critical": is_critical,
            "is_fumble": is_fumble,
        },
    )
    notifications = collect_homebrew_notifications(firing)
    remember_roll(char, "attack", opts, {
        "die": die, "dice": outcome.dice, "mode": outcome.mode, "bonus": bonus, "total": total,
        "notes": applied.notes, "auto_fail": False, "description": "",
    }, spell_id=spell.id)

    twinned = _twinned_attack(char, spell, body.mode, applied, bonus, keep=body.with_inspiration)
    character = await build_character_response(session, char)
    character.spell_effects = spell_fx
    return SpellAttackResult(
        twinned_attack=twinned,
        spell_name=spell.name,
        to_hit_die=die,
        dice=outcome.dice,
        mode=outcome.mode,
        mode_applied=outcome.mode,
        notes=applied.notes,
        to_hit_bonus=bonus,
        to_hit_total=total,
        is_critical=is_critical,
        is_fumble=is_fumble,
        caster_class=caster.class_name if caster else None,
        cast_option_result=cast_block,
        option_result=attack_block,
        character=character,
        homebrew_notifications=notifications or None,
    )


def _cast_level(spell: Spell, slot_level: int | None, ritual: bool = False) -> int:
    """Il livello a cui si lancia: quello dello slot (un incantesimo di livello superiore «assume il livello superiore»),
    il proprio se è un trucchetto, un rituale o un lancio senza slot."""
    return slot_level if slot_level and slot_level >= spell.level and not ritual else spell.level


def _end_cast(char: Character, opts: Any = None) -> None:
    """Le opzioni del lancio hanno visto cosa c'era prima di questo incantesimo: il segno non serve più. ``opts``: quelle scelte
    al lancio; le opzioni di Metamagia restano sul turno, perché Trasmutato (al danno) rispetti il limite di una per incantesimo."""
    turn = get_turn(char)
    meta = [k for k in (opts.keys if opts is not None else []) if k.startswith("sorcerer.metamagic_")]
    changed = any([turn.pop("cast_prior_slot", None) is not None, turn.pop(EMPOWERED_USED, None) is not None,  # nuovo lancio: Invocazione Potente si riapre
                   turn.pop(AFFINITY_USED, None) is not None,  # e Affinità Elementale
                   turn.pop(SPELL_ATTACK_DICE, None) is not None])  # e i dadi extra di un attacco precedente (forse mancato) non contano
    if meta or turn.get("cast_metamagic"):
        turn["cast_metamagic"], changed = meta, True
    if changed:
        char.turn_state = turn


def _mark_empowered(char: Character, spell: Spell) -> None:
    """Invocazione Potente somma l'Intelligenza a un solo tiro di danno per lancio: il tiro appena contato chiude il bonus."""
    if any(spec.key == "wizard.empowered_evocation" and _empowered(RuleContext(
            char=char, edition=character_edition(char), roll="damage", spell=spell, class_row=row, class_level=row.level))
           for spec, row in active_features(char)):
        turn = get_turn(char)
        turn[EMPOWERED_USED] = spell.id
        char.turn_state = turn


def _close_twinned(char: Character) -> None:
    """Il segno di Incantesimo Raddoppiato vale per un solo lancio: un lancio nuovo lo chiude, l'opzione lo riapre."""
    turn = get_turn(char)
    if turn.pop(TWINNED_TURN_KEY, None) is not None:
        char.turn_state = turn


def _twinned_attack(char: Character, spell: Spell, mode: RollMode, applied: Any, bonus: int, keep: bool = False) -> dict | None:
    """Incantesimo Raddoppiato: il secondo bersaglio ha il suo tiro per colpire, con lo stesso modo e lo stesso bonus. Il
    critico (o il 1 naturale) resta sul turno per il danno del secondo bersaglio. Il rilancio dell'altro bersaglio non
    tocca il suo tiro: ``keep`` restituisce quello già fatto."""
    twin = (char.turn_state or {}).get(TWINNED_TURN_KEY)
    if not twin or twin.get("spell_id") != spell.id:
        return None
    if keep and twin.get("attack"):
        return twin["attack"]
    outcome = resolve_applied(mode, None, None, applied)
    record_dice(char, d20_records(outcome), outcome.kept + bonus)
    critical = outcome.kept >= applied.crit_min
    result = {"die": outcome.kept, "dice": outcome.dice, "mode": outcome.mode, "total": outcome.kept + bonus,
              "is_critical": critical, "is_fumble": outcome.kept == 1}
    turn = get_turn(char)
    turn[TWINNED_TURN_KEY] = {**twin, "is_critical": critical, "is_fumble": result["is_fumble"], "attack": result}
    char.turn_state = turn
    return result


@router.patch("/{char_id}/concentration", response_model=CharacterFull)
async def update_concentration(
    char_id: int,
    body: ConcentrationUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CharacterFull:
    char = await get_owned_full(char_id, user_id, session)
    if body.spell_id is None:
        if is_concentrating(char):  # il log della serata e la Cronologia dicono che è stata interrotta
            name = next((s.name for s in char.spells if s.id == char.concentrating_spell_id),
                        item_spell_held(char).get("name"))
            add_history(session, char.id, "concentration", "Concentrazione interrotta" + (f": {name}" if name else ""))
        end_concentration(char)
    elif body.rounds is not None or body.spell_id != char.concentrating_spell_id:
        # Senza `rounds` sullo stesso incantesimo non cambia nulla: il lancio ha già avviato il contatore.
        spell = next((s for s in char.spells if s.id == body.spell_id), None)
        if spell is None:
            raise HTTPException(status_code=404, detail="spell_not_found")
        rounds = body.rounds if body.rounds is not None else parse_duration_rounds(spell.duration)
        start_concentration(char, body.spell_id, rounds)
    await release_concentration_effects(session, char)
    return await build_character_response(session, char)


# ---------------------------------------------------------------------------
# Concentration saving throw
# ---------------------------------------------------------------------------

@router.post("/{char_id}/concentration/save", response_model=ConcentrationSaveResult)
async def concentration_save(
    char_id: int,
    body: ConcentrationSaveRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> ConcentrationSaveResult:
    char = await get_owned_full(char_id, user_id, session)
    return await roll_concentration_save(
        char, body.damage, session, body.mode, body.dice,
    )


# ---------------------------------------------------------------------------
# Spell damage roll
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Upcast:
    """Scalata che «+NdM per livello» non dice; il client la rispecchia (UPCAST_RULES in webapp/src/lib/srd/catalog.ts)."""
    dice: str | None = None  # dadi per passo, anche quando la riga non li ha
    step: int = 1  # livelli di slot per passo
    max_extra: int | None = None  # dadi in più al massimo
    both: bool = False  # i dadi in più valgono per ciascuna parte del danno


# Per incantesimo ed edizione di chi lancia (docs/superpowers/rules/{2014,2024}/spells.md)
_UPCAST = {
    ("spiritual-weapon", "2014"): _Upcast(dice="1d8", step=2),  # +1d8 ogni due slot oltre il 2° (pag. 215)
    ("flame-blade", "2014"): _Upcast(dice="1d6", step=2),  # +1d6 al 4°, 6° e 8° (pag. 247)
    ("hail-of-thorns", "2014"): _Upcast(max_extra=5),  # massimo 6d10 (pag. 266)
    ("sleep", "2014"): _Upcast(dice="2d8"),  # la riserva di PF cresce di 2d8 per slot (pag. 279)
    ("flame-strike", "2024"): _Upcast(both=True),  # +1d6 fuoco e +1d6 radiosi per livello (pag. 275)
    ("jallarzis-storm-of-radiance", "2024"): _Upcast(both=True),  # +1d10 radiosi e +1d10 da tuono per livello (pag. 289)
}
# Danno «dadi + modificatore da incantatore» (2014 pag. 215; 2024 pag. 275, 302, 319-320)
_ADDS_SPELL_MOD = {("spiritual-weapon", "2014"), ("spiritual-weapon", "2024"), ("flame-blade", "2024"), ("arcane-sword", "2024")}
# Tipo del danno deciso da una scelta del lancio che non è «damage_type»: Scudo di Fuoco caldo fuoco, freddo freddo (2014 pag. 275; 2024 pag. 274)
_TYPE_BY_CHOICE = {"fire_shield": ("shield", {"warm": "fire", "cold": "cold"})}


def _cast_choice_type(char: Character, spell: Spell) -> str | None:
    """Il tipo di danno che decide la scelta dell'incantesimo in corso (nell'orologio su chi lancia), o ``None``."""
    found = spell_effect(character_edition(char), spell.srd_index, spell.name)
    if not found or (rule := _TYPE_BY_CHOICE.get(found[0].key)) is None:
        return None
    clock = next((s for s in char.active_states or [] if s.get("key") == f"{SPELL_CLOCK_PREFIX}{found[0].key}"), None)
    return rule[1].get((((clock or {}).get("data") or {}).get("state_data") or {}).get("choices", {}).get(rule[0]))


@router.post(
    "/{char_id}/spells/{spell_id}/roll_damage",
    response_model=RollDamageResult,
)
async def roll_spell_damage(
    char_id: int,
    spell_id: int,
    body: RollDamageRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
    lang: Annotated[str, Depends(get_current_lang)],
) -> RollDamageResult:
    char = await get_owned_full(char_id, user_id, session)
    spell = next((s for s in char.spells if s.id == spell_id), None)
    if spell is None:
        raise HTTPException(status_code=404, detail="Spell not found")
    if not spell.damage_dice:
        raise HTTPException(status_code=400, detail="Spell has no damage_dice")

    casting_level = body.casting_level if body.casting_level is not None else spell.level
    if casting_level < spell.level:
        raise HTTPException(
            status_code=400,
            detail=f"casting_level {casting_level} < spell.level {spell.level}",
        )
    if casting_level > 9:
        raise HTTPException(status_code=400, detail="casting_level must be <= 9")

    # Parse spell.damage_dice using shared regex
    m = DICE_RE.match(spell.damage_dice.strip())
    if not m:
        raise HTTPException(status_code=422, detail={"code": "bad_damage_dice"})
    base_count = int(m.group(1))
    if spell.level == 0:
        base_count *= cantrip_dice_multiplier(char.total_level)
    sides = int(m.group(2))
    base_bonus = int(m.group(3)) if m.group(3) else 0
    second_gained = 0
    edition = character_edition(char)
    rule = _UPCAST.get((spell.srd_index or "", edition), _Upcast())
    per_level = rule.dice or spell.higher_levels_dice
    # Upcast automatico: i dadi per livello extra si sommano ai dadi base (solo incantesimi di livello >= 1, stessi lati).
    if spell.level > 0 and per_level:
        um = DICE_RE.match(per_level.strip())
        if um and int(um.group(2)) == sides:
            steps = (casting_level - spell.level) // rule.step
            gained = int(um.group(1)) * steps
            if rule.max_extra is not None:
                gained = min(gained, rule.max_extra)
            base_count += gained
            second_die = DICE_RE.match((spell.extra_damage_dice or "").strip())
            same_sides = bool(second_die) and int(second_die.group(2)) == sides
            if rule.both:  # un dado in più di ciascun tipo
                second_gained = gained if same_sides else 0
            # I dadi in più sono del tipo scelto al lancio: se non è quello principale lasciano il tiro e passano alla seconda parte
            # di quel tipo (Colpo Infuocato: radioso), o senza una si applicano a mano (Fame di Hadar 2024: l'acido, pag. 286)
            elif (up := cast_upcast_type(char, spell)) and up != canonical_damage_type(spell.damage_type):
                base_count -= gained
                second_gained = gained if same_sides and up == spell.extra_damage_type else 0
            # Bonus fisso per livello (Dardo incantato: +1 per ogni dardo extra).
            base_bonus += int(um.group(3) or 0) * steps

    # Privilegi che aggiungono un fisso ai danni di un incantesimo (Incantesimi Potenti)
    base_bonus += modifiers_for(char, "damage", spell=spell).flat
    if (spell.srd_index, edition) in _ADDS_SPELL_MOD and (caster := spell_stats(char, spell)):
        base_bonus += effective_ability_mod(char, caster.ability)
    _mark_empowered(char, spell)

    # Apply critical (double dice count, not the flat bonus)
    dice_count = base_count * 2 if body.is_critical else base_count
    if body.main_rolls is not None:
        if len(body.main_rolls) != dice_count:
            raise HTTPException(
                status_code=400,
                detail=f"main_rolls length {len(body.main_rolls)} != expected {dice_count}",
            )
        if any(v < 1 or v > sides for v in body.main_rolls):
            raise HTTPException(
                status_code=400,
                detail=f"main_rolls values must be in [1, {sides}]",
            )
        main_rolls = list(body.main_rolls)
    else:
        main_rolls = [random.randint(1, sides) for _ in range(dice_count)]

    # Seconda parte del danno dell'incantesimo (di un altro tipo; il giocatore sceglie fra i tipi se ce n'e' piu' di uno)
    second_count = second_sides = 0
    second_type: str | None = None
    if spell.extra_damage_dice:
        sm = DICE_RE.match(spell.extra_damage_dice.strip())
        if not sm:
            raise HTTPException(status_code=422, detail={"code": "bad_damage_dice"})
        second_sides = int(sm.group(2))
        second_count = (int(sm.group(1)) + second_gained) * (2 if body.is_critical else 1)
        types = [t for t in (spell.extra_damage_type or "").split("|") if t]
        if body.extra_damage_type is not None and body.extra_damage_type not in types:
            raise HTTPException(status_code=422, detail={"code": "invalid_damage_type"})
        second_type = body.extra_damage_type or (types[0] if types else None)

    # Dadi extra scritti dal giocatore: si sommano, di tipo ignoto
    extra_bonus = 0
    extra_sides = 0
    extra_count = 0
    if body.extra_dice:
        em = DICE_RE.match(body.extra_dice)
        if em:
            extra_sides = int(em.group(2))
            extra_bonus = int(em.group(3)) if em.group(3) else 0
            extra_count = int(em.group(1)) * (2 if body.is_critical else 1)
    groups = [("second", second_count, second_sides), ("extra", extra_count, extra_sides)]
    extra_total = second_count + extra_count
    if body.extra_rolls is not None and extra_total:
        if len(body.extra_rolls) != extra_total:
            raise HTTPException(
                status_code=400,
                detail=f"extra_rolls length {len(body.extra_rolls)} != expected {extra_total}",
            )
        at = 0
        for _, count, group_sides in groups:
            if any(v < 1 or v > group_sides for v in body.extra_rolls[at:at + count]):
                raise HTTPException(
                    status_code=400,
                    detail=f"extra_rolls values must be in [1, {group_sides}]",
                )
            at += count
        all_extra = list(body.extra_rolls)
    else:
        all_extra = [random.randint(1, group_sides) for _, count, group_sides in groups for _ in range(count)]
    second_rolls, extra_rolls = all_extra[:second_count], all_extra[second_count:]

    base_type = chosen_damage_type(char, spell, body.damage_type) or _cast_choice_type(char, spell) or spell.damage_type  # il tipo scelto al lancio
    opts = use_options(session, char, "spell_damage", body, spell=spell, casting_level=casting_level, damage_type=canonical_damage_type(base_type))
    main_type = opts.damage_type or base_type  # Incantesimo Trasmutato
    await deliver_temp_gifts(session, char, opts)  # Incantesimi Potenti Migliorati
    if opts.maximize:  # Collera Distruttiva: valgono il massimo i dadi dei tipi che l'opzione tocca, mai quelli messi a mano
        def maximized(kind: str | None) -> bool:
            return opts.maximize_types is None or canonical_damage_type(kind) in opts.maximize_types
        if maximized(main_type):
            main_rolls = [sides] * len(main_rolls)
        if second_rolls and maximized(second_type):
            second_rolls = [second_sides] * len(second_rolls)
    # Adepto elementale: i dadi del tipo scelto che mostrano 1 contano come 2
    for kind, rolls in ((main_type, main_rolls), (second_type, second_rolls)):
        floor = modifiers_for(char, "spell_damage", spell=spell, damage_type=canonical_damage_type(kind)).damage_min_die if kind else 0
        if floor:
            rolls[:] = [max(v, floor) for v in rolls]
    option_rolls, option_total = roll_option_dice(char, opts, body.is_critical)
    carry = get_turn(char)
    carried = carry.pop(SPELL_ATTACK_DICE, None)  # i dadi dell'attacco con incantesimo appena fatto: valgono per questo tiro di danno
    char.turn_state = carry
    carried = carried if carried and carried["spell_id"] == spell.id else None
    carried_dice = carried["dice"] if carried else []
    total = (sum(main_rolls) + sum(second_rolls) + sum(extra_rolls) + base_bonus + extra_bonus + option_total + opts.bonus
             + sum(v for _, v in carried_dice))
    total = scale_damage(max(0, total), opts.multiplier)  # il danno arriva a 0, mai sotto (2014 pag. 196; 2024 pag. 27)
    half_damage = total // 2  # per difetto, in entrambe le edizioni

    parts = damage_parts([("main", main_type, sides, main_rolls), ("second", second_type, second_sides, second_rolls),
                          ("extra", None, extra_sides, extra_rolls)])
    breakdown_parts = [f"{len(main_rolls)}d{sides}={main_rolls}"]
    for part in parts[1:]:
        breakdown_parts.append(f"+{len(part['rolls'])}{part['kind']}={part['rolls']}")
    if base_bonus:
        breakdown_parts.append(f"{'+' if base_bonus >= 0 else ''}{base_bonus}")
    if extra_bonus:
        breakdown_parts.append(f"{'+' if extra_bonus >= 0 else ''}{extra_bonus}")
    if carried_dice:
        breakdown_parts.append(f"+{[v for _, v in carried_dice]}")
    if opts.keys:
        breakdown_parts.append(f"+{option_rolls}{opts.bonus:+d}" if option_rolls else f"{opts.bonus:+d}")
    breakdown = " ".join(breakdown_parts) + f" = {total}"

    record_dice(
        char,
        [(f"d{sides}", v) for v in main_rolls]
        + [(f"d{second_sides}", v) for v in second_rolls]
        + [(f"d{extra_sides}", v) for v in extra_rolls],
    )

    # Append to rolls_history if character supports it
    history_entry = {
        "type": "spell_damage",
        "spell_name": spell.name,
        "label": spell.name,  # l'ultimo tiro sulla card della serata: cosa e con quali dadi
        "notation": "+".join(f"{len(r)}d{s}" for s, r in ((sides, main_rolls), (second_sides, second_rolls),
                                                          (extra_sides, extra_rolls)) if r)
                    + (f"{base_bonus + extra_bonus:+d}" if base_bonus + extra_bonus else ""),
        "rolls": main_rolls + second_rolls + extra_rolls,
        "total": total,
        "damage_type": main_type,
        "casting_level": casting_level,
        "is_critical": body.is_critical,
        "timestamp": utc_now_iso(),  # il recap filtra per timestamp nella finestra della serata
    }
    if isinstance(char.rolls_history, list):  # niente commit qui: la richiesta ne fa uno solo, alla fine
        char.rolls_history = [*char.rolls_history, history_entry]
    dmg_slug = canonical_damage_type(main_type)
    add_history(session, char.id, "spell_damage",  # una riga nel log della serata: chi ha fatto quanti danni e di che tipo
                f"{spell.name}: {total} danni" + (f" da {LABELS_IT[dmg_slug]}" if dmg_slug in LABELS_IT else ""))

    all_extra = second_rolls + extra_rolls
    extra_kind = f"d{second_sides}" if second_rolls else (f"d{extra_sides}" if extra_rolls else None)

    result = RollDamageResult(
        rolls=main_rolls + all_extra,
        total=total,
        half_damage=half_damage,
        save_halves=_save_halves(char, spell),
        damage_type=main_type,
        breakdown=breakdown,
        casting_level=casting_level,
        is_critical=bool(body.is_critical),
        scaled_dice=f"{base_count}d{sides}",
        main_kind=f"d{sides}",
        main_rolls=main_rolls,
        option_result=option_result(opts, option_rolls, option_total, previous=OptionResult(**carried["block"]) if carried else None),
        extra_kind=extra_kind,
        extra_rolls=all_extra,
        extra_damage_type=second_type if second_rolls else None,
        parts=parts,
        twinned_damage=_twinned_damage(char, spell, base_count, sides, base_bonus),
        save_success_damage=half_damage if _potent_cantrip(char, spell) else None,
    )
    await _self_damage(session, char, opts, spell, result, lang)
    # I dadi delle opzioni vengono dopo quelli dell'incantesimo e si ritirano come loro; il loro fisso resta nel resto.
    base_dice = ([[sides, v] for v in main_rolls] + [[second_sides, v] for v in second_rolls]
                 + [[extra_sides, v] for v in extra_rolls])
    dice = base_dice + pairs(opts.rolled_dice) + carried_dice
    result.reroll_dice = dice
    turn = get_turn(char)
    turn["last_damage"] = {
        "roll_id": uuid.uuid4().hex, "spell_id": spell.id, "dice": dice,
        "main": len(main_rolls), "base": len(base_dice), "added": [], "multiplier": opts.multiplier, "mod": 0,
        "flat": base_bonus + extra_bonus + option_total - sum(v for _, v in opts.rolled_dice) + opts.bonus,
        "groups": [[p["label"], p["type"], p["kind"], len(p["rolls"])] for p in parts],
        "result": result.model_dump(mode="json"),
    }
    char.turn_state = turn
    return result


# Incantesimi di livello con TS e danno in cui il TS superato non dimezza (``docs/superpowers/rules/{2014,2024}/spells.md``):
# danno solo a TS fallito (prima riga), oppure danno che non dipende dal TS, che vale solo per l'effetto (punizioni e il resto).
_NO_HALF_ON_SAVE = {
    "disintegrate", "contagion", "black-tentacles", "hunger-of-hadar", "cordon-of-arrows", "dream", "geas",
    "contact-other-plane", "faithful-hound", "conjure-animals", "storm-of-vengeance",
    "blinding-smite", "banishing-smite", "searing-smite", "staggering-smite", "thunderous-smite", "wrathful-smite",
    "ensnaring-strike", "feeblemind", "heat-metal", "phantasmal-force", "web", "fount-of-moonlight", "bestow-curse",
}
# Uccisore Fantasma: nel 2014 il danno arriva solo a TS fallito; il 2024 dimezza a TS superato.
_NO_HALF_ON_SAVE_2014 = {"phantasmal-killer"}


def _save_halves(char: Character, spell: Spell) -> bool:
    """Un TS superato dimezza il danno? No per i trucchetti (Fiamma Sacra, Fiotto Acido, ...: il Trucchetto Potente passa da
    ``save_success_damage``) e per gli incantesimi elencati sopra, secondo l'edizione di chi lancia."""
    no_half = _NO_HALF_ON_SAVE | (_NO_HALF_ON_SAVE_2014 if character_edition(char) == "2014" else set())
    return spell.level > 0 and spell.srd_index not in no_half


def _potent_cantrip(char: Character, spell: Spell) -> bool:
    """Trucchetto Potente: un trucchetto di danno con un TS fa comunque metà danni a chi lo supera; dal 2024 anche quello con
    tiro per colpire che manca."""
    kind = (spell.attack_save or "").strip().upper()
    return spell.level == 0 and kind != "" and any(
        spec.save_half_cantrips and (kind != "ATK" or spec.cantrip_half_on_miss) for spec, _row in active_features(char))


async def _self_damage(session: AsyncSession, char: Character, opts: Any, spell: Spell, result: RollDamageResult, lang: str) -> None:
    """Saturazione Magica dal secondo uso: i dadi necrotici si tirano e si applicano a chi lancia con lo stesso percorso di ogni
    danno, ma senza resistenze né immunità (``damage_modifier="none"``). L'esito entra fra gli effetti mostrati."""
    from api.routers.hp import update_hp  # import locale: hp importa questo modulo
    from api.schemas.common import HPOp, HPUpdate
    for expr, damage_type in opts.self_damage:
        count, sides = (int(n) for n in expr.split("d"))
        rolls = [random.randint(1, sides) for _ in range(count)]
        record_dice(char, [(f"d{sides}", v) for v in rolls])
        total = sum(rolls)
        await update_hp(char.id, HPUpdate(op=HPOp.DAMAGE, value=total, damage_type=damage_type, damage_modifier="none"),
                        char.user_id, session, lang)
        note = {"it": f"{spell.name}: subisci {total} danni necrotici ({expr}), senza resistenze né immunità.",
                "en": f"{spell.name}: you take {total} necrotic damage ({expr}), ignoring resistance and immunity."}
        if result.option_result is not None:
            result.option_result.effects.append(note)


def _twinned_damage(char: Character, spell: Spell, count: int, sides: int, bonus: int) -> dict | None:
    """Incantesimo Raddoppiato: l'incantesimo con tiro per colpire ripete i danni per il secondo bersaglio (uno con TS tira una
    volta sola per entrambi). Il segno si consuma: vale per un solo tiro di danno."""
    turn = get_turn(char)
    twin = turn.pop(TWINNED_TURN_KEY, None)
    if not twin or twin.get("spell_id") != spell.id:
        return None
    char.turn_state = turn
    if (spell.attack_save or "").strip().upper() != "ATK" or twin.get("is_fumble"):  # il 1 naturale manca: nessun danno
        return None
    rolls = [random.randint(1, sides) for _ in range(count * (2 if twin.get("is_critical") else 1))]
    record_dice(char, [(f"d{sides}", v) for v in rolls])
    return {"rolls": rolls, "total": sum(rolls) + bonus}


@router.post("/{char_id}/spells/{spell_id}/roll_healing", response_model=RollHealingResult)
async def roll_spell_healing(
    char_id: int,
    spell_id: int,
    body: RollHealingRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> RollHealingResult:
    """PF che un incantesimo di cura restituisce (R41): dadi allo slot scelto, modificatore da incantatore e privilegi
    (Discepolo della Vita, Guarigione Suprema). Il server tira e somma; con ``apply_to_self`` li aggiunge a chi lancia."""
    from api.services.effects import apply_heal  # import locale: effects importa il router degli incantesimi
    char = await get_owned_full(char_id, user_id, session)
    spell = next((s for s in char.spells if s.id == spell_id), None)
    if spell is None:
        raise HTTPException(status_code=404, detail="Spell not found")
    healing = healing_spec(spell.srd_index, character_edition(char))
    if healing is None:
        raise HTTPException(status_code=400, detail={"code": "not_a_healing_spell"})
    level = body.casting_level if body.casting_level is not None else spell.level
    if level < spell.level or level > 9:
        raise HTTPException(status_code=400, detail="invalid casting_level")
    wanted = body.target_character_ids
    if len(set(wanted)) != len(wanted) or len(wanted) + body.apply_to_self > healing.targets:
        raise HTTPException(status_code=422, detail={"code": "invalid_target"})
    if body.apply_to_self and healing.targets == 1 and BLESSED_HEALER.key in body.options:  # l'unico bersaglio è chi lancia
        raise HTTPException(status_code=409, detail={"code": "option_unavailable", "key": BLESSED_HEALER.key})
    receivers = [*([char.id] if body.apply_to_self else []), *wanted]
    split = healing.pool and bool(body.amounts or len(receivers) > 1)  # il totale si divide (Guarigione di Massa, D-038)
    if split and (set(body.amounts) != set(receivers) or sum(body.amounts.values()) > healing_fixed(healing, spell.level, level)):
        raise HTTPException(status_code=422, detail={"code": "bad_allocation"})
    allies = [await ally_target(session, char, tid) for tid in wanted]  # PG seduti alla stessa serata attiva, prima di tirare
    if any(a.is_dead for a in allies):
        raise HTTPException(status_code=409, detail={"code": "target_dead"})
    count, sides = healing_dice(healing, spell.level, level)
    main_rolls = [random.randint(1, sides) for _ in range(count)]

    opts = use_options(session, char, "spell_healing", body, spell=spell, casting_level=level)
    applied = modifiers_for(char, "spell_healing", spell=spell, casting_level=level)
    maximized = bool(main_rolls) and (applied.maximize_healing or opts.maximize)
    if maximized:
        main_rolls = [sides] * len(main_rolls)
    option_rolls, option_total = roll_option_dice(char, opts)
    modifier = healing_fixed(healing, spell.level, level)
    if healing.add_mod:
        from core.game.stats import effective_ability_mod  # import locale
        caster = spell_stats(char, spell)
        modifier += effective_ability_mod(char, caster.ability) if caster else 0
    total = max(0, sum(main_rolls) + modifier + applied.flat + opts.bonus + option_total)
    record_dice(char, [(f"d{sides}", v) for v in main_rolls])
    parts = [f"{count}d{sides}={main_rolls}" if count else "fisso"]
    if modifier:
        parts.append(f"{modifier:+d}")
    if applied.flat:
        parts.append(f"{applied.flat:+d}")
    breakdown = " ".join(parts) + f" = {total}"
    given = dict.fromkeys(receivers, total)
    if split:  # i privilegi (Discepolo della Vita) si aggiungono alla parte di ogni creatura
        given = {tid: body.amounts[tid] + total - modifier for tid in receivers}
        total = sum(given.values())
        breakdown = " + ".join(str(n) for n in given.values()) + f" = {total}"
    healed = 0
    if body.apply_to_self:
        healed = (await apply_heal(session, char, given[char.id]))["healed"]
    healed_allies = []
    for ally in allies:  # riletto da zero: la cura parte dai PF veri (a 0 PF azzera i TS contro la morte)
        receiver = await load_receiver(session, ally.id)
        healed_allies.append({"id": receiver.id, "name": receiver.name, "healed": (await apply_heal(session, receiver, given[receiver.id], by=char, source=spell.name))["healed"]})
    self_healed = 0
    if opts.self_heal:
        self_healed = (await apply_heal(session, char, opts.self_heal))["healed"]
    add_history(session, char_id, "spell_healing", f"{spell.name}: cura {breakdown}")
    return RollHealingResult(
        rolls=main_rolls, total=total, breakdown=breakdown, casting_level=level, main_kind=f"d{sides}" if count else None,
        main_rolls=main_rolls, modifier=modifier, bonus=applied.flat + opts.bonus, maximized=maximized, healed=healed,
        healed_allies=healed_allies, self_healed=self_healed, option_result=option_result(opts, option_rolls, option_total))


@router.post("/{char_id}/last-damage/options",
             response_model=RollDamageResult | WeaponAttackResult | CompanionAttackResult)
async def last_damage_options(
    char_id: int,
    body: LastDamageBody,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> RollDamageResult | WeaponAttackResult | CompanionAttackResult:
    """Privilegi usati dopo aver visto i dadi di danno (incantesimo, arma o compagno). Il tiro è quello salvato dal server."""
    char = await get_owned_full(char_id, user_id, session)
    last = get_turn(char).get("last_damage")
    kind = (last or {}).get("kind", "spell")
    spell = next((s for s in char.spells if last and kind == "spell" and s.id == last["spell_id"]), None)
    if not last or (kind == "spell" and spell is None):
        raise HTTPException(status_code=409, detail={"code": "no_last_damage"})
    if used := set(body.options) & set(last.get("after_used", [])):  # Potenziato si somma a un'altra opzione, non a sé stesso
        raise HTTPException(status_code=409, detail={"code": "option_unavailable", "key": sorted(used)[0]})
    opts = use_options(session, char, "spell_damage" if kind == "spell" else "weapon_damage", body, phase="after_damage",
                       spell=spell, damage_type=canonical_damage_type(last["result"].get("damage_type")) if spell else None)

    dice = [list(d) for d in last["dice"]]
    picked = list(dict.fromkeys(body.reroll))
    valid = (len(opts.keys) == 1 and 1 <= len(picked) <= opts.reroll_limit
             and all(0 <= i < len(dice) and (not opts.keep_rolled or dice[i][1] == dice[i][0]) for i in picked))
    if not valid:  # get_db annulla ciò che le opzioni hanno pagato
        raise HTTPException(status_code=409, detail={"code": "bad_reroll"})

    rolled = [(dice[i][0], random.randint(1, dice[i][0])) for i in picked]
    record_dice(char, [(f"d{sides}", v) for sides, v in rolled])
    added, flat = list(last["added"]), last["flat"]
    if opts.keep_rolled:
        added += [v for _, v in rolled]
        flat += sum(v for _, v in rolled)
    else:
        for i, (_, v) in zip(picked, rolled):
            dice[i][1] = v

    values = [v for _, v in dice]
    total = max(0, last_damage_total(values, {**last, "flat": flat}))  # come il tiro: mai sotto 0
    base = last.get("base", len(values))
    old = last["result"]
    previous = OptionResult(**old["option_result"]) if old.get("option_result") else None
    block = option_result(opts, [], 0, previous=previous)
    if block is not None:  # i dadi delle opzioni sono quelli di adesso, non si accodano ai vecchi
        old_values, new_values = [v for _, v in last["dice"][base:]], values[base:]
        newly = added[len(last["added"]):]
        block = block.model_copy(update={
            "extra_rolls": [*new_values, *added],
            "extra_total": block.extra_total - sum(old_values) + sum(new_values) + sum(newly)})
    if kind == "weapon":
        # Danno base fisso ("1"): senza dadi di base il fisso già mostrato resta nell'elenco.
        result = WeaponAttackResult(**{**old, "damage_rolls": (values[:base] if base else old["damage_rolls"]) + added,
                                       "damage_total": total,
                                       "attack_id": None, "reroll_dice": dice, "option_result": block})
        label = result.weapon_name
    elif kind == "companion":
        result = CompanionAttackResult(**{**old, "damage_rolls": values[:base] + added, "damage_total": total,
                                          "reroll_dice": dice, "option_result": block})
        label = last.get("name") or "Compagno"
    else:
        main, extra = values[:last["main"]], values[last["main"]:base]
        shown = regroup(last.get("groups"), values[:base]) if last.get("groups") else old.get("parts") or []
        text = [f"{len(main)}{old['main_kind']}={main}"]
        text += [f"+{len(p['rolls'])}{p['kind']}={p['rolls']}" for p in shown[1:]]
        if flat:
            text.append(f"{flat:+d}")
        result = RollDamageResult(**{
            **old, "rolls": values[:base] + added, "main_rolls": main, "extra_rolls": extra, "total": total,
            "half_damage": total // 2, "breakdown": " ".join(text) + f" = {total}", "reroll_dice": dice,
            "option_result": block, "parts": shown,
        })
        label = f"{spell.name} = {total}"
    add_history(session, char_id, "spell_damage" if kind == "spell" else "attack_roll",
                 f"Dopo il danno ({option_names(char, opts.keys)}): {label}" + (f" = {total}" if kind != "spell" else ""))
    turn = get_turn(char)  # il pagamento ha riscritto il turno
    turn["last_damage"] = {**last, "dice": dice, "added": added, "flat": flat, "result": result.model_dump(mode="json"),
                           "after_used": [*last.get("after_used", []), *opts.keys]}
    char.turn_state = turn
    await session.commit()  # get_db chiude dopo la risposta: il client rilegge subito usi e turno
    return result

"""Lancio di un incantesimo con effetto sui bersagli: validazione prima della spesa, stati sui bersagli e orologio sul lanciatore.

Ogni stato ``spell:<chiave>`` sul bersaglio non ha durata propria: la scandisce lo stato ``spell_cast:<chiave>`` di chi lancia
(round, concentrazione, riposo). Alla chiusura dell'orologio ``settle_closed`` segna i bersagli da liberare e il flush
della richiesta (``api.services.effects``) toglie loro lo stato."""
from __future__ import annotations

from types import SimpleNamespace

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.spell import SpellEffectsRead
from api.services.session_allies import ally_target
from core.db.models import Character, GameSession, SessionParticipant, SessionStatus
from core.rules.catalog.spells import spell_effect
from core.rules.edition import character_edition
from core.rules.spell_effects import SPELL_CLOCK_PREFIX, SPELL_STATE_PREFIX, SpellEffect, SpellVariant
from core.rules.states import SPELL_GIVEN, SPELL_RELEASE, begin_state
from core.rules.types import StateSpec

_OUTSIDE_TEXT = {"it": "Fuori da una serata l'effetto non si applica da solo: lo applica il GM ai bersagli.",
                 "en": "Outside an evening the effect is not applied automatically: the GM applies it to the targets."}


def cast_level(char: Character, spell, slot_id: int | None, slot_level: int | None) -> int:
    """Il livello a cui si lancia: quello dello slot scelto (per id o per livello), altrimenti il livello dell'incantesimo."""
    if slot_id is not None:
        slot_level = next((s.level for s in char.spell_slots if s.id == slot_id), slot_level)
    return slot_level if slot_level and slot_level >= spell.level else spell.level


def _invalid(code: str, http: int = status.HTTP_422_UNPROCESSABLE_ENTITY) -> HTTPException:
    return HTTPException(http, detail={"code": code})


async def _seated(session: AsyncSession, char: Character) -> bool:
    row = await session.execute(
        select(SessionParticipant.id).join(GameSession, GameSession.id == SessionParticipant.session_id)
        .where(SessionParticipant.character_id == char.id, GameSession.status == SessionStatus.ACTIVE).limit(1))
    return row.first() is not None


def _check_choices(variant: SpellVariant, edition: str, choices: dict[str, str] | None) -> dict[str, str]:
    chosen = dict(choices or {})
    wanted = {c.key: c.options(edition) for c in variant.choices}
    if set(chosen) != set(wanted) or any(chosen[k] not in opts for k, opts in wanted.items()):
        raise _invalid("invalid_choice")
    return chosen


async def _resolve(session: AsyncSession, caster: Character, spell, slot_level: int,
                   targets: list[int] | None, choices: dict[str, str] | None):
    """``(effetto, variante, bersagli, scelte, fuori_serata)`` o ``None`` se l'incantesimo non è nel catalogo.
    Tutti i rifiuti (422 ``invalid_target`` / ``invalid_choice``, 409 ``target_dead``) escono da qui, prima di spendere."""
    edition = character_edition(caster)
    found = spell_effect(edition, spell.srd_index, spell.name)
    if found is None:
        return None
    effect, variant = found
    chosen = _check_choices(variant, edition, choices)
    if effect.target.kind == "self" or targets is None:
        return effect, variant, [caster], chosen, False
    if len(targets) != len(set(targets)) or len(targets) > effect.target.count(slot_level):
        raise _invalid("invalid_target")
    others = [t for t in targets if t != caster.id]
    outside = bool(others) and not await _seated(session, caster)
    chars = [caster] if caster.id in targets else []
    if not outside:
        for tid in others:
            ally = await ally_target(session, caster, tid)
            if ally.is_dead:
                raise _invalid("target_dead", status.HTTP_409_CONFLICT)
            chars.append(ally)
    return effect, variant, chars, chosen, outside


async def validate_spell_targets(session: AsyncSession, caster: Character, spell, slot_level: int,
                                 targets: list[int] | None, choices: dict[str, str] | None
                                 ) -> tuple[SpellEffect, SpellVariant, list[Character]] | None:
    """Da chiamare prima della spesa del lancio. ``None``: l'incantesimo non ha un effetto nel catalogo."""
    resolved = await _resolve(session, caster, spell, slot_level, targets, choices)
    return resolved and resolved[:3]


def _drop_state(target: Character, key: str, caster_id: int) -> None:
    states = target.active_states or []
    kept = [s for s in states if not (s.get("key") == key and (s.get("data") or {}).get("caster_id") == caster_id)]
    if len(kept) != len(states):
        target.active_states = kept


async def apply_spell_effects(session: AsyncSession, caster: Character, spell, slot_level: int,
                              targets: list[int] | None, choices: dict[str, str] | None) -> SpellEffectsRead | None:
    """Dopo la spesa: uno stato per bersaglio e l'orologio su chi lancia. Fuori serata (o per un effetto solo descrittivo)
    nessuno stato e un testo per il GM."""
    resolved = await _resolve(session, caster, spell, slot_level, targets, choices)
    if resolved is None:
        return None
    effect, variant, chars, chosen, outside = resolved
    data = {"spell_key": effect.key, "slot_level": slot_level, "choices": chosen, "caster_id": caster.id,
            "caster_name": caster.name, "edition": character_edition(caster),
            "duration": {"rounds": variant.rounds, "concentration": variant.concentration, "until_rest": variant.until_rest}}
    if not (variant.modifiers(data) or variant.options) or (outside and not chars):
        return SpellEffectsRead(applied=[], text=variant.text or _OUTSIDE_TEXT)
    key, clock = f"{SPELL_STATE_PREFIX}{effect.key}", f"{SPELL_CLOCK_PREFIX}{effect.key}"
    settings = dict(caster.settings or {})
    given = dict(settings.get(SPELL_GIVEN) or {})
    for old in set(given.get(clock, [])) - {c.id for c in chars}:  # lanciato di nuovo su altri: i vecchi bersagli lo perdono
        previous = caster if old == caster.id else await session.get(Character, old)
        if previous is not None:
            _drop_state(previous, key, caster.id)
    applied = []
    for target in chars:
        begin_state(target, StateSpec(key, ends_on=("manual",), data=dict(data)), key, spell.name)
        if variant.on_apply:
            variant.on_apply(target, data)
        applied.append({"id": target.id, "name": target.name})
    ends = [*(["concentration_end"] if variant.concentration else []), *(["rest_long"] if variant.until_rest else [])]
    begin_state(caster, StateSpec(clock, rounds=variant.rounds, ends_on=tuple(ends) or ("manual",), data={"spell_key": effect.key, "state_data": data}),
                clock, spell.name)
    settings = dict(caster.settings or {})  # riletto: la chiusura del lancio precedente può averlo cambiato
    regranted = {(a["id"], key) for a in applied}
    pending = [e for e in settings.get(SPELL_RELEASE) or [] if (e["id"], e["key"]) not in regranted]  # chiuso e riaperto nella stessa richiesta
    settings[SPELL_GIVEN] = {**(settings.get(SPELL_GIVEN) or {}), clock: [a["id"] for a in applied]}
    if pending:
        settings[SPELL_RELEASE] = pending
    else:
        settings.pop(SPELL_RELEASE, None)
    caster.settings = settings
    return SpellEffectsRead(applied=applied, text=variant.text or (_OUTSIDE_TEXT if outside else None))


async def regrant_spells(session: AsyncSession, caster: Character, before_given: dict | None) -> None:
    """Un annullo ha riaperto l'orologio ``spell_cast:*`` che la chiusura aveva spento: i bersagli riavuti ritrovano lo stato
    (ricostruito dai dati dell'orologio) e ``SPELL_GIVEN`` torna. Un bersaglio cancellato o con lo stato di un altro lanciatore si salta."""
    settings = dict(caster.settings or {})
    given = dict(settings.get(SPELL_GIVEN) or {})
    for clock, ids in (before_given or {}).items():
        state = next((s for s in caster.active_states or [] if s.get("key") == clock), None)
        if clock in given or state is None or not (state.get("data") or {}).get("state_data"):
            continue
        key = SPELL_STATE_PREFIX + state["data"]["spell_key"]
        back = []
        for tid in ids:
            target = caster if tid == caster.id else await session.get(Character, tid)
            held = next((s for s in (target.active_states or []) if s.get("key") == key), None) if target is not None else None
            if target is None or (held and (held.get("data") or {}).get("caster_id") != caster.id):
                continue
            if held is None:
                begin_state(target, StateSpec(key, ends_on=("manual",), data=dict(state["data"]["state_data"])), key, state.get("name"))
            back.append(tid)
        given[clock] = back
    caster.settings = {**settings, SPELL_GIVEN: given} if given else settings


def item_spell(spell: dict) -> SimpleNamespace:
    """L'incantesimo concesso da un oggetto (un dict dei metadati) con la forma che il servizio si aspetta."""
    return SimpleNamespace(name=spell.get("name"), srd_index=spell.get("srd_index"), level=int(spell.get("level") or 1))

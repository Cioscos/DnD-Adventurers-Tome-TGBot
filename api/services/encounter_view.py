"""Viewer-redacted response builder for the combat tracker.

Shared by api/routers/encounters.py (mutation responses) and
api/routers/sessions.py (the `encounter` block in /live).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.schemas.condition_effects import ConditionEffectRead, PendingSaveRead
from api.schemas.encounter import CombatantLive, EncounterLive, PublicState, PublicStateOther
from api.services.condition_effects import effect_reads, pending_read
from api.services.homebrew.passive import get_passive_modifiers
from api.services.rules_states import GENERIC_STATE_NAME
from core.rules.catalog import active_features
from core.rules.spell_effects import SPELL_STATE_PREFIX
from core.rules.modifiers import INCAPACITATING
from core.rules.states import is_conscious
from core.game.item_bonuses import item_bonus_total
from core.game.stats import effective_ability_score
from core.db.models import Character, Combatant, ConditionEffect, Encounter, PendingSave
from core.utils.session_view import hp_bucket_from_ratio


async def pc_initiative_mod(db: AsyncSession, char: Character) -> int:
    """Il modificatore d'iniziativa della scheda in questo momento (DES effettiva, oggetti, homebrew)."""
    base = next((a.value for a in (char.ability_scores or []) if a.name == "dexterity"), 10)
    effective, _ = effective_ability_score("dexterity", base, [i for i in (char.items or []) if i.is_equipped])
    return (effective - 10) // 2 + item_bonus_total(char.items or [], "initiative") + await get_passive_modifiers(
        db, char, "character.initiative")


def public_states(char: Character, lang: str = "it", *, gm: bool = False) -> list[PublicState]:
    """Gli stati attivi che portano effetti su altri. Nome e testo vengono dal catalogo, nella lingua di chi guarda:
    mai da ``Ability.name``/``description``, che il giocatore può modificare e sono privati. Il GM (``gm``) vede anche
    gli stati dei privilegi che agiscono solo sul PG, come Arma Consacrata (M6)."""
    specs = {spec.key: spec for spec, _row in active_features(char)}
    out: list[PublicState] = []
    for state in char.active_states or []:
        if str(state.get("key", "")).startswith(SPELL_STATE_PREFIX):
            # U33: incantesimo su questo PG (Benedizione, Scudo, Ragnatela…): nome, durata e chi l'ha lanciato
            data = state.get("data") or {}
            out.append(PublicState(key=state["key"], name=state.get("name") or GENERIC_STATE_NAME,
                                   rounds_left=state.get("rounds_left"), source_name=data.get("caster_name"),
                                   concentration=bool((data.get("duration") or {}).get("concentration"))))
            continue
        others = [
            PublicStateOther(key=key, name=spec.name.get(lang) or spec.name["it"],
                             text=spec.summary.get(lang) or spec.summary["it"])
            for key in (state.get("data") or {}).get("others") or []
            if (spec := specs.get(key)) is not None and not (spec.needs_conscious and not is_conscious(char))
            # la condizione Incapacitato, non la sorpresa 2014 (p.189 e 291): Inafferrabile vale anche nel turno della sorpresa
            and not (spec.suspended_when_incapacitated and any((char.conditions or {}).get(c) for c in INCAPACITATING))
        ]
        owner = specs.get(state.get("feature_key"))
        if others:
            name = (owner.name.get(lang) or owner.name["it"]) if owner is not None else state.get("name") or GENERIC_STATE_NAME
            out.append(PublicState(key=state["key"], name=name,
                                   rounds_left=state.get("rounds_left"), others=others))
        elif gm and owner is not None and not (state.get("data") or {}).get("others"):  # un'aura sospesa resta nascosta
            out.append(PublicState(key=state["key"], name=owner.name.get(lang) or owner.name["it"],
                                   rounds_left=state.get("rounds_left")))
    return out


def combatant_payload(
    c: Combatant, *, mode: str, viewer_is_gm: bool,
    effects: list[ConditionEffectRead] = (), pending: list[PendingSaveRead] = (),
    states: list[PublicState] = (), initiative_mod: int | None = None,
) -> CombatantLive:
    show_hp = c.kind == "monster" and mode == "full"
    bucket = None
    if show_hp and not viewer_is_gm:
        bucket = "dead" if c.is_dead else hp_bucket_from_ratio(c.current_hp, c.max_hp)
    return CombatantLive(
        id=c.id,
        kind=c.kind,
        character_id=c.character_id,
        owner_user_id=c.owner_user_id,
        name=c.name,
        initiative=c.initiative,
        initiative_die=c.initiative_die,
        initiative_mod=c.initiative_mod if initiative_mod is None else initiative_mod,
        sort_order=c.sort_order,
        is_dead=c.is_dead,
        surprised=c.surprised,
        conditions=c.conditions or {},
        current_hp=c.current_hp if (show_hp and viewer_is_gm) else None,
        max_hp=c.max_hp if (show_hp and viewer_is_gm) else None,
        ac=c.ac if (show_hp and viewer_is_gm) else None,
        hp_bucket=bucket,
        condition_effects=list(effects),
        pending_saves=list(pending) if viewer_is_gm else [],
        active_states=list(states),
    )


async def build_encounter_block(
    db: AsyncSession, enc: Encounter, *, viewer_is_gm: bool, lang: str = "it",
) -> EncounterLive:
    combs = list(enc.combatants)
    # Monster effects live on the combatant; PC effects are on the sheet (live_characters).
    mon_ids = [c.id for c in combs if c.kind == "monster"]
    all_rows = list((await db.execute(select(ConditionEffect).where(
        ConditionEffect.combatant_id.in_(mon_ids)).order_by(ConditionEffect.id))).scalars())
    rows = [r for r in all_rows if not r.pending]  # i pending non sono ancora sul mostro
    effects: dict[int, list[ConditionEffectRead]] = {}
    for row, read in zip(rows, await effect_reads(db, rows)):
        effects.setdefault(row.combatant_id, []).append(read)
    pending: dict[int, list[PendingSaveRead]] = {}
    slugs = {r.id: r.slug for r in all_rows}
    for p in (await db.execute(select(PendingSave).where(
            PendingSave.combatant_id.in_(mon_ids), PendingSave.character_id.is_(None),
            PendingSave.status == "pending").order_by(PendingSave.id))).scalars():
        pending.setdefault(p.combatant_id, []).append(pending_read(p, slugs.get(p.effect_id, "")))
    pc_ids = [c.character_id for c in combs if c.kind == "pc" and c.character_id]
    states: dict[int, list[PublicState]] = {}
    if pc_ids:
        for ch in (await db.execute(select(Character).options(selectinload(Character.classes))
                                    .where(Character.id.in_(pc_ids)))).scalars():
            if ch.active_states:
                states[ch.id] = public_states(ch, lang, gm=viewer_is_gm)
    # Chi non ha ancora tirato vede il modificatore che il tiro userà, non quello di quando l'incontro è stato aperto.
    mods: dict[int, int] = {}
    if waiting := [c.character_id for c in combs if c.kind == "pc" and c.character_id and c.initiative is None]:
        for ch in (await db.execute(select(Character).options(
                selectinload(Character.ability_scores), selectinload(Character.items)).where(Character.id.in_(waiting)))).scalars():
            mods[ch.id] = await pc_initiative_mod(db, ch)
    if enc.status == "setup":
        combs.sort(key=lambda c: (c.created_at, c.id))
    else:
        combs.sort(key=lambda c: (c.sort_order is None, c.sort_order or 0, c.id))
    return EncounterLive(
        id=enc.id,
        mode=enc.mode,
        status=enc.status,
        round=enc.round,
        active_combatant_id=enc.active_combatant_id,
        created_at=enc.created_at,
        started_at=enc.started_at,
        ended_at=enc.ended_at,
        combatants=[
            combatant_payload(c, mode=enc.mode, viewer_is_gm=viewer_is_gm,
                              effects=effects.get(c.id, []), pending=pending.get(c.id, []),
                              states=states.get(c.character_id, []) if c.kind == "pc" else [],
                              initiative_mod=mods.get(c.character_id) if c.initiative is None else None)
            for c in combs
        ],
    )

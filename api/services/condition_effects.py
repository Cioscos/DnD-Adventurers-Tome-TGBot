"""Condition effects: expiry / repeated-save / source metadata for an active condition.

The ``conditions`` map stays the source of truth for "is it on"; an effect exists only
while the condition is on. Exactly one of character_id / combatant_id is set (no DB
constraint: guaranteed here via ``Target``).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Iterable, Literal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.data.labels import condition_label
from core.rules.edition import character_edition
from core.rules.states import RETURNED_FROM, SUSPENDED_EFFECTS, SUSPENDED_KEY, SUSPENDED_ON, has_state, item_spell_held, restore_exhaustion
from api.services.rules_turn import get_turn, set_damaged, set_start_heal, set_surprised
from api.schemas.condition_effects import ConditionEffectRead, PendingSaveRead
from core.db.models import (
    Character, Combatant, Companion, ConditionEffect, Encounter, PendingSave,
)

Target = tuple[Literal["character", "combatant"], int]


@dataclass
class ExpirySpec:
    anchor: Literal["owner", "source"]
    edge: Literal["start", "end"]
    count: int


@dataclass
class SaveSpec:
    ability: str
    dc: int
    edge: Literal["start", "end"]


@dataclass
class UndoLog:
    """What one forward turn advance changed, stored on ``Encounter.last_advance_undo``.

    ``decremented`` holds only effects that survived; expired ones are in ``expired``
    (snapshot taken before the decrement, so recreating it restores the prior count).
    """
    from_combatant_id: int | None = None
    to_combatant_id: int | None = None
    round_before: int | None = None
    round_after: int | None = None
    decremented: list[dict] = field(default_factory=list)  # {effect_id, prev_count}
    # {target, slug, prev_value, effect_snapshot, pending_saves: [snapshot]}
    expired: list[dict] = field(default_factory=list)
    created_saves: list[int] = field(default_factory=list)
    skip_cleared: list[int] = field(default_factory=list)  # effect ids whose save_skip_once was consumed
    # {char_id, prev_rounds, prev_spell_id, prev_item_spell, released_effects: [snapshot]}
    concentration: dict | None = None
    # {char_id: {active_states, damaged}} dei PG toccati, snapshot prima dell'avanzamento
    char_states: dict[str, dict] = field(default_factory=dict)
    # {char_id: lista} dei PG a cui l'avanzamento ha svuotato gli effetti «una volta per turno»
    once_per_turn: dict[str, list[str]] = field(default_factory=dict)
    # Sorpresa: combattenti a cui il turno finito l'ha tolta; PG 2014 a cui il turno iniziato l'ha imposta
    surprise_ended: list[int] = field(default_factory=list)
    surprise_started: list[int] = field(default_factory=list)  # non più scritto: il PG è segnato quando il GM lo segna

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict) -> "UndoLog":
        return cls(**data)


def effect_snapshot(effect: ConditionEffect | PendingSave) -> dict:
    return {c.name: getattr(effect, c.name) for c in type(effect).__table__.columns}


async def _restore_row(db: AsyncSession, model, snap: dict):
    """Recreate a deleted row, keeping its id unless something reused it meanwhile."""
    data = dict(snap)
    if "id" in data and await db.get(model, data["id"]) is not None:
        data.pop("id")
    for column in model.__table__.columns:  # una fonte cancellata nel frattempo (PG tolto dall'incontro) non blocca il ripristino
        for fk in column.foreign_keys:
            if column.nullable and data.get(column.name) is not None and (
                    await db.execute(select(fk.column).where(fk.column == data[column.name]))).first() is None:
                data[column.name] = None
    row = model(**data)
    db.add(row)
    await db.flush()
    return row


async def undo_last_advance(db: AsyncSession, enc: Encounter) -> None:
    """Revert the last forward advance (spec §2 "Turno indietro"), one step only and
    only if the pointer is still where that advance left it. Each entry is reverted
    only if its state is still the one the advance left; conflicting ones are skipped."""
    data, enc.last_advance_undo = enc.last_advance_undo, None
    if not data:
        return
    log = UndoLog.from_json(data)
    if enc.active_combatant_id != log.to_combatant_id or enc.round != log.round_after:
        return
    created = set(log.created_saves)
    for sid in log.created_saves:
        ps = await db.get(PendingSave, sid)
        if ps is not None and ps.status == "pending":
            await db.delete(ps)
    for d in log.decremented:
        eff = await db.get(ConditionEffect, d["effect_id"])
        if eff is not None and eff.expiry_count == d["prev_count"] - 1:
            eff.expiry_count = d["prev_count"]
    new_ids: dict[int, int] = {}
    resumed: int | None = None  # chi riprende la concentrazione finita con l'avanzamento
    c = log.concentration
    char = await db.get(Character, c["char_id"]) if c else None
    if char is not None:
        prev = c["prev_rounds"]
        s = dict(char.settings or {})
        left = prev - 1 if isinstance(prev, int) and not isinstance(prev, bool) and prev > 1 else None
        ended = left is None and isinstance(prev, int) and not isinstance(prev, bool)
        still = (char.concentrating_spell_id is None and not s.get("concentration_item_spell")
                 and "concentration_rounds_left" not in s) if ended else (
            char.concentrating_spell_id == c["prev_spell_id"]
            and s.get("concentration_item_spell") == c["prev_item_spell"]
            and s.get("concentration_rounds_left") == left)
        if still:
            resumed = char.id if ended else None
            char.concentrating_spell_id = c["prev_spell_id"]
            s["concentration_rounds_left"] = prev
            if c["prev_item_spell"] is not None:
                s["concentration_item_spell"] = c["prev_item_spell"]
            if c.get("prev_level") is not None:
                s["concentration_level"] = c["prev_level"]
            char.settings = s
            await _restore_released(db, c.get("released_effects", []), created, new_ids)
    await _restore_released(db, log.expired, created, new_ids)  # dopo la concentrazione: vi guarda
    for cid, snap in log.char_states.items():
        pc = await db.get(Character, int(cid))
        if pc is not None:
            snap_forms = {(s.get("data") or {}).get("companion_id") for s in snap["active_states"] if s.get("key") == "wild_shape"}
            cur_wild = [s for s in pc.active_states or [] if s.get("key") == "wild_shape"
                        and (s.get("data") or {}).get("companion_id") not in snap_forms]  # la stessa forma torna dallo snapshot, round compresi
            now_wild = bool(cur_wild)
            holds = has_state(pc, SUSPENDED_KEY) or resumed == pc.id  # chi ha chiuso la sospensione dopo l'avanzamento non la riprende
            suspending = [s for s in pc.active_states or [] if s.get("key") == SUSPENDED_KEY]
            pc.active_states = list(snap["active_states"])
            if not holds:
                pc.active_states = [s for s in pc.active_states if s.get("key") != SUSPENDED_KEY]
            elif not has_state(pc, SUSPENDED_KEY):  # sospensione cominciata dopo l'avanzamento
                pc.active_states = [*pc.active_states, *suspending]
            if now_wild:  # una nuova forma è partita dopo l'avanzamento: resta la sua, non quella dello snapshot
                pc.active_states = [x for x in pc.active_states if x.get("key") != "wild_shape"] + cur_wild
            set_damaged(pc, snap["damaged"])
            from api.services.condition_removal import resuspend  # import locale: il servizio importa questo modulo
            from api.services.effects import _still_concentrating  # circular import
            await resuspend(db, pc)
            for slug, x in (snap.get("suspended") or {}).items():  # tornata dopo l'avanzamento: le resta la durata di prima
                eff = (await db.execute(select(ConditionEffect).where(
                    _target_filter(("character", pc.id)), ConditionEffect.slug == slug,
                    ConditionEffect.pending.is_(False)))).scalars().first() if (pc.conditions or {}).get(slug) else None
                if eff is not None and eff.expiry_count == x["effect"]["expiry_count"] - 1:
                    eff.expiry_count += 1
            held = {}
            for slug, x in (snap.get("suspended") or {}).items():
                if (pc.conditions or {}).get(slug):
                    continue
                if await _rehold(db, pc.id, slug, x["by"]):
                    held[slug] = x
                elif not x["effect"].get("ends_with_concentration") or await db.run_sync(_still_concentrating, x["effect"]):
                    # chi la sospendeva ha smesso dopo l'avanzamento: torna attiva
                    pc.conditions = {**(pc.conditions or {}), slug: True}
                    await _restore_row(db, ConditionEffect, x["effect"])
            if held:
                st = pc.settings or {}
                pc.settings = {**st, SUSPENDED_EFFECTS: {**(st.get(SUSPENDED_EFFECTS) or {}), **{c: x["effect"] for c, x in held.items()}},
                               SUSPENDED_ON: {**(st.get(SUSPENDED_ON) or {}), **{c: x["by"] for c, x in held.items()}}}
            form = await db.get(Companion, snap["wild_closed"]) if snap.get("wild_closed") else None  # la riga che ha chiuso proprio l'avanzamento
            if form is not None and form.character_id == pc.id and form.kind == "wild_shape" and not form.is_active and not now_wild:
                from api.services.wild_shape import deactivate_other_forms  # import locale: il servizio importa gli stati
                await deactivate_other_forms(db, pc.id, form.id)
                form.is_active = True
            healed = snap.get("healed")  # la cura d'inizio turno: si toglie solo se i PF sono ancora quelli che ha dato
            if healed and pc.current_hit_points == healed["after"]:
                pc.current_hit_points = healed["before"]
                set_start_heal(pc, [])
                if "death_saves" in healed:
                    pc.death_saves = dict(healed["death_saves"])
                    if healed["unconscious"] and not (pc.conditions or {}).get("unconscious"):
                        pc.conditions = {**(pc.conditions or {}), "unconscious": True}
            temp = snap.get("temp")  # i PF temporanei d'inizio turno: si tolgono solo se sono ancora quelli dati
            if temp and (pc.temp_hp or 0) == temp["after"]:
                pc.temp_hp = temp["before"]
            if snap.get("inspired"):
                pc.heroic_inspiration = False
            if "exhaustion" in snap:  # la spossatezza addebitata dagli stati chiusi dall'avanzamento
                restore_exhaustion(pc, snap["exhaustion"])
                if not snap["is_dead"] and pc.is_dead and snap["exhaustion"] < 6:
                    pc.is_dead = False
            from api.services.spell_effects import regrant_spells  # import locale: il servizio importa gli alleati di sessione
            await regrant_spells(db, pc, snap.get("spell_given"))  # l'orologio di un incantesimo riaperto ridà lo stato ai bersagli
    for char_id, used in log.once_per_turn.items():
        pc = await db.get(Character, int(char_id))
        if pc is not None:
            pc.turn_state = {**get_turn(pc), "once_per_turn": used}
    for comb_id in log.surprise_ended:
        comb = await db.get(Combatant, comb_id)
        if comb is not None:
            comb.surprised = True
            pc = await db.get(Character, comb.character_id) if comb.character_id else None
            if pc is not None and character_edition(pc) == "2014":
                set_surprised(pc)
    for eid in log.skip_cleared:
        eff = await db.get(ConditionEffect, new_ids.get(eid, eid))
        if eff is not None:
            eff.save_skip_once = True
    await db.flush()


async def _rehold(db: AsyncSession, receiver_id: int, slug: str, caster_id: int) -> bool:
    """La condizione scaduta mentre era sospesa torna nell'elenco di chi la sospende. False se non la sospende più."""
    caster = await db.get(Character, caster_id)
    if caster is None or not has_state(caster, SUSPENDED_KEY):
        return False
    held = list((caster.settings or {}).get(SUSPENDED_KEY) or [])
    if not any(e["id"] == receiver_id and slug in e["conditions"] for e in held):
        caster.settings = {**(caster.settings or {}), SUSPENDED_KEY: [*held, {"id": receiver_id, "conditions": [slug]}]}
    return True


async def _restore_released(db: AsyncSession, entries: list[dict], created: set[int],
                            new_ids: dict[int, int]) -> None:
    """Recreate effects an advance switched off, skipping targets changed meanwhile."""
    from api.services.effects import _still_concentrating  # circular import
    for x in entries:
        kind, tid = x["target"]
        slug = x["slug"]
        owner = await db.get(Character if kind == "character" else Combatant, tid)
        snap = x["effect_snapshot"]
        if owner is not None and kind == "combatant" and owner.created_at > snap["created_at"]:
            continue  # l'id è di un combattente aggiunto dopo: il bersaglio non c'è più
        if snap["encounter_id"] is not None and (snap["expiry_count"] is not None or snap["save_dc"] is not None):
            enc = await db.get(Encounter, snap["encounter_id"])
            if enc is None or enc.status == "ended":  # L5: finito lo scontro, durate e TS cadono
                continue
        if owner is None or (owner.conditions or {}).get(slug) or (await db.execute(
                select(ConditionEffect.id).where(_target_filter((kind, tid)), ConditionEffect.slug == slug,
                                                 ConditionEffect.pending.is_(False)))).first():
            continue
        if snap["ends_with_concentration"] and not await db.run_sync(_still_concentrating, snap):
            continue  # la concentrazione che la teneva è finita nel frattempo
        owner.conditions = {**(owner.conditions or {}), slug: x["prev_value"]}
        if x.get("returned_from") is not None:
            owner.settings = {**(owner.settings or {}), RETURNED_FROM: {**((owner.settings or {}).get(RETURNED_FROM) or {}), slug: x["returned_from"]}}
        eff = await _restore_row(db, ConditionEffect, x["effect_snapshot"])
        new_ids[x["effect_snapshot"]["id"]] = eff.id
        for ps in x.get("pending_saves", []):
            if ps["id"] not in created:  # created by this advance: stays undone
                await _restore_row(db, PendingSave, {**ps, "effect_id": eff.id})


async def restore_released(db: AsyncSession, entries: list[dict]) -> None:
    """Ricrea gli effetti fatti cadere con ``release_concentration_effects(..., undo_list)``."""
    await _restore_released(db, entries, set(), {})


async def expire_effect(db: AsyncSession, eff: ConditionEffect, history: str | None,
                        undo_list: list[dict] | None) -> str:
    """Switch the condition off on its target (dropping the effect row); returns its label.
    ``history`` (formatted with ``{label}``) is logged on a PC target."""
    from api.services.effects import apply_conditions  # circular import
    from api.services.history import add_history
    label = condition_label(eff.slug)
    if eff.pending:  # TS ancora in attesa: la condizione non c'è mai stata (nulla di preesistente si tocca) e un TS tardivo non deve applicarla
        for ps in (await db.execute(select(PendingSave).where(PendingSave.effect_id == eff.id))).scalars():
            await db.delete(ps)
        await db.delete(eff)
        await db.flush()
        return label
    snapshot, returned = effect_snapshot(eff), None
    saves = [effect_snapshot(ps) for ps in (await db.execute(select(PendingSave).where(
        PendingSave.effect_id == eff.id).order_by(PendingSave.id))).scalars()]
    if eff.character_id is not None:
        target = ("character", eff.character_id)
        char = await db.get(Character, eff.character_id)
        prev = (char.conditions or {}).get(eff.slug)
        returned = ((char.settings or {}).get(RETURNED_FROM) or {}).get(eff.slug)
        if history:
            add_history(db, char.id, "condition_change", history.format(label=label))
        await apply_conditions(db, char, {eff.slug: False})
    else:
        target = ("combatant", eff.combatant_id)
        comb = await db.get(Combatant, eff.combatant_id)
        conds = dict(comb.conditions or {})
        prev = conds.pop(eff.slug, None)
        comb.conditions = conds
        await clear_effects_for(db, target, [eff.slug])
    if undo_list is not None:
        undo_list.append({"target": list(target), "returned_from": returned, "slug": eff.slug, "prev_value": prev,
                          "effect_snapshot": snapshot, "pending_saves": saves})
    return label


RELEASED_LOG = "released_effects"  # ``session.info``: effetti caduti con una concentrazione durante un'operazione PF


def item_concentration(char: Character) -> str | None:
    """Chiave dell'incantesimo di un oggetto o privilegio su cui ``char`` si concentra (non ha una riga fra i suoi incantesimi)."""
    held = item_spell_held(char)
    return f"{held.get('item_id') or held.get('feature_key') or ''}:{held.get('name')}"[:200] if held else None


async def release_concentration_effects(db: AsyncSession, char: Character,
                                        undo_list: list[dict] | None = None) -> list[str]:
    """Spec §5: end the effects tied to ``char``'s concentration on a spell other than the
    current one (all of them if it no longer concentrates). Returns their labels."""
    q = select(ConditionEffect).where(ConditionEffect.ends_with_concentration.is_(True),
                                      ConditionEffect.source_character_id == char.id)
    if char.__dict__.pop("concentration_restarted", False):
        pass  # un nuovo lancio chiude il precedente, anche dello stesso incantesimo (2014 pag. 203)
    elif char.concentrating_spell_id is not None:
        q = q.where(or_(ConditionEffect.source_spell_id.is_(None),
                        ConditionEffect.source_spell_id != char.concentrating_spell_id))
    elif (held := item_concentration(char)) is not None:
        q = q.where(or_(ConditionEffect.source_item_spell.is_(None), ConditionEffect.source_item_spell != held))
    history = f"Terminata (fine concentrazione di {char.name}): {{label}}"
    dropped: list[dict] = []
    labels = [await expire_effect(db, eff, history, dropped)
              for eff in (await db.execute(q.order_by(ConditionEffect.id))).scalars().all()]
    for keep in (undo_list, db.info.get(RELEASED_LOG)):  # l'operazione PF in corso li tiene per il suo annullo
        if keep is not None:
            keep.extend(dropped)
    return labels


def _target_filter(target: Target):
    kind, tid = target
    col = ConditionEffect.character_id if kind == "character" else ConditionEffect.combatant_id
    return col == tid


async def _target_combatant_id(db: AsyncSession, target: Target, encounter: Encounter) -> int | None:
    kind, tid = target
    if kind == "combatant":
        return tid
    return (await db.execute(select(Combatant.id).where(
        Combatant.encounter_id == encounter.id, Combatant.character_id == tid,
    ))).scalar_one_or_none()


async def clear_effects_for(db: AsyncSession, target: Target, slugs: Iterable[str]) -> None:
    slugs = list(slugs)
    if not slugs:
        return
    # Un effetto ``pending`` (TS in attesa di un privilegio) non è una condizione attiva: non si tocca.
    rows = (await db.execute(select(ConditionEffect).where(
        _target_filter(target), ConditionEffect.slug.in_(slugs), ConditionEffect.pending.is_(False)))).scalars().all()
    for row in rows:
        # Explicit delete of pendings: SQLite FK cascade is not guaranteed to be enabled.
        for ps in (await db.execute(select(PendingSave).where(
                PendingSave.effect_id == row.id))).scalars():
            await db.delete(ps)
        await db.delete(row)
    await db.flush()


async def upsert_effect(
    db: AsyncSession, target: Target, slug: str, *,
    expiry: ExpirySpec | None = None, save: SaveSpec | None = None,
    source_combatant_id: int | None = None, source_character_id: int | None = None,
    source_spell_id: int | None = None, source_item_spell: str | None = None, ends_with_concentration: bool = False,
    applied_by_gm: bool = False, encounter: Encounter | None = None, source_note: str | None = None,
) -> ConditionEffect:
    """Replace the effect for (target, slug). Applies the "next turn" correction when
    ``encounter`` is active: an end-edge expiry anchored on the active combatant lasts one
    turn more, and an end-edge save on the active target skips its first edge."""
    await clear_effects_for(db, target, [slug])
    count = expiry.count if expiry else None
    skip_once = False
    if encounter is not None and encounter.status == "active" and encounter.active_combatant_id:
        active = encounter.active_combatant_id
        if expiry and expiry.edge == "end":
            anchor_id = (source_combatant_id if expiry.anchor == "source"
                         else await _target_combatant_id(db, target, encounter))
            if anchor_id == active:
                count += 1
        if save and save.edge == "end":
            skip_once = await _target_combatant_id(db, target, encounter) == active
    kind, tid = target
    effect = ConditionEffect(
        character_id=tid if kind == "character" else None,
        combatant_id=tid if kind == "combatant" else None,
        slug=slug,
        expiry_anchor=expiry.anchor if expiry else None,
        expiry_edge=expiry.edge if expiry else None,
        expiry_count=count,
        save_ability=save.ability if save else None,
        save_dc=save.dc if save else None,
        save_edge=save.edge if save else None,
        save_skip_once=skip_once,
        source_combatant_id=source_combatant_id,
        source_character_id=source_character_id,
        source_spell_id=source_spell_id,
        source_item_spell=source_item_spell,
        ends_with_concentration=ends_with_concentration,
        applied_by_gm=applied_by_gm,
        source_note=source_note,
        encounter_id=encounter.id if encounter is not None else None,
        created_at=datetime.utcnow().isoformat(timespec="seconds"),
    )
    db.add(effect)
    await db.flush()
    return effect


async def effects_for_character(db: AsyncSession, char_id: int) -> list[ConditionEffect]:
    """Gli effetti attivi: quelli ancora in attesa del TS (``pending``) non sono sulla scheda."""
    return list((await db.execute(select(ConditionEffect).where(
        ConditionEffect.character_id == char_id, ConditionEffect.pending.is_(False),
    ).order_by(ConditionEffect.id))).scalars())


async def effect_reads(db: AsyncSession, effects: list[ConditionEffect]) -> list[ConditionEffectRead]:
    """Read models with source names resolved (PC and monster targets alike)."""
    comb_ids = {e.source_combatant_id for e in effects if e.source_combatant_id}
    char_ids = {e.source_character_id for e in effects if e.source_character_id}
    comb_names = dict((await db.execute(select(Combatant.id, Combatant.name).where(
        Combatant.id.in_(comb_ids)))).all()) if comb_ids else {}
    char_names = dict((await db.execute(select(Character.id, Character.name).where(
        Character.id.in_(char_ids)))).all()) if char_ids else {}
    return [ConditionEffectRead(
        slug=e.slug, expiry_anchor=e.expiry_anchor, expiry_edge=e.expiry_edge,
        expiry_count=e.expiry_count, save_ability=e.save_ability, save_dc=e.save_dc,
        save_edge=e.save_edge,
        source_name=comb_names.get(e.source_combatant_id) or char_names.get(e.source_character_id),
        ends_with_concentration=e.ends_with_concentration, applied_by_gm=e.applied_by_gm,
        source_note=e.source_note,
    ) for e in effects]


def pending_read(p: PendingSave, slug: str) -> PendingSaveRead:
    return PendingSaveRead(id=p.id, slug=slug, ability=p.ability, dc=p.dc, status=p.status,
                           created_at=p.created_at, last_roll=p.last_roll)


async def characters_effect_payload(
    db: AsyncSession, char_ids: list[int],
) -> dict[int, tuple[list[ConditionEffectRead], list[PendingSaveRead]]]:
    """Effetti attivi e TS aperti di più schede, con un numero di query che non dipende da quante sono.

    TS aperti: tutti i pending, più il TS fallito di ogni effetto se nessun TS più recente l'ha superato."""
    rows = list((await db.execute(select(ConditionEffect).where(
        ConditionEffect.character_id.in_(char_ids)).order_by(ConditionEffect.id))).scalars())
    on = dict((await db.execute(select(Character.id, Character.conditions).where(Character.id.in_(char_ids)))).all())
    # i pending non sono sulla scheda, né la condizione già spenta che aspetta l'archivio del suo TS...
    active = [e for e in rows if e.pending is False and (on.get(e.character_id) or {}).get(e.slug)]
    slugs = {(e.character_id, e.id): e.slug for e in rows}  # ...ma i loro TS vanno mostrati
    newest = {(cid, eid): top for cid, eid, top in (await db.execute(
        select(PendingSave.character_id, PendingSave.effect_id, func.max(PendingSave.id))
        .where(PendingSave.character_id.in_(char_ids))
        .group_by(PendingSave.character_id, PendingSave.effect_id))).all()}
    saves = (await db.execute(select(PendingSave).where(
        PendingSave.character_id.in_(char_ids), PendingSave.dismissed.is_(False),
        PendingSave.status.in_(("pending", "failed"))).order_by(PendingSave.id))).scalars()
    out: dict[int, tuple[list[ConditionEffectRead], list[PendingSaveRead]]] = {c: ([], []) for c in char_ids}
    for eff, read in zip(active, await effect_reads(db, active)):
        out[eff.character_id][0].append(read)
    for p in saves:
        if p.status == "pending" or newest.get((p.character_id, p.effect_id)) == p.id:
            out[p.character_id][1].append(pending_read(p, slugs.get((p.character_id, p.effect_id), "")))
    return out


async def character_effect_payload(
    db: AsyncSession, char_id: int,
) -> tuple[list[ConditionEffectRead], list[PendingSaveRead]]:
    """Read models for CharacterFull (source names resolved)."""
    return (await characters_effect_payload(db, [char_id]))[char_id]

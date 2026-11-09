"""Effetti dei privilegi su un altro combattente dell'incontro (D1).

Il giocatore sceglie il combattente, il server applica condizione e durata con gli stessi meccanismi del GM
(``apply_condition_to_combatant``). Con un TS il bersaglio lo tira come qualunque TS in sospeso: un PG dalla propria
scheda (``SaveRollSheet``), un mostro lo segna il GM. La condizione resta applicata finché il TS non riesce, come per i
TS ripetuti: un TS superato la toglie con la sua durata.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import inspect as sa_inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.encounter import GmConditionApply
from api.services.condition_effects import ExpirySpec, SaveSpec, _target_combatant_id, clear_effects_for, upsert_effect
from api.services.effects import _add_history, apply_conditions
from core.data.labels import condition_label
from core.db.models import Character, Combatant, ConditionEffect, Encounter, PendingSave
from core.rules.states import add_target_immunity, immune_conditions, is_target_immune


async def pc_char(db: AsyncSession, comb: Combatant) -> Character:
    char = await db.get(Character, comb.character_id) if comb.character_id else None
    if char is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
    if "classes" in sa_inspect(char).unloaded:  # le immunità dei privilegi (Interdizione della Natura) vengono dalle classi
        await db.refresh(char, ["classes"])
    return char


async def pc_char_by_id(db: AsyncSession, char_id: int) -> Character:
    """Il personaggio con le classi caricate (servono alle immunità dei privilegi)."""
    char = await db.get(Character, char_id)
    if "classes" in sa_inspect(char).unloaded:
        await db.refresh(char, ["classes"])
    return char


async def set_condition(db: AsyncSession, comb: Combatant, slug: str, value: Any) -> None:
    """Write one slug on the target's map; a falsy value drops the slug's effect."""
    if comb.kind == "pc":
        await apply_conditions(db, await pc_char(db, comb), {slug: value})
        return
    comb.conditions = {**(comb.conditions or {}), slug: value}
    if not value:
        await clear_effects_for(db, ("combatant", comb.id), [slug])


async def apply_condition_to_combatant(
    db: AsyncSession, enc: Encounter, comb: Combatant, body: GmConditionApply, *, applied_by_gm: bool = True,
) -> None:
    """Applica ``body`` a ``comb``: solo mappa (``value``) oppure condizione ricca con durata, TS e fonte."""
    if body.value is not None:
        await set_condition(db, comb, body.slug, body.value)
        return
    src = None
    if body.source_combatant_id is not None:
        src = next((c for c in enc.combatants if c.id == body.source_combatant_id), None)
        if src is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail="source_combatant_id not in this encounter")
    src_char = await pc_char(db, src) if src is not None and src.kind == "pc" else None
    spell_id = None
    if body.ends_with_concentration:
        if src_char is None or src_char.concentrating_spell_id is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail={"code": "source_not_concentrating"})
        spell_id = src_char.concentrating_spell_id
    owner = await pc_char(db, comb) if comb.kind == "pc" else comb
    if comb.kind == "pc" and body.slug in immune_conditions(owner):
        return  # respinta per immunità: né condizione, né effetto, né TS di fine turno
    if not (owner.conditions or {}).get(body.slug):  # keep custom:* payloads on re-apply
        await set_condition(db, comb, body.slug, True)
    target = ("character", comb.character_id) if comb.kind == "pc" else ("combatant", comb.id)
    await upsert_effect(
        db, target, body.slug,
        expiry=ExpirySpec(**body.expiry.model_dump()) if body.expiry else None,
        save=SaveSpec(**body.save.model_dump()) if body.save else None,
        source_combatant_id=src.id if src else None,
        source_character_id=src_char.id if src_char else None,
        source_spell_id=spell_id,
        ends_with_concentration=body.ends_with_concentration,
        applied_by_gm=applied_by_gm, encounter=enc,
    )


def pending_target_effect(char: Character, effect_key: str) -> dict:
    """L'effetto che il server ha tenuto alla conferma dell'opzione; 409 se non c'è (o è già stato applicato)."""
    found = (char.turn_state or {}).get("target_effects", {}).get(effect_key)
    if found is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "no_target_effect"})
    return found


def _expiry(effect: dict) -> dict | None:
    if effect.get("ends_at"):
        return effect["ends_at"]
    return {"anchor": "owner", "edge": "end", "count": effect["rounds"]} if effect.get("rounds") else None


async def _delete_effect(db: AsyncSession, eff: ConditionEffect) -> None:
    """Elimina l'effetto e i suoi TS (la cascata di SQLite non è garantita)."""
    for ps in (await db.execute(select(PendingSave).where(PendingSave.effect_id == eff.id))).scalars():
        await db.delete(ps)
    await db.delete(eff)


async def drop_pending_effect(db: AsyncSession, eff: ConditionEffect) -> None:
    """TS superato: l'effetto non è mai esistito sul bersaglio, ciò che aveva già resta com'è. Se l'effetto lo prevede
    (``immune_on_success``), chi l'ha usato non può più colpire quel bersaglio fino al suo prossimo riposo lungo."""
    if eff.immunity_key and eff.source_character_id is not None:
        source = await db.get(Character, eff.source_character_id)
        if source is not None:
            add_target_immunity(source, eff.immunity_key,
                                f"character:{eff.character_id}" if eff.character_id is not None
                                else f"combatant:{eff.combatant_id}")
            # il TS superato toglie lo stato che autorizzava il seguito, se lo dichiara (Lettura del Pensiero: il lancio gratuito)
            source.active_states = [s for s in source.active_states or []
                                    if not (s.get("feature_key") == eff.immunity_key and (s.get("data") or {}).get("ends_on_passed_save"))]
    await _delete_effect(db, eff)
    await db.flush()


async def _activate_also(db: AsyncSession, eff: ConditionEffect, target: tuple[str, int]) -> None:
    """Le altre condizioni dello stesso effetto (``TargetEffect.also``) arrivano col TS fallito, con durata e fonte uguali."""
    for slug in filter(None, (eff.also_slugs or "").split(",")):
        if target[0] == "character":
            char = await pc_char_by_id(db, target[1])
            if slug in immune_conditions(char):
                continue
            if not (char.conditions or {}).get(slug):
                await apply_conditions(db, char, {slug: True})
        else:
            comb = await db.get(Combatant, target[1])
            if not (comb.conditions or {}).get(slug):
                comb.conditions = {**(comb.conditions or {}), slug: True}
        await clear_effects_for(db, target, [slug])
        db.add(ConditionEffect(
            character_id=eff.character_id, combatant_id=eff.combatant_id, slug=slug, expiry_anchor=eff.expiry_anchor,
            expiry_edge=eff.expiry_edge, expiry_count=eff.expiry_count, source_combatant_id=eff.source_combatant_id,
            source_character_id=eff.source_character_id, applied_by_gm=False, encounter_id=eff.encounter_id,
            created_at=eff.created_at))


async def activate_pending_effect(db: AsyncSession, eff: ConditionEffect) -> None:
    """TS fallito: la condizione va sulla scheda o sul mostro e la durata decorre da ora."""
    others = (await db.execute(select(ConditionEffect).where(
        ConditionEffect.character_id == eff.character_id, ConditionEffect.combatant_id == eff.combatant_id,
        ConditionEffect.slug == eff.slug, ConditionEffect.id != eff.id))).scalars().all()
    for other in others:  # un solo effetto per condizione, come in ``upsert_effect``
        await _delete_effect(db, other)
    if eff.character_id is not None:
        char = await pc_char_by_id(db, eff.character_id)
        if eff.slug in immune_conditions(char):  # immune: il TS fallito non porta nulla, l'effetto non resta
            await _delete_effect(db, eff)
            await db.flush()
            return
        if not (char.conditions or {}).get(eff.slug):
            await apply_conditions(db, char, {eff.slug: True})
        target = ("character", eff.character_id)
    else:
        comb = await db.get(Combatant, eff.combatant_id)
        if not (comb.conditions or {}).get(eff.slug):
            comb.conditions = {**(comb.conditions or {}), eff.slug: True}
        target = ("combatant", eff.combatant_id)
    eff.pending = False
    enc = await db.get(Encounter, eff.encounter_id) if eff.encounter_id else None
    if enc is not None and enc.status == "active" and enc.active_combatant_id and eff.expiry_edge == "end"             and eff.expiry_count is not None:
        anchor = eff.source_combatant_id if eff.expiry_anchor == "source" else await _target_combatant_id(db, target, enc)
        if anchor == enc.active_combatant_id:  # come ``upsert_effect``: dura un turno in più
            eff.expiry_count += 1
    await _activate_also(db, eff, target)
    await db.flush()


async def drop_pending_effects(db: AsyncSession, encounter_id: int) -> None:
    """A fine incontro i TS in attesa non servono più: la condizione non è mai esistita."""
    for eff in (await db.execute(select(ConditionEffect).where(
            ConditionEffect.encounter_id == encounter_id, ConditionEffect.pending.is_(True)))).scalars().all():
        await _delete_effect(db, eff)
    await db.flush()


async def apply_target_effect(
    db: AsyncSession, char: Character, enc: Encounter, mine: Combatant, target: Combatant, effect_key: str,
) -> tuple[bool, PendingSave | None]:
    """Applica l'effetto tenuto per ``effect_key``: (applicato, TS in sospeso). Lo consuma.

    Con un TS la condizione non c'è ancora: nasce un effetto ``pending`` e il TS ne decide la sorte."""
    effect = pending_target_effect(char, effect_key)
    if effect.get("immune_on_success") and is_target_immune(char, effect_key, target):
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "target_immune"})
    slug = effect.get("condition")
    with_save = bool(slug and effect.get("save_ability") and effect.get("on_failure_only", True))
    extending = bool(with_save and effect.get("extends") and (await db.execute(select(ConditionEffect.id).where(
        ConditionEffect.character_id == (target.character_id if target.kind == "pc" else None),
        ConditionEffect.combatant_id == (target.id if target.kind == "monster" else None),
        ConditionEffect.slug == slug, ConditionEffect.pending.is_(False),
        ConditionEffect.source_character_id == char.id))).first())
    if extending:
        with_save = False  # prolungamento: la condizione c'è già da parte nostra, la durata si rinnova senza un nuovo TS
    if with_save and (await db.execute(select(ConditionEffect.id).where(
            ConditionEffect.character_id == (target.character_id if target.kind == "pc" else None),
            ConditionEffect.combatant_id == (target.id if target.kind == "monster" else None),
            ConditionEffect.slug == slug, ConditionEffect.pending.is_(True)))).first():
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "target_effect_pending"})
    turn = dict(char.turn_state or {})
    turn["target_effects"] = {k: v for k, v in turn["target_effects"].items() if k != effect_key}
    char.turn_state = turn
    if not slug:
        return False, None
    expiry = _expiry(effect)
    if not with_save:
        for each in (slug, *effect.get("also", ())):
            await apply_condition_to_combatant(db, enc, target, GmConditionApply(
                slug=each, expiry=expiry, source_combatant_id=mine.id,
                ends_with_concentration=bool(effect.get("ends_with_concentration"))), applied_by_gm=False)
        _add_history(db, char.id, "condition_change",
                     f"{condition_label(slug)} su {target.name}" + (" (prolungato)" if extending else ""))
        return True, None
    now = datetime.utcnow().isoformat(timespec="seconds")
    eff = ConditionEffect(
        character_id=target.character_id if target.kind == "pc" else None,
        combatant_id=target.id if target.kind == "monster" else None, slug=slug, pending=True,
        expiry_anchor=expiry["anchor"] if expiry else None, expiry_edge=expiry["edge"] if expiry else None,
        expiry_count=expiry["count"] if expiry else None, source_combatant_id=mine.id, source_character_id=char.id,
        applied_by_gm=False, encounter_id=enc.id, created_at=now,
        ends_with_concentration=bool(effect.get("ends_with_concentration")),
        source_spell_id=char.concentrating_spell_id if effect.get("ends_with_concentration") else None,
        immunity_key=effect_key if effect.get("immune_on_success") else None,
        also_slugs=",".join(effect.get("also", ())) or None,
        # TS ripetuto (Collera della Natura): lo porta la condizione, comincia a contare quando il primo TS è fallito
        save_ability=effect["save_ability"] if effect.get("repeat_save") else None,
        save_dc=effect["save_dc"] if effect.get("repeat_save") else None, save_edge=effect.get("repeat_save"))
    db.add(eff)
    await db.flush()
    save = PendingSave(
        effect_id=eff.id, character_id=eff.character_id, combatant_id=eff.combatant_id,
        ability=effect["save_ability"], dc=effect["save_dc"], status="pending", created_at=now)
    db.add(save)
    await db.flush()
    _add_history(db, char.id, "condition_change", f"{condition_label(slug)} su {target.name}: TS in attesa")
    return True, save

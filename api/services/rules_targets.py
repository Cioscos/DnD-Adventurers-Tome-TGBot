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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.encounter import GmConditionApply
from api.services.condition_effects import ExpirySpec, SaveSpec, clear_effects_for, upsert_effect
from api.services.effects import _add_history, apply_conditions
from core.data.labels import condition_label
from core.db.models import Character, Combatant, ConditionEffect, Encounter, PendingSave


async def pc_char(db: AsyncSession, comb: Combatant) -> Character:
    char = await db.get(Character, comb.character_id) if comb.character_id else None
    if char is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
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


async def apply_target_effect(
    db: AsyncSession, char: Character, enc: Encounter, mine: Combatant, target: Combatant, effect_key: str,
) -> tuple[bool, PendingSave | None]:
    """Applica l'effetto tenuto per ``effect_key``: (applicato, TS in sospeso). Lo consuma.

    La condizione si applica subito; con un TS ne nasce uno in sospeso che la toglie se riesce."""
    effect = pending_target_effect(char, effect_key)
    turn = dict(char.turn_state or {})
    turn["target_effects"] = {k: v for k, v in turn["target_effects"].items() if k != effect_key}
    char.turn_state = turn
    slug = effect.get("condition")
    if not slug:
        return False, None
    await apply_condition_to_combatant(db, enc, target, GmConditionApply(
        slug=slug, expiry=_expiry(effect), source_combatant_id=mine.id), applied_by_gm=False)
    _add_history(db, char.id, "condition_change", f"{condition_label(slug)} su {target.name}")
    save = None
    if effect.get("save_ability") and effect.get("on_failure_only", True):
        eff = await _effect_row(db, target, slug)
        save = PendingSave(
            effect_id=eff.id, character_id=target.character_id if target.kind == "pc" else None,
            combatant_id=target.id if target.kind == "monster" else None,
            ability=effect["save_ability"], dc=effect["save_dc"], status="pending",
            created_at=datetime.utcnow().isoformat(timespec="seconds"))
        db.add(save)
        await db.flush()
    return True, save


async def _effect_row(db: AsyncSession, target: Combatant, slug: str):
    col = ConditionEffect.character_id if target.kind == "pc" else ConditionEffect.combatant_id
    return (await db.execute(select(ConditionEffect).where(
        col == (target.character_id if target.kind == "pc" else target.id), ConditionEffect.slug == slug))).scalar_one()

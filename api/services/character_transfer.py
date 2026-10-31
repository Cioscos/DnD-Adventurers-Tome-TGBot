"""Costruzione del file di esportazione personaggio (nessun ID interno, nessun dato privato)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.schemas.transfer import CharacterExport, ExportCharacter
from api.version import APP_VERSION
from core.db.models import Character

_VOICE_PREFIX = "[VOICE:"


def _val(v):
    return getattr(v, "value", v)


def _meta(raw: str | None) -> dict:
    try:
        parsed = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _export_notes(notes: dict | None) -> dict:
    out: dict = {}
    for title, value in (notes or {}).items():
        rec = value if isinstance(value, dict) else {"body": value}
        body = str(rec.get("body") or "")
        was_voice = body.startswith(_VOICE_PREFIX)  # il file audio non viene esportato
        out[title] = {
            "body": "" if was_voice else body,
            "created_at": rec.get("created_at"),
            "updated_at": rec.get("updated_at"),
            "tags": list(rec.get("tags") or []),
            "was_voice": was_voice,
        }
    return out


async def load_for_export(session: AsyncSession, char_id: int) -> Character | None:
    res = await session.execute(
        select(Character).where(Character.id == char_id).options(
            selectinload(Character.classes),
            selectinload(Character.ability_scores),
            selectinload(Character.spells),
            selectinload(Character.spell_slots),
            selectinload(Character.items),
            selectinload(Character.abilities),
            selectinload(Character.currency),
            selectinload(Character.homebrew_rules),
            selectinload(Character.homebrew_resources),
        )
    )
    return res.scalar_one_or_none()


async def build_export(session: AsyncSession, char: Character) -> CharacterExport:
    # Garantisce le relazioni caricate anche se `char` arriva da una query semplice.
    char = await load_for_export(session, char.id) or char
    classes = sorted(char.classes, key=lambda c: c.id)
    class_key = {c.id: f"c{i}" for i, c in enumerate(classes)}
    spells = sorted(char.spells, key=lambda s: s.id)
    spell_key = {s.id: f"s{i}" for i, s in enumerate(spells)}
    rules = sorted(char.homebrew_rules, key=lambda r: r.id)
    rule_index = {r.id: i for i, r in enumerate(rules)}

    cols = {k: getattr(char, k) for k in ExportCharacter.model_fields if k != "notes"}
    cols["spell_slots_mode"] = _val(char.spell_slots_mode)
    for k in ("settings", "conditions", "skills", "saving_throws", "death_saves",
              "personality", "damage_modifiers"):
        cols[k] = cols[k] or {}
    for k in ("languages", "general_proficiencies"):
        cols[k] = cols[k] or []

    return CharacterExport.model_validate({
        "app_version": APP_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "character": {**cols, "notes": _export_notes(char.notes)},
        "classes": [c.__dict__ for c in classes],
        "ability_scores": [a.__dict__ for a in char.ability_scores],
        "items": [
            {**i.__dict__, "item_metadata": _meta(i.item_metadata), "equipment_slot": _val(i.equipment_slot)}
            for i in sorted(char.items, key=lambda i: i.id)
        ],
        "spells": [{**s.__dict__, "export_key": spell_key[s.id]} for s in spells],
        "concentrating_spell_key": spell_key.get(char.concentrating_spell_id),
        "spell_slots": [s.__dict__ for s in char.spell_slots],
        "abilities": [
            {**a.__dict__, "restoration_type": _val(a.restoration_type),
             "source_class_key": class_key.get(a.source_class_id)}
            for a in sorted(char.abilities, key=lambda a: a.id)
        ],
        "currency": char.currency.__dict__ if char.currency else None,
        "homebrew_rules": [r.__dict__ for r in rules],
        "homebrew_resources": [
            {**h.__dict__, "rule_index": rule_index[h.rule_id], "restoration_type": _val(h.restoration_type)}
            for h in char.homebrew_resources if h.rule_id in rule_index
        ],
    })

"""Costruzione del file di esportazione personaggio (nessun ID interno, nessun dato privato)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.schemas.transfer import CharacterExport, ExportCharacter
from api.services.homebrew.dsl import RuleDSL
from api.version import APP_VERSION
from core.db.models import (
    Ability, AbilityScore, Character, CharacterClass, Currency, HomebrewResource,
    HomebrewRule, Item, RestorationType, Spell, SpellSlot, SpellSlotsMode,
)

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
        was_voice = body.startswith(_VOICE_PREFIX) or bool(rec.get("was_voice"))  # il file audio non viene esportato
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

    # Export tollerante: i limiti di import non si applicano ai dati gia' salvati (altrimenti 500).
    # Anche /duplicate ne beneficia: passa l'oggetto gia' costruito a import_character senza
    # rivalidarlo, quindi un personaggio "legacy" fuori limite si duplica com'e'.
    return CharacterExport.model_validate(context={"lenient": True}, obj={
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
        "spell_slots": [s.__dict__ for s in sorted(char.spell_slots, key=lambda s: (s.is_pact, s.level))],
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


def _unprocessable(msg: str) -> HTTPException:
    return HTTPException(status_code=422, detail=msg)


async def import_character(
    session: AsyncSession, user_id: int, data: CharacterExport, *, name_suffix: str
) -> Character:
    """Crea un nuovo personaggio di `user_id` dal file; gli ID del file non vengono mai usati.

    Non fa commit: la transazione e' quella della richiesta (rollback su qualsiasi errore).
    """
    spell_keys = [sp.export_key for sp in data.spells]
    if len(set(spell_keys)) != len(spell_keys):
        raise _unprocessable("Duplicate spell export_key")
    if data.concentrating_spell_key is not None and data.concentrating_spell_key not in spell_keys:
        raise _unprocessable("Unknown concentrating_spell_key")
    # Chiavi uniche a DB: un file artefatto altrimenti darebbe IntegrityError (500).
    for label, keys in (
        ("class_name", [c.class_name for c in data.classes]),
        ("ability score name", [a.name for a in data.ability_scores]),
        ("spell slot (level, is_pact)", [(s.level, s.is_pact) for s in data.spell_slots]),
        ("homebrew resource key", [h.key for h in data.homebrew_resources]),
    ):
        if len(set(keys)) != len(keys):
            raise _unprocessable(f"Duplicate {label}")
    class_keys = {f"c{i}" for i in range(len(data.classes))}
    for a in data.abilities:
        if a.source_class_key is not None and a.source_class_key not in class_keys:
            raise _unprocessable("Unknown source_class_key")
    for h in data.homebrew_resources:
        if h.rule_index >= len(data.homebrew_rules):
            raise _unprocessable("Unknown rule_index")
    for r in data.homebrew_rules:
        try:
            RuleDSL.model_validate(r.dsl)
        except ValidationError as e:
            errs = e.errors(include_url=False, include_context=False, include_input=False)
            raise _unprocessable(f"Invalid homebrew rule '{r.name}': {errs}")

    taken = (await session.execute(
        select(Character.id).where(Character.user_id == user_id, Character.name == data.character.name)
    )).first() is not None
    name = data.character.name
    if taken:
        name = name[: 100 - len(name_suffix)] + name_suffix

    cols = data.character.model_dump(exclude={"notes", "name", "spell_slots_mode"})
    char = Character(
        user_id=user_id, name=name, notes=data.character.notes,
        spell_slots_mode=SpellSlotsMode(data.character.spell_slots_mode), **cols,
    )
    classes = [CharacterClass(**c.model_dump()) for c in data.classes]
    spells = [Spell(**sp.model_dump(exclude={"export_key"})) for sp in data.spells]
    seen_slots: set = set()
    items = []
    for it in data.items:
        slot, equipped = it.equipment_slot, it.is_equipped
        if slot is not None and equipped:
            if slot in seen_slots:  # due oggetti equipaggiati sullo stesso slot: vince il primo
                slot, equipped = None, False
            seen_slots.add(slot)
        items.append(Item(
            **it.model_dump(exclude={"item_metadata", "equipment_slot", "is_equipped"}),
            item_metadata=json.dumps(it.item_metadata), equipment_slot=slot, is_equipped=equipped,
        ))
    char.classes = classes
    char.ability_scores = [AbilityScore(**a.model_dump()) for a in data.ability_scores]
    char.spells = spells
    char.spell_slots = [SpellSlot(**s.model_dump()) for s in data.spell_slots]
    char.items = items
    char.currency = Currency(**(data.currency.model_dump() if data.currency else {}))
    session.add(char)
    await session.flush()  # assegna gli id nuovi

    for a in data.abilities:
        src = classes[int(a.source_class_key[1:])].id if a.source_class_key else None
        session.add(Ability(
            character_id=char.id, source_class_id=src, restoration_type=RestorationType(a.restoration_type),
            **a.model_dump(exclude={"source_class_key", "restoration_type"}),
        ))
    now = datetime.now(timezone.utc).isoformat()
    rules = [
        HomebrewRule(character_id=char.id, created_at=now, updated_at=now, **r.model_dump())
        for r in data.homebrew_rules
    ]
    session.add_all(rules)
    await session.flush()
    for h in data.homebrew_resources:
        session.add(HomebrewResource(
            character_id=char.id, rule_id=rules[h.rule_index].id,
            restoration_type=RestorationType(h.restoration_type),
            **h.model_dump(exclude={"rule_index", "restoration_type"}),
        ))
    if data.concentrating_spell_key is not None:
        char.concentrating_spell_id = spells[spell_keys.index(data.concentrating_spell_key)].id
    await session.flush()
    return char

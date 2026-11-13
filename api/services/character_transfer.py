"""Costruzione del file di esportazione personaggio (nessun ID interno, nessun dato privato)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.schemas.common import normalize_proficiencies
from api.schemas.transfer import CharacterExport, ExportCharacter
from api.services.homebrew.dsl import RuleDSL
from api.services.wild_shape import start_form
from api.version import APP_VERSION
from core.data.tools import TOOLS
from core.rules.tools import migrate_tools
from core.game.containers import is_container
from core.game.stats import migrate_character_ac
from core.rules.feature_sync import (
    ABILITY_BONUS_KEY, ARCHIVED_FEATURES, GRANTED_CREATED, GRANTED_SPELL_KEYS, REPLACED_AT_REST, RETROFIT_DONE, clean_ability_bonus, clean_archive, clean_granted_keys,
    clean_target_immunity, clean_zero_hp_uses,
)
from core.rules.level_choices import FREE_KNOWN_KEY
from api.services.spell_slots import CREATED_SLOTS, clean_created_slots
from core.rules.states import ALLY_EXCLUSIVE, COND_RELEASE, SPELL_CAST_TYPE, SPELL_GIVEN, SPELL_RELEASE, SPELL_SPENT, SPELL_TEMP_DROPPED, SUSPENDED_KEY, SUSPENDED_ON, TARGET_IMMUNITY, TEMP_GIVEN, TEMP_RELEASE, ZERO_HP_USES
from core.rules.subclasses import sync_subclass_keys
from api.services.item_charges import attunement_limit
from core.game.item_bonuses import is_attuned
from core.db.models import (
    Ability, AbilityScore, Character, CharacterClass, Companion, Currency, HomebrewResource,
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
            "campaign_id": rec.get("campaign_id"),
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
            selectinload(Character.companions),
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
    sorted_items = sorted(char.items, key=lambda i: i.id)
    item_ref = {i.id: n for n, i in enumerate(sorted_items)}  # indici, non id: l'export resta stabile al reimport

    cols = {k: getattr(char, k) for k in ExportCharacter.model_fields if k != "notes"}
    cols["spell_slots_mode"] = _val(char.spell_slots_mode)
    for k in ("settings", "conditions", "skills", "saving_throws", "death_saves",
              "personality", "damage_modifiers", "tool_proficiencies"):
        cols[k] = cols[k] or {}
    for k in ("languages", "pending_choices"):
        cols[k] = cols[k] or []
    cols["general_proficiencies"] = normalize_proficiencies(cols["general_proficiencies"])
    # Gli incantesimi che non contano fra i conosciuti stanno per id: nel file usano le chiavi "s{i}" degli incantesimi.
    free = cols["settings"].get(FREE_KNOWN_KEY)
    if free is not None:
        cols["settings"] = {**cols["settings"],
                            FREE_KNOWN_KEY: [spell_key[i] for i in free if isinstance(i, int) and i in spell_key]}
    # hp_rolls e' indicizzato per class_id: nel file usa le stesse chiavi "c{i}" delle abilita'.
    raw_rolls = cols["settings"].get("hp_rolls")
    if raw_rolls is not None:  # dati legacy/corrotti: scarta quel che non e' {id: {...}}
        valid = {}
        for cid, m in (raw_rolls.items() if isinstance(raw_rolls, dict) else ()):
            try:
                if int(cid) in class_key and isinstance(m, dict):
                    valid[class_key[int(cid)]] = m
            except (TypeError, ValueError):
                pass
        cols["settings"] = {**cols["settings"], "hp_rolls": valid}

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
            {**i.__dict__, "item_metadata": _meta(i.item_metadata), "equipment_slot": _val(i.equipment_slot),
             "ref": item_ref[i.id], "container_ref": item_ref.get(i.container_id)}
            for i in sorted_items
        ],
        "spells": [{**s.__dict__, "export_key": spell_key[s.id], "source_class_key": class_key.get(s.class_id)}
                   for s in spells],
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
        "companions": [c.__dict__ for c in sorted(char.companions, key=lambda c: c.id)],
    })


def _unprocessable(msg: str) -> HTTPException:
    return HTTPException(status_code=422, detail=msg)


def _link_containers(specs, items) -> None:
    """Seconda passata: ref inesistenti/duplicati, non-contenitori, auto-riferimenti e cicli -> radice."""
    refs = [s.ref for s in specs if s.ref is not None]
    by_ref = {s.ref: it for s, it in zip(specs, items) if s.ref is not None and refs.count(s.ref) == 1}
    parent = {}
    for s, it in zip(specs, items):
        t = by_ref.get(s.container_ref)
        if t is not None and t is not it and is_container(t):
            parent[it] = t
            it.container_id = t.id
            it.is_equipped, it.equipment_slot = False, None  # chi sta in un contenitore non e' mai equipaggiato
    for it in items:  # chi ritrova se stesso risalendo la catena e' in un ciclo
        cur, n = parent.get(it), 0
        while cur is not None and cur is not it and n <= len(items):
            cur, n = parent.get(cur), n + 1
        if cur is it:
            it.container_id = None


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
    if any(sp.source_class_key is not None and sp.source_class_key not in class_keys for sp in data.spells):
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
    cols["general_proficiencies"] = normalize_proficiencies(cols["general_proficiencies"])
    cols["tool_proficiencies"] = {k: v for k, v in cols["tool_proficiencies"].items()
                                  if k in TOOLS and v in (True, "expert")}  # file modificato a mano: solo il catalogo
    char = Character(
        user_id=user_id, name=name, notes=data.character.notes,
        spell_slots_mode=SpellSlotsMode(data.character.spell_slots_mode), **cols,
    )
    migrate_tools(char)  # export vecchi: strumenti scritti come testo
    classes = [CharacterClass(**c.model_dump()) for c in data.classes]
    spells = [Spell(**sp.model_dump(exclude={"export_key", "source_class_key"})) for sp in data.spells]
    seen_slots: set = set()
    items = []
    for it in data.items:  # un contenitore e' sempre singolo: la quantita' si normalizza a 1, il contenuto (monete incluse) resta
        if it.quantity != 1 and "container" in it.item_metadata:
            it.quantity = 1
    refs = [s.ref for s in data.items if s.ref is not None]
    boxes = {s.ref for s in data.items if s.ref is not None and refs.count(s.ref) == 1 and "container" in s.item_metadata}
    for it in data.items:
        slot, equipped = it.equipment_slot, it.is_equipped
        if it.container_ref in boxes:  # finira' in un contenitore: non deve rubare lo slot a un oggetto indossato
            slot, equipped = None, False
        if slot is not None and equipped:
            if slot in seen_slots:  # due oggetti equipaggiati sullo stesso slot: vince il primo
                slot, equipped = None, False
            seen_slots.add(slot)
        items.append(Item(
            **it.model_dump(exclude={"item_metadata", "equipment_slot", "is_equipped", "ref", "container_ref"}),
            item_metadata=json.dumps(it.item_metadata), equipment_slot=slot, is_equipped=equipped,
        ))
    char.classes = classes
    sync_subclass_keys(char)
    char.ability_scores = [AbilityScore(**a.model_dump()) for a in data.ability_scores]
    char.spells = spells
    char.spell_slots = [SpellSlot(**s.model_dump()) for s in data.spell_slots]
    char.items = items
    if sum(1 for it in items if is_attuned(it)) > attunement_limit(char):  # il limite dipende dalla scheda importata
        raise _unprocessable("attunement_limit")
    char.currency = Currency(**(data.currency.model_dump() if data.currency else {}))
    session.add(char)
    await session.flush()  # assegna gli id nuovi

    _link_containers(data.items, items)

    rolls = (char.settings or {}).get("hp_rolls")
    if isinstance(rolls, dict) and rolls:  # chiavi "c{i}" del file -> id nuovi; chiavi sconosciute scartate
        s = dict(char.settings)
        s["hp_rolls"] = {str(classes[int(k[1:])].id): v for k, v in rolls.items()
                         if k in class_keys and isinstance(v, dict)}
        char.settings = s
    elif rolls is not None:  # non-dict (file artefatto): ignora
        char.settings = {k: v for k, v in char.settings.items() if k != "hp_rolls"}

    if ARCHIVED_FEATURES in (char.settings or {}):  # server-owned: il client non potrebbe più ripararlo
        char.settings = {**char.settings, ARCHIVED_FEATURES: clean_archive(char.settings[ARCHIVED_FEATURES])}
    if FREE_KNOWN_KEY in (char.settings or {}):  # chiavi "s{i}" del file -> id nuovi; il resto è scartato
        by_key = {sp.export_key: row.id for sp, row in zip(data.spells, spells)}
        wanted = char.settings[FREE_KNOWN_KEY]
        char.settings = {**char.settings, FREE_KNOWN_KEY: [by_key[k] for k in wanted if isinstance(k, str) and k in by_key]
                         if isinstance(wanted, list) else []}
    for granted_key in (GRANTED_SPELL_KEYS, GRANTED_CREATED):
        if granted_key in (char.settings or {}):
            char.settings = {**char.settings, granted_key: clean_granted_keys(char.settings[granted_key])}
    for key, clean in ((ABILITY_BONUS_KEY, clean_ability_bonus), (ZERO_HP_USES, clean_zero_hp_uses),
                       (TARGET_IMMUNITY, clean_target_immunity), (CREATED_SLOTS, clean_created_slots)):
        if key in (char.settings or {}):
            char.settings = {**char.settings, key: clean(char.settings[key])}

    # un file importato passa dal retrofit per le sue classi (R34, R39): il segno del file non vale
    # gli id dei personaggi di un altro database non valgono qui
    char.settings = {k: v for k, v in (char.settings or {}).items() if k not in (RETROFIT_DONE, REPLACED_AT_REST, ALLY_EXCLUSIVE, TEMP_GIVEN, TEMP_RELEASE, SPELL_GIVEN, SPELL_RELEASE, SPELL_SPENT, SPELL_TEMP_DROPPED, SPELL_CAST_TYPE, SUSPENDED_KEY, COND_RELEASE, SUSPENDED_ON)}

    for sp, row in zip(data.spells, spells):
        row.class_id = classes[int(sp.source_class_key[1:])].id if sp.source_class_key else None
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
    active_seen, active_form = False, None
    for c in data.companions:  # al massimo una forma attiva, solo per wild_shape
        active = c.is_active and c.kind == "wild_shape" and not active_seen
        active_seen = active_seen or active
        comp = Companion(
            character_id=char.id, created_at=now,
            **c.model_dump(exclude={"is_active", "current_hp"}),
            current_hp=min(c.current_hp, c.max_hp), is_active=active,
        )
        session.add(comp)
        if active:
            active_form = comp
    if data.concentrating_spell_key is not None:
        char.concentrating_spell_id = spells[spell_keys.index(data.concentrating_spell_key)].id
    migrate_character_ac(char)  # file vecchi: valore del file, Destrezza già inclusa, altra scheda
    await session.flush()
    if active_form is not None:  # la forma attiva del file riprende con il suo stato (senza nuovi PF temporanei)
        await session.refresh(char, attribute_names=["classes"])
        start_form(char, active_form, grant=False)
    return char

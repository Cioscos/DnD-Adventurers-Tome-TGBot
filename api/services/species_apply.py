"""Scelta e cambio della specie 2024 sulla scheda (spec cataloghi 2024, obiettivo 8 e «Scelte del designer»).

``plan_species`` valida e calcola i cambiamenti senza scrivere (anteprima); ``apply_species`` li applica e risincronizza.
Gli effetti una tantum (abilità di Sensi acuti/Abile, talento di Versatile) restano in ``species_options`` con chiavi
``_granted_skill``/``_feat_ability_id`` per poterli togliere al cambio.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.choices import _SRD_DIR, remove_feat, take_feat
from api.services.class_features import sync_cataloged_features
from core.data.feats_2024 import ALL_FEATS
from core.data.species_2024 import SPECIES_2024, required_choices
from api.services.condition_effects import release_concentration_effects
from api.services.durations import end_concentration
from core.db.models import Ability, Character
from core.rules.catalog import active_features
from core.rules.catalog.species_2024 import SPECIES_TRAITS, SpeciesSource
from core.rules.edition import character_edition
from core.rules.feature_sync import GRANTED_CREATED, GRANTED_SPELL_KEYS

GRANTED_SKILL = "_granted_skill"
FEAT_ABILITY_ID = "_feat_ability_id"
_LINEAGE_CHOICES = ("lineage", "legacy")


def _bad(code: str) -> HTTPException:
    return HTTPException(422, code)


@lru_cache(maxsize=1)
def _old_trait_names() -> frozenset[str]:
    """Nomi (it/en, minuscoli) dei tratti delle razze 2014 del wizard e dei tratti 2024: le righe di testo da archiviare."""
    names: set[str] = set()
    races = json.loads((_SRD_DIR / "races.json").read_text(encoding="utf-8"))["items"]
    for race in races:
        for trait in [*race["traits"], *(t for sub in race.get("subraces") or [] for t in sub.get("traits") or [])]:
            names.update(n.lower() for n in trait["name"].values())
    for data in SPECIES_2024.values():
        for _key, name, _summary in data.traits:
            names.update(n.lower() for n in name.values())
    return frozenset(names)


@lru_cache(maxsize=1)
def _race_note_texts() -> frozenset[str]:
    """Testi (it/en) delle note sui tiri che il vecchio wizard scrive dalla razza (webapp/src/lib/species.ts, max 120)."""
    races = json.loads((_SRD_DIR / "races.json").read_text(encoding="utf-8"))["items"]
    notes = [n for race in races for n in [*race["roll_notes"].values(),
                                           *(v for sub in race.get("subraces") or [] for v in (sub.get("roll_notes") or {}).values())]]
    return frozenset(text[:120] for n in notes for text in n.values())


def _cleaned_settings(settings: dict) -> dict:
    """Senza la scurovisione e le note di razza (le dà la specie); sensi e note personali restano."""
    out = dict(settings)
    senses = [s for s in out.pop("senses", None) or [] if not (isinstance(s, dict) and s.get("type") == "darkvision")]
    notes = {k: v for k, v in (out.pop("roll_notes", None) or {}).items() if not (isinstance(v, str) and v in _race_note_texts())}
    return {**out, **({"senses": senses} if senses else {}), **({"roll_notes": notes} if notes else {})}


@dataclass
class SpeciesPlan:
    changes: list[str] = field(default_factory=list)
    first: bool = False
    old_rows: list[Ability] = field(default_factory=list)
    drop_skill: str | None = None
    add_skill: str | None = None
    keep_skill: str | None = None
    drop_feat: Ability | None = None
    add_feat: str | None = None
    keep_feat: Ability | None = None
    drop_spells: list[str] = field(default_factory=list)  # srd_index


def _feat_row(char: Character, old: dict) -> Ability | None:
    """La riga del talento di Versatile: per id, o per chiave se l'id non vale più (personaggio importato)."""
    if not old.get("origin_feat"):
        return None
    rows = [a for a in char.abilities if a.feature_key == f"feat.{old['origin_feat']}"]
    return next((a for a in rows if a.id == old.get(FEAT_ABILITY_ID)), None) or next(iter(rows), None)


def plan_species(char: Character, key: str, options: dict[str, str]) -> SpeciesPlan:
    """Valida tutto (422) e calcola i cambiamenti, senza scrivere."""
    if character_edition(char) != "2024":
        raise _bad("species_edition")
    data = SPECIES_2024.get(key)
    if data is None:
        raise _bad("species_unknown")
    choices = {c.key: c for c in data.choices}
    if (any(k not in choices or v not in choices[k].options for k, v in options.items())
            or any(k not in options for k in required_choices(key))):
        raise _bad("species_options_invalid")

    plan = SpeciesPlan()
    old = char.species_options or {}
    skills = char.skills or {}
    if char.species_key is None:
        plan.first = True
        settings, cleaned = char.settings or {}, _cleaned_settings(char.settings or {})
        names = _old_trait_names()
        plan.old_rows = [a for a in char.abilities if not a.feature_key and a.source_class_id is None
                         and (a.name or "").strip().lower() in names]
        plan.changes += [code for code, hit in (
            ("speed_reset", char.speed != data.speed_ft), ("senses_removed", (settings.get("senses") or []) != cleaned.get("senses", [])),
            ("roll_notes_removed", (settings.get("roll_notes") or {}) != cleaned.get("roll_notes", {}))) if hit]
        if plan.old_rows:  # cancellate, non archiviate: il giocatore vede quali
            plan.changes.append(f"traits_archived:{len(plan.old_rows)}")
            plan.changes += [f"trait_removed:{a.name}" for a in plan.old_rows]
        race = (char.race or "").lower()
        if "nan" in race or "dwarf" in race:
            plan.changes.append("hp_check")
        plan.changes.append("scores_check")

    old_skill, new_skill = old.get(GRANTED_SKILL), options.get("skill")
    if old_skill and old_skill == new_skill:
        plan.keep_skill = old_skill
    else:
        if old_skill and skills.get(old_skill) is True:  # ancora quella data dalla specie (non Maestria nel frattempo)
            plan.drop_skill = old_skill
            plan.changes.append(f"skill_removed:{old_skill}")
        if new_skill and not skills.get(new_skill):  # già competente da altro: niente da dare né da togliere poi
            plan.add_skill = new_skill
            plan.changes.append(f"skill_added:{new_skill}")

    old_row, new_feat = _feat_row(char, old), options.get("origin_feat")
    if old_row is not None and old.get("origin_feat") == new_feat:
        plan.keep_feat = old_row
    else:
        if old_row is not None:
            plan.drop_feat = old_row
            plan.changes.append(f"feat_removed:{old['origin_feat']}")
        if new_feat:  # le opzioni sono già solo talenti d'Origine 2024; resta il «già preso» di take_feat, controllato qui
            if not ALL_FEATS[new_feat].repeatable and any(
                    a.feature_key == f"feat.{new_feat}" and a is not old_row for a in char.abilities):
                raise _bad("species_options_invalid")
            plan.add_feat = new_feat
            plan.changes.append(f"feat_added:{new_feat}")

    # D-005: gli incantesimi che la vecchia specie ha creato sulla scheda se ne vanno con lei, come abilità e talento.
    # Restano quelli che il personaggio aveva già di suo e quelli che dà anche un altro privilegio o la nuova specie.
    level = max(1, sum(c.level or 0 for c in char.classes))

    def spells_of(species: str | None, chosen: dict) -> set[str]:
        return {k for s in SPECIES_TRAITS.get(species or "", ()) if s.level <= level
                and (s.option_group is None or s.option_key == chosen.get(s.option_group)) for k in s.granted_spells}

    leaving = spells_of(char.species_key, old) & set((char.settings or {}).get(GRANTED_CREATED) or [])
    if leaving:
        kept = spells_of(key, options) | {k for spec, src in active_features(char)
                                         if not isinstance(src, SpeciesSource) for k in spec.granted_spells}
        plan.drop_spells = sorted(leaving - kept)
        names = {s.srd_index: s.name for s in char.spells}
        plan.changes += [f"spell_removed:{names[k]}" for k in plan.drop_spells if k in names]
    return plan


async def apply_species(session: AsyncSession, char: Character, key: str, options: dict, lang: str) -> list[str]:
    """Scrive la specie 2024 ``key`` con le sue scelte; tutto o niente (la validazione è in ``plan_species``)."""
    plan = plan_species(char, key, options)
    data = SPECIES_2024[key]
    stored = dict(options)

    if plan.drop_feat is not None:  # il percorso di «Rimuovi talento»; la riga sparisce dal DB, la collezione si ricarica
        await remove_feat(session, char, plan.drop_feat)
        await session.refresh(char, attribute_names=["abilities"])
    if plan.first:
        char.speed = data.speed_ft
        char.settings = _cleaned_settings(char.settings or {})
        for row in plan.old_rows:
            char.abilities.remove(row)
    skills = dict(char.skills or {})
    if plan.drop_skill:
        skills.pop(plan.drop_skill, None)
    if plan.add_skill:
        skills[plan.add_skill] = True
    char.skills = skills
    if plan.keep_skill or plan.add_skill:
        stored[GRANTED_SKILL] = plan.keep_skill or plan.add_skill
    if plan.add_feat:
        row = take_feat(session, char, plan.add_feat, None, lang, "creation")
        await session.flush()
        stored[FEAT_ABILITY_ID] = row.id
    elif plan.keep_feat is not None:
        stored[FEAT_ABILITY_ID] = plan.keep_feat.id

    name = data.name.get(lang) or data.name["it"]
    lineage = next((c for c in data.choices if c.key in _LINEAGE_CHOICES and c.key in options), None)
    if lineage is not None:
        label = lineage.option_labels[options[lineage.key]]
        name = f"{name} ({label.get(lang) or label['it']})"
    char.race = name
    char.species_key = key
    char.species_options = stored
    await sync_cataloged_features(session, char, lang)
    for spell in [s for s in char.spells if s.srd_index in plan.drop_spells]:
        if char.concentrating_spell_id == spell.id:
            end_concentration(char)
            await session.flush()
            await release_concentration_effects(session, char)
        char.spells.remove(spell)
        await session.delete(spell)
    if plan.drop_spells:
        char.settings = {**(char.settings or {}), **{k: [x for x in (char.settings or {}).get(k) or [] if x not in plan.drop_spells]
                                                     for k in (GRANTED_CREATED, GRANTED_SPELL_KEYS)}}
    return plan.changes

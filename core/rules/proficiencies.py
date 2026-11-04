"""Competenze concesse dalle classi, per edizione, e verifica di armi e armature.

Valori dalle schede `docs/superpowers/rules/<anno>/classes/` e da `2014/general.md` (multiclasse).
Le concessioni si scrivono nel formato oggetto di `Character.general_proficiencies`
(`armor`, `weapons`, `tools`, `other`), sommandole a quanto c'è già.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from core.data.classes import get_saving_throw_proficiencies
from core.data.skills import SKILL_ABILITY_MAP
from core.rules.edition import character_edition, class_key as row_class_key
from core.rules.types import Edition

CATEGORIES = ("armor", "weapons", "tools", "other")
SEEDED_FLAG = "proficiencies_seeded"
FEATURE_GRANTS_KEY = "feature_proficiencies_granted"

# id -> (it, en). Le armi specifiche sono al singolare: si confrontano col nome dell'oggetto.
LABELS: dict[str, tuple[str, str]] = {
    "light": ("Armature leggere", "Light armor"),
    "medium": ("Armature medie", "Medium armor"),
    "heavy": ("Armature pesanti", "Heavy armor"),
    "shields": ("Scudi", "Shields"),
    "simple": ("Armi semplici", "Simple weapons"),
    "martial": ("Armi da guerra", "Martial weapons"),
    "martial_light": ("Armi da guerra con proprietà Leggera", "Martial weapons with the Light property"),
    "martial_finesse_light": ("Armi da guerra con proprietà Accurata o Leggera",
                              "Martial weapons with the Finesse or Light property"),
    "hand_crossbow": ("Balestra a mano", "Hand crossbow"),
    "longsword": ("Spada lunga", "Longsword"),
    "rapier": ("Stocco", "Rapier"),
    "shortsword": ("Spada corta", "Shortsword"),
    "dagger": ("Pugnale", "Dagger"),
    "dart": ("Dardo", "Dart"),
    "sling": ("Fionda", "Sling"),
    "quarterstaff": ("Bastone ferrato", "Quarterstaff"),
    "light_crossbow": ("Balestra leggera", "Light crossbow"),
    "club": ("Randello", "Club"),
    "javelin": ("Giavellotto", "Javelin"),
    "mace": ("Mazza", "Mace"),
    "scimitar": ("Scimitarra", "Scimitar"),
    "sickle": ("Falcetto", "Sickle"),
    "spear": ("Lancia", "Spear"),
    "thieves_tools": ("Arnesi da scasso", "Thieves' tools"),
    "herbalism_kit": ("Borsa da erborista", "Herbalism kit"),
    "thieves_cant": ("Gergo Ladresco", "Thieves' Cant"),
    "druidic": ("Druidico", "Druidic"),
}
_ALIAS: dict[str, str] = {label.lower(): pid for pid, labels in LABELS.items() for label in labels}

_ARMOR = {"light", "medium", "heavy", "shields"}
_TOOLS = {"thieves_tools", "herbalism_kit"}
_LANGS = {"thieves_cant", "druidic"}


@dataclass(frozen=True)
class ProficiencyGrant:
    armor: tuple[str, ...] = ()
    weapons: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    saves: tuple[str, ...] = ()
    skills_from: tuple[str, ...] = ()
    skills_count: int = 0
    languages: tuple[str, ...] = ()


ALL_SKILLS = tuple(sorted(SKILL_ABILITY_MAP))
_SPECIFIC_CASTER = ("dagger", "dart", "sling", "quarterstaff", "light_crossbow")
_ROGUE_BARD_2014 = ("simple", "hand_crossbow", "longsword", "rapier", "shortsword")
_ALL_ARMOR = ("light", "medium", "heavy", "shields")
_MEDIUM = ("light", "medium", "shields")


def _g(armor=(), weapons=(), tools=(), skills_from=(), skills_count=0, languages=()) -> ProficiencyGrant:
    return ProficiencyGrant(tuple(armor), tuple(weapons), tuple(tools), (), tuple(skills_from), skills_count,
                            tuple(languages))


def _s(*names: str) -> tuple[str, ...]:
    return tuple(names)


# Prima classe del personaggio: edizione -> classe.
_FIRST: dict[str, dict[str, ProficiencyGrant]] = {
    "2014": {
        "barbarian": _g(_MEDIUM, ("simple", "martial"), (), _s("animal_handling", "athletics", "intimidation", "nature", "perception", "survival"), 2),
        "bard": _g(("light",), _ROGUE_BARD_2014, (), ALL_SKILLS, 3),
        "cleric": _g(_MEDIUM, ("simple",), (), _s("history", "insight", "medicine", "persuasion", "religion"), 2),
        "druid": _g(_MEDIUM, ("club", "dagger", "dart", "javelin", "mace", "quarterstaff", "scimitar", "sickle", "sling", "spear"),
                    ("herbalism_kit",), _s("arcana", "animal_handling", "insight", "medicine", "nature", "perception", "religion", "survival"), 2, ("druidic",)),
        "fighter": _g(_ALL_ARMOR, ("simple", "martial"), (), _s("acrobatics", "animal_handling", "athletics", "history", "insight", "intimidation", "perception", "survival"), 2),
        "monk": _g((), ("simple", "shortsword"), (), _s("acrobatics", "athletics", "history", "insight", "religion", "stealth"), 2),
        "paladin": _g(_ALL_ARMOR, ("simple", "martial"), (), _s("athletics", "insight", "intimidation", "medicine", "persuasion", "religion"), 2),
        "ranger": _g(_MEDIUM, ("simple", "martial"), (), _s("animal_handling", "athletics", "insight", "investigation", "nature", "perception", "stealth", "survival"), 3),
        "rogue": _g(("light",), _ROGUE_BARD_2014, ("thieves_tools",), _s("acrobatics", "athletics", "deception", "insight", "intimidation", "investigation", "perception", "performance", "persuasion", "sleight_of_hand", "stealth"), 4, ("thieves_cant",)),
        "sorcerer": _g((), _SPECIFIC_CASTER, (), _s("arcana", "deception", "insight", "intimidation", "persuasion", "religion"), 2),
        "warlock": _g(("light",), ("simple",), (), _s("arcana", "deception", "history", "intimidation", "investigation", "nature", "religion"), 2),
        "wizard": _g((), _SPECIFIC_CASTER, (), _s("arcana", "history", "insight", "investigation", "medicine", "religion"), 2),
    },
    "2024": {
        "barbarian": _g(_MEDIUM, ("simple", "martial"), (), _s("animal_handling", "athletics", "intimidation", "nature", "perception", "survival"), 2),
        "bard": _g(("light",), ("simple",), (), ALL_SKILLS, 3),
        "cleric": _g(_MEDIUM, ("simple",), (), _s("history", "insight", "medicine", "persuasion", "religion"), 2),
        "druid": _g(("light", "shields"), ("simple",), ("herbalism_kit",), _s("arcana", "animal_handling", "insight", "medicine", "nature", "perception", "religion", "survival"), 2, ("druidic",)),
        "fighter": _g(_ALL_ARMOR, ("simple", "martial"), (), _s("acrobatics", "animal_handling", "athletics", "history", "insight", "intimidation", "persuasion", "perception", "survival"), 2),
        "monk": _g((), ("simple", "martial_light"), (), _s("acrobatics", "athletics", "history", "insight", "religion", "stealth"), 2),
        "paladin": _g(_ALL_ARMOR, ("simple", "martial"), (), _s("athletics", "insight", "intimidation", "medicine", "persuasion", "religion"), 2),
        "ranger": _g(_MEDIUM, ("simple", "martial"), (), _s("animal_handling", "athletics", "insight", "investigation", "nature", "perception", "stealth", "survival"), 3),
        "rogue": _g(("light",), ("simple", "martial_finesse_light"), ("thieves_tools",), _s("acrobatics", "athletics", "deception", "insight", "intimidation", "investigation", "perception", "persuasion", "sleight_of_hand", "stealth"), 4, ("thieves_cant",)),
        "sorcerer": _g((), ("simple",), (), _s("arcana", "deception", "insight", "intimidation", "persuasion", "religion"), 2),
        "warlock": _g(("light",), ("simple",), (), _s("arcana", "deception", "history", "intimidation", "investigation", "nature", "religion"), 2),
        "wizard": _g((), ("simple",), (), _s("arcana", "history", "insight", "investigation", "medicine", "nature", "religion"), 2),
    },
}

# Classe aggiunta a un personaggio che ne ha già una: tabella multiclasse (nessun TS).
_MULTI: dict[str, dict[str, ProficiencyGrant]] = {
    "2014": {
        "barbarian": _g(("shields",), ("simple", "martial")),
        "bard": _g(("light",), (), (), ALL_SKILLS, 1),
        "cleric": _g(_MEDIUM),
        "druid": _g(_MEDIUM, (), (), (), 0, ("druidic",)),
        "fighter": _g(_MEDIUM, ("simple", "martial")),
        "monk": _g((), ("simple", "shortsword")),
        "paladin": _g(_MEDIUM, ("simple", "martial")),
        "ranger": _g(_MEDIUM, ("simple", "martial"), (), _FIRST["2014"]["ranger"].skills_from, 1),
        "rogue": _g(("light",), (), ("thieves_tools",), _FIRST["2014"]["rogue"].skills_from, 1, ("thieves_cant",)),
        "sorcerer": _g(),
        "warlock": _g(("light",), ("simple",)),
        "wizard": _g(),
    },
    "2024": {
        "barbarian": _g(("shields",), ("martial",)),
        "bard": _g(("light",), (), (), ALL_SKILLS, 1),
        "cleric": _g(_MEDIUM),
        "druid": _g(("light", "shields"), (), (), (), 0, ("druidic",)),
        "fighter": _g(_MEDIUM, ("martial",)),
        "monk": _g(),
        "paladin": _g(_MEDIUM, ("martial",)),
        "ranger": _g(_MEDIUM, ("martial",), (), _FIRST["2024"]["ranger"].skills_from, 1),
        "rogue": _g(("light",), (), ("thieves_tools",), _FIRST["2024"]["rogue"].skills_from, 1, ("thieves_cant",)),
        "sorcerer": _g(),
        "warlock": _g(("light",)),
        "wizard": _g(),
    },
}


def class_proficiencies(edition: Edition, class_key: str | None, as_multiclass: bool) -> ProficiencyGrant:
    """Concessione della classe; vuota per le classi custom. I TS solo per la prima classe."""
    table = (_MULTI if as_multiclass else _FIRST).get(edition, {})
    base = table.get(class_key or "")
    if base is None:
        return ProficiencyGrant()
    saves = () if as_multiclass else tuple(get_saving_throw_proficiencies(class_key))
    return ProficiencyGrant(base.armor, base.weapons, base.tools, saves, base.skills_from, base.skills_count,
                            base.languages)


def label(pid: str, lang: str = "it") -> str:
    it, en = LABELS[pid]
    return en if lang == "en" else it


def normalize(raw: Any) -> dict[str, list[str]]:
    """Come `api.schemas.common.normalize_proficiencies`: lista piatta -> `other`; oggetto -> le 4 categorie."""
    if isinstance(raw, dict):
        return {k: [str(x) for x in (raw.get(k) or [])] for k in CATEGORIES}
    return {**{k: [] for k in CATEGORIES}, "other": [str(x) for x in (raw or [])]}


def _canon(text: str) -> str:
    low = text.strip().lower()
    return _ALIAS.get(low, low)


def _add(target: list[str], entries: list[str]) -> bool:
    have = {_canon(x) for x in target}
    changed = False
    for e in entries:
        if _canon(e) not in have:
            target.append(e)
            have.add(_canon(e))
            changed = True
    return changed


def merge_grant(char: Any, grant: ProficiencyGrant, lang: str = "it", skills: tuple[str, ...] = ()) -> None:
    """Somma la concessione a quanto il personaggio ha già: mai sovrascrive né toglie.

    ``skills`` sono le abilità scelte (già validate); un'abilità già `expert` resta tale.
    """
    cats = normalize(char.general_proficiencies)
    changed = _add(cats["armor"], [label(p, lang) for p in grant.armor])
    changed |= _add(cats["weapons"], [label(p, lang) for p in grant.weapons])
    changed |= _add(cats["tools"], [label(p, lang) for p in grant.tools])
    if changed or not isinstance(char.general_proficiencies, dict):
        char.general_proficiencies = cats  # riassegnato: la colonna JSON non traccia le mutazioni
    if grant.saves:
        saves = dict(char.saving_throws or {})
        for ability in grant.saves:
            saves.setdefault(ability, True)
        char.saving_throws = saves
    if grant.languages:
        langs = list(char.languages or [])
        if _add(langs, [label(p, lang) for p in grant.languages]):
            char.languages = langs
    if skills:
        current = dict(char.skills or {})
        for s in skills:
            if current.get(s) != "expert":
                current[s] = True
        char.skills = current


def validate_skill_choices(grant: ProficiencyGrant, chosen: list[str]) -> str | None:
    """Messaggio d'errore se la scelta non rispetta elenco e numero della concessione, altrimenti `None`."""
    if len(set(chosen)) != len(chosen):
        return "Duplicate skill"
    if any(s not in grant.skills_from for s in chosen):
        return "Skill not allowed for this class"
    if len(chosen) > grant.skills_count:
        return f"At most {grant.skills_count} skills"
    return None


def grant_to_dict(grant: ProficiencyGrant, lang: str = "it") -> dict:
    return {
        "armor": [label(p, lang) for p in grant.armor],
        "weapons": [label(p, lang) for p in grant.weapons],
        "tools": [label(p, lang) for p in grant.tools],
        "saves": list(grant.saves),
        "skills_from": list(grant.skills_from),
        "skills_count": grant.skills_count,
        "languages": [label(p, lang) for p in grant.languages],
    }


def mark_seeded(char: Any) -> None:
    char.settings = {**(char.settings or {}), SEEDED_FLAG: True}


def _meta(item: Any) -> dict:
    raw = getattr(item, "item_metadata", None)
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return {}
    return raw if isinstance(raw, dict) else {}


def _profs(char: Any, *cats: str) -> set[str]:
    data = normalize(char.general_proficiencies)
    return {_canon(x) for c in cats for x in data[c]}


def _unseeded_empty(char: Any, profs: set[str]) -> bool:
    """Personaggio mai seminato e senza elenco: non si toglie nulla finché non ha competenze proprie."""
    return not profs and not (getattr(char, "settings", None) or {}).get(SEEDED_FLAG)


def is_weapon_proficient(char: Any, item: Any) -> bool:
    """False solo se l'arma ha categoria nota (semplice/da guerra) e nulla la copre.

    Oggetto senza categoria, o personaggio mai seminato e con elenco vuoto: competente (nessuna perdita di bonus).
    """
    meta = _meta(item)
    category = meta.get("weapon_category")
    profs = _profs(char, "weapons", "other")
    if category not in ("simple", "martial") or _unseeded_empty(char, profs):
        return True
    if category in profs or _canon(str(getattr(item, "name", ""))) in profs:
        return True
    if category == "martial":
        props = " ".join(str(p).lower() for p in meta.get("properties") or [])
        light = "light" in props or "legger" in props
        finesse = "finesse" in props or "accurat" in props
        return ("martial_light" in profs and light) or ("martial_finesse_light" in profs and (light or finesse))
    return False


def is_armor_proficient(char: Any, item: Any) -> bool:
    """Armatura o scudo: stesso criterio di `is_weapon_proficient` (tipo ignoto = competente)."""
    if _unseeded_empty(char, _profs(char, "armor", "other")):
        return True
    item_type = getattr(item, "item_type", None)
    kind = "shields" if item_type == "shield" else _meta(item).get("armor_type") if item_type == "armor" else None
    return kind not in _ARMOR or kind in _profs(char, "armor", "other")


def seed_character(char: Any, lang: str = "it") -> None:
    """Migrazione una tantum: aggiunge le competenze di ogni classe a quelle esistenti. Idempotente."""
    if (char.settings or {}).get(SEEDED_FLAG):
        return
    edition = character_edition(char)
    rows = sorted(char.classes, key=lambda c: c.id or 0)
    known = False
    for i, row in enumerate(rows):
        key = row_class_key(row)
        if key:
            known = True
            merge_grant(char, class_proficiencies(edition, key, as_multiclass=i > 0), lang)
    if not known:
        # Classe custom o nessuna classe: fino a ieri ogni arma dava il bonus, lo conservano.
        merge_grant(char, ProficiencyGrant(weapons=("simple", "martial")), lang)
    mark_seeded(char)


def apply_feature_grants(char: Any, lang: str = "it") -> None:
    """Competenze dei privilegi attivi (es. dominio): una volta sola per privilegio, anche da seconda classe."""
    from core.rules.catalog import active_features

    done = list((char.settings or {}).get(FEATURE_GRANTS_KEY) or [])
    for spec, _row in active_features(char):
        grants = getattr(spec, "proficiency_grants", None)
        if not grants or spec.key in done:
            continue
        merge_grant(char, ProficiencyGrant(armor=tuple(grants.get("armor", ())),
                                           weapons=tuple(grants.get("weapons", ())),
                                           tools=tuple(grants.get("tools", ()))), lang)
        done.append(spec.key)
        char.settings = {**(char.settings or {}), FEATURE_GRANTS_KEY: done}

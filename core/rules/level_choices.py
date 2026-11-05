"""Scelte di livello in sospeso (ASI, Dono Epico 2024, opzioni di classe).

ASI e Doni nascono attraversando il livello e non tornano dopo la risoluzione; le opzioni di classe
si riconciliano sullo stato (attese - scelte - in sospeso), così valgono anche per personaggi
esistenti, cambi di sottoclasse o di edizione.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from core.data.classes import ASI_LEVELS, ASI_LEVELS_DEFAULT, class_table_key
from core.rules.catalog import features_for
from core.rules.edition import character_edition, class_key

RESOLVED_KEY = "resolved_choice_levels"  # settings: {class_key: ["asi:4", "epic_boon:19"]}
FREE_KNOWN_KEY = "free_known_spells"  # settings: id degli incantesimi che non contano fra i conosciuti (Segreti Magici Aggiuntivi)


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def pending_key(cls: Any) -> str:
    """`class_key` delle scelte in sospeso: nome-tabella italiano (come gli ASI) o nome libero."""
    return class_table_key(cls.class_name) or cls.class_name


def _token(c: dict) -> str:
    return f"{c.get('kind', 'asi')}:{c['level']}"


def mark_resolved(char: Any, choice: dict) -> None:
    if choice.get("kind") == "class_option":  # le opzioni si riconciliano sul conteggio
        return
    done = dict((char.settings or {}).get(RESOLVED_KEY) or {})
    done[choice["class_key"]] = sorted({*done.get(choice["class_key"], []), _token(choice)})
    char.settings = {**(char.settings or {}), RESOLVED_KEY: done}


def active_choice_specs(char: Any, cls: Any) -> list:
    """`ChoiceSpec` delle feature della classe valide per edizione e sottoclasse."""
    return [ch for spec in features_for(character_edition(char), class_key(cls))
            if spec.subclass is None or spec.subclass == cls.subclass_key
            for ch in spec.choices]


def apply_grants(char: Any, ch: Any, keys: list[str]) -> None:
    """Le opzioni scelte di una ``ChoiceSpec`` con ``grants`` sono abilità: competenza o maestria, mai una maestria che
    scende. Unico punto per la risoluzione di una scelta e per l'import."""
    if not ch.grants:
        return
    skills = dict(char.skills or {})
    for key in keys:
        if not (ch.grants == "proficient" and skills.get(key) == "expert"):
            skills[key] = "expert" if ch.grants == "expert" else True
    char.skills = skills


def sync_level_choices(char: Any, cls: Any, old_level: int, new_level: int) -> None:
    """ASI dei livelli attraversati (mai duplicati né già risolti), poi riconciliazione.

    Scendendo di livello toglie le scelte in sospeso della classe oltre il nuovo livello.
    Chiamare dopo aver aggiornato `cls.level`.
    """
    key = pending_key(cls)
    edition = character_edition(char)
    choices = [c for c in (char.pending_choices or [])
               if not (c.get("class_key") == key and c.get("level", 0) > new_level)]
    resolved = (char.settings or {}).get(RESOLVED_KEY) or {}
    done = set(resolved.get(key, [])) if isinstance(resolved, dict) else set()
    if new_level > old_level:
        for lvl in ASI_LEVELS.get(key, ASI_LEVELS_DEFAULT):
            entry = {"id": uuid.uuid4().hex, "kind": "asi", "class_key": key, "level": lvl, "created_at": _now()}
            if (old_level < lvl <= new_level and (edition == "2014" or lvl != 19) and _token(entry) not in done
                    and not any(c.get("class_key") == key and _token(c) == _token(entry) for c in choices)):
                choices.append(entry)
    char.pending_choices = choices
    reconcile_choices(char)


def seed_from_sheet(char: Any) -> None:
    """R39, personaggio esistente prima del catalogo o importato: una scelta che si deduce dalla scheda si semina con ciò
    che c'è già (le abilità con maestria riempiono Maestria, fino al limite), così non viene chiesta una seconda volta."""
    claimed: set[str] = set()
    for cls in char.classes:
        for ch in active_choice_specs(char, cls):
            if ch.grants != "expert" or (cls.options or {}).get(ch.group):
                continue
            reached = [lvl for lvl in ch.levels if lvl <= cls.level]
            limit = ch.levels[max(reached)] if reached else 0
            have = [k for k, v in (char.skills or {}).items() if v == "expert" and k not in claimed][:limit]
            if have:
                cls.options = {**(cls.options or {}), ch.group: have}
                claimed.update(have)


def reconcile_choices(char: Any, retrofit: bool = False) -> None:
    """Riporta in linea Doni Epici e opzioni di classe con lo stato attuale, potando le orfane.

    ``retrofit`` (R39): le scelte di opzioni portano ``retrofit: true``, e ammettono ciò che è già sulla scheda."""
    edition = character_edition(char)
    pending = list(char.pending_choices or [])
    resolved = (char.settings or {}).get(RESOLVED_KEY) or {}
    out = [c for c in pending if c.get("kind") not in ("class_option", "epic_boon")]
    for cls in char.classes:
        key = pending_key(cls)
        mine = [c for c in pending if c.get("class_key") == key]
        # Dono Epico: 2024, livello di classe 19+, finché non risolto
        boons = [c for c in mine if c.get("kind") == "epic_boon"]
        done = set(resolved.get(key, [])) if isinstance(resolved, dict) else set()
        if edition == "2024" and cls.level >= 19 and "epic_boon:19" not in done:
            out.extend(boons or [{"id": uuid.uuid4().hex, "kind": "epic_boon", "class_key": key,
                                  "level": 19, "created_at": _now()}])
        for ch in active_choice_specs(char, cls):
            reached = [lvl for lvl in ch.levels if lvl <= cls.level]
            needed = (ch.levels[max(reached)] if reached else 0) - len((cls.options or {}).get(ch.group, []))
            existing = [c for c in mine if c.get("kind") == "class_option" and c.get("group") == ch.group]
            if needed <= 0:
                continue
            flag = {"retrofit": True} if retrofit or any(c.get("retrofit") for c in existing) else {}
            if sum(c.get("count", 0) for c in existing) == needed:
                out.extend({**c, **flag} for c in existing)
            else:  # la scelta resta la stessa (stesso id) con meno opzioni da prendere
                out.append({"id": existing[0]["id"] if existing else uuid.uuid4().hex, "kind": "class_option", "class_key": key,
                            "level": max(reached), "group": ch.group, "count": needed, "created_at": _now(), **flag})
    char.pending_choices = out

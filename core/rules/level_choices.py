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
from core.rules.types import RuleContext

RESOLVED_KEY = "resolved_choice_levels"  # settings: {class_key: ["asi:4", "epic_boon:19"]}
TOOL_SEED_FLAG = "tool_choices_seeded"  # settings: strumenti sulla scheda già contati nelle scelte di classe (una volta)
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
    ctx = RuleContext(char=char, edition=character_edition(char), class_row=cls, class_level=cls.level)
    return [ch for spec in features_for(character_edition(char), class_key(cls))
            if (spec.subclass is None or spec.subclass == cls.subclass_key)
            # la scelta di un'opzione (Patto del Tomo) vale solo a chi ha scelto quell'opzione
            and (spec.option_group is None or spec.option_key in (cls.options or {}).get(spec.option_group, []))
            for ch in spec.choices if ch.applies is None or ch.applies(ctx)]


def apply_grants(char: Any, ch: Any, keys: list[str]) -> None:
    """Le opzioni scelte di una ``ChoiceSpec`` con ``grants`` sono abilità: competenza o maestria, mai una maestria che
    scende. Unico punto per la risoluzione di una scelta e per l'import."""
    if ch.adds_language:
        known = {str(x).strip().lower() for x in char.languages or []}
        if not ({n.lower() for n in ch.adds_language} & known):
            char.languages = [*(char.languages or []), ch.adds_language[0]]
    if not ch.grants:
        return
    if ch.grants == "language":
        known = {str(x).strip().lower() for x in char.languages or []}
        added = list(char.languages or [])
        for key in keys:
            if ch.label and ch.label(key).get("skip"):  # «nessun linguaggio»: la scelta si chiude senza aggiungere nulla
                continue
            names = ch.label(key)["name"] if ch.label else {"it": key, "en": key}
            if not ({n.lower() for n in names.values()} & known):
                added.append(names["it"])
        char.languages = added
        return
    if ch.grants == "save":
        char.saving_throws = {**(char.saving_throws or {}), **{key: True for key in keys}}
        return
    tools = [k[len("tool:"):] for k in keys if k.startswith("tool:")]
    if tools:
        from core.rules.tools import add_tools  # import locale come gli altri moduli delle regole
        add_tools(char, tools)
        if ch.grants == "expert":
            char.tool_proficiencies = {**char.tool_proficiencies, **{k: "expert" for k in tools}}
        keys = [k for k in keys if not k.startswith("tool:")]
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


def _group_totals(specs: list, level: int) -> list[tuple[Any, list[int], int]]:
    """Per gruppo: la ``ChoiceSpec`` da usare, i suoi livelli raggiunti e quante opzioni servono in tutto. Più spec dello
    stesso gruppo (una per sottoclasse: la seconda scelta di stile del Campione) valgono il massimo, non la somma."""
    best: dict[str, tuple[Any, list[int], int]] = {}
    for ch in specs:
        reached = [lvl for lvl in ch.levels if lvl <= level]
        total = ch.levels[max(reached)] if reached else 0
        if ch.group not in best or total > best[ch.group][2]:
            best[ch.group] = (ch, reached, total)
    return list(best.values())


def seed_from_sheet(char: Any, class_ids: set[int] | None = None) -> None:
    """R39, personaggio esistente prima del catalogo o importato: una scelta che si deduce dalla scheda si semina con ciò
    che c'è già (le abilità con maestria riempiono Maestria, fino al limite), così non viene chiesta una seconda volta."""
    claimed: set[str] = set()
    tools_once = not (char.settings or {}).get(TOOL_SEED_FLAG)
    taken_tools = _feat_tools(char) | {k for c in char.classes for opts in (c.options or {}).values()
                                       for k in opts if isinstance(k, str) and k.startswith("tool:")}
    for cls in char.classes:
        retro = class_ids is None or cls.id in class_ids
        for ch in active_choice_specs(char, cls):
            if (cls.options or {}).get(ch.group):
                continue
            reached = [lvl for lvl in ch.levels if lvl <= cls.level]
            limit = ch.levels[max(reached)] if reached else 0
            if ch.grants == "proficient" and ch.owned and (retro or tools_once):
                # Strumenti già sulla scheda (anche di un personaggio già passato dal catalogo, una volta sola): sono la
                # scelta, così non se ne aggiungono altri. Esclusi quelli dei talenti e delle altre scelte.
                ctx = RuleContext(char=char, edition=character_edition(char), class_row=cls, class_level=cls.level)
                have = [k for k in ch.owned(ctx) if k.startswith("tool:") and k not in taken_tools][:limit]
                if have:
                    cls.options = {**(cls.options or {}), ch.group: have}
                    taken_tools.update(have)
                continue
            if ch.grants != "expert" or not retro:
                continue
            experts = [k for k, v in (char.skills or {}).items() if v == "expert"]
            experts += [f"tool:{k}" for k in ch.expert_tools if (getattr(char, "tool_proficiencies", None) or {}).get(k) == "expert"]
            have = [k for k in experts if k not in claimed][:limit]
            if have:
                cls.options = {**(cls.options or {}), ch.group: have}
                claimed.update(have)
    if tools_once:
        char.settings = {**(char.settings or {}), TOOL_SEED_FLAG: True}


def _feat_tools(char: Any) -> set[str]:
    """Strumenti presi con un talento (``tool:<chiave>``; i nomi salvati prima del catalogo si convertono)."""
    from core.data.tools import TOOLS, tool_key
    from core.rules.catalog.feats import _abilities  # righe non caricate: nessun lazy load asincrono
    out: set[str] = set()
    for a in _abilities(char):
        if not (a.feature_key or "").startswith("feat."):
            continue
        opts = a.options or {}
        names = [*(opts.get("tools") or []), *(opts.get("instruments") or []),
                 *(p[len("tool:"):] for p in opts.get("picks") or [] if isinstance(p, str) and p.startswith("tool:"))]
        out |= {f"tool:{k}" for n in names if isinstance(n, str) and (k := n if n in TOOLS else tool_key(n))}
    return out


def reconcile_choices(char: Any, retrofit: "bool | set[int]" = False) -> None:
    """Riporta in linea Doni Epici e opzioni di classe con lo stato attuale, potando le orfane.

    ``retrofit`` (R39): le scelte di opzioni portano ``retrofit: true``, e ammettono ciò che è già sulla scheda; un
    insieme di id di classe lo limita a quelle classi."""
    edition = character_edition(char)
    pending = list(char.pending_choices or [])
    resolved = (char.settings or {}).get(RESOLVED_KEY) or {}
    # Il 19° livello è un Dono Epico nel 2024 e un ASI nel 2014: un cambio di edizione scambia la scelta in sospeso
    out = [c for c in pending if c.get("kind") not in ("class_option", "epic_boon")
           and not (edition == "2024" and c.get("kind", "asi") == "asi" and c.get("level") == 19)]
    for cls in char.classes:
        key = pending_key(cls)
        mine = [c for c in pending if c.get("class_key") == key]
        done_now = set(resolved.get(key, [])) if isinstance(resolved, dict) else set()
        # Solo lo scambio: il Dono Epico in sospeso (2024 → 2014) diventa l'ASI. Mai una scelta nuova a chi non cambia edizione
        # (personaggi 2014 importati o senza il segno `asi:19`: l'ASI non è stato guadagnato).
        if (edition == "2014" and cls.level >= 19 and 19 in ASI_LEVELS.get(key, ASI_LEVELS_DEFAULT)
                and any(c.get("class_key") == key and c.get("kind") == "epic_boon" for c in pending)
                and "asi:19" not in done_now and not any(c.get("class_key") == key and c.get("kind", "asi") == "asi" and c.get("level") == 19 for c in out)):
            out.append({"id": uuid.uuid4().hex, "kind": "asi", "class_key": key, "level": 19, "created_at": _now()})
        # Dono Epico: 2024, livello di classe 19+, finché non risolto
        boons = [c for c in mine if c.get("kind") == "epic_boon"]
        done = set(resolved.get(key, [])) if isinstance(resolved, dict) else set()
        if edition == "2024" and cls.level >= 19 and "epic_boon:19" not in done:
            out.extend(boons or [{"id": uuid.uuid4().hex, "kind": "epic_boon", "class_key": key,
                                  "level": 19, "created_at": _now()}])
        for ch, reached, total in _group_totals(active_choice_specs(char, cls), cls.level):
            needed = total - len((cls.options or {}).get(ch.group, []))
            existing = [c for c in mine if c.get("kind") == "class_option" and c.get("group") == ch.group]
            if needed <= 0:
                continue
            retro = retrofit is True or (isinstance(retrofit, set) and cls.id in retrofit)
            flag = {"retrofit": True} if retro or any(c.get("retrofit") for c in existing) else {}
            if sum(c.get("count", 0) for c in existing) == needed:
                out.extend({**c, **flag} for c in existing)
            else:  # la scelta resta la stessa (stesso id) con meno opzioni da prendere
                out.append({"id": existing[0]["id"] if existing else uuid.uuid4().hex, "kind": "class_option", "class_key": key,
                            "level": max(reached), "group": ch.group, "count": needed, "created_at": _now(), **flag})
    char.pending_choices = out

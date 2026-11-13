"""Competenze negli strumenti: ``Character.tool_proficiencies`` = ``{chiave del catalogo: True | "expert"}``.

Il vecchio testo ``general_proficiencies["tools"]`` si converte con ``migrate_tools``: gli strumenti riconosciuti vanno
nella colonna, il resto in ``other`` (niente si perde) e la lista resta vuota.
"""
from __future__ import annotations

from typing import Any, Iterable

from core.data.tools import TOOLS, tool_key


def _profs(char: Any) -> dict:
    return dict(getattr(char, "tool_proficiencies", None) or {})


def add_tools(char: Any, keys: Iterable[str]) -> None:
    """Competenza negli strumenti dati; una Maestria non scende mai."""
    profs = _profs(char)
    for k in keys:
        if k in TOOLS and profs.get(k) != "expert":
            profs[k] = True
    char.tool_proficiencies = profs  # riassegnato: la colonna JSON non traccia le mutazioni


def drop_tools(char: Any, keys: Iterable[str]) -> None:
    """Toglie le competenze date, tranne quelle con Maestria (scelta del giocatore, non della concessione)."""
    profs = _profs(char)
    for k in keys:
        if profs.get(k) is True:
            del profs[k]
    char.tool_proficiencies = profs


def add_tool_names(char: Any, names: Iterable[str]) -> None:
    """Nomi scritti: riconosciuti → colonna, sconosciuti → ``general_proficiencies["other"]`` senza doppioni."""
    from core.rules.proficiencies import normalize  # import locale: proficiencies usa questo modulo

    names = [str(n).strip() for n in names if str(n).strip()]
    keys = [k for n in names if (k := tool_key(n))]
    if keys:
        add_tools(char, keys)
    unknown = [n for n in names if not tool_key(n)]
    if unknown:
        cats = normalize(char.general_proficiencies)
        have = {x.lower() for x in cats["other"]}
        for n in unknown:
            if n.lower() not in have:
                cats["other"].append(n)
                have.add(n.lower())
        char.general_proficiencies = cats


def migrate_tools(char: Any) -> None:
    """Sposta nella colonna il testo di ``general_proficiencies["tools"]`` e gli strumenti precisi scritti in ``other``
    (idempotente: dopo restano solo voci che non sono strumenti del catalogo)."""
    from core.rules.proficiencies import normalize

    cats = normalize(char.general_proficiencies)
    in_other = [x for x in cats["other"] if tool_key(x)]
    if not cats["tools"] and not in_other:
        return
    names, cats["tools"] = [*cats["tools"], *in_other], []
    cats["other"] = [x for x in cats["other"] if not tool_key(x)]
    char.general_proficiencies = cats
    add_tool_names(char, names)


def tool_bonus(char: Any, key: str) -> int | None:
    """Bonus di competenza per una prova con lo strumento (doppio con la Maestria); ``None`` senza competenza."""
    level = _profs(char).get(key)
    if not level:
        return None
    return char.proficiency_bonus * (2 if level == "expert" else 1)

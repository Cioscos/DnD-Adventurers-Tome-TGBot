"""Nomi che stanno nell'indirizzo di una richiesta (titolo di nota, zona di mappe)."""
from __future__ import annotations

import unicodedata
from collections.abc import Collection

# Spazi «pieni» che Unicode conta come lettere o simboli: non si vedono.
_BLANK_LETTERS = "\u115f\u1160\u2800\u3164\uffa0"
# Almeno un carattere che si vede (sintassi regex di pydantic)
VISIBLE = r"[^\s\p{Cf}\p{Cc}" + _BLANK_LETTERS + "]"


def is_visible(name: str) -> bool:
    """Come ``VISIBLE``."""
    return any(not c.isspace() and unicodedata.category(c) not in ("Cf", "Cc") and c not in _BLANK_LETTERS for c in name)


def is_reachable(name: str) -> bool:
    """Vuoto non si raggiunge; «.» e «..» il browser li risolve (DELETE …/notes/.. eliminava il personaggio)."""
    return is_visible(name) and not any(part.strip() in (".", "..") for part in name.split("/"))


def reachable_name(name: str, fallback: str, taken: Collection[str] = ()) -> str:
    """Il nome, o uno raggiungibile e libero al suo posto."""
    if is_reachable(name):
        return name
    base = name.replace("/", "-") if "/" in name else fallback
    out, n = base, 2
    while out in taken:
        out, n = f"{base} ({n})", n + 1
    return out


def reachable_notes(notes: dict) -> dict:
    """Le stesse note, con i titoli irraggiungibili rinominati; l'ordine resta."""
    out: dict = {}
    for title, value in notes.items():
        out[reachable_name(title, "Nota", notes.keys() | out.keys())] = value
    return out

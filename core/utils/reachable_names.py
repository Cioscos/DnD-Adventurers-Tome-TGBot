"""Nomi che stanno nell'indirizzo di una richiesta (titolo di nota, zona di mappe)."""
from __future__ import annotations

from collections.abc import Collection


def is_reachable(name: str) -> bool:
    """Vuoto non si raggiunge; «.» e «..» il browser li risolve (DELETE …/notes/.. eliminava il personaggio)."""
    return bool(name.strip()) and not any(part.strip() in (".", "..") for part in name.split("/"))


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

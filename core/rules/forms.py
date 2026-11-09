"""Forma Selvatica per edizione: limiti per livello e circolo, PF temporanei e durata (nessun import da `api/`)."""
from __future__ import annotations

from dataclasses import dataclass

from core.rules.types import Edition

ROUNDS_PER_HOUR = 600


@dataclass(frozen=True)
class FormLimits:
    """``max_cr`` ``None``: sotto il 2° livello nessuna forma. ``known_forms`` ``None``: nessun limite (2014).
    ``temp_hp``: PF temporanei all'attivazione (2024). ``own_hp``: la forma ha PF propri (2014)."""
    max_cr: float | None
    fly: bool
    swim: bool
    known_forms: int | None
    rounds: int
    temp_hp: int
    own_hp: bool
    ac_wisdom: bool = False  # 2024, Circolo della Luna: CA minima 13 + modificatore di Saggezza
    elemental: bool = False  # 2014, Circolo della Luna dal 10°: Forma Selvatica Elementale (due usi)


def FormRules(edition: Edition, level: int, subclass_key: str | None) -> FormLimits:  # noqa: N802
    """Limiti della forma di un druido di `level` (livello da druido, non totale)."""
    moon = subclass_key == "moon"
    cr = None if level < 2 else 0.25 if level < 4 else 0.5 if level < 8 else 1
    if edition == "2014":
        if moon and cr is not None:
            cr = 1 if level < 6 else level // 3
        return FormLimits(max_cr=cr, fly=level >= 8, swim=level >= 4, known_forms=None,
                          rounds=level // 2 * ROUNDS_PER_HOUR, temp_hp=0, own_hp=True, elemental=moon and level >= 10)
    if moon and level >= 3:
        cr = level // 3
    known = None if level < 2 else 4 if level < 4 else 6 if level < 8 else 8
    return FormLimits(max_cr=cr, fly=level >= 8, swim=True, known_forms=known, rounds=level // 2 * ROUNDS_PER_HOUR,
                      temp_hp=level * (3 if moon and level >= 3 else 1), own_hp=False, ac_wisdom=moon and level >= 3)


ELEMENTALS = frozenset({"air-elemental", "earth-elemental", "fire-elemental", "water-elemental"})


def is_elemental_form(statblock: dict, srd_index: str | None) -> bool:
    """La forma è un elementale (Forma Selvatica Elementale): per tipo dello statblock o per indice dei quattro."""
    return statblock.get("type") == "elemental" or srd_index in ELEMENTALS


def elemental_violations(limits: FormLimits, statblock: dict, srd_index: str | None) -> list[str]:
    """Forma Selvatica Elementale: ``no_elemental_shape`` (non è la Luna dal 10°) o ``not_elemental_form`` (un elementale
    SRD che non è fra i quattro). Il manuale non dà limiti di GS, volo o nuoto: non se ne controlla nessuno."""
    if not limits.elemental:
        return ["no_elemental_shape"]
    if srd_index is not None and srd_index not in ELEMENTALS:
        return ["not_elemental_form"]
    return []


def form_violations(limits: FormLimits, statblock: dict) -> list[str]:
    """Quali limiti la bestia rompe: ``no_wild_shape``, ``not_beast``, ``cr``, ``fly``, ``swim``."""
    if limits.max_cr is None:
        return ["no_wild_shape"]
    speed = statblock.get("speed") or {}
    out = []
    if statblock.get("type") != "beast":
        out.append("not_beast")
    if float(statblock.get("challenge_rating") or 0) > limits.max_cr:
        out.append("cr")
    if (speed.get("fly_ft") or 0) > 0 and not limits.fly:
        out.append("fly")
    if (speed.get("swim_ft") or 0) > 0 and not limits.swim:
        out.append("swim")
    return out


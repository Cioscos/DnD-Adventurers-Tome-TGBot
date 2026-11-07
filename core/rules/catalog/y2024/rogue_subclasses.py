"""Ladro 2024, parte B (sottoclassi): Mistificatore Arcano, Assassino, Coltello dell'Anima, Furfante.

Le righe vanno in ``SUBCLASS_ROWS`` con ``subclass=`` (chiavi di ``core/rules/subclasses.py``). Dalla parte A (``rogue.py``) si riusano
``POISON`` (Assassino 13: +2d6 di veleno), ``TRIP`` (Mistificatore Arcano 13: seconda creatura), ``steady_aim_keeps_speed`` (Assassino 9:
la Mira Costante non azzera la Velocità) e ``SNEAK`` (Furfante 9: Attacco Furtivo di Nascosto).
"""
from __future__ import annotations

SUBCLASS_ROWS: tuple = ()

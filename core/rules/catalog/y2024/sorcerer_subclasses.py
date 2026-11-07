"""Sottoclassi dello Stregone 2024 (parte B): Stregoneria Aberrante, Meccanica, Draconica e Magia Selvaggia.

Le righe vanno in ``SUBCLASS_ROWS`` con ``subclass=`` (aberrant, clockwork, draconic, wild_magic). La parte A, in ``sorcerer.py``,
lascia alla parte B: ``INNATE_STATE`` (stato di Stregoneria Innata), ``SP`` (riserva dei punti), ``cast_option(...)`` e ``price(...)``
(opzioni al lancio a punti, con Apoteosi Arcana e il limite di opzioni per incantesimo già applicati) e ``innate_sorcerer_spell(ctx)``.
"""
from __future__ import annotations

SUBCLASS_ROWS: tuple = ()

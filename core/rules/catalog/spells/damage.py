"""Incantesimi in cui chi lancia sceglie il tipo di danno: la scelta arriva al tiro di danno (Sfera Cromatica, Esplosione Stregonesca...)."""
from __future__ import annotations

from core.rules.spell_effects import SpellChoice, SpellEffect, SpellTarget, SpellVariant

HOUR, MIN10, MIN1 = 600, 100, 10  # round (6 secondi)


def txt(it: str, en: str) -> dict[str, str]:
    return {"it": it, "en": en}


def _types(*types: str) -> SpellChoice:
    return SpellChoice("damage_type", txt("Tipo di danno", "Damage type"), lambda _ed: list(types))


def both(variant: SpellVariant) -> dict[str, SpellVariant]:
    return {"2014": variant, "2024": variant}


# Istantanei: nessuno stato né orologio, la scelta viaggia con la richiesta di danno
_ORB = SpellVariant(choices=(_types("acid", "cold", "lightning", "fire", "thunder", "poison"),))
_GLYPH = SpellVariant(choices=(_types("acid", "cold", "lightning", "fire", "thunder"),))
_BURST = SpellVariant(choices=(_types("acid", "cold", "fire", "lightning", "poison", "psychic", "thunder"),))

# Con durata: lo stato sul bersaglio e l'orologio di chi lancia ricordano il tipo scelto per i danni dei round dopo
_BREATH = SpellVariant(
    choices=(_types("acid", "cold", "fire", "lightning", "poison"),), track=True, concentration=True, rounds=MIN1,
    text=txt("Il bersaglio può soffiare in un Cono di 4,5 m usando la Magia: il tipo di danno è quello scelto.",
             "The target can breathe in a 15-foot Cone using the Magic action: the damage type is the chosen one."))
_ELEMENTAL = SpellVariant(  # 2024: l'elemento del Grande Spirito decide il tipo (aria fulmine, terra tuono, fuoco fuoco, acqua freddo)
    choices=(_types("lightning", "thunder", "fire", "cold"),), track=True, concentration=True, rounds=MIN10,
    text=txt("Chi entra nello Spirito o inizia lì il turno fa il TS Destrezza o subisce 8d8 del tipo dell'elemento scelto (aria fulmine, terra tuono, fuoco fuoco, acqua freddo): li applichi a mano.",
             "A creature that enters the spirit or starts its turn there makes a DEX save or takes 8d8 of the chosen element's type (air lightning, earth thunder, fire fire, water cold): apply it by hand."))

SPELLS: tuple[SpellEffect, ...] = (
    SpellEffect("chromatic_orb", ("chromatic-orb",), ("Globo Cromatico", "Sfera Cromatica", "Chromatic Orb"), SpellTarget("self"), both(_ORB)),
    SpellEffect("glyph_of_warding", ("glyph-of-warding",), ("Glifo di Interdizione", "Glyph of Warding"), SpellTarget("self"), both(_GLYPH)),
    SpellEffect("sorcerous_burst", ("sorcerous-burst",), ("Esplosione Stregonesca", "Sorcerous Burst"), SpellTarget("self"), {"2024": _BURST}),
    SpellEffect("dragons_breath", ("dragons-breath",), ("Soffio del Drago", "Dragon's Breath"), SpellTarget("ally"), {"2024": _BREATH}),
    SpellEffect("conjure_elemental", ("conjure-elemental",), ("Evoca Elementale", "Conjure Elemental"), SpellTarget("self"), {"2024": _ELEMENTAL}),
)

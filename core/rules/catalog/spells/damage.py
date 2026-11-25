"""Incantesimi in cui chi lancia sceglie il tipo di danno: la scelta arriva al tiro di danno (Sfera Cromatica, Esplosione Stregonesca...)."""
from __future__ import annotations

from dataclasses import replace

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
# Il tipo serve solo alle Rune Esplosive: un Glifo incantesimo non infligge danno e non lo chiede
_GLYPH = SpellVariant(choices=(
    SpellChoice("glyph", txt("Glifo", "Glyph"), lambda _ed: ["explosive", "spell"]),
    replace(_types("acid", "cold", "lightning", "fire", "thunder"), when=("glyph", "explosive"))))
_BURST = SpellVariant(choices=(_types("acid", "cold", "fire", "lightning", "poison", "psychic", "thunder"),))

# Con durata: lo stato sul bersaglio e l'orologio di chi lancia ricordano il tipo scelto per i danni dei round dopo
_BREATH = SpellVariant(
    choices=(_types("acid", "cold", "fire", "lightning", "poison"),), track=True, concentration=True, rounds=MIN1,
    text=txt("Il bersaglio può soffiare in un Cono di 4,5 m usando la Magia: il tipo di danno è quello scelto.",
             "The target can breathe in a 15-foot Cone using the Magic action: the damage type is the chosen one."))
_ELEMENTAL = SpellVariant(  # 2024: l'elemento del Grande Spirito decide il tipo (aria fulmine, terra tuono, fuoco fuoco, acqua freddo)
    choices=(_types("lightning", "thunder", "fire", "cold"),), track=True, concentration=True, rounds=MIN10,
    text=txt("Chi entra nello Spirito o inizia lì il turno fa il TS Destrezza o subisce 8d8 del tipo dell'elemento scelto (aria fulmine, terra tuono, fuoco fuoco, acqua freddo): li tiri dalla pagina degli incantesimi.",
             "A creature that enters the spirit or starts its turn there makes a DEX save or takes 8d8 of the chosen element's type (air lightning, earth thunder, fire fire, water cold): you roll it from the spells page."))
_GUARDIANS_2014 = SpellVariant(  # la carta dice «secondo l'allineamento»: lo sceglie chi lancia (D-031)
    choices=(_types("radiant", "necrotic"),), track=True, concentration=True, rounds=MIN10,
    text=txt("Entro 4,5 m la velocità è dimezzata e chi entra o inizia lì il turno fa il TS Saggezza o subisce 3d8 del tipo scelto (metà se riesce): li tiri dalla pagina degli incantesimi.",
             "Within 15 ft speed is halved, and a creature that enters or starts its turn there makes a WIS save or takes 3d8 of the chosen type (half on a success): you roll it from the spells page."))
_GUARDIANS_2024 = SpellVariant(  # pag. 319, come nel 2014 (D-046)
    choices=(_types("radiant", "necrotic"),), track=True, concentration=True, rounds=MIN10,
    text=txt("Entro 4,5 m la velocità è dimezzata e chi ci entra, ci finisce il turno o è raggiunto dall'area fa il TS Saggezza, una volta per turno, o subisce 3d8 del tipo scelto (metà se riesce): li tiri dalla pagina degli incantesimi.",
             "Within 15 ft speed is halved, and a creature that enters, ends its turn there or is reached by the area makes a WIS save, once per turn, or takes 3d8 of the chosen type (half on a success): you roll it from the spells page."))
_FLAME_2024 = SpellVariant(  # pag. 308: il lancio (azione bonus) accende la fiamma, scagliarla è un'azione Magia e non la spegne
    track=True, rounds=MIN10, hurled=True,
    text=txt("La fiamma fa luce intensa per 6 m e fioca per altri 6 m: finché dura la scagli con un'azione.",
             "The flame sheds bright light for 20 ft and dim light for 20 ft more: while it lasts you hurl it with an action."))
_BLADE = SpellVariant(  # 2014 pag. 247, 2024 pag. 275: il lancio (azione bonus) crea la lama, ogni attacco è un'azione con il suo tiro (D-047)
    track=True, concentration=True, rounds=MIN10, hurled=True,
    text=txt("La lama fa luce intensa per 3 m e fioca per altri 3 m: finché dura ci attacchi in mischia con un'azione, con il tiro per colpire degli incantesimi.",
             "The blade sheds bright light for 10 ft and dim light for 10 ft more: while it lasts you make a melee spell attack with it as an action."))

SPELLS: tuple[SpellEffect, ...] = (
    SpellEffect("chromatic_orb", ("chromatic-orb",), ("Globo Cromatico", "Sfera Cromatica", "Chromatic Orb"), SpellTarget("self"), both(_ORB)),
    SpellEffect("glyph_of_warding", ("glyph-of-warding",), ("Glifo di Interdizione", "Glyph of Warding"), SpellTarget("self"), both(_GLYPH)),
    SpellEffect("sorcerous_burst", ("sorcerous-burst",), ("Esplosione Stregonesca", "Sorcerous Burst"), SpellTarget("self"), {"2024": _BURST}),
    SpellEffect("dragons_breath", ("dragons-breath",), ("Soffio del Drago", "Dragon's Breath"), SpellTarget("ally"), {"2024": _BREATH}),
    SpellEffect("conjure_elemental", ("conjure-elemental",), ("Evoca Elementale", "Conjure Elemental"), SpellTarget("self"), {"2024": _ELEMENTAL}),
    SpellEffect("spirit_guardians", ("spirit-guardians",), ("Guardiani Spirituali", "Spiriti Guardiani", "Spirit Guardians"), SpellTarget("self"),
                {"2014": _GUARDIANS_2014, "2024": _GUARDIANS_2024}),
    SpellEffect("produce_flame", ("produce-flame",), ("Produrre Fiamma", "Produce Flame"), SpellTarget("self"), {"2024": _FLAME_2024}),
    SpellEffect("flame_blade", ("flame-blade",), ("Lama Infuocata", "Flame Blade"), SpellTarget("self"), both(_BLADE)),
)

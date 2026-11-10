"""Armi incantate e danni extra agli attacchi con arma (Arma Magica, Arma Elementale, Favore Divino, Manto del Crociato,
Fonte di Luce Lunare, Evoca Elementali Minori).

- Armi incantate: il lancio sceglie un'arma non magica del **bersaglio** (``choices["item_id"]``, ``weapon_choice``); i bonus valgono solo
  con quell'arma (``ctx.item``).
- Danni extra: opzioni automatiche sull'attacco (come la Punizione Divina Migliorata) o, se serve sapere dove sta il bersaglio, da confermare.
  Il tipo di danno sta in ``RollOptionSpec.extra_damage_type`` (statico): se lo sceglie il lancio c'è un'opzione per tipo, attiva per quello scelto.
- Aure (Manto del Crociato): vive, vedi ``core.rules.auras``; l'opzione arriva a ogni seduto alla serata.
"""
from __future__ import annotations

from core.rules.catalog.spells.defenses import HOUR, MIN10, both, res, txt
from core.rules.catalog.spells.movement import _described
from core.rules.spell_effects import SpellChoice, SpellEffect, SpellTarget, SpellVariant
from core.rules.types import Modifier, RollOptionSpec, RuleContext

MIN1 = 10  # round (6 secondi)
_ELEMENTS = ("acid", "cold", "fire", "lightning", "thunder")
_TYPE_CHOICE = SpellChoice("damage_type", txt("Tipo di danno", "Damage type"), lambda _ed: list(_ELEMENTS))


def _choices(ctx: RuleContext) -> dict:
    return (ctx.spell_data or {}).get("choices") or {}


def _own(ctx: RuleContext) -> bool:
    """L'attacco è del personaggio, non della bestia o del compagno."""
    return ctx.attack_mode not in ("beast", "companion")


def _weapon(ctx: RuleContext) -> bool:
    return ctx.spell is None and ctx.item is not None and _own(ctx)


def _weapon_or_unarmed(ctx: RuleContext) -> bool:
    return ctx.spell is None and _own(ctx)


def _melee_weapon_or_unarmed(ctx: RuleContext) -> bool:
    return _weapon_or_unarmed(ctx) and ctx.attack_mode not in ("ranged", "thrown")


def _chosen_item(data: dict) -> int:
    return int((data.get("choices") or {}).get("item_id") or 0)


def _with_chosen(data: dict, roll: str):
    return lambda c: c.roll == roll and c.item is not None and c.item.id == _chosen_item(data)


def _chosen_weapon(ctx: RuleContext) -> bool:
    return ctx.spell is None and ctx.item is not None and ctx.item.id == _chosen_item(ctx.spell_data or {})


def _extra(key: str, label: dict[str, str], dice, kind: str | None, available, *, automatic: bool = True) -> RollOptionSpec:
    return RollOptionSpec(key=f"spell:{key}", phase="before", rolls=("attack",), automatic=automatic, extra_dice=lambda _c, _i: dice,
                          extra_damage_type=kind, available=available, label=label,
                          effect=lambda _c, _i: txt(f"{label['it']}, già nel totale.", f"{label['en']}, already in the total."))


# --- Armi incantate -----------------------------------------------------------------------------------------------
def _magic_weapon(bonus):
    def modifiers(d: dict) -> tuple[Modifier, ...]:
        n = bonus(int(d.get("slot_level") or 2))
        return (Modifier("attack", n, when=_with_chosen(d, "attack")), Modifier("damage", n, when=_with_chosen(d, "damage")),
                Modifier("magic_weapon", 1, when=_with_chosen(d, "attack")))
    return modifiers


_MAGIC_WEAPON_TEXT = txt("L'arma scelta è magica: +1 al tiro per colpire e ai danni (+2 con slot 4°-5°, +3 dal 6°) solo con quella.",
                         "The chosen weapon is magical: +1 to attack and damage rolls (+2 with a 4th-5th level slot, +3 from 6th) with it only.")
_MAGIC_WEAPON_2014 = SpellVariant(modifiers=_magic_weapon(lambda s: 3 if s >= 6 else 2 if s >= 4 else 1), weapon_choice=True,
                                  concentration=True, rounds=HOUR, text=_MAGIC_WEAPON_TEXT)
_MAGIC_WEAPON_2024 = SpellVariant(  # niente concentrazione; +2 già dal 3°; termina se rilanci (un nuovo lancio toglie lo stato)
    modifiers=_magic_weapon(lambda s: 3 if s >= 6 else 2 if s >= 3 else 1), weapon_choice=True, rounds=HOUR,
    text=txt("L'arma scelta è magica: +1 al tiro per colpire e ai danni (+2 con slot 3°-5°, +3 dal 6°) solo con quella.",
             "The chosen weapon is magical: +1 to attack and damage rolls (+2 with a 3rd-5th level slot, +3 from 6th) with it only."))


def _elemental_n(slot: int) -> int:
    return 3 if slot >= 7 else 2 if slot >= 5 else 1


def _elemental_options(kind: str) -> RollOptionSpec:
    label = txt(f"Arma Elementale: danni extra ({kind})", f"Elemental Weapon: extra damage ({kind})")
    return RollOptionSpec(
        key=f"spell:elemental_weapon:damage:{kind}", phase="before", rolls=("attack",), automatic=True, extra_damage_type=kind,
        extra_dice=lambda c, _i: f"{_elemental_n(int((c.spell_data or {}).get('slot_level') or 3))}d4",
        available=lambda c: _chosen_weapon(c) and _choices(c).get("damage_type") == kind, label=label,
        effect=lambda _c, _i: txt("Arma Elementale: danni extra del tipo scelto, già nel totale.", "Elemental Weapon: extra damage of the chosen type, already in the total."))


_ELEMENTAL = SpellVariant(
    modifiers=lambda d: (Modifier("attack", _elemental_n(int(d.get("slot_level") or 3)), when=_with_chosen(d, "attack")),
                         Modifier("magic_weapon", 1, when=_with_chosen(d, "attack"))),
    options=tuple(_elemental_options(t) for t in _ELEMENTS), choices=(_TYPE_CHOICE,), weapon_choice=True, concentration=True, rounds=HOUR,
    text=txt("L'arma scelta è magica: +1 al tiro per colpire (+2 con slot 5°-6°, +3 dal 7°) e 1d4 danni extra del tipo scelto (2d4, 3d4) solo con quella: già nel totale.",
             "The chosen weapon is magical: +1 to attack rolls (+2 with a 5th-6th level slot, +3 from 7th) and 1d4 extra damage of the chosen type (2d4, 3d4) with it only: already in the total."))

# --- Danni extra --------------------------------------------------------------------------------------------------
_DIVINE_FAVOR_OPTION = _extra("divine_favor:damage", txt("Favore Divino: +1d4 radiosi", "Divine Favor: extra 1d4 radiant"), "1d4", "radiant", _weapon)
_DIVINE_FAVOR_2014 = SpellVariant(options=(_DIVINE_FAVOR_OPTION,), concentration=True, rounds=MIN1)
_DIVINE_FAVOR_2024 = SpellVariant(options=(_DIVINE_FAVOR_OPTION,), rounds=MIN1)  # 2024: niente concentrazione

_MANTLE_TEXT = txt("Chi è nell'aura infligge 1d4 radiosi in più con gli attacchi con arma (già nel totale).",
                   "Whoever is in the aura deals an extra 1d4 radiant damage with weapon attacks (already in the total).")
_MANTLE_2014 = SpellVariant(
    options=(_extra("crusaders_mantle:damage", txt("Manto del Crociato: +1d4 radiosi", "Crusader's Mantle: extra 1d4 radiant"), "1d4", "radiant", _weapon),),
    concentration=True, rounds=MIN1, text=_MANTLE_TEXT)
_MANTLE_2024 = SpellVariant(  # 2024: anche il Colpo Senz'Armi
    options=(_extra("crusaders_mantle:damage", txt("Manto del Crociato: +1d4 radiosi", "Crusader's Mantle: extra 1d4 radiant"), "1d4", "radiant", _weapon_or_unarmed),),
    concentration=True, rounds=MIN1, text=_MANTLE_TEXT)

_FOUNT_OF_MOONLIGHT = SpellVariant(
    modifiers=res("radiant"), concentration=True, rounds=MIN10,
    options=(_extra("fount_of_moonlight:damage", txt("Fonte di Luce Lunare: +2d6 radiosi", "Fount of Moonlight: extra 2d6 radiant"), "2d6", "radiant",
                    _melee_weapon_or_unarmed),),
    text=txt("I tuoi attacchi in mischia infliggono 2d6 radiosi in più (già nel totale). Con una reazione, dopo un danno da una creatura visibile entro 18 m, essa fa un TS Costituzione o è Accecata: lo applichi tu.",
             "Your melee attacks deal an extra 2d6 radiant damage (already in the total). As a reaction, after taking damage from a visible creature within 60 feet, it makes a CON save or is Blinded: you apply it."))


def _minor_elementals_option(kind: str) -> RollOptionSpec:
    label = txt(f"Evoca Elementali Minori: il bersaglio è nell'Emanazione? +2d8 ({kind})", f"Conjure Minor Elementals: is the target in the Emanation? Extra 2d8 ({kind})")
    return RollOptionSpec(
        key=f"spell:conjure_minor_elementals:damage:{kind}", phase="before", rolls=("attack",), extra_damage_type=kind,
        extra_dice=lambda c, _i: f"{2 + 2 * max(int((c.spell_data or {}).get('slot_level') or 4) - 4, 0)}d8",
        available=lambda c: _own(c) and _choices(c).get("damage_type") == kind, label=label,
        effect=lambda _c, _i: txt("Evoca Elementali Minori: danni extra del tipo scelto, già nel totale.", "Conjure Minor Elementals: extra damage of the chosen type, already in the total."))


_MINOR_ELEMENTALS = SpellVariant(
    options=tuple(_minor_elementals_option(t) for t in ("acid", "cold", "fire", "lightning")),
    choices=(SpellChoice("damage_type", txt("Tipo di danno", "Damage type"), lambda _ed: ["acid", "cold", "fire", "lightning"]),),
    concentration=True, rounds=MIN10,
    text=txt("Ai tuoi attacchi che colpiscono nell'Emanazione (4,5 m) l'app chiede se il bersaglio è dentro e aggiunge 2d8 del tipo scelto (+2d8 per slot oltre il 4°). Il terreno è Difficile per i nemici: lo applica il GM.",
             "On your attacks that hit in the Emanation (15 ft) the app asks whether the target is inside and adds 2d8 of the chosen type (+2d8 per slot above 4th). The ground is Difficult for enemies: the GM applies it."))

# --- Solo testo: l'effetto cambia la caratteristica, il dado o gli attacchi di un'arma e la scheda non lo modella ------------
_SHILLELAGH_2014 = _described(  # trucchetto: 1 minuto, nessuna concentrazione
    10, "Il randello o bastone che impugni diventa magico e usa la tua caratteristica da incantatore al posto della Forza per attacco e danni; il suo dado di danno è d8. "
        "Finisce se lo rilanci o lasci l'arma: lo applichi tu.",
    "The club or quarterstaff you hold becomes magical and uses your spellcasting ability instead of Strength for attack and damage rolls; its damage die is a d8. "
    "It ends if you cast it again or let go of the weapon: you apply it.")
_SHILLELAGH_2024 = _described(
    10, "Il Randello o Bastone che impugni usa la tua caratteristica da incantatore al posto della Forza per tiri per colpire e danni in mischia; "
        "il suo dado di danno diventa d8 (d10 dal 5° livello, d12 dall'11°, 2d6 dal 17°) e il danno può essere da Forza o quello normale. "
        "Finisce se lo rilanci o lasci l'arma: lo applichi tu.",
    "The Club or Quarterstaff you hold uses your spellcasting ability instead of Strength for melee attack and damage rolls; "
    "its damage die becomes a d8 (d10 from level 5, d12 from 11, 2d6 from 17) and the damage can be Force or its normal type. "
    "It ends if you cast it again or let go of the weapon: you apply it.")
_SWIFT_QUIVER = _described(
    MIN1, "La faretra produce munizioni non magiche; con l'azione bonus, a ogni tuo turno, fai due attacchi con un'arma che le usa (Frecce o Quadrelli): "
          "gli attacchi li fai e li registri tu dal Turno.",
    "The quiver produces nonmagical ammunition; as a bonus action on each of your turns you make two attacks with a weapon that uses it (arrows or bolts): "
    "you make and record the attacks yourself from the Turn.", concentration=True)

SPELLS: tuple[SpellEffect, ...] = (
    SpellEffect("magic_weapon", ("magic-weapon",), ("Arma Magica", "Magic Weapon"), SpellTarget("ally"), {"2014": _MAGIC_WEAPON_2014, "2024": _MAGIC_WEAPON_2024}),
    SpellEffect("elemental_weapon", ("elemental-weapon",), ("Arma Elementale", "Elemental Weapon"), SpellTarget("ally"), both(_ELEMENTAL)),
    SpellEffect("shillelagh", ("shillelagh",), ("Randello Incantato", "Shillelagh"), SpellTarget("self"), {"2014": _SHILLELAGH_2014, "2024": _SHILLELAGH_2024}),
    SpellEffect("swift_quiver", ("swift-quiver",), ("Faretra Rapida", "Swift Quiver"), SpellTarget("self"), both(_SWIFT_QUIVER)),
    SpellEffect("divine_favor", ("divine-favor",), ("Favore Divino", "Favore divino", "Divine Favor"), SpellTarget("self"),
                {"2014": _DIVINE_FAVOR_2014, "2024": _DIVINE_FAVOR_2024}),
    SpellEffect("crusaders_mantle", ("crusaders-mantle",), ("Manto del Crociato", "Mantello del Crociato", "Crusader's Mantle"), SpellTarget("aura"),
                {"2014": _MANTLE_2014, "2024": _MANTLE_2024}),
    SpellEffect("fount_of_moonlight", ("fount-of-moonlight",), ("Fonte di Luce Lunare", "Fount of Moonlight"), SpellTarget("self"), {"2024": _FOUNT_OF_MOONLIGHT}),
    SpellEffect("conjure_minor_elementals", ("conjure-minor-elementals",), ("Evoca Elementali Minori", "Conjure Minor Elementals"),
                SpellTarget("self"), {"2024": _MINOR_ELEMENTALS}),
)

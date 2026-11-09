"""Incantesimi di difesa: resistenze, immunità, vantaggi ai tiri salvezza e condizioni imposte (Pelle di Pietra, Aura di Purezza, Invisibilità...)."""
from __future__ import annotations

from core.data.damage_types import DAMAGE_TYPES
from core.rules.spell_effects import SpellChoice, SpellEffect, SpellTarget, SpellVariant, roll
from core.rules.types import Modifier, RollOptionSpec, RuleContext

SAVES = ("save", "death_save", "concentration")
D20 = (*SAVES, "attack", "skill", "ability", "initiative")
PHYSICAL = ("bludgeoning", "piercing", "slashing")
ENERGY = ("acid", "cold", "fire", "lightning", "thunder")  # Protezione dall'Energia
MIN10, HOUR, DAY = 100, 600, 14400  # durate in round (6 secondi)


def txt(it: str, en: str) -> dict[str, str]:
    return {"it": it, "en": en}


def res(*types: str):
    return lambda d: tuple(Modifier(f"resistance:{t}", 1) for t in types)


def adv(when) -> Modifier:
    return Modifier("advantage", 1, when=when)


def both(variant: SpellVariant) -> dict[str, SpellVariant]:
    return {"2014": variant, "2024": variant}


def confirm_save(spell: str, label: dict[str, str]) -> RollOptionSpec:
    """Vantaggio al TS solo contro ciò che l'app non vede (una condizione, un incantesimo): lo conferma il giocatore al tiro."""
    return RollOptionSpec(key=f"spell:{spell}:save", phase="before", rolls=("save",), mode="advantage", label=label)


def confirm_physical(key: str, label: dict[str, str]) -> RollOptionSpec:
    """Resistenza ai soli colpi fisici «non magici» / «da arma»: l'app non lo vede, la applica il giocatore confermando (come Avatar della Battaglia)."""
    return RollOptionSpec(key=key, phase="damage_in", rolls=("damage_taken",), multiplier=0.5, label=label,
                          available=lambda c: c.damage_type in PHYSICAL)


# --- Resistenze ---------------------------------------------------------------------------------------------------
_STONESKIN_2014 = SpellVariant(
    options=(confirm_physical("spell:stoneskin:nonmagical", txt("Pelle di Pietra: il colpo è di un'arma non magica?",
                                                                "Stoneskin: is the hit from a nonmagical weapon?")),),
    concentration=True, rounds=HOUR,
    text=txt("Resistenza ai danni contundenti, perforanti e taglienti non magici: conferma al danno che il colpo non è magico.",
             "Resistance to non-magical bludgeoning, piercing and slashing: confirm on the damage that the hit is not magical."))
_STONESKIN_2024 = SpellVariant(modifiers=res(*PHYSICAL), concentration=True, rounds=HOUR)

_AURA_LIFE = SpellVariant(
    modifiers=res("necrotic"), concentration=True, rounds=MIN10,
    turn_heal=lambda d, c: 1 if c.current_hit_points == 0 and not c.is_dead else 0,  # a 0 PF recupera 1 PF a inizio turno
    text=txt("PF massimi non riducibili: lo applica il GM. A 0 PF recuperi 1 PF a inizio turno (automatico).",
             "Hit point maximum can't be reduced: the GM applies it. At 0 HP you regain 1 HP at the start of your turn (automatic)."))

_PURITY_OPTION = confirm_save("aura_of_purity", txt(
    "Aura di Purezza: il TS è contro accecato, affascinato, assordato, avvelenato, paralizzato, spaventato o stordito?",
    "Aura of Purity: is the save against blinded, charmed, deafened, poisoned, paralyzed, frightened or stunned?"))
_AURA_PURITY_2014 = SpellVariant(
    modifiers=res("poison"), options=(_PURITY_OPTION,), concentration=True, rounds=MIN10,
    text=txt("Chi è nell'aura non può ammalarsi: lo applica il GM.", "Creatures in the aura can't be diseased: the GM applies it."))
_AURA_PURITY_2024 = SpellVariant(modifiers=res("poison"), options=(_PURITY_OPTION,), concentration=True, rounds=MIN10)

# Interdizione alle Lame 2014 (la 2024 sta in dice.py): resistenza fino alla fine del turno successivo
BLADE_WARD_2014 = SpellVariant(
    options=(confirm_physical("spell:blade_ward:weapon", txt("Interdizione alle Lame: è il danno di un attacco con arma?",
                                                             "Blade Ward: is it the damage of a weapon attack?")),),
    rounds=1,
    text=txt("Resistenza ai danni degli attacchi con armi fino alla fine del tuo turno successivo: conferma al danno che viene da un attacco con arma.",
             "Resistance to weapon attack damage until the end of your next turn: confirm on the damage that it comes from a weapon attack."))

_FIRE_SHIELD = SpellVariant(
    modifiers=lambda d: (Modifier(f"resistance:{'cold' if (d.get('choices') or {}).get('shield') == 'warm' else 'fire'}", 1),),
    choices=(SpellChoice("shield", txt("Scudo", "Shield"), lambda _ed: ["warm", "cold"]),),
    rounds=MIN10,
    retaliation=lambda d, _temp: txt(
        f"Scudo di Fuoco: se il colpo era in mischia entro 1,5 m, chi ti ha colpito subisce 2d8 danni da {'fuoco' if (d.get('choices') or {}).get('shield') == 'warm' else 'freddo'}.",
        f"Fire Shield: if the hit was a melee attack within 5 ft, the attacker takes 2d8 {'fire' if (d.get('choices') or {}).get('shield') == 'warm' else 'cold'} damage."),
    text=txt("Chi ti colpisce in mischia entro 1,5 m subisce 2d8 danni (fuoco con lo scudo caldo, freddo con quello freddo): a ogni danno subito l'app te lo ricorda, li applica il GM.",
             "A creature that hits you in melee within 5 ft takes 2d8 damage (fire with the warm shield, cold with the cold one): on every damage you take the app reminds you, the GM applies it."))

_FEIGN_DEATH = SpellVariant(
    condition="incapacitated", immune_conditions=("poisoned",), rounds=HOUR,
    modifiers=lambda d: (Modifier("speed_zero", 1), *(Modifier(f"resistance:{t}", 1) for t in DAMAGE_TYPES if t != "psychic")),
    text=txt("Appare morto a ogni ispezione ed è anche accecato (non segnato sulla scheda). Il veleno non ha effetto finché dura.",
             "Appears dead to any inspection and is also blinded (not marked on the sheet). Poison has no effect while it lasts."))

_PROT_ENERGY = SpellVariant(
    modifiers=lambda d: (Modifier(f"resistance:{(d.get('choices') or {}).get('damage_type')}", 1),),
    choices=(SpellChoice("damage_type", txt("Tipo di danno", "Damage type"), lambda _ed: list(ENERGY)),),
    concentration=True, rounds=HOUR)

_POISON_OPTION = confirm_save("protection_from_poison", txt("Protezione dai Veleni: il TS è contro avvelenato?",
                                                           "Protection from Poison: is the save against being poisoned?"))


def _cure_poisoned(target, _data) -> None:
    if (target.conditions or {}).get("poisoned"):
        target.conditions = {**target.conditions, "poisoned": False}


_PROT_POISON_2014 = SpellVariant(
    modifiers=res("poison"), options=(_POISON_OPTION,), rounds=HOUR,
    text=txt("Neutralizza subito un veleno sul bersaglio: lo applica il GM.", "Neutralizes one poison on the target right away: the GM applies it."))
_PROT_POISON_2024 = SpellVariant(modifiers=res("poison"), options=(_POISON_OPTION,), rounds=HOUR, on_apply=_cure_poisoned)

_FOUNT_OF_MOONLIGHT = SpellVariant(
    modifiers=res("radiant"), concentration=True, rounds=MIN10,
    text=txt("I tuoi attacchi in mischia infliggono 2d6 radiosi extra; con una reazione acceca chi ti ha danneggiato (TS Costituzione): li applichi a mano.",
             "Your melee attacks deal 2d6 extra radiant damage; as a reaction you blind a creature that damaged you (CON save): apply them by hand."))


def _reduces(ctx: RuleContext) -> bool:
    return ctx.damage_type == ((ctx.spell_data or {}).get("choices") or {}).get("damage_type")


# 2024: il primo danno del tipo scelto in ogni turno scende di 1d4
RESISTANCE_2024 = SpellVariant(
    options=(RollOptionSpec(
        key="spell:resistance:reduce", phase="damage_in", rolls=("damage_taken",), once_per_turn=True,
        extra_dice=lambda _c, _i: "1d4", available=_reduces,
        label=txt("Resistenza: riduci il danno di 1d4", "Resistance: reduce the damage by 1d4")),),
    choices=(SpellChoice("damage_type", txt("Tipo di danno", "Damage type"),
                         lambda _ed: [t for t in DAMAGE_TYPES if t not in ("force", "psychic")]),),
    concentration=True, rounds=10)

# --- Vantaggi -----------------------------------------------------------------------------------------------------
_BEACON = SpellVariant(
    modifiers=lambda d: (adv(lambda c: (c.roll == "save" and c.ability == "wisdom") or c.roll == "death_save"),),
    concentration=True, rounds=10,
    text=txt("Ogni cura che ricevi dà il massimo dei PF: lo applica chi cura.", "Every healing you receive gives the maximum: the healer applies it."))

_BLUR = SpellVariant(
    track=True, concentration=True, rounds=10,
    text=txt("Ogni creatura ha svantaggio ai tiri per colpire contro di te (non chi non si affida alla vista): lo applica il GM agli attaccanti.",
             "Every creature has disadvantage on attack rolls against you (not those who don't rely on sight): the GM applies it to the attackers."))

_FORESIGHT_2014 = SpellVariant(
    modifiers=lambda d: (adv(lambda c: c.roll in D20),), rounds=DAY // 3,
    text=txt("Non puoi essere sorpreso; gli attaccanti hanno svantaggio contro di te: lo applica il GM.",
             "You can't be surprised; attackers have disadvantage against you: the GM applies it."))
_FORESIGHT_2024 = SpellVariant(
    modifiers=lambda d: (adv(lambda c: c.roll in D20),), rounds=DAY // 3,
    text=txt("Gli altri hanno svantaggio ai tiri per colpire contro di te: lo applica il GM.",
             "Others have disadvantage on attack rolls against you: the GM applies it."))

_HOLY_AURA = SpellVariant(
    modifiers=lambda d: (adv(lambda c: c.roll in SAVES),), concentration=True, rounds=10,
    text=txt("Gli altri hanno svantaggio ai tiri per colpire contro di te; un immondo o non morto che ti colpisce in mischia fa un TS Costituzione o è accecato: lo applica il GM.",
             "Others have disadvantage on attack rolls against you; a fiend or undead that hits you in melee makes a CON save or is blinded: the GM applies it."))

_PROT_EVIL = SpellVariant(
    options=(confirm_save("protection_from_evil_and_good", txt(
        "Protezione dal Bene e dal Male: il TS è contro un effetto di quelle creature (affascinato, spaventato, posseduto)?",
        "Protection from Evil and Good: is the save against an effect from those creatures (charmed, frightened, possessed)?")),),
    concentration=True, rounds=MIN10,
    text=txt("Aberrazioni, celestiali, elementali, folletti, immondi e non morti hanno svantaggio ai tiri per colpire contro di te e non possono affascinarti, spaventarti o possederti: lo applica il GM.",
             "Aberrations, celestials, elementals, fey, fiends and undead have disadvantage on attack rolls against you and can't charm, frighten or possess you: the GM applies it."))

_CIRCLE_OF_POWER = SpellVariant(
    options=(confirm_save("circle_of_power", txt("Cerchio di Potere: il TS è contro un incantesimo o un effetto magico?",
                                                 "Circle of Power: is the save against a spell or magical effect?")),),
    concentration=True, rounds=MIN10,
    text=txt("Se un TS per metà danni riesce, non subisci danni: lo applica il GM.", "If a save for half damage succeeds, you take no damage: the GM applies it."))

_DISPEL_EVIL = SpellVariant(
    track=True, concentration=True, rounds=10,
    text=txt("Celestiali, elementali, folletti, immondi e non morti hanno svantaggio ai tiri per colpire contro di te; puoi chiudere l'incantesimo con Congedo o Spezzare Incantesimo.",
             "Celestials, elementals, fey, fiends and undead have disadvantage on attack rolls against you; you can end it with Dismissal or Break Enchantment."))

# --- Condizioni e immunità ----------------------------------------------------------------------------------------
_INVISIBILITY_2014 = SpellVariant(
    condition="invisible", ends_on=("attack", "cast", "manual"), concentration=True, rounds=HOUR,
    text=txt("Finisce per il bersaglio se attacca o lancia un incantesimo.", "It ends for the target if it attacks or casts a spell."))
_INVISIBILITY_2024 = SpellVariant(
    condition="invisible", ends_on=("attack", "cast", "manual"), concentration=True, rounds=HOUR,
    text=txt("Finisce per il bersaglio se attacca, infligge danni o lancia un incantesimo: se infligge danni senza attaccare, chiudi tu lo stato.",
             "It ends for the target if it attacks, deals damage or casts a spell: if it deals damage without attacking, end the state yourself."))
_GREATER_INVISIBILITY = SpellVariant(condition="invisible", concentration=True, rounds=10)

_HEROISM = SpellVariant(
    immune_conditions=("frightened",), track=True, concentration=True, rounds=10,
    turn_temp_hp=lambda d: max(0, d.get("cast_mod", 0)),  # il modificatore da incantatore di chi lancia, fissato al lancio
    text=txt("A inizio di ogni tuo turno ottieni PF temporanei pari al modificatore da incantatore di chi ha lanciato (automatico).",
             "At the start of each of your turns you gain temporary HP equal to the caster's spellcasting modifier (automatic)."))
_MIND_BLANK = SpellVariant(
    modifiers=lambda d: (Modifier("immunity:psychic", 1),), immune_conditions=("charmed",), rounds=DAY,
    text=txt("Immune anche a ciò che percepisce emozioni o legge i pensieri e alle divinazioni: lo applica il GM.",
             "Also immune to anything that senses emotions or reads thoughts, and to divination: the GM applies it."))
_FEAST_TEXT = txt("Cura le malattie: lo applica il GM. I PF massimi e attuali +2d10 sono automatici.",
                  "Cures disease: the GM applies it. Hit point maximum and current +2d10 are automatic.")


def _feast_hp(d: dict) -> tuple[Modifier, ...]:
    return (Modifier("hp_max", d.get("feast_hp", 0)),)


_FEAST_HP = dict(per_target=lambda d: {"feast_hp": roll(2, 10)}, heal=lambda d: d.get("feast_hp", 0))
_FEAST_2014 = SpellVariant(
    modifiers=lambda d: (Modifier("immunity:poison", 1), adv(lambda c: c.roll == "save" and c.ability == "wisdom"), *_feast_hp(d)),
    immune_conditions=("frightened", "poisoned"), rounds=DAY, text=_FEAST_TEXT, **_FEAST_HP)
_FEAST_2024 = SpellVariant(modifiers=lambda d: (Modifier("resistance:poison", 1), *_feast_hp(d)),
                           immune_conditions=("frightened", "poisoned"), rounds=DAY, text=_FEAST_TEXT, **_FEAST_HP)

_AURA = SpellTarget("aura", lambda slot: 20)

SPELLS: tuple[SpellEffect, ...] = (
    SpellEffect("stoneskin", ("stoneskin",), ("Pelle di Pietra", "Stoneskin"), SpellTarget("ally"),
                {"2014": _STONESKIN_2014, "2024": _STONESKIN_2024}),
    SpellEffect("aura_of_life", ("aura-of-life",), ("Aura di Vita", "Aura of Life"), _AURA, both(_AURA_LIFE)),
    SpellEffect("aura_of_purity", ("aura-of-purity",), ("Aura di Purezza", "Aura of Purity"), _AURA,
                {"2014": _AURA_PURITY_2014, "2024": _AURA_PURITY_2024}),
    SpellEffect("fire_shield", ("fire-shield",), ("Scudo di Fuoco", "Fire Shield"), SpellTarget("self"), both(_FIRE_SHIELD)),
    SpellEffect("feign_death", ("feign-death",), ("Morte Apparente", "Feign Death"), SpellTarget("ally"), both(_FEIGN_DEATH)),
    SpellEffect("protection_from_energy", ("protection-from-energy",), ("Protezione dall'Energia", "Protection from Energy"),
                SpellTarget("ally"), both(_PROT_ENERGY)),
    SpellEffect("protection_from_poison", ("protection-from-poison",), ("Protezione dai Veleni", "Protezione dal Veleno", "Protection from Poison"),
                SpellTarget("ally"), {"2014": _PROT_POISON_2014, "2024": _PROT_POISON_2024}),
    SpellEffect("fount_of_moonlight", ("fount-of-moonlight",), ("Fonte di Luce Lunare", "Fount of Moonlight"),
                SpellTarget("self"), {"2024": _FOUNT_OF_MOONLIGHT}),
    SpellEffect("beacon_of_hope", ("beacon-of-hope",), ("Faro di Speranza", "Beacon of Hope"),
                SpellTarget("allies", lambda slot: 20), both(_BEACON)),
    SpellEffect("blur", ("blur",), ("Sfocatura", "Blur"), SpellTarget("self"), both(_BLUR)),
    SpellEffect("foresight", ("foresight",), ("Previsione", "Preveggenza", "Foresight"), SpellTarget("ally"),
                {"2014": _FORESIGHT_2014, "2024": _FORESIGHT_2024}),
    SpellEffect("holy_aura", ("holy-aura",), ("Aura Sacra", "Holy Aura"), _AURA, both(_HOLY_AURA)),
    SpellEffect("protection_from_evil_and_good", ("protection-from-evil-and-good",),
                ("Protezione dal Bene e dal Male", "Protezione dal Male e dal Bene", "Protection from Evil and Good"),
                SpellTarget("ally"), both(_PROT_EVIL)),
    SpellEffect("circle_of_power", ("circle-of-power",), ("Cerchio di Potere", "Circle of Power"), _AURA, both(_CIRCLE_OF_POWER)),
    SpellEffect("dispel_evil_and_good", ("dispel-evil-and-good",), ("Dissolvi il Bene e il Male", "Dispel Evil and Good"),
                SpellTarget("self"), both(_DISPEL_EVIL)),
    SpellEffect("invisibility", ("invisibility",), ("Invisibilità", "Invisibility"),
                SpellTarget("allies", lambda slot: max(slot - 1, 1)), {"2014": _INVISIBILITY_2014, "2024": _INVISIBILITY_2024}),
    SpellEffect("greater_invisibility", ("greater-invisibility",), ("Invisibilità Superiore", "Greater Invisibility"),
                SpellTarget("ally"), both(_GREATER_INVISIBILITY)),
    SpellEffect("heroism", ("heroism",), ("Eroismo", "Heroism"), SpellTarget("allies", lambda slot: max(slot, 1)), both(_HEROISM)),
    SpellEffect("mind_blank", ("mind-blank",), ("Vuoto Mentale", "Mente Vuota", "Mind Blank"), SpellTarget("ally"), both(_MIND_BLANK)),
    SpellEffect("heroes_feast", ("heroes-feast",), ("Banchetto degli Eroi", "Heroes' Feast"),
                SpellTarget("allies", lambda slot: 12), {"2014": _FEAST_2014, "2024": _FEAST_2024}),
)

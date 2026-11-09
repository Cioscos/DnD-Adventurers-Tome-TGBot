"""Incantesimi sui punti ferita: PF temporanei, CA impostata, Interdizione alla Morte, Legame di Protezione, rigenerazione."""
from __future__ import annotations

from core.game.stats import effective_ability_mod
from core.rules.catalog.spells.defenses import HOUR, both, txt
from core.rules.spell_effects import SpellEffect, SpellTarget, SpellVariant, roll
from core.rules.types import Cost, Modifier, RollOptionSpec

EIGHT_HOURS = 4800


# --- CA impostata -------------------------------------------------------------------------------------------------
# Armatura Magica: CA base 13 + Des solo senza armatura (lo verifica ``ac_delta``); indossare un'armatura la chiude (``end_unarmored_spells``).
_MAGE_ARMOR = SpellVariant(
    modifiers=lambda d: (Modifier("ac_base", lambda ctx: 13 + effective_ability_mod(ctx.char, "dexterity")),), rounds=EIGHT_HOURS,
    text=txt("CA base 13 + Destrezza: l'incantesimo termina se il bersaglio indossa un'armatura (l'app lo chiude da sola).",
             "Base AC 13 + Dexterity: the spell ends if the target puts on armor (the app ends it for you)."))
# Pelle Coriacea: CA totale minima, qualunque armatura si indossi (2014 16 con concentrazione; 2024 17 senza)
_BARKSKIN_2014 = SpellVariant(modifiers=lambda d: (Modifier("ac_min", 16),), concentration=True, rounds=HOUR)
_BARKSKIN_2024 = SpellVariant(modifiers=lambda d: (Modifier("ac_min", 17),), rounds=HOUR)

# --- PF temporanei -------------------------------------------------------------------------------------------------
_HIGHER = lambda d: 5 * max(d.get("slot_level", 1) - 1, 0)  # noqa: E731  +5 per livello oltre il 1°


def _agathys_note(d: dict, had_temp: bool) -> dict[str, str] | None:
    if not had_temp:
        return None
    n = 5 * max(d.get("slot_level", 1), 1)
    return txt(f"Armatura di Agathys: se il colpo era in mischia, chi ti ha colpito subisce {n} danni da freddo.",
               f"Armor of Agathys: if the hit was a melee attack, the attacker takes {n} cold damage.")


def _agathys(ends_at_zero: bool) -> SpellVariant:
    return SpellVariant(
        temp_hp=lambda d: 5 * max(d.get("slot_level", 1), 1), track=True, rounds=HOUR, ends_at_zero_temp=ends_at_zero,
        retaliation=_agathys_note,
        text=txt("5 PF temporanei (+5 per livello oltre il 1°): chi ti colpisce in mischia finché li hai subisce 5 danni da freddo (+5 per livello), "
                 "l'app te lo ricorda a ogni danno." + (" Finisce quando i PF temporanei sono esauriti." if ends_at_zero else ""),
                 "5 temporary HP (+5 per level above 1st): a creature that hits you in melee while you have them takes 5 cold damage (+5 per level), "
                 "the app reminds you on every damage." + (" It ends when the temporary HP are gone." if ends_at_zero else "")))


# Vita Falsata: istantanea nel 2024; nel 2014 dura un'ora ma i PF temporanei sono solo quelli tirati (nessuno stato)
_FALSE_LIFE_2014 = SpellVariant(temp_hp=lambda d: roll(1, 4, 4) + _HIGHER(d))
_FALSE_LIFE_2024 = SpellVariant(temp_hp=lambda d: roll(2, 4, 4) + _HIGHER(d))
# Parola del Potere: Fortificare: 120 PF temporanei divisi in parti uguali (la ripartizione a scelta non c'è)
_FORTIFY = SpellVariant(
    temp_hp=lambda d: 120 // max(d.get("targets", 1), 1),
    text=txt("120 PF temporanei divisi in parti uguali fra i bersagli: per una ripartizione diversa correggi i PF temporanei a mano.",
             "120 temporary HP split equally among the targets: for a different split, edit the temporary HP by hand."))

# --- Interdizione alla Morte -----------------------------------------------------------------------------------------
# Il manuale (2014 e 2024) non esclude il danno massiccio: ciò che porta a 0 PF lascia a 1 PF e l'incantesimo finisce.
DEATH_WARD_HOLD = "spell:death_ward:hold"
_DEATH_WARD_OPTION = RollOptionSpec(
    key=DEATH_WARD_HOLD, phase="damage_in", rolls=("damage_taken",), holds_at_one=True, holds_vs_massive=True,
    cost=Cost(state_key="spell:death_ward"),
    label=txt("Interdizione alla Morte: se il colpo ti porta a 0 PF resti a 1 PF", "Death Ward: if the hit takes you to 0 HP you stay at 1 HP"))
_DEATH_WARD = SpellVariant(
    options=(_DEATH_WARD_OPTION,), rounds=EIGHT_HOURS,
    text=txt("La prima volta che scendi a 0 PF resti a 1 PF e l'incantesimo finisce (lo applica l'app da sola al danno). Un effetto che uccide all'istante senza danni "
             "viene annullato dal GM, e l'incantesimo finisce.",
             "The first time you would drop to 0 HP you stay at 1 HP and the spell ends (the app applies it by itself on the damage). An effect that kills outright without "
             "damage is negated by the GM, and the spell ends."))

# --- Legame di Protezione --------------------------------------------------------------------------------------------
_WARDING_BOND = SpellVariant(
    modifiers=lambda d: (Modifier("ac", 1), Modifier("save", 1), Modifier("resistance:all", 1)),
    shares_damage=True, clock_ends_on=("unconscious",), rounds=HOUR,
    text=txt("Chi lancia subisce lo stesso danno del bersaglio (l'app lo scrive sulla sua scheda) e l'incantesimo finisce se scende a 0 PF. "
             "La distanza (18 m) la controlla il GM.",
             "The caster takes the same damage as the target (the app writes it on their sheet) and the spell ends if they drop to 0 HP. "
             "The GM checks the distance (60 ft)."))

# --- Rigenerazione e cure nel tempo -----------------------------------------------------------------------------------
_REGENERATE = SpellVariant(
    heal=lambda d: roll(4, 8, 15), turn_heal=lambda d, c: 1, rounds=HOUR,
    text=txt("4d8+15 PF subito e 1 PF a inizio di ogni tuo turno (automatici). Gli arti recisi ricrescono in 2 minuti: lo applica il GM.",
             "4d8+15 HP now and 1 HP at the start of each of your turns (automatic). Severed limbs regrow in 2 minutes: the GM applies it."))
_VITALITY_TEXT = txt("2d6 PF a una creatura nell'aura: usa «Cura» sulla scheda del beneficiario (2014 con un'azione bonus a ogni tuo turno; "
                     "2024 alla creazione e a inizio di ogni tuo turno).",
                     "2d6 HP to a creature in the aura: use Heal on the recipient's sheet (2014 with a bonus action on each of your turns; "
                     "2024 on casting and at the start of each of your turns).")
_AURA_VITALITY = SpellVariant(track=True, concentration=True, rounds=10, text=_VITALITY_TEXT)

SPELLS: tuple[SpellEffect, ...] = (
    SpellEffect("mage_armor", ("mage-armor",), ("Armatura Magica", "Mage Armor"), SpellTarget("ally"), both(_MAGE_ARMOR)),
    SpellEffect("barkskin", ("barkskin",), ("Pelle Coriacea", "Pelle d'Albero", "Barkskin"), SpellTarget("ally"),
                {"2014": _BARKSKIN_2014, "2024": _BARKSKIN_2024}),
    SpellEffect("armor_of_agathys", ("armor-of-agathys",), ("Armatura di Agathys", "Armor of Agathys"), SpellTarget("self"),
                {"2014": _agathys(False), "2024": _agathys(True)}),
    SpellEffect("false_life", ("false-life",), ("Vita Falsata", "Falsa Vita", "False Life"), SpellTarget("self"),
                {"2014": _FALSE_LIFE_2014, "2024": _FALSE_LIFE_2024}),
    SpellEffect("power_word_fortify", ("power-word-fortify",), ("Parola del Potere: Fortificare", "Power Word Fortify"),
                SpellTarget("allies", lambda slot: 6), {"2024": _FORTIFY}),
    SpellEffect("death_ward", ("death-ward",), ("Interdizione alla Morte", "Death Ward"), SpellTarget("ally"), both(_DEATH_WARD)),
    SpellEffect("warding_bond", ("warding-bond",), ("Vincolo di Interdizione", "Legame di Protezione", "Warding Bond"),
                SpellTarget("ally"), both(_WARDING_BOND)),
    SpellEffect("regenerate", ("regenerate",), ("Rigenerazione", "Regenerate"), SpellTarget("ally"), both(_REGENERATE)),
    SpellEffect("aura_of_vitality", ("aura-of-vitality",), ("Aura di Vitalità", "Aura of Vitality"), SpellTarget("self"), both(_AURA_VITALITY)),
)

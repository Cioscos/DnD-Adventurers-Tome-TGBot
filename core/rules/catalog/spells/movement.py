"""Incantesimi di movimento, sensi e tratti: Volare, Velocità, Saltare, Scurovisione, Potenziamento Caratteristica..."""
from __future__ import annotations

from dataclasses import replace

from core.rules.catalog.spells.defenses import DAY, HOUR, MIN10, adv, both, txt
from core.rules.spell_effects import SpellChoice, SpellEffect, SpellTarget, SpellVariant
from core.rules.types import Modifier
from core.rules.weapons import ability_score

_ABILITIES = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]


def _described(rounds: int, it: str, en: str, *, concentration: bool = False) -> SpellVariant:
    """Effetto che la scheda non modella: lo stato resta visibile (e la concentrazione tracciata), il testo dice cosa fa."""
    return SpellVariant(track=True, rounds=rounds, concentration=concentration, text=txt(it, en))


_FLY = SpellVariant(modifiers=lambda d: (Modifier("fly_speed_value", 60),), concentration=True, rounds=MIN10,
                    text=txt("Cade alla fine se è ancora in aria.", "It falls at the end if still in the air."))

_HASTE = SpellVariant(
    modifiers=lambda d: (Modifier("ac", 2), Modifier("speed", lambda ctx: ctx.char.speed),
                         adv(lambda c: c.roll == "save" and c.ability == "dexterity")),
    concentration=True, rounds=10,
    text=txt("Azione extra (un attacco, Scatto, Disimpegno, Nascondersi o Usare un Oggetto). Alla fine non può muoversi né agire fino alla fine del turno successivo: lo applica il GM.",
             "Extra action (one attack, Dash, Disengage, Hide or Use an Object). When it ends it can't move or act until the end of its next turn: the GM applies it."))
_HASTE_2024 = replace(_HASTE, text=txt(
    "Azione extra (solo un attacco, Scatto, Disimpegno, Nascondersi o Utilizzare). Alla fine il bersaglio è Incapacitato e ha Velocità 0 fino alla fine del suo turno successivo: lo applica il GM.",
    "Extra action (only one attack, Dash, Disengage, Hide or Utilize). When it ends the target is Incapacitated with Speed 0 until the end of its next turn: the GM applies it."))

_JUMP_2014 = SpellVariant(  # distanza triplicata: +2 volte il salto base (punteggio di Forza in piedi); un solo bersaglio, senza scalata
    modifiers=lambda d: (Modifier("jump_bonus", lambda ctx: 2 * ability_score(ctx.char, "strength")),), rounds=10,
    max_targets=lambda slot: 1,
    text=txt("La distanza dei salti è triplicata: la scheda triplica il salto in lungo, il salto in alto lo triplichi tu.",
             "Jump distance is tripled: the sheet triples the long jump, you triple the high jump yourself."))
_JUMP_2024 = _described(10, "Una volta per turno puoi saltare fino a 9 m spendendo 3 m di movimento.",
                        "Once per turn you can jump up to 30 ft by spending 10 ft of movement.")

_FREEDOM_2014 = _described(
    HOUR, "Ignori il terreno difficile; la velocità non si riduce e la magia non ti paralizza né ti trattiene. Sott'acqua nessuna penalità a movimento e attacchi.",
    "You ignore difficult terrain; your speed can't be reduced and magic can't paralyze or restrain you. No penalty to movement and attacks underwater.")
_FREEDOM_2014 = replace(_FREEDOM_2014, max_targets=lambda slot: 1)  # il 2014 non scala
_FREEDOM_2024 = SpellVariant(
    modifiers=lambda d: (Modifier("swim_speed", 1),), rounds=HOUR,
    text=txt("Ignori il terreno difficile; effetti magici non riducono la velocità né ti paralizzano o trattengono.",
             "You ignore difficult terrain; magical effects can't reduce your speed or paralyze or restrain you."))


def _enhance(d: dict) -> tuple[Modifier, ...]:
    ability = (d.get("choices") or {}).get("ability")
    out = [adv(lambda c: (c.roll in ("skill", "ability") and c.ability == ability) or (c.roll == "initiative" and ability == "dexterity"))]
    if ability == "strength" and d.get("edition") != "2024":
        out.append(Modifier("carry_double", 1))
    return tuple(out)


_ENHANCE_CHOICE = (SpellChoice("ability", txt("Caratteristica", "Ability"), lambda _ed: list(_ABILITIES)),)
_ENHANCE_2014 = SpellVariant(
    modifiers=_enhance, choices=_ENHANCE_CHOICE, concentration=True, rounds=HOUR,
    text=txt("Costituzione: 2d6 PF temporanei (tirali tu). Destrezza: niente danni da caduta fino a 6 m. Forza: capacità di carico doppia (già applicata).",
             "Constitution: 2d6 temporary HP (roll them). Dexterity: no fall damage up to 20 ft. Strength: double carrying capacity (already applied)."))
_ENHANCE_2024 = SpellVariant(
    modifiers=_enhance, choices=_ENHANCE_CHOICE, concentration=True, rounds=HOUR,
    text=txt("Ogni bersaglio riceve la stessa caratteristica; se ognuno ne sceglie una diversa, le altre le applica il GM (un nuovo lancio toglie l'effetto ai bersagli precedenti).",
             "Every target gets the same ability; if each picks a different one, the GM applies the others (casting again removes the effect from the previous targets)."))

_DARKVISION_2014 = SpellVariant(modifiers=lambda d: (Modifier("sense:darkvision", 60),), rounds=DAY // 3)
_DARKVISION_2024 = SpellVariant(modifiers=lambda d: (Modifier("sense:darkvision", 150),), rounds=DAY // 3)
_TRUE_SEEING = SpellVariant(modifiers=lambda d: (Modifier("sense:truesight", 120),), rounds=HOUR)
_SEE_INVISIBILITY = _described(HOUR, "Vedi le creature e gli oggetti invisibili come se fossero visibili, e il Piano Etereo (spettrale).",
                               "You see invisible creatures and objects as if visible, and the Ethereal Plane (ghostly).")
_LEVITATE = _described(MIN10, "Sale di 6 m e resta sospeso; si muove solo spingendosi contro superfici fisse. Alla fine scende lentamente.",
                       "Rises 20 ft and hovers; it moves only by pushing against fixed surfaces. It descends slowly at the end.", concentration=True)
_WATER_BREATHING = _described(DAY, "Respira sott'acqua mantenendo la respirazione normale.", "Breathes underwater while keeping normal breathing.")
_WATER_WALK = _described(HOUR, "Cammina su qualsiasi liquido come su suolo solido.", "Walks on any liquid as if it were solid ground.")
_FEATHER_FALL = _described(10, "Discesa rallentata a 18 m per round e nessun danno da caduta se atterra durante la durata.",
                           "Descends at 60 ft per round and takes no fall damage if it lands during the duration.")

SPELLS: tuple[SpellEffect, ...] = (
    SpellEffect("fly", ("fly",), ("Volare", "Fly"), SpellTarget("allies", lambda slot: max(slot - 2, 1)), both(_FLY)),
    SpellEffect("haste", ("haste",), ("Velocità", "Haste"), SpellTarget("ally"), {"2014": _HASTE, "2024": _HASTE_2024}),
    SpellEffect("jump", ("jump",), ("Saltare", "Jump"), SpellTarget("allies", lambda slot: max(slot, 1)),
                {"2014": _JUMP_2014, "2024": _JUMP_2024}),
    SpellEffect("freedom_of_movement", ("freedom-of-movement",), ("Libertà di Movimento", "Freedom of Movement"),
                SpellTarget("allies", lambda slot: max(slot - 3, 1)), {"2014": _FREEDOM_2014, "2024": _FREEDOM_2024}),
    SpellEffect("enhance_ability", ("enhance-ability",), ("Caratteristica Potenziata", "Potenziamento caratteristica", "Enhance Ability"),
                SpellTarget("allies", lambda slot: max(slot - 1, 1)), {"2014": _ENHANCE_2014, "2024": _ENHANCE_2024}),
    SpellEffect("darkvision", ("darkvision",), ("Scurovisione", "Darkvision"), SpellTarget("ally"),
                {"2014": _DARKVISION_2014, "2024": _DARKVISION_2024}),
    SpellEffect("true_seeing", ("true-seeing",), ("Visione del Vero", "True Seeing"), SpellTarget("ally"), both(_TRUE_SEEING)),
    SpellEffect("see_invisibility", ("see-invisibility",), ("Vedere Invisibilità", "See Invisibility"), SpellTarget("self"),
                both(_SEE_INVISIBILITY)),
    SpellEffect("levitate", ("levitate",), ("Levitazione", "Levitate"), SpellTarget("ally"), both(_LEVITATE)),
    SpellEffect("water_breathing", ("water-breathing",), ("Respirare sott'Acqua", "Water Breathing"),
                SpellTarget("allies", lambda slot: 10), both(_WATER_BREATHING)),
    SpellEffect("water_walk", ("water-walk",), ("Camminare sull'Acqua", "Water Walk"),
                SpellTarget("allies", lambda slot: 10), both(_WATER_WALK)),
    SpellEffect("feather_fall", ("feather-fall",), ("Caduta Morbida", "Feather Fall"),
                SpellTarget("allies", lambda slot: 5), both(_FEATHER_FALL)),
)

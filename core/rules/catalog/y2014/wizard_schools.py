"""Le otto scuole del Mago 2014 (Tradizione Arcana). Valori dalla scheda ``docs/superpowers/rules/2014/classes/wizard.md``.

Ogni scuola ha il suo «Sapiente» (tempo e costo della copia nel libro dimezzati, vedi ``core/rules/spellbook.py``). Ciò che si
fa al lancio di un incantesimo della scuola sta in ``core/rules/school_hooks.py`` (interdizione, finestre, ricariche).
"""
from __future__ import annotations

from typing import Any

from core.rules import arcane_ward
from core.rules.catalog._common import feature
from core.rules.catalog.y2014.wizard_common import CK, ED, dc as _dc, mod as _mod, say as _say, savant as _savant
from core.rules.schools import WINDOW_ENCHANTMENT, normalize_school
from core.rules.states import has_state
from core.rules.types import Modifier, OnUse, RollOptionSpec, RuleContext, TargetEffect, UseText



# ---------------------------------------------------------------------------
# Scuola di Abiurazione
# ---------------------------------------------------------------------------

def _ward_up(ctx: RuleContext) -> bool:
    ward = arcane_ward.ward_state(ctx.char)
    return ward is not None and int((ward.get("data") or {}).get("hp") or 0) > 0


def _projected_damage(params: dict) -> int | None:
    text = str(params.get("damage") or "").strip()
    return int(text) if text.isdigit() and int(text) > 0 else None


def _project(ctx: RuleContext, params: dict) -> None:
    arcane_ward.absorb(ctx.char, _projected_damage(params) or 0)


def _projected_message(ctx: RuleContext, params: dict) -> dict[str, str]:
    """Calcolato prima dell'effetto: i PF dell'interdizione sono ancora quelli di adesso."""
    damage = _projected_damage(params) or 0
    hp = int(((arcane_ward.ward_state(ctx.char) or {}).get("data") or {}).get("hp") or 0)
    taken, rest = min(hp, damage), max(0, damage - hp)
    return {"it": f"L'interdizione assorbe {taken} danni. La creatura subisce i restanti {rest}.",
            "en": f"The ward absorbs {taken} damage. The creature takes the remaining {rest}."}


PROJECTED_USE = OnUse(
    cost=0, slot="reaction", available=_ward_up, check=lambda _c, p: None if _projected_damage(p) else (422, "invalid_text"),
    texts=(UseText("damage", {"it": "Danni subiti dalla creatura", "en": "Damage the creature takes"}, max_len=6),),
    effect=_project, message=_projected_message)

# La prova di controincantesimo o dissolvi magie: la competenza si somma anche a chi non la ha nell'Intelligenza
IMPROVED_ABJURATION = RollOptionSpec(
    key=f"{CK}.improved_abjuration", phase="before", rolls=("ability",),
    available=lambda c: c.ability == "intelligence" and (c.char.turn_state or {}).get("last_cast_spell") in ("counterspell", "dispel-magic"),
    bonus=lambda c, _i: c.char.proficiency_bonus,
    label={"it": "Abiurazione Migliorata: la prova è per controincantesimo o dissolvi magie? Aggiungi la competenza",
           "en": "Improved Abjuration: is the check for counterspell or dispel magic? Add your proficiency bonus"})

SPELL_RESISTANCE_SAVE = RollOptionSpec(
    key=f"{CK}.spell_resistance", phase="before", rolls=("save",), mode="advantage",
    label={"it": "Resistenza agli Incantesimi: il tiro salvezza è contro un incantesimo? Vantaggio",
           "en": "Spell Resistance: is the saving throw against a spell? Advantage"})
SPELL_RESISTANCE_DAMAGE = RollOptionSpec(
    key=f"{CK}.spell_resistance_damage", phase="damage_in", rolls=("damage_taken",), grants_resistance=True,
    label={"it": "Resistenza agli Incantesimi: il danno è di un incantesimo? Resistenza",
           "en": "Spell Resistance: is the damage from a spell? Resistance"})

ABJURATION = (
    _savant("abjuration"),
    feature("arcane_ward", CK, ED, 2, "Interdizione Arcana / Arcane Ward (Abiurazione 2, pag. 85)",
            ("Interdizione Arcana", "Arcane Ward"),
            ("Lanciando un'abiurazione di 1° livello o più crei un'interdizione di 2 x livello da mago + Int PF: assorbe i danni al posto tuo. Ogni abiurazione la ricarica di 2 x livello dell'incantesimo.",
             "Casting an abjuration of 1st level or higher creates a ward of 2 x wizard level + Int HP that takes damage for you. Each abjuration recharges it by 2 x the spell's level."),
            subclass="abjuration"),
    feature("projected_ward", CK, ED, 6, "Interdizione Proiettata / Projected Ward (Abiurazione 6, pag. 85)",
            ("Interdizione Proiettata", "Projected Ward"),
            ("Reazione: quando una creatura entro 9 m subisce danni, la tua interdizione ne assorbe quanto può; il resto lo subisce la creatura.",
             "Reaction: when a creature within 30 ft takes damage, your ward absorbs what it can; the creature takes the rest."),
            "reaction", subclass="abjuration", on_use=PROJECTED_USE),
    feature("improved_abjuration", CK, ED, 10, "Abiurazione Migliorata / Improved Abjuration (Abiurazione 10, pag. 85)",
            ("Abiurazione Migliorata", "Improved Abjuration"),
            ("Alla prova di Intelligenza di controincantesimo o dissolvi magie aggiungi il bonus di competenza.",
             "Add your proficiency bonus to the Intelligence check of counterspell or dispel magic."),
            subclass="abjuration", roll_options=(IMPROVED_ABJURATION,)),
    feature("spell_resistance", CK, ED, 14, "Resistenza agli Incantesimi / Spell Resistance (Abiurazione 14, pag. 85)",
            ("Resistenza agli Incantesimi", "Spell Resistance"),
            ("Vantaggio ai tiri salvezza contro gli incantesimi e resistenza ai danni degli incantesimi.",
             "Advantage on saving throws against spells and resistance to spell damage."),
            subclass="abjuration", roll_options=(SPELL_RESISTANCE_SAVE, SPELL_RESISTANCE_DAMAGE)),
)

# ---------------------------------------------------------------------------
# Scuola di Ammaliamento
# ---------------------------------------------------------------------------

def _till_my_next_turn() -> dict:
    return {"anchor": "source", "edge": "end", "count": 1}


GAZE_USE = OnUse(
    cost=0, slot="action",
    target_effect=lambda ctx, _p: TargetEffect(
        condition="charmed", also=("incapacitated",), save_ability="wisdom", save_dc=_dc(ctx), ends_at=_till_my_next_turn(), extends=True,
        immune_on_success=True, note="hypnotic_gaze"))
CHARM_USE = OnUse(
    cost=0, slot="reaction",
    target_effect=lambda ctx, _p: TargetEffect(
        condition="custom:instinctive_charm", save_ability="wisdom", save_dc=_dc(ctx), rounds=1, immune_on_success=True,
        note="instinctive_charm"))


def _forgotten_hours(ctx: RuleContext) -> int:
    return max(1, 1 + _mod(ctx, "charisma"))


MEMORIES_USE = OnUse(
    cost=0, slot="action", available=lambda c: has_state(c.char, WINDOW_ENCHANTMENT),
    ends_state=WINDOW_ENCHANTMENT,  # una volta per incantesimo
    target_effect=lambda ctx, _p: TargetEffect(
        condition="custom:altered_memory", save_ability="intelligence", save_dc=_dc(ctx), note="altered_memory"),
    message=lambda ctx, _p: {"it": f"Se il TS fallisce, la creatura dimentica fino a {_forgotten_hours(ctx)} ore del tempo passato affascinata.",
                             "en": f"If the save fails, the creature forgets up to {_forgotten_hours(ctx)} hours of the time it spent charmed."})

SPLIT_ENCHANTMENT = RollOptionSpec(
    key=f"{CK}.split_enchantment", phase="before", rolls=("cast",),
    available=lambda c: c.spell is not None and c.spell.level >= 1 and normalize_school(c.spell.school) == "enchantment",
    label={"it": "Ammaliamento Condiviso: l'incantesimo ha un solo bersaglio? Ne puoi scegliere un secondo",
           "en": "Split Enchantment: does the spell target only one creature? You can pick a second one"},
    effect=_say("Una seconda creatura entro gittata è bersaglio dell'incantesimo, con lo stesso effetto.",
                "A second creature in range is also a target of the spell, with the same effect."))

ENCHANTMENT = (
    _savant("enchantment"),
    feature("hypnotic_gaze", CK, ED, 2, "Sguardo Ipnotico / Hypnotic Gaze (Ammaliamento 2, pag. 85)",
            ("Sguardo Ipnotico", "Hypnotic Gaze"),
            ("Azione: una creatura entro 1,5 m che ti vede o sente fa un TS Saggezza o è affascinata e incapacitata, a velocità 0, fino alla fine del tuo prossimo turno. Rinnovabile con un'azione.",
             "Action: a creature within 5 ft that can see or hear you makes a Wisdom save or is charmed and incapacitated, speed 0, until the end of your next turn. Renew with an action."),
            "action", subclass="enchantment", on_use=GAZE_USE),
    feature("instinctive_charm", CK, ED, 6, "Fascino Istintivo / Instinctive Charm (Ammaliamento 6, pag. 85)",
            ("Fascino Istintivo", "Instinctive Charm"),
            ("Reazione: una creatura entro 9 m che ti attacca fa un TS Saggezza; se fallisce attacca un'altra creatura. Chi supera il TS è immune fino al tuo riposo lungo.",
             "Reaction: a creature within 30 ft attacking you makes a Wisdom save; on a failure it attacks another creature. On a success it is immune until your long rest."),
            "reaction", subclass="enchantment", on_use=CHARM_USE),
    feature("split_enchantment", CK, ED, 10, "Ammaliamento Condiviso / Split Enchantment (Ammaliamento 10, pag. 85)",
            ("Ammaliamento Condiviso", "Split Enchantment"),
            ("Lanciando un ammaliamento di 1° livello o più su una sola creatura puoi bersagliarne anche una seconda.",
             "When you cast an enchantment of 1st level or higher that targets one creature, you can target a second one."),
            subclass="enchantment", roll_options=(SPLIT_ENCHANTMENT,)),
    feature("alter_memories", CK, ED, 14, "Alterare Ricordi / Alter Memories (Ammaliamento 14, pag. 85)",
            ("Alterare Ricordi", "Alter Memories"),
            ("Dopo un ammaliamento: azione per far dimenticare 1 + Carisma ore (min. 1) del tempo affascinato; TS Intelligenza, una volta per incantesimo.",
             "After an enchantment: an action to make a creature forget 1 + Charisma hours (min. 1) of the time it spent charmed; Intelligence save, once per spell."),
            "action", subclass="enchantment", on_use=MEMORIES_USE),
)

FEATURES = (*ABJURATION, *ENCHANTMENT)

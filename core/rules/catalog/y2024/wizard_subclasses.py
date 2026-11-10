"""Sottoclassi del Mago 2024 (parte B): Abiuratore, Divinatore, Invocatore e Illusionista (``subclass=`` abjurer, diviner, evoker,
illusionist).

Valori dalla scheda ``docs/superpowers/rules/2024/classes/wizard.md``; i testi sono nostri, mai quelli del manuale. Le chiavi sono
quelle delle scuole del 2014 quando il privilegio è lo stesso (interdizione, Portento, Terzo Occhio, Saturazione...): i ganci al
lancio di ``core/rules/school_hooks.py`` e gli stati (``arcane_ward``, ``overchannel``) valgono quindi per entrambe le edizioni.
I Sapienti sono scelte di incantesimi per il libro (``ChoiceSpec.spell_school``): due al 3° livello, uno per ogni nuovo livello di
slot. Non importa ``wizard.py`` (che importa questo modulo in fondo).
"""
from __future__ import annotations

from typing import Any

from core.rules import arcane_ward
from core.rules.catalog._common import feature
from core.rules.catalog.y2014.wizard import _no_options
from core.rules.catalog.y2014.wizard_common import mod as _mod
from core.rules.catalog.y2014.wizard_schools import PROJECTED_USE, SPELL_RESISTANCE_DAMAGE, SPELL_RESISTANCE_SAVE
from core.rules.catalog.y2014.wizard_schools_b import EXPERT_DIVINATION, PORTENT, _third_eye
from core.rules.catalog.y2014.wizard_schools_c import OVERCHANNEL_OPTION, _empowered, _evocation_save, _object_text
from core.rules.schools import WINDOW_ILLUSION_TURN, normalize_school
from core.rules.states import has_state
from core.rules.types import (
    ChoiceSpec, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, Uses, UseChoice, UseToggle,
)

ED, CK = "2024", "wizard"
P = f"{CK}."
SAVANT_LEVELS = {3: 2, 5: 3, 7: 4, 9: 5, 11: 6, 13: 7, 15: 8, 17: 9}  # due al 3°, poi uno a ogni nuovo livello di slot


def _highest_slot_level(char: Any) -> int:
    """Il livello di slot più alto della tabella multiclasse (non solo da mago): quanti incantesimi vale il Sapiente."""
    from core.rules.edition import character_edition  # import locale: spellcasting importa il catalogo
    from core.rules.spellcasting import slots_for
    return max((lvl for lvl, total in slots_for(character_edition(char), char.classes).regular.items() if total > 0), default=0)


def _both(it: str, en: str) -> dict[str, str]:
    return {"it": it, "en": en}


def _sub(label: str, subclass: str):
    """Fabbrica delle righe di una sottoclasse: il titolo è quello della scheda."""
    def make(key: str, level: int, it: str, en: str, page: int, summary: tuple[str, str], action_type: str | None = None, **kw: Any):
        return feature(key, CK, ED, level, f"{it} / {en} ({label} {level}, pag. {page})", (it, en), summary, action_type, subclass=subclass, **kw)
    return make


def _savant(make, school: str, it: str, en: str, page: int, school_it: str, school_en: str):
    return make(f"{school}_savant", 3, it, en, page,
                (f"Due incantesimi da mago di {school_it} (max 2° livello) gratis nel libro, poi uno per ogni nuovo livello di slot.",
                 f"Two wizard {school_en} spells (up to 2nd level) free in the book, then one for each new slot level."),
                passive=True,
                choices=(ChoiceSpec(group=f"{school}_savant", levels=SAVANT_LEVELS, options=_no_options, spell_pick="book",
                                    spell_list="wizard", spell_school=school, total_by=_highest_slot_level),))


def _slot_levels(minimum: int):
    def options(ctx: RuleContext) -> list[str]:
        return [str(level) for level in sorted({s.level for s in ctx.char.spell_slots or [] if s.level >= minimum and s.available > 0})]
    return options


def _slot_label(level: str) -> dict[str, str]:
    return _both(f"Slot di {level}° livello", f"Level {level} slot")


# ---------------------------------------------------------------------------
# Abiuratore
# ---------------------------------------------------------------------------

def _ward_exists(ctx: RuleContext) -> bool:
    return arcane_ward.ward_state(ctx.char) is not None


def _recharge_ward(ctx: RuleContext, params: dict) -> None:
    """Azione bonus: lo slot speso ridà alla protezione 2 x il suo livello, entro il massimo (la protezione c'è già)."""
    arcane_ward.on_abjuration(ctx.char, ctx.class_row, int(params["slot_level"]), lambda _hp, _max: None)


WARD_RECHARGE = OnUse(
    cost=0, slot="bonus", available=_ward_exists, spends_slot="slot_level", effect=_recharge_ward,
    choices=(UseChoice("slot_level", _both("Slot da spendere", "Slot to spend"), _slot_levels(1), _slot_label),),
    message=lambda _c, p: _both(f"La protezione recupera {2 * int(p['slot_level'])} PF, fino al massimo.",
                                f"The ward regains {2 * int(p['slot_level'])} HP, up to its maximum."))

_COUNTER_OR_DISPEL = ("counterspell", "dispel-magic")
SPELL_BREAKER_CHECK = RollOptionSpec(
    key=f"{P}spell_breaker_check", phase="before", rolls=("ability",),
    available=lambda c: c.ability == "intelligence" and (c.char.turn_state or {}).get("last_cast_spell") == "dispel-magic",
    bonus=lambda c, _i: c.char.proficiency_bonus,
    label=_both("Rompi-Incantesimi: la prova è per Dissolvi Magie? Aggiungi la competenza",
                "Spell Breaker: is the check for Dispel Magic? Add your proficiency bonus"))


def _breaker_cast(ctx: RuleContext) -> dict | None:
    """L'ultimo lancio del turno con slot, se è Controincantesimo o Dissolvi Magie."""
    last = (ctx.char.turn_state or {}).get("last_slot_cast")
    return last if last and last.get("spell") in _COUNTER_OR_DISPEL else None


def _give_slot_back(ctx: RuleContext, _params: dict) -> None:
    """Il bersaglio non è stato fermato: lo slot del lancio (già speso) torna disponibile, una sola volta."""
    last = _breaker_cast(ctx)
    slots = [s for s in ctx.char.spell_slots if s.level == last["level"] and s.used > 0 and bool(s.is_pact) == last["pact"]]
    if slots:
        slots[0].used -= 1
    turn = dict(ctx.char.turn_state or {})
    turn.pop("last_slot_cast", None)
    ctx.char.turn_state = turn


SPELL_BREAKER_USE = OnUse(cost=0, available=lambda c: _breaker_cast(c) is not None, effect=_give_slot_back)

_ABJ = _sub("Abiuratore", "abjurer")
ABJURER = (
    _savant(_ABJ, "abjuration", "Abiurazione Sapiente", "Abjuration Savant", 172, "abiurazione", "Abjuration"),
    _ABJ("arcane_ward", 3, "Interdizione Arcana", "Arcane Ward", 172,
         ("Lanciando un'abiurazione con slot crei una protezione di 2 x livello da mago + Int PF che assorbe i danni; ogni abiurazione la ricarica.",
          "Casting an abjuration with a slot creates a ward of 2 x wizard level + Int HP that absorbs damage; each abjuration recharges it."),
         "bonus_action", on_use=WARD_RECHARGE),
    _ABJ("projected_ward", 6, "Interdizione Proiettata", "Projected Ward", 172,
         ("Reazione: quando una creatura che vedi entro 9 m subisce danni, la tua protezione ne assorbe quanto può; il resto lo subisce lei.",
          "Reaction: when a creature you see within 30 ft takes damage, your ward absorbs what it can; the creature takes the rest."),
         "reaction", on_use=PROJECTED_USE),
    _ABJ("spell_breaker", 10, "Rompi-Incantesimi", "Spell Breaker", 173,
         ("Controincantesimo e Dissolvi Magie sono sempre preparati; Dissolvi Magie è un'azione bonus con competenza alla prova; slot reso se fallisce.",
          "Counterspell and Dispel Magic are always prepared; Dispel Magic is a bonus action with proficiency on the check; after the cast, give the slot back if it failed."),
         granted_spells=_COUNTER_OR_DISPEL, bonus_cast_spells=("dispel-magic",), roll_options=(SPELL_BREAKER_CHECK,),
         on_use=SPELL_BREAKER_USE),
    _ABJ("spell_resistance", 14, "Resistenza agli Incantesimi", "Spell Resistance", 173,
         ("Vantaggio ai tiri salvezza contro gli incantesimi e resistenza ai danni degli incantesimi.",
          "Advantage on saving throws against spells and resistance to spell damage."),
         roll_options=(SPELL_RESISTANCE_SAVE, SPELL_RESISTANCE_DAMAGE)),
)

# ---------------------------------------------------------------------------
# Divinatore
# ---------------------------------------------------------------------------

THIRD_EYE_OPTIONS = {"darkvision": ("Scurovisione", "Darkvision"), "greater_comprehension": ("Comprensione Superiore", "Greater Comprehension"),
                     "see_invisibility": ("Vedere Invisibilità", "See Invisibility")}


def _third_eye_state(_ctx: RuleContext, params: dict) -> StateSpec:
    """Dura fino all'inizio di un riposo. Vedere Invisibilità autorizza il lancio senza slot finché dura (``free_cast``)."""
    data: dict = {"option": params["option"]}
    if params["option"] == "see_invisibility":
        data |= {"free_cast": "see-invisibility", "free_cast_keep": True}
    return StateSpec("third_eye", ends_on=("rest_short", "rest_long", "manual"), data=data)


THIRD_EYE_USE = OnUse(
    slot="bonus", state=_third_eye_state,
    choices=(UseChoice("option", _both("Beneficio", "Benefit"), lambda _c: list(THIRD_EYE_OPTIONS),
                       lambda k: _both(*THIRD_EYE_OPTIONS[k])),))


def _option_row(make, key: str, it: str, en: str, summary: tuple[str, str], **kw: Any):
    return make(key, 10, it, en, 173, summary, no_row=True, covered_by="UseChoice option di Terzo Occhio (OnUse) di questa classe", **kw)


_DIV = _sub("Divinatore", "diviner")
DIVINER = (
    _savant(_DIV, "divination", "Divinazione Sapiente", "Divination Savant", 173, "divinazione", "Divination"),
    _DIV("portent", 3, "Portento", "Portent", 173,
         ("A fine riposo lungo tiri 2d20 (3 dal 14°) e li registri: ognuno può sostituire un Test d20, una volta per turno.",
          "At the end of a long rest you roll 2d20 (3 from 14th) and record them: each can replace a D20 Test, once per turn."),
         roll_options=(PORTENT,), long_rest_dice=(f"{P}portent", lambda c: 3 if c.class_level >= 14 else 2)),
    _DIV("expert_divination", 6, "Divinazione Esperta", "Expert Divination", 173,
         ("Lanciando una divinazione con slot di 2° livello o più recuperi uno slot speso di livello inferiore, al massimo di 5°.",
          "Casting a divination with a slot of 2nd level or higher you regain a spent slot of a lower level, 5th at most."),
         roll_options=(EXPERT_DIVINATION,)),
    _DIV("third_eye", 10, "Terzo Occhio", "The Third Eye", 173,
         ("Azione bonus: scegli Scurovisione 36 m, Comprensione Superiore o Vedere Invisibilità fino all'inizio di un riposo. Un uso, riposo breve o lungo.",
          "Bonus action: pick Darkvision 120 ft, Greater Comprehension or See Invisibility until you start a rest. One use, short or long rest."),
         "bonus_action", uses=Uses(table={10: 1}), restoration="short_rest", on_use=THIRD_EYE_USE, granted_spells=("see-invisibility",),  # sempre disponibile, non scritto nel libro
         modifiers=(Modifier("sense:darkvision", 120, when=_third_eye("darkvision"), source=f"feature:{P}third_eye"),)),
    _option_row(_DIV, "darkvision", "Scurovisione", "Darkvision",
                ("Opzione di Terzo Occhio: scurovisione entro 36 m.", "Third Eye option: darkvision out to 120 ft.")),
    _option_row(_DIV, "greater_comprehension", "Comprensione Superiore", "Greater Comprehension",
                ("Opzione di Terzo Occhio: leggi qualsiasi lingua.", "Third Eye option: you read any language.")),
    _option_row(_DIV, "see_invisibility", "Vedere Invisibilità", "See Invisibility",
                ("Opzione di Terzo Occhio: lanci Vedere Invisibilità senza slot.", "Third Eye option: you cast See Invisibility with no slot.")),
    _DIV("greater_portent", 14, "Portento Superiore", "Greater Portent", 173,
         ("Portento registra tre d20 invece di due.", "Portent records three d20s instead of two."), passive=True),
)

# ---------------------------------------------------------------------------
# Invocatore
# ---------------------------------------------------------------------------

def _sculpt_effect(ctx: RuleContext, _inputs: dict) -> dict[str, str]:
    n = 1 + (ctx.casting_level or ctx.spell.level)
    return _both(f"Scegli fino a {n} creature che vedi: superano da sole il TS e non subiscono danni.",
                 f"Choose up to {n} creatures you can see: they automatically pass the save and take no damage.")


SCULPT_SPELLS = RollOptionSpec(
    key=f"{P}sculpt_spells", phase="before", rolls=("cast",), effect=_sculpt_effect,
    available=_evocation_save,
    label=_both("Plasmare Incantesimi: proteggi alcune creature visibili dall'incantesimo",
                "Sculpt Spells: shield some visible creatures from the spell"))

_EVO = _sub("Invocatore", "evoker")
EVOKER = (
    _savant(_EVO, "evocation", "Invocazione Sapiente", "Evocation Savant", 174, "invocazione", "Evocation"),
    _EVO("potent_cantrip", 3, "Trucchetto Potente", "Potent Cantrip", 174,
         ("Un trucchetto di danno il cui bersaglio supera il TS, o il cui attacco manca, infligge comunque metà danni, senza altri effetti.",
          "A damaging cantrip whose target passes the save, or whose attack misses, still deals half damage, with no other effect."),
         passive=True, save_half_cantrips=True, cantrip_half_on_miss=True),
    _EVO("sculpt_spells", 6, "Plasmare Incantesimi", "Sculpt Spells", 174,
         ("Lanciando un'invocazione scegli 1 + livello dell'incantesimo creature visibili: superano il TS e non subiscono danni.",
          "When you cast an evocation you pick 1 + the spell's level visible creatures: they pass the save and take no damage."),
         roll_options=(SCULPT_SPELLS,)),
    _EVO("empowered_evocation", 10, "Invocazione Potente", "Empowered Evocation", 174,
         ("Aggiungi il modificatore di Intelligenza a un tiro di danno di un tuo incantesimo da mago di invocazione.",
          "Add your Intelligence modifier to one damage roll of a wizard evocation spell you cast."),
         modifiers=(Modifier("damage", lambda c: _mod(c, "intelligence"), when=_empowered, source=f"feature:{P}empowered_evocation"),)),
    _EVO("overchannel", 14, "Saturazione Magica", "Overchannel", 174,
         ("Un incantesimo da mago di 1°-5° livello infligge il massimo. Dal secondo uso fra riposi lunghi subisci 2d12 necrotici per livello (+1d12 a uso).",
          "A wizard spell of 1st-5th level deals maximum damage. From the second use between long rests you take 2d12 necrotic per level (+1d12 each use)."),
         roll_options=(OVERCHANNEL_OPTION,)),
)

# ---------------------------------------------------------------------------
# Illusionista
# ---------------------------------------------------------------------------

def _self_check(_ctx: RuleContext, params: dict) -> tuple[int, str] | None:
    return (422, "invalid_choice") if params.get("restore") and params.get("slot_level") is None else None


ILLUSORY_SELF_USE = OnUse(
    slot="reaction", spends_slot="slot_level", spends_slot_when=lambda _c, p: bool(p.get("restore")),
    cost_by=lambda _c, p: 0 if p.get("restore") else 1, check=_self_check,
    toggles=(UseToggle("restore", _both("Ripristina spendendo uno slot di 2° livello o superiore (nessuna azione)",
                                        "Restore by spending a level 2 or higher slot (no action)")),),
    choices=(UseChoice("slot_level", _both("Slot da spendere per ripristinare", "Slot to spend to restore"), _slot_levels(2), _slot_label,
                       optional=True),))

REALITY_USE = OnUse(
    cost=0, slot="bonus", available=lambda c: has_state(c.char, WINDOW_ILLUSION_TURN), ends_state=WINDOW_ILLUSION_TURN, texts=_object_text(),
    state=lambda _c, p: StateSpec("illusory_reality", rounds=10, ends_on=("manual",), data={"object": str(p["object"]).strip()}))


def _knew_minor_illusion(ctx: RuleContext) -> bool:
    """Illusione Minore c'era già fra gli incantesimi prima che il privilegio la concedesse (relazione non caricata: no)."""
    from core.rules.feature_sync import GRANTED_CREATED  # import locale: feature_sync importa il catalogo
    spells = ctx.char.__dict__.get("spells") or []
    return any(s.srd_index == "minor-illusion" for s in spells) and "minor-illusion" not in ((ctx.char.settings or {}).get(GRANTED_CREATED) or [])


def _phantasmal(key: str, spell: str, it: str, en: str):
    half = RollOptionSpec(
        key=f"{P}{key}_half_hp", phase="before", rolls=("cast",), available=lambda c: c.slotless and c.spell is not None and c.spell.srd_index == spell,
        effect=lambda _c, _i: _both("La creatura evocata ha la metà dei Punti Ferita: riferiscilo al GM.", "The summoned creature has half its Hit Points: tell the GM."),
        label=_both(f"Creature Fantasmatiche: {it} senza slot, la creatura ha metà dei PF", f"Phantasmal Creatures: {en} with no slot, the creature has half HP"))
    return _ILL(key, 6, "Creature Fantasmatiche", "Phantasmal Creatures", 175,
                (f"{it} è sempre preparato e di scuola Illusione: una volta per riposo lungo lo lanci senza slot, con la creatura a PF dimezzati.",
                 f"{en} is always prepared and of the Illusion school: once per long rest cast it with no slot, the creature has half HP."),
                granted_spells=(spell,), free_spell=spell, uses=Uses(table={6: 1}), restoration="long_rest",
                school_as=("illusion", (spell,)), roll_options=(half,))


_ILL = _sub("Illusionista", "illusionist")
ILLUSIONIST = (
    _savant(_ILL, "illusion", "Illusione Sapiente", "Illusion Savant", 175, "illusione", "Illusion"),
    _ILL("improved_illusions", 3, "Illusioni Migliorate", "Improved Illusions", 175,
         ("Illusione senza componenti Verbali e +18 m di gittata (da 3 m in su); impari Illusione Minore (un lancio crea suono e immagine).",
          "Illusion spells lose Verbal components and gain 60 ft of range (from 10 ft up); you learn Minor Illusion (one casting makes sound and image)."),
         passive=True, school_boost=("illusion", 18), bonus_cast_spells=("minor-illusion",), granted_spells=("minor-illusion",),
         # lo conosci; se lo sapevi già (non l'ha creato la concessione) impari un altro trucchetto da mago, fuori dal limite
         choices=(ChoiceSpec(group="improved_illusions", levels={3: 1}, options=_no_options, spell_pick="extra", spell_level=0,
                             spell_list="wizard", applies=_knew_minor_illusion),)),
    _phantasmal("phantasmal_beast", "summon-beast", "Evocare bestia", "Summon Beast"),
    _phantasmal("phantasmal_fey", "summon-fey", "Evocare fatato", "Summon Fey"),
    _ILL("illusory_self", 10, "Sosia Illusorio", "Illusory Self", 175,
         ("Reazione: un attacco contro di te manca automaticamente. Un uso, riposo breve o lungo, o ripristino spendendo uno slot di 2° livello o più.",
          "Reaction: an attack against you automatically misses. One use, short or long rest, or restore by spending a level 2 or higher slot."),
         "reaction", uses=Uses(table={10: 1}), restoration="short_rest", on_use=ILLUSORY_SELF_USE),
    _ILL("illusory_reality", 14, "Realtà Illusoria", "Illusory Reality", 175,
         ("Azione bonus, nel turno in cui lanci un'illusione con slot: un oggetto inanimato non magico dell'illusione diventa reale per 1 minuto.",
          "Bonus action, on the turn you cast an illusion with a slot: a nonmagical inanimate object of the illusion becomes real for 1 minute."),
         "bonus_action", on_use=REALITY_USE),
)

SUBCLASS_ROWS = (*ABJURER, *DIVINER, *EVOKER, *ILLUSIONIST)

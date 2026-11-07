"""Druido 2024: base della classe (Task 34, parte A). I circoli (Terra, Luna, Mare, Stelle) vengono dopo (parte B).

Valori dalla scheda ``docs/superpowers/rules/2024/classes/druid.md``; i testi sono nostri, mai quelli del manuale.
La Forma Selvatica è la riserva ``druid.wild_shape`` (stessa chiave del 2014): usi, forme conosciute, durata, PF temporanei e CA
stanno in ``core/rules/forms.py`` e ``api/services/wild_shape.py``; qui ci sono gli usi a tabella e le azioni che la spendono.

Per la parte B: i privilegi di circolo vanno in ``CIRCLE_FEATURES`` (``subclass="land"|"moon"|"sea"|"stars"``) e spendono
``WILD_SHAPE`` con ``OnUse.spends``. I circoli che sostituiscono i limiti di GS della Luna sono già in ``FormRules``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.rules.catalog._common import feature, state_on
from core.rules.catalog.y2014.cleric import _no_options, _own_cantrip, _wisdom_mod
from core.rules.types import (
    ChoiceSpec, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, UseChoice, Uses, UseText,
)

ED, CK = "2024", "druid"
WILD_SHAPE = f"{CK}.wild_shape"
WILD_COMPANION = f"{CK}.wild_companion"
ORDER, FURY = "primal_order", "elemental_fury"
NAME_MAX = 80
_NATURE = ("arcana", "nature")
_ENERGIES = {"cold": ("Freddo", "cold"), "fire": ("Fuoco", "fire"), "lightning": ("Fulmine", "lightning"),
             "thunder": ("Tuono", "thunder")}


def _chosen(ctx: RuleContext, group: str, option: str) -> bool:
    return option in ((getattr(ctx.class_row, "options", None) or {}).get(group) or [])


def _wild_row(ctx: RuleContext) -> Any:
    return next((a for a in ctx.char.abilities if a.feature_key == WILD_SHAPE and a.source_class_id == getattr(ctx.class_row, "id", None)), None)


def _no_uses_left(ctx: RuleContext) -> bool:
    row = _wild_row(ctx)
    return row is not None and row.max_uses is not None and (row.uses or 0) <= 0


def _free_slot_levels(ctx: RuleContext) -> list[str]:
    return [str(n) for n in sorted({s.level for s in ctx.char.spell_slots if s.used < s.total and s.level >= 1})]


def _level_label(key: str) -> dict[str, str]:
    return {"it": f"{key}° livello", "en": f"Level {key}"}


# ---------------------------------------------------------------------------
# Ordine Primordiale: Mago e Custode
# ---------------------------------------------------------------------------

def _magician_bonus(ctx: RuleContext) -> int:
    return max(1, _wisdom_mod(ctx))


MAGICIAN_BONUS = Modifier("skill", _magician_bonus, when=lambda c: c.roll == "skill" and c.skill in _NATURE,
                          source=f"feature:{CK}.primal_order_magician")


# ---------------------------------------------------------------------------
# Compagno Selvatico: Trova Famiglio pagando uno slot o un uso di Forma Selvatica
# ---------------------------------------------------------------------------

_PAYMENTS = {"wild_shape": {"it": "Un uso di Forma Selvatica", "en": "One Wild Shape use"},
             "slot": {"it": "Uno slot incantesimo", "en": "A spell slot"}}


def _companion_check(_ctx: RuleContext, params: dict) -> tuple[int, str] | None:
    return (422, "invalid_choice") if params.get("pay") == "slot" and params.get("slot_level") is None else None


def _companion_effect(ctx: RuleContext, params: dict) -> None:
    """Il famiglio è Fatato e scompare al riposo lungo (``long_rest_familiar``); un nuovo lancio sostituisce il precedente."""
    from core.db.models import Companion  # import locale: i modelli non servono al resto del catalogo
    for old in [c for c in ctx.char.companions if c.feature_key == WILD_COMPANION]:
        ctx.char.companions.remove(old)
    name = str(params.get("name") or "").strip() or "Famiglio"
    ctx.char.companions.append(Companion(
        character_id=ctx.char.id, kind="familiar", name=name, statblock={"type": "fey", "size": "Tiny"}, max_hp=1, current_hp=1,
        armor_class=11, feature_key=WILD_COMPANION, created_at=datetime.now(timezone.utc).isoformat(timespec="seconds")))


def _companion_message(_ctx: RuleContext, _params: dict) -> dict[str, str]:
    return {"it": "Lanci Trova Famiglio senza componenti materiali. Il famiglio è Fatato e scompare al riposo lungo: "
                  "è fra i compagni.",
            "en": "You cast Find Familiar with no Material components. The familiar is a Fey and vanishes on a long rest: "
                  "it is among your companions."}


WILD_COMPANION_USE = OnUse(
    slot="action", spends=WILD_SHAPE, cost_by=lambda _c, p: 1 if p.get("pay") == "wild_shape" else 0,
    spends_slot="slot_level", spends_slot_when=lambda _c, p: p.get("pay") == "slot", check=_companion_check,
    effect=_companion_effect, message=_companion_message,
    choices=(UseChoice("pay", {"it": "Costo", "en": "Cost"}, lambda _c: list(_PAYMENTS), lambda k: _PAYMENTS[k]),
             UseChoice("slot_level", {"it": "Livello dello slot", "en": "Slot level"}, _free_slot_levels, _level_label, optional=True)),
    texts=(UseText("name", {"it": "Nome del famiglio", "en": "Familiar name"}, max_len=NAME_MAX, optional=True),))


# ---------------------------------------------------------------------------
# Rigenerazione Selvatica
# ---------------------------------------------------------------------------

def _resurgence_use(ctx: RuleContext, _params: dict) -> None:
    row = _wild_row(ctx)
    if row is not None:
        row.uses = (row.uses or 0) + 1


RESURGENCE_USE = OnUse(
    once_per_turn=True, available=_no_uses_left, spends_slot="slot_level", effect=_resurgence_use,
    choices=(UseChoice("slot_level", {"it": "Slot da spendere", "en": "Slot to spend"}, _free_slot_levels, _level_label),),
    message=lambda _c, _p: {"it": "Hai recuperato un uso di Forma Selvatica.", "en": "You regained a Wild Shape use."})


def _spent_first_level_slots(ctx: RuleContext) -> list[Any]:
    return [s for s in ctx.char.spell_slots if s.level == 1 and not s.is_pact and s.used > 0]


def _resurgence_check(ctx: RuleContext, _params: dict) -> tuple[int, str] | None:
    return None if _spent_first_level_slots(ctx) else (409, "no_spent_slot")


def _resurgence_slot(ctx: RuleContext, _params: dict) -> None:
    _spent_first_level_slots(ctx)[0].used -= 1


RESURGENCE_SLOT_STATE = f"{CK}.wild_resurgence_slot_used"
RESURGENCE_SLOT_USE = OnUse(
    spends=WILD_SHAPE, available=lambda c: not state_on(c, RESURGENCE_SLOT_STATE), check=_resurgence_check,
    effect=_resurgence_slot, state=StateSpec(RESURGENCE_SLOT_STATE, ends_on=("rest_long",), data={"locked": True}),
    message=lambda _c, _p: {"it": "Hai recuperato uno slot di 1° livello. Serve un riposo lungo per rifarlo.",
                            "en": "You regained a level 1 spell slot. It takes a long rest to do it again."})


# ---------------------------------------------------------------------------
# Furia Elementale: Incantesimi Potenti e Colpo Primordiale
# ---------------------------------------------------------------------------

POTENT = Modifier("damage", _wisdom_mod, when=lambda c: c.roll == "damage" and _own_cantrip(c),
                  source=f"feature:{CK}.elemental_fury_potent")


def _strike_dice(ctx: RuleContext, _inputs: dict) -> str:
    return "1d8" if ctx.class_level < 15 else "2d8"


def _attack_hit(ctx: RuleContext) -> bool:
    """Un colpo con un'arma o con la forma Bestia (non un incantesimo né un Colpo Senz'Armi fuori forma)."""
    return ctx.spell is None and (ctx.item is not None or state_on(ctx, "wild_shape"))


def _primal_strike(kind: str) -> RollOptionSpec:
    it, en = _ENERGIES[kind]
    return RollOptionSpec(
        key=f"{CK}.primal_strike_{kind}", phase="after_hit", rolls=("attack",), once_per_turn=True, group="primal_strike",
        extra_dice=_strike_dice, available=_attack_hit,
        label={"it": f"Colpo Primordiale: danni da {it} in più", "en": f"Primal Strike: extra {en} damage"})


def _regain_use(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    _resurgence_use(ctx, {})


EVERGREEN = RollOptionSpec(
    key=f"{CK}.evergreen_wild_shape", phase="before", rolls=("initiative",), on_confirm=_regain_use,
    available=lambda c: _no_uses_left(c) and c.class_level >= 20,
    label={"it": "Forma Selvatica Sempreverde: tirando l'Iniziativa senza usi ne recuperi uno",
           "en": "Archdruid's Evergreen Wild Shape: rolling Initiative with no uses left gives one back"})


# ---------------------------------------------------------------------------
# Arcidruido: Mago della Natura
# ---------------------------------------------------------------------------

NATURE_MAGICIAN_STATE = f"{CK}.nature_magician_used"


def _magician_cost(_ctx: RuleContext, params: dict) -> int:
    return int(params.get("uses") or 1)  # la scheda lo chiama anche senza parametri


def _magician_slot(ctx: RuleContext, params: dict) -> None:
    from core.rules.created_slots import add_created_slot  # import locale: il catalogo si carica prima dei modelli
    add_created_slot(ctx.char, 2 * int(params["uses"]))


def _magician_message(_ctx: RuleContext, params: dict) -> dict[str, str]:
    level = 2 * int(params["uses"])
    return {"it": f"Hai uno slot di {level}° livello in più fino al riposo lungo.",
            "en": f"You have an extra level {level} spell slot until your next long rest."}


NATURE_MAGICIAN_USE = OnUse(
    spends=WILD_SHAPE, cost_by=_magician_cost, available=lambda c: not state_on(c, NATURE_MAGICIAN_STATE),
    effect=_magician_slot, message=_magician_message,
    state=StateSpec(NATURE_MAGICIAN_STATE, ends_on=("rest_long",), data={"locked": True}),
    choices=(UseChoice("uses", {"it": "Usi da convertire (2 livelli ciascuno)", "en": "Uses to convert (2 levels each)"},
                       lambda c: [str(n) for n in range(1, min(4, (_wild_row(c).uses or 0) if _wild_row(c) else 0) + 1)],
                       lambda k: {"it": f"{k} (slot di {2 * int(k)}° livello)", "en": f"{k} (level {2 * int(k)} slot)"}),))


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

# Circoli (parte B)
CIRCLE_FEATURES: tuple = ()

CLASS_FEATURES = (
    feature("core_traits", CK, ED, 1, "Tratti Base del Druido / Core Druid Traits (Druido 1, pag. 79)", ("Tratti Base del Druido", "Core Druid Traits"),
            ("Dado Vita d8, TS Intelligenza e Saggezza, 2 abilità, armi semplici, Kit da Erborista, armature leggere e scudi.",
             "Hit die d8, Intelligence and Wisdom saves, 2 skills, simple weapons, Herbalism Kit, light armor and shields."),
            # PF, TS, armi, armature, strumenti e abilità: api/routers/classes.py e core/rules/proficiencies.py; equipaggiamento A/B no (R32)
            no_row=True, covered_by="lavori-successivi"),
    feature("spellcasting", CK, ED, 1, "Incantesimi / Spellcasting (Druido 1, pag. 79)", ("Incantesimi", "Spellcasting"),
            ("Saggezza; trucchetti 2/3/4 e incantesimi preparati da 4 a 22; slot da tabella; focus druidico.",
             "Wisdom; cantrips 2/3/4 and prepared spells from 4 to 22; slots by table; a druidic focus."),
            no_row=True, covered_by="core/rules/spellcasting.py (prepared_limit, known_limits, slots_for); "
                                    "test_cantrips_and_prepared_spells_follow_the_2024_table"),
    feature("druidic", CK, ED, 1, "Druidico / Druidic (Druido 1, pag. 80)", ("Druidico", "Druidic"),
            ("Conosci il Druidico; Parlare con gli Animali è sempre preparato e non conta nel limite.",
             "You know Druidic; Speak with Animals is always prepared and does not count against the limit."),
            granted_spells=("speak-with-animals",)),
    feature("primal_order", CK, ED, 1, "Ordine Primordiale / Primal Order (Druido 1, pag. 80)", ("Ordine Primordiale", "Primal Order"),
            ("Al 1° livello si sceglie Mago o Custode.", "At level 1 you choose Magician or Warden."),
            choices=(ChoiceSpec(group=ORDER, levels={1: 1}, options=lambda _c: ["magician", "warden"]),)),
    feature("primal_order_magician", CK, ED, 1, "Mago / Magician (Druido 1, pag. 80)", ("Mago", "Magician"),
            ("Un trucchetto da druido in più, fuori dal limite; alle prove di Arcano e Natura somma Saggezza (minimo +1).",
             "One extra druid cantrip, outside the limit; add Wisdom (minimum +1) to Arcana and Nature checks."),
            option_group=ORDER, option_key="magician", modifiers=(MAGICIAN_BONUS,),
            choices=(ChoiceSpec(group="magician_cantrip", levels={1: 1}, options=_no_options, spell_pick="extra", spell_level=0,
                                spell_list="druid"),)),
    feature("primal_order_warden", CK, ED, 1, "Custode / Warden (Druido 1, pag. 80)", ("Custode", "Warden"),
            ("Competenza nelle armi da guerra e addestramento con le armature medie.",
             "Proficiency with martial weapons and training with medium armor."),
            option_group=ORDER, option_key="warden", proficiency_grants={"armor": ("medium",), "weapons": ("martial",)}),
    feature("wild_shape", CK, ED, 2, "Forma Selvatica / Wild Shape (Druido 2, pag. 80)", ("Forma Selvatica", "Wild Shape"),
            ("Azione bonus: assumi una Bestia conosciuta. Usi 2, 3 dal 6°, 4 dal 17°; un riposo breve ne rende 1, uno lungo tutti.",
             "Bonus action: take a known Beast shape. Uses 2, 3 from 6th, 4 from 17th; a short rest returns 1, a long rest all."),
            "bonus_action", uses=Uses(table={2: 2, 6: 3, 17: 4}), restoration="long_rest", short_rest_recovers=1),
    feature("wild_shape_rules", CK, ED, 2, "Regole della Forma Selvatica / Rules While Shape-Shifted (Druido 2, pag. 81)",
            ("Regole della Forma Selvatica", "Rules While Shape-Shifted"),
            ("PF temporanei pari al livello da druido; PF, Dadi Vita, Int, Sag e Car restano tuoi; vale il modificatore più alto fra druido e Bestia.",
             "Temporary HP equal to your druid level; HP, Hit Dice, Int, Wis and Cha stay yours; the higher modifier of druid and Beast applies."),
            no_row=True, covered_by="api/services/wild_shape.py (start_form), core/game/stats.py e core/rules/forms.py; "
                                    "test_wild_shape_is_a_bonus_action_gives_temporary_hp_equal_to_the_level_and_keeps_the_real_hp"),
    feature("wild_companion", CK, ED, 2, "Compagno Selvatico / Wild Companion (Druido 2, pag. 81)", ("Compagno Selvatico", "Wild Companion"),
            ("Azione Magia: lanci Trova Famiglio senza materiali, pagando uno slot o un uso di Forma Selvatica. Il famiglio è Fatato e sparisce al riposo lungo.",
             "Magic action: cast Find Familiar with no Material components, paying a slot or a Wild Shape use. The familiar is a Fey and vanishes on a long rest."),
            "action", on_use=WILD_COMPANION_USE),
    feature("druid_subclass", CK, ED, 3, "Sottoclasse del Druido / Druid Subclass (Druido 3, pag. 81)",
            ("Sottoclasse del Druido", "Druid Subclass"),
            ("Al 3° livello si sceglie il Circolo della Terra, della Luna, del Mare o delle Stelle.",
             "At level 3 you choose the Circle of the Land, Moon, Sea or Stars."),
            no_row=True, covered_by="core/rules/subclasses.py (match_subclass) e il campo sottoclasse della classe"),
    feature("ability_score_improvement", CK, ED, 4,
            "Aumento dei Punteggi di Caratteristica / Ability Score Improvement (Druido 4, pag. 81)",
            ("Aumento dei Punteggi di Caratteristica", "Ability Score Improvement"),
            ("Ai livelli 4, 8, 12 e 16 il talento Aumento dei Punteggi o un altro talento di cui hai i requisiti.",
             "At levels 4, 8, 12 and 16 the Ability Score Improvement feat or another feat you qualify for."),
            no_row=True, covered_by="core/rules/level_choices.py (scelta asi); test_asi_choice_is_pending_at_each_asi_level_and_the_19th_is_an_epic_boon"),
    feature("wild_resurgence", CK, ED, 5, "Rigenerazione Selvatica / Wild Resurgence (Druido 5, pag. 81)",
            ("Rigenerazione Selvatica: slot in cambio di un uso", "Wild Resurgence: slot for a use"),
            ("Senza azione, una volta per turno, a zero usi di Forma Selvatica spendi uno slot per riavere un uso.",
             "No action, once per turn, with no Wild Shape uses left you spend a slot to regain one use."),
            on_use=RESURGENCE_USE),
    feature("wild_resurgence_slot", CK, ED, 5, "Rigenerazione Selvatica / Wild Resurgence (Druido 5, pag. 81)",
            ("Rigenerazione Selvatica: uso in cambio di uno slot", "Wild Resurgence: use for a slot"),
            ("Senza azione spendi un uso di Forma Selvatica e recuperi uno slot di 1° livello; poi serve un riposo lungo.",
             "No action, you spend a Wild Shape use and regain a level 1 slot; then it takes a long rest."),
            on_use=RESURGENCE_SLOT_USE),
    feature("elemental_fury", CK, ED, 7, "Furia Elementale / Elemental Fury (Druido 7, pag. 81)", ("Furia Elementale", "Elemental Fury"),
            ("Al 7° livello si sceglie Incantesimi Potenti o Colpo Primordiale.", "At level 7 you choose Potent Spellcasting or Primal Strike."),
            choices=(ChoiceSpec(group=FURY, levels={7: 1}, options=lambda _c: ["potent_spellcasting", "primal_strike"]),)),
    feature("elemental_fury_potent", CK, ED, 7, "Incantesimi Potenti / Potent Spellcasting (Druido 7, pag. 81)",
            ("Incantesimi Potenti", "Potent Spellcasting"),
            ("Ai danni di ogni tuo trucchetto da druido si somma il modificatore di Saggezza.",
             "Add your Wisdom modifier to the damage of every druid cantrip you cast."),
            option_group=FURY, option_key="potent_spellcasting", modifiers=(POTENT,)),
    feature("elemental_fury_strike", CK, ED, 7, "Colpo Primordiale / Primal Strike (Druido 7, pag. 81)",
            ("Colpo Primordiale", "Primal Strike"),
            ("Una volta per turno, con un colpo d'arma o della forma Bestia: 1d8 (2d8 dal 15°) di Freddo, Fuoco, Fulmine o Tuono in più.",
             "Once per turn, on a weapon or Beast-form hit: 1d8 (2d8 from level 15) extra Cold, Fire, Lightning or Thunder damage."),
            option_group=FURY, option_key="primal_strike", roll_options=tuple(_primal_strike(k) for k in _ENERGIES)),
    feature("improved_elemental_fury_potent", CK, ED, 15, "Furia Elementale Migliorata / Improved Elemental Fury (Druido 15, pag. 81)",
            ("Furia Elementale Migliorata: Incantesimi Potenti", "Improved Elemental Fury: Potent Spellcasting"),
            ("La gittata dei tuoi trucchetti da druido di 3 m o più aumenta di 90 m.",
             "The range of your druid cantrips of 10 feet or more increases by 300 feet."),
            option_group=FURY, option_key="potent_spellcasting", cantrip_range_bonus=90, passive=True),
    feature("improved_elemental_fury_strike", CK, ED, 15, "Furia Elementale Migliorata / Improved Elemental Fury (Druido 15, pag. 81)",
            ("Furia Elementale Migliorata: Colpo Primordiale", "Improved Elemental Fury: Primal Strike"),
            ("Colpo Primordiale infligge 2d8 in più.", "Primal Strike deals 2d8 extra."),
            option_group=FURY, option_key="primal_strike", passive=True),
    feature("beast_spells", CK, ED, 18, "Incantesimi Bestiali / Beast Spells (Druido 18, pag. 81)",
            ("Incantesimi Bestiali", "Beast Spells"),
            ("In Forma Selvatica lanci incantesimi, salvo quelli con un materiale che costa o si consuma (l'app te lo chiede).",
             "While in Wild Shape you cast spells, except those with a Material component that costs or is consumed (the app asks)."),
            cast_in_form=True, ignores_components=True),
    feature("epic_boon", CK, ED, 19, "Dono Epico / Epic Boon (Druido 19, pag. 81)", ("Dono Epico", "Epic Boon"),
            ("Al 19° livello un talento Dono Epico o un altro talento di cui hai i requisiti.",
             "At level 19 an Epic Boon feat or another feat you qualify for."),
            no_row=True, covered_by="core/rules/level_choices.py (reconcile_choices, scelta epic_boon)"),
    feature("archdruid", CK, ED, 20, "Arcidruido / Archdruid (Druido 20, pag. 82)", ("Arcidruido", "Archdruid"),
            ("Forma Selvatica Sempreverde: tirando l'Iniziativa senza usi ne recuperi uno. Longevità: invecchi di 1 anno ogni 10.",
             "Evergreen Wild Shape: rolling Initiative with no uses left gives one back. Longevity: you age 1 year per 10."),
            roll_options=(EVERGREEN,), passive=True),
    feature("nature_magician", CK, ED, 20, "Arcidruido / Archdruid (Druido 20, pag. 82)", ("Mago della Natura", "Nature Magician"),
            ("Senza azione converti usi inutilizzati di Forma Selvatica in un solo slot (2 livelli per uso); una volta fino al riposo lungo.",
             "No action, you convert unexpended Wild Shape uses into one spell slot (2 levels per use); once until a long rest."),
            on_use=NATURE_MAGICIAN_USE),
    feature("multiclassing", CK, ED, 1, "Multiclasse: Druido / Multiclassing: Druid (Regole multiclasse, pag. 44)",
            ("Multiclasse: Druido", "Multiclassing: Druid"),
            ("Requisito Saggezza 13. Da multiclasse: armature leggere e scudi; i livelli contano per intero negli slot.",
             "Requires Wisdom 13. As a multiclass: light armor and shields; levels count in full for slots."),
            no_row=True, covered_by="core/rules/proficiencies.py (as_multiclass) e webapp/src/data/multiclassPrereqs.ts (D2)"),
)

FEATURES = CIRCLE_FEATURES + CLASS_FEATURES

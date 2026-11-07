"""Stregone 2024, parte A (base della classe). Le sottoclassi (Aberrante, Meccanica, Draconica, Magia Selvaggia) sono la parte B, in
``sorcerer_subclasses.py``: le loro righe vanno in ``SUBCLASS_ROWS`` con ``subclass=`` (aberrant, clockwork, draconic, wild_magic).

Valori dalla scheda ``docs/superpowers/rules/2024/classes/sorcerer.md``; i testi sono nostri, mai quelli del manuale. Le opzioni di
Metamagia sono dieci (la mappatura ne contava otto: R31, vale il manuale). Per la parte B: ``INNATE_STATE`` è lo stato di Stregoneria
Innata, ``SP`` la riserva dei punti, ``cast_option(...)`` costruisce un'opzione al lancio a punti (con Apoteosi Arcana e il limite
di opzioni per incantesimo già applicati) e ``innate_sorcerer_spell(ctx)`` dice se l'incantesimo è da stregone.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from core.data.damage_types import canonical_damage_type
from core.game.actions import parse_casting_time
from core.rules.catalog._common import feature, save_spell, state_on
from core.rules.catalog.y2014.sorcerer import (
    CONVERT_USE, EMPOWERED as EMPOWERED_2014, METAMAGIC_GROUP, ONE_OPTION, SP,
    _cha, _distant_effect, _distant_ok, _doubled_rounds, _extend_concentration, _extended_effect, _meta, _say,
)
from core.rules.states import begin_state
from core.rules.types import (
    ChoiceSpec, Cost, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, TargetEffect, UseChoice, Uses, UseToggle,
)

ED, CK = "2024", "sorcerer"
INNATE = f"{CK}.innate_sorcery"
INNATE_STATE = "innate_sorcery"
EXTENDED_STATE = "extended_spell"
FREE_TURN_KEY = "apotheosis_free_used"  # turn_state: l'opzione gratuita di Apoteosi Arcana è già stata usata in questo turno
CREATE_MIN_LEVEL = {1: 2, 2: 3, 3: 5, 4: 7, 5: 9}  # livello dello slot creato -> livello da stregone minimo
CREATE_COST = {1: 2, 2: 3, 3: 5, 4: 6, 5: 7}  # ... -> punti stregoneria
TRANSMUTE_TYPES = ("acid", "cold", "fire", "lightning", "poison", "thunder")
_TYPE_LABELS = {"acid": ("acido", "acid"), "cold": ("freddo", "cold"), "fire": ("fuoco", "fire"), "lightning": ("fulmine", "lightning"),
                "poison": ("veleno", "poison"), "thunder": ("tuono", "thunder")}
# Incantesimi che con uno slot più alto prendono una creatura in più (Incantesimo Raddoppiato): srd_index
TWINNED_SPELLS = frozenset({
    "animal-friendship", "banishment", "bane", "bless", "blindness-deafness", "charm-person", "command", "enhance-ability", "fly",
    "hold-monster", "hold-person", "invisibility", "jump", "longstrider",
})
_ROWS = "core/rules/proficiencies.py (class_proficiencies, as_multiclass), api/routers/classes.py create_class_for_character e add_class"


def _both(it: str, en: str) -> dict[str, str]:
    return {"it": it, "en": en}


# ---------------------------------------------------------------------------
# Stregoneria Innata e Stregoneria Incarnata
# ---------------------------------------------------------------------------

def innate_sorcerer_spell(ctx: RuleContext) -> bool:
    """L'incantesimo è da stregone: assegnato a questa classe, o senza classe quando è l'unico incantatore."""
    from core.rules.spellcasting import caster_stats  # import locale: spellcasting importa il catalogo
    spell, row = ctx.spell, ctx.class_row
    if spell is None or row is None:
        return False
    return spell.class_id == row.id or (spell.class_id is None and len(caster_stats(ctx.char)) == 1)


def _innate_attack(ctx: RuleContext) -> bool:
    return ctx.roll == "attack" and state_on(ctx, INNATE_STATE) and innate_sorcerer_spell(ctx)


def _innate_uses(ctx: RuleContext) -> int:
    row = next((a for a in ctx.char.abilities if a.feature_key == INNATE), None)
    return (row.uses or 0) if row is not None else 0


def _innate_cost(_ctx: RuleContext, params: dict) -> int:
    return 2 if params.get("restore") else 1


def _innate_check(ctx: RuleContext, params: dict) -> tuple[int, str] | None:
    """Stregoneria Incarnata: i 2 punti sostituiscono un uso solo dal 7° livello e solo a usi finiti."""
    if params.get("restore") and (ctx.class_level < 7 or _innate_uses(ctx) > 0):
        return 409, "innate_uses_left"
    return None


INNATE_USE = OnUse(
    slot="bonus", state=StateSpec(INNATE_STATE, rounds=10, ends_on=("manual",)), alt_spends=SP, cost_by=_innate_cost,
    check=_innate_check,
    toggles=(UseToggle("restore", _both("Senza usi: spendi 2 punti stregoneria (Stregoneria Incarnata)",
                                        "No uses left: spend 2 sorcery points (Sorcery Incarnate)"),
                       available=lambda c: c.class_level >= 7),))


# ---------------------------------------------------------------------------
# Fonte di Magia
# ---------------------------------------------------------------------------

def _created_label(level: str) -> dict:
    cost = CREATE_COST[int(level)]
    return _both(f"Slot di {level}° livello ({cost} punti)", f"Level {level} slot ({cost} points)")


def _create_slot(ctx: RuleContext, params: dict) -> None:
    from core.rules.created_slots import add_created_slot  # import locale: il catalogo si carica prima dei modelli
    add_created_slot(ctx.char, int(params["slot_level"]))


CREATE_USE = OnUse(
    slot="bonus", spends=SP, cost_by=lambda _c, params: CREATE_COST[int(params["slot_level"])], effect=_create_slot,
    choices=(UseChoice("slot_level", _both("Livello dello slot da creare", "Level of the slot to create"),
                       lambda c: [str(level) for level, minimum in CREATE_MIN_LEVEL.items() if c.class_level >= minimum], _created_label),))
CONVERT_USE_2024 = replace(CONVERT_USE, slot=None)  # nessuna azione


# ---------------------------------------------------------------------------
# Ripristino Stregonesco
# ---------------------------------------------------------------------------

def _pool(ctx: RuleContext) -> Any:
    return next((a for a in ctx.char.abilities if a.feature_key == SP), None)


def _restore_check(ctx: RuleContext, _params: dict) -> tuple[int, str] | None:
    pool = _pool(ctx)
    return (409, "nothing_to_restore") if pool is None or (pool.uses or 0) >= (pool.max_uses or 0) else None


def _restore_points(ctx: RuleContext, params: dict) -> None:
    pool = _pool(ctx)
    pool.uses = min(pool.max_uses, (pool.uses or 0) + int(params["points"]))


RESTORATION_USE = OnUse(
    slot=None, check=_restore_check, effect=_restore_points,
    choices=(UseChoice("points", _both("Punti stregoneria da recuperare (al massimo metà livello)", "Sorcery points to regain (half your level at most)"),
                       lambda c: [str(n) for n in range(1, c.class_level // 2 + 1)],
                       lambda k: _both(f"{k} punti", f"{k} points")),))


# ---------------------------------------------------------------------------
# Metamagia
# ---------------------------------------------------------------------------

def _free_available(ctx: RuleContext) -> bool:
    """Apoteosi Arcana: con Stregoneria Innata attiva, una opzione per turno senza punti."""
    return ctx.class_level >= 20 and state_on(ctx, INNATE_STATE) and not (ctx.char.turn_state or {}).get(FREE_TURN_KEY)


def price(base: int) -> Cost:
    """Costo in punti di un'opzione: ``base``, o nulla per l'opzione gratuita del turno."""
    return Cost(feature_key=SP, amount_by=lambda ctx: 0 if _free_available(ctx) else base)


def _confirm(base: Any = None):
    """Segna sul turno l'opzione gratuita appena usata (prima di ``base``), così la seconda dello stesso turno si paga."""
    def run(session: Any, ctx: RuleContext, inputs: dict) -> None:
        if _free_available(ctx):
            ctx.char.turn_state = {**(ctx.char.turn_state or {}), FREE_TURN_KEY: True}
        if base:
            base(session, ctx, inputs)
    return run


def _max_options(ctx: RuleContext) -> int:
    """Una opzione per incantesimo; due con Stregoneria Incarnata mentre Innata è attiva."""
    return 2 if ctx.class_level >= 7 and state_on(ctx, INNATE_STATE) else 1


def cast_option(key: str, label: dict, cost: int = 1, on_confirm: Any = None, **kw: Any) -> RollOptionSpec:
    return RollOptionSpec(key=_meta(key), phase="before", rolls=("cast",), group=ONE_OPTION, group_max=_max_options, cost=price(cost),
                          on_confirm=_confirm(on_confirm), label=label, **kw)


def _prior_level_one_cast(ctx: RuleContext) -> bool:
    """Prima di questo lancio, in questo turno, è già stato lanciato un incantesimo di livello 1 o più con uno slot?"""
    turn = ctx.char.turn_state or {}
    return bool(turn.get("cast_prior_slot", turn.get("spell_slot_cast")))


def _quicken(session: Any, ctx: RuleContext, inputs: dict) -> None:
    """Il lancio vale come azione bonus: non più come incantesimo dell'azione."""
    turn = dict(ctx.char.turn_state or {})
    turn["bonus_spell_cast"] = True
    turn.pop("action_spell_level", None)
    turn["action_spell_class"] = None
    ctx.char.turn_state = turn


def _extend(session: Any, ctx: RuleContext, inputs: dict) -> None:
    """Durata raddoppiata e, per una concentrazione, vantaggio ai TS per mantenerla finché dura."""
    _extend_concentration(session, ctx, inputs)
    if ctx.char.concentrating_spell_id == ctx.spell.id:
        begin_state(ctx.char, StateSpec(EXTENDED_STATE, ends_on=("concentration_end", "manual")), f"{CK}.metamagic_extended",
                    "Incantesimo Esteso")


CAREFUL = cast_option(
    "careful", _both("Incantesimo Preciso: alcune creature superano da sole il TS, senza danni (1 punto)",
                     "Careful Spell: some creatures automatically pass the save and take no damage (1 point)"),
    available=lambda c: c.spell is not None and save_spell(c.spell),
    effect=lambda c, _i: _both(
        f"Fino a {max(1, _cha(c))} creature a tua scelta superano da sole il TS; se a TS riuscito subirebbero metà danni, non subiscono nessun danno.",
        f"Up to {max(1, _cha(c))} creatures of your choice automatically pass the save; if they would take half damage on a success, they take no damage."))
DISTANT = cast_option(
    "distant", _both("Incantesimo Distante: gittata raddoppiata, a contatto 9 m (1 punto)",
                     "Distant Spell: doubled range, touch becomes 30 ft (1 point)"),
    available=_distant_ok, effect=_distant_effect)
EXTENDED = cast_option(
    "extended", _both("Incantesimo Esteso: durata raddoppiata, fino a 24 ore (1 punto)",
                      "Extended Spell: doubled duration, up to 24 hours (1 point)"),
    available=lambda c: c.spell is not None and _doubled_rounds(c.spell) is not None, effect=_extended_effect, on_confirm=_extend)
HEIGHTENED = cast_option(
    "heightened", _both("Incantesimo Intensificato: un bersaglio ha svantaggio al TS contro l'incantesimo (2 punti)",
                        "Heightened Spell: one target has disadvantage on the save against the spell (2 points)"),
    cost=2, available=lambda c: c.spell is not None and save_spell(c.spell),
    effect=_say("Un bersaglio a tua scelta ha svantaggio al TS contro questo incantesimo.",
                "One target of your choice has disadvantage on its saving throw against this spell."),
    target_effect=lambda _c, _i: TargetEffect(condition="custom:heightened_spell"))
QUICKENED = cast_option(
    "quickened", _both("Incantesimo Rapido: il lancio di 1 azione diventa un'azione bonus (2 punti)",
                       "Quickened Spell: a 1-action cast becomes a bonus action (2 points)"),
    cost=2, slot="bonus", on_confirm=_quicken,
    available=lambda c: c.spell is not None and parse_casting_time(c.spell.casting_time) == "action" and not _prior_level_one_cast(c),
    effect=_say("L'incantesimo è lanciato con l'azione bonus: in questo turno non lanci altri incantesimi di livello 1 o più.",
                "The spell is cast with a bonus action: this turn you cast no other spell of level 1 or higher."))
SUBTLE = cast_option(
    "subtle", _both("Incantesimo Celato: lancia senza componenti verbali, somatiche né materiali (1 punto)",
                    "Subtle Spell: cast without verbal, somatic or material components (1 point)"),
    effect=_say("L'incantesimo non ha componenti verbali, somatiche né materiali (restano quelle con un costo o consumate).",
                "The spell has no verbal, somatic or material components (those with a cost or consumed remain)."))


def _twinned_ok(ctx: RuleContext) -> bool:
    return ctx.spell is not None and (ctx.spell.srd_index or "") in TWINNED_SPELLS


def _twinned_effect(ctx: RuleContext, _inputs: dict) -> dict[str, str]:
    level = max(ctx.casting_level or 0, ctx.spell.level) + 1
    return _both(f"Livello effettivo {level} per i bersagli: una creatura in più, senza spendere uno slot più alto.",
                 f"Effective level {level} for the targets: one more creature, without spending a higher slot.")


TWINNED = cast_option(
    "twinned", _both("Incantesimo Raddoppiato: un bersaglio in più, come con uno slot di un livello più alto (1 punto)",
                     "Twinned Spell: one more target, as with a slot one level higher (1 point)"),
    available=_twinned_ok, effect=_twinned_effect)

SEEKING = RollOptionSpec(
    key=_meta("seeking"), phase="after_roll", rolls=("attack",), after="reroll", cost=price(1), on_confirm=_confirm(),
    available=lambda c: c.spell is not None,
    label=_both("Incantesimo Inseguitore: il tiro per colpire è mancato? Ritira il d20 e usa il nuovo (1 punto)",
                "Seeking Spell: did the attack roll miss? Reroll the d20 and use the new roll (1 point)"))


def _transmute(damage_type: str) -> RollOptionSpec:
    it, en = _TYPE_LABELS[damage_type]
    return RollOptionSpec(
        key=f"{_meta('transmuted')}_{damage_type}", phase="before", rolls=("spell_damage",), group=f"{CK}.transmuted", cost=price(1),
        damage_type_to=damage_type, on_confirm=_confirm(),
        available=lambda c: c.spell is not None and canonical_damage_type(c.spell.damage_type) in TRANSMUTE_TYPES
        and canonical_damage_type(c.spell.damage_type) != damage_type,
        label=_both(f"Incantesimo Trasmutato: il danno diventa {it} (1 punto)", f"Transmuted Spell: the damage becomes {en} (1 point)"),
        effect=_say(f"Il tipo di danno dell'incantesimo diventa {it}.", f"The spell's damage type becomes {en}."))


TRANSMUTED = tuple(_transmute(t) for t in TRANSMUTE_TYPES)
EMPOWERED = replace(EMPOWERED_2014, cost=price(1), on_confirm=_confirm())

METAMAGIC_2024 = (
    ("careful", "Incantesimo Preciso", "Careful Spell", "Incantesimo Preciso / Careful Spell (Metamagia, pag. 141)",
     ("Al lancio, 1 punto: fino a Carisma creature (minimo 1) superano da sole il TS e, se avrebbero metà danni, non ne subiscono.",
      "On the cast, 1 point: up to Charisma creatures (minimum 1) pass the save and, if they would take half damage, take none."), (CAREFUL,)),
    ("distant", "Incantesimo Distante", "Distant Spell", "Incantesimo Distante / Distant Spell (Metamagia, pag. 141)",
     ("Al lancio, 1 punto: gittata raddoppiata; a contatto diventa 9 m. Serve una gittata di almeno 1,5 m.",
      "On the cast, 1 point: doubled range; touch becomes 30 ft. Needs a range of at least 5 ft."), (DISTANT,)),
    ("empowered", "Incantesimo Potenziato", "Empowered Spell", "Incantesimo Potenziato / Empowered Spell (Metamagia, pag. 142)",
     ("Dopo il danno, 1 punto: ritiri fino a Carisma dadi (minimo 1). Si somma a un'altra opzione.",
      "After the damage, 1 point: reroll up to Charisma dice (minimum 1). It adds to another option."), (EMPOWERED,)),
    ("extended", "Incantesimo Esteso", "Extended Spell", "Incantesimo Esteso / Extended Spell (Metamagia, pag. 142)",
     ("Al lancio, 1 punto: durata raddoppiata, al massimo 24 ore. In concentrazione hai vantaggio ai TS per mantenerla.",
      "On the cast, 1 point: doubled duration, 24 hours at most. On concentration you have advantage on saves to keep it."), (EXTENDED,)),
    ("heightened", "Incantesimo Intensificato", "Heightened Spell", "Incantesimo Intensificato / Heightened Spell (Metamagia, pag. 142)",
     ("Al lancio, 2 punti: un bersaglio ha svantaggio al TS contro l'incantesimo.",
      "On the cast, 2 points: one target has disadvantage on the save against the spell."), (HEIGHTENED,)),
    ("quickened", "Incantesimo Rapido", "Quickened Spell", "Incantesimo Rapido / Quickened Spell (Metamagia, pag. 142)",
     ("Al lancio, 2 punti: un incantesimo di 1 azione si lancia con un'azione bonus. Non dopo un incantesimo di livello 1+ nel turno.",
      "On the cast, 2 points: a 1-action spell is cast as a bonus action. Not after a level 1+ spell this turn."), (QUICKENED,)),
    ("seeking", "Incantesimo Inseguitore", "Seeking Spell", "Incantesimo Inseguitore / Seeking Spell (Metamagia, pag. 142)",
     ("Dopo un tiro per colpire di incantesimo mancato, 1 punto: ritiri il d20 e usi il nuovo risultato. Si somma a un'altra opzione.",
      "After a missed spell attack roll, 1 point: reroll the d20 and use the new roll. It adds to another option."), (SEEKING,)),
    ("subtle", "Incantesimo Celato", "Subtle Spell", "Incantesimo Celato / Subtle Spell (Metamagia, pag. 142)",
     ("Al lancio, 1 punto: nessuna componente verbale, somatica o materiale (restano quelle con costo o consumate).",
      "On the cast, 1 point: no verbal, somatic or material components (costly or consumed ones remain)."), (SUBTLE,)),
    ("transmuted", "Incantesimo Trasmutato", "Transmuted Spell", "Incantesimo Trasmutato / Transmuted Spell (Metamagia, pag. 142)",
     ("Prima del danno, 1 punto: cambi il tipo di danno fra acido, freddo, fuoco, fulmine, veleno e tuono (se è uno di questi).",
      "Before the damage, 1 point: change the damage type among acid, cold, fire, lightning, poison and thunder (if it is one)."), TRANSMUTED),
    ("twinned", "Incantesimo Raddoppiato", "Twinned Spell", "Incantesimo Raddoppiato / Twinned Spell (Metamagia, pag. 142)",
     ("Al lancio, 1 punto: per un incantesimo che con uno slot più alto prende un bersaglio in più, conta come di un livello più alto.",
      "On the cast, 1 point: for a spell that gains a target with a higher slot, it counts as one level higher."), (TWINNED,)),
)


def _option_row(key: str, it: str, en: str, title: str, summary: tuple[str, str], rolls: tuple) -> Any:
    extra = {"modifiers": (Modifier("advantage", 1, when=lambda c: c.roll == "concentration" and state_on(c, EXTENDED_STATE),
                                    source=f"feature:{CK}.metamagic_extended"),)} if key == "extended" else {}
    return feature(f"metamagic_{key}", CK, ED, 2, title, (it, en), summary, option_group=METAMAGIC_GROUP, option_key=key,
                   roll_options=rolls, passive=True, **extra)


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

BASE_ROWS = (
    feature("core_traits", CK, ED, 1, "Tratti Base / Core Sorcerer Traits (Stregone 1, pag. 139)", ("Tratti Base", "Core Sorcerer Traits"),
            ("Dado vita d6, TS Costituzione e Carisma, 2 abilità su 6, armi semplici, nessuna armatura. Multiclasse: solo il dado vita.",
             "Hit die d6, Constitution and Charisma saves, 2 skills out of 6, simple weapons, no armor. Multiclass: the hit die only."),
            no_row=True, covered_by=f"{_ROWS}; test_hit_points_use_the_d6, test_class_and_multiclass_proficiencies; equipaggiamento di partenza: lavori-successivi"),
    feature("spellcasting", CK, ED, 1, "Incantesimi / Spellcasting (Stregone 1, pag. 139)", ("Incantesimi", "Spellcasting"),
            ("Incantatore pieno con Carisma. Trucchetti 4 (5 al 4°, 6 al 10°); preparati da 2 a 22 e sostituibili a ogni livello; focus arcano.",
             "Full caster with Charisma. Cantrips 4 (5 at 4th, 6 at 10th); prepared 2 to 22, swappable every level; arcane focus."),
            no_row=True, covered_by="core/rules/spellcasting.py (known_limits, prepared_limit, slots_for); "
                                    "test_slots_cantrips_and_prepared_follow_the_table, test_multiclass_uses_the_multiclass_slot_table_and_prepares_per_class"),
    feature("innate_sorcery", CK, ED, 1, "Stregoneria Innata / Innate Sorcery (Stregone 1, pag. 140)", ("Stregoneria Innata", "Innate Sorcery"),
            ("Azione bonus, 2 usi per riposo lungo: per 1 minuto +1 alla CD dei tuoi incantesimi da stregone e vantaggio ai loro tiri per colpire.",
             "Bonus action, 2 uses per long rest: for 1 minute +1 to your sorcerer spells' save DC and advantage on their attack rolls."),
            "bonus_action", uses=Uses(table={1: 2}), restoration="long_rest", on_use=INNATE_USE,
            modifiers=(Modifier("advantage", 1, when=_innate_attack, source=f"feature:{CK}.innate_sorcery"),)),
    feature("sorcery_points", CK, ED, 2, "Fonte di Magia / Font of Magic (Stregone 2, pag. 140)", ("Punti Stregoneria", "Sorcery Points"),
            ("Punti stregoneria pari al tuo livello da stregone (da 2 a 20): tornano con un riposo lungo. Alimentano Metamagia e altri privilegi.",
             "Sorcery points equal to your sorcerer level (2 to 20): they return on a long rest. They fuel Metamagic and other features."),
            uses=Uses(table={lv: lv for lv in range(2, 21)}), restoration="long_rest"),
    feature("font_create_slot", CK, ED, 2, "Fonte di Magia / Font of Magic (Stregone 2, pag. 140)",
            ("Fonte di Magia: Creare Slot", "Font of Magic: Creating Slots"),
            ("Azione bonus: spendi punti per uno slot di 1°-5° livello (2, 3, 5, 6, 7 punti; dal 2°, 3°, 5°, 7°, 9° livello). Svanisce al riposo lungo.",
             "Bonus action: spend points for a 1st-5th level slot (2, 3, 5, 6, 7 points; from level 2, 3, 5, 7, 9). It vanishes on a long rest."),
            "bonus_action", on_use=CREATE_USE),
    feature("font_convert_slot", CK, ED, 2, "Fonte di Magia / Font of Magic (Stregone 2, pag. 140)",
            ("Fonte di Magia: Convertire uno Slot", "Font of Magic: Converting a Slot"),
            ("Nessuna azione: spendi uno slot libero e ottieni tanti punti stregoneria quanto il suo livello, senza superare il massimo.",
             "No action: spend an unused slot and gain sorcery points equal to its level, without exceeding the maximum."),
            on_use=CONVERT_USE_2024),
    feature("metamagic", CK, ED, 2, "Metamagia / Metamagic (Stregone 2, pag. 141)", ("Metamagia", "Metamagic"),
            ("Due opzioni al 2° livello, due in più al 10° e al 17°, sostituibili a ogni livello. Una sola opzione per incantesimo.",
             "Two options at 2nd level, two more at 10th and 17th, replaceable every level. One option per spell."),
            no_row=True, choices=(ChoiceSpec(group=METAMAGIC_GROUP, levels={2: 2, 10: 4, 17: 6}, replaceable=True,
                                             options=lambda _c: [k for k, *_ in METAMAGIC_2024]),),
            covered_by="ChoiceSpec metamagic di questa riga e le righe delle dieci opzioni; test_metamagic_options_known_follow_the_level"),
    feature("sorcerer_subclass", CK, ED, 3, "Sottoclasse da Stregone / Sorcerer Subclass (Stregone 3, pag. 141)",
            ("Sottoclasse da Stregone", "Sorcerer Subclass"),
            ("Al 3° livello si sceglie Stregoneria Aberrante, Meccanica, Draconica o Magia Selvaggia: privilegi ai livelli 3, 6, 14 e 18.",
             "At level 3 you choose Aberrant Sorcery, Clockwork Sorcery, Draconic Sorcery or Wild Magic: features at levels 3, 6, 14 and 18."),
            no_row=True, covered_by="core/rules/subclasses.py (match_subclass) e il campo sottoclasse della classe"),
    feature("ability_score_improvement", CK, ED, 4, "Aumento dei Punteggi di Caratteristica / Ability Score Improvement (Stregone 4, pag. 141)",
            ("Aumento dei Punteggi di Caratteristica", "Ability Score Improvement"),
            ("Ai livelli 4, 8, 12 e 16: il talento Aumento dei Punteggi o un altro talento di cui hai i requisiti.",
             "At levels 4, 8, 12 and 16: the Ability Score Improvement feat or another feat you qualify for."),
            no_row=True, covered_by="core/rules/level_choices.py (scelta asi); test_asi_at_4_8_12_16_and_the_19th_is_an_epic_boon"),
    feature("sorcerous_restoration", CK, ED, 5, "Ripristino Stregonesco / Sorcerous Restoration (Stregone 5, pag. 141)",
            ("Ripristino Stregonesco", "Sorcerous Restoration"),
            ("A fine riposo breve recuperi fino a metà del livello da stregone in punti stregoneria spesi. Un uso fra riposi lunghi.",
             "At the end of a short rest you regain spent sorcery points, up to half your sorcerer level. One use between long rests."),
            uses=Uses(table={5: 1}), restoration="long_rest", on_use=RESTORATION_USE),
    feature("sorcery_incarnate", CK, ED, 7, "Stregoneria Incarnata / Sorcery Incarnate (Stregone 7, pag. 141)", ("Stregoneria Incarnata", "Sorcery Incarnate"),
            ("Senza usi di Stregoneria Innata la attivi con 2 punti stregoneria. Con Innata attiva usi fino a 2 opzioni di Metamagia per incantesimo.",
             "With no Innate Sorcery uses left you activate it for 2 sorcery points. While it is active you use up to 2 Metamagic options per spell."),
            passive=True),
    feature("epic_boon", CK, ED, 19, "Favore Epico / Epic Boon (Stregone 19, pag. 141)", ("Favore Epico", "Epic Boon"),
            ("Al 19° livello un talento Favore Epico o un altro talento di cui hai i requisiti; consigliato Favore del Viaggio Dimensionale.",
             "At 19th level an Epic Boon feat or another feat you qualify for; Boon of Dimensional Travel is recommended."),
            no_row=True, covered_by="core/rules/level_choices.py (scelta epic_boon); test_asi_at_4_8_12_16_and_the_19th_is_an_epic_boon"),
    feature("arcane_apotheosis", CK, ED, 20, "Apoteosi Arcana / Arcane Apotheosis (Stregone 20, pag. 141)", ("Apoteosi Arcana", "Arcane Apotheosis"),
            ("Con Stregoneria Innata attiva usi una opzione di Metamagia per turno senza spendere punti stregoneria.",
             "While Innate Sorcery is active you use one Metamagic option per turn without spending sorcery points."),
            passive=True),
    *(_option_row(k, it, en, title, summary, rolls) for k, it, en, title, summary, rolls in METAMAGIC_2024),
    feature("multiclassing", CK, ED, 1, "Multiclasse: Stregone / Multiclassing: Sorcerer (Multiclasse, pag. 44)",
            ("Multiclasse: Stregone", "Multiclassing: Sorcerer"),
            ("Requisito Carisma 13. Da multiclasse: solo il dado vita d6; si prepara per classe e i punti contano i soli livelli da stregone.",
             "Requires Charisma 13. As a multiclass: only the d6 hit die; spells are prepared per class and points count sorcerer levels only."),
            no_row=True, covered_by=f"{_ROWS} e webapp/src/data/multiclassPrereqs.ts (D2); test_sorcery_points_depend_only_on_sorcerer_levels"),
)

from core.rules.catalog.y2024.sorcerer_subclasses import SUBCLASS_ROWS  # noqa: E402  (parte B, dopo le definizioni comuni)

FEATURES = BASE_ROWS + SUBCLASS_ROWS

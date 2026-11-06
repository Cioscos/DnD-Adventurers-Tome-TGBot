"""Stregone 2014 e le sue origini: Discendenza Draconica e Magia Selvaggia.

Valori dalla scheda ``docs/superpowers/rules/2014/classes/sorcerer.md``; i testi sono nostri, mai quelli del manuale.
I punti stregoneria sono una riserva (``sorcerer.sorcery_points``) che Incantesimi Flessibili e Metamagia spendono. Le otto
opzioni di Metamagia sono opzioni di una scelta (``metamagic``, sostituibile) e conferme al lancio (fase ``cast``, una per
incantesimo) o al danno (Incantesimo Potenziato, che si somma). Gli impulsi di Magia Selvaggia vivono in
``api/services/wild_magic.py`` con la tabella di ``sorcerer_wild_magic.py``.
"""
from __future__ import annotations

import re
from typing import Any

from core.data.damage_types import canonical_damage_type
from core.data.skills import SKILL_ABILITY_MAP
from core.game.actions import parse_casting_time, parse_duration_rounds
from core.rules.catalog._common import feature, state_on
from core.rules.catalog.y2014.fighter import _save_spell
from core.rules.types import (
    ChoiceSpec, Cost, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, TargetEffect, UnarmoredAc, Uses, UseChoice,
)

ED, CK = "2014", "sorcerer"
SP = f"{CK}.sorcery_points"
METAMAGIC_GROUP, ANCESTOR_GROUP = "metamagic", "dragon_ancestor"
ONE_OPTION = f"{CK}.metamagic"  # una sola opzione per incantesimo (Incantesimo Potenziato fa eccezione: agisce dopo il danno)
SLOT_COSTS = {1: 2, 2: 3, 3: 5, 4: 6, 5: 7}  # livello dello slot creato -> punti stregoneria
TWINNED_EXCLUDED = ("magic-missile", "scorching-ray")  # a quel livello colpiscono più creature
TWINNED_EXCLUDED_NAMES = ("dardo incantato", "raggio rovente", "magic missile", "scorching ray")
MAX_DURATION_ROUNDS = 24 * 600  # 24 ore
TWINNED_TURN_KEY = "twinned"  # turn_state: l'incantesimo che ha il secondo bersaglio (lo legge il router degli incantesimi)

# draghi dell'Antenato: chiave -> (nome it, nome en, tipo di danno)
DRAGONS: dict[str, tuple[str, str, str]] = {
    "silver": ("Argento", "Silver", "cold"), "white": ("Bianco", "White", "cold"),
    "blue": ("Blu", "Blue", "lightning"), "bronze": ("Bronzo", "Bronze", "lightning"),
    "black": ("Nero", "Black", "acid"), "copper": ("Rame", "Copper", "acid"),
    "gold": ("Oro", "Gold", "fire"), "brass": ("Ottone", "Brass", "fire"), "red": ("Rosso", "Red", "fire"),
    "green": ("Verde", "Green", "poison"),
}
_DAMAGE_LABELS = {"cold": ("freddo", "cold"), "lightning": ("fulmine", "lightning"), "acid": ("acido", "acid"),
                  "fire": ("fuoco", "fire"), "poison": ("veleno", "poison")}

# opzioni di Metamagia: chiave, nome it, nome en
METAMAGIC = (
    ("subtle", "Incantesimo Celato", "Subtle Spell"), ("distant", "Incantesimo Distante", "Distant Spell"),
    ("extended", "Incantesimo Esteso", "Extended Spell"), ("heightened", "Incantesimo Intensificato", "Heightened Spell"),
    ("empowered", "Incantesimo Potenziato", "Empowered Spell"), ("careful", "Incantesimo Preciso", "Careful Spell"),
    ("twinned", "Incantesimo Raddoppiato", "Twinned Spell"), ("quickened", "Incantesimo Rapido", "Quickened Spell"),
)


def _say(it: str, en: str):
    return lambda _ctx, _inputs: {"it": it, "en": en}


def _mod(ctx: RuleContext, ability: str) -> int:
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    return effective_ability_mod(ctx.char, ability)


def _cha(ctx: RuleContext) -> int:
    return _mod(ctx, "charisma")


def _dc(ctx: RuleContext) -> int:
    return 8 + ctx.char.proficiency_bonus + _cha(ctx)


def _meta(key: str) -> str:
    return f"{CK}.metamagic_{key}"


# ---------------------------------------------------------------------------
# Incantesimi Flessibili
# ---------------------------------------------------------------------------

def _slot_level_label(level: str) -> dict:
    return {"it": f"Slot di {level}° livello", "en": f"Level {level} slot"}


def _created_label(level: str) -> dict:
    cost = SLOT_COSTS[int(level)]
    return {"it": f"Slot di {level}° livello ({cost} punti)", "en": f"Level {level} slot ({cost} points)"}


def _create_slot(ctx: RuleContext, params: dict) -> None:
    from core.rules.created_slots import add_created_slot  # import locale: il catalogo si carica prima dei modelli
    add_created_slot(ctx.char, int(params["slot_level"]))


def _convert_slot(ctx: RuleContext, params: dict) -> None:
    """Lo slot è già stato speso dal server (``spends_slot``): i punti salgono fino al massimo."""
    pool = next((a for a in ctx.char.abilities if a.feature_key == SP), None)
    if pool is not None and pool.max_uses is not None:
        pool.uses = min(pool.max_uses, (pool.uses or 0) + int(params["slot_level"]))


CREATE_USE = OnUse(
    slot="bonus", spends=SP, cost_by=lambda _c, params: SLOT_COSTS[int(params["slot_level"])], effect=_create_slot,
    choices=(UseChoice("slot_level", {"it": "Livello dello slot da creare", "en": "Level of the slot to create"},
                       lambda _c: [str(level) for level in SLOT_COSTS], _created_label),))
CONVERT_USE = OnUse(
    slot="bonus", spends_slot="slot_level", effect=_convert_slot,
    choices=(UseChoice("slot_level", {"it": "Slot da convertire in punti", "en": "Slot to convert into points"},
                       lambda c: sorted({str(s.level) for s in c.char.spell_slots or [] if s.available > 0}), _slot_level_label),))


# ---------------------------------------------------------------------------
# Metamagia: la gittata, la durata, le condizioni dell'incantesimo
# ---------------------------------------------------------------------------

_RANGE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(km|m|metri|metro|ft|feet|foot|piedi|mi|miglia|miles?)\b", re.IGNORECASE)
_TOUCH = ("contatto", "tocco", "touch")
_SELF = ("personale", "self")


def _range_of(spell: Any) -> tuple[float, str] | str | None:
    """La gittata come ``(valore, unità)``, ``"touch"`` per un incantesimo a contatto, ``None`` se è personale, sconosciuta
    o senza un valore (Vista, Illimitata)."""
    text = (spell.range_area or "").strip().lower()
    if not text or text.startswith(_SELF):
        return None
    if text.startswith(_TOUCH):
        return "touch"
    m = _RANGE.search(text)
    if m is None:
        return None
    unit = m[2].lower()
    return float(m[1].replace(",", ".")), "m" if unit.startswith(("m", "k")) and unit not in ("mi", "miles", "mile") else unit


def _distant_ok(ctx: RuleContext) -> bool:
    """Gittata di almeno 1,5 m (5 piedi) o a contatto."""
    found = _range_of(ctx.spell) if ctx.spell is not None else None
    if found is None:
        return False
    if found == "touch":
        return True
    value, unit = found
    return value >= (1.5 if unit == "m" else 5 if unit in ("ft", "feet", "foot", "piedi") else 0.01)


def _number(value: float) -> str:
    return str(int(value)) if value == int(value) else str(value).replace(".", ",")


def _distant_effect(ctx: RuleContext, _inputs: dict) -> dict:
    found = _range_of(ctx.spell)
    if found == "touch":
        return {"it": "Gittata: 9 m invece del contatto.", "en": "Range: 30 ft instead of touch."}
    value, unit = found
    shown = f"{_number(value * 2)} {unit}"
    return {"it": f"Gittata raddoppiata: {shown}.", "en": f"Range doubled: {shown}."}


def _doubled_rounds(spell: Any) -> int | None:
    rounds = parse_duration_rounds(spell.duration)
    return None if rounds is None or rounds < 10 else min(rounds * 2, MAX_DURATION_ROUNDS)


def _duration_text(rounds: int) -> tuple[str, str]:
    if rounds % 600 == 0:
        hours = rounds // 600
        return f"{hours} {'ora' if hours == 1 else 'ore'}", f"{hours} hour{'s' if hours != 1 else ''}"
    minutes = rounds // 10
    return f"{minutes} {'minuto' if minutes == 1 else 'minuti'}", f"{minutes} minute{'s' if minutes != 1 else ''}"


def _extended_effect(ctx: RuleContext, _inputs: dict) -> dict:
    it, en = _duration_text(_doubled_rounds(ctx.spell))
    return {"it": f"Durata raddoppiata: {it} (al massimo 24 ore).", "en": f"Duration doubled: {en} (24 hours at most)."}


def _extend_concentration(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    """Il contatore della concentrazione di questo lancio raddoppia, fino a 24 ore."""
    settings = ctx.char.settings or {}
    left = settings.get("concentration_rounds_left")
    if ctx.char.concentrating_spell_id == ctx.spell.id and type(left) is int:
        ctx.char.settings = {**settings, "concentration_rounds_left": min(left * 2, MAX_DURATION_ROUNDS)}


def _twinned_ok(ctx: RuleContext) -> bool:
    spell = ctx.spell
    if spell is None or (spell.srd_index or "") in TWINNED_EXCLUDED or (spell.name or "").strip().lower() in TWINNED_EXCLUDED_NAMES:
        return False
    return not (spell.range_area or "").strip().lower().startswith(_SELF)


def _twinned_cost(ctx: RuleContext) -> int:
    return max(1, ctx.spell.level) if ctx.spell is not None else 1


def _mark_twinned(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    """Il secondo bersaglio ha i suoi tiri: il router degli incantesimi li ripete per questo lancio."""
    turn = dict(ctx.char.turn_state or {})
    turn[TWINNED_TURN_KEY] = {"spell_id": ctx.spell.id}
    ctx.char.turn_state = turn


def _quickened(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    """Il lancio vale come azione bonus: non più come incantesimo dell'azione (Magia da Battaglia, Magia da Guerra)."""
    turn = dict(ctx.char.turn_state or {})
    turn["bonus_spell_cast"] = True
    turn.pop("action_spell_level", None)
    turn["action_spell_class"] = None
    ctx.char.turn_state = turn


def _cast_option(key: str, label: dict, cost: int | Cost = 1, **kw: Any) -> RollOptionSpec:
    return RollOptionSpec(key=_meta(key), phase="before", rolls=("cast",), group=ONE_OPTION,
                          cost=cost if isinstance(cost, Cost) else Cost(feature_key=SP, amount=cost), label=label, **kw)


SUBTLE_KEY = _meta("subtle")  # il router degli incantesimi non chiude il nascondiglio con la componente verbale
SUBTLE = _cast_option(
    "subtle", {"it": "Incantesimo Celato: lancia senza componenti somatiche né verbali (1 punto)",
               "en": "Subtle Spell: cast without somatic or verbal components (1 point)"},
    effect=_say("L'incantesimo non ha componenti somatiche né verbali.", "The spell has no somatic or verbal components."))
DISTANT = _cast_option(
    "distant", {"it": "Incantesimo Distante: gittata raddoppiata, a contatto 9 m (1 punto)",
                "en": "Distant Spell: doubled range, touch becomes 30 ft (1 point)"},
    available=_distant_ok, effect=_distant_effect)
EXTENDED = _cast_option(
    "extended", {"it": "Incantesimo Esteso: durata raddoppiata, fino a 24 ore (1 punto)",
                 "en": "Extended Spell: doubled duration, up to 24 hours (1 point)"},
    available=lambda c: c.spell is not None and _doubled_rounds(c.spell) is not None, effect=_extended_effect,
    on_confirm=_extend_concentration)
HEIGHTENED = _cast_option(
    "heightened", {"it": "Incantesimo Intensificato: un bersaglio ha svantaggio al suo primo TS contro l'incantesimo (3 punti)",
                   "en": "Heightened Spell: one target has disadvantage on its first save against the spell (3 points)"},
    cost=3, available=lambda c: c.spell is not None and _save_spell(c.spell),
    effect=_say("Un bersaglio a tua scelta ha svantaggio al primo TS contro questo incantesimo.",
                "One target of your choice has disadvantage on its first saving throw against this spell."),
    target_effect=lambda _c, _i: TargetEffect(condition="custom:heightened_spell"))
CAREFUL = _cast_option(
    "careful", {"it": "Incantesimo Preciso: alcune creature superano da sole il TS (1 punto)",
                "en": "Careful Spell: some creatures automatically pass the save (1 point)"},
    available=lambda c: c.spell is not None and _save_spell(c.spell),
    effect=lambda c, _i: {"it": f"Fino a {max(1, _cha(c))} creature a tua scelta superano da sole il TS e non subiscono danni.",
                          "en": f"Up to {max(1, _cha(c))} creatures of your choice automatically pass the save and take no damage."})
TWINNED = _cast_option(
    "twinned", {"it": "Incantesimo Raddoppiato: l'incantesimo ha un solo bersaglio e non può mirarne di più a questo livello?",
                "en": "Twinned Spell: does the spell target only one creature and cannot target more at this level?"},
    cost=Cost(feature_key=SP, amount_by=_twinned_cost), available=_twinned_ok, on_confirm=_mark_twinned,
    effect=_say("Una seconda creatura entro gittata è bersaglio dell'incantesimo: tiri per colpire e danni sono ripetuti per lei.",
                "A second creature in range is also a target of the spell: attack and damage rolls are repeated for it."))
QUICKENED = _cast_option(
    "quickened", {"it": "Incantesimo Rapido: il lancio di 1 azione diventa un'azione bonus (2 punti)",
                  "en": "Quickened Spell: a 1-action cast becomes a bonus action (2 points)"},
    cost=2, slot="bonus", available=lambda c: c.spell is not None and parse_casting_time(c.spell.casting_time) == "action",
    on_confirm=_quickened, effect=_say("L'incantesimo è lanciato con l'azione bonus.", "The spell is cast with a bonus action."))
EMPOWERED = RollOptionSpec(
    key=_meta("empowered"), phase="after_damage", rolls=("spell_damage",), cost=Cost(feature_key=SP),
    reroll_dice=lambda ctx, _i: max(1, _cha(ctx)),
    label={"it": "Incantesimo Potenziato: ritira fino a un numero di dadi pari al tuo Carisma, minimo 1 (1 punto)",
           "en": "Empowered Spell: reroll up to your Charisma modifier in dice, minimum 1 (1 point)"})


# ---------------------------------------------------------------------------
# Discendenza Draconica
# ---------------------------------------------------------------------------

def _ancestor_type(ctx: RuleContext) -> str | None:
    chosen = ((getattr(ctx.class_row, "options", None) or {}).get(ANCESTOR_GROUP) or [None])[0]
    return DRAGONS[chosen][2] if chosen in DRAGONS else None


def _dragon_label(key: str) -> dict:
    it, en, damage = DRAGONS[key]
    d_it, d_en = _DAMAGE_LABELS[damage]
    return {"name": {"it": f"Drago {it}", "en": f"{en} dragon"},
            "summary": {"it": f"Tipo di danno: {d_it}.", "en": f"Damage type: {d_en}."}}


def _dragon_check(ctx: RuleContext) -> bool:
    """Prova di Carisma con una competenza (la maestria è già doppia): il giocatore conferma che è con un drago."""
    level = (ctx.char.skills or {}).get(ctx.skill)
    return ctx.roll == "skill" and SKILL_ABILITY_MAP.get(ctx.skill) == "charisma" and (level is True or level == 1)


DRAGON_ANCESTOR_CHECK = RollOptionSpec(
    key=f"{CK}.dragon_ancestor_check", phase="before", rolls=("skill",), available=_dragon_check,
    bonus=lambda c, _i: c.char.proficiency_bonus,
    label={"it": "Antenato Draconico: la prova è per interagire con un drago? Il bonus di competenza raddoppia",
           "en": "Dragon Ancestor: is the check to interact with a dragon? Your proficiency bonus doubles"})

AFFINITY_BONUS = RollOptionSpec(
    key=f"{CK}.elemental_affinity", phase="before", rolls=("spell_damage",),
    available=lambda c: c.spell is not None and _ancestor_type(c) is not None
    and canonical_damage_type(c.spell.damage_type) == _ancestor_type(c),
    bonus=lambda c, _i: _cha(c),
    label={"it": "Affinità Elementale: aggiungi il Carisma ai danni del tipo del tuo antenato",
           "en": "Elemental Affinity: add your Charisma modifier to damage of your ancestor's type"})


def _affinity_state(ctx: RuleContext, _params: dict) -> StateSpec:
    return StateSpec("elemental_resistance", rounds=600, ends_on=("manual", "rest_short", "rest_long"),
                     data={"damage_type": _ancestor_type(ctx), "others": [f"{CK}.elemental_affinity_resistance"]})


def _affinity_resistance(damage_type: str) -> Modifier:
    def active(ctx: RuleContext) -> bool:
        state = next((s for s in ctx.char.active_states or [] if s.get("key") == "elemental_resistance"), None)
        return state is not None and (state.get("data") or {}).get("damage_type") == damage_type
    return Modifier(f"resistance:{damage_type}", 1, when=active, source=f"feature:{CK}.elemental_affinity_resistance")


def _wears_armor(ctx: RuleContext) -> bool:
    return any(i.is_equipped and i.item_type == "armor" for i in ctx.char.items or [])


DRAGON_WINGS_USE = OnUse(
    slot="bonus", available=lambda c: not _wears_armor(c),
    state=StateSpec("dragon_wings", ends_on=("manual",), end_slot="bonus", data={"others": [f"{CK}.dragon_wings"]}))


def _presence_state(ctx: RuleContext, params: dict) -> StateSpec:
    return StateSpec("draconic_presence", rounds=10, ends_on=("concentration_end", "manual"),
                     data={"dc": _dc(ctx), "save": "wisdom", "mode": params.get("mode"), "others": [f"{CK}.draconic_presence"]})


def _presence_target(ctx: RuleContext, params: dict) -> TargetEffect:
    return TargetEffect(condition="charmed" if params.get("mode") == "awe" else "frightened", save_ability="wisdom",
                        save_dc=_dc(ctx), rounds=10, immune_on_success=True)


PRESENCE_USE = OnUse(
    slot="action", spends=SP, cost=5, concentration=True, state=_presence_state, target_effect=_presence_target,
    choices=(UseChoice("mode", {"it": "Aura", "en": "Aura"}, lambda _c: ["awe", "fear"],
                       lambda k: {"it": "Soggezione (affascinate)", "en": "Awe (charmed)"} if k == "awe"
                       else {"it": "Paura (spaventate)", "en": "Fear (frightened)"}),))


# ---------------------------------------------------------------------------
# Magia Selvaggia
# ---------------------------------------------------------------------------

TIDES = f"{CK}.tides_of_chaos"
TIDES_ADVANTAGE = RollOptionSpec(
    key=f"{CK}.tides_of_chaos_advantage", phase="before", rolls=("attack", "skill", "save"), mode="advantage", cost=Cost(feature_key=TIDES),
    label={"it": "Onde di Caos: tira questo attacco, prova o TS con vantaggio", "en": "Tides of Chaos: make this attack, check or save with advantage"})

BEND_LUCK_USE = OnUse(
    slot="reaction", spends=SP, cost=2, rolls="1d4", notes=lambda _c, params: [f"bend_luck_{params['sign']}"],
    choices=(UseChoice("sign", {"it": "Il d4 è un bonus o una penalità", "en": "The d4 is a bonus or a penalty"},
                       lambda _c: ["plus", "minus"],
                       lambda k: {"it": "Bonus al tiro", "en": "Bonus to the roll"} if k == "plus"
                       else {"it": "Penalità al tiro", "en": "Penalty to the roll"}),))

BOMBARDMENT = RollOptionSpec(
    key=f"{CK}.spell_bombardment", phase="after_damage", rolls=("spell_damage",), reroll_dice=lambda _c, _i: 1, keep_rolled=True,
    once_per_turn=True,
    label={"it": "Bombardamento Magico: ritira un dado di danno che mostra il massimo e somma il nuovo risultato",
           "en": "Spell Bombardment: reroll a damage die showing its maximum and add the new result"})

SURGE = f"{CK}.wild_magic_surge"


def _regeneration(ctx: RuleContext) -> int:
    return 5 if state_on(ctx, "wild_regeneration") else 0


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

def _draconic(key: str, level: int, title: str, name: tuple[str, str], summary: tuple[str, str], action_type: str | None = None, **kw: Any):
    return feature(key, CK, ED, level, title, name, summary, action_type, subclass="draconic", **kw)


def _wild(key: str, level: int, title: str, name: tuple[str, str], summary: tuple[str, str], action_type: str | None = None, **kw: Any):
    return feature(key, CK, ED, level, title, name, summary, action_type, subclass="wild_magic", **kw)


def _option_row(key: str, it: str, en: str, summary: tuple[str, str], roll_options: tuple) -> Any:
    return feature(f"metamagic_{key}", CK, ED, 3, f"{it} / {en} (Stregone 3, pag. 110)", (it, en), summary,
                   option_group=METAMAGIC_GROUP, option_key=key, roll_options=roll_options, passive=True)


_OPTION_SUMMARIES = {
    "subtle": ("Al lancio, 1 punto: nessuna componente somatica né verbale.", "On the cast, 1 point: no somatic or verbal components."),
    "distant": ("Al lancio, 1 punto: gittata raddoppiata; a contatto diventa 9 m. Serve una gittata di almeno 1,5 m.",
                "On the cast, 1 point: doubled range; touch becomes 30 ft. Needs a range of at least 5 ft."),
    "extended": ("Al lancio, 1 punto: durata raddoppiata, al massimo 24 ore. Solo durate di almeno un minuto.",
                 "On the cast, 1 point: doubled duration, 24 hours at most. Only durations of at least one minute."),
    "heightened": ("Al lancio, 3 punti: un bersaglio ha svantaggio al primo TS contro l'incantesimo.",
                   "On the cast, 3 points: one target has disadvantage on its first save against the spell."),
    "empowered": ("Dopo il danno, 1 punto: ritiri fino a Carisma dadi (minimo 1). Si somma a un'altra opzione.",
                  "After the damage, 1 point: reroll up to Charisma dice (minimum 1). It adds to another option."),
    "careful": ("Al lancio, 1 punto: fino a Carisma creature (minimo 1) superano da sole il TS dell'incantesimo.",
                "On the cast, 1 point: up to Charisma creatures (minimum 1) automatically pass the spell's save."),
    "twinned": ("Al lancio, punti pari al livello dell'incantesimo (1 se trucchetto): un secondo bersaglio per un incantesimo a bersaglio singolo.",
                "On the cast, points equal to the spell's level (1 for a cantrip): a second target for a single-target spell."),
    "quickened": ("Al lancio, 2 punti: un incantesimo di 1 azione si lancia con un'azione bonus.",
                  "On the cast, 2 points: a spell with a casting time of 1 action is cast as a bonus action."),
}
_OPTION_ROLLS = {"subtle": (SUBTLE,), "distant": (DISTANT,), "extended": (EXTENDED,), "heightened": (HEIGHTENED,),
                 "empowered": (EMPOWERED,), "careful": (CAREFUL,), "twinned": (TWINNED,), "quickened": (QUICKENED,)}


FEATURES = (
    feature("hit_points", CK, ED, 1, "Punti Ferita / Hit Points (Stregone 1, pag. 108)", ("Punti Ferita", "Hit Points"),
            ("Dado vita d6; al 1° livello 6 + Costituzione, poi d6 (o 4) + Costituzione.",
             "Hit die d6; level 1 gives 6 + Constitution, then d6 (or 4) + Constitution."), no_row=True,
            covered_by="api/routers/classes.py create_class_for_character e total_base_hp; test_hit_points_use_the_d6_and_follow_constitution"),
    feature("proficiencies", CK, ED, 1, "Competenze / Proficiencies (Stregone 1, pag. 108)", ("Competenze", "Proficiencies"),
            ("Pugnali, dardi, fionde, bastoni ferrati, balestre leggere; TS Costituzione e Carisma; 2 abilità fra Arcano, Inganno, Intuizione, Intimidire, Persuasione, Religione.",
             "Daggers, darts, slings, quarterstaffs, light crossbows; Constitution and Charisma saves; 2 skills from Arcana, Deception, Insight, Intimidation, Persuasion, Religion."),
            no_row=True, covered_by="core/rules/proficiencies.py (class_proficiencies) e la scelta ClassSkillChoice; "
                                    "test_class_proficiencies_first_class_and_multiclass"),
    feature("equipment", CK, ED, 1, "Equipaggiamento / Equipment (Stregone 1, pag. 109)", ("Equipaggiamento", "Equipment"),
            ("Dotazione iniziale: balestra leggera e 20 quadrelli o un'arma semplice, borsa componenti o focus arcano, dotazione a scelta, due pugnali.",
             "Starting gear: a light crossbow and 20 bolts or a simple weapon, a component pouch or arcane focus, a pack of your choice, two daggers."),
            no_row=True, covered_by="lavori-successivi"),
    feature("spellcasting", CK, ED, 1, "Incantesimi / Spellcasting (Stregone 1, pag. 109)", ("Incantesimi", "Spellcasting"),
            ("Incantatore pieno con Carisma. Trucchetti 4 (5 al 4°, 6 al 10°); conosciuti da 2 a 15, lista fissa; focus arcano. CD 8 + competenza + Carisma.",
             "Full caster with Charisma. Cantrips 4 (5 at 4th, 6 at 10th); known spells 2 to 15, fixed list; arcane focus. DC 8 + proficiency + Charisma."),
            no_row=True, covered_by="core/rules/spellcasting.py (known_limits, slots_for, caster_stats); "
                                    "test_slots_cantrips_and_known_follow_the_table"),
    feature("sorcerous_origin", CK, ED, 1, "Origine Stregonesca / Sorcerous Origin (Stregone 1, pag. 109)",
            ("Origine Stregonesca", "Sorcerous Origin"),
            ("Al 1° livello si sceglie Discendenza Draconica o Magia Selvaggia: privilegi ai livelli 1, 6, 14 e 18.",
             "At 1st level you choose Draconic Bloodline or Wild Magic: features at levels 1, 6, 14 and 18."),
            no_row=True, covered_by="core/rules/subclasses.py (match_subclass) e il campo sottoclasse della classe"),
    feature("sorcery_points", CK, ED, 2, "Fonte di Magia / Font of Magic (Stregone 2, pag. 109)", ("Punti Stregoneria", "Sorcery Points"),
            ("Punti stregoneria pari al tuo livello da stregone (da 2 a 20): tornano con un riposo lungo. Dal 20° livello 4 tornano anche con un riposo breve.",
             "Sorcery points equal to your sorcerer level (2 to 20): they return on a long rest. From 20th level 4 also return on a short rest."),
            uses=Uses(table={lv: lv for lv in range(2, 21)}), restoration="long_rest", short_rest_recovers={20: 4}),
    feature("flexible_casting_create", CK, ED, 2,
            "Incantesimi Flessibili: Creare Slot Incantesimo / Flexible Casting: Creating Spell Slots (Stregone 2, pag. 109)",
            ("Incantesimi Flessibili: Creare Slot", "Flexible Casting: Creating Slots"),
            ("Azione bonus: spendi punti stregoneria per uno slot di 1°-5° livello (2, 3, 5, 6, 7 punti). Lo slot creato svanisce con un riposo lungo.",
             "Bonus action: spend sorcery points for a 1st-5th level slot (2, 3, 5, 6, 7 points). The created slot vanishes on a long rest."),
            "bonus_action", on_use=CREATE_USE),
    feature("flexible_casting_convert", CK, ED, 2,
            "Incantesimi Flessibili: Convertire uno Slot in Punti / Flexible Casting: Converting a Spell Slot to Sorcery Points (Stregone 2, pag. 109)",
            ("Incantesimi Flessibili: Convertire uno Slot", "Flexible Casting: Converting a Slot"),
            ("Azione bonus: spendi uno slot libero e ottieni tanti punti stregoneria quanto il suo livello, senza superare il massimo.",
             "Bonus action: spend an unused slot and gain sorcery points equal to its level, without exceeding the maximum."),
            "bonus_action", on_use=CONVERT_USE),
    feature("metamagic", CK, ED, 3, "Metamagia / Metamagic (Stregone 3, pag. 109)", ("Metamagia", "Metamagic"),
            ("Due opzioni di Metamagia al 3° livello, una in più al 10° e al 17°. Al lancio se ne usa una sola per incantesimo, salvo Potenziato.",
             "Two Metamagic options at 3rd level, one more at 10th and 17th. One option per spell on the cast, except Empowered."),
            no_row=True, choices=(ChoiceSpec(group=METAMAGIC_GROUP, levels={3: 2, 10: 3, 17: 4}, replaceable=True,
                                             options=lambda _c: [k for k, _it, _en in METAMAGIC]),),
            covered_by="ChoiceSpec metamagic di questa riga e le righe delle otto opzioni; test_metamagic_options_known_follow_the_level"),
    *(_option_row(k, it, en, _OPTION_SUMMARIES[k], _OPTION_ROLLS[k]) for k, it, en in METAMAGIC),
    feature("ability_score_improvement", CK, ED, 4, "Aumento dei Punteggi di Caratteristica / Ability Score Improvement (Stregone 4, pag. 110)",
            ("Aumento dei Punteggi di Caratteristica", "Ability Score Improvement"),
            ("Ai livelli 4, 8, 12, 16 e 19: +2 a un punteggio o +1 a due, oppure un talento; massimo 20.",
             "At levels 4, 8, 12, 16 and 19: +2 to one score or +1 to two, or a feat; maximum 20."), no_row=True,
            covered_by="core/rules/level_choices.py (scelta asi); test_asi_choices_are_pending_at_levels_4_8_12_16_and_19"),
    feature("sorcerous_restoration", CK, ED, 20, "Ripristino Stregonesco / Sorcerous Restoration (Stregone 20, pag. 110)",
            ("Ripristino Stregonesco", "Sorcerous Restoration"),
            ("Con un riposo breve recuperi 4 punti stregoneria spesi, senza superare il massimo.",
             "On a short rest you regain 4 spent sorcery points, without exceeding the maximum."), no_row=True,
            covered_by="short_rest_recovers={20: 4} sulla riga sorcerer.sorcery_points; "
                       "test_sorcerous_restoration_gives_back_up_to_four_points_on_a_short_rest_from_level_20"),

    # Discendenza Draconica
    _draconic("dragon_ancestor", 1, "Antenato Draconico / Dragon Ancestor (Discendenza Draconica 1, pag. 110)",
              ("Antenato Draconico", "Dragon Ancestor"),
              ("Scegli un drago: il suo tipo di danno vale per Affinità Elementale. Conosci il Draconico; con i draghi il bonus di competenza raddoppia nelle prove di Carisma.",
               "Choose a dragon: its damage type applies to Elemental Affinity. You know Draconic; with dragons your proficiency bonus doubles on Charisma checks."),
              no_row=True, roll_options=(DRAGON_ANCESTOR_CHECK,),
              choices=(ChoiceSpec(group=ANCESTOR_GROUP, levels={1: 1}, options=lambda _c: list(DRAGONS), label=_dragon_label,
                                  adds_language=("Draconico", "Draconic"), listed=True),),
              covered_by="ChoiceSpec dragon_ancestor di questa riga; test_the_ancestor_is_one_of_ten_dragons_chosen_at_level_1_and_only_by_the_draconic_bloodline"),
    _draconic("draconic_resilience", 1, "Resilienza Draconica / Draconic Resilience (Discendenza Draconica 1, pag. 110)",
              ("Resilienza Draconica", "Draconic Resilience"),
              ("+1 PF massimo per livello da stregone. Senza armatura la CA è 13 + Destrezza.",
               "+1 maximum hit point per sorcerer level. Without armor your AC is 13 + Dexterity."),
              modifiers=(Modifier("hp_max", lambda c: c.class_level, source=f"feature:{CK}.draconic_resilience"),),
              unarmored=UnarmoredAc(("dexterity",), base=13), passive=True),
    _draconic("elemental_affinity", 6, "Affinità Elementale / Elemental Affinity (Discendenza Draconica 6, pag. 111)",
              ("Affinità Elementale", "Elemental Affinity"),
              ("Con un incantesimo del tipo del tuo antenato aggiungi Carisma a un tiro di danno. 1 punto: resistenza a quel tipo per 1 ora.",
               "With a spell of your ancestor's type add Charisma to one damage roll. 1 point: resistance to that type for 1 hour."),
              roll_options=(AFFINITY_BONUS,), passive=True),
    _draconic("elemental_affinity_resistance", 6, "Affinità Elementale / Elemental Affinity (Discendenza Draconica 6, pag. 111)",
              ("Affinità Elementale: Resistenza", "Elemental Affinity: Resistance"),
              ("Spendi 1 punto stregoneria: resistenza al tipo di danno del tuo antenato per 1 ora.",
               "Spend 1 sorcery point: resistance to your ancestor's damage type for 1 hour."),
              "special", on_use=OnUse(spends=SP, cost=1, state=_affinity_state,
                                      available=lambda c: _ancestor_type(c) is not None),
              modifiers=tuple(_affinity_resistance(t) for t in ("cold", "lightning", "acid", "fire", "poison"))),
    _draconic("dragon_wings", 14, "Ali di Drago / Dragon Wings (Discendenza Draconica 14, pag. 111)", ("Ali di Drago", "Dragon Wings"),
              ("Azione bonus: ali con velocità di volo pari alla velocità attuale, finché non le congedi (azione bonus). Non con un'armatura indossata.",
               "Bonus action: wings with a flying speed equal to your current speed until you dismiss them (bonus action). Not while wearing armor."),
              "bonus_action", on_use=DRAGON_WINGS_USE,
              modifiers=(Modifier("fly_speed", 1, when=lambda c: state_on(c, "dragon_wings"), source=f"feature:{CK}.dragon_wings"),)),
    _draconic("draconic_presence", 18, "Presenza Draconica / Draconic Presence (Discendenza Draconica 18, pag. 111)",
              ("Presenza Draconica", "Draconic Presence"),
              ("Azione, 5 punti: aura di 18 m per 1 minuto, in concentrazione. Le creature ostili fanno un TS Saggezza o sono affascinate o spaventate; chi supera è immune 24 ore.",
               "Action, 5 points: 60 ft aura for 1 minute, concentration. Hostile creatures make a Wisdom save or are charmed or frightened; a success grants 24 hours of immunity."),
              "action", on_use=PRESENCE_USE, dc_ability="charisma"),

    # Magia Selvaggia
    _wild("wild_magic_surge", 1, "Impulso di Magia Selvaggia / Wild Magic Surge (Magia Selvaggia 1, pag. 111)",
          ("Impulso di Magia Selvaggia", "Wild Magic Surge"),
          ("Se il GM lo chiede dopo un incantesimo di 1° livello o più: d20 una volta per turno; con 1 tiri sulla tabella dei 50 impulsi e l'app applica gli effetti.",
           "When the GM asks after a spell of 1st level or higher: a d20 once per turn; on a 1 you roll the 50-result table and the app applies the effects."),
          "special", on_use=OnUse(panel="wild_magic"), turn_start_heal=_regeneration, dc_ability="charisma",
          modifiers=(Modifier("ac", 2, when=lambda c: state_on(c, "wild_shield"), source=f"feature:{CK}.wild_magic_surge"),
                     Modifier("resistance:all", 1, when=lambda c: state_on(c, "wild_resistance"), source=f"feature:{CK}.wild_magic_surge"))),
    _wild("tides_of_chaos", 1, "Onde di Caos / Tides of Chaos (Magia Selvaggia 1, pag. 111)", ("Onde di Caos", "Tides of Chaos"),
          ("Un uso: un attacco, una prova o un TS con vantaggio. Torna con un riposo lungo, o quando il GM ti fa tirare un impulso.",
           "One use: an attack, check or save with advantage. It returns on a long rest, or when the GM has you roll a surge."),
          uses=Uses(table={1: 1}), restoration="long_rest", roll_options=(TIDES_ADVANTAGE,)),
    _wild("bend_luck", 6, "Piegare la Fortuna / Bend Luck (Magia Selvaggia 6, pag. 111)", ("Piegare la Fortuna", "Bend Luck"),
          ("Reazione, 2 punti: tira 1d4 e applicalo come bonus o penalità al tiro di un'altra creatura che vedi.",
           "Reaction, 2 points: roll 1d4 and apply it as a bonus or penalty to another creature's roll that you can see."),
          "reaction", on_use=BEND_LUCK_USE),
    _wild("controlled_chaos", 14, "Caos Controllato / Controlled Chaos (Magia Selvaggia 14, pag. 111)", ("Caos Controllato", "Controlled Chaos"),
          ("Sulla tabella degli impulsi tiri due volte e scegli il risultato.", "On the surge table you roll twice and choose the result."),
          passive=True),
    _wild("spell_bombardment", 18, "Bombardamento Magico / Spell Bombardment (Magia Selvaggia 18, pag. 111)",
          ("Bombardamento Magico", "Spell Bombardment"),
          ("Una volta per turno, se un dado di danno di un incantesimo mostra il massimo, lo ritiri e sommi il nuovo risultato.",
           "Once per turn, if a spell damage die shows its maximum, reroll it and add the new result."),
          roll_options=(BOMBARDMENT,), passive=True),

    feature("multiclassing", CK, ED, 1, "Multiclasse: Stregone / Multiclassing: Sorcerer (Multiclasse, pag. 163)",
            ("Multiclasse: Stregone", "Multiclassing: Sorcerer"),
            ("Requisito Carisma 13. Nessuna competenza da multiclasse; i livelli da stregone contano per intero negli slot.",
             "Requires Charisma 13. No proficiencies as a multiclass; sorcerer levels count in full toward slots."),
            no_row=True, covered_by="core/rules/proficiencies.py (as_multiclass) e webapp/src/data/multiclassPrereqs.ts (D2); "
                                    "test_sorcery_points_depend_only_on_sorcerer_levels"),
)

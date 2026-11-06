"""Ranger 2014 e i suoi archetipi: Cacciatore e Signore delle Bestie.

Valori dalla scheda ``docs/superpowers/rules/2014/classes/ranger.md``; i testi sono nostri, mai quelli del manuale.
Nemici prescelti, terreni, stile di combattimento e le scelte del Cacciatore sono opzioni di una ``ChoiceSpec``: ciò che il
catalogo scrive su una scheda è la sola opzione scelta. Il compagno del Signore delle Bestie vive nella tabella dei compagni
(``core/rules/companions.py``, ordini e Dadi Vita in ``api/routers/companions.py``).
"""
from __future__ import annotations

from typing import Any

from core.rules.catalog._common import attacks_made, feature, state_on, style_options
from core.rules.catalog.y2014.cleric import LANGUAGES, _languages_owned, language_label
from core.rules.catalog.y2014.fighter import _is_ranged_weapon, _off_hand_modifier, _dueling, _weapon_in_hand, _wears_armor
from core.rules.states import begin_state
from core.rules.types import ChoiceSpec, Cost, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, UseChoice, UseToggle

ED, CK = "2014", "ranger"
ENEMY, ENEMY_LANGUAGE, TERRAIN = "favored_enemy", "favored_enemy_language", "favored_terrain"
STYLES = ("archery", "defense", "dueling", "two_weapon")
EVASION_STATE = "evasion"
SLAYER_GROUP = "foe_slayer"

# (chiave, it, en): i tipi di nemico, e «due razze di umanoidi» come una sola opzione (la scelta delle razze è col GM)
ENEMIES = (
    ("aberrations", "Aberrazioni", "Aberrations"), ("beasts", "Bestie", "Beasts"), ("celestials", "Celestiali", "Celestials"),
    ("constructs", "Costrutti", "Constructs"), ("dragons", "Draghi", "Dragons"), ("elementals", "Elementali", "Elementals"),
    ("fey", "Folletti", "Fey"), ("giants", "Giganti", "Giants"), ("fiends", "Immondi", "Fiends"), ("oozes", "Melme", "Oozes"),
    ("monstrosities", "Mostruosità", "Monstrosities"), ("undead", "Non morti", "Undead"), ("plants", "Vegetali", "Plants"),
    ("humanoids", "Due razze di umanoidi", "Two humanoid races"),
)
TERRAINS = (
    ("arctic", "Artico", "Arctic"), ("coast", "Costa", "Coast"), ("desert", "Deserto", "Desert"), ("forest", "Foresta", "Forest"),
    ("mountain", "Montagna", "Mountain"), ("swamp", "Palude", "Swamp"), ("grassland", "Prateria", "Grassland"),
    ("underdark", "Underdark", "Underdark"),
)
NONE_LANGUAGES = ("none_1", "none_2", "none_3")  # una per nemico: «nessun linguaggio» non si può scegliere due volte di fila


def _label(table: tuple[tuple[str, str, str], ...], summary: tuple[str, str]):
    names = {k: (it, en) for k, it, en in table}

    def label(key: str) -> dict:
        it, en = names[key]
        return {"name": {"it": it, "en": en}, "summary": {"it": summary[0], "en": summary[1]}}
    return label


def _keys(table: tuple[tuple[str, str, str], ...]):
    return lambda _ctx: [k for k, _it, _en in table]


def _language_options(ctx: RuleContext) -> list[str]:
    """La prima «nessun linguaggio» non ancora usata, poi le lingue che la scheda non ha già (R39 per chi ne ha)."""
    chosen = (getattr(ctx.class_row, "options", None) or {}).get(ENEMY_LANGUAGE, [])
    skip = next((k for k in NONE_LANGUAGES if k not in chosen), None)
    owned = set(_languages_owned(ctx))
    return [*([skip] if skip else []), *(k for k in LANGUAGES if k not in owned)]


def _language_label(key: str) -> dict:
    if key in NONE_LANGUAGES:
        return {"name": {"it": "Nessun linguaggio", "en": "No language"},
                "summary": {"it": "Il nemico non parla un linguaggio: nulla da aggiungere.",
                            "en": "The enemy speaks no language: nothing to add."}, "skip": True}
    return language_label(key)


def _wis_mod(ctx: RuleContext) -> int:
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    return effective_ability_mod(ctx.char, "wisdom")


def _say(it: str, en: str):
    return lambda _ctx, _inputs: {"it": it, "en": en}


def _permanent_note(key: str) -> StateSpec:
    """Lo stato sempre attivo che porta il testo di un privilegio a GM e gruppo (R36)."""
    return StateSpec(key, ends_on=("manual",), data={"others": [f"{CK}.{key}"], "permanent": True})


def _weapon_attack(ctx: RuleContext) -> bool:
    return _weapon_in_hand(ctx)


def _melee_weapon(ctx: RuleContext) -> bool:
    return _weapon_in_hand(ctx) and ctx.attack_mode in ("melee", "offhand")


def _ranged_weapon(ctx: RuleContext) -> bool:
    return _weapon_in_hand(ctx) and ctx.attack_mode in ("ranged", "thrown")


# ---------------------------------------------------------------------------
# Nemico Prescelto, Esploratore Nato
# ---------------------------------------------------------------------------

FAVORED_ENEMY_ADVANTAGE = RollOptionSpec(
    key=f"{CK}.favored_enemy_advantage", phase="before", rolls=("skill",), mode="advantage",
    available=lambda c: c.skill == "survival" or c.ability == "intelligence",
    label={"it": "Nemico Prescelto: segui le tracce di un tuo nemico prescelto o ricordi informazioni su di lui? Vantaggio",
           "en": "Favored Enemy: are you tracking a favored enemy or recalling information about it? Advantage"})


def _proficient_not_expert(ctx: RuleContext) -> bool:
    level = (ctx.char.skills or {}).get(ctx.skill)
    return level is True or level == 1  # con la maestria la competenza è già doppia: il raddoppio non si somma


NATURAL_EXPLORER_DOUBLE = RollOptionSpec(
    key=f"{CK}.natural_explorer_double", phase="before", rolls=("skill",), bonus=lambda c, _i: c.char.proficiency_bonus,
    available=lambda c: bool(c.skill) and c.ability in ("intelligence", "wisdom") and _proficient_not_expert(c),
    label={"it": "Esploratore Nato: la prova riguarda il tuo terreno prescelto? Il bonus di competenza vale il doppio",
           "en": "Natural Explorer: is the check about your favored terrain? Your proficiency bonus is doubled"},
    effect=_say("Il bonus di competenza vale il doppio: il bonus in più è già nel totale.",
                "Your proficiency bonus is doubled: the extra bonus is already in the total."))


# ---------------------------------------------------------------------------
# Stile di Combattimento
# ---------------------------------------------------------------------------

def _style(key: str, title: str, name: tuple[str, str], summary: tuple[str, str], **kw: Any):
    return feature(f"style_{key}", CK, ED, 2, title, name, summary, option_group="fighting_style", option_key=key, **kw)


STYLE_ROWS = (
    _style("two_weapon", "Combattere con Due Armi / Two-Weapon Fighting (Ranger 2, pag. 104)",
           ("Combattere con Due Armi", "Two-Weapon Fighting"),
           ("Il danno dell'attacco con la seconda arma include il modificatore di caratteristica.",
            "The damage of the attack with the second weapon includes the ability modifier."),
           modifiers=(Modifier("damage", _off_hand_modifier, when=lambda c: c.roll == "damage" and c.offhand and _weapon_in_hand(c),
                               source=f"feature:{CK}.style_two_weapon"),)),
    _style("defense", "Difesa / Defense (Ranger 2, pag. 104)", ("Difesa", "Defense"),
           ("+1 alla CA finché indossi un'armatura (lo scudo da solo non basta).",
            "+1 to AC while you wear armor (a shield alone does not count)."),
           modifiers=(Modifier("ac", 1, when=lambda c: c.roll == "ac" and _wears_armor(c), source=f"feature:{CK}.style_defense"),)),
    _style("dueling", "Duellare / Dueling (Ranger 2, pag. 104)", ("Duellare", "Dueling"),
           ("+2 al danno con un'arma da mischia impugnata a una mano, se non impugni altre armi (lo scudo va bene).",
            "+2 damage with a melee weapon held in one hand when you hold no other weapon (a shield is fine)."),
           modifiers=(Modifier("damage", 2, when=_dueling, source=f"feature:{CK}.style_dueling"),)),
    _style("archery", "Tiro / Archery (Ranger 2, pag. 104)", ("Tiro", "Archery"),
           ("+2 ai tiri per colpire con armi a distanza (non con quelle da lancio da mischia).",
            "+2 to attack rolls with ranged weapons (not with melee weapons you throw)."),
           modifiers=(Modifier("attack", 2, when=lambda c: c.roll == "attack" and _is_ranged_weapon(c),
                               source=f"feature:{CK}.style_archery"),)),
)


# ---------------------------------------------------------------------------
# Consapevolezza Primordiale
# ---------------------------------------------------------------------------

def _free_slot_levels(ctx: RuleContext) -> list[str]:
    from core.rules.roll_options import slot_choices  # import locale: roll_options usa il catalogo
    return [str(level) for level in slot_choices(ctx.char, 1)]


def _awareness_state(_ctx: RuleContext, params: dict) -> StateSpec:
    """Un minuto (10 round) per livello dello slot speso; 9 km nel terreno prescelto, altrimenti 1,5 km."""
    return StateSpec("primeval_awareness", rounds=10 * int(params["slot_level"]), ends_on=("manual", "rest_short", "rest_long"),
                     data={"radius_km": 9 if params.get("terrain") else 1.5})


PRIMEVAL_AWARENESS_USE = OnUse(
    slot="action", spends_slot="slot_level", state=_awareness_state, notes=lambda _c, _p: ["primeval_awareness"],
    choices=(UseChoice("slot_level", {"it": "Livello dello slot da spendere", "en": "Slot level to spend"}, _free_slot_levels,
                       lambda k: {"it": f"Slot di {k}° livello", "en": f"Level {k} slot"}),),
    toggles=(UseToggle("terrain", {"it": "Sei nel tuo terreno prescelto? (raggio 9 km)", "en": "Are you in your favored terrain? (9 km radius)"}),))


# ---------------------------------------------------------------------------
# Dal 5° livello
# ---------------------------------------------------------------------------

LANDS_STRIDE_SAVE = RollOptionSpec(
    key=f"{CK}.lands_stride", phase="before", rolls=("save",), mode="advantage",
    label={"it": "Andatura sul Territorio: l'effetto è una pianta creata o manipolata con la magia per ostacolare il movimento? Vantaggio",
           "en": "Land's Stride: is it a plant magically created or manipulated to impede movement? Advantage"})

HIDE_STEALTH = RollOptionSpec(
    key=f"{CK}.hide_in_plain_sight_stealth", phase="before", rolls=("skill",), bonus=lambda _c, _i: 10,
    available=lambda c: c.skill == "stealth" and state_on(c, "camouflaged"),
    label={"it": "Nascondersi in Piena Vista: sei fermo contro una superficie solida, senza muoverti né agire? +10 a Furtività",
           "en": "Hide in Plain Sight: are you still against a solid surface, without moving or acting? +10 to Stealth"})

FERAL_SENSES = RollOptionSpec(
    key=f"{CK}.feral_senses", phase="before", rolls=("attack",), cancels=("condition:blinded",),
    label={"it": "Sensi Ferini: attacchi una creatura entro 9 m che non vedi? Non vederla non ti dà svantaggio",
           "en": "Feral Senses: are you attacking a creature within 30 ft that you cannot see? Not seeing it gives no disadvantage"},
    effect=_say("Sensi Ferini: non vedere il bersaglio non ti dà svantaggio al tiro per colpire. Le altre fonti di svantaggio restano: "
                "non scegliere svantaggio solo per questo.",
                "Feral Senses: not seeing the target gives no disadvantage on the attack roll. Other sources of disadvantage "
                "remain: do not pick disadvantage for this alone."))


def _slayer_ready(ctx: RuleContext) -> bool:
    return _wis_mod(ctx) > 0


def _slayer_bonus(ctx: RuleContext, _inputs: dict) -> int:
    return _wis_mod(ctx)


FOE_SLAYER_ATTACK = RollOptionSpec(
    key=f"{CK}.foe_slayer_attack", phase="before", rolls=("attack",), group=SLAYER_GROUP, once_per_turn=True,
    bonus=_slayer_bonus, available=_slayer_ready,
    label={"it": "Sterminatore di Nemici: il bersaglio è un tuo nemico prescelto? Somma la Saggezza al tiro per colpire (una volta per turno)",
           "en": "Foe Slayer: is the target a favored enemy? Add your Wisdom to the attack roll (once per turn)"})
FOE_SLAYER_ATTACK_LATE = RollOptionSpec(
    key=f"{CK}.foe_slayer_attack_late", phase="after_roll", after="add", rolls=("attack",), group=SLAYER_GROUP, once_per_turn=True,
    bonus=_slayer_bonus, available=_slayer_ready,
    label={"it": "Sterminatore di Nemici: dopo aver visto il d20, somma la Saggezza al tiro per colpire contro un nemico prescelto",
           "en": "Foe Slayer: after seeing the d20, add your Wisdom to the attack roll against a favored enemy"})
FOE_SLAYER_DAMAGE = RollOptionSpec(
    key=f"{CK}.foe_slayer_damage", phase="after_hit", rolls=("attack",), group=SLAYER_GROUP, once_per_turn=True,
    bonus=_slayer_bonus, available=_slayer_ready,
    label={"it": "Sterminatore di Nemici: il bersaglio è un tuo nemico prescelto? Somma la Saggezza al danno (una volta per turno)",
           "en": "Foe Slayer: is the target a favored enemy? Add your Wisdom to the damage (once per turn)"})


# ---------------------------------------------------------------------------
# Cacciatore
# ---------------------------------------------------------------------------

COLOSSUS_SLAYER = RollOptionSpec(
    key=f"{CK}.colossus_slayer", phase="after_hit", rolls=("attack",), once_per_turn=True, extra_dice=lambda _c, _i: "1d8",
    available=_weapon_attack,
    label={"it": "Sterminatore di Colossi: il bersaglio è sotto il massimo dei PF? +1d8 danni (una volta per turno)",
           "en": "Colossus Slayer: is the target below its hit point maximum? +1d8 damage (once per turn)"})

HORDE_BREAKER = RollOptionSpec(
    key=f"{CK}.horde_breaker", phase="before", rolls=("attack",), once_per_turn=True, outside_action=True,
    available=lambda c: _weapon_attack(c) and attacks_made(c) >= 1,
    label={"it": "Devastatore dell'Orda: un altro attacco con la stessa arma contro una creatura diversa entro 1,5 m dal primo bersaglio",
           "en": "Horde Breaker: another attack with the same weapon against a different creature within 5 ft of the first target"},
    effect=_say("Attacco in più, fuori dall'azione Attacco: un bersaglio diverso entro 1,5 m dal primo, con la stessa arma e nella sua gittata.",
                "An extra attack outside the Attack action: a different target within 5 ft of the first, with the same weapon and within its range."))

GIANT_KILLER = RollOptionSpec(
    key=f"{CK}.giant_killer", phase="before", rolls=("attack",), slot="reaction", offered_on_damage=False, available=_weapon_attack,
    label={"it": "Uccisore di Giganti: una creatura Grande o più grande entro 1,5 m, che vedi, ti ha colpito o mancato? Reazione: attaccala",
           "en": "Giant Killer: did a Large or larger creature you can see within 5 ft hit or miss you? Reaction: attack it"})

MULTIATTACK_DEFENSE_ID = f"{CK}.multiattack_defense"


def _multiattack_defense_started(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    begin_state(ctx.char, StateSpec("multiattack_defense", rounds=1, ends_on=("new_turn", "turn_end", "manual"),
                                    data={"ac_bonus": 4, "others": [MULTIATTACK_DEFENSE_ID]}), MULTIATTACK_DEFENSE_ID,
                "Difesa dal Multiattacco")


MULTIATTACK_DEFENSE = RollOptionSpec(
    key=MULTIATTACK_DEFENSE_ID, phase="damage_in", rolls=("damage_taken",), on_confirm=_multiattack_defense_started,
    label={"it": "Difesa dal Multiattacco: ti ha colpito una creatura? +4 alla CA contro i suoi attacchi per il resto del turno",
           "en": "Multiattack Defense: did a creature hit you? +4 to AC against its attacks for the rest of the turn"},
    effect=_say("+4 alla CA contro i prossimi attacchi di quella creatura, fino alla fine del turno: la CA mostrata lo include.",
                "+4 to AC against that creature's next attacks until the end of the turn: the AC shown includes it."))

STEEL_WILL = RollOptionSpec(
    key=f"{CK}.steel_will", phase="before", rolls=("save",), mode="advantage",
    label={"it": "Volontà d'Acciaio: il tiro salvezza è contro l'essere spaventato? Vantaggio",
           "en": "Steel Will: is the saving throw against being frightened? Advantage"})


def _one_turn_state(key: str):
    return StateSpec(key, rounds=1, ends_on=("new_turn", "manual"))


WHIRLWIND_HIT = RollOptionSpec(
    key=f"{CK}.whirlwind_attack_hit", phase="before", rolls=("attack",), outside_action=True,
    available=lambda c: _melee_weapon(c) and state_on(c, "whirlwind_attack"),
    label={"it": "Attacco Turbinante: un attacco in mischia contro una creatura entro 1,5 m (un tiro per ogni bersaglio)",
           "en": "Whirlwind Attack: a melee attack against a creature within 5 ft (one roll per target)"})
VOLLEY_HIT = RollOptionSpec(
    key=f"{CK}.volley_hit", phase="before", rolls=("attack",), outside_action=True,
    available=lambda c: _ranged_weapon(c) and state_on(c, "volley"),
    label={"it": "Raffica: un attacco a distanza contro una creatura entro 3 m dal punto scelto (un tiro e una munizione per bersaglio)",
           "en": "Volley: a ranged attack against a creature within 10 ft of the chosen point (one roll and one piece of ammunition per target)"})


def _evasion_started(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    begin_state(ctx.char, StateSpec(EVASION_STATE, rounds=1, ends_on=("new_turn", "manual")), f"{CK}.evasion", "Elusione")


EVASION_SAVE = RollOptionSpec(
    key=f"{CK}.evasion", phase="before", rolls=("save",), available=lambda c: c.ability == "dexterity", on_confirm=_evasion_started,
    label={"it": "Elusione: l'effetto dimezza i danni con un TS Destrezza?", "en": "Evasion: does the effect halve damage on a Dexterity save?"},
    effect=_say("Elusione: se superi il TS non subisci danni, se lo fallisci subisci la metà. Applica l'esito al danno.",
                "Evasion: if you pass the save you take no damage, on a failure you take half. Apply the outcome to the damage."))
EVASION_SUCCESS = RollOptionSpec(
    key=f"{CK}.evasion_success", phase="damage_in", rolls=("damage_taken",), multiplier=0, group="evasion",
    cost=Cost(state_key=EVASION_STATE), available=lambda c: state_on(c, EVASION_STATE),
    label={"it": "Elusione: hai superato il TS, nessun danno", "en": "Evasion: you passed the save, no damage"})
EVASION_FAILED = RollOptionSpec(
    key=f"{CK}.evasion_failed", phase="damage_in", rolls=("damage_taken",), multiplier=0.5, group="evasion",
    cost=Cost(state_key=EVASION_STATE), available=lambda c: state_on(c, EVASION_STATE),
    label={"it": "Elusione: hai fallito il TS, metà del danno", "en": "Evasion: you failed the save, half damage"})

UNCANNY_DODGE = RollOptionSpec(
    key=f"{CK}.uncanny_dodge", phase="damage_in", rolls=("damage_taken",), slot="reaction", multiplier=0.5, offered_on_damage=False,
    label={"it": "Schivata Prodigiosa: un attaccante che vedi ti ha colpito? Reazione, dimezza i danni dell'attacco",
           "en": "Uncanny Dodge: did an attacker you can see hit you? Reaction, halves the damage of the attack"})


# ---------------------------------------------------------------------------
# Signore delle Bestie
# ---------------------------------------------------------------------------

def _self_only_spell(ctx: RuleContext) -> bool:
    """Un incantesimo che ha come bersaglio solo chi lo lancia: portata «Personale» (senza un'area)."""
    return ctx.spell is not None and (ctx.spell.range_area or "").strip().lower() in ("personale", "self")


SHARE_SPELLS_EXTEND = RollOptionSpec(
    key=f"{CK}.share_spells_extend", phase="before", rolls=("cast",), available=_self_only_spell,
    label={"it": "Condividere Incantesimi: la tua bestia compagna è entro 9 m? L'incantesimo vale anche per lei",
           "en": "Share Spells: is your beast companion within 30 ft? The spell affects it too"},
    effect=_say("La bestia compagna, entro 9 m da te, è influenzata dall'incantesimo come te.",
                "Your beast companion, within 30 ft of you, is affected by the spell as you are."))


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

def _hunter(key: str, level: int, title: str, name: tuple[str, str], summary: tuple[str, str], action_type: str | None = None,
            **kw: Any):
    return feature(key, CK, ED, level, title, name, summary, action_type, subclass="hunter", **kw)


def _choice_row(key: str, level: int, title: str, name: tuple[str, str], summary: tuple[str, str], group: str,
                options: tuple[str, ...]):
    return _hunter(key, level, title, name, summary, no_row=True, choices=(ChoiceSpec(group=group, levels={level: 1}, options=lambda _c: list(options)),),
                   covered_by=f"ChoiceSpec {group} di questa riga e le righe delle opzioni; test_each_hunter_choice_comes_at_its_level_with_its_options")


def _option(key: str, level: int, group: str, title: str, name: tuple[str, str], summary: tuple[str, str],
            action_type: str | None = None, **kw: Any):
    return _hunter(key, level, title, name, summary, action_type, option_group=group, option_key=key, **kw)


FEATURES = (
    feature("hit_points", CK, ED, 1, "Punti Ferita e Competenze / Hit Points and Proficiencies (Ranger 1, pag. 103)",
            ("Punti Ferita e Competenze", "Hit Points and Proficiencies"),
            ("Dado vita d10; al 1° livello 10 + Costituzione. Armature leggere e medie, scudi, armi semplici e da guerra, TS Forza e Destrezza, 3 abilità.",
             "Hit die d10; level 1 gives 10 + Constitution. Light and medium armor, shields, simple and martial weapons, Strength and Dexterity saves, 3 skills."),
            no_row=True, covered_by="api/routers/classes.py create_class_for_character, core/rules/proficiencies.py (class_proficiencies); "
                                    "test_hit_points_use_the_d10_and_follow_constitution e test_class_proficiencies_first_class_and_multiclass; "
                                    "equipaggiamento di partenza: lavori-successivi"),
    feature("favored_enemy", CK, ED, 1, "Nemico Prescelto / Favored Enemy (Ranger 1, pag. 104)", ("Nemico Prescelto", "Favored Enemy"),
            ("Scegli un tipo di nemico (a 6° e 14° un altro) e un linguaggio che parla: vantaggio a seguirne le tracce (Sopravvivenza) e a ricordare informazioni (Intelligenza).",
             "Pick a type of enemy (another at 6th and 14th) and a language it speaks: advantage to track it (Survival) and to recall information (Intelligence)."),
            choices=(ChoiceSpec(group=ENEMY, levels={1: 1, 6: 2, 14: 3}, options=_keys(ENEMIES), listed=True,
                                label=_label(ENEMIES, ("Vantaggio a seguirne le tracce e a ricordare informazioni su di loro.",
                                                       "Advantage to track them and to recall information about them."))),
                     ChoiceSpec(group=ENEMY_LANGUAGE, levels={1: 1, 6: 2, 14: 3}, options=_language_options, label=_language_label,
                                grants="language", owned=_languages_owned)),
            roll_options=(FAVORED_ENEMY_ADVANTAGE,), passive=True),
    feature("natural_explorer", CK, ED, 1, "Esploratore Nato / Natural Explorer (Ranger 1, pag. 104)", ("Esploratore Nato", "Natural Explorer"),
            ("Scegli un terreno (a 6° e 10° un altro): nelle prove di Intelligenza o Saggezza su di esso con un'abilità posseduta il bonus di competenza vale il doppio. Benefici di viaggio dopo un'ora.",
             "Pick a terrain (another at 6th and 10th): on Intelligence or Wisdom checks about it with a skill you have, your proficiency bonus is doubled. Travel benefits after an hour."),
            choices=(ChoiceSpec(group=TERRAIN, levels={1: 1, 6: 2, 10: 3}, options=_keys(TERRAINS), listed=True,
                                label=_label(TERRAINS, ("Il tuo terreno prescelto: prove raddoppiate e benefici di viaggio.",
                                                        "Your favored terrain: doubled checks and travel benefits."))),),
            roll_options=(NATURAL_EXPLORER_DOUBLE,), passive=True),
    feature("fighting_style", CK, ED, 2, "Stile di Combattimento / Fighting Style (Ranger 2, pag. 104)",
            ("Stile di Combattimento", "Fighting Style"),
            ("Al 2° livello scegli uno stile: Tiro, Difesa, Duellare o Due Armi. Mai due volte lo stesso.",
             "At 2nd level you choose a style: Archery, Defense, Dueling or Two-Weapon Fighting. Never the same one twice."),
            no_row=True, choices=(ChoiceSpec(group="fighting_style", levels={2: 1}, options=style_options(STYLES)),),
            covered_by="ChoiceSpec fighting_style di questa riga e le righe dei quattro stili; test_the_style_is_chosen_at_level_2_among_four"),
    *STYLE_ROWS,
    feature("spellcasting", CK, ED, 2, "Incantesimi / Spellcasting (Ranger 2, pag. 104)", ("Incantesimi", "Spellcasting"),
            ("Saggezza; CD 8 + competenza + Saggezza. Slot da mezzo incantatore dal 2°, incantesimi conosciuti da 2 a 11, nessun trucchetto.",
             "Wisdom; DC 8 + proficiency + Wisdom. Half-caster slots from 2nd, known spells from 2 to 11, no cantrips."),
            no_row=True, covered_by="core/rules/spellcasting.py (known_limits, slots_for, caster_stats); "
                                    "test_known_spells_follow_the_ranger_table_with_no_cantrips"),
    feature("ranger_archetype", CK, ED, 3, "Archetipo Ranger / Ranger Archetype (Ranger 3, pag. 105)", ("Archetipo Ranger", "Ranger Archetype"),
            ("Al 3° livello si sceglie Cacciatore o Signore delle Bestie: privilegi ai livelli 3, 7, 11 e 15.",
             "At 3rd level you choose Hunter or Beast Master: features at levels 3, 7, 11 and 15."),
            no_row=True, covered_by="core/rules/subclasses.py (match_subclass) e il campo sottoclasse della classe"),
    feature("primeval_awareness", CK, ED, 3, "Consapevolezza Primordiale / Primeval Awareness (Ranger 3, pag. 105)",
            ("Consapevolezza Primordiale", "Primeval Awareness"),
            ("Azione, uno slot di qualunque livello: per 1 minuto per livello senti aberrazioni, celestiali, draghi, elementali, folletti, immondi e non morti entro 1,5 km (9 km nel terreno prescelto).",
             "Action, a slot of any level: for 1 minute per level you sense aberrations, celestials, dragons, elementals, fey, fiends and undead within 1 mile (6 miles in your favored terrain)."),
            "action", on_use=PRIMEVAL_AWARENESS_USE),
    feature("ability_score_improvement", CK, ED, 4,
            "Aumento dei Punteggi di Caratteristica / Ability Score Improvement (Ranger 4, pag. 105)",
            ("Aumento dei Punteggi di Caratteristica", "Ability Score Improvement"),
            ("Ai livelli 4, 8, 12, 16 e 19: +2 a un punteggio o +1 a due, oppure un talento; massimo 20.",
             "At levels 4, 8, 12, 16 and 19: +2 to one score or +1 to two, or a feat; maximum 20."), no_row=True,
            covered_by="core/rules/level_choices.py (scelta asi); test_asi_choices_are_pending_at_levels_4_8_12_16_and_19_only"),
    feature("extra_attack", CK, ED, 5, "Attacco Extra / Extra Attack (Ranger 5, pag. 105)", ("Attacco Extra", "Extra Attack"),
            ("Con l'azione Attacco attacchi due volte. Non si somma all'Attacco Extra di altre classi.",
             "You attack twice with the Attack action. Does not stack with other classes' Extra Attack."),
            attacks_per_action=2),
    feature("lands_stride", CK, ED, 8, "Andatura sul Territorio / Land's Stride (Ranger 8, pag. 105)",
            ("Andatura sul Territorio", "Land's Stride"),
            ("Il terreno difficile non magico e le piante non magiche non ti rallentano né ti feriscono; vantaggio ai TS contro piante magiche che ostacolano il movimento.",
             "Nonmagical difficult terrain and plants do not slow or hurt you; advantage on saves against magical plants that impede movement."),
            roll_options=(LANDS_STRIDE_SAVE,), passive=True),
    feature("hide_in_plain_sight", CK, ED, 10, "Nascondersi in Piena Vista / Hide in Plain Sight (Ranger 10, pag. 105)",
            ("Nascondersi in Piena Vista", "Hide in Plain Sight"),
            ("Dopo 1 minuto con materiali naturali ti mimetizzi: +10 a Furtività restando fermo contro una superficie solida. Muoverti, agire o reagire lo toglie.",
             "After 1 minute with natural materials you camouflage: +10 to Stealth while still against a solid surface. Moving, acting or reacting ends it."),
            roll_options=(HIDE_STEALTH,),
            on_use=OnUse(state=StateSpec("camouflaged", ends_on=("manual", "attack", "cast", "rest_short", "rest_long"),
                                         data={"stealth_bonus": 10}))),
    feature("vanish", CK, ED, 14, "Svanire / Vanish (Ranger 14, pag. 105)", ("Svanire", "Vanish"),
            ("Puoi usare Nascondersi come azione bonus. Non si seguono le tue tracce con mezzi non magici, se non vuoi.",
             "You can take the Hide action as a bonus action. You cannot be tracked by nonmagical means unless you choose to leave a trail."),
            "bonus_action", on_use=OnUse(slot="bonus", notes=lambda _c, _p: ["vanish_hide"])),
    feature("feral_senses", CK, ED, 18, "Sensi Ferini / Feral Senses (Ranger 18, pag. 105)", ("Sensi Ferini", "Feral Senses"),
            ("Attaccando una creatura che non vedi, non localizzarla non dà svantaggio. Senti le creature invisibili entro 9 m, se non nascoste e non sei accecato né assordato.",
             "Attacking a creature you cannot see, not locating it gives no disadvantage. You sense invisible creatures within 30 ft if not hidden and you are not blinded or deafened."),
            roll_options=(FERAL_SENSES,), passive=True),
    feature("foe_slayer", CK, ED, 20, "Sterminatore di Nemici / Foe Slayer (Ranger 20, pag. 105)", ("Sterminatore di Nemici", "Foe Slayer"),
            ("Una volta per turno somma la Saggezza al tiro per colpire o al danno di un attacco contro un nemico prescelto, prima o dopo il tiro.",
             "Once per turn add your Wisdom to the attack or damage roll against a favored enemy, before or after the roll."),
            roll_options=(FOE_SLAYER_ATTACK, FOE_SLAYER_ATTACK_LATE, FOE_SLAYER_DAMAGE), passive=True),

    # Cacciatore
    _choice_row("hunters_prey", 3, "Preda del Cacciatore / Hunter's Prey (Cacciatore 3, pag. 106)", ("Preda del Cacciatore", "Hunter's Prey"),
                ("Al 3° livello scegli Devastatore dell'Orda, Sterminatore di Colossi o Uccisore di Giganti: resta attivo solo quello.",
                 "At 3rd level you choose Horde Breaker, Colossus Slayer or Giant Killer: only that one is active."),
                "hunters_prey", ("horde_breaker", "colossus_slayer", "giant_killer")),
    _option("horde_breaker", 3, "hunters_prey", "Devastatore dell'Orda / Horde Breaker (Cacciatore 3, pag. 106)",
            ("Devastatore dell'Orda", "Horde Breaker"),
            ("Una volta per turno, dopo un attacco con arma, un altro attacco con la stessa arma contro una creatura diversa entro 1,5 m dal primo bersaglio.",
             "Once per turn, after a weapon attack, another attack with the same weapon against a different creature within 5 ft of the first target."),
            roll_options=(HORDE_BREAKER,), passive=True),
    _option("colossus_slayer", 3, "hunters_prey", "Sterminatore di Colossi / Colossus Slayer (Cacciatore 3, pag. 106)",
            ("Sterminatore di Colossi", "Colossus Slayer"),
            ("Una volta per turno, colpendo con un'arma una creatura sotto il massimo dei PF infliggi 1d8 danni in più.",
             "Once per turn, hitting a creature below its hit point maximum with a weapon deals an extra 1d8 damage."),
            roll_options=(COLOSSUS_SLAYER,), passive=True),
    _option("giant_killer", 3, "hunters_prey", "Uccisore di Giganti / Giant Killer (Cacciatore 3, pag. 106)",
            ("Uccisore di Giganti", "Giant Killer"),
            ("Reazione: una creatura Grande o più grande entro 1,5 m, che vedi, ti colpisce o ti manca: la attacchi subito.",
             "Reaction: a Large or larger creature within 5 ft, which you can see, hits or misses you: you attack it right away."),
            "reaction", roll_options=(GIANT_KILLER,), passive=True),
    _choice_row("defensive_tactics", 7, "Tattiche Difensive / Defensive Tactics (Cacciatore 7, pag. 106)", ("Tattiche Difensive", "Defensive Tactics"),
                ("Al 7° livello scegli Sfuggire all'Orda, Difesa dal Multiattacco o Volontà d'Acciaio: resta attivo solo quello.",
                 "At 7th level you choose Escape the Horde, Multiattack Defense or Steel Will: only that one is active."),
                "defensive_tactics", ("escape_the_horde", "multiattack_defense", "steel_will")),
    _option("escape_the_horde", 7, "defensive_tactics", "Sfuggire all'Orda / Escape the Horde (Cacciatore 7, pag. 106)",
            ("Sfuggire all'Orda", "Escape the Horde"),
            ("Gli attacchi di opportunità contro di te hanno svantaggio.", "Opportunity attacks against you have disadvantage."),
            passive=True, permanent_state=_permanent_note("escape_the_horde")),
    _option("multiattack_defense", 7, "defensive_tactics", "Difesa dal Multiattacco / Multiattack Defense (Cacciatore 7, pag. 106)",
            ("Difesa dal Multiattacco", "Multiattack Defense"),
            ("Dopo che una creatura ti colpisce hai +4 alla CA contro i suoi attacchi successivi nel resto del turno.",
             "After a creature hits you, you have +4 AC against its later attacks for the rest of the turn."),
            modifiers=(Modifier("ac", 4, when=lambda c: c.roll == "ac" and state_on(c, "multiattack_defense"),
                                source=f"feature:{CK}.multiattack_defense"),),
            roll_options=(MULTIATTACK_DEFENSE,), passive=True),
    _option("steel_will", 7, "defensive_tactics", "Volontà d'Acciaio / Steel Will (Cacciatore 7, pag. 106)",
            ("Volontà d'Acciaio", "Steel Will"),
            ("Vantaggio ai tiri salvezza contro l'essere spaventato.", "Advantage on saving throws against being frightened."),
            roll_options=(STEEL_WILL,), passive=True),
    _choice_row("multiattack", 11, "Multiattacco / Multiattack (Cacciatore 11, pag. 106)", ("Multiattacco", "Multiattack"),
                ("All'11° livello scegli Attacco Turbinante o Raffica: resta disponibile solo quello.",
                 "At 11th level you choose Whirlwind Attack or Volley: only that one is available."),
                "hunter_multiattack", ("whirlwind_attack", "volley")),
    _option("whirlwind_attack", 11, "hunter_multiattack", "Attacco Turbinante / Whirlwind Attack (Cacciatore 11, pag. 106)",
            ("Attacco Turbinante", "Whirlwind Attack"),
            ("Azione: un attacco in mischia contro ogni creatura entro 1,5 m, un tiro per colpire separato ciascuno.",
             "Action: a melee attack against every creature within 5 ft, a separate attack roll for each."),
            "action", roll_options=(WHIRLWIND_HIT,),
            on_use=OnUse(slot="action", state=_one_turn_state("whirlwind_attack"))),
    _option("volley", 11, "hunter_multiattack", "Raffica / Volley (Cacciatore 11, pag. 106)", ("Raffica", "Volley"),
            ("Azione: un attacco a distanza contro ogni creatura entro 3 m da un punto che vedi, un tiro e una munizione per bersaglio.",
             "Action: a ranged attack against every creature within 10 ft of a point you can see, one roll and one piece of ammunition each."),
            "action", roll_options=(VOLLEY_HIT,), on_use=OnUse(slot="action", state=_one_turn_state("volley"))),
    _choice_row("superior_hunters_defense", 15, "Difesa del Cacciatore Superiore / Superior Hunter's Defense (Cacciatore 15, pag. 106)",
                ("Difesa del Cacciatore Superiore", "Superior Hunter's Defense"),
                ("Al 15° livello scegli Elusione, Opporsi alla Marea o Schivata Prodigiosa: resta attivo solo quello.",
                 "At 15th level you choose Evasion, Stand Against the Tide or Uncanny Dodge: only that one is active."),
                "superior_hunters_defense", ("evasion", "stand_against_the_tide", "uncanny_dodge")),
    _option("evasion", 15, "superior_hunters_defense", "Elusione / Evasion (Cacciatore 15, pag. 106)", ("Elusione", "Evasion"),
            ("Nei TS Destrezza per dimezzare i danni: nessun danno se superi, metà se fallisci.",
             "On Dexterity saves for half damage: no damage on a success, half on a failure."),
            roll_options=(EVASION_SAVE, EVASION_SUCCESS, EVASION_FAILED), passive=True),
    _option("stand_against_the_tide", 15, "superior_hunters_defense", "Opporsi alla Marea / Stand Against the Tide (Cacciatore 15, pag. 106)",
            ("Opporsi alla Marea", "Stand Against the Tide"),
            ("Reazione: una creatura ostile manca un attacco in mischia contro di te: deve ripeterlo contro un'altra creatura a tua scelta, non lei stessa.",
             "Reaction: a hostile creature misses you with a melee attack: it must repeat the attack against another creature of your choice, not itself."),
            "reaction", on_use=OnUse(slot="reaction", state=StateSpec("stand_against_the_tide", rounds=1, ends_on=("new_turn", "manual"),
                                                                      data={"others": [f"{CK}.stand_against_the_tide"]}))),
    _option("uncanny_dodge", 15, "superior_hunters_defense", "Schivata Prodigiosa / Uncanny Dodge (Cacciatore 15, pag. 106)",
            ("Schivata Prodigiosa", "Uncanny Dodge"),
            ("Reazione: un attaccante che vedi ti colpisce: dimezzi i danni dell'attacco.",
             "Reaction: an attacker you can see hits you: you halve the damage of the attack."),
            "reaction", roll_options=(UNCANNY_DODGE,), passive=True),

    # Signore delle Bestie
    feature("rangers_companion", CK, ED, 3, "Compagno del Ranger / Ranger's Companion (Signore delle Bestie 3, pag. 106)",
            ("Compagno del Ranger", "Ranger's Companion"),
            ("Una bestia Media o minore, GS 1/4 o meno: aggiunge la tua competenza a CA, attacco, danni e prove; PF il maggiore fra la scheda e 4 × livello. Agisce solo se glielo ordini.",
             "A Medium or smaller beast, CR 1/4 or less: adds your proficiency to AC, attacks, damage and proficient rolls; HP the greater of its sheet and 4 × level. It acts only on your orders."),
            subclass="beast_master", passive=True),
    feature("exceptional_training", CK, ED, 7, "Addestramento Straordinario / Exceptional Training (Signore delle Bestie 7, pag. 106)",
            ("Addestramento Straordinario", "Exceptional Training"),
            ("In un turno in cui la bestia non attacca, un'azione bonus per ordinarle Aiuto, Disimpegno, Scatto o Schivata.",
             "On a turn the beast does not attack, a bonus action to order it to Help, Disengage, Dash or Dodge."),
            "bonus_action", subclass="beast_master", passive=True),
    feature("bestial_fury", CK, ED, 11, "Furia Bestiale / Bestial Fury (Signore delle Bestie 11, pag. 106)",
            ("Furia Bestiale", "Bestial Fury"),
            ("Con l'ordine di Attacco la bestia compie due attacchi, o il Multiattacco se lo possiede.",
             "When ordered to Attack, the beast makes two attacks, or its Multiattack if it has one."),
            subclass="beast_master", passive=True),
    feature("share_spells", CK, ED, 15, "Condividere Incantesimi / Share Spells (Signore delle Bestie 15, pag. 106)",
            ("Condividere Incantesimi", "Share Spells"),
            ("Lanciando un incantesimo che ha come bersaglio solo te, puoi estenderlo alla bestia compagna entro 9 m.",
             "When you cast a spell that targets only you, you can extend it to your beast companion within 30 ft."),
            subclass="beast_master", roll_options=(SHARE_SPELLS_EXTEND,), passive=True),

    feature("multiclassing", CK, ED, 1, "Multiclasse: Ranger / Multiclassing: Ranger (Opzioni di Personalizzazione, pag. 163)",
            ("Multiclasse: Ranger", "Multiclassing: Ranger"),
            ("Requisito Destrezza 13 e Saggezza 13. Da multiclasse: armature leggere e medie, scudi, armi semplici e da guerra, 1 abilità; slot a metà livelli.",
             "Requires Dexterity 13 and Wisdom 13. As a multiclass: light and medium armor, shields, simple and martial weapons, 1 skill; half-level slots."),
            no_row=True, covered_by="core/rules/proficiencies.py (as_multiclass) e webapp/src/data/multiclassPrereqs.ts (D2); "
                                    "test_a_ranger_added_as_a_second_class_adds_half_its_levels_to_the_slots"),
)

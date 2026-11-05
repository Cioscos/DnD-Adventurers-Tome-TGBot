"""Chierico 2014 e i suoi domini: Conoscenza, Guerra, Inganno, Luce, Natura, Tempesta, Vita.

Valori dalla scheda ``docs/superpowers/rules/2014/classes/cleric.md``; i testi sono nostri, mai quelli del manuale.
Competenze di dominio sempre concesse (D5); incantesimi di dominio sempre preparati (D4).
"""
from __future__ import annotations

from typing import Any

from core.data.damage_types import canonical_damage_type
from core.data.skills import SKILLS
from core.rules.catalog._common import attacks_made, feature, skill_label, state_on
from core.rules.types import (
    TRICKSTER_BLESSING, WAR_GODS_BLESSING, ChoiceSpec, Cost, FeatureSpec, Modifier, OnUse, RollOptionSpec, RuleContext,
    StateSpec, TargetEffect, UseChoice, Uses,
)

ED, CK = "2014", "cleric"
POOL = f"{CK}.channel_divinity"
TURN_UNDEAD = f"{CK}.turn_undead"
DESTROY_UNDEAD = f"{CK}.destroy_undead"
WAR_PRIEST = f"{CK}.war_priest"
WARDING_FLARE = f"{CK}.warding_flare"
IMPROVED_FLARE = f"{CK}.improved_flare"
WRATH_OF_THE_STORM = f"{CK}.wrath_of_the_storm"
CHARM_ANIMALS = f"{CK}.charm_animals_and_plants"
DIVINE_INTERVENTION = f"{CK}.divine_intervention"
INVOKE_DUPLICITY = f"{CK}.invoke_duplicity"

_DESTROY_CR = {5: "1/2", 8: "1", 11: "2", 14: "3", 17: "4"}
_ELEMENTS = ("acid", "cold", "lightning", "fire", "thunder")
_PHYSICAL = ("bludgeoning", "piercing", "slashing")


def destroy_threshold(level: int) -> str | None:
    """GS massimo dei non morti distrutti da Scacciare Non Morti (``None`` sotto il 5° livello)."""
    return next((cr for lv, cr in sorted(_DESTROY_CR.items(), reverse=True) if level >= lv), None)


def spell_dc(ctx: RuleContext) -> int:
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    return 8 + ctx.char.proficiency_bonus + effective_ability_mod(ctx.char, "wisdom")


def _wisdom_mod(ctx: RuleContext) -> int:
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    return effective_ability_mod(ctx.char, "wisdom")


def _no_options(_ctx: RuleContext) -> list[str]:
    return []


# ---------------------------------------------------------------------------
# Incanalare Divinità: ogni effetto è un privilegio che spende gli usi della riserva comune
# ---------------------------------------------------------------------------

def _turn_undead_state(ctx: RuleContext, _params: dict) -> StateSpec:
    """Il promemoria di Scacciare Non Morti: CD e, dal 5° livello, il GS dei non morti che Distruggere Non Morti elimina."""
    data: dict[str, Any] = {"dc": spell_dc(ctx), "save": "wisdom", "others": [DESTROY_UNDEAD]}
    if (cr := destroy_threshold(ctx.class_level)) is not None:
        data["cr"] = cr
    return StateSpec("turn_undead", rounds=10, ends_on=("manual",), data=data)


def _turn_undead_effect(ctx: RuleContext, _params: dict) -> TargetEffect:
    return TargetEffect(condition="custom:turned", save_ability="wisdom", save_dc=spell_dc(ctx), rounds=10)


def _charm_effect(ctx: RuleContext, _params: dict) -> TargetEffect:
    return TargetEffect(condition="charmed", save_ability="wisdom", save_dc=spell_dc(ctx), rounds=10)


def _charm_state(ctx: RuleContext, _params: dict) -> StateSpec:
    return StateSpec("charm_animals_and_plants", rounds=10, ends_on=("manual",),
                     data={"dc": spell_dc(ctx), "save": "wisdom", "others": [f"{CK}.master_of_nature"]})


def _radiance_state(ctx: RuleContext, _params: dict) -> StateSpec:
    """Danni radiosi 2d10 + livello da chierico: i dadi si tirano all'uso, il fisso sta qui con la CD (TS Costituzione)."""
    return StateSpec("radiance_of_the_dawn", rounds=1, ends_on=("manual", "new_turn"),
                     data={"dc": spell_dc(ctx), "save": "constitution", "bonus": ctx.class_level})


def _wrath_state(ctx: RuleContext, _params: dict) -> StateSpec:
    return StateSpec("wrath_of_the_storm", rounds=1, ends_on=("manual", "new_turn"),
                     data={"dc": spell_dc(ctx), "save": "dexterity", "others": [WRATH_OF_THE_STORM]})


def _flare_state(ctx: RuleContext, _params: dict) -> StateSpec:
    others = [WARDING_FLARE] + ([IMPROVED_FLARE] if ctx.class_level >= 6 else [])
    return StateSpec("warding_flare", rounds=1, ends_on=("manual", "new_turn"), data={"others": others})


def _corona_state(_ctx: RuleContext, _params: dict) -> StateSpec:
    return StateSpec("corona_of_light", rounds=10, ends_on=("incapacitated", "manual"), end_slot="action",
                     data={"others": [f"{CK}.corona_of_light"]})


def _divine_intervention_roll(ctx: RuleContext) -> str | None:
    """Il d100 si tira sotto il 20° livello; al 20° riesce sempre e non c'è nulla da tirare."""
    return "1d100" if ctx.class_level < 20 else None


def _divine_intervention_state(ctx: RuleContext, params: dict) -> StateSpec:
    """Esito: riesce se il d100 non supera il livello da chierico. Il successo blocca il privilegio per 7 giorni, finché il
    giocatore non chiude lo stato; il fallimento lo lascia fino al riposo lungo, che gli rende anche l'uso."""
    level, rolled = ctx.class_level, int(params.get("rolled") or 0)
    success = level >= 20 or 1 <= rolled <= level
    ends = ("manual",) if success else ("rest_long", "manual")
    return StateSpec("divine_intervention", ends_on=ends, data={"roll": rolled or None, "level": level, "success": success})


def _visions_state(ctx: RuleContext, _params: dict) -> StateSpec:
    """Meditazione per un massimo di minuti pari alla Saggezza (10 round al minuto), in concentrazione."""
    from core.rules.weapons import ability_score  # import locale
    return StateSpec("visions_of_the_past", rounds=ability_score(ctx.char, "wisdom") * 10,
                     ends_on=("concentration_end", "incapacitated", "manual"))


def _duplicity_state(ctx: RuleContext, _params: dict) -> StateSpec:
    """Un duplicato (quattro dal 17° livello); dura un minuto finché si mantiene la concentrazione."""
    return StateSpec("invoke_duplicity", rounds=10, ends_on=("concentration_end", "incapacitated", "manual"),
                     data={"duplicates": 4 if ctx.class_level >= 17 else 1, "others": [INVOKE_DUPLICITY]})


def _ages_state(_ctx: RuleContext, params: dict) -> StateSpec:
    return StateSpec("knowledge_of_the_ages", rounds=100, ends_on=("manual",), data={"skill": params.get("skill")})


def _ages_bonus(ctx: RuleContext) -> int:
    """Competenza in più per l'abilità scelta, solo se non l'hai già: chi è competente o esperto non la somma due volte."""
    state = next((s for s in ctx.char.active_states or [] if s.get("key") == "knowledge_of_the_ages"), None)
    if state is None or (state.get("data") or {}).get("skill") != ctx.skill or (ctx.char.skills or {}).get(ctx.skill):
        return 0
    return ctx.char.proficiency_bonus


def _war_blessing_state(_ctx: RuleContext, params: dict) -> StateSpec:
    """+10 al tiro per colpire di un'altra creatura. Con un alleato della serata lo stato sta sul ricevente, che lo spende
    dalla propria scheda; senza (una creatura del GM) resta su chi lo usa come promemoria per il gruppo (D1)."""
    ends = ("rest_short", "rest_long", "manual")
    if params.get("target_character_id") is None:
        return StateSpec("war_gods_blessing_note", ends_on=ends, data={"attack_bonus": 10, "others": [f"{CK}.war_gods_blessing"]})
    return StateSpec(WAR_GODS_BLESSING, ends_on=ends, data={"attack_bonus": 10})


def _trickster_state(_ctx: RuleContext, params: dict) -> StateSpec:
    """Vantaggio a Furtività per 1 ora (600 round) a una creatura consenziente: stessa regola dell'alleato di sopra."""
    ends = ("rest_long", "manual")
    if params.get("target_character_id") is None:
        return StateSpec("trickster_blessing_note", rounds=600, ends_on=ends, data={"others": [f"{CK}.blessing_of_the_trickster"]})
    return StateSpec(TRICKSTER_BLESSING, rounds=600, ends_on=ends)


def _cloak_state(_ctx: RuleContext, _params: dict) -> StateSpec:
    return StateSpec("cloak_of_shadows", rounds=2, ends_on=("incapacitated", "manual"), data={"others": [f"{CK}.cloak_of_shadows"]})


def _end_cloak(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    ctx.char.active_states = [s for s in ctx.char.active_states or [] if s.get("key") != "cloak_of_shadows"]


# ---------------------------------------------------------------------------
# Conferme al tiro
# ---------------------------------------------------------------------------

def _strike_dice(ctx: RuleContext, _inputs: dict) -> str:
    return "1d8" if ctx.class_level < 14 else "2d8"


def _weapon_hit(ctx: RuleContext) -> bool:
    return ctx.item is not None and ctx.spell is None


def _divine_strike(domain: str, type_it: str, type_en: str, *, group: str | None = None, suffix: str = "") -> RollOptionSpec:
    """Una volta per turno, dopo un colpo con un'arma: 1d8 (2d8 dal 14°) di danni; il tipo lo dice l'etichetta."""
    return RollOptionSpec(
        key=f"{CK}.divine_strike_{domain}{suffix}", phase="after_hit", rolls=("attack",), once_per_turn=True, group=group,
        extra_dice=_strike_dice, available=_weapon_hit,
        label={"it": f"Colpo Divino: danni {type_it} in più", "en": f"Divine Strike: extra {type_en} damage"})


GUIDED_STRIKE = RollOptionSpec(
    key=f"{CK}.guided_strike", phase="after_roll", after="add", rolls=("attack",), bonus=lambda _c, _i: 10,
    cost=Cost(feature_key=POOL),
    label={"it": "Colpo Guidato: spendi Incanalare Divinità e somma 10 al tiro per colpire",
           "en": "Guided Strike: spend Channel Divinity and add 10 to the attack roll"})

WAR_PRIEST_ATTACK = RollOptionSpec(
    key=WAR_PRIEST, phase="before", rolls=("attack",), slot="bonus", cost=Cost(feature_key=WAR_PRIEST),
    label={"it": "Sacerdote di Guerra: attacco con arma come azione bonus", "en": "War Priest: weapon attack as a bonus action"},
    available=lambda c: c.spell is None and attacks_made(c) > 0)

def _spell_damage_in(ctx: RuleContext, *types: str) -> bool:
    return ctx.spell is not None and canonical_damage_type(ctx.spell.damage_type) in types


DESTRUCTIVE_WRATH = RollOptionSpec(
    key=f"{CK}.destructive_wrath", phase="before", rolls=("spell_damage",), maximize=True, cost=Cost(feature_key=POOL),
    label={"it": "Collera Distruttiva: spendi Incanalare Divinità, i dadi valgono il massimo",
           "en": "Destructive Wrath: spend Channel Divinity, the dice deal maximum damage"},
    available=lambda c: _spell_damage_in(c, "lightning", "thunder"))

THUNDERBOLT_STRIKE = RollOptionSpec(
    key=f"{CK}.thunderbolt_strike", phase="before", rolls=("spell_damage",),
    label={"it": "Colpo del Tuono e del Fulmine: il bersaglio è Grande o più piccolo?",
           "en": "Thunderbolt Strike: is the target Large or smaller?"},
    available=lambda c: _spell_damage_in(c, "lightning"),
    effect=lambda _c, _i: {"it": "Il bersaglio è spinto di 3 m lontano da te.", "en": "The target is pushed 10 ft away from you."})

CLOAK_ATTACK = RollOptionSpec(
    key=f"{CK}.cloak_attack", phase="before", rolls=("attack",), mode="advantage", on_confirm=_end_cloak,
    label={"it": "Manto di Ombre: attacchi da invisibile (l'invisibilità finisce)", "en": "Cloak of Shadows: attack while invisible (it ends)"},
    available=lambda c: state_on(c, "cloak_of_shadows"))

CLOAK_CAST = RollOptionSpec(
    key=f"{CK}.cloak_cast", phase="before", rolls=("cast",), on_confirm=_end_cloak,
    label={"it": "Manto di Ombre: lanci un incantesimo (l'invisibilità finisce)", "en": "Cloak of Shadows: cast a spell (it ends)"},
    available=lambda c: state_on(c, "cloak_of_shadows"))

DUPLICITY_ADVANTAGE = RollOptionSpec(
    key=f"{CK}.duplicity_advantage", phase="before", rolls=("attack",), mode="advantage",
    label={"it": "Duplicato: tu e il duplicato siete entro 1,5 m dal bersaglio, che lo vede?",
           "en": "Duplicity: are you and the illusion within 5 ft of a target that sees it?"},
    available=lambda c: state_on(c, "invoke_duplicity"))

def _healing_roll(ctx: RuleContext) -> bool:
    return ctx.roll == "spell_healing" and (ctx.casting_level or 0) >= 1


BLESSED_HEALER = RollOptionSpec(
    key=f"{CK}.blessed_healer", phase="before", rolls=("spell_healing",),
    self_heal=lambda c, _i: 2 + (c.casting_level or 0),
    label={"it": "Guaritore Benedetto: il bersaglio è un'altra creatura? Ti curi di 2 + livello dell'incantesimo",
           "en": "Blessed Healer: is the target another creature? You regain 2 + the spell's level"},
    available=lambda c: (c.casting_level or 0) >= 1)

AVATAR_OF_BATTLE = RollOptionSpec(
    key=f"{CK}.avatar_of_battle", phase="damage_in", rolls=("damage_taken",), multiplier=0.5,
    label={"it": "Avatar della Battaglia: il colpo è di un'arma non magica?",
           "en": "Avatar of Battle: is the hit from a nonmagical weapon?"},
    available=lambda c: c.damage_type in _PHYSICAL)

DAMPEN_ELEMENTS = RollOptionSpec(
    key=f"{CK}.dampen_elements", phase="damage_in", rolls=("damage_taken",), multiplier=0.5, slot="reaction",
    label={"it": "Mitigare Elementi: reazione, resistenza a questo danno", "en": "Dampen Elements: reaction, resistance to this damage"},
    available=lambda c: c.damage_type in _ELEMENTS)


def _own_cantrip(ctx: RuleContext) -> bool:
    spell = ctx.spell
    if spell is None or spell.level != 0:
        return False
    return spell.class_id == ctx.class_row.id or (spell.class_id is None and len(ctx.char.classes) == 1)


def _potent() -> Modifier:
    return Modifier("damage", _wisdom_mod, when=lambda c: c.roll == "damage" and _own_cantrip(c),
                    source=f"feature:{CK}.potent_spellcasting")


def _domain_spells(domain: str, title: str, name: tuple[str, str], tiers: tuple[tuple[str, ...], ...]) -> list[FeatureSpec]:
    """Due incantesimi per ogni soglia (1°, 3°, 5°, 7°, 9°). La riga del 1° livello è quella della scheda; le soglie
    successive sono le stesse voci a livello più alto e non portano una riga propria."""
    out = [feature(f"{domain}_spells", CK, ED, 1, title, name,
                   (f"Incantesimi di dominio sempre preparati, due ogni soglia (1°, 3°, 5°, 7°, 9°); non contano nel limite.",
                    "Domain spells are always prepared, two per tier (1st, 3rd, 5th, 7th, 9th); they do not count against the limit."),
                   subclass=domain, granted_spells=tiers[0])]
    for tier, spells in zip((3, 5, 7, 9), tiers[1:]):
        out.append(feature(f"{domain}_spells_{tier}", CK, ED, tier, title, name,
                           (f"Incantesimi di dominio del {tier}° livello.", f"Domain spells gained at level {tier}."),
                           subclass=domain, granted_spells=spells, no_row=True,
                           covered_by=f"{CK}.{domain}_spells (stessa voce della mappatura) e test_domain_spells_follow_the_level"))
    return out


DOMAIN_SPELLS = {
    "knowledge": (("command", "identify"), ("augury", "suggestion"), ("nondetection", "speak-with-dead"),
                  ("confusion", "arcane-eye"), ("legend-lore", "scrying")),
    "war": (("divine-favor", "shield-of-faith"), ("magic-weapon", "spiritual-weapon"), ("spirit-guardians", "crusaders-mantle"),
            ("freedom-of-movement", "stoneskin"), ("hold-monster", "flame-strike")),
    "trickery": (("disguise-self", "charm-person"), ("mirror-image", "pass-without-trace"), ("dispel-magic", "blink"),
                 ("polymorph", "dimension-door"), ("dominate-person", "modify-memory")),
    "light": (("burning-hands", "faerie-fire"), ("scorching-ray", "flaming-sphere"), ("daylight", "fireball"),
              ("guardian-of-faith", "wall-of-fire"), ("flame-strike", "scrying")),
    "nature": (("animal-friendship", "speak-with-animals"), ("barkskin", "spike-growth"), ("plant-growth", "wind-wall"),
               ("dominate-beast", "grasping-vine"), ("insect-plague", "tree-stride")),
    "tempest": (("fog-cloud", "thunderwave"), ("gust-of-wind", "shatter"), ("call-lightning", "sleet-storm"),
                ("control-water", "ice-storm"), ("destructive-wave", "insect-plague")),
    "life": (("bless", "cure-wounds"), ("lesser-restoration", "spiritual-weapon"), ("beacon-of-hope", "revivify"),
             ("death-ward", "guardian-of-faith"), ("mass-cure-wounds", "raise-dead")),
}


FEATURES = (
    feature("hit_points", CK, ED, 1, "Punti Ferita / Hit Points (Chierico 1, pag. 57)", ("Punti Ferita", "Hit Points"),
            ("Dado vita d8; al 1° livello 8 + Costituzione, poi d8 (o 5) + Costituzione.",
             "Hit die d8; level 1 gives 8 + Constitution, then d8 (or 5) + Constitution."), no_row=True,
            covered_by="api/routers/classes.py create_class_for_character e total_base_hp; test_hit_points_use_the_d8_and_follow_constitution"),
    feature("proficiencies", CK, ED, 1, "Competenze / Proficiencies (Chierico 1, pag. 57)", ("Competenze", "Proficiencies"),
            ("Armature leggere e medie, scudi, armi semplici, TS Saggezza e Carisma, 2 abilità fra Intuizione, Medicina, "
             "Persuasione, Religione e Storia.",
             "Light and medium armor, shields, simple weapons, Wisdom and Charisma saves, 2 skills from Insight, Medicine, "
             "Persuasion, Religion and History."),
            no_row=True, covered_by="core/rules/proficiencies.py (class_proficiencies) e la scelta ClassSkillChoice"),
    feature("equipment", CK, ED, 1, "Equipaggiamento / Equipment (Chierico 1, pag. 57)", ("Equipaggiamento", "Equipment"),
            ("Dotazione iniziale: mazza o martello da guerra, un'armatura, balestra leggera o arma semplice, pacco, scudo e simbolo sacro.",
             "Starting gear: a mace or warhammer, an armor, a light crossbow or simple weapon, a pack, a shield and a holy symbol."),
            no_row=True, covered_by="lavori-successivi"),
    feature("spellcasting", CK, ED, 1, "Incantesimi / Spellcasting (Chierico 1, pag. 58)", ("Incantesimi", "Spellcasting"),
            ("Saggezza; CD 8 + competenza + Saggezza. Trucchetti 3/4/5, preparati Saggezza + livello, slot da tabella, rituali; simbolo sacro come focus.",
             "Wisdom; DC 8 + proficiency + Wisdom. Cantrips 3/4/5, prepared Wisdom + level, slots by table, rituals; a holy symbol as focus."),
            no_row=True, covered_by="core/rules/spellcasting.py (known_limits, prepared_limit, slots_for, caster_stats); "
                                    "test_cantrips_and_prepared_spells_follow_the_class_table"),
    feature("divine_domain", CK, ED, 1, "Dominio Divino / Divine Domain (Chierico 1, pag. 58)", ("Dominio Divino", "Divine Domain"),
            ("Al 1° livello si sceglie un dominio: Conoscenza, Guerra, Inganno, Luce, Natura, Tempesta o Vita.",
             "At level 1 you choose a domain: Knowledge, War, Trickery, Light, Nature, Tempest or Life."),
            no_row=True, covered_by="core/rules/subclasses.py (match_subclass) e il campo sottoclasse della classe"),
    feature("domain_spells", CK, ED, 1, "Incantesimi di Dominio / Domain Spells (Chierico 1, pag. 58)",
            ("Incantesimi di Dominio", "Domain Spells"),
            ("Ogni dominio dà due incantesimi sempre preparati al 1°, 3°, 5°, 7° e 9° livello; vedi la voce del dominio.",
             "Each domain grants two always-prepared spells at levels 1, 3, 5, 7 and 9; see the domain entry."),
            no_row=True, covered_by="le voci «Incantesimi del Dominio» di ogni dominio e test_domain_spells_follow_the_level"),
    feature("channel_divinity", CK, ED, 2, "Incanalare Divinità / Channel Divinity (Chierico 2, pag. 59)",
            ("Incanalare Divinità", "Channel Divinity"),
            ("Usi: 1 al 2°, 2 al 6°, 3 al 18°, tornano a ogni riposo breve o lungo. Ogni effetto (Scacciare Non Morti e quelli del dominio) ne spende uno.",
             "Uses: 1 at 2nd, 2 at 6th, 3 at 18th, regained on a short or long rest. Each effect (Turn Undead and your domain's) spends one."),
            "action", uses=Uses(table={2: 1, 6: 2, 18: 3}), restoration="short_rest"),
    feature("turn_undead", CK, ED, 2, "Incanalare Divinità: Scacciare Non Morti / Channel Divinity: Turn Undead (Chierico 2, pag. 59)",
            ("Scacciare Non Morti", "Turn Undead"),
            ("Azione: spendi un uso. I non morti entro 9 m fanno un TS Saggezza (CD 8 + competenza + Saggezza) o sono scacciati per 1 minuto o fino al danno.",
             "Action: spend a use. Undead within 30 ft make a Wisdom save (DC 8 + proficiency + Wisdom) or are turned for 1 minute or until damaged."),
            "action",
            on_use=OnUse(slot="action", spends=POOL, state=_turn_undead_state, target_effect=_turn_undead_effect)),
    feature("ability_score_improvement", CK, ED, 4,
            "Aumento dei Punteggi di Caratteristica / Ability Score Improvement (Chierico 4, pag. 59)",
            ("Aumento dei Punteggi di Caratteristica", "Ability Score Improvement"),
            ("Ai livelli 4, 8, 12, 16 e 19: +2 a un punteggio o +1 a due, oppure un talento; massimo 20.",
             "At levels 4, 8, 12, 16 and 19: +2 to one score or +1 to two, or a feat; maximum 20."), no_row=True,
            covered_by="core/rules/level_choices.py (scelta asi); test_asi_choice_is_pending_at_each_asi_level"),
    feature("destroy_undead", CK, ED, 5, "Distruggere Non Morti / Destroy Undead (Chierico 5, pag. 59)",
            ("Distruggere Non Morti", "Destroy Undead"),
            ("Scacciare Non Morti distrugge i non morti che falliscono il TS fino al GS: 1/2 al 5°, 1 all'8°, 2 all'11°, 3 al 14°, 4 al 17°.",
             "Turn Undead destroys undead that fail the save up to this CR: 1/2 at 5th, 1 at 8th, 2 at 11th, 3 at 14th, 4 at 17th.")),
    feature("divine_intervention", CK, ED, 10, "Intervento Divino / Divine Intervention (Chierico 10, pag. 59)",
            ("Intervento Divino", "Divine Intervention"),
            ("Azione: tira un d100; riesce se non supera il tuo livello da chierico. Se riesce, 7 giorni di attesa; altrimenti torna dopo un riposo lungo.",
             "Action: roll a d100; it works if it does not exceed your cleric level. On success, wait 7 days; otherwise it returns after a long rest."),
            "action", uses=Uses(table={10: 1}), restoration="long_rest",
            on_use=OnUse(slot="action", rolls=_divine_intervention_roll, state=_divine_intervention_state,
                         available=lambda c: not state_on(c, "divine_intervention"))),
    feature("divine_intervention_improvement", CK, ED, 20,
            "Intervento Divino Migliorato / Divine Intervention Improvement (Chierico 20, pag. 59)",
            ("Intervento Divino Migliorato", "Divine Intervention Improvement"),
            ("Al 20° livello Intervento Divino riesce sempre, senza tirare.", "At 20th level Divine Intervention always works, no roll.")),
    feature("multiclassing", CK, ED, 1, "Multiclasse: Chierico / Multiclassing: Cleric (Chierico, pag. 163)",
            ("Multiclasse: Chierico", "Multiclassing: Cleric"),
            ("Requisito Saggezza 13. Da multiclasse: armature leggere e medie e scudi; gli slot sommano i livelli interi.",
             "Requires Wisdom 13. As a multiclass: light and medium armor and shields; spell slots add up full levels."),
            no_row=True, covered_by="core/rules/proficiencies.py (as_multiclass) e webapp/src/data/multiclassPrereqs.ts (D2)"),

    # Dominio della Conoscenza
    *_domain_spells("knowledge", "Incantesimi del Dominio della Conoscenza / Knowledge Domain Spells (Conoscenza 1, pag. 59)",
                    ("Incantesimi del Dominio della Conoscenza", "Knowledge Domain Spells"), DOMAIN_SPELLS["knowledge"]),
    feature("blessings_of_knowledge", CK, ED, 1,
            "Benedizioni della Conoscenza / Blessings of Knowledge (Conoscenza 1, pag. 60)",
            ("Benedizioni della Conoscenza", "Blessings of Knowledge"),
            ("Due abilità fra Arcano, Natura, Religione e Storia passano a maestria (doppia competenza).",
             "Two skills among Arcana, Nature, Religion and History gain expertise (double proficiency)."),
            subclass="knowledge",
            choices=(ChoiceSpec(group="knowledge_skills", levels={1: 2},
                                options=lambda _c: ["arcana", "nature", "religion", "history"],
                                label=skill_label, grants="expert"),)),
    feature("knowledge_of_the_ages", CK, ED, 2,
            "Incanalare Divinità: Conoscenze Secolari / Channel Divinity: Knowledge of the Ages (Conoscenza 2, pag. 60)",
            ("Conoscenze Secolari", "Knowledge of the Ages"),
            ("Azione: spendi un uso e scegli un'abilità: per 10 minuti ne hai la competenza.",
             "Action: spend a use and choose a skill: you are proficient in it for 10 minutes."),
            "action", subclass="knowledge",
            modifiers=(Modifier("skill", _ages_bonus, when=lambda c: c.roll == "skill" and _ages_bonus(c) > 0,
                                source=f"feature:{CK}.knowledge_of_the_ages"),),
            on_use=OnUse(slot="action", spends=POOL, state=_ages_state, choices=(
                UseChoice("skill", {"it": "Abilità", "en": "Skill"}, lambda _c: [s for s, _a in SKILLS],
                          lambda s: skill_label(s)["name"]),))),
    feature("potent_spellcasting_knowledge", CK, ED, 8, "Incantesimi Potenti / Potent Spellcasting (Conoscenza 8, pag. 60)",
            ("Incantesimi Potenti", "Potent Spellcasting"),
            ("Ai danni di ogni tuo trucchetto da chierico si somma il modificatore di Saggezza.",
             "Add your Wisdom modifier to the damage of every cleric cantrip you cast."),
            subclass="knowledge", modifiers=(_potent(),)),

    feature("visions_of_the_past", CK, ED, 17, "Visioni del Passato / Visions of the Past (Conoscenza 17, pag. 60)",
            ("Visioni del Passato", "Visions of the Past"),
            ("Meditazione in concentrazione per un massimo di minuti pari a Saggezza: visioni sul passato di un oggetto o dell'area. Un uso per riposo breve o lungo.",
             "Meditation in concentration for up to Wisdom minutes: visions of an object's or the area's past. One use per short or long rest."),
            subclass="knowledge", uses=Uses(table={17: 1}), restoration="short_rest",
            on_use=OnUse(concentration=True, state=_visions_state)),
    feature("object_reading", CK, ED, 17, "Lettura degli Oggetti / Object Reading (Conoscenza 17, pag. 60)",
            ("Lettura degli Oggetti", "Object Reading"),
            ("Con un oggetto in mano apprendi come il precedente proprietario lo ottenne e lo perse; lo racconta il GM.",
             "Holding an object you learn how its last owner got and lost it; the GM tells it."),
            subclass="knowledge", passive=True),
    feature("area_reading", CK, ED, 17, "Lettura dell'Area / Area Reading (Conoscenza 17, pag. 60)",
            ("Lettura dell'Area", "Area Reading"),
            ("Dopo 1 minuto vedi un evento recente dell'area, fino a un numero di giorni pari alla Saggezza; lo racconta il GM.",
             "After 1 minute you see a recent event in the area, up to Wisdom days back; the GM tells it."),
            subclass="knowledge", passive=True),

    # Dominio della Guerra
    *_domain_spells("war", "Incantesimi del Dominio della Guerra / War Domain Spells (Guerra 1, pag. 60)",
                    ("Incantesimi del Dominio della Guerra", "War Domain Spells"), DOMAIN_SPELLS["war"]),
    feature("war_bonus_proficiencies", CK, ED, 1, "Competenze Bonus / Bonus Proficiencies (Guerra 1, pag. 60)",
            ("Competenze Bonus (Guerra)", "Bonus Proficiencies (War)"),
            ("Competenza in armature pesanti e armi da guerra.", "Proficiency with heavy armor and martial weapons."),
            subclass="war", proficiency_grants={"armor": ("heavy",), "weapons": ("martial",)}),
    feature("war_priest", CK, ED, 1, "Sacerdote di Guerra / War Priest (Guerra 1, pag. 60)", ("Sacerdote di Guerra", "War Priest"),
            ("Dopo l'azione Attacco, un attacco con arma come azione bonus. Usi pari al modificatore di Saggezza (minimo 1), al riposo lungo.",
             "After the Attack action, one weapon attack as a bonus action. Uses equal your Wisdom modifier (minimum 1), per long rest."),
            "bonus_action", subclass="war", uses=Uses(ability="wisdom", minimum=1), restoration="long_rest",
            roll_options=(WAR_PRIEST_ATTACK,)),
    feature("guided_strike", CK, ED, 2, "Incanalare Divinità: Colpo Guidato / Channel Divinity: Guided Strike (Guerra 2, pag. 60)",
            ("Colpo Guidato", "Guided Strike"),
            ("Dopo un tiro per colpire, spendi un uso e somma 10 al tiro.",
             "After an attack roll, spend a use and add 10 to the roll."),
            subclass="war", roll_options=(GUIDED_STRIKE,)),
    feature("war_gods_blessing", CK, ED, 6,
            "Incanalare Divinità: Benedizione del Dio della Guerra / Channel Divinity: War God's Blessing (Guerra 6, pag. 60)",
            ("Benedizione del Dio della Guerra", "War God's Blessing"),
            ("Reazione: spendi un uso e una creatura entro 9 m che tira per colpire somma 10 al tiro, anche dopo averlo visto.",
             "Reaction: spend a use and a creature within 30 ft making an attack roll adds 10 to it, even after seeing it."),
            "reaction", subclass="war",
            on_use=OnUse(slot="reaction", spends=POOL, ally_state=True, state=_war_blessing_state)),
    feature("divine_strike_war", CK, ED, 8, "Colpo Divino / Divine Strike (Guerra 8, pag. 60)", ("Colpo Divino", "Divine Strike"),
            ("Una volta per turno, con un colpo d'arma: 1d8 (2d8 dal 14°) di danni in più, dello stesso tipo dell'arma.",
             "Once per turn, on a weapon hit: 1d8 (2d8 from 14th) extra damage of the weapon's type."),
            subclass="war", roll_options=(_divine_strike("war", "dello stesso tipo dell'arma", "of the weapon's type"),)),
    feature("avatar_of_battle", CK, ED, 17, "Avatar della Battaglia / Avatar of Battle (Guerra 17, pag. 61)",
            ("Avatar della Battaglia", "Avatar of Battle"),
            ("Resistenza ai danni contundenti, perforanti e taglienti delle armi non magiche.",
             "Resistance to bludgeoning, piercing and slashing damage from nonmagical weapons."),
            subclass="war", roll_options=(AVATAR_OF_BATTLE,)),

    # Dominio dell'Inganno
    *_domain_spells("trickery", "Incantesimi del Dominio dell'Inganno / Trickery Domain Spells (Inganno 1, pag. 61)",
                    ("Incantesimi del Dominio dell'Inganno", "Trickery Domain Spells"), DOMAIN_SPELLS["trickery"]),
    feature("blessing_of_the_trickster", CK, ED, 1, "Benedizione dell'Ingannatore / Blessing of the Trickster (Inganno 1, pag. 61)",
            ("Benedizione dell'Ingannatore", "Blessing of the Trickster"),
            ("Azione: una creatura consenziente, non tu, ha vantaggio alle prove di Furtività per 1 ora o finché non la usi di nuovo.",
             "Action: a willing creature other than you has advantage on Stealth checks for 1 hour or until you use this again."),
            "action", subclass="trickery", on_use=OnUse(slot="action", ally_state=True, state=_trickster_state)),
    feature("divine_strike_trickery", CK, ED, 8, "Colpo Divino / Divine Strike (Inganno 8, pag. 61)", ("Colpo Divino", "Divine Strike"),
            ("Una volta per turno, con un colpo d'arma: 1d8 (2d8 dal 14°) di danni da veleno in più.",
             "Once per turn, on a weapon hit: 1d8 (2d8 from 14th) extra poison damage."),
            subclass="trickery", roll_options=(_divine_strike("trickery", "da veleno", "poison"),)),

    feature("cloak_of_shadows", CK, ED, 6,
            "Incanalare Divinità: Manto di Ombre / Channel Divinity: Cloak of Shadows (Inganno 6, pag. 61)",
            ("Manto di Ombre", "Cloak of Shadows"),
            ("Azione: spendi un uso e sei invisibile fino alla fine del tuo prossimo turno; finisce se attacchi o lanci un incantesimo.",
             "Action: spend a use and be invisible until the end of your next turn; it ends if you attack or cast a spell."),
            "action", subclass="trickery", roll_options=(CLOAK_ATTACK, CLOAK_CAST),
            on_use=OnUse(slot="action", spends=POOL, state=_cloak_state)),
    feature("invoke_duplicity", CK, ED, 2,
            "Incanalare Divinità: Invocare Duplicato / Channel Divinity: Invoke Duplicity (Inganno 2, pag. 61)",
            ("Invocare Duplicato", "Invoke Duplicity"),
            ("Azione: spendi un uso e crei un duplicato illusorio per 1 minuto, in concentrazione. Lanci incantesimi dal suo spazio; vantaggio agli attacchi se siete entrambi entro 1,5 m dal bersaglio.",
             "Action: spend a use and create an illusory duplicate for 1 minute, in concentration. Cast spells from its space; advantage on attacks if you are both within 5 ft of the target."),
            "action", subclass="trickery", roll_options=(DUPLICITY_ADVANTAGE,),
            on_use=OnUse(slot="action", spends=POOL, concentration=True, state=_duplicity_state,
                         available=lambda c: not state_on(c, "invoke_duplicity"))),
    feature("invoke_duplicity_move", CK, ED, 2,
            "Incanalare Divinità: Invocare Duplicato / Channel Divinity: Invoke Duplicity (Inganno 2, pag. 61)",
            ("Muovere il Duplicato", "Move the Duplicate"),
            ("Azione bonus, finché il duplicato esiste: lo muovi fino a 9 m (dal 17° livello ne muovi quanti vuoi).",
             "Bonus action while the duplicate exists: move it up to 30 ft (from 17th level, as many as you like)."),
            "bonus_action", subclass="trickery",
            on_use=OnUse(slot="bonus", cost=0, available=lambda c: state_on(c, "invoke_duplicity"))),
    feature("improved_duplicity", CK, ED, 17, "Duplicato Migliorato / Improved Duplicity (Inganno 17, pag. 61)",
            ("Duplicato Migliorato", "Improved Duplicity"),
            ("Invocare Duplicato crea fino a quattro duplicati e l'azione bonus ne muove un numero qualsiasi.",
             "Invoke Duplicity creates up to four duplicates and the bonus action moves any number of them."),
            subclass="trickery"),

    # Dominio della Luce
    *_domain_spells("light", "Incantesimi del Dominio della Luce / Light Domain Spells (Luce 1, pag. 61)",
                    ("Incantesimi del Dominio della Luce", "Light Domain Spells"), DOMAIN_SPELLS["light"]),
    feature("bonus_cantrip", CK, ED, 1, "Trucchetto Bonus / Bonus Cantrip (Luce 1, pag. 62)", ("Trucchetto Bonus", "Bonus Cantrip"),
            ("Conosci il trucchetto luce, in più rispetto a quelli del limite.", "You know the light cantrip, in addition to your limit."),
            subclass="light", granted_spells=("light",)),
    feature("warding_flare", CK, ED, 1, "Lampo di Interdizione / Warding Flare (Luce 1, pag. 62)",
            ("Lampo di Interdizione", "Warding Flare"),
            ("Reazione: un attaccante entro 9 m che vedi tira con svantaggio, se non è immune all'accecamento. Usi pari a Saggezza (minimo 1), al riposo lungo.",
             "Reaction: an attacker within 30 ft you can see attacks with disadvantage unless immune to blindness. Uses equal Wisdom (minimum 1), per long rest."),
            "reaction", subclass="light", uses=Uses(ability="wisdom", minimum=1), restoration="long_rest",
            on_use=OnUse(slot="reaction", state=_flare_state)),
    feature("radiance_of_the_dawn", CK, ED, 2,
            "Incanalare Divinità: Fulgore dell'Alba / Channel Divinity: Radiance of the Dawn (Luce 2, pag. 62)",
            ("Fulgore dell'Alba", "Radiance of the Dawn"),
            ("Azione: spendi un uso. Dissolve l'oscurità magica entro 9 m; le creature ostili fanno un TS Costituzione o subiscono 2d10 + livello radiosi (la metà se lo superano).",
             "Action: spend a use. Dispels magical darkness within 30 ft; hostile creatures make a Constitution save or take 2d10 + level radiant (half on a success)."),
            "action", subclass="light",
            on_use=OnUse(slot="action", spends=POOL, rolls="2d10", state=_radiance_state)),
    feature("improved_flare", CK, ED, 6, "Lampo Migliorato / Improved Flare (Luce 6, pag. 62)",
            ("Lampo Migliorato", "Improved Flare"),
            ("Il Lampo di Interdizione vale anche quando una creatura entro 9 m attacca un'altra; stessi usi.",
             "Warding Flare also works when a creature within 30 ft attacks another; same uses."),
            subclass="light"),
    feature("potent_spellcasting_light", CK, ED, 8, "Incantesimi Potenti / Potent Spellcasting (Luce 8, pag. 62)",
            ("Incantesimi Potenti", "Potent Spellcasting"),
            ("Ai danni di ogni tuo trucchetto da chierico si somma il modificatore di Saggezza.",
             "Add your Wisdom modifier to the damage of every cleric cantrip you cast."),
            subclass="light", modifiers=(_potent(),)),
    feature("corona_of_light", CK, ED, 17, "Corona di Luce / Corona of Light (Luce 17, pag. 62)",
            ("Corona di Luce", "Corona of Light"),
            ("Azione: per 1 minuto luce intensa a 18 m e fioca a 9 m; i nemici nella luce intensa hanno svantaggio ai TS contro fuoco e radioso.",
             "Action: for 1 minute bright light 60 ft and dim 30 ft; enemies in the bright light have disadvantage on saves against fire and radiant."),
            "action", subclass="light", on_use=OnUse(slot="action", state=_corona_state)),

    # Dominio della Natura
    *_domain_spells("nature", "Incantesimi del Dominio della Natura / Nature Domain Spells (Natura 1, pag. 62)",
                    ("Incantesimi del Dominio della Natura", "Nature Domain Spells"), DOMAIN_SPELLS["nature"]),
    feature("acolyte_of_nature", CK, ED, 1, "Accolito della Natura / Acolyte of Nature (Natura 1, pag. 62)",
            ("Accolito della Natura", "Acolyte of Nature"),
            ("Un trucchetto da druido a scelta e competenza in Addestrare Animali, Natura o Sopravvivenza.",
             "One druid cantrip of your choice and proficiency in Animal Handling, Nature or Survival."),
            subclass="nature",
            choices=(ChoiceSpec(group="nature_skill", levels={1: 1},
                                options=lambda _c: ["animal_handling", "nature", "survival"],
                                label=skill_label, grants="proficient"),
                     ChoiceSpec(group="nature_cantrip", levels={1: 1}, options=_no_options, spell_pick="extra"))),
    feature("nature_bonus_proficiency", CK, ED, 1, "Competenza Bonus / Bonus Proficiency (Natura 1, pag. 62)",
            ("Competenza Bonus (Natura)", "Bonus Proficiency (Nature)"),
            ("Competenza in armature pesanti.", "Proficiency with heavy armor."),
            subclass="nature", proficiency_grants={"armor": ("heavy",)}),
    feature("charm_animals_and_plants", CK, ED, 2,
            "Incanalare Divinità: Charme su Animali e Vegetali / Channel Divinity: Charm Animals and Plants (Natura 2, pag. 62)",
            ("Charme su Animali e Vegetali", "Charm Animals and Plants"),
            ("Azione: spendi un uso. Animali e vegetali entro 9 m fanno un TS Saggezza o sono affascinati per 1 minuto o fino al danno.",
             "Action: spend a use. Beasts and plants within 30 ft make a Wisdom save or are charmed for 1 minute or until damaged."),
            "action", subclass="nature",
            on_use=OnUse(slot="action", spends=POOL, state=_charm_state, target_effect=_charm_effect)),
    feature("dampen_elements", CK, ED, 6, "Mitigare Elementi / Dampen Elements (Natura 6, pag. 62)",
            ("Mitigare Elementi", "Dampen Elements"),
            ("Reazione: resistenza a un danno da acido, freddo, fulmine, fuoco o tuono, tuo o di un alleato entro 9 m.",
             "Reaction: resistance to acid, cold, lightning, fire or thunder damage, yours or an ally's within 30 ft."),
            "reaction", subclass="nature", roll_options=(DAMPEN_ELEMENTS,)),
    feature("divine_strike_nature", CK, ED, 8, "Colpo Divino / Divine Strike (Natura 8, pag. 62)", ("Colpo Divino", "Divine Strike"),
            ("Una volta per turno, con un colpo d'arma: 1d8 (2d8 dal 14°) di danni da freddo, fulmine o fuoco in più, a scelta.",
             "Once per turn, on a weapon hit: 1d8 (2d8 from 14th) extra cold, lightning or fire damage, your choice."),
            subclass="nature",
            roll_options=tuple(_divine_strike("nature", it, en, group=f"{CK}.divine_strike_nature", suffix=f"_{t}")
                               for t, it, en in (("cold", "da freddo", "cold"), ("lightning", "da fulmine", "lightning"),
                                                 ("fire", "da fuoco", "fire")))),
    feature("master_of_nature", CK, ED, 17, "Maestro della Natura / Master of Nature (Natura 17, pag. 62)",
            ("Maestro della Natura", "Master of Nature"),
            ("Azione bonus, finché Charme su Animali e Vegetali è attivo: comandi le creature affascinate; il comando lo dai al GM.",
             "Bonus action while Charm Animals and Plants is active: command the charmed creatures; you give the order to the GM."),
            "bonus_action", subclass="nature",
            on_use=OnUse(slot="bonus", cost=0, available=lambda c: state_on(c, "charm_animals_and_plants"))),

    # Dominio della Tempesta
    *_domain_spells("tempest", "Incantesimi del Dominio della Tempesta / Tempest Domain Spells (Tempesta 1, pag. 63)",
                    ("Incantesimi del Dominio della Tempesta", "Tempest Domain Spells"), DOMAIN_SPELLS["tempest"]),
    feature("tempest_bonus_proficiencies", CK, ED, 1, "Competenze Bonus / Bonus Proficiencies (Tempesta 1, pag. 63)",
            ("Competenze Bonus (Tempesta)", "Bonus Proficiencies (Tempest)"),
            ("Competenza in armature pesanti e armi da guerra.", "Proficiency with heavy armor and martial weapons."),
            subclass="tempest", proficiency_grants={"armor": ("heavy",), "weapons": ("martial",)}),
    feature("wrath_of_the_storm", CK, ED, 1, "Collera della Tempesta / Wrath of the Storm (Tempesta 1, pag. 63)",
            ("Collera della Tempesta", "Wrath of the Storm"),
            ("Reazione: chi ti colpisce entro 1,5 m fa un TS Destrezza o subisce 2d8 da fulmine o tuono (la metà se lo supera). Usi pari a Saggezza (minimo 1), al riposo lungo.",
             "Reaction: a creature within 5 ft that hits you makes a Dexterity save or takes 2d8 lightning or thunder (half on a success). Uses equal Wisdom (minimum 1), per long rest."),
            "reaction", subclass="tempest", uses=Uses(ability="wisdom", minimum=1), restoration="long_rest",
            on_use=OnUse(slot="reaction", rolls="2d8", state=_wrath_state)),
    feature("destructive_wrath", CK, ED, 2,
            "Incanalare Divinità: Collera Distruttiva / Channel Divinity: Destructive Wrath (Tempesta 2, pag. 63)",
            ("Collera Distruttiva", "Destructive Wrath"),
            ("Quando tiri danni da fulmine o tuono di un incantesimo, spendi un uso e i dadi valgono il massimo.",
             "When you roll lightning or thunder damage for a spell, spend a use and the dice deal maximum damage."),
            subclass="tempest", roll_options=(DESTRUCTIVE_WRATH,)),
    feature("thunderbolt_strike", CK, ED, 6, "Colpo del Tuono e del Fulmine / Thunderbolt Strike (Tempesta 6, pag. 63)",
            ("Colpo del Tuono e del Fulmine", "Thunderbolt Strike"),
            ("Se i tuoi danni da fulmine colpiscono una creatura Grande o più piccola, la spingi di 3 m lontano da te.",
             "When your lightning damage hits a Large or smaller creature, push it 10 ft away from you."),
            subclass="tempest", roll_options=(THUNDERBOLT_STRIKE,)),
    feature("divine_strike_tempest", CK, ED, 8, "Colpo Divino / Divine Strike (Tempesta 8, pag. 63)", ("Colpo Divino", "Divine Strike"),
            ("Una volta per turno, con un colpo d'arma: 1d8 (2d8 dal 14°) di danni da tuono in più.",
             "Once per turn, on a weapon hit: 1d8 (2d8 from 14th) extra thunder damage."),
            subclass="tempest", roll_options=(_divine_strike("tempest", "da tuono", "thunder"),)),

    feature("stormborn", CK, ED, 17, "Nato dalla Tempesta / Stormborn (Tempesta 17, pag. 63)",
            ("Nato dalla Tempesta", "Stormborn"),
            ("Velocità di volo pari a quella a terra, tranne sottoterra o al chiuso: «Usa» sospende il volo, «Termina» lo riattiva.",
             "Flying speed equal to your walking speed, except underground or indoors: «Use» suspends flight, «End» restores it."),
            subclass="tempest", modifiers=(Modifier("fly_speed", 1, when=lambda c: not state_on(c, "stormborn_off"),
                                                    source=f"feature:{CK}.stormborn"),),
            on_use=OnUse(cost=0, available=lambda c: not state_on(c, "stormborn_off"),
                         state=StateSpec("stormborn_off", ends_on=("manual",)))),

    # Dominio della Vita
    *_domain_spells("life", "Incantesimi del Dominio della Vita / Life Domain Spells (Vita 1, pag. 63)",
                    ("Incantesimi del Dominio della Vita", "Life Domain Spells"), DOMAIN_SPELLS["life"]),
    feature("life_bonus_proficiency", CK, ED, 1, "Competenza Bonus / Bonus Proficiency (Vita 1, pag. 63)",
            ("Competenza Bonus (Vita)", "Bonus Proficiency (Life)"),
            ("Competenza in armature pesanti.", "Proficiency with heavy armor."),
            subclass="life", proficiency_grants={"armor": ("heavy",)}),
    feature("disciple_of_life", CK, ED, 1, "Discepolo della Vita / Disciple of Life (Vita 1, pag. 63)",
            ("Discepolo della Vita", "Disciple of Life"),
            ("Un incantesimo di cura di 1° livello o superiore restituisce 2 PF più il livello dello slot in più.",
             "A healing spell of 1st level or higher restores 2 extra HP plus the slot's level."),
            subclass="life",
            modifiers=(Modifier("healing", lambda c: 2 + (c.casting_level or 0), when=_healing_roll,
                                source=f"feature:{CK}.disciple_of_life"),)),
    feature("preserve_life", CK, ED, 2,
            "Incanalare Divinità: Preservare Vita / Channel Divinity: Preserve Life (Vita 2, pag. 63)",
            ("Preservare Vita", "Preserve Life"),
            ("Azione: spendi un uso e distribuisci 5 × livello PF fra le creature entro 9 m, fino alla metà dei loro PF massimi; non su costrutti né non morti.",
             "Action: spend a use and split 5 × level HP among creatures within 30 ft, up to half their maximum HP; not on constructs or undead."),
            "action", subclass="life", on_use=OnUse(slot="action", spends=POOL, panel="preserve_life")),
    feature("blessed_healer", CK, ED, 6, "Guaritore Benedetto / Blessed Healer (Vita 6, pag. 63)",
            ("Guaritore Benedetto", "Blessed Healer"),
            ("Quando curi un'altra creatura con un incantesimo di 1° livello o superiore, recuperi 2 PF più il livello dell'incantesimo.",
             "When you heal another creature with a spell of 1st level or higher, you regain 2 HP plus the spell's level."),
            subclass="life", roll_options=(BLESSED_HEALER,)),
    feature("supreme_healing", CK, ED, 17, "Guarigione Suprema / Supreme Healing (Vita 17, pag. 63)",
            ("Guarigione Suprema", "Supreme Healing"),
            ("I dadi di un incantesimo di cura valgono sempre il massimo.", "The dice of a healing spell always count as their maximum."),
            subclass="life", modifiers=(Modifier("maximize_healing", 1, when=lambda c: c.roll == "spell_healing",
                                                 source=f"feature:{CK}.supreme_healing"),)),
    feature("divine_strike_life", CK, ED, 8, "Colpo Divino / Divine Strike (Vita 8, pag. 63)", ("Colpo Divino", "Divine Strike"),
            ("Una volta per turno, con un colpo d'arma: 1d8 (2d8 dal 14°) di danni radiosi in più.",
             "Once per turn, on a weapon hit: 1d8 (2d8 from 14th) extra radiant damage."),
            subclass="life", roll_options=(_divine_strike("life", "radiosi", "radiant"),)),
)

"""Barbaro 2014 e le sue sottoclassi: Cammino del Berserker e Cammino del Combattente Totemico.

Valori dalla scheda ``docs/superpowers/rules/2014/classes/barbarian.md``; i testi sono nostri, mai quelli del manuale.
"""
from __future__ import annotations

from typing import Any

from core.data.damage_types import DAMAGE_TYPES
from core.rules.catalog._common import (
    attacks_made, cannot_perceive_or_act, feature, heavy_armor, once_used, state_on,
)
from core.rules.states import begin_state
from core.rules.types import (
    ChoiceSpec, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, TargetEffect, UnarmoredAc, Uses, UseToggle,
    ZeroHpSave,
)

ED, CK = "2014", "barbarian"
RAGE = "barbarian.rage"
RECKLESS = "barbarian.reckless_attack"
ANIMALS = ["eagle", "wolf", "bear"]


def rage_damage(level: int) -> int:
    return 2 if level < 9 else 3 if level < 16 else 4


def raging(ctx: RuleContext) -> bool:
    """In ira e senza armatura pesante: l'armatura pesante annulla i benefici (e quelli dei totem)."""
    return state_on(ctx, "rage") and not heavy_armor(ctx.char)


def _melee_strength(ctx: RuleContext) -> bool:
    return ctx.ability == "strength" and ctx.attack_mode == "melee"


def _chosen(row: Any, group: str) -> list[str]:
    return list((row.options or {}).get(group, []))


def _rage_state(ctx: RuleContext, params: dict) -> StateSpec:
    """Lo stato dell'Ira dipende dal livello, dalla sottoclasse e da ciò che si sceglie entrando."""
    level, row = ctx.class_level, ctx.class_row
    berserker = row.subclass_key == "berserker"
    others: list[str] = []  # privilegi che agiscono su altri: sono mostrati sotto lo stato (D1)
    if row.subclass_key == "totem_warrior":
        spirit = _chosen(row, "totem_spirit")
        others += [f"{CK}.totem_{a}" for a in ("eagle", "wolf") if a in spirit]
        if level >= 14 and "bear" in _chosen(row, "totem_attunement"):
            others.append(f"{CK}.attunement_bear")
    frenzy = berserker and bool(params.get("frenzy"))
    # Ira Persistente (15): resta solo la perdita dei sensi; prima finisce anche a fine turno senza aver attaccato.
    ends = ("unconscious", "rest_short", "rest_long") + (() if level >= 15 else ("turn_end_inactive",))
    return StateSpec(
        "rage", rounds=10, ends_on=ends, blocks_casting=True, exhaustion_on_end=1 if frenzy else 0,
        immune_conditions=("charmed", "frightened") if berserker and level >= 6 else (),
        data={"damage": rage_damage(level), "frenzy": frenzy, "others": others},
    )


def _rage_resistances() -> list[Modifier]:
    return [Modifier(f"resistance:{t}", 1, when=raging, source=f"feature:{RAGE}")
            for t in ("bludgeoning", "piercing", "slashing")]


RAGE_MODIFIERS = (
    Modifier("advantage", 1, source=f"feature:{RAGE}",
             when=lambda c: raging(c) and c.ability == "strength" and c.roll in ("skill", "ability", "save")),
    Modifier("damage", lambda c: rage_damage(c.class_level), source=f"feature:{RAGE}",
             when=lambda c: raging(c) and c.roll == "damage" and _melee_strength(c)),
    *_rage_resistances(),
)


def _reckless_confirmed(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    """Fino al prossimo turno gli attacchi contro di lui hanno vantaggio (mostrato sulla scheda, D1)."""
    begin_state(ctx.char, StateSpec(
        "reckless", rounds=1, data={"others": [RECKLESS]}), RECKLESS, "Attacco Irruento")


def _reckless_declared(ctx: RuleContext) -> bool:
    return once_used(ctx.char, RECKLESS)


RECKLESS_ATTACK = RollOptionSpec(
    key=RECKLESS, phase="before", rolls=("attack",), mode="advantage", once_per_turn=True,
    label={"it": "Attacco Irruento: vantaggio ora, ma gli attacchi contro di te hanno vantaggio",
           "en": "Reckless Attack: advantage now, but attacks against you have advantage"},
    # va deciso al primo attacco del turno
    available=lambda c: _melee_strength(c) and attacks_made(c) == 0,
    on_confirm=_reckless_confirmed,
)

DANGER_SENSE = RollOptionSpec(
    key="barbarian.danger_sense", phase="before", rolls=("save",), mode="advantage",
    label={"it": "Percezione del Pericolo: l'effetto è visibile?", "en": "Danger Sense: is the effect visible?"},
    available=lambda c: c.ability == "dexterity" and not cannot_perceive_or_act(c.char),
)


def _frenzy_on(ctx: RuleContext) -> bool:
    rage = next((s for s in ctx.char.active_states or [] if s.get("key") == "rage"), None)
    return bool(rage and (rage.get("data") or {}).get("frenzy"))


FRENZY_ATTACK = RollOptionSpec(
    key="barbarian.frenzy_attack", phase="before", rolls=("attack",), slot="bonus",
    label={"it": "Frenesia: attacco in mischia come azione bonus", "en": "Frenzy: melee attack as a bonus action"},
    available=lambda c: _frenzy_on(c) and c.attack_mode == "melee",
)

RETALIATION = RollOptionSpec(
    key="barbarian.retaliation", phase="before", rolls=("attack",), slot="reaction",
    label={"it": "Ritorsione: una creatura entro 1,5 m ti ha colpito?",
           "en": "Retaliation: did a creature within 5 ft hit you?"},
    available=lambda c: c.attack_mode == "melee" and bool((c.turn or {}).get("damaged")),
)

WOLF_KNOCK = RollOptionSpec(
    key="barbarian.attunement_wolf_knock", phase="after_hit", rolls=("attack",), slot="bonus",
    label={"it": "Lupo: abbatti il bersaglio (Grande o più piccolo)?",
           "en": "Wolf: knock the target prone (Large or smaller)?"},
    available=lambda c: raging(c) and c.attack_mode == "melee",
    target_effect=lambda _c, _i: TargetEffect(condition="prone"),
)

BEAR_CHECK = RollOptionSpec(
    key="barbarian.aspect_bear_check", phase="before", rolls=("skill",), mode="advantage",
    label={"it": "Orso: prova per spingere, trascinare, sollevare o spezzare?",
           "en": "Bear: check to push, drag, lift or break?"},
    available=lambda c: c.ability == "strength",
)


def _intimidation(ctx: RuleContext, _params: dict) -> TargetEffect:
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    return TargetEffect(
        condition="frightened", save_ability="wisdom",
        save_dc=8 + ctx.char.proficiency_bonus + effective_ability_mod(ctx.char, "charisma"),
        ends_at={"anchor": "source", "edge": "end", "count": 1},
    )


def _strength_score(ctx: RuleContext) -> int:
    from core.rules.weapons import ability_score  # import locale
    return ability_score(ctx.char, "strength")


def _totem(group: str, key: str, level: int, title: str, name: tuple[str, str], summary: tuple[str, str], **kw: Any):
    return feature(f"{group}_{key}" if group != "totem" else f"totem_{key}", CK, ED, level, title, name, summary,
                   subclass="totem_warrior", option_group={"totem": "totem_spirit", "aspect": "totem_aspect",
                                                          "attunement": "totem_attunement"}[group],
                   option_key=key, **kw)


ANIMAL_EN = {"eagle": "Eagle", "wolf": "Wolf", "bear": "Bear"}


def _beast_choice(group: str, level: int) -> ChoiceSpec:
    # `label` serve solo all'import da Beyond, che chiama l'opzione col nome nudo dell'animale
    return ChoiceSpec(group=group, levels={level: 1}, options=lambda _ctx: list(ANIMALS),
                      label=lambda key: {"name": ANIMAL_EN[key], "summary": ""})


FEATURES = (
    feature("hit_points", CK, ED, 1, ("Punti Ferita / Hit Points (Barbaro 1, pag. 47)"),
            ("Punti Ferita", "Hit Points"),
            ("Dado vita d12; al 1° livello 12 + Costituzione, poi d12 (o 7) + Costituzione.",
             "Hit die d12; level 1 gives 12 + Constitution, then d12 (or 7) + Constitution."), no_row=True),
    feature("proficiencies", CK, ED, 1, ("Competenze / Proficiencies (Barbaro 1, pag. 47)"),
            ("Competenze", "Proficiencies"),
            ("Armature leggere e medie, scudi, armi semplici e da guerra, TS Forza e Costituzione, 2 abilità.",
             "Light and medium armor, shields, simple and martial weapons, Strength and Constitution saves, 2 skills."),
            no_row=True),
    feature("equipment", CK, ED, 1, ("Equipaggiamento / Equipment (Barbaro 1, pag. 48)"),
            ("Equipaggiamento", "Equipment"),
            ("Dotazione iniziale: ascia bipenne o arma da guerra, due asce o arma semplice, 4 giavellotti, pacco.",
             "Starting gear: greataxe or martial melee weapon, two handaxes or a simple weapon, 4 javelins, pack."),
            no_row=True),
    feature("rage", CK, ED, 1, ("Ira / Rage (Barbaro 1, pag. 48)"), ("Ira", "Rage"),
            ("Azione bonus: 1 minuto di ira. Vantaggio a prove e TS di Forza, danno in mischia con Forza, "
             "resistenza a danni fisici. Niente incantesimi né armatura pesante.",
             "Bonus action: 1 minute of rage. Advantage on Strength checks and saves, melee Strength damage bonus, "
             "resistance to physical damage. No spells, no heavy armor."),
            "bonus_action", uses=Uses(table={1: 2, 3: 3, 6: 4, 12: 5, 17: 6}, unlimited_from=20),
            restoration="long_rest", modifiers=RAGE_MODIFIERS,
            on_use=OnUse(
                slot="bonus", ends_concentration=True, state=_rage_state,
                available=lambda c: not state_on(c, "rage"),
                toggles=(UseToggle(
                    "frenzy", {"it": "Frenesia", "en": "Frenzy"},
                    available=lambda c: c.class_row.subclass_key == "berserker"),),
            )),
    feature("unarmored_defense", CK, ED, 1, ("Difesa Senza Armatura / Unarmored Defense (Barbaro 1, pag. 48)"),
            ("Difesa Senza Armatura", "Unarmored Defense"),
            ("Senza armatura CA = 10 + Destrezza + Costituzione; lo scudo si somma.",
             "Without armor AC = 10 + Dexterity + Constitution; a shield adds to it."),
            unarmored=UnarmoredAc(("dexterity", "constitution"))),
    feature("reckless_attack", CK, ED, 2, ("Attacco Irruento / Reckless Attack (Barbaro 2, pag. 48)"),
            ("Attacco Irruento", "Reckless Attack"),
            ("Al primo attacco del turno: vantaggio agli attacchi in mischia con Forza, ma chi ti attacca ha "
             "vantaggio fino al tuo turno successivo.",
             "On your first attack of the turn: advantage on melee Strength attacks, but attacks against you have "
             "advantage until your next turn."),
            roll_options=(RECKLESS_ATTACK,),
            modifiers=(Modifier(
                "advantage", 1, source=f"feature:{RECKLESS}",
                when=lambda c: c.roll == "attack" and _melee_strength(c) and _reckless_declared(c)),)),
    feature("danger_sense", CK, ED, 2, ("Percezione del Pericolo / Danger Sense (Barbaro 2, pag. 48)"),
            ("Percezione del Pericolo", "Danger Sense"),
            ("Vantaggio ai TS su Destrezza contro effetti che vedi; non da accecato, assordato o incapacitato.",
             "Advantage on Dexterity saves against effects you can see; not while blinded, deafened or incapacitated."),
            roll_options=(DANGER_SENSE,)),
    feature("primal_path", CK, ED, 3, ("Cammino Primordiale / Primal Path (Barbaro 3, pag. 48)"),
            ("Cammino Primordiale", "Primal Path"),
            ("Al 3° livello si sceglie il Cammino del Berserker o del Combattente Totemico.",
             "At level 3 you choose the Path of the Berserker or of the Totem Warrior."), no_row=True),
    feature("ability_score_improvement", CK, ED, 4,
            ("Aumento dei Punteggi di Caratteristica / Ability Score Improvement (Barbaro 4, 8, 12, 16, 19, pag. 49)"),
            ("Aumento dei Punteggi di Caratteristica", "Ability Score Improvement"),
            ("Ai livelli 4, 8, 12, 16 e 19: +2 a un punteggio o +1 a due, oppure un talento; massimo 20.",
             "At levels 4, 8, 12, 16 and 19: +2 to one score or +1 to two, or a feat; maximum 20."), no_row=True),
    feature("extra_attack", CK, ED, 5, ("Attacco Extra / Extra Attack (Barbaro 5, pag. 49)"),
            ("Attacco Extra", "Extra Attack"),
            ("Due attacchi con l'azione Attacco; non si somma ad altri Attacco Extra.",
             "Two attacks with the Attack action; does not stack with other Extra Attack."), attacks_per_action=2),
    feature("fast_movement", CK, ED, 5, ("Movimento Veloce / Fast Movement (Barbaro 5, pag. 49)"),
            ("Movimento Veloce", "Fast Movement"),
            ("Velocità +3 m (+10 ft), non con armatura pesante.", "Speed +10 ft, not in heavy armor."),
            modifiers=(Modifier("speed", 10, when=lambda c: not heavy_armor(c.char), source="feature:barbarian.fast_movement"),)),
    feature("feral_instinct", CK, ED, 7, ("Istinto Ferino / Feral Instinct (Barbaro 7, pag. 49)"),
            ("Istinto Ferino", "Feral Instinct"),
            ("Vantaggio all'iniziativa. Se sorpreso agisci nel primo turno solo entrando in ira prima di ogni altra cosa.",
             "Advantage on initiative. If surprised you act on your first turn only if you enter your rage first."),
            acts_when_surprised="rage",
            modifiers=(Modifier("advantage", 1, when=lambda c: c.roll == "initiative",
                                source="feature:barbarian.feral_instinct"),)),
    feature("brutal_critical", CK, ED, 9, ("Critico Brutale / Brutal Critical (Barbaro 9, 13, 17, pag. 49)"),
            ("Critico Brutale", "Brutal Critical"),
            ("Nei critici in mischia tiri 1 dado dell'arma in più (2 al 13°, 3 al 17°).",
             "On melee critical hits roll 1 extra weapon die (2 at 13th, 3 at 17th)."),
            modifiers=(Modifier(
                "crit_dice", lambda c: 1 if c.class_level < 13 else 2 if c.class_level < 17 else 3,
                when=lambda c: c.roll == "damage" and c.attack_mode == "melee",
                source="feature:barbarian.brutal_critical"),)),
    feature("relentless_rage", CK, ED, 11, ("Ira Implacabile / Relentless Rage (Barbaro 11, pag. 49)"),
            ("Ira Implacabile", "Relentless Rage"),
            ("A 0 PF in ira (senza morte istantanea): TS Costituzione CD 10, +5 a ogni uso fino al riposo; se riesce, 1 PF.",
             "At 0 HP while raging (not killed outright): Constitution save DC 10, +5 each use until a rest; on success, 1 HP."),
            zero_hp_save=ZeroHpSave(state="rage")),
    feature("persistent_rage", CK, ED, 15, ("Ira Persistente / Persistent Rage (Barbaro 15, pag. 49)"),
            ("Ira Persistente", "Persistent Rage"),
            ("L'ira finisce solo se perdi i sensi o la termini tu: niente fine per mancanza di attacchi o danni.",
             "Your rage ends only if you fall unconscious or end it: no ending for lack of attacks or damage.")),
    feature("indomitable_might", CK, ED, 18, ("Potenza Indomabile / Indomitable Might (Barbaro 18, pag. 49)"),
            ("Potenza Indomabile", "Indomitable Might"),
            ("Nelle prove di Forza il totale minimo è il tuo punteggio di Forza.",
             "On Strength checks your total is at least your Strength score."),
            modifiers=(Modifier("min_total", _strength_score, source="feature:barbarian.indomitable_might",
                                when=lambda c: c.roll in ("skill", "ability") and c.ability == "strength"),)),
    feature("primal_champion", CK, ED, 20, ("Campione Primordiale / Primal Champion (Barbaro 20, pag. 49)"),
            ("Campione Primordiale", "Primal Champion"),
            ("Forza e Costituzione +4, massimo 24. Le ire sono illimitate.",
             "Strength and Constitution +4, maximum 24. Rages are unlimited."),
            ability_bonus={"strength": 4, "constitution": 4}, ability_cap=24),

    # Cammino del Berserker
    feature("frenzy", CK, ED, 3, ("Frenesia / Frenzy (Cammino del Berserker 3, pag. 49)"),
            ("Frenesia", "Frenzy"),
            ("Scelta entrando in ira: un attacco in mischia come azione bonus per turno; a fine ira +1 spossatezza.",
             "Chosen when you rage: one melee attack per turn as a bonus action; one level of exhaustion when it ends."),
            subclass="berserker", roll_options=(FRENZY_ATTACK,)),
    feature("mindless_rage", CK, ED, 6, ("Ira Incontenibile / Mindless Rage (Cammino del Berserker 6, pag. 49)"),
            ("Ira Incontenibile", "Mindless Rage"),
            ("In ira sei immune ad affascinato e spaventato; quelle già presenti restano sospese finché dura.",
             "While raging you are immune to charmed and frightened; existing ones are suspended while it lasts."),
            subclass="berserker"),
    feature("intimidating_presence", CK, ED, 10,
            ("Presenza Intimidatoria / Intimidating Presence (Cammino del Berserker 10, pag. 49)"),
            ("Presenza Intimidatoria", "Intimidating Presence"),
            ("Azione: una creatura entro 9 m fa un TS Saggezza (CD 8 + competenza + Carisma) o è spaventata; "
             "si prolunga con un'azione.",
             "Action: a creature within 30 ft makes a Wisdom save (DC 8 + proficiency + Charisma) or is frightened; "
             "extend it with an action."),
            "action", subclass="berserker", on_use=OnUse(slot="action", target_effect=_intimidation)),
    feature("retaliation", CK, ED, 14, ("Ritorsione / Retaliation (Cammino del Berserker 14, pag. 50)"),
            ("Ritorsione", "Retaliation"),
            ("Reazione: dopo il danno di una creatura entro 1,5 m, attacchi quella creatura in mischia.",
             "Reaction: after a creature within 5 ft damages you, make a melee attack against it."),
            subclass="berserker", roll_options=(RETALIATION,)),

    # Cammino del Combattente Totemico
    feature("spirit_seeker", CK, ED, 3, ("Cercatore di Spiriti / Spirit Seeker (Combattente Totemico 3, pag. 50)"),
            ("Cercatore di Spiriti", "Spirit Seeker"),
            ("Percezione delle bestie e Parlare con gli animali, solo come rituali.",
             "Beast sense and speak with animals, as rituals only."),
            subclass="totem_warrior", granted_spells=("beast-sense", "speak-with-animals")),
    feature("totem_spirit", CK, ED, 3, ("Spirito Totemico / Totem Spirit (Combattente Totemico 3, pag. 50)"),
            ("Spirito Totemico", "Totem Spirit"),
            ("Scegli un animale totemico: Aquila, Lupo o Orso.", "Choose a totem animal: Eagle, Wolf or Bear."),
            subclass="totem_warrior", choices=(_beast_choice("totem_spirit", 3),), no_row=True),
    _totem("totem", "eagle", 3, ("Aquila / Eagle (Combattente Totemico 3, pag. 50)"),
           ("Aquila (Spirito Totemico)", "Eagle (Totem Spirit)"),
           ("In ira, senza armatura pesante: attacchi di opportunità contro di te con svantaggio; Scatto come azione bonus.",
            "While raging, without heavy armor: opportunity attacks against you have disadvantage; Dash as a bonus action."),
           action_type="bonus_action", on_use=OnUse(slot="bonus", available=raging)),
    _totem("totem", "wolf", 3, ("Lupo / Wolf (Combattente Totemico 3, pag. 50)"),
           ("Lupo (Spirito Totemico)", "Wolf (Totem Spirit)"),
           ("In ira, gli alleati hanno vantaggio in mischia contro i nemici entro 1,5 m da te.",
            "While raging, allies have advantage on melee attacks against enemies within 5 ft of you.")),
    _totem("totem", "bear", 3, ("Orso / Bear (Combattente Totemico 3, pag. 50)"),
           ("Orso (Spirito Totemico)", "Bear (Totem Spirit)"),
           ("In ira hai resistenza a tutti i danni tranne lo psichico.",
            "While raging you resist all damage except psychic."),
           modifiers=tuple(Modifier(f"resistance:{t}", 1, when=raging, source="feature:barbarian.totem_bear")
                           for t in DAMAGE_TYPES if t != "psychic")),
    feature("aspect_of_the_beast", CK, ED, 6,
            ("Aspetto della Bestia / Aspect of the Beast (Combattente Totemico 6, pag. 50)"),
            ("Aspetto della Bestia", "Aspect of the Beast"),
            ("Scegli un animale totemico, anche diverso: ne ottieni il beneficio, che non richiede l'ira.",
             "Choose a totem animal, even a different one: you gain its benefit, which needs no rage."),
            subclass="totem_warrior", choices=(_beast_choice("totem_aspect", 6),), no_row=True),
    _totem("aspect", "eagle", 6, ("Aquila / Eagle (Combattente Totemico 6, pag. 50)"),
           ("Aquila (Aspetto della Bestia)", "Eagle (Aspect of the Beast)"),
           ("Vista a 1,5 km, dettagli a 30 m; la luce fioca non dà svantaggio a Percezione.",
            "Sight out to a mile, detail at 100 ft; dim light does not impose disadvantage on Perception.")),
    _totem("aspect", "wolf", 6, ("Lupo / Wolf (Combattente Totemico 6, pag. 50)"),
           ("Lupo (Aspetto della Bestia)", "Wolf (Aspect of the Beast)"),
           ("Segui tracce a passo veloce e ti muovi furtivo a passo normale.",
            "Track at a fast pace and move stealthily at a normal pace.")),
    _totem("aspect", "bear", 6, ("Orso / Bear (Combattente Totemico 6, pag. 50)"),
           ("Orso (Aspetto della Bestia)", "Bear (Aspect of the Beast)"),
           ("Capacità di trasporto doppia; vantaggio alle prove di Forza per spingere, trascinare, sollevare o spezzare.",
            "Carrying capacity doubled; advantage on Strength checks to push, drag, lift or break."),
           roll_options=(BEAR_CHECK,), modifiers=(Modifier("carry_double", 1, source="feature:barbarian.aspect_bear"),)),
    feature("spirit_walker", CK, ED, 10, ("Viandante Spirituale / Spirit Walker (Combattente Totemico 10, pag. 50)"),
            ("Viandante Spirituale", "Spirit Walker"),
            ("Comunione con la natura, solo come rituale.", "Commune with nature, as a ritual only."),
            subclass="totem_warrior", granted_spells=("commune-with-nature",)),
    feature("totemic_attunement", CK, ED, 14,
            ("Sintonia Totemica / Totemic Attunement (Combattente Totemico 14, pag. 50)"),
            ("Sintonia Totemica", "Totemic Attunement"),
            ("Scegli un animale totemico, anche ripetuto: ne ottieni il beneficio.",
             "Choose a totem animal, even a repeat: you gain its benefit."),
            subclass="totem_warrior", choices=(_beast_choice("totem_attunement", 14),), no_row=True),
    _totem("attunement", "eagle", 14, ("Aquila / Eagle (Combattente Totemico 14, pag. 50)"),
           ("Aquila (Sintonia Totemica)", "Eagle (Totemic Attunement)"),
           ("In ira hai velocità di volo pari a quella a terra; se finisci il turno in aria senza sostegno, cadi.",
            "While raging you have a flying speed equal to your walking speed; you fall if you end your turn in the air."),
           modifiers=(Modifier("fly_speed", 1, when=raging, source="feature:barbarian.attunement_eagle"),)),
    _totem("attunement", "wolf", 14, ("Lupo / Wolf (Combattente Totemico 14, pag. 50)"),
           ("Lupo (Sintonia Totemica)", "Wolf (Totemic Attunement)"),
           ("In ira, azione bonus: butti a terra una creatura Grande o più piccola colpita in mischia.",
            "While raging, bonus action: knock a Large or smaller creature you hit in melee prone."),
           roll_options=(WOLF_KNOCK,)),
    _totem("attunement", "bear", 14, ("Orso / Bear (Combattente Totemico 14, pag. 50)"),
           ("Orso (Sintonia Totemica)", "Bear (Totemic Attunement)"),
           ("In ira i nemici entro 1,5 m hanno svantaggio ad attaccare chi non è tu; immune chi non ti vede né sente.",
            "While raging, enemies within 5 ft have disadvantage attacking anyone but you; immune if they can't see or hear you.")),

    feature("multiclassing", CK, ED, 1, ("Multiclasse: Barbaro / Multiclassing: Barbarian (Multiclasse, pag. 163)"),
            ("Multiclasse: Barbaro", "Multiclassing: Barbarian"),
            ("Requisito Forza 13. Da multiclasse: scudi, armi semplici e da guerra; Attacco Extra non si somma.",
             "Requires Strength 13. As a multiclass: shields, simple and martial weapons; Extra Attack does not stack."),
            no_row=True),
)

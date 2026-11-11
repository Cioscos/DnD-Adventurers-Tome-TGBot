"""Paladino 2014 e i suoi giuramenti: Devozione, Antichi e Vendetta.

Valori dalla scheda ``docs/superpowers/rules/2014/classes/paladin.md``; i testi sono nostri, mai quelli del manuale.
Gli stili di combattimento sono opzioni di una scelta (``fighting_style``); le opzioni di Incanalare Divinità sono privilegi
del giuramento che spendono gli usi della riserva comune; gli incantesimi di giuramento sono sempre preparati (D4).
"""
from __future__ import annotations

from typing import Any

from core.rules.catalog._common import feature, state_on, style_options
from core.rules.catalog.y2014.fighter import (
    _dueling, _great_weapon, _protection_effect, _weapon_in_hand, _wears_armor, _wields_shield,
)
from core.rules.states import is_conscious
from core.rules.condition_removal import ConditionRemoval
from core.rules.types import (
    AuraSpec, ChoiceSpec, Cost, FeatureSpec, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, TargetEffect, UseChoice, Uses,
)

ED, CK = "2014", "paladin"
POOL = f"{CK}.channel_divinity"
LAY_ON_HANDS = f"{CK}.lay_on_hands"
SMITE, SMITE_FIEND = f"{CK}.divine_smite", f"{CK}.divine_smite_fiend"
STYLES = ("great_weapon", "defense", "dueling", "protection")
SAVE_ROLLS = ("save", "death_save", "concentration")

# Due incantesimi per ogni soglia (3°, 5°, 9°, 13°, 17°): ``srd_index``, chiavi di ``GRANTED_SPELLS``.
OATH_SPELLS = {
    "devotion": (("protection-from-evil-and-good", "sanctuary"), ("lesser-restoration", "zone-of-truth"),
                 ("dispel-magic", "beacon-of-hope"), ("guardian-of-faith", "freedom-of-movement"), ("flame-strike", "commune")),
    "ancients": (("ensnaring-strike", "speak-with-animals"), ("moonbeam", "misty-step"), ("plant-growth", "protection-from-energy"),
                 ("stoneskin", "ice-storm"), ("commune-with-nature", "tree-stride")),
    "vengeance": (("bane", "hunters-mark"), ("hold-person", "misty-step"), ("haste", "protection-from-energy"),
                  ("banishment", "dimension-door"), ("hold-monster", "scrying")),
}
OATH_LEVELS = (3, 5, 9, 13, 17)


# ---------------------------------------------------------------------------
# Valori comuni
# ---------------------------------------------------------------------------

def _cha_mod(ctx: RuleContext) -> int:
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    return effective_ability_mod(ctx.char, "charisma")


def _cha_bonus(ctx: RuleContext) -> int:
    """Il modificatore di Carisma, almeno +1 (Aura di Protezione, Arma Consacrata)."""
    return max(1, _cha_mod(ctx))


def _spell_dc(ctx: RuleContext) -> int:
    """CD degli incantesimi da paladino (le opzioni di Incanalare Divinità usano questa)."""
    from core.rules.spellcasting import caster_stats  # import locale: spellcasting usa il catalogo
    mine = next((s.save_dc for s in caster_stats(ctx.char) if ctx.class_row is not None and s.class_id == ctx.class_row.id), None)
    return mine if mine is not None else 8 + ctx.char.proficiency_bonus + _cha_mod(ctx)


def _aura_range(ctx: RuleContext) -> int:
    """3 m (10 piedi); 9 m (30 piedi) dal 18° livello (Aure Migliorate)."""
    return 30 if ctx.class_level >= 18 else 10


def _melee_weapon(ctx: RuleContext) -> bool:
    """Un attacco con un'arma da mischia (non un'arma da lancio né a distanza, non un incantesimo)."""
    return _weapon_in_hand(ctx) and ctx.attack_mode in ("melee", "offhand")


def _metres(feet: int) -> str:
    value = feet * 0.3
    return f"{value:.1f}".replace(".", ",").removesuffix(",0")


def _say(it: str, en: str):
    return lambda _ctx, _inputs: {"it": it, "en": en}


# ---------------------------------------------------------------------------
# Imposizione delle Mani
# ---------------------------------------------------------------------------

_LOH_MODES = {
    "self": {"it": "Cura PF a te stesso", "en": "Heal yourself"},
    "other": {"it": "Cura PF a un altro", "en": "Heal another creature"},
    "cure": {"it": "Cura un veleno o una malattia (5 punti ciascuno)", "en": "Cure a poison or disease (5 points each)"},
}


def _loh_notes(_ctx: RuleContext, params: dict) -> list[str]:
    """Esiti per chi usa il privilegio: la cura di un altro fuori serata, e l'eccezione di costrutti e non morti."""
    if params.get("mode") == "other" and params.get("target_character_id") is None:
        return ["lay_on_hands_other"]
    return []  # veleno e malattia sono nel meccanismo comune (``removal``)


# Cinque punti per un veleno o una malattia (PHB 2014): il veleno è la condizione, la malattia una nota. Foglio comune.
_LOH_REMOVAL = ConditionRemoval(
    ("poisoned",), ("disease",), count=None, modes=("cure",), cost_each=5,
    footer={"it": "Non vale su costrutti e non morti.", "en": "Not on constructs or undead."})

LAY_ON_HANDS_USE = OnUse(
    slot="action", choose_amount=True, heal=lambda _c, _r: 1, heal_when=lambda _c, params: params.get("mode") == "self",
    heal_ally_when=lambda _c, params: params.get("mode") == "other", ally_modes=("other",),
    notes=_loh_notes, removal=_LOH_REMOVAL,
    choices=(UseChoice("mode", {"it": "Su chi", "en": "On whom"}, lambda _c: list(_LOH_MODES), lambda k: _LOH_MODES[k]),))


# ---------------------------------------------------------------------------
# Stile di Combattimento
# ---------------------------------------------------------------------------

def _style(key: str, title: str, name: tuple[str, str], summary: tuple[str, str], action_type: str | None = None, **kw: Any):
    return feature(f"style_{key}", CK, ED, 2, title, name, summary, action_type, option_group="fighting_style",
                   option_key=key, **kw)


STYLE_ROWS = (
    _style("great_weapon",
           "Combattere con Armi Possenti / Great Weapon Fighting (Stile di Combattimento, Paladino 2, pag. 97)",
           ("Combattere con Armi Possenti", "Great Weapon Fighting"),
           ("Con un'arma da mischia a due mani, i dadi dell'arma che mostrano 1 o 2 si ritirano una volta e vale il nuovo risultato.",
            "With a melee weapon held in two hands, weapon dice showing 1 or 2 are rerolled once and the new result stands."),
           modifiers=(Modifier("damage_reroll", 2, when=_great_weapon, source=f"feature:{CK}.style_great_weapon"),)),
    _style("defense", "Difesa / Defense (Stile di Combattimento, Paladino 2, pag. 97)", ("Difesa", "Defense"),
           ("+1 alla CA finché indossi un'armatura (lo scudo da solo non basta).",
            "+1 to AC while you wear armor (a shield alone does not count)."),
           modifiers=(Modifier("ac", 1, when=lambda c: c.roll == "ac" and _wears_armor(c), source=f"feature:{CK}.style_defense"),)),
    _style("dueling", "Duellare / Dueling (Stile di Combattimento, Paladino 2, pag. 97)", ("Duellare", "Dueling"),
           ("+2 al danno con un'arma da mischia impugnata a una mano, se non impugni altre armi (lo scudo va bene).",
            "+2 damage with a melee weapon held in one hand when you hold no other weapon (a shield is fine)."),
           modifiers=(Modifier("damage", 2, when=_dueling, source=f"feature:{CK}.style_dueling"),)),
    _style("protection", "Protezione / Protection (Stile di Combattimento, Paladino 2, pag. 97)", ("Protezione", "Protection"),
           ("Reazione, con uno scudo: una creatura che vedi attacca un altro bersaglio entro 1,5 m da te e ha svantaggio al tiro.",
            "Reaction, with a shield: a creature you see attacks a target other than you within 5 ft of you and has disadvantage."),
           "reaction", on_use=OnUse(slot="reaction", available=_wields_shield, target_effect=_protection_effect)),
)


# ---------------------------------------------------------------------------
# Punizione Divina
# ---------------------------------------------------------------------------

def _smite_dice(_ctx: RuleContext, inputs: dict) -> str:
    """2d8 con uno slot di 1° livello, un d8 in più per ogni livello oltre il primo, al massimo 5d8."""
    return f"{min(5, 1 + int(inputs.get('slot_level') or 1))}d8"


def _fiend_available(ctx: RuleContext) -> bool:
    from core.rules.roll_options import slot_choices  # import locale: roll_options usa il catalogo
    return _melee_weapon(ctx) and (SMITE in ctx.confirmed or bool(slot_choices(ctx.char, 1)))


DIVINE_SMITE = RollOptionSpec(
    key=SMITE, phase="after_hit", rolls=("attack",), requires_input="slot", cost=Cost(spell_slot_min=1),
    extra_damage_type="radiant", extra_dice=_smite_dice, available=_melee_weapon,
    label={"it": "Punizione Divina: spendi uno slot per danni radiosi in più (2d8, +1d8 per livello oltre il 1°, massimo 5d8)",
           "en": "Divine Smite: spend a slot for extra radiant damage (2d8, +1d8 per level above 1st, up to 5d8)"},
    effect=_say("I dadi in più sono danni radiosi.", "The extra dice are radiant damage."))
DIVINE_SMITE_FIEND = RollOptionSpec(
    key=SMITE_FIEND, phase="after_hit", rolls=("attack",), needs=SMITE, extra_damage_type="radiant", extra_dice=lambda _c, _i: "1d8", available=_fiend_available,
    label={"it": "Punizione Divina: il bersaglio è un non morto o un immondo? +1d8 radioso",
           "en": "Divine Smite: is the target an undead or a fiend? +1d8 radiant"})
IMPROVED_SMITE = RollOptionSpec(
    key=f"{CK}.improved_divine_smite", phase="before", rolls=("attack",), automatic=True, extra_damage_type="radiant", extra_dice=lambda _c, _i: "1d8",
    available=_melee_weapon,
    label={"it": "Punizione Divina Migliorata: 1d8 radioso in più", "en": "Improved Divine Smite: extra 1d8 radiant"},
    effect=_say("Punizione Divina Migliorata: 1d8 danni radiosi in più, già nel totale.",
                "Improved Divine Smite: an extra 1d8 radiant damage, already in the total."))


# ---------------------------------------------------------------------------
# Incanalare Divinità: ogni effetto è un privilegio che spende gli usi della riserva comune
# ---------------------------------------------------------------------------

def _turn_state(key: str):
    def state(ctx: RuleContext, _params: dict) -> StateSpec:
        return StateSpec(key, rounds=10, ends_on=("manual",), data={"dc": _spell_dc(ctx), "save": "wisdom", "others": [f"{CK}.{key}"]})
    return state


def _turn_effect(note: str):
    def effect(ctx: RuleContext, _params: dict) -> TargetEffect:
        return TargetEffect(condition="custom:turned", save_ability="wisdom", save_dc=_spell_dc(ctx), rounds=10, note=note)
    return effect


def _wielded_weapons(ctx: RuleContext) -> list[Any]:
    return [i for i in ctx.char.items or [] if i.is_equipped and i.item_type == "weapon"]


def _weapon_label(ctx: RuleContext, key: str) -> dict:
    name = next((i.name for i in _wielded_weapons(ctx) if str(i.id) == key), key)
    return {"it": name, "en": name}


def _sacred_state(ctx: RuleContext, params: dict) -> StateSpec:
    return StateSpec("sacred_weapon", rounds=10, ends_on=("manual", "unconscious"),
                     data={"weapon_id": int(params["weapon"]), "bound_item": int(params["weapon"]), "attack_bonus": _cha_bonus(ctx)})


def _sacred_bonus(ctx: RuleContext) -> int:
    state = next((s for s in ctx.char.active_states or [] if s.get("key") == "sacred_weapon"), None)
    return int(((state or {}).get("data") or {}).get("attack_bonus") or 0)


def _sacred_applies(ctx: RuleContext) -> bool:
    """L'attacco è con l'arma legata, ancora impugnata."""
    state = next((s for s in ctx.char.active_states or [] if s.get("key") == "sacred_weapon"), None)
    weapon = ((state or {}).get("data") or {}).get("weapon_id")
    return (ctx.roll == "attack" and ctx.spell is None and ctx.item is not None and ctx.item.id == weapon
            and bool(ctx.item.is_equipped))


def _nimbus_state(_ctx: RuleContext, _params: dict) -> StateSpec:
    return StateSpec("holy_nimbus", rounds=10, ends_on=("manual",), data={"others": [f"{CK}.holy_nimbus"], "start_damage": 10, "radius_m": 9})


HOLY_NIMBUS_SAVE = RollOptionSpec(
    key=f"{CK}.holy_nimbus_save", phase="before", rolls=("save",), mode="advantage", available=lambda c: state_on(c, "holy_nimbus"),
    label={"it": "Nube Sacra: l'incantesimo è lanciato da un immondo o da un non morto? Vantaggio al TS",
           "en": "Holy Nimbus: is the spell cast by a fiend or an undead? Advantage on the save"})
PURITY_ADVANTAGE = RollOptionSpec(
    key=f"{CK}.purity_of_spirit", phase="before", rolls=("save",), mode="advantage",
    label={"it": "Purezza di Spirito: l'effetto è charme, paura o possessione di un'aberrazione, celestiale, elementale, folletto, immondo o non morto? Vantaggio",
           "en": "Purity of Spirit: is it charm, fear or possession by an aberration, celestial, elemental, fey, fiend or undead? Advantage"})
PURITY_IMMUNE = RollOptionSpec(
    key=f"{CK}.purity_of_spirit_immune", phase="after_roll", after="succeed", rolls=("save",),
    label={"it": "Purezza di Spirito: charme, paura o possessione di quei tipi di creatura non ti riguardano (il TS riesce)",
           "en": "Purity of Spirit: charm, fear or possession by those creature types cannot affect you (the save succeeds)"})
WARDING = RollOptionSpec(
    key=f"{CK}.aura_of_warding", phase="damage_in", rolls=("damage_taken",), grants_resistance=True,
    label={"it": "Aura di Interdizione: il danno viene da un incantesimo? Resistenza, danno dimezzato",
           "en": "Aura of Warding: does the damage come from a spell? Resistance, damage halved"})


def _wrath_effect(ctx: RuleContext, _params: dict) -> TargetEffect:
    """Trattenuto; il bersaglio sceglie Forza o Destrezza per il TS (lo segna il GM), ripetuto a fine turno."""
    return TargetEffect(condition="restrained", save_ability="strength", save_dc=_spell_dc(ctx), repeat_save="end")


def _abjure_effect(ctx: RuleContext, _params: dict) -> TargetEffect:
    return TargetEffect(condition="frightened", save_ability="wisdom", save_dc=_spell_dc(ctx), rounds=10, note="abjure_enemy")


def _angel_effect(ctx: RuleContext, _params: dict) -> TargetEffect:
    return TargetEffect(condition="frightened", save_ability="wisdom", save_dc=_spell_dc(ctx), rounds=10, note="avenging_angel")


def _abjure_state(ctx: RuleContext, _params: dict) -> StateSpec:
    return StateSpec("abjure_enemy", rounds=10, ends_on=("manual",),
                     data={"dc": _spell_dc(ctx), "save": "wisdom", "others": [f"{CK}.abjure_enemy"]})


def _wrath_state(ctx: RuleContext, _params: dict) -> StateSpec:
    return StateSpec("natures_wrath", rounds=10, ends_on=("manual",),
                     data={"dc": _spell_dc(ctx), "save": "strength", "others": [f"{CK}.natures_wrath"]})


def _vow_state(_ctx: RuleContext, _params: dict) -> StateSpec:
    return StateSpec("vow_of_enmity", rounds=10, ends_on=("manual",), data={"others": [f"{CK}.vow_of_enmity"]})


VOW_ATTACK = RollOptionSpec(
    key=f"{CK}.vow_of_enmity_attack", phase="before", rolls=("attack",), mode="advantage", available=lambda c: state_on(c, "vow_of_enmity"),
    label={"it": "Giuramento di Inimicizia: l'attacco è contro la creatura giurata? Vantaggio",
           "en": "Vow of Enmity: is the attack against the creature you swore against? Advantage"})
OPPORTUNITY_ATTACK = RollOptionSpec(
    key=f"{CK}.opportunity_attack", phase="before", rolls=("attack",), slot="reaction", offered_on_damage=False,
    available=_melee_weapon,
    label={"it": "Attacco di opportunità: spende la reazione", "en": "Opportunity attack: spends your reaction"})


def _avenger_effect(ctx: RuleContext, _inputs: dict) -> dict[str, str]:
    from core.rules.modifiers import effective_speed  # import locale: modifiers usa il catalogo
    half = effective_speed(ctx.char, ctx.char.speed) // 2
    return {"it": f"Muoviti fino a metà della tua velocità ({_metres(half)} m) senza provocare attacchi di opportunità.",
            "en": f"Move up to half your speed ({half} ft) without provoking opportunity attacks."}


RELENTLESS_AVENGER = RollOptionSpec(
    key=f"{CK}.relentless_avenger", phase="after_hit", rolls=("attack",), needs=OPPORTUNITY_ATTACK.key, available=_melee_weapon,
    label={"it": "Vendicatore Implacabile: muoviti di metà velocità dopo il colpo", "en": "Relentless Avenger: move half your speed after the hit"},
    effect=_avenger_effect)
SOUL_OF_VENGEANCE = RollOptionSpec(
    key=f"{CK}.soul_of_vengeance", phase="before", rolls=("attack",), slot="reaction", offered_on_damage=False,
    available=lambda c: _melee_weapon(c) and state_on(c, "vow_of_enmity"),
    label={"it": "Anima di Vendetta: la creatura sotto Giuramento di Inimicizia ha attaccato? Reazione: attacco in mischia",
           "en": "Soul of Vengeance: did the creature under your Vow of Enmity attack? Reaction: melee attack"})


def _angel_state(ctx: RuleContext, _params: dict) -> StateSpec:
    return StateSpec("avenging_angel", rounds=600, ends_on=("manual",),
                     data={"dc": _spell_dc(ctx), "save": "wisdom", "others": [f"{CK}.avenging_angel"], "radius_m": 9, "fly_ft": 60})


def _champion_state(_ctx: RuleContext, _params: dict) -> StateSpec:
    return StateSpec("elder_champion", rounds=10, ends_on=("manual",), data={"others": [f"{CK}.elder_champion"], "start_heal": 10})


def _champion_heal(ctx: RuleContext) -> int:
    return 10 if state_on(ctx, "elder_champion") and not ctx.char.is_dead else 0


def _permanent_note(key: str) -> StateSpec:
    """Lo stato sempre attivo che porta il testo di un privilegio a GM e gruppo (R36)."""
    return StateSpec(key, ends_on=("manual",), data={"others": [f"{CK}.{key}"], "permanent": True})


def _purity_state() -> StateSpec:
    return _permanent_note("purity_of_spirit")


def _drops_to_zero(ctx: RuleContext) -> bool:
    """In piedi, e il danno che sta per subire (se lo si sa) lo porta a 0 PF: solo allora Sentinella Imperitura si offre."""
    char = ctx.char
    if char.is_dead or char.current_hit_points <= 0:
        return False
    return ctx.damage is None or ctx.damage >= char.current_hit_points + (char.temp_hp or 0)


UNDYING_SENTINEL = f"{CK}.undying_sentinel"
SENTINEL = RollOptionSpec(
    key=UNDYING_SENTINEL, phase="damage_in", rolls=("damage_taken",), holds_at_one=True, cost=Cost(feature_key=UNDYING_SENTINEL),
    label={"it": "Sentinella Imperitura: se il danno ti porta a 0 PF senza ucciderti sul colpo, resti a 1 PF (un uso, riposo lungo)",
           "en": "Undying Sentinel: if the damage would drop you to 0 HP without killing you outright, you stay at 1 HP (one use, long rest)"},
    available=_drops_to_zero)


def _removable_conditions(ctx: RuleContext) -> list[str]:
    return [k for k, v in (ctx.char.conditions or {}).items() if v is True]


def _condition_label(_ctx: RuleContext, key: str) -> dict:
    from core.data.labels import condition_label  # import locale
    return {"it": condition_label(key), "en": key.removeprefix("custom:").replace("_", " ").title()}


# ---------------------------------------------------------------------------
# Incantesimi di giuramento
# ---------------------------------------------------------------------------

def _oath_spells(oath: str, title: str, name: tuple[str, str]) -> list[FeatureSpec]:
    """Due incantesimi per ogni soglia (3°, 5°, 9°, 13°, 17°). La riga del 3° livello è quella della scheda; le soglie
    successive sono le stesse voci a livello più alto e non portano una riga propria."""
    tiers = OATH_SPELLS[oath]
    out = [feature(f"{oath}_spells", CK, ED, OATH_LEVELS[0], title, name,
                   ("Incantesimi di giuramento sempre preparati, due ogni soglia (3°, 5°, 9°, 13°, 17°); non contano nel limite.",
                    "Oath spells are always prepared, two per tier (3rd, 5th, 9th, 13th, 17th); they do not count against the limit."),
                   subclass=oath, granted_spells=tiers[0])]
    for level, spells in zip(OATH_LEVELS[1:], tiers[1:]):
        out.append(feature(f"{oath}_spells_{level}", CK, ED, level, title, name,
                           (f"Incantesimi di giuramento del {level}° livello.", f"Oath spells gained at level {level}."),
                           subclass=oath, granted_spells=spells, no_row=True,
                           covered_by=f"{CK}.{oath}_spells (stessa voce della mappatura) e test_oath_spells_follow_the_level"))
    return out


def _tenets(oath: str, title: str, name: tuple[str, str], summary: tuple[str, str]) -> FeatureSpec:
    return feature(f"tenets_of_{oath}", CK, ED, 3, title, name, summary, subclass=oath, passive=True)


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

FEATURES = (
    feature("hit_points", CK, ED, 1, "Punti Ferita / Hit Points (Paladino 1, pag. 97)", ("Punti Ferita", "Hit Points"),
            ("Dado vita d10; al 1° livello 10 + Costituzione, poi d10 (o 6) + Costituzione.",
             "Hit die d10; level 1 gives 10 + Constitution, then d10 (or 6) + Constitution."), no_row=True,
            covered_by="api/routers/classes.py create_class_for_character e total_base_hp; test_hit_points_use_the_d10_and_follow_constitution"),
    feature("proficiencies", CK, ED, 1, "Competenze / Proficiencies (Paladino 1, pag. 97)", ("Competenze", "Proficiencies"),
            ("Tutte le armature e gli scudi, armi semplici e da guerra, TS Saggezza e Carisma, 2 abilità fra sei.",
             "All armor and shields, simple and martial weapons, Wisdom and Charisma saves, 2 skills from six."),
            no_row=True, covered_by="core/rules/proficiencies.py (class_proficiencies) e la scelta ClassSkillChoice; "
                                    "test_class_proficiencies_first_class_and_multiclass"),
    feature("equipment", CK, ED, 1, "Equipaggiamento / Equipment (Paladino 1, pag. 97)", ("Equipaggiamento", "Equipment"),
            ("Dotazione iniziale: arma da guerra e scudo o due armi, cinque giavellotti o un'arma semplice, pacco, cotta di maglia e simbolo sacro.",
             "Starting gear: a martial weapon and shield or two weapons, five javelins or a simple weapon, a pack, chain mail and a holy symbol."),
            no_row=True, covered_by="lavori-successivi"),
    feature("divine_sense", CK, ED, 1, "Percezione del Divino / Divine Sense (Paladino 1, pag. 97)",
            ("Percezione del Divino", "Divine Sense"),
            ("Azione: fino alla fine del tuo prossimo turno senti celestiali, immondi e non morti entro 18 m non al coperto. 1 + Carisma usi, riposo lungo.",
             "Action: until the end of your next turn you sense celestials, fiends and undead within 60 ft not behind total cover. 1 + Charisma uses, long rest."),
            "action", uses=Uses(table={1: 1}, ability="charisma", minimum=1), restoration="long_rest",
            on_use=OnUse(slot="action", state=StateSpec(
                "divine_sense", ends_on=("new_turn", "turn_end_counted", "rest_short", "rest_long", "manual"),
                data={"skip_new_turns": 1, "range_m": 18, "until": "next_turn_end"}))),
    feature("lay_on_hands", CK, ED, 1, "Imposizione delle Mani / Lay on Hands (Paladino 1, pag. 97)",
            ("Imposizione delle Mani", "Lay on Hands"),
            ("Azione: riserva di 5 PF per livello; tocchi una creatura e spendi PF per curarla, o 5 per curare una malattia o un veleno. Non su costrutti e non morti. Riposo lungo.",
             "Action: a pool of 5 HP per level; touch a creature and spend HP to heal it, or 5 to cure a disease or poison. Not on constructs or undead. Long rest."),
            "action", uses=Uses(per_level=5), restoration="long_rest", on_use=LAY_ON_HANDS_USE),
    feature("fighting_style", CK, ED, 2, "Stile di Combattimento / Fighting Style (Paladino 2, pag. 97)",
            ("Stile di Combattimento", "Fighting Style"),
            ("Al 2° livello scegli uno stile: Armi Possenti, Difesa, Duellare o Protezione. Mai due volte lo stesso.",
             "At 2nd level you choose a style: Great Weapon Fighting, Defense, Dueling or Protection. Never the same one twice."),
            no_row=True, choices=(ChoiceSpec(group="fighting_style", levels={2: 1}, options=style_options(STYLES)),),
            covered_by="ChoiceSpec fighting_style di questa riga e le righe dei quattro stili; test_the_style_is_chosen_at_level_2_among_four"),
    *STYLE_ROWS,
    feature("spellcasting", CK, ED, 2, "Incantesimi / Spellcasting (Paladino 2, pag. 97)", ("Incantesimi", "Spellcasting"),
            ("Carisma; CD 8 + competenza + Carisma. Slot da mezzo incantatore dal 2°, preparati Carisma + metà livello (minimo 1); simbolo sacro come focus.",
             "Charisma; DC 8 + proficiency + Charisma. Half-caster slots from 2nd, prepared Charisma + half level (minimum 1); a holy symbol as focus."),
            no_row=True, covered_by="core/rules/spellcasting.py (known_limits, prepared_limit, slots_for, caster_stats); "
                                    "test_prepared_spells_are_charisma_plus_half_the_level_with_a_minimum_of_one"),
    feature("divine_smite", CK, ED, 2, "Punizione Divina / Divine Smite (Paladino 2, pag. 98)", ("Punizione Divina", "Divine Smite"),
            ("Dopo un colpo con un'arma da mischia spendi uno slot: 2d8 radiosi, +1d8 per livello oltre il 1° (massimo 5d8), +1d8 contro non morti e immondi.",
             "After a melee weapon hit, spend a slot: 2d8 radiant, +1d8 per level above 1st (up to 5d8), +1d8 against undead and fiends."),
            roll_options=(DIVINE_SMITE, DIVINE_SMITE_FIEND)),
    feature("divine_health", CK, ED, 3, "Salute Divina / Divine Health (Paladino 3, pag. 98)", ("Salute Divina", "Divine Health"),
            ("Sei immune alle malattie.", "You are immune to disease."), passive=True),
    feature("sacred_oath", CK, ED, 3, "Giuramento Sacro / Sacred Oath (Paladino 3, pag. 98)", ("Giuramento Sacro", "Sacred Oath"),
            ("Al 3° livello si sceglie Devozione, Antichi o Vendetta: privilegi ai livelli 3, 7, 15 e 20, incantesimi sempre preparati.",
             "At 3rd level you choose Devotion, the Ancients or Vengeance: features at levels 3, 7, 15 and 20, always-prepared spells."),
            no_row=True, covered_by="core/rules/subclasses.py (match_subclass) e il campo sottoclasse della classe"),
    feature("channel_divinity", CK, ED, 3, "Incanalare Divinità / Channel Divinity (Giuramento Sacro, Paladino 3, pag. 98)",
            ("Incanalare Divinità", "Channel Divinity"),
            ("Un uso, torna con un riposo breve o lungo. Ogni effetto del tuo giuramento ne spende uno; la CD è quella degli incantesimi.",
             "One use, back after a short or long rest. Each effect of your oath spends it; the DC is your spell save DC."),
            "action", uses=Uses(table={3: 1}), restoration="short_rest", shared_pool="channel_divinity"),
    feature("ability_score_improvement", CK, ED, 4,
            "Aumento dei Punteggi di Caratteristica / Ability Score Improvement (Paladino 4, pag. 98)",
            ("Aumento dei Punteggi di Caratteristica", "Ability Score Improvement"),
            ("Ai livelli 4, 8, 12, 16 e 19: +2 a un punteggio o +1 a due, oppure un talento; massimo 20.",
             "At levels 4, 8, 12, 16 and 19: +2 to one score or +1 to two, or a feat; maximum 20."), no_row=True,
            covered_by="core/rules/level_choices.py (scelta asi); test_asi_choice_is_pending_at_each_paladin_asi_level"),
    feature("extra_attack", CK, ED, 5, "Attacco Extra / Extra Attack (Paladino 5, pag. 98)", ("Attacco Extra", "Extra Attack"),
            ("Con l'azione Attacco attacchi due volte. Non si somma all'Attacco Extra di altre classi.",
             "You attack twice with the Attack action. Does not stack with other classes' Extra Attack."),
            attacks_per_action=2),
    feature("aura_of_protection", CK, ED, 6, "Aura di Protezione / Aura of Protection (Paladino 6, pag. 98)",
            ("Aura di Protezione", "Aura of Protection"),
            ("Tu e gli alleati entro 3 m (9 m dal 18°) sommate il tuo Carisma (minimo +1) ai TS, finché sei cosciente. Il tuo bonus è già nei tuoi TS.",
             "You and allies within 10 ft (30 ft from 18th) add your Charisma (minimum +1) to saves while you are conscious. Your bonus is already in your saves."),
            modifiers=(Modifier("save", _cha_bonus, when=lambda c: c.roll in SAVE_ROLLS and is_conscious(c.char),
                                source=f"feature:{CK}.aura_of_protection"),),
            aura=AuraSpec("protection", _aura_range, _cha_bonus)),
    feature("aura_of_courage", CK, ED, 10, "Aura di Coraggio / Aura of Courage (Paladino 10, pag. 98)",
            ("Aura di Coraggio", "Aura of Courage"),
            ("Tu e gli alleati entro 3 m (9 m dal 18°) non potete essere spaventati, finché sei cosciente.",
             "You and allies within 10 ft (30 ft from 18th) cannot be frightened while you are conscious."),
            condition_immunities=("frightened",), needs_conscious=True, passive=True, permanent_state=_permanent_note("aura_of_courage")),
    feature("improved_divine_smite", CK, ED, 11, "Punizione Divina Migliorata / Improved Divine Smite (Paladino 11, pag. 98)",
            ("Punizione Divina Migliorata", "Improved Divine Smite"),
            ("Ogni colpo con un'arma da mischia infligge 1d8 radiosi in più, anche insieme a Punizione Divina.",
             "Every melee weapon hit deals an extra 1d8 radiant damage, also with Divine Smite."),
            roll_options=(IMPROVED_SMITE,), passive=True),
    feature("cleansing_touch", CK, ED, 14, "Tocco Purificatore / Cleansing Touch (Paladino 14, pag. 98)",
            ("Tocco Purificatore", "Cleansing Touch"),
            ("Azione: termini un incantesimo su di te o su una creatura consenziente che tocchi. Usi pari al Carisma (minimo 1), riposo lungo.",
             "Action: end one spell on yourself or on a willing creature you touch. Uses equal to Charisma (minimum 1), long rest."),
            "action", uses=Uses(ability="charisma", minimum=1), restoration="long_rest",
            on_use=OnUse(slot="action", removal=ConditionRemoval(allowed=lambda c: tuple(_removable_conditions(c)), ally=False, optional=True))),
    feature("aura_improvements", CK, ED, 18, "Aure Migliorate / Aura Improvements (Paladino 18, pag. 98)",
            ("Aure Migliorate", "Aura Improvements"),
            ("La gittata delle tue aure (Protezione, Coraggio e quella del giuramento) passa da 3 m a 9 m.",
             "The range of your auras (Protection, Courage and your oath's) grows from 10 ft to 30 ft."), passive=True),

    # Giuramento di Devozione
    _tenets("devotion", "Dettami di Devozione / Tenets of Devotion (Giuramento di Devozione, Paladino 3, pag. 99)",
            ("Dettami di Devozione", "Tenets of Devotion"),
            ("Onestà, coraggio, compassione, onore, dovere: precetti di condotta, senza regole di gioco.",
             "Honesty, courage, compassion, honor, duty: conduct tenets, no game rules.")),
    *_oath_spells("devotion", "Incantesimi del Giuramento di Devozione / Oath of Devotion Spells (Giuramento di Devozione, Paladino 3, pag. 99)",
                  ("Incantesimi del Giuramento di Devozione", "Oath of Devotion Spells")),
    feature("sacred_weapon", CK, ED, 3, "Arma Consacrata / Sacred Weapon (Incanalare Divinità, Giuramento di Devozione, Paladino 3, pag. 99)",
            ("Arma Consacrata", "Sacred Weapon"),
            ("Azione, un uso di Incanalare Divinità: per 1 minuto aggiungi il Carisma (minimo +1) ai tiri per colpire con un'arma impugnata, che fa luce e conta come magica.",
             "Action, one Channel Divinity use: for 1 minute add your Charisma (minimum +1) to attack rolls with a wielded weapon, which sheds light and counts as magical."),
            "action", subclass="devotion", modifiers=(Modifier("attack", _sacred_bonus, when=_sacred_applies, source=f"feature:{CK}.sacred_weapon"),
                                                      Modifier("magic_weapon", 1, when=_sacred_applies, source=f"feature:{CK}.sacred_weapon")),
            on_use=OnUse(slot="action", spends=POOL, available=lambda c: bool(_wielded_weapons(c)), state=_sacred_state, choices=(UseChoice(
                "weapon", {"it": "Arma", "en": "Weapon"}, lambda c: [str(i.id) for i in _wielded_weapons(c)],
                lambda k: {"it": k, "en": k}, option_label_ctx=_weapon_label),))),
    feature("turn_the_unholy", CK, ED, 3, "Scacciare i Sacrileghi / Turn the Unholy (Incanalare Divinità, Giuramento di Devozione, Paladino 3, pag. 99)",
            ("Scacciare i Sacrileghi", "Turn the Unholy"),
            ("Azione, un uso di Incanalare Divinità: immondi e non morti entro 9 m fanno un TS Saggezza o sono scacciati per 1 minuto o fino al danno.",
             "Action, one Channel Divinity use: fiends and undead within 30 ft make a Wisdom save or are turned for 1 minute or until damaged."),
            "action", subclass="devotion",
            on_use=OnUse(slot="action", spends=POOL, state=_turn_state("turn_the_unholy"), target_effect=_turn_effect("turn_the_unholy"))),
    feature("aura_of_devotion", CK, ED, 7, "Aura di Devozione / Aura of Devotion (Giuramento di Devozione, Paladino 7, pag. 99)",
            ("Aura di Devozione", "Aura of Devotion"),
            ("Tu e gli alleati entro 3 m (9 m dal 18°) non potete essere affascinati, finché sei cosciente.",
             "You and allies within 10 ft (30 ft from 18th) cannot be charmed while you are conscious."),
            subclass="devotion", condition_immunities=("charmed",), needs_conscious=True, passive=True,
            permanent_state=_permanent_note("aura_of_devotion")),
    feature("purity_of_spirit", CK, ED, 15, "Purezza di Spirito / Purity of Spirit (Giuramento di Devozione, Paladino 15, pag. 99)",
            ("Purezza di Spirito", "Purity of Spirit"),
            ("Sei sempre sotto protezione dal bene e dal male: aberrazioni, celestiali, elementali, folletti, immondi e non morti ti attaccano con svantaggio e non ti affascinano, spaventano o possiedono.",
             "You are always under protection from evil and good: aberrations, celestials, elementals, fey, fiends and undead attack you with disadvantage and cannot charm, frighten or possess you."),
            subclass="devotion", roll_options=(PURITY_ADVANTAGE, PURITY_IMMUNE), passive=True, permanent_state=_purity_state()),
    feature("holy_nimbus", CK, ED, 20, "Nube Sacra / Holy Nimbus (Giuramento di Devozione, Paladino 20, pag. 99)",
            ("Nube Sacra", "Holy Nimbus"),
            ("Azione: per 1 minuto luce intensa entro 9 m; i nemici che iniziano il turno nella luce subiscono 10 radiosi; vantaggio ai TS contro incantesimi di immondi e non morti. Riposo lungo.",
             "Action: for 1 minute bright light within 30 ft; enemies starting their turn in it take 10 radiant; advantage on saves against spells from fiends and undead. Long rest."),
            "action", subclass="devotion", uses=Uses(table={20: 1}), restoration="long_rest", roll_options=(HOLY_NIMBUS_SAVE,),
            on_use=OnUse(slot="action", state=_nimbus_state)),

    # Giuramento degli Antichi
    _tenets("ancients", "Dettami degli Antichi / Tenets of the Ancients (Giuramento degli Antichi, Paladino 3, pag. 100)",
            ("Dettami degli Antichi", "Tenets of the Ancients"),
            ("Alimenta, proteggi, preserva la luce e sii la luce: precetti di condotta, senza regole di gioco.",
             "Kindle, shelter, preserve the light and be the light: conduct tenets, no game rules.")),
    *_oath_spells("ancients", "Incantesimi del Giuramento degli Antichi / Oath of the Ancients Spells (Giuramento degli Antichi, Paladino 3, pag. 100)",
                  ("Incantesimi del Giuramento degli Antichi", "Oath of the Ancients Spells")),
    feature("natures_wrath", CK, ED, 3, "Collera della Natura / Nature's Wrath (Incanalare Divinità, Giuramento degli Antichi, Paladino 3, pag. 100)",
            ("Collera della Natura", "Nature's Wrath"),
            ("Azione, un uso di Incanalare Divinità: una creatura entro 3 m fa un TS Forza o Destrezza (a sua scelta) o è trattenuta, e ripete il TS a fine turno.",
             "Action, one Channel Divinity use: a creature within 10 ft makes a Strength or Dexterity save (its choice) or is restrained, repeating the save at the end of its turns."),
            "action", subclass="ancients",
            on_use=OnUse(slot="action", spends=POOL, state=_wrath_state, target_effect=_wrath_effect)),
    feature("turn_the_faithless", CK, ED, 3, "Scacciare gli Infedeli / Turn the Faithless (Incanalare Divinità, Giuramento degli Antichi, Paladino 3, pag. 100)",
            ("Scacciare gli Infedeli", "Turn the Faithless"),
            ("Azione, un uso di Incanalare Divinità: folletti e immondi entro 9 m (non i non morti) fanno un TS Saggezza o sono scacciati per 1 minuto o fino al danno; la loro vera forma si rivela.",
             "Action, one Channel Divinity use: fey and fiends within 30 ft (not undead) make a Wisdom save or are turned for 1 minute or until damaged; their true form is revealed."),
            "action", subclass="ancients",
            on_use=OnUse(slot="action", spends=POOL, state=_turn_state("turn_the_faithless"), target_effect=_turn_effect("turn_the_faithless"))),
    feature("aura_of_warding", CK, ED, 7, "Aura di Interdizione / Aura of Warding (Giuramento degli Antichi, Paladino 7, pag. 100)",
            ("Aura di Interdizione", "Aura of Warding"),
            ("Tu e gli alleati entro 3 m (9 m dal 18°) avete resistenza ai danni degli incantesimi. Il tuo è una conferma sul danno subito.",
             "You and allies within 10 ft (30 ft from 18th) have resistance to spell damage. Yours is a confirmation on the damage you take."),
            subclass="ancients", roll_options=(WARDING,), passive=True,
            aura=AuraSpec("warding", _aura_range, needs_conscious=False)),
    feature("undying_sentinel", CK, ED, 15, "Sentinella Imperitura / Undying Sentinel (Giuramento degli Antichi, Paladino 15, pag. 100)",
            ("Sentinella Imperitura", "Undying Sentinel"),
            ("A 0 PF, se non sei morto sul colpo, resti a 1 PF. Un uso, riposo lungo. Non invecchi.",
             "When reduced to 0 HP and not killed outright, you drop to 1 HP instead. One use, long rest. You do not age."),
            "special", subclass="ancients", uses=Uses(table={15: 1}), restoration="long_rest", roll_options=(SENTINEL,)),
    feature("elder_champion", CK, ED, 20, "Campione degli Antichi / Elder Champion (Giuramento degli Antichi, Paladino 20, pag. 100)",
            ("Campione degli Antichi", "Elder Champion"),
            ("Azione, 1 minuto: +10 PF a inizio turno; incantesimi da paladino da 1 azione come azione bonus; nemici entro 3 m con svantaggio ai TS contro i tuoi incantesimi da paladino e Incanalare Divinità.",
             "Action, 1 minute: regain 10 HP at turn start; 1-action paladin spells as a bonus action; enemies within 10 ft have disadvantage on saves against your paladin spells and Channel Divinity. Long rest."),
            "action", subclass="ancients", uses=Uses(table={20: 1}), restoration="long_rest", turn_start_heal=_champion_heal,
            on_use=OnUse(slot="action", state=_champion_state)),

    # Giuramento di Vendetta
    _tenets("vengeance", "Dettami di Vendetta / Tenets of Vengeance (Giuramento di Vendetta, Paladino 3, pag. 101)",
            ("Dettami di Vendetta", "Tenets of Vengeance"),
            ("Combatti il male peggiore, nessuna pietà, costi quel che costi, risarcimento: precetti di condotta, senza regole di gioco.",
             "Fight the greater evil, no mercy, by any means, restitution: conduct tenets, no game rules.")),
    *_oath_spells("vengeance", "Incantesimi del Giuramento di Vendetta / Oath of Vengeance Spells (Giuramento di Vendetta, Paladino 3, pag. 101)",
                  ("Incantesimi del Giuramento di Vendetta", "Oath of Vengeance Spells")),
    feature("abjure_enemy", CK, ED, 3, "Abiurare Nemico / Abjure Enemy (Incanalare Divinità, Giuramento di Vendetta, Paladino 3, pag. 101)",
            ("Abiurare Nemico", "Abjure Enemy"),
            ("Azione, un uso di Incanalare Divinità: creatura entro 18 m, TS Saggezza (svantaggio se immonda o non morta) o spaventata, velocità 0, per 1 minuto o fino al danno; se supera, velocità dimezzata.",
             "Action, one Channel Divinity use: a creature within 60 ft makes a Wisdom save (disadvantage if fiend or undead) or is frightened, speed 0, for 1 minute or until damaged; on a success, speed halved."),
            "action", subclass="vengeance",
            on_use=OnUse(slot="action", spends=POOL, state=_abjure_state, target_effect=_abjure_effect)),
    feature("vow_of_enmity", CK, ED, 3, "Giuramento di Inimicizia / Vow of Enmity (Incanalare Divinità, Giuramento di Vendetta, Paladino 3, pag. 101)",
            ("Giuramento di Inimicizia", "Vow of Enmity"),
            ("Azione bonus, un uso di Incanalare Divinità: per 1 minuto hai vantaggio ai tiri per colpire contro una creatura entro 3 m, finché non scende a 0 PF o cade priva di sensi.",
             "Bonus action, one Channel Divinity use: for 1 minute you have advantage on attack rolls against a creature within 10 ft, until it drops to 0 HP or falls unconscious."),
            "bonus_action", subclass="vengeance", roll_options=(VOW_ATTACK,),
            on_use=OnUse(slot="bonus", spends=POOL, state=_vow_state)),
    feature("relentless_avenger", CK, ED, 7, "Vendicatore Implacabile / Relentless Avenger (Giuramento di Vendetta, Paladino 7, pag. 101)",
            ("Vendicatore Implacabile", "Relentless Avenger"),
            ("Dopo un colpo con un attacco di opportunità ti muovi fino a metà della velocità, senza provocare, nella stessa reazione.",
             "After hitting with an opportunity attack you move up to half your speed, without provoking, as part of the same reaction."),
            subclass="vengeance", roll_options=(OPPORTUNITY_ATTACK, RELENTLESS_AVENGER), passive=True),
    feature("soul_of_vengeance", CK, ED, 15, "Anima di Vendetta / Soul of Vengeance (Giuramento di Vendetta, Paladino 15, pag. 101)",
            ("Anima di Vendetta", "Soul of Vengeance"),
            ("Reazione: quando la creatura sotto il tuo Giuramento di Inimicizia attacca, la colpisci con un attacco in mischia se è a portata.",
             "Reaction: when the creature under your Vow of Enmity attacks, you make a melee attack against it if it is within reach."),
            "reaction", subclass="vengeance", roll_options=(SOUL_OF_VENGEANCE,)),
    feature("avenging_angel", CK, ED, 20, "Angelo Vendicatore / Avenging Angel (Giuramento di Vendetta, Paladino 20, pag. 101)",
            ("Angelo Vendicatore", "Avenging Angel"),
            ("Azione, 1 ora: ali (volo 18 m), aura di 9 m: il nemico che vi entra o vi inizia il turno la prima volta fa un TS Saggezza o è spaventato 1 minuto o fino al danno; attacchi contro di lui con vantaggio.",
             "Action, 1 hour: wings (fly 60 ft), 30 ft aura: first time an enemy enters it or starts its turn there, it saves Wisdom or is frightened 1 minute or until damaged; attacks against it have advantage."),
            "action", subclass="vengeance", uses=Uses(table={20: 1}), restoration="long_rest",
            modifiers=(Modifier("fly_speed_value", 60, when=lambda c: state_on(c, "avenging_angel"), source=f"feature:{CK}.avenging_angel"),),
            on_use=OnUse(slot="action", state=_angel_state, target_effect=_angel_effect)),

    feature("multiclassing", CK, ED, 1, "Multiclasse: Paladino / Multiclassing: Paladin (Regole opzionali, pag. 163)",
            ("Multiclasse: Paladino", "Multiclassing: Paladin"),
            ("Requisito Forza 13 e Carisma 13. Da multiclasse: armature leggere e medie, scudi, armi semplici e da guerra; slot a metà livelli.",
             "Requires Strength 13 and Charisma 13. As a multiclass: light and medium armor, shields, simple and martial weapons; half-level slots."),
            no_row=True, covered_by="core/rules/proficiencies.py (as_multiclass) e webapp/src/data/multiclassPrereqs.ts (D2)"),
)

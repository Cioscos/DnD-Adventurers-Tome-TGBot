"""Talenti 2014 (Manuale del Giocatore 2014, pagg. 165-170) nel motore: quello che l'app sa modellare agisce da solo,
il resto (distanze, spinte, attacchi bonus, attacchi di opportunità) resta nel riassunto per il GM (D1).

Nome e riassunto vengono dalla scheda di selezione (``core/data/feats.py``). La riga del talento è un ``FeatSource``:
``ctx.class_row.options["ability"]`` è la caratteristica del +1 scelta."""
from __future__ import annotations

from typing import Any

from core.rules.catalog._common import heavy_armor, state_on
from core.rules.catalog.feats import D20_TESTS, _register, feat
from core.rules.catalog.feats_2024 import _PHYSICAL, _both, _finesse_in_hand, _medium_armor_dex, _pb
from core.rules.types import Cost, FeatureSpec, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, Uses
from core.utils.session_view import armor_category

_DUELIST = "feat.defensive_duelist"


def _f14(key: str, **kw: Any) -> FeatureSpec:
    """Voce 2014 con nome e riassunto della scheda di selezione."""
    from core.data.feats import FEATS  # import locale: i dati dei talenti non dipendono dal motore
    data = FEATS[key]
    return feat(key, "2014", data.name["it"], data.name["en"], data.summary["it"], data.summary["en"], **kw)


def _lucky_reroll(key: str, rolls: tuple[str, ...]) -> RollOptionSpec:
    return RollOptionSpec(
        key=key, phase="after_roll", after="reroll", rolls=rolls, cost=Cost(feature_key=key),
        label={"it": "Fortunato: spendi un punto e ritira il d20 (scegli tu quale risultato tenere)",
               "en": "Lucky: spend a point and reroll the d20 (you choose which result to keep)"})


_register(
    _f14("alert", modifiers=(Modifier("initiative", 5),)),
    _f14("tough", modifiers=(Modifier("hp_max", lambda ctx: 2 * ctx.class_level),)),
    _f14("mobile", modifiers=(Modifier("speed", 10),)),
    _f14("observant", modifiers=(Modifier("passive", 5, when=lambda ctx: ctx.skill in ("perception", "investigation")),)),
    _f14("war_caster", modifiers=(Modifier("advantage", 0, when=lambda ctx: ctx.roll == "concentration"),)),
    _f14("lucky", passive=False, uses=Uses(table={1: 3}), restoration="long_rest",
         roll_options=(_lucky_reroll("feat.lucky", D20_TESTS),)),
    *(_f14(k) for k in (
        "skilled", "elemental_adept", "martial_adept", "spell_sniper", "ritual_caster", "magic_initiate", "linguist",
        "weapon_master", "great_weapon_master", "sharpshooter",  # scelte e attacco potente: Task 3-4
        # solo testo (D1): distanze, attacchi bonus o di opportunità, cure ad altri
        "skulker", "mounted_combatant", "crossbow_expert", "healer", "polearm_master", "keen_mind", "resilient",
        "sentinel")),
)


def _melee_weapon(item: Any) -> bool:
    from core.game.item_bonuses import item_meta  # import locale come negli altri moduli del catalogo
    return item.item_type == "weapon" and item_meta(item).get("weapon_type", "melee") == "melee"


def _two_melee_weapons(ctx: RuleContext) -> bool:
    slots = {str(getattr(i.equipment_slot, "value", i.equipment_slot)) for i in ctx.char.items or []
             if i.is_equipped and _melee_weapon(i)}
    return {"main_hand", "off_hand"} <= slots


def _shield(char: Any) -> Any:
    return next((i for i in char.items or [] if i.is_equipped and i.item_type == "shield"), None)


def _shield_ac(ctx: RuleContext, _inputs: dict) -> int:
    from core.game.item_bonuses import item_meta
    item = _shield(ctx.char)
    return int(ctx.char.shield_armor_class or (item_meta(item).get("ac_value") if item else 0) or 0)


def _leader_hp(ctx: RuleContext) -> int:
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    return ctx.class_level + effective_ability_mod(ctx.char, "charisma")


def _advantage(key: str, rolls: tuple[str, ...], it: str, en: str, available=lambda _c: True) -> RollOptionSpec:
    return RollOptionSpec(key=key, phase="before", rolls=rolls, mode="advantage", available=available, label=_both(it, en))


_register(
    _f14("actor", roll_options=(_advantage("feat.actor", ("skill",), "Attore: vantaggio spacciandoti per un'altra persona",
                                           "Actor: advantage while passing yourself off as someone else",
                                           lambda c: c.skill in ("deception", "performance")),)),
    _f14("athlete", modifiers=(Modifier("climb_speed", 0),)),
    _f14("charger", roll_options=(RollOptionSpec(
        key="feat.charger", phase="after_hit", rolls=("attack",), once_per_turn=True, bonus=lambda _c, _i: 5,
        available=lambda c: c.attack_mode == "melee",
        label=_both("Carica: hai usato Scatto e ti sei mosso di almeno 3 m in linea retta, +5 al danno",
                    "Charger: you used Dash and moved at least 10 ft in a straight line, +5 damage")),)),
    _f14("dual_wielder", modifiers=(Modifier("ac", 1, when=lambda c: c.roll == "ac" and _two_melee_weapons(c)),)),
    _f14("dungeon_delver", roll_options=(
        _advantage("feat.dungeon_delver", ("skill",), "Esperto di Dungeon: cerchi una porta segreta, vantaggio",
                   "Dungeon Delver: you are looking for a secret door, advantage",
                   lambda c: c.skill in ("perception", "investigation")),
        _advantage("feat.dungeon_delver_traps", ("save",), "Esperto di Dungeon: TS contro una trappola, vantaggio",
                   "Dungeon Delver: save against a trap, advantage"),
        RollOptionSpec(key="feat.dungeon_delver_trap_damage", phase="damage_in", rolls=("damage_taken",), multiplier=0.5,
                       label=_both("Esperto di Dungeon: il danno viene da una trappola, resistenza",
                                   "Dungeon Delver: the damage comes from a trap, resistance")))),
    _f14("grappler", roll_options=(_advantage("feat.grappler", ("attack",), "Lottatore: vantaggio contro la creatura che stai lottando",
                                              "Grappler: advantage against the creature you are grappling"),)),
    _f14("mage_slayer", roll_options=(_advantage("feat.mage_slayer", ("save",),
                                                 "Sterminatore di Maghi: incantesimo di una creatura entro 1,5 m, vantaggio",
                                                 "Mage Slayer: spell from a creature within 5 ft, advantage"),)),
    _f14("medium_armor_master", modifiers=(Modifier("ac", 1, when=_medium_armor_dex),)),
    _f14("heavy_armor_master", roll_options=(RollOptionSpec(
        key="feat.heavy_armor_master", phase="damage_in", rolls=("damage_taken",), bonus=lambda _c, _i: 3,
        available=lambda c: heavy_armor(c.char) and c.damage_type in _PHYSICAL,
        label=_both("Maestro delle Armature Pesanti: il danno viene da un'arma non magica, -3",
                    "Heavy Armor Master: the damage comes from a nonmagical weapon, -3")),)),
    _f14("shield_master", roll_options=(
        RollOptionSpec(key="feat.shield_master", phase="before", rolls=("save",), bonus=_shield_ac,
                       available=lambda c: c.ability == "dexterity" and _shield(c.char) is not None,
                       label=_both("Maestro degli Scudi: l'effetto bersaglia solo te, sommi la CA dello scudo",
                                   "Shield Master: the effect targets only you, add your shield's AC")),
        RollOptionSpec(key="feat.shield_master_evasion", phase="damage_in", rolls=("damage_taken",), multiplier=0,
                       available=lambda c: _shield(c.char) is not None,
                       label=_both("Maestro degli Scudi: hai superato il TS di Destrezza contro un effetto a metà danni",
                                   "Shield Master: you passed the Dexterity save against a half-damage effect")))),
    _f14("defensive_duelist", passive=False, action_type="reaction",
         on_use=OnUse(slot="reaction", available=_finesse_in_hand,
                      state=StateSpec(_DUELIST, rounds=1, ends_on=("new_turn", "manual"))),
         modifiers=(Modifier("ac", _pb, when=lambda c: c.roll == "ac" and state_on(c, _DUELIST)),)),
    _f14("durable"),  # minimo della cura dei Dadi Vita: ``hit_dice/spend`` (api/routers/hp.py)
    _f14("tavern_brawler", unarmed_die="1d4", proficiency_grants={"weapons": ("improvised",)}),
    _f14("savage_attacker", weapon_damage_twice="melee"),
    _f14("lightly_armored", proficiency_grants={"armor": ("light",)}),
    _f14("moderately_armored", proficiency_grants={"armor": ("medium", "shields")}),
    _f14("heavily_armored", proficiency_grants={"armor": ("heavy",)}),
    _f14("inspiring_leader", rest_temp_hp=_leader_hp, rest_temp_hp_ally=lambda c: (5, _leader_hp(c))),
)


def medium_armor_master(char: Any) -> bool:
    """Maestro delle Armature Medie 2014 con armatura media: niente svantaggio di furtività dall'armatura."""
    from core.rules.catalog import active_features  # import locale: il catalogo importa questo modulo
    return armor_category(char) == "medium" and any(s.key == "feat.medium_armor_master" for s, _r in active_features(char))


def has_feat(char: Any, key: str) -> bool:
    from core.rules.catalog import active_features
    return any(s.key == key for s, _r in active_features(char))

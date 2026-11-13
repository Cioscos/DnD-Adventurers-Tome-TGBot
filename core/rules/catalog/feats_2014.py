"""Talenti 2014 (Manuale del Giocatore 2014, pagg. 165-170) nel motore: quello che l'app sa modellare agisce da solo,
il resto (distanze, spinte, attacchi bonus, attacchi di opportunità) resta nel riassunto per il GM (D1).

Nome e riassunto vengono dalla scheda di selezione (``core/data/feats.py``). La riga del talento è un ``FeatSource``:
``ctx.class_row.options["ability"]`` è la caratteristica del +1 scelta."""
from __future__ import annotations

from typing import Any

from core.rules.catalog.feats import D20_TESTS, _register, feat
from core.rules.types import Cost, FeatureSpec, Modifier, RollOptionSpec, Uses


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
    # solo testo per ora: gli effetti arrivano con le voci qui sotto (PR 3, Task 2-4)
    *(_f14(k) for k in (
        "skilled", "elemental_adept", "martial_adept", "savage_attacker", "skulker", "athlete", "actor", "charger",
        "spell_sniper", "dual_wielder", "mounted_combatant", "inspiring_leader", "lightly_armored", "moderately_armored",
        "heavily_armored", "defensive_duelist", "crossbow_expert", "dungeon_delver", "healer", "ritual_caster",
        "magic_initiate", "linguist", "grappler", "tavern_brawler", "weapon_master", "great_weapon_master",
        "shield_master", "medium_armor_master", "heavy_armor_master", "polearm_master", "keen_mind", "resilient",
        "sentinel", "mage_slayer", "durable", "sharpshooter")),
)

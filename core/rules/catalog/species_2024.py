"""Tratti delle specie 2024 nel motore delle regole di classe.

Come i talenti (``feats.py``): ``active_features`` restituisce ogni tratto con un ``SpeciesSource`` al posto della riga
di classe. La specie è ``Character.species_key`` (``2024_dwarf``); le scelte (lignaggio, ...) sono ``species_options``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.data.species_2024 import DRAGON_ANCESTRY, SPECIES_2024
from core.rules.catalog._common import state_on
from core.rules.catalog.feats import _abilities
from core.rules.catalog.y2014.paladin import _drops_to_zero
from core.rules.edition import character_edition
from core.rules.types import Cost, FeatureSpec, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, Uses


@dataclass(frozen=True)
class SpeciesSource:
    """Al posto della riga di classe per i tratti di specie."""
    ability: Any
    level: int
    options: dict

    @property
    def id(self) -> None:
        return None

    @property
    def class_name(self) -> str:
        return "species"

    @property
    def subclass_key(self) -> None:
        return None


def trait(species: str, key: str, level: int, title: str, name: tuple[str, str], summary: tuple[str, str],
          **kw: Any) -> FeatureSpec:
    """Tratto di specie: ``species`` è la chiave senza anno (``dwarf``), la spec ha chiave ``species.2024_<species>_<key>``."""
    kw.setdefault("passive", kw.get("on_use") is None)
    return FeatureSpec(key=f"species.2024_{species}_{key}", class_key="species", edition="2024", level=level,
                       source_title=title, name={"it": name[0], "en": name[1]},
                       summary={"it": summary[0], "en": summary[1]}, action_type=kw.pop("action_type", None), **kw)


def data_trait(species: str, key: str, level: int, page: int, **kw: Any) -> FeatureSpec:
    """Come ``trait`` ma nome e riassunto vengono da ``core/data/species_2024.py`` (come ``_f24`` per i talenti)."""
    data = SPECIES_2024[f"2024_{species}"]
    _key, name, summary = next(t for t in data.traits if t[0] == key)
    return trait(species, key, level, f"{name['it']} / {name['en']} (Specie, pag. {page})",
                 (name["it"], name["en"]), (summary["it"], summary["en"]), **kw)


def _both(it: str, en: str) -> dict[str, str]:
    return {"it": it, "en": en}


def _con_mod(ctx: RuleContext) -> int:
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    return effective_ability_mod(ctx.char, "constitution")


def _opt(ctx: RuleContext, group: str) -> str | None:
    return (getattr(ctx.class_row, "options", None) or {}).get(group)


def _pb(ctx: RuleContext, _rolled: int = 0) -> int:
    return ctx.char.proficiency_bonus


def _advantage(key: str, rolls: tuple[str, ...], it: str, en: str) -> RollOptionSpec:
    """Vantaggio dichiarato dal giocatore (modello Volontà d'Acciaio): l'app non sa contro cosa è il tiro."""
    return RollOptionSpec(key=key, phase="before", rolls=rolls, mode="advantage", label=_both(it, en))


def _darkvision(species: str, feet: int, page: int) -> FeatureSpec:
    return data_trait(species, "darkvision", 1, page, modifiers=(Modifier("sense:darkvision", feet),))


_PB_LONG: dict[str, Any] = dict(uses=Uses(proficiency=True), restoration="long_rest")
_TEN_MINUTES = 100  # round


# --- Dragonide (pag. 187) ---------------------------------------------------------------------------------------------
def _breath_dice(ctx: RuleContext) -> str:
    return f"{1 + sum(ctx.class_level >= lv for lv in (5, 11, 17))}d10"


def _breath_message(ctx: RuleContext, _params: dict) -> dict[str, str]:
    kind = DRAGON_ANCESTRY.get(_opt(ctx, "ancestry") or "", ("", "", "?"))[2]
    dc = 8 + _con_mod(ctx) + ctx.char.proficiency_bonus
    return _both(f"Soffio: cono 4,5 m o linea 9 m, TS Destrezza CD {dc}, danni da {kind}, metà se il TS riesce. Tira tu e applica il danno: lo decide il GM.",
                 f"Breath: 15 ft cone or 30 ft line, Dexterity save DC {dc}, {kind} damage, half on a success. Roll it and apply it: the GM decides.")


DRAGONBORN = (
    data_trait("dragonborn", "breath_weapon", 1, 187, passive=False, action_type="action", dc_ability="constitution", **_PB_LONG,
               on_use=OnUse(slot="action", forgoes_attack=True, rolls=_breath_dice, message=_breath_message)),
    data_trait("dragonborn", "damage_resistance", 1, 187, modifiers=tuple(
        Modifier(f"resistance:{t}", 0, when=lambda c, t=t: DRAGON_ANCESTRY.get(_opt(c, "ancestry") or "", ("", "", ""))[2] == t)
        for t in sorted({v[2] for v in DRAGON_ANCESTRY.values()}))),
    _darkvision("dragonborn", 60, 187),
    data_trait("dragonborn", "draconic_flight", 5, 187, passive=False, action_type="bonus_action", uses=Uses(table={1: 1}), restoration="long_rest",
               on_use=OnUse(slot="bonus", state=StateSpec("draconic_flight", rounds=_TEN_MINUTES, ends_on=("manual", "incapacitated"))),
               modifiers=(Modifier("fly_speed", 1, when=lambda c: state_on(c, "draconic_flight")),)),
)

# --- Nano (pag. 188) --------------------------------------------------------------------------------------------------
DWARF = (
    _darkvision("dwarf", 120, 188),
    data_trait("dwarf", "dwarven_resilience", 1, 188, modifiers=(Modifier("resistance:poison", 0),), roll_options=(_advantage(
        "species.2024_dwarf_dwarven_resilience", ("save",), "Resilienza nanica: il tiro salvezza è contro l'essere avvelenato? Vantaggio",
        "Dwarven Resilience: is the saving throw against being poisoned? Advantage"),)),
    data_trait("dwarf", "dwarven_toughness", 1, 188, modifiers=(Modifier("hp_max", lambda c: c.class_level),)),
    data_trait("dwarf", "stonecunning", 1, 188, passive=False, action_type="bonus_action", **_PB_LONG,
               on_use=OnUse(slot="bonus", state=StateSpec("stonecunning", rounds=_TEN_MINUTES, ends_on=("manual",))),
               modifiers=(Modifier("sense:tremorsense", 60, when=lambda c: state_on(c, "stonecunning")),)),
)

# --- Goliath (pag. 192) -----------------------------------------------------------------------------------------------
_G = "species.2024_goliath_giant_ancestry_"


def _giant(giant: str, **kw: Any) -> FeatureSpec:
    return data_trait("goliath", f"giant_ancestry_{giant}", 1, 192, option_group="giant", option_key=giant, passive=False, **_PB_LONG, **kw)


def _on_hit(giant: str, dice: str, damage: str, it: str, en: str) -> FeatureSpec:
    return _giant(giant, roll_options=(RollOptionSpec(
        key=_G + giant, phase="after_hit", rolls=("attack",), extra_dice=lambda _c, _i: dice, extra_damage_type=damage,
        cost=Cost(feature_key=_G + giant), label=_both(it, en)),))


def _stone_reduction() -> RollOptionSpec:
    return RollOptionSpec(
        key=_G + "stone", phase="damage_in", rolls=("damage_taken",), slot="reaction", extra_dice=lambda _c, _i: "1d12",
        bonus=lambda c, _i: _con_mod(c), cost=Cost(feature_key=_G + "stone"),
        label=_both("Resistenza della pietra: reazione, riduci il danno subito di 1d12 + Cos", "Stone's Endurance: reaction, reduce the damage you took by 1d12 + Con"))


GOLIATH = (
    data_trait("goliath", "speed", 1, 192, modifiers=(Modifier("speed", 5),)),
    _giant("cloud", action_type="bonus_action", on_use=OnUse(slot="bonus")),
    _on_hit("fire", "1d10", "fire", "Ardore del fuoco: +1d10 danni da fuoco al colpo", "Fire's Burn: +1d10 fire damage on the hit"),
    _on_hit("frost", "1d6", "cold", "Gelo del ghiaccio: +1d6 danni da freddo al colpo (velocità del bersaglio -3 m, a mano)",
            "Frost's Chill: +1d6 cold damage on the hit (target's Speed -10 ft, by hand)"),
    _giant("hill", on_use=OnUse()),  # la caduta Prona è un effetto sul bersaglio: testo per il GM
    _giant("stone", action_type="reaction", roll_options=(_stone_reduction(),)),
    _giant("storm", action_type="reaction", on_use=OnUse(slot="reaction", rolls="1d8")),
    data_trait("goliath", "large_form", 5, 192, passive=False, action_type="bonus_action", uses=Uses(table={1: 1}), restoration="long_rest",
               on_use=OnUse(slot="bonus", state=StateSpec("large_form", rounds=_TEN_MINUTES, ends_on=("manual",))),
               modifiers=(Modifier("speed", 10, when=lambda c: state_on(c, "large_form")),
                          Modifier("advantage", 1, when=lambda c: state_on(c, "large_form") and c.roll in ("skill", "ability") and c.ability == "strength",
                                   source="feature:species.2024_goliath_large_form"))),
    data_trait("goliath", "powerful_build", 1, 192, modifiers=(Modifier("carry_double", 1),), roll_options=(_advantage(
        "species.2024_goliath_powerful_build", ("save",), "Corporatura possente: il tiro salvezza serve a terminare l'essere afferrato? Vantaggio",
        "Powerful Build: is the saving throw to end being grappled? Advantage"),)),
)

# --- Orco (pag. 195) --------------------------------------------------------------------------------------------------
_RELENTLESS = "species.2024_orc_relentless_endurance"
ORC = (
    data_trait("orc", "adrenaline_rush", 1, 195, passive=False, action_type="bonus_action", uses=Uses(proficiency=True), restoration="short_rest",
               on_use=OnUse(slot="bonus", temp_hp=_pb)),  # lo Scatto è testo: l'app non muove
    _darkvision("orc", 120, 195),
    # Un uso della riga (riposo lungo) al posto dello stato «pronto»: la riga nasce con la specie, non serve avviare niente
    data_trait("orc", "relentless_endurance", 1, 195, uses=Uses(table={1: 1}), restoration="long_rest", roll_options=(RollOptionSpec(
        key=_RELENTLESS, phase="damage_in", rolls=("damage_taken",), holds_at_one=True, cost=Cost(feature_key=_RELENTLESS), available=_drops_to_zero,
        label=_both("Resistenza implacabile: se il danno ti porta a 0 PF senza ucciderti sul colpo, resti a 1 PF (un uso, riposo lungo)",
                    "Relentless Endurance: if the damage would drop you to 0 HP without killing you outright, you stay at 1 HP (one use, long rest)")),)),
)

# Riempito dai moduli delle singole specie: chiave ``2024_dwarf`` -> tratti
SPECIES_TRAITS: dict[str, tuple[FeatureSpec, ...]] = {
    "2024_dragonborn": DRAGONBORN, "2024_dwarf": DWARF, "2024_goliath": GOLIATH, "2024_orc": ORC,
}


def owned_species(char: Any) -> list[tuple[FeatureSpec, SpeciesSource]]:
    if character_edition(char) != "2024":
        return []
    traits = SPECIES_TRAITS.get(getattr(char, "species_key", None) or "")
    if not traits:
        return []
    level = max(1, sum(getattr(c, "level", 0) or 0 for c in getattr(char, "classes", None) or []))
    chosen = getattr(char, "species_options", None) or {}
    rows = {a.feature_key: a for a in _abilities(char)}
    return [(s, SpeciesSource(rows.get(s.key), level, chosen)) for s in traits
            if s.level <= level and (s.option_group is None or s.option_key == chosen.get(s.option_group))]

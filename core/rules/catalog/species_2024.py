"""Tratti delle specie 2024 nel motore delle regole di classe.

Come i talenti (``feats.py``): ``active_features`` restituisce ogni tratto con un ``SpeciesSource`` al posto della riga
di classe. La specie è ``Character.species_key`` (``2024_dwarf``); le scelte (lignaggio, ...) sono ``species_options``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.data.species_2024 import DRAGON_ANCESTRY, SPECIES_2024
from core.rules.catalog._common import state_on
from core.rules.catalog.feats import D20_TESTS, _abilities
from core.rules.catalog.granted_spells import GRANTED_SPELLS
from core.rules.catalog.y2014.paladin import _drops_to_zero
from core.rules.edition import character_edition
from core.rules.types import Cost, FeatureSpec, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, UseChoice, Uses


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


def _spell_attack(ctx: RuleContext) -> bool:
    return (getattr(ctx.spell, "attack_save", None) or "").strip().upper() == "ATK"


def _on_hit(giant: str, dice: str, damage: str, it: str, en: str) -> FeatureSpec:
    # Anche l'attacco con incantesimo è un attacco: la variante «_spell» vale sul suo danno (come la Rivelazione celeste)
    def option(suffix: str, phase: str, rolls: tuple[str, ...], **kw: Any) -> RollOptionSpec:
        return RollOptionSpec(key=_G + giant + suffix, phase=phase, rolls=rolls, extra_dice=lambda _c, _i: dice, extra_damage_type=damage,
                              cost=Cost(feature_key=_G + giant), label=_both(it, en), **kw)
    return _giant(giant, roll_options=(option("", "after_hit", ("attack",)),
                                       option("_spell", "before", ("spell_damage",), available=_spell_attack)))


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

# --- Incantesimi di lignaggio (Elfo, Gnomo, Tiefling) -----------------------------------------------------------------
def _lineage(species: str, group: str, option: str, page: int, cantrips: tuple[str, ...], **kw: Any) -> FeatureSpec:
    """Beneficio di livello 1 del lignaggio: i trucchetti, sempre preparati, con la caratteristica scelta."""
    return data_trait(species, f"{group}_{option}", 1, page, option_group=group,
                      option_key=option, granted_spells=cantrips, **kw)


def _lineage_spell(species: str, group: str, option: str, level: int, page: int, spell: str) -> FeatureSpec:
    """Incantesimo di lignaggio del livello 3 o 5: sempre preparato, una volta senza slot per riposo lungo (o con uno slot)."""
    name = GRANTED_SPELLS[spell].name
    return trait(species, f"{group}_{option}_{level}", level, f"{name['it']} / {name['en']} (Specie, pag. {page})",
                 (name["it"], name["en"]),
                 ("Sempre preparato; una volta senza slot per riposo lungo, o con uno slot.",
                  "Always prepared; once without a slot per long rest, or with a slot."),
                 option_group=group, option_key=option, passive=False, granted_spells=(spell,), free_spell=spell,
                 uses=Uses(table={1: 1}), restoration="long_rest")


def _lineage_rows(species: str, group: str, page: int, rows: tuple[tuple[str, tuple[str, ...], str, str], ...],
            **extra: dict[str, Any]) -> tuple[FeatureSpec, ...]:
    """``rows``: (opzione, trucchetti, incantesimo del 3, incantesimo del 5); ``extra[opzione]``: altri campi del livello 1."""
    return tuple(spec for option, cantrips, third, fifth in rows for spec in (
        _lineage(species, group, option, page, cantrips, **extra.get(option, {})),
        _lineage_spell(species, group, option, 3, page, third), _lineage_spell(species, group, option, 5, page, fifth)))


# --- Aasimar (pag. 186) -----------------------------------------------------------------------------------------------
_REVELATION = "celestial_revelation"
_FORMS = {"wings": _both("Ali celesti", "Heavenly Wings"), "radiance": _both("Radiosità interiore", "Inner Radiance"),
          "shroud": _both("Manto necrotico", "Necrotic Shroud")}
_HEAL_MODES = {"self": _both("Curi te stesso", "Heal yourself"), "other": _both("Curi un'altra creatura", "Heal another creature")}


def _form(ctx: RuleContext) -> str | None:
    state = next((s for s in ctx.char.active_states or [] if s.get("key") == _REVELATION), None)
    return (state.get("data") or {}).get("form") if state else None


def _revelation_message(ctx: RuleContext, params: dict) -> dict[str, str]:
    pb = ctx.char.proficiency_bonus
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    dc = 8 + effective_ability_mod(ctx.char, "charisma") + pb
    return {
        "wings": _both("Ali celesti: velocità di volo pari alla tua velocità per 1 minuto.",
                       "Heavenly Wings: fly speed equal to your Speed for 1 minute."),
        "radiance": _both(f"Radiosità interiore: luce intensa 3 m e fioca per altri 3 m; alla fine di ogni tuo turno ogni creatura entro 3 m subisce {pb} danni radianti (a mano).",
                          f"Inner Radiance: bright light 10 ft and dim light 10 ft more; at the end of each of your turns every creature within 10 ft takes {pb} radiant damage (by hand)."),
        "shroud": _both(f"Manto necrotico: le creature non alleate entro 3 m fanno un TS Carisma CD {dc} o sono Spaventate fino alla fine del tuo prossimo turno (lo decide il GM).",
                        f"Necrotic Shroud: non-ally creatures within 10 ft make a Charisma save DC {dc} or are Frightened until the end of your next turn (the GM decides)."),
    }[params["form"]]


def _revelation_type(ctx: RuleContext, _inputs: dict) -> dict[str, str]:
    """Il fisso si somma al danno dell'arma o dell'incantesimo: l'esito dice di che tipo è quella parte."""
    pb = ctx.char.proficiency_bonus
    if _form(ctx) == "shroud":
        return _both(f"Rivelazione celeste: {pb} di questi danni sono necrotici", f"Celestial Revelation: {pb} of this damage is necrotic")
    return _both(f"Rivelazione celeste: {pb} di questi danni sono radianti", f"Celestial Revelation: {pb} of this damage is radiant")


def _revelation_damage(phase: str, rolls: tuple[str, ...]) -> RollOptionSpec:
    return RollOptionSpec(
        key=f"species.2024_aasimar_revelation_damage{'' if phase == 'after_hit' else '_spell'}", phase=phase, rolls=rolls,
        once_per_turn=True, group="species.2024_aasimar_revelation_damage", bonus=lambda c, _i: c.char.proficiency_bonus,
        available=lambda c: _form(c) is not None, effect=_revelation_type,
        label=_both("Rivelazione celeste: danni extra pari alla competenza (necrotici col Manto, altrimenti radianti), una volta per turno",
                    "Celestial Revelation: extra damage equal to your proficiency (necrotic with the Shroud, radiant otherwise), once per turn"))


AASIMAR = (
    data_trait("aasimar", "celestial_resistance", 1, 186, modifiers=(Modifier("resistance:necrotic", 0), Modifier("resistance:radiant", 0))),
    _darkvision("aasimar", 60, 186),
    data_trait("aasimar", "healing_hands", 1, 186, passive=False, action_type="action", uses=Uses(table={1: 1}), restoration="long_rest",
               on_use=OnUse(slot="action", rolls=lambda c: f"{c.char.proficiency_bonus}d4", heal=lambda _c, rolled: rolled,
                            heal_when=lambda _c, p: p.get("mode") == "self", heal_ally_when=lambda _c, p: p.get("mode") == "other",
                            ally_modes=("other",),
                            choices=(UseChoice("mode", _both("Su chi", "On whom"), lambda _c: list(_HEAL_MODES), lambda k: _HEAL_MODES[k]),))),
    data_trait("aasimar", "light_bearer", 1, 186, granted_spells=("light",), dc_ability="charisma"),
    data_trait("aasimar", _REVELATION, 3, 186, passive=False, action_type="bonus_action", uses=Uses(table={1: 1}), restoration="long_rest",
               dc_ability="charisma",
               on_use=OnUse(slot="bonus", message=_revelation_message,
                            state=lambda _c, p: StateSpec(_REVELATION, rounds=10, ends_on=("manual",), data={"form": p["form"]}),
                            choices=(UseChoice("form", _both("Forma", "Form"), lambda _c: list(_FORMS), lambda k: _FORMS[k]),)),
               modifiers=(Modifier("fly_speed", 1, when=lambda c: _form(c) == "wings"),),
               roll_options=(_revelation_damage("after_hit", ("attack",)), _revelation_damage("before", ("spell_damage",)))),
)

# --- Elfo (pag. 189-190) ----------------------------------------------------------------------------------------------
ELF = (
    _darkvision("elf", 60, 189),
    *_lineage_rows("elf", "lineage", 190, (
        ("drow", ("dancing-lights",), "faerie-fire", "darkness"),
        ("high", ("prestidigitation",), "detect-magic", "misty-step"),
        ("wood", ("druidcraft",), "longstrider", "pass-without-trace")),
        drow={"modifiers": (Modifier("sense:darkvision", 120),)}, wood={"modifiers": (Modifier("speed", 5),)}),
    data_trait("elf", "fey_ancestry", 1, 189, roll_options=(_advantage(
        "species.2024_elf_fey_ancestry", ("save",), "Ascendenza fatata: il tiro salvezza è contro l'essere affascinato? Vantaggio",
        "Fey Ancestry: is the saving throw against being charmed? Advantage"),)),
    # Sensi acuti: nessuna riga, l'abilità scelta (``species_options["skill"]``) la scrive il Task 5
    data_trait("elf", "trance", 1, 189),
)

# --- Gnomo (pag. 191) -------------------------------------------------------------------------------------------------
GNOME = (
    _darkvision("gnome", 60, 191),
    data_trait("gnome", "gnomish_cunning", 1, 191, modifiers=(Modifier(
        "advantage", 0, when=lambda c: c.roll == "save" and c.ability in ("intelligence", "wisdom", "charisma"),
        source="feature:species.2024_gnome_gnomish_cunning"),)),
    _lineage("gnome", "lineage", "forest", 191, ("minor-illusion", "speak-with-animals"), passive=False,
             free_spell="speak-with-animals", **_PB_LONG),
    _lineage("gnome", "lineage", "rock", 191, ("mending", "prestidigitation")),  # i congegni: testo
)

# --- Halfling (pag. 193) ----------------------------------------------------------------------------------------------
def _rolled_a_one(ctx: RuleContext) -> bool:
    """Con Vantaggio o Svantaggio il ritiro tocca uno dei due d20, a scelta (pag. 12-13): conta anche l'1 non tenuto."""
    if ctx.natural_d20 is None:  # nessun tiro salvato di questo tipo
        return False
    return 1 in ((((ctx.turn or {}).get("last_roll") or {}).get("dice")) or [ctx.natural_d20])


HALFLING = (
    data_trait("halfling", "brave", 1, 193, roll_options=(_advantage(
        "species.2024_halfling_brave", ("save",), "Coraggioso: il tiro salvezza è contro l'essere spaventato? Vantaggio",
        "Brave: is the saving throw against being frightened? Advantage"),)),
    data_trait("halfling", "halfling_nimbleness", 1, 193),
    # Gratuita e offerta (non automatica): il manuale dice «puoi ritirare». Basta un 1 fra i d20 del tiro salvato
    data_trait("halfling", "luck", 1, 193, roll_options=(RollOptionSpec(
        key="species.2024_halfling_luck", phase="after_roll", after="reroll", rolls=D20_TESTS, available=_rolled_a_one,
        label=_both("Fortuna: hai fatto 1 sul d20, ritiralo (vale il nuovo risultato)", "Luck: you rolled a 1 on the d20, reroll it (the new roll stands)")),)),
    data_trait("halfling", "naturally_stealthy", 1, 193),
)

# --- Umano (pag. 194) -------------------------------------------------------------------------------------------------
# Abile e Versatile: nessuna riga, abilità e talento d'Origine scelti (``species_options``) li scrive il Task 5
HUMAN = (data_trait("human", "resourceful", 1, 194, long_rest_inspiration=True),)

# --- Tiefling (pag. 196-197) ------------------------------------------------------------------------------------------
TIEFLING = (
    _darkvision("tiefling", 60, 196),
    *_lineage_rows("tiefling", "legacy", 197, (
        ("abyssal", ("poison-spray",), "ray-of-sickness", "hold-person"),
        ("chthonic", ("chill-touch",), "false-life", "ray-of-enfeeblement"),
        ("infernal", ("fire-bolt",), "hellish-rebuke", "darkness")),
        abyssal={"modifiers": (Modifier("resistance:poison", 0),)}, chthonic={"modifiers": (Modifier("resistance:necrotic", 0),)},
        infernal={"modifiers": (Modifier("resistance:fire", 0),)}),
    data_trait("tiefling", "otherworldly_presence", 1, 196, granted_spells=("thaumaturgy",)),
)

# Riempito dai moduli delle singole specie: chiave ``2024_dwarf`` -> tratti
SPECIES_TRAITS: dict[str, tuple[FeatureSpec, ...]] = {
    "2024_dragonborn": DRAGONBORN, "2024_dwarf": DWARF, "2024_goliath": GOLIATH, "2024_orc": ORC,
    "2024_aasimar": AASIMAR, "2024_elf": ELF, "2024_gnome": GNOME, "2024_halfling": HALFLING, "2024_human": HUMAN,
    "2024_tiefling": TIEFLING,
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

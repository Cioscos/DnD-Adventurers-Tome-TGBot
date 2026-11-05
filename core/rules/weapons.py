"""Armi: tabella 2024, proprietà, Arti Marziali e Weapon Mastery.

Le armi si riconoscono da ``item_metadata.base_weapon`` o dal nome dell'oggetto, in italiano o in inglese.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from core.game.item_bonuses import item_meta
from core.game.stats import effective_ability_score, roll_ability_mod
from core.rules.edition import character_edition, class_key
from core.rules.proficiencies import is_weapon_proficient
from core.rules.types import ChoiceSpec, RollOptionSpec, RuleContext, TargetEffect

MASTERY_GROUP = "weapon_mastery"  # `CharacterClass.options[...]`: le armi scelte col privilegio


@dataclass(frozen=True)
class Weapon:
    en: str
    it: str
    category: str  # `simple` o `martial`
    mastery: str
    ranged: bool = False
    light: bool = False
    finesse: bool = False


def _w(en: str, it: str, category: str, mastery: str, *flags: str) -> Weapon:
    return Weapon(en, it, category, mastery, "ranged" in flags, "light" in flags, "finesse" in flags)


# Tabella del capitolo 6 del PHB 2024. `light` e `finesse` servono solo a filtrare le armi sceglibili.
WEAPONS: dict[str, Weapon] = {
    "club": _w("Club", "Randello", "simple", "slow", "light"),
    "dagger": _w("Dagger", "Pugnale", "simple", "nick", "light", "finesse"),
    "greatclub": _w("Greatclub", "Randello pesante", "simple", "push"),
    "handaxe": _w("Handaxe", "Accetta", "simple", "vex", "light"),
    "javelin": _w("Javelin", "Giavellotto", "simple", "slow"),
    "light_hammer": _w("Light Hammer", "Martello leggero", "simple", "nick", "light"),
    "mace": _w("Mace", "Mazza", "simple", "sap"),
    "quarterstaff": _w("Quarterstaff", "Bastone ferrato", "simple", "topple"),
    "sickle": _w("Sickle", "Falcetto", "simple", "nick", "light"),
    "spear": _w("Spear", "Lancia", "simple", "sap"),
    "dart": _w("Dart", "Dardo", "simple", "vex", "ranged", "finesse"),
    "light_crossbow": _w("Light Crossbow", "Balestra leggera", "simple", "slow", "ranged"),
    "shortbow": _w("Shortbow", "Arco corto", "simple", "vex", "ranged"),
    "sling": _w("Sling", "Fionda", "simple", "slow", "ranged"),
    "battleaxe": _w("Battleaxe", "Ascia da battaglia", "martial", "topple"),
    "flail": _w("Flail", "Mazzafrusto", "martial", "sap"),
    "glaive": _w("Glaive", "Falcione", "martial", "graze"),
    "greataxe": _w("Greataxe", "Ascia bipenne", "martial", "cleave"),
    "greatsword": _w("Greatsword", "Spadone", "martial", "graze"),
    "halberd": _w("Halberd", "Alabarda", "martial", "cleave"),
    "lance": _w("Lance", "Lancia da cavaliere", "martial", "topple"),
    "longsword": _w("Longsword", "Spada lunga", "martial", "sap"),
    "maul": _w("Maul", "Maglio", "martial", "topple"),
    "morningstar": _w("Morningstar", "Morning star", "martial", "sap"),
    "pike": _w("Pike", "Picca", "martial", "push"),
    "rapier": _w("Rapier", "Stocco", "martial", "vex", "finesse"),
    "scimitar": _w("Scimitar", "Scimitarra", "martial", "nick", "light", "finesse"),
    "shortsword": _w("Shortsword", "Spada corta", "martial", "vex", "light", "finesse"),
    "trident": _w("Trident", "Tridente", "martial", "topple"),
    "warhammer": _w("Warhammer", "Martello da guerra", "martial", "push"),
    "war_pick": _w("War Pick", "Piccone da guerra", "martial", "sap"),
    "whip": _w("Whip", "Frusta", "martial", "slow", "finesse"),
    "blowgun": _w("Blowgun", "Cerbottana", "martial", "vex", "ranged"),
    "hand_crossbow": _w("Hand Crossbow", "Balestra a mano", "martial", "vex", "ranged", "light"),
    "heavy_crossbow": _w("Heavy Crossbow", "Balestra pesante", "martial", "push", "ranged"),
    "longbow": _w("Longbow", "Arco lungo", "martial", "slow", "ranged"),
    "musket": _w("Musket", "Moschetto", "martial", "slow", "ranged"),
    "pistol": _w("Pistol", "Pistola", "martial", "vex", "ranged"),
}

# Altri nomi italiani in uso: l'app e il compendio dicono «Falcione», il documento delle regole «Gliaia».
_ALIASES = (("glaive", "Gliaia"),)
# Il nome più lungo vince: «Lancia da cavaliere» prima di «Lancia».
_NAMES = sorted(
    ((re.compile(rf"\b{re.escape(name.lower())}\b"), key)
     for key, name in (*((k, n) for k, w in WEAPONS.items() for n in (w.en, w.it)), *_ALIASES)),
    key=lambda pair: -len(pair[0].pattern),
)
_PROPERTY_WORDS = {
    "light": ("light", "legger"), "heavy": ("heavy", "pesant"), "finesse": ("finesse", "accurat"),
    "two_handed": ("two_handed", "two-handed", "two handed", "due mani"),
}
_DICE = re.compile(r"^(\d+)d(\d+)([+-]\d+)?$")


def weapon_key(item: Any) -> str | None:
    """Chiave di ``WEAPONS``: quella dichiarata sull'oggetto, altrimenti dal nome. ``None`` se non è in tabella."""
    declared = item_meta(item).get("base_weapon")
    if declared in WEAPONS:
        return declared
    name = str(getattr(item, "name", "")).lower()
    return next((key for pattern, key in _NAMES if pattern.search(name)), None)


def weapon_mastery(item: Any) -> str | None:
    """Proprietà di maestria dell'arma, dalla tabella 2024."""
    key = weapon_key(item)
    return WEAPONS[key].mastery if key else None


def has_property(item: Any, prop: str) -> bool:
    listed = " ".join(str(p).lower() for p in item_meta(item).get("properties") or [])
    return any(word in listed for word in _PROPERTY_WORDS[prop])


def ability_score(char: Any, ability: str) -> int:
    """Punteggio effettivo, con i modificatori degli oggetti equipaggiati."""
    row = next((a for a in char.ability_scores if a.name == ability), None)
    if row is None:
        return 10
    return effective_ability_score(ability, row.value, [i for i in char.items if i.is_equipped])[0]


_SMALL_RACES = ("halfling", "halfelin", "mezzuomo", "gnom", "goblin", "kobold", "coboldo")
_MEDIUM_RACES = ("human", "uman", "elf", "elfo", "elfi", "dwarf", "nano", "nana", "dragon", "drago", "half-orc",
                 "mezzorco", "half-elf", "mezzelf", "tiefling")


def small_race(char: Any) -> bool | None:
    """Il 2014 lega Pesante alla taglia. ``None``: razza che l'app non conosce, lo dichiara il giocatore."""
    race = (getattr(char, "race", None) or "").lower()
    if any(word in race for word in _SMALL_RACES):
        return True
    return False if any(word in race for word in _MEDIUM_RACES) else None


# --- Arti Marziali ------------------------------------------------------------------------------------------------

def is_monk_weapon(item: Any, edition: str) -> bool:
    meta = item_meta(item)
    if meta.get("weapon_type", "melee") == "ranged":
        return False
    key = weapon_key(item)
    category = meta.get("weapon_category") or (WEAPONS[key].category if key else None)
    if edition == "2024":
        return category == "simple" or (category == "martial" and has_property(item, "light"))
    if key == "shortsword":
        return True
    return category == "simple" and not has_property(item, "two_handed") and not has_property(item, "heavy")


def martial_arts_level(char: Any, item: Any = None, ignore_held: bool = False) -> int:
    """Livello da Monaco se Arti Marziali vale ora: niente armatura né scudo, solo armi da monaco. Altrimenti 0.
    ``ignore_held``: per un attacco che non usa ciò che si impugna (il proiettile rilanciato) contano solo armatura e scudo."""
    level = next((c.level for c in char.classes if class_key(c) == "monk"), 0)
    if not level:
        return 0
    edition = character_edition(char)
    worn = [i for i in char.items if i.is_equipped]
    if any(i.item_type in ("armor", "shield") for i in worn):
        return 0
    if ignore_held:
        return level
    held = [i for i in worn if i.item_type == "weapon"] + ([item] if item is not None else [])
    return level if all(is_monk_weapon(w, edition) for w in held) else 0


def _average(dice: str) -> float:
    match = _DICE.match(dice)
    return int(match[1]) * (int(match[2]) + 1) / 2 + int(match[3] or 0) if match else 0


def best_damage_dice(dice: str, martial_die: str) -> str:
    """Il dado di Arti Marziali si tira «al posto di» quello dell'arma: conviene solo se è più alto."""
    return martial_die if _average(martial_die) > _average(dice) else dice


# --- Weapon Mastery -----------------------------------------------------------------------------------------------

def _knows(ctx: RuleContext) -> bool:
    """Nell'edizione 2024, con l'arma scelta da una qualsiasi classe del personaggio."""
    if ctx.edition != "2024" or ctx.item is None:
        return False
    key = weapon_key(ctx.item)
    return bool(key) and any(key in (getattr(c, "options", None) or {}).get(MASTERY_GROUP, []) for c in ctx.char.classes)


def _has(prop: str):
    return lambda ctx: _knows(ctx) and weapon_mastery(ctx.item) == prop


def _modifier(ctx: RuleContext) -> int:
    return roll_ability_mod(ctx.char, ctx.ability) if ctx.ability else 0


def _graze_available(ctx: RuleContext) -> bool:
    pending = (ctx.char.turn_state or {}).get("pending_attack") or {}
    return _has("graze")(ctx) and _modifier(ctx) > 0 and not pending.get("result", {}).get("is_critical")


def _cleave_dice(ctx: RuleContext, _inputs: dict) -> str:
    """Il dado dell'arma senza caratteristica, salvo che sia negativa."""
    meta = item_meta(ctx.item)
    dice = (ctx.grip == "two" and meta.get("versatile_dice")) or meta.get("damage_dice") or "1d4"
    match = _DICE.match(dice)
    if match is None:
        return "0d4"
    flat = int(match[3] or 0) + int(meta.get("magic_bonus") or 0) + min(_modifier(ctx), 0)
    return f"{match[1]}d{match[2]}{flat:+d}" if flat else f"{match[1]}d{match[2]}"


def _topple_effect(ctx: RuleContext, _inputs: dict) -> dict[str, str]:
    dc = 8 + _modifier(ctx) + ctx.char.proficiency_bonus
    return {"it": f"Topple: TS su Costituzione CD {dc}, se fallisce il bersaglio è Prono.",
            "en": f"Topple: DC {dc} Constitution save, on a failure the target is Prone."}


def _topple_target(ctx: RuleContext, _inputs: dict) -> TargetEffect:
    return TargetEffect(condition="prone", save_ability="constitution", save_dc=8 + _modifier(ctx) + ctx.char.proficiency_bonus)


def _until_my_turn(slug: str):
    """Sap e Slow: fino all'inizio del turno di chi colpisce, senza TS."""
    return lambda _ctx, _inputs: TargetEffect(condition=slug, ends_at={"anchor": "source", "edge": "start", "count": 1})


def _note(it: str, en: str):
    return lambda _ctx, _inputs: {"it": it, "en": en}


def _arm_vex(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    # Vale ancora nel turno seguente: `reset_turn` lo scala di uno.
    ctx.char.turn_state = {**(ctx.char.turn_state or {}), "vex": 2}


def _use_vex(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    ctx.char.turn_state = {k: v for k, v in (ctx.char.turn_state or {}).items() if k != "vex"}


def _after_hit(key: str, it: str, en: str, **fields: Any) -> RollOptionSpec:
    return RollOptionSpec(
        key=f"mastery_{key}", phase="after_hit", rolls=("attack",), group="mastery", label={"it": it, "en": en},
        **{"available": _has(key), **fields},
    )


NICK_OPTION = "mastery_nick"  # chi la conferma non spende l'azione bonus

# Da mettere in `FeatureSpec.roll_options` del privilegio (Weapon Mastery di ogni classe).
# Push è solo esito: spostare il bersaglio richiederebbe posizioni, che l'app non ha (D1).
MASTERY_OPTIONS: tuple[RollOptionSpec, ...] = (
    RollOptionSpec(
        key="mastery_graze", phase="after_roll", after="miss", rolls=("attack",), available=_graze_available,
        miss_damage=_modifier,
        label={"it": "Graze: hai mancato, infliggi comunque il modificatore",
               "en": "Graze: you missed, deal your modifier anyway"},
    ),
    RollOptionSpec(
        key=NICK_OPTION, phase="before", rolls=("attack",), once_per_turn=True,
        available=lambda ctx: _has("nick")(ctx) and ctx.offhand,
        label={"it": "Nick: attacco extra senza spendere l'azione bonus",
               "en": "Nick: extra attack without spending your bonus action"},
    ),
    RollOptionSpec(
        key="mastery_vex_advantage", phase="before", rolls=("attack",), mode="advantage", on_confirm=_use_vex,
        available=lambda ctx: bool((ctx.char.turn_state or {}).get("vex")),
        label={"it": "Vex: attacchi la creatura che hai colpito?", "en": "Vex: attacking the creature you hit?"},
    ),
    _after_hit(
        "cleave", "Cleave: attacca una seconda creatura vicina alla prima",
        "Cleave: attack a second creature next to the first",
        available=lambda ctx: _has("cleave")(ctx) and ctx.attack_mode == "melee",
        extra_dice=_cleave_dice, crit_doubles=False, separate_damage=True, once_per_turn=True, second_attack=True,
    ),
    _after_hit("push", "Push: allontana il bersaglio di 3 m", "Push: move the target 10 ft away",
               effect=_note("Push: bersaglio spinto di 3 m, se è Grande o più piccolo.",
                            "Push: target pushed 10 ft, if Large or smaller.")),
    _after_hit("sap", "Sap: svantaggio al prossimo attacco del bersaglio",
               "Sap: disadvantage on the target's next attack",
               effect=_note("Sap: svantaggio al prossimo attacco del bersaglio, fino all'inizio del tuo turno.",
                            "Sap: disadvantage on the target's next attack, until the start of your turn."),
               target_effect=_until_my_turn("custom:sap")),
    _after_hit("slow", "Slow: velocità del bersaglio ridotta di 3 m", "Slow: target's speed reduced by 10 ft",
               effect=_note("Slow: velocità del bersaglio -3 m fino all'inizio del tuo turno, non cumulabile.",
                            "Slow: target's speed -10 ft until the start of your turn, doesn't stack."),
               target_effect=_until_my_turn("custom:slow")),
    _after_hit("topple", "Topple: TS su Costituzione o il bersaglio cade Prono",
               "Topple: Constitution save or the target falls Prone", effect=_topple_effect,
               target_effect=_topple_target),
    _after_hit("vex", "Vex: vantaggio al prossimo attacco contro il bersaglio",
               "Vex: advantage on your next attack against the target", on_confirm=_arm_vex,
               effect=_note("Vex: vantaggio al prossimo attacco contro il bersaglio, entro la fine del tuo prossimo turno.",
                            "Vex: advantage on your next attack against the target, by the end of your next turn.")),
)


def _mastery_label(key: str) -> dict:
    w = WEAPONS[key]
    return {"name": {"it": w.it, "en": w.en},
            "summary": {"it": w.mastery.capitalize(), "en": w.mastery.capitalize()}}


def mastery_choice(levels: dict[int, int], melee_only: bool = False) -> ChoiceSpec:
    """La scelta delle armi: fra quelle in cui il personaggio è competente, sostituibile dopo un riposo lungo."""

    def options(ctx: RuleContext) -> list[str]:
        out = []
        for key, w in WEAPONS.items():
            props = [p for p, on in (("light", w.light), ("finesse", w.finesse)) if on]
            probe = SimpleNamespace(name=w.it, item_metadata={"weapon_category": w.category, "properties": props})
            if not (melee_only and w.ranged) and is_weapon_proficient(ctx.char, probe):
                out.append(key)
        return out

    return ChoiceSpec(group=MASTERY_GROUP, levels=levels, options=options, replaceable=True, label=_mastery_label)

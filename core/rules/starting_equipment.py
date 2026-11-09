"""Equipaggiamento di partenza per classe ed edizione (Task 47): oggetti inerti e monete.

Una tabella per classe ed edizione: una lista di gruppi, ogni gruppo una lista di alternative.
Un gruppo con una sola alternativa e' fisso. Ogni alternativa e' una stringa `chiave[*quantita]+...`,
con `gold:N` per le monete. Le chiavi sono indici dell'SRD (armi e armature, dati da `equipment.json`)
oppure voci di `GENERIC`. I pacchetti non sono scomposti: un oggetto generico col nome del pacchetto.
Nessun equipaggiamento automatico, nessun effetto: il giocatore equipaggia a mano.
"""
from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

from core.rules.types import Edition

_SRD = Path(__file__).resolve().parents[2] / "webapp" / "src" / "data" / "srd" / "equipment.json"

# chiave -> (item_type, it, en). I segnaposto «a scelta» li rinomina il giocatore.
GENERIC: dict[str, tuple[str, str, str]] = {
    "simple-weapon": ("generic", "Arma semplice a scelta", "Simple weapon of choice"),
    "simple-melee": ("generic", "Arma semplice da mischia a scelta", "Simple melee weapon of choice"),
    "martial-weapon": ("generic", "Arma da guerra a scelta", "Martial weapon of choice"),
    "martial-melee": ("generic", "Arma da guerra da mischia a scelta", "Martial melee weapon of choice"),
    "wooden-shield": ("shield", "Scudo di legno", "Wooden shield"),
    "arrows": ("ammunition", "Frecce", "Arrows"),
    "bolts": ("ammunition", "Quadrelli", "Crossbow bolts"),
    "quiver": ("generic", "Faretra", "Quiver"),
    "explorer-pack": ("generic", "Dotazione da esploratore", "Explorer's pack"),
    "dungeoneer-pack": ("generic", "Dotazione da avventuriero", "Dungeoneer's pack"),
    "priest-pack": ("generic", "Dotazione da sacerdote", "Priest's pack"),
    "scholar-pack": ("generic", "Dotazione da studioso", "Scholar's pack"),
    "burglar-pack": ("generic", "Dotazione da scassinatore", "Burglar's pack"),
    "diplomat-pack": ("generic", "Dotazione da diplomatico", "Diplomat's pack"),
    "entertainer-pack": ("generic", "Dotazione da intrattenitore", "Entertainer's pack"),
    "holy-symbol": ("generic", "Simbolo sacro", "Holy symbol"),
    "druidic-focus": ("generic", "Focus druidico", "Druidic focus"),
    "arcane-focus": ("generic", "Focus arcano", "Arcane focus"),
    "component-pouch": ("generic", "Borsa componenti", "Component pouch"),
    "instrument": ("tool", "Strumento musicale a scelta", "Musical instrument of choice"),
    "lute": ("tool", "Liuto", "Lute"),
    "artisan-or-instrument": ("tool", "Strumenti da artigiano o strumento musicale", "Artisan's tools or musical instrument"),
    "thieves-tools": ("tool", "Arnesi da scasso", "Thieves' tools"),
    "herbalism-kit": ("tool", "Kit da erborista", "Herbalism kit"),
    "spellbook": ("generic", "Libro degli incantesimi", "Spellbook"),
    "occult-book": ("generic", "Libro (sapere occulto)", "Book (occult lore)"),
    "robe": ("generic", "Veste", "Robe"),
}

_E, _D = "explorer-pack", "dungeoneer-pack"
_S, _SM, _M, _MM = "simple-weapon", "simple-melee", "martial-weapon", "martial-melee"
_XB = "crossbow-light+bolts*20"
_FOCUS = ("component-pouch", "arcane-focus")

Groups = tuple[tuple[str, ...], ...]

STARTING_EQUIPMENT: dict[tuple[Edition, str], Groups] = {
    ("2014", "barbarian"): (("greataxe", _MM), ("handaxe*2", _SM), (_E,), ("javelin*4",)),
    ("2014", "bard"): (("rapier", "longsword", _S), ("diplomat-pack", "entertainer-pack"), ("lute", "instrument"),
                       ("leather-armor",), ("dagger",)),
    ("2014", "cleric"): (("mace", "warhammer"), ("scale-mail", "leather-armor", "chain-mail"), (_XB, _S),
                         ("priest-pack", _E), ("shield+holy-symbol",)),
    ("2014", "druid"): (("wooden-shield", _S), ("scimitar", _SM), ("leather-armor+explorer-pack+druidic-focus",)),
    ("2014", "fighter"): (("chain-mail", "leather-armor+longbow+arrows*20"), (f"{_M}+shield", f"{_M}*2"),
                          (_XB, "handaxe*2"), (_D, _E)),
    ("2014", "monk"): (("shortsword", _S), (_D, _E), ("dart*10",)),
    ("2014", "paladin"): ((f"{_M}+shield", f"{_M}*2"), ("javelin*5", _SM), ("priest-pack", _E),
                          ("chain-mail+holy-symbol",)),
    ("2014", "ranger"): (("scale-mail", "leather-armor"), ("shortsword*2", f"{_SM}*2"), (_D, _E),
                         ("longbow+quiver+arrows*20",)),
    ("2014", "rogue"): (("rapier", "shortsword"), ("shortbow+quiver+arrows*20", "shortsword"),
                        ("burglar-pack", _D, _E), ("leather-armor+dagger*2+thieves-tools",)),
    ("2014", "sorcerer"): ((_XB, _S), _FOCUS, (_D, _E), ("dagger*2",)),
    ("2014", "warlock"): ((_XB, _S), _FOCUS, ("scholar-pack", _D), (f"leather-armor+{_S}+dagger*2",)),
    ("2014", "wizard"): (("quarterstaff", "dagger"), _FOCUS, ("scholar-pack", _E), ("spellbook",)),
    ("2024", "barbarian"): (("greataxe+handaxe*4+explorer-pack+gold:15", "gold:75"),),
    ("2024", "bard"): (("leather-armor+dagger*2+instrument+entertainer-pack+gold:19", "gold:90"),),
    ("2024", "cleric"): (("chain-shirt+shield+mace+holy-symbol+priest-pack+gold:7", "gold:110"),),
    ("2024", "druid"): (("leather-armor+shield+sickle+druidic-focus+explorer-pack+herbalism-kit+gold:9", "gold:50"),),
    ("2024", "fighter"): (("chain-mail+greatsword+flail+javelin*8+dungeoneer-pack+gold:4",
                           "studded-leather-armor+scimitar+shortsword+longbow+arrows*20+quiver+dungeoneer-pack+gold:11",
                           "gold:155"),),
    ("2024", "monk"): (("spear+dagger*5+artisan-or-instrument+explorer-pack+gold:11", "gold:50"),),
    ("2024", "paladin"): (("chain-mail+shield+longsword+javelin*6+holy-symbol+priest-pack+gold:9", "gold:150"),),
    ("2024", "ranger"): (("studded-leather-armor+scimitar+shortsword+longbow+arrows*20+quiver+druidic-focus"
                          "+explorer-pack+gold:7", "gold:150"),),
    ("2024", "rogue"): (("leather-armor+dagger*2+shortsword+shortbow+arrows*20+quiver+thieves-tools"
                         "+burglar-pack+gold:8", "gold:100"),),
    ("2024", "sorcerer"): (("spear+dagger*2+arcane-focus+dungeoneer-pack+gold:28", "gold:50"),),
    ("2024", "warlock"): (("leather-armor+sickle+dagger*2+arcane-focus+occult-book+scholar-pack+gold:15", "gold:100"),),
    ("2024", "wizard"): (("dagger*2+quarterstaff+robe+spellbook+scholar-pack+gold:5", "gold:55"),),
}


@cache
def _srd() -> dict[str, dict[str, Any]]:
    return {e["index"]: e for e in json.loads(_SRD.read_text(encoding="utf-8"))["items"]}


def _parse(alt: str) -> tuple[list[tuple[str, int]], int]:
    """Alternativa -> (oggetti `(chiave, quantita)`, oro)."""
    items: list[tuple[str, int]] = []
    gold = 0
    for token in alt.split("+"):
        if token.startswith("gold:"):
            gold += int(token[5:])
            continue
        key, _, qty = token.partition("*")
        if key not in GENERIC and key not in _srd():
            raise KeyError(key)
        items.append((key, int(qty or 1)))
    return items, gold


def _item(key: str, qty: int, lang: str) -> dict[str, Any]:
    """Riga di inventario: dati dell'SRD per armi e armature, oggetto generico per il resto."""
    if key in GENERIC:
        kind, it, en = GENERIC[key]
        return {"name": it if lang == "it" else en, "item_type": kind, "quantity": qty, "weight": 0.0,
                "item_metadata": {"ac_bonus": 2} if kind == "shield" else None}
    e = _srd()[key]
    meta: dict[str, Any] = {"srd_index": key}
    if e.get("armor_type") == "shield":
        kind, meta["ac_bonus"] = "shield", e.get("ac_value", 2)
    elif e.get("armor_type"):
        kind = "armor"
        meta.update(armor_type=e["armor_type"], ac_value=e.get("ac_value", 10),
                    stealth_disadvantage=bool(e.get("stealth_disadvantage")), strength_req=e.get("strength_req", 0))
    else:
        kind = "weapon"
        dice = e.get("damage_dice") or "1d6"
        meta.update(damage_dice=f"{dice}d1" if dice.isdigit() else dice,
                    damage_type=f"dmg_{e.get('damage_type', 'slashing')}",
                    weapon_type=e.get("weapon_range", "melee"), properties=e.get("properties", []))
        if e.get("versatile_dice"):
            meta["versatile_dice"] = e["versatile_dice"]
        if e.get("weapon_category"):
            meta["weapon_category"] = e["weapon_category"]
    return {"name": e["name"].get(lang) or e["name"]["en"], "item_type": kind,
            "quantity": qty if kind == "weapon" else 1, "weight": float(e.get("weight_lb", 0)), "item_metadata": meta}


def starting_groups(edition: str, class_key: str) -> Groups:
    """Gruppi di scelta; vuoto per una classe custom."""
    return STARTING_EQUIPMENT.get(("2024" if edition == "2024" else "2014", class_key), ())


def describe(edition: str, class_key: str, lang: str) -> list[list[str]]:
    """Etichette delle alternative di ogni gruppo, nella lingua richiesta."""
    out: list[list[str]] = []
    for group in starting_groups(edition, class_key):
        labels = []
        for alt in group:
            items, gold = _parse(alt)
            parts = [f"{r['quantity']}x {r['name']}" if r["quantity"] > 1 else r["name"]
                     for r in (_item(k, q, lang) for k, q in items)]
            if gold:
                parts.append(f"{gold} mo" if lang == "it" else f"{gold} gp")
            labels.append(", ".join(parts))
        out.append(labels)
    return out


def resolve(edition: str, class_key: str, picks: list[int], lang: str) -> tuple[list[dict[str, Any]], int]:
    """Scelte (una alternativa per gruppo) -> righe di inventario e oro. `ValueError` se non valide."""
    groups = starting_groups(edition, class_key)
    if not groups or len(picks) != len(groups) or any(not 0 <= p < len(g) for p, g in zip(picks, groups)):
        raise ValueError("invalid_starting_equipment")
    rows: list[dict[str, Any]] = []
    total_gold = 0
    for pick, group in zip(picks, groups):
        items, gold = _parse(group[pick])
        total_gold += gold
        for key, qty in items:
            row = _item(key, qty, lang)
            # Stessa riga da gruppi diversi (due pugnali): una riga sola, quantita' sommata.
            same = next((r for r in rows if r["name"] == row["name"] and r["item_metadata"] == row["item_metadata"]), None)
            if same:
                same["quantity"] += row["quantity"]
            else:
                rows.append(row)
    # Poche armi (due asce) = una riga ciascuna, cosi' si impugnano una per mano; le pile (giavellotti, dardi) restano.
    out: list[dict[str, Any]] = []
    for r in rows:
        n = r["quantity"] if r["item_type"] == "weapon" and r["quantity"] <= 2 else 1
        out += [{**r, "quantity": r["quantity"] // n} for _ in range(n)]
    return out, total_gold


ASSASSIN_KITS_FLAG = "assassin_kits_given"
_KITS = (("Kit da travestimento", "Disguise Kit"), ("Kit da avvelenatore", "Poisoner's Kit"))


def grant_assassin_kits(char, lang: str) -> None:
    """Assassino 2024 (Strumenti dell'Assassino): i due kit entrano in inventario, inerti, una volta sola."""
    from core.db.models import Item
    from core.rules.edition import character_edition
    if (char.settings or {}).get(ASSASSIN_KITS_FLAG) or character_edition(char) != "2024":
        return
    if not any(c.subclass_key == "assassin" for c in char.classes):
        return
    for it, en in _KITS:
        char.items.append(Item(name=it if lang == "it" else en, item_type="tool", quantity=1, weight=0.0))
    char.settings = {**(char.settings or {}), ASSASSIN_KITS_FLAG: True}
    char.recalculate_encumbrance()

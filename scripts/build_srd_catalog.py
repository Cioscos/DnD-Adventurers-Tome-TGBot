"""Build the English SRD 5e (2014) catalogue JSON files in webapp/src/data/srd/.

Run from Windows:  uv run python scripts/build_srd_catalog.py

Source: https://www.dnd5eapi.co (CC-BY-4.0 SRD content). Uses the REST API
(per-item detail) because the GraphQL schema hides damage-at-slot-level and the
weapon/armor union fields; the GraphQL client in bot/dnd5e is not needed here.
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import date
from pathlib import Path

import httpx

API = "https://www.dnd5eapi.co"
OUT = Path(__file__).resolve().parents[1] / "webapp" / "src" / "data" / "srd"

PROP_SLUGS = {
    "finesse": "prop_finesse", "versatile": "prop_versatile", "heavy": "prop_heavy",
    "light": "prop_light", "thrown": "prop_thrown", "two-handed": "prop_two_handed",
    "ammunition": "prop_ammunition", "loading": "prop_loading", "reach": "prop_reach",
    "special": "prop_special",
}


# --- curated magic-item mechanics (5e SRD values) ---------------------------------
def _w(n, rec, dice, spells=(), bonuses=(), c=True):
    return {"charges": {"max": n, "recharge": rec, "recharge_dice": dice} if c else None,
            "bonuses": [{"target": t, "value": v} for t, v in bonuses],
            "granted_spells": [{"spell": s, "charge_cost": k} for s, k in spells]}


def _b(*bonuses):
    return _w(0, None, None, bonuses=bonuses, c=False)


MECHANICS: dict[str, dict] = {
    "wand-of-magic-missiles": _w(7, "dawn", "1d6+1", [("magic-missile", 1)]),
    "wand-of-fireballs": _w(7, "dawn", "1d6+1", [("fireball", 1)]),
    "wand-of-lightning-bolts": _w(7, "dawn", "1d6+1", [("lightning-bolt", 1)]),
    "wand-of-web": _w(7, "dawn", "1d6+1", [("web", 1)]),
    "wand-of-fear": _w(7, "dawn", "1d6+1", [("fear", 2)]),
    "wand-of-polymorph": _w(7, "dawn", "1d6+1", [("polymorph", 1)]),
    "wand-of-paralysis": _w(7, "dawn", "1d6+1"),
    "wand-of-binding": _w(7, "dawn", "1d6+1"),
    "wand-of-wonder": _w(7, "dawn", "1d6+1"),
    "wand-of-enemy-detection": _w(7, "dawn", "1d6+1"),
    "wand-of-magic-detection": _w(3, "dawn", "1d3", [("detect-magic", 1)]),
    "wand-of-secrets": _w(3, "dawn", "1d3"),
    "wand-of-the-war-mage-1": _b(("spell_attack", 1)),
    "wand-of-the-war-mage-2": _b(("spell_attack", 2)),
    "wand-of-the-war-mage-3": _b(("spell_attack", 3)),
    "staff-of-fire": _w(10, "dawn", "1d6+4", [("burning-hands", 1), ("fireball", 3), ("wall-of-fire", 4)]),
    "staff-of-frost": _w(10, "dawn", "1d6+4", [("cone-of-cold", 5), ("fog-cloud", 1), ("ice-storm", 4), ("wall-of-ice", 4)]),
    "staff-of-healing": _w(10, "dawn", "1d6+4", [("cure-wounds", 1), ("lesser-restoration", 2), ("mass-cure-wounds", 5)]),
    "staff-of-charming": _w(10, "dawn", "1d8+2", [("charm-person", 1), ("command", 1), ("comprehend-languages", 1)]),
    "staff-of-swarming-insects": _w(10, "dawn", "1d6+4", [("giant-insect", 4), ("insect-plague", 5)]),
    "staff-of-withering": _w(3, "dawn", "1d3"),
    "staff-of-the-woodlands": _w(10, "dawn", "1d6+4", [("animal-friendship", 1), ("awaken", 5), ("barkskin", 2), ("speak-with-plants", 3), ("wall-of-thorns", 6)], [("spell_attack", 2)]),
    "staff-of-striking": _w(10, "dawn", "1d6+4", bonuses=[("attack", 3), ("damage", 3)]),
    "staff-of-power": _w(
        20, "dawn", "2d8+4",
        [("cone-of-cold", 5), ("fireball", 5), ("globe-of-invulnerability", 6), ("hold-monster", 5), ("levitate", 2),
         ("lightning-bolt", 5), ("magic-missile", 1), ("ray-of-enfeeblement", 1), ("wall-of-force", 5)],
        [("attack", 2), ("damage", 2), ("spell_attack", 2), ("ac", 2), ("saves", 2)]),
    "staff-of-the-magi": _w(
        50, "dawn", "4d6+2",
        [("conjure-elemental", 7), ("dispel-magic", 3), ("fireball", 7), ("flaming-sphere", 2), ("ice-storm", 4),
         ("invisibility", 2), ("knock", 2), ("lightning-bolt", 7), ("passwall", 5), ("plane-shift", 7),
         ("telekinesis", 5), ("wall-of-fire", 4), ("web", 2)],
        [("spell_attack", 2)]),
    "ring-of-three-wishes": _w(3, None, None, [("wish", 1)]),
    "ring-of-the-ram": _w(3, "dawn", "1d3"),
    "scarab-of-protection": _w(12, None, None),
    "gem-of-seeing": _w(3, "dawn", "1d3"),
    "cloak-of-protection": _b(("ac", 1), ("saves", 1)),
    "ring-of-protection": _b(("ac", 1), ("saves", 1)),
    "bracers-of-defense": _b(("ac", 2)),
    "ioun-stone-of-protection": _b(("ac", 1)),
    "robe-of-the-archmagi": _b(("spell_attack", 2), ("spell_dc", 2)),
    "armor-1": _b(("ac", 1)), "armor-2": _b(("ac", 2)), "armor-3": _b(("ac", 3)),
    "dwarven-plate": _b(("ac", 2)),
    "glamoured-studded-leather-armor": _b(("ac", 1)),
    "dragon-scale-mail": _b(("ac", 1)),
    "weapon-1": _b(("attack", 1), ("damage", 1)),
    "weapon-2": _b(("attack", 2), ("damage", 2)),
    "weapon-3": _b(("attack", 3), ("damage", 3)),
    "ammunition-1": _b(("attack", 1), ("damage", 1)),
    "ammunition-2": _b(("attack", 2), ("damage", 2)),
    "ammunition-3": _b(("attack", 3), ("damage", 3)),
    "sun-blade": _b(("attack", 2), ("damage", 2)),
    "holy-avenger": _b(("attack", 3), ("damage", 3)),
    "vorpal-sword": _b(("attack", 3), ("damage", 3)),
    "dwarven-thrower": _b(("attack", 3), ("damage", 3)),
    "scimitar-of-speed": _b(("attack", 2), ("damage", 2)),
}

# Curated rules text for racial saving-throw advantages (not in the API as data).
ROLL_NOTES = {
    "dwarf": {"poison_save": "Advantage on saving throws against poison, and resistance against poison damage."},
    "elf": {"charm_save": "Advantage on saving throws against being charmed, and magic can't put you to sleep."},
    "halfling": {"frightened_save": "Advantage on saving throws against being frightened."},
}

# Desc only mentions attunement further down (Giant's Bane clause), so the first-line check misses it.
ATTUNEMENT_OVERRIDES = {"hammer-of-thunderbolts"}

SEM = asyncio.Semaphore(15)


async def get(client: httpx.AsyncClient, path: str) -> dict:
    async with SEM:
        for attempt in range(4):
            try:
                r = await client.get(API + path)
                r.raise_for_status()
                return r.json()
            except httpx.HTTPError:
                if attempt == 3:
                    raise
                await asyncio.sleep(1 + attempt)
    raise AssertionError("unreachable")


async def fetch_all(client, endpoint: str) -> list[dict]:
    idx = [r["index"] for r in (await get(client, f"/api/2014/{endpoint}"))["results"]]
    return await asyncio.gather(*(get(client, f"/api/2014/{endpoint}/{i}") for i in idx))


def en(s):
    return {"en": s}


def text(lines) -> str:
    return "\n\n".join(lines or [])


def feet(s: str | None) -> int | None:
    """'120 feet' / '120 ft.' -> 120, '1 mile' -> 5280, anything else (Self, Touch, ...) -> None."""
    m = re.fullmatch(r"\s*(\d+)\s*(feet|foot|ft\.?)\s*", s or "", re.I)
    if m:
        return int(m[1])
    m = re.fullmatch(r"\s*(\d+)\s*miles?\s*", s or "", re.I)
    return int(m[1]) * 5280 if m else None


def linear_increment(levels: dict[str, str]) -> str | None:
    """Per-step dice increment if the damage table grows linearly (same die), else None."""
    parts = []
    for k in sorted(levels, key=int):
        m = re.fullmatch(r"(\d+)d(\d+)", levels[k])
        if not m:
            return None
        parts.append((int(m[1]), int(m[2])))
    if len(parts) < 2 or len({p[1] for p in parts}) != 1:
        return None
    steps = {b[0] - a[0] for a, b in zip(parts, parts[1:])}
    if len(steps) != 1:
        return None
    n = steps.pop()
    return f"{n}d{parts[0][1]}" if n > 0 else None


def dice(d: str | None) -> str | None:
    """Normalise a dice string to NdM[+K]: strip spaces, drop the '+ MOD' placeholder (UI adds the modifier)."""
    return re.sub(r"\+?MOD$", "", d.replace(" ", "")) if d else d


HIGHER_RE = re.compile(r"(?:increases by|additional) (\d+d\d+) for each slot level above", re.I)
# Upcast che il testo non esprime come dadi: un dardo in più (1d4+1) per livello.
HIGHER_OVERRIDES = {"magic-missile": "1d4+1"}


def build_spell(s: dict) -> dict:
    dmg = s["damage"][0] if s.get("damage") else {}
    table = dmg.get("damage_at_slot_level") or dmg.get("damage_at_character_level") or {}
    base = table[min(table, key=int)] if table else None
    inc = linear_increment(dmg["damage_at_slot_level"]) if dmg.get("damage_at_slot_level") else None
    if inc is None and base and (m := HIGHER_RE.search(text(s.get("higher_level")))):
        inc = m[1]  # "every two slot levels" / extra darts or rays do not match
    inc = HIGHER_OVERRIDES.get(s["index"], inc)
    aoe = s.get("area_of_effect")
    return {
        "index": s["index"], "name": en(s["name"]), "level": s["level"], "school": s["school"]["index"],
        "casting_time": en(s["casting_time"]), "range_ft": feet(s["range"]), "range_text": en(s["range"]),
        "area": {"type": aoe["type"], "size_ft": int(aoe["size"])} if aoe else None,
        "components": s["components"], "material": en(s["material"]) if s.get("material") else None,
        "duration": en(s["duration"]), "concentration": s["concentration"], "ritual": s["ritual"],
        "desc": en(text(s["desc"])), "higher_level": en(text(s["higher_level"])) if s.get("higher_level") else None,
        "attack_type": "ATK" if s.get("attack_type") else ("SAVE" if s.get("dc") else None),
        "save_ability": s["dc"]["dc_type"]["index"] if s.get("dc") else None,
        "damage_dice": dice(base),
        "damage_type": dmg["damage_type"]["index"] if dmg.get("damage_type") else None,
        "higher_levels_dice": inc,
        "classes": sorted(c["index"] for c in s.get("classes", [])),
    }


def build_magic_item(m: dict) -> dict:
    desc = m.get("desc") or []
    out = {
        "index": m["index"], "name": en(m["name"]), "rarity": m["rarity"]["name"].lower(),
        "requires_attunement": m["index"] in ATTUNEMENT_OVERRIDES or any("requires attunement" in d.lower() for d in desc[:1]),
        "category": m["equipment_category"]["index"], "desc": en(text(desc)),
        "charges": None, "bonuses": [], "granted_spells": [],
    }
    out.update(MECHANICS.get(m["index"], {}))
    return out


def build_equipment(e: dict) -> dict | None:
    cat = e["equipment_category"]["index"]
    base = {"index": e["index"], "name": en(e["name"]), "weight_lb": e.get("weight")}
    if cat == "weapon":
        props = [PROP_SLUGS[p["index"]] for p in e.get("properties", []) if p["index"] in PROP_SLUGS]
        two = e.get("two_handed_damage")
        dmg = e.get("damage") or {}  # the net deals no damage
        return {**base, "damage_dice": dice(dmg.get("damage_dice")), "damage_type": (dmg.get("damage_type") or {}).get("index"),
                "weapon_category": e["weapon_category"].lower(), "weapon_range": e["weapon_range"].lower(),
                "properties": sorted(props),
                "versatile_dice": dice(two["damage_dice"]) if two and "prop_versatile" in props else None,
                "range_ft": (e.get("range") or {}).get("normal"),
                "thrown_range_ft": [tr["normal"], tr["long"]] if (tr := e.get("throw_range")) else None}
    if cat == "armor":
        return {**base, "armor_type": e["armor_category"].lower(), "ac_value": e["armor_class"]["base"],
                "dex_bonus": e["armor_class"]["dex_bonus"], "strength_req": e.get("str_minimum") or 0,
                "stealth_disadvantage": e["stealth_disadvantage"]}
    return None


def darkvision(traits: list[dict]) -> list[dict]:
    out = []
    for t in traits:
        if "darkvision" in t["index"]:
            m = re.search(r"within (\d+) feet", text(t["desc"]))
            if m:
                out.append({"type": "darkvision", "range_ft": int(m[1])})
    return out


def trait(t: dict) -> dict:
    return {"index": t["index"], "name": en(t["name"]), "desc": en(text(t["desc"]))}


def bonuses(lst) -> dict:
    return {b["ability_score"]["index"]: b["bonus"] for b in lst}


async def build_races(client) -> list[dict]:
    out = []
    for r in await fetch_all(client, "races"):
        traits = await asyncio.gather(*(get(client, t["url"]) for t in r.get("traits", [])))
        subs = []
        for sr in await asyncio.gather(*(get(client, s["url"]) for s in r.get("subraces", []))):
            st = await asyncio.gather(*(get(client, t["url"]) for t in sr.get("racial_traits", [])))
            subs.append({"index": sr["index"], "name": en(sr["name"]), "ability_bonuses": bonuses(sr["ability_bonuses"]),
                         "senses": darkvision(st), "traits": [trait(t) for t in st]})
        out.append({"index": r["index"], "name": en(r["name"]), "speed_ft": r["speed"],
                    "ability_bonuses": bonuses(r["ability_bonuses"]), "size": r["size"].lower(),
                    "languages": [lang["index"] for lang in r.get("languages", [])], "senses": darkvision(traits),
                    "traits": [trait(t) for t in traits], "subraces": subs,
                    "roll_notes": {k: en(v) for k, v in ROLL_NOTES.get(r["index"], {}).items()}})
    return out


def build_background(b: dict) -> dict:
    return {"index": b["index"], "name": en(b["name"]),
            "skill_proficiencies": [p["index"].removeprefix("skill-") for p in b["starting_proficiencies"]],
            "feature": {"name": en(b["feature"]["name"]), "desc": en(text(b["feature"]["desc"]))}}


def build_feat(f: dict) -> dict:
    return {"index": f["index"], "name": en(f["name"]), "desc": en(text(f["desc"])),
            "prerequisites": [{"ability": p["ability_score"]["index"], "minimum": p["minimum_score"]}
                              for p in f["prerequisites"]]}


def num(s):
    m = re.match(r"\s*(\d+)", s) if isinstance(s, str) else None
    return int(m[1]) if m else None


def build_monster(m: dict) -> dict:
    prof = {p["proficiency"]["index"]: p["value"] for p in m.get("proficiencies", [])}

    def action(a):
        d = (a.get("damage") or [{}])[0]
        dt = (d.get("damage_type") or {}).get("index")
        return {"name": en(a["name"]), "desc": en(a["desc"]), "attack_bonus": a.get("attack_bonus"),
                "damage_dice": dice(d.get("damage_dice")), "damage_type": dt}

    return {
        "index": m["index"], "name": en(m["name"]), "size": m["size"].lower(), "type": m["type"],
        "alignment": m["alignment"], "armor_class": m["armor_class"][0]["value"] if m["armor_class"] else None,
        "hit_points": m["hit_points"], "hit_dice": m["hit_dice"],
        "speed": {f"{k}_ft": num(v) for k, v in m["speed"].items() if num(v) is not None},
        "abilities": {k[:3]: m[k] for k in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")},
        "saves": {k.removeprefix("saving-throw-"): v for k, v in prof.items() if k.startswith("saving-throw-")},
        "skills": {k.removeprefix("skill-"): v for k, v in prof.items() if k.startswith("skill-")},
        "senses": {k: (v if k == "passive_perception" else num(v)) for k, v in m["senses"].items()},
        "languages": m["languages"], "challenge_rating": m["challenge_rating"], "xp": m["xp"],
        "traits": [{"name": en(t["name"]), "desc": en(t["desc"])} for t in m.get("special_abilities", [])],
        "actions": [action(a) for a in m.get("actions", [])],
    }


def write(name: str, items: list[dict]) -> None:
    items = sorted(items, key=lambda i: i["index"])
    doc = {"_meta": {"source": "https://www.dnd5eapi.co (D&D 5e SRD 2014)", "license": "CC-BY-4.0",
                     "generated_at": date.today().isoformat()}, "items": items}
    (OUT / f"{name}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{name}: {len(items)}")


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        spells = [build_spell(s) for s in await fetch_all(c, "spells")]
        items = [build_magic_item(m) for m in await fetch_all(c, "magic-items")]
        missing = set(MECHANICS) - {i["index"] for i in items}
        spell_ids = {s["index"] for s in spells}
        bad = {g["spell"] for v in MECHANICS.values() for g in v["granted_spells"]} - spell_ids
        assert not missing and not bad, f"curated data refers to unknown ids: {missing} {bad}"
        equip = [x for e in await fetch_all(c, "equipment") if (x := build_equipment(e))]
        write("spells", spells)
        write("magic-items", items)
        write("equipment", equip)
        write("races", await build_races(c))
        write("backgrounds", [build_background(b) for b in await fetch_all(c, "backgrounds")])
        write("feats", [build_feat(f) for f in await fetch_all(c, "feats")])
        write("monsters", [build_monster(m) for m in await fetch_all(c, "monsters")])


if __name__ == "__main__":
    asyncio.run(main())

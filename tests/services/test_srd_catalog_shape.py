"""Shape checks for the generated SRD catalogue (webapp/src/data/srd/*.json)."""
import json
import re
from pathlib import Path

import pytest

SRD = Path(__file__).resolve().parents[2] / "webapp" / "src" / "data" / "srd"
FILES = ["spells", "magic-items", "equipment", "races", "backgrounds", "feats", "monsters"]
PROPS = {"prop_finesse", "prop_versatile", "prop_heavy", "prop_light", "prop_thrown",
         "prop_two_handed", "prop_ammunition", "prop_loading", "prop_reach", "prop_special"}


def load(name):
    return json.loads((SRD / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", FILES)
def test_envelope_sorted(name):
    d = load(name)
    assert d["_meta"]["license"] == "CC-BY-4.0" and d["_meta"]["source"] and d["_meta"]["generated_at"]
    idx = [i["index"] for i in d["items"]]
    assert idx == sorted(idx) and len(idx) == len(set(idx))
    assert all(isinstance(i["name"]["en"], str) for i in d["items"])


def test_spells():
    items = load("spells")["items"]
    assert len(items) >= 300
    for s in items:
        assert 0 <= s["level"] <= 9
        assert s["range_ft"] is None or isinstance(s["range_ft"], int)
        assert s["area"] is None or isinstance(s["area"]["size_ft"], int)
        assert set(s["components"]) <= {"V", "S", "M"}
        assert s["attack_type"] in ("ATK", "SAVE", None)
        for k in ("range_text", "casting_time", "duration", "desc"):
            assert "en" in s[k]
        assert "higher_levels_dice" in s and "classes" in s
    fb = next(s for s in items if s["index"] == "fireball")
    assert fb["range_ft"] == 150 and fb["higher_levels_dice"] == "1d6" and fb["save_ability"] == "dex"


def test_magic_items():
    items = load("magic-items")["items"]
    assert len(items) >= 200
    for i in items:
        assert {"rarity", "requires_attunement", "category", "desc"} <= i.keys()
    mech = [i for i in items if i.get("charges") or i.get("bonuses") or i.get("granted_spells")]
    assert len(mech) >= 30
    targets = {"ac", "saves", "attack", "damage", "spell_attack", "spell_dc", "speed", "initiative"}
    for i in mech:
        for b in i.get("bonuses") or []:
            assert b["target"] in targets or b["target"].startswith("save.")
    w = next(i for i in items if i["index"] == "wand-of-magic-missiles")
    assert w["charges"]["max"] == 7


def test_equipment():
    items = load("equipment")["items"]
    weapons = [i for i in items if "damage_dice" in i]
    armor = [i for i in items if "ac_value" in i]
    assert len(weapons) == 37 and len(armor) == 13
    for w in weapons:
        assert set(w["properties"]) <= PROPS
        assert w["range_ft"] is None or isinstance(w["range_ft"], int)
    assert next(w for w in weapons if w["index"] == "longsword")["versatile_dice"] == "1d10"


def test_races():
    items = load("races")["items"]
    assert len(items) == 9
    for r in items:
        assert isinstance(r["speed_ft"], int) and "subraces" in r and "roll_notes" in r
    assert "en" in next(r for r in items if r["index"] == "dwarf")["roll_notes"]["poison_save"]


def test_background_feat_monsters():
    assert len(load("backgrounds")["items"]) >= 1
    assert [f["index"] for f in load("feats")["items"]] == ["grappler"]
    mons = load("monsters")["items"]
    assert len(mons) >= 300
    for m in mons:
        assert {"abilities", "speed", "actions", "traits", "challenge_rating", "xp"} <= m.keys()
        assert all(v is None or isinstance(v, int) for v in m["speed"].values())


DICE_RE = re.compile(r"^\d+d\d+([+-]\d+)?$|^\d+$")


def _all_dice():
    for s in load("spells")["items"]:
        yield s["index"], s["damage_dice"]
        yield s["index"], s["higher_levels_dice"]
    for w in load("equipment")["items"]:
        yield w["index"], w.get("damage_dice")
        yield w["index"], w.get("versatile_dice")
    for i in load("magic-items")["items"]:
        yield i["index"], (i["charges"] or {}).get("recharge_dice")
    for m in load("monsters")["items"]:
        for a in m["actions"]:
            yield m["index"], a["damage_dice"]


def test_dice_format_normalised():
    bad = [(k, d) for k, d in _all_dice() if d is not None and not DICE_RE.match(d)]
    assert not bad, bad


def test_curated_fixes():
    mi = {i["index"]: i for i in load("magic-items")["items"]}
    assert mi["staff-of-the-magi"]["charges"]["recharge_dice"] == "4d6+2"
    spells = {g["spell"]: g["charge_cost"] for g in mi["staff-of-power"]["granted_spells"]}
    assert spells["globe-of-invulnerability"] == 6
    assert mi["hammer-of-thunderbolts"]["requires_attunement"] is True


def test_higher_levels_and_thrown():
    sp = {s["index"]: s for s in load("spells")["items"]}
    for k, v in {"flame-strike": "1d6", "disintegrate": "3d6", "wall-of-fire": "1d8", "phantasmal-killer": "1d10"}.items():
        assert sp[k]["higher_levels_dice"] == v, k
    assert sp["disintegrate"]["damage_dice"] == "10d6+40"
    assert sp["spiritual-weapon"]["higher_levels_dice"] is None and sp["chain-lightning"]["higher_levels_dice"] is None
    eq = {e["index"]: e for e in load("equipment")["items"]}
    assert eq["dagger"]["thrown_range_ft"] == [20, 60] and eq["longsword"]["thrown_range_ft"] is None

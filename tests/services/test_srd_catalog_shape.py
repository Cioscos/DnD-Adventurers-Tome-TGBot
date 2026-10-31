"""Shape checks for the generated SRD catalogue (webapp/src/data/srd/*.json)."""
import json
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
    assert len(weapons) >= 30 and len(armor) >= 12
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

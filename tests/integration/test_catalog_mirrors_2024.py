import json

from core.rules.weapons import has_property, weapon_key, weapon_mastery
from scripts.export_catalogs_2024 import FILES, build_all


def test_catalogs_2024_mirror_up_to_date():
    for path, data in build_all().items():
        assert json.loads(path.read_text(encoding="utf-8")) == data, "uv run python -m scripts.export_catalogs_2024"


def test_equipment_2024_diffs():
    items = {e["index"]: e for e in build_all()[FILES["equipment"]]["items"]}
    assert "net" not in items
    assert items["lance"]["damage_dice"] == "1d10" and {"prop_heavy", "prop_two_handed", "prop_reach"} <= set(items["lance"]["properties"])
    assert (items["trident"]["damage_dice"], items["trident"]["versatile_dice"]) == ("1d8", "1d10")
    assert items["war-pick"]["versatile_dice"] == "1d10" and "prop_versatile" in items["war-pick"]["properties"]
    assert items["musket"]["damage_dice"] == "1d12" and items["musket"]["mastery"] == "slow" and items["musket"]["range_ft"] == 40
    assert items["pistol"]["damage_dice"] == "1d10" and items["pistol"]["mastery"] == "vex"


class _Item:
    def __init__(self, name, meta=None):
        self.name, self.item_metadata = name, meta or {}


def test_musket_pistol_weapon_keys():
    assert weapon_key(_Item("Moschetto")) == "musket"
    assert weapon_key(_Item("Pistol")) == "pistol"
    assert weapon_key(_Item("x", {"srd_index": "musket"})) == "musket"
    assert weapon_mastery(_Item("Moschetto")) == "slow" and weapon_mastery(_Item("Pistol")) == "vex"
    assert has_property(_Item("Moschetto", {"properties": ["prop_loading"]}), "loading")

"""Specie 2024 (Task 4): Aasimar, Elfo, Gnomo, Halfling, Umano, Tiefling. Valori da docs/superpowers/rules/2024/races.md."""
from __future__ import annotations

from core.data.species_2024 import SPECIES_2024, required_choices
from tests.integration.rules.test_2014_bard import _ability, _full, _roll_keys, _spells, _use
from tests.integration.rules.test_2014_fighter_styles import _item
from tests.integration.rules.test_2014_paladin import _hp, _hurt, _rest
from tests.integration.rules.test_species_2024_traits_a import _species

AASIMAR = "species.2024_aasimar_"
LUCK = "species.2024_halfling_luck"


async def _by_index(client, cid) -> dict[str, dict]:
    return {s["srd_index"]: s for s in (await _spells(client, cid)).values() if s.get("srd_index")}


async def _score(client, cid, ability, value) -> None:
    r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
    assert r.status_code == 200, r.text


async def _save(client, cid, ability, **body) -> dict:
    r = await client.post(f"/characters/{cid}/saving_throws/{ability}/roll", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_data_cover_the_six_species():
    assert set(SPECIES_2024) >= {f"2024_{k}" for k in ("aasimar", "elf", "gnome", "halfling", "human", "tiefling")}
    assert required_choices("2024_elf") == ("lineage", "spell_ability", "skill")
    assert required_choices("2024_tiefling") == ("size", "legacy", "spell_ability")
    assert required_choices("2024_human") == ("size", "skill", "origin_feat")
    assert required_choices("2024_halfling") == ()
    human = {c.key: c for c in SPECIES_2024["2024_human"].choices}
    assert len(human["skill"].options) == 18 and "2024_skilled" in human["origin_feat"].options
    assert "2024_actor" not in human["origin_feat"].options


async def test_human_heroic_inspiration_on_long_rest(client, test_session_factory):
    cid = await _species(client, test_session_factory, "2024_human", {"size": "medium", "skill": "athletics", "origin_feat": "2024_skilled"})
    assert (await _full(client, cid))["heroic_inspiration"] is False
    await _rest(client, cid, "long")
    assert (await _full(client, cid))["heroic_inspiration"] is True
    old = await _species(client, test_session_factory, "2024_human", edition="2014")
    await _rest(client, old, "long")
    assert (await _full(client, old))["heroic_inspiration"] is False


async def test_halfling_luck_rerolls_natural_one(client, test_session_factory):
    cid = await _species(client, test_session_factory, "2024_halfling")
    first = await _save(client, cid, "wisdom", die=1)
    assert LUCK in await _roll_keys(client, cid, "save", ability="wisdom")
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [LUCK], "dice": [15]})
    assert r.status_code == 200, r.text
    assert r.json()["die"] == 15 and r.json()["total"] == first["total"] + 14
    again = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [LUCK], "dice": [1]})
    assert again.status_code == 409  # il nuovo risultato resta
    await _save(client, cid, "wisdom", die=2)
    assert LUCK not in await _roll_keys(client, cid, "save", ability="wisdom")
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [LUCK], "dice": [15]})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable"


async def test_halfling_brave_and_elf_fey_ancestry_offer_advantage_on_saves(client, test_session_factory):
    halfling = await _species(client, test_session_factory, "2024_halfling")
    assert "species.2024_halfling_brave" in await _roll_keys(client, halfling, "save", ability="wisdom")
    elf = await _species(client, test_session_factory, "2024_elf", {"lineage": "high", "spell_ability": "intelligence", "skill": "insight"})
    assert "species.2024_elf_fey_ancestry" in await _roll_keys(client, elf, "save", ability="wisdom")


async def test_gnome_advantage_on_int_wis_cha_saves_only(client, test_session_factory):
    cid = await _species(client, test_session_factory, "2024_gnome", {"lineage": "rock", "spell_ability": "intelligence"})
    for ability in ("intelligence", "wisdom", "charisma"):
        assert (await _save(client, cid, ability, dice=[3, 15]))["mode_applied"] == "advantage"
    for ability in ("strength", "dexterity", "constitution"):
        assert (await _save(client, cid, ability, dice=[3]))["mode_applied"] != "advantage"
    spells = await _by_index(client, cid)
    assert {"mending", "prestidigitation"} <= set(spells)
    assert {"type": "darkvision", "range_ft": 60} in (await _full(client, cid))["computed"]["senses"]


async def test_forest_gnome_speaks_with_animals_pb_times(client, test_session_factory):
    cid = await _species(client, test_session_factory, "2024_gnome", {"lineage": "forest", "spell_ability": "wisdom"}, level=5)
    spells = await _by_index(client, cid)
    assert "minor-illusion" in spells and spells["speak-with-animals"]["pact_cast"]["uses_left"] == 3


async def test_elf_drow_spells_by_level_and_darkvision_120(client, test_session_factory):
    opts = {"lineage": "drow", "spell_ability": "charisma", "skill": "perception"}
    low = await _species(client, test_session_factory, "2024_elf", opts)
    spells = await _by_index(client, low)
    assert "dancing-lights" in spells and "faerie-fire" not in spells and "darkness" not in spells
    assert {"type": "darkvision", "range_ft": 120} in (await _full(client, low))["computed"]["senses"]

    cid = await _species(client, test_session_factory, "2024_elf", opts, level=5)
    await _score(client, cid, "charisma", 16)
    spells = await _by_index(client, cid)
    for key in ("faerie-fire", "darkness"):
        assert spells[key]["always_prepared"] and spells[key]["pact_cast"]["uses_left"] == 1
        assert spells[key]["save_dc"] == 8 + 3 + 3  # competenza 3, Carisma 16
    r = await client.post(f"/characters/{cid}/spells/{spells['darkness']['id']}/use", json={"free_cast": True})
    assert r.status_code == 200, r.text
    assert (await _by_index(client, cid))["darkness"]["pact_cast"]["uses_left"] == 0


async def test_wood_elf_speed_35(client, test_session_factory):
    cid = await _species(client, test_session_factory, "2024_elf", {"lineage": "wood", "spell_ability": "wisdom", "skill": "survival"})
    full = await _full(client, cid)
    assert full["computed"]["speed"] == 35
    assert {"type": "darkvision", "range_ft": 60} in full["computed"]["senses"]
    assert "druidcraft" in await _by_index(client, cid)


async def test_tiefling_infernal_resistance_and_spells(client, test_session_factory):
    opts = {"size": "medium", "legacy": "infernal", "spell_ability": "charisma"}
    cid = await _species(client, test_session_factory, "2024_tiefling", opts, level=3)
    full = await _full(client, cid)
    assert full["computed"]["resistances"] == ["fire"]
    spells = await _by_index(client, cid)
    assert {"fire-bolt", "thaumaturgy", "hellish-rebuke"} <= set(spells) and "darkness" not in spells
    assert spells["hellish-rebuke"]["pact_cast"]["uses_left"] == 1
    chthonic = await _species(client, test_session_factory, "2024_tiefling", {**opts, "legacy": "chthonic"}, level=5)
    assert (await _full(client, chthonic))["computed"]["resistances"] == ["necrotic"]
    assert {"chill-touch", "false-life", "ray-of-enfeeblement"} <= set(await _by_index(client, chthonic))


async def test_aasimar_healing_hands_rolls_pb_d4(client, test_session_factory):
    cid = await _species(client, test_session_factory, "2024_aasimar", {"size": "medium"}, level=5)
    row = await _ability(client, cid, AASIMAR + "healing_hands")
    assert (row["max_uses"], row["restoration_type"]) == (1, "long_rest")
    await _hurt(test_session_factory, cid, 1)
    r = await _use(client, cid, AASIMAR + "healing_hands", params={"mode": "self"})
    assert r.status_code == 200, r.text
    rolls = r.json()["rolls"]
    assert len(rolls) == 3 and all(1 <= x <= 4 for x in rolls)
    assert await _hp(client, cid) == 1 + sum(rolls)
    full = await _full(client, cid)
    assert sorted(full["computed"]["resistances"]) == ["necrotic", "radiant"]
    assert "light" in await _by_index(client, cid)


async def test_aasimar_celestial_revelation_wings_and_extra_damage(client, test_session_factory):
    low = await _species(client, test_session_factory, "2024_aasimar", {"size": "small"}, level=2)
    assert await _ability(client, low, AASIMAR + "celestial_revelation") is None
    cid = await _species(client, test_session_factory, "2024_aasimar", {"size": "medium"}, level=3)
    wid = await _item(client, cid, "Spada", damage_dice="1d8", weapon_type="melee", properties=[])
    assert AASIMAR + "revelation_damage" not in await _roll_keys(client, cid, "attack", item_id=wid)
    r = await _use(client, cid, AASIMAR + "celestial_revelation", params={"form": "wings"})
    assert r.status_code == 200, r.text
    full = await _full(client, cid)
    assert full["computed"]["fly_speed"] == full["computed"]["speed"]
    assert AASIMAR + "revelation_damage" in await _roll_keys(client, cid, "attack", item_id=wid)
    assert (await _ability(client, cid, AASIMAR + "celestial_revelation"))["uses"] == 0

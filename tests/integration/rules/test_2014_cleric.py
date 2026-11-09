"""Chierico 2014 (Task 21): progressione, Incanalare Divinità, Scacciare Non Morti, incantesimi e competenze di dominio,
Colpo Divino, Colpo Guidato, Sacerdote di Guerra, Lampo di Interdizione, Collera della Tempesta e gli altri privilegi
dei sette domini."""
from __future__ import annotations

import pytest

from core.rules.catalog import features_for
from core.rules.catalog.y2014.cleric import DOMAIN_SPELLS, destroy_threshold
from core.rules.proficiencies import class_proficiencies
from core.rules.spellcasting import known_limits, slots_for
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys, _spells, _states, _use

DOMAINS = {
    "knowledge": "Dominio della Conoscenza", "war": "Dominio della Guerra", "trickery": "Dominio dell'Inganno",
    "light": "Dominio della Luce", "nature": "Dominio della Natura", "tempest": "Dominio della Tempesta",
    "life": "Dominio della Vita",
}
POOL = "cleric.channel_divinity"
TURN = "cleric.turn_undead"


async def _cleric(client, level=5, domain=None, **scores) -> int:
    body = {"name": "Chierico", "initial_class": {"class_name": "cleric", "level": level, "subclass": DOMAINS.get(domain)}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for ability, value in scores.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    return cid


# ---------------------------------------------------------------------------
# Progressione e catalogo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,cantrips", [(1, 3), (3, 3), (4, 4), (9, 4), (10, 5), (20, 5)])
def test_cantrips_and_prepared_spells_follow_the_class_table(level, cantrips):
    assert known_limits("2014", "cleric", level).cantrips == cantrips


async def test_slots_and_prepared_cap_follow_wisdom_plus_level(client):
    cid = await _cleric(client, 5, wisdom=16)
    full = await _full(client, cid)
    assert {s["level"]: s["total"] for s in full["spell_slots"]} == {1: 4, 2: 3, 3: 2}
    assert full["spellcasting"]["prepared_cap"] == 3 + 5  # Saggezza 16 (+3) + livello


async def test_hit_points_use_the_d8_and_follow_constitution(client):
    cid = await _cleric(client, 3)
    full = await _full(client, cid)
    assert full["classes"][0]["hit_die"] == 8
    assert full["hit_points"] == 8 + 5 + 5  # 8 + COS al 1°, poi la media 5 (COS 10)


def test_class_proficiencies_first_class_and_multiclass():
    first = class_proficiencies("2014", "cleric", False)
    assert set(first.armor) == {"light", "medium", "shields"} and first.weapons == ("simple",)
    assert set(first.saves) == {"wisdom", "charisma"} and first.skills_count == 2
    multi = class_proficiencies("2014", "cleric", True)
    assert set(multi.armor) == {"light", "medium", "shields"} and not multi.weapons and not multi.saves


@pytest.mark.parametrize("level", [4, 8, 12, 16, 19])
async def test_asi_choice_is_pending_at_each_asi_level(client, level):
    cid = await _cleric(client, level)
    levels = sorted(c["level"] for c in (await _full(client, cid))["pending_choices"] if c["kind"] == "asi")
    assert levels == [lv for lv in (4, 8, 12, 16, 19) if lv <= level]


async def test_rules_only_rows_do_not_clutter_the_sheet(client):
    cid = await _cleric(client, 20, "life")
    keys = await _keys_of(client, cid)
    assert not keys & {f"cleric.{k}" for k in ("hit_points", "proficiencies", "equipment", "spellcasting", "divine_domain",
                                                "domain_spells", "ability_score_improvement", "multiclassing", "life_spells_3")}


def test_every_domain_has_its_spells_and_nothing_else_is_missing():
    assert set(DOMAIN_SPELLS) == set(DOMAINS) and all(len(t) == 5 and all(len(p) == 2 for p in t) for t in DOMAIN_SPELLS.values())
    keys = {f.key for f in features_for("2014", "cleric")}
    assert {f"cleric.{d}_spells" for d in DOMAINS} <= keys


# ---------------------------------------------------------------------------
# Incantesimi di dominio
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,tiers", [(1, 1), (2, 1), (3, 2), (5, 3), (7, 4), (9, 5), (20, 5)])
async def test_domain_spells_follow_the_level(client, level, tiers):
    cid = await _cleric(client, level, "life")
    spells = await _spells(client, cid)
    expected = {name for tier in DOMAIN_SPELLS["life"][:tiers] for name in tier}
    got = {s["srd_index"] for s in spells.values() if s.get("always_prepared")}
    assert got == expected
    assert all(s["is_prepared"] and s["class_id"] for s in spells.values() if s["srd_index"] in expected)


@pytest.mark.parametrize("domain", sorted(DOMAINS))
async def test_every_domain_grants_its_first_spells_as_always_prepared(client, domain):
    cid = await _cleric(client, 1, domain)
    got = {s["srd_index"] for s in (await _spells(client, cid)).values() if s.get("always_prepared")}
    assert got >= set(DOMAIN_SPELLS[domain][0])


async def test_domain_spells_do_not_count_against_the_prepared_cap(client):
    cid = await _cleric(client, 5, "life", wisdom=10)
    full = await _full(client, cid)
    assert full["spellcasting"]["prepared_count"] == 0  # i sei di dominio sono fuori dal limite


async def test_a_domain_that_changes_keeps_the_spells_as_normal_ones(client):
    cid = await _cleric(client, 3, "war")
    cls = (await _full(client, cid))["classes"][0]["id"]
    await client.patch(f"/characters/{cid}/classes/{cls}", json={"subclass": DOMAINS["life"]})
    spells = await _spells(client, cid)
    assert all(not s["always_prepared"] for s in spells.values() if s["srd_index"] in DOMAIN_SPELLS["war"][0])
    assert {"bless", "cure-wounds"} <= {s["srd_index"] for s in spells.values() if s["always_prepared"]}


async def test_nature_speak_with_animals_is_not_ritual_only(client):
    cid = await _cleric(client, 1, "nature")
    spell = next(s for s in (await _spells(client, cid)).values() if s["srd_index"] == "speak-with-animals")
    assert (await _full(client, cid))["spellcasting"]["ritual_only_spell_ids"] == []
    assert (await client.get(f"/characters/{cid}/spells/{spell['id']}/cast-check")).json() == []


# ---------------------------------------------------------------------------
# Competenze di dominio (D5)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("domain,armor,weapons", [
    ("war", True, True), ("tempest", True, True), ("nature", True, False), ("life", True, False),
    ("knowledge", False, False), ("trickery", False, False), ("light", False, False),
])
async def test_domain_proficiencies_are_always_granted(client, domain, armor, weapons):
    cid = await _cleric(client, 1, domain)
    got = (await _full(client, cid))["general_proficiencies"]
    assert ("Armature pesanti" in got["armor"]) is armor and ("Armi da guerra" in got["weapons"]) is weapons


# ---------------------------------------------------------------------------
# Incanalare Divinità e Scacciare Non Morti
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,uses", [(2, 1), (5, 1), (6, 2), (17, 2), (18, 3), (20, 3)])
async def test_channel_divinity_uses_follow_the_level(client, level, uses):
    cid = await _cleric(client, level)
    row = await _ability(client, cid, POOL)
    assert (row["max_uses"], row["restoration_type"]) == (uses, "short_rest")


async def test_channel_divinity_appears_at_level_2_only(client):
    assert POOL not in await _keys_of(client, await _cleric(client, 1))
    assert {POOL, TURN} <= await _keys_of(client, await _cleric(client, 2))


@pytest.mark.parametrize("level,cr", [(2, None), (4, None), (5, "1/2"), (7, "1/2"), (8, "1"), (11, "2"), (14, "3"), (17, "4"), (20, "4")])
def test_destroy_undead_threshold_follows_the_level(level, cr):
    assert destroy_threshold(level) == cr


async def test_turn_undead_spends_the_shared_pool_and_shows_dc_and_cr(client):
    cid = await _cleric(client, 8, wisdom=16)  # competenza +3, Saggezza +3
    r = await _use(client, cid, TURN)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["targets"] == [TURN]  # l'effetto su altri lo applica il giocatore dall'incontro (D1)
    assert body["state"]["data"]["dc"] == 8 + 3 + 3 and body["state"]["data"]["cr"] == "1"
    assert body["state"]["rounds_left"] == 10 and body["state"]["data"]["others"] == ["cleric.destroy_undead"]
    assert (await _ability(client, cid, POOL))["uses"] == 1 and len(await _states(client, cid)) == 1
    turn = (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]
    assert turn["action_used"] is True
    assert (await _use(client, cid, TURN)).status_code == 409  # l'azione è spesa


async def test_turn_undead_without_uses_is_refused_before_spending_the_action(client):
    cid = await _cleric(client, 2)
    assert (await _use(client, cid, TURN)).status_code == 200
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "action", "used": False})
    r = await _use(client, cid, TURN)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]["action_used"] is False


async def test_turn_undead_has_no_cr_before_level_5(client):
    cid = await _cleric(client, 3)
    assert "cr" not in (await _use(client, cid, TURN)).json()["state"]["data"]


async def test_short_rest_returns_the_channel_divinity_uses(client):
    cid = await _cleric(client, 6)
    await _use(client, cid, TURN)
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})
    assert (await _ability(client, cid, POOL))["uses"] == 2


# ---------------------------------------------------------------------------
# Sottoclasse riconosciuta e non
# ---------------------------------------------------------------------------

async def test_domain_features_need_a_recognised_domain(client):
    life = await _cleric(client, 8, "life")
    war = await _cleric(client, 8, "war")
    free = await _cleric(client, 8)
    assert "cleric.divine_strike_life" in {f.key for f in features_for("2014", "cleric")}
    assert "cleric.war_priest" in await _keys_of(client, war) and "cleric.war_priest" not in await _keys_of(client, life)
    assert not {k for k in await _keys_of(client, free) if k.split(".")[1] in ("war_priest", "warding_flare")}


# ---------------------------------------------------------------------------
# Colpo Divino
# ---------------------------------------------------------------------------

async def _sword(client, cid) -> int:
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Mazza", "item_type": "weapon", "weapon_type": "melee", "damage_dice": "1d6", "damage_type": "bludgeoning"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.mark.parametrize("domain", ["war", "trickery", "tempest", "life"])
async def test_divine_strike_is_offered_after_a_weapon_hit_at_level_8(client, domain):
    cid = await _cleric(client, 8, domain)
    item = await _sword(client, cid)
    assert f"cleric.divine_strike_{domain}" in await _roll_keys(client, cid, "attack", item_id=item)
    low = await _cleric(client, 7, domain)
    assert f"cleric.divine_strike_{domain}" not in await _roll_keys(client, low, "attack", item_id=await _sword(client, low))


async def test_divine_strike_nature_offers_one_option_per_damage_type(client):
    cid = await _cleric(client, 8, "nature")
    keys = await _roll_keys(client, cid, "attack", item_id=await _sword(client, cid))
    assert {f"cleric.divine_strike_nature_{t}" for t in ("cold", "lightning", "fire")} <= set(keys)


@pytest.mark.parametrize("level,dice", [(8, "1d8"), (13, "1d8"), (14, "2d8"), (20, "2d8")])
def test_divine_strike_dice_follow_the_level(level, dice):
    from core.rules.catalog.y2014.cleric import _strike_dice
    from core.rules.types import RuleContext
    assert _strike_dice(RuleContext(char=None, edition="2014", class_level=level), {}) == dice

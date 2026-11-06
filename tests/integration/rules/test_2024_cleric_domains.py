"""Chierico 2024 (Task 33, parte B): Domini della Vita, della Luce, dell'Inganno e della Guerra. Valori dalla scheda
``docs/superpowers/rules/2024/classes/cleric.md``."""
from __future__ import annotations

import pytest

from core.rules.catalog import features_for
from core.rules.catalog.granted_spells import GRANTED_SPELLS
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_barbarian import _attack, _turn, _weapon
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys, _states, _use
from tests.integration.rules.test_2014_bard_inspiration import _seat
from tests.integration.rules.test_2024_cleric import POOL, _paladin_pool_spec

DOMAINS = {"life": "Dominio della Vita", "light": "Dominio della Luce", "trickery": "Dominio dell'Inganno", "war": "Dominio della Guerra"}
SPELLS = {
    "life": (("aid", "bless", "cure-wounds", "lesser-restoration"), ("mass-healing-word", "revivify"), ("aura-of-life", "death-ward"),
             ("greater-restoration", "mass-cure-wounds")),
    "light": (("burning-hands", "faerie-fire", "scorching-ray", "see-invisibility"), ("daylight", "fireball"), ("arcane-eye", "wall-of-fire"),
              ("flame-strike", "scrying")),
    "trickery": (("charm-person", "disguise-self", "invisibility", "pass-without-trace"), ("hypnotic-pattern", "nondetection"),
                 ("confusion", "dimension-door"), ("dominate-person", "modify-memory")),
    "war": (("guiding-bolt", "magic-weapon", "shield-of-faith", "spiritual-weapon"), ("crusaders-mantle", "spirit-guardians"),
            ("fire-shield", "freedom-of-movement"), ("hold-monster", "steel-wind-strike")),
}


async def _dom(client, level=5, domain="life", **scores) -> int:
    body = {"name": "Chierico", "initial_class": {"class_name": "cleric", "level": level, "subclass": DOMAINS[domain]}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    for ability, value in scores.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    return cid


async def _table(client, factory, level=5, domain="life"):
    sid, hero = await seed_session(factory)
    as_user(GM_ID)
    cleric = await _dom(client, level, domain, wisdom=16)  # Saggezza +3
    await _seat(factory, cleric)
    return sid, cleric, hero


async def _spell_rows(client, cid) -> dict[str, dict]:
    return {s["srd_index"]: s for s in (await client.get(f"/characters/{cid}/spells")).json()}


async def _rest(client, cid, kind) -> None:
    await client.post(f"/characters/{cid}/rest", json={"rest_type": kind, **({"confirm_early": True} if kind == "long" else {})})


# ---------------------------------------------------------------------------
# Incantesimi di dominio (tutti e quattro)
# ---------------------------------------------------------------------------

def test_every_2024_domain_spell_has_data_to_be_granted():
    missing = {s for tiers in SPELLS.values() for tier in tiers for s in tier} - set(GRANTED_SPELLS)
    assert not missing


@pytest.mark.parametrize("domain", sorted(DOMAINS))
@pytest.mark.parametrize("level,tiers", [(2, 0), (3, 1), (4, 1), (5, 2), (7, 3), (9, 4), (20, 4)])
async def test_domain_spells_arrive_at_3_5_7_and_9_outside_the_prepared_cap(client, domain, level, tiers):
    cid = await _dom(client, level, domain)
    got = {k for k, s in (await _spell_rows(client, cid)).items() if s.get("always_prepared")}
    assert got == {s for tier in SPELLS[domain][:tiers] for s in tier}


@pytest.mark.parametrize("domain", sorted(DOMAINS))
async def test_every_domain_title_of_the_mapping_has_its_row(domain):
    titles = {f.source_title for f in features_for("2024", "cleric") if f.subclass == domain}
    assert any(t.startswith("Incantesimi del Dominio") for t in titles)
    assert len(titles) >= 5 or domain == "trickery"


# ---------------------------------------------------------------------------
# Dominio della Vita
# ---------------------------------------------------------------------------

async def test_disciple_of_life_adds_two_plus_the_slot_level_to_a_healing_spell(client):
    cid = await _dom(client, 3, "life")
    spell = (await _spell_rows(client, cid))["cure-wounds"]
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/roll_healing", json={"casting_level": 2})
    assert r.status_code == 200, r.text
    assert r.json()["bonus"] == 2 + 2


async def test_blessed_healer_is_offered_for_a_slot_healing_spell_from_level_6_only(client):
    high, low = await _dom(client, 6, "life"), await _dom(client, 5, "life")
    q = {"roll": "spell_healing", "casting_level": 1}
    assert "cleric.blessed_healer" in await _roll_keys(client, high, **q)
    assert "cleric.blessed_healer" not in await _roll_keys(client, low, **q)


async def test_supreme_healing_maximizes_the_dice_of_the_spark_without_spending_another_use(client, monkeypatch):
    monkeypatch.setattr("api.services.rules_states.random.randint", lambda a, b: 1)
    life, other = await _dom(client, 17, "life", wisdom=16), await _dom(client, 17, "war", wisdom=16)
    r = await _use(client, life, "cleric.divine_spark", params={"mode": "heal"})
    assert r.status_code == 200, r.text
    assert r.json()["given"] == 3 * 8 + 3 and r.json()["rolls"] == [8, 8, 8]  # 3d8 massimi + Saggezza
    assert (await _ability(client, life, POOL))["uses"] == 2  # 3 usi al 17°, uno solo speso
    r = await _use(client, other, "cleric.divine_spark", params={"mode": "heal"})
    assert r.json()["given"] == 3 * 1 + 3  # un altro dominio: i dadi si tirano
    low = await _dom(client, 16, "life", wisdom=16)
    assert (await _use(client, low, "cleric.divine_spark", params={"mode": "heal"})).json()["given"] == 3 * 1 + 3


async def test_supreme_healing_does_not_maximize_the_damage_mode(client, monkeypatch):
    monkeypatch.setattr("api.services.rules_states.random.randint", lambda a, b: 1)
    cid = await _dom(client, 17, "life", wisdom=16)
    r = await _use(client, cid, "cleric.divine_spark", params={"mode": "damage_radiant"})
    assert r.status_code == 200 and r.json()["rolls"] == [1, 1, 1]


async def test_supreme_healing_maximizes_the_healing_spell_dice(client):
    cid = await _dom(client, 17, "life")
    spell = (await _spell_rows(client, cid))["cure-wounds"]
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/roll_healing", json={"casting_level": 1})
    assert r.status_code == 200 and r.json()["maximized"] is True


async def _hp(client, cid, current, maximum=40) -> None:
    for body in ({"op": "set_max", "value": maximum}, {"op": "set_current", "value": current}):
        assert (await client.patch(f"/characters/{cid}/hp", json=body)).status_code == 200


async def test_preserve_life_heals_five_times_the_level_up_to_half_and_spends_the_pool(client, test_session_factory):
    sid, cleric, hero = await _table(client, test_session_factory, 5, "life")
    await _hp(client, cleric, 10)
    as_user(PLAYER_ID)
    await _hp(client, hero, 5)
    as_user(GM_ID)
    r = await client.post(f"/characters/{cleric}/preserve-life", json={
        "allocations": [{"character_id": cleric, "amount": 10}, {"character_id": hero, "amount": 15}], "confirm_living": True})
    assert r.status_code == 200, r.text
    assert r.json()["pool"] == 25
    over = await client.post(f"/characters/{cleric}/preserve-life", json={
        "allocations": [{"character_id": cleric, "amount": 11}], "confirm_living": True})
    assert over.status_code == 422  # mai oltre la metà dei PF massimi
    assert (await _ability(client, cleric, POOL))["uses"] == 1


@pytest.mark.parametrize("cleric_first", [True, False])
async def test_preserve_life_spends_the_shared_pool_in_both_multiclass_orders(client, cleric_first):
    from core.rules import catalog
    catalog._REGISTRY[("2024", "paladin")] = (_paladin_pool_spec(3),)
    try:
        first, second = ("cleric", "paladin") if cleric_first else ("paladin", "cleric")
        sub = [DOMAINS["life"] if c == "cleric" else None for c in (first, second)]
        r = await client.post("/characters", json={"name": "Mix", "initial_class": {"class_name": first, "level": 5, "subclass": sub[0]}})
        cid = r.json()["id"]
        assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
        r = await client.post(f"/characters/{cid}/classes", json={"class_name": second, "level": 5, "hit_die": 8, "subclass": sub[1]})
        assert r.status_code == 201, r.text
        await _hp(client, cid, 10)
        rows = [a for a in (await _full(client, cid))["abilities"] if a["feature_key"] in (POOL, "paladin.channel_divinity")]
        assert len(rows) == 1
        r = await client.post(f"/characters/{cid}/preserve-life", json={
            "allocations": [{"character_id": cid, "amount": 5}], "confirm_living": True})
        assert r.status_code == 200, r.text
        assert (await _ability(client, cid, POOL))["uses"] == rows[0]["max_uses"] - 1
    finally:
        catalog._REGISTRY.pop(("2024", "paladin"), None)


# ---------------------------------------------------------------------------
# Dominio della Luce
# ---------------------------------------------------------------------------

async def test_radiance_of_the_dawn_rolls_2d10_plus_level_with_the_constitution_save(client, monkeypatch):
    monkeypatch.setattr("api.services.rules_states.random.randint", lambda a, b: 5)
    cid = await _dom(client, 5, "light", wisdom=16)
    r = await _use(client, cid, "cleric.radiance_of_the_dawn")
    assert r.status_code == 200, r.text
    data = r.json()["state"]["data"]
    assert (data["save"], data["dc"], data["damage"], data["damage_type"]) == ("constitution", 8 + 3 + 3, 5 + 5 + 5, "radiant")
    assert (await _ability(client, cid, POOL))["uses"] == 1 and (await _turn(client, cid))["action_used"] is True


async def test_warding_flare_uses_follow_wisdom_and_are_a_reaction(client):
    for wis, uses in ((8, 1), (16, 3)):
        cid = await _dom(client, 3, "light", wisdom=wis)
        assert (await _ability(client, cid, "cleric.warding_flare"))["max_uses"] == uses
    r = await _use(client, cid, "cleric.warding_flare")
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["reaction_used"] is True and (await _ability(client, cid, "cleric.warding_flare"))["uses"] == 2


async def test_warding_flare_returns_on_a_short_rest_only_from_level_6(client):
    low, high = await _dom(client, 5, "light", wisdom=16), await _dom(client, 6, "light", wisdom=16)
    for cid in (low, high):
        await _use(client, cid, "cleric.warding_flare")
        await client.post(f"/characters/{cid}/turn/new")
        await _rest(client, cid, "short")
    assert (await _ability(client, low, "cleric.warding_flare"))["uses"] == 2
    assert (await _ability(client, high, "cleric.warding_flare"))["uses"] == 3


async def test_improved_warding_flare_shows_2d6_plus_wisdom_temporary_hp(client, monkeypatch):
    monkeypatch.setattr("api.services.rules_states.random.randint", lambda a, b: 4)
    low, high = await _dom(client, 5, "light", wisdom=16), await _dom(client, 6, "light", wisdom=16)
    assert (await _use(client, low, "cleric.warding_flare")).json()["given"] == 0
    r = await _use(client, high, "cleric.warding_flare")
    assert r.json()["given"] == 4 + 4 + 3 and (await _full(client, high))["temp_hp"] == 0  # all'attaccante, non a te


async def test_corona_of_light_is_a_ten_round_state_ended_without_an_action(client):
    cid = await _dom(client, 17, "light", wisdom=16)
    assert (await _ability(client, cid, "cleric.corona_of_light"))["max_uses"] == 3
    r = await _use(client, cid, "cleric.corona_of_light")
    assert r.status_code == 200, r.text
    assert r.json()["state"]["rounds_left"] == 10 and r.json()["state"].get("end_slot") is None
    assert (await _ability(client, cid, "cleric.corona_of_light"))["uses"] == 2
    assert "cleric.corona_of_light" not in await _keys_of(client, await _dom(client, 16, "light"))


# ---------------------------------------------------------------------------
# Dominio dell'Inganno
# ---------------------------------------------------------------------------

async def test_blessing_of_the_trickster_on_yourself_gives_advantage_on_stealth_until_a_long_rest(client):
    cid = await _dom(client, 3, "trickery")
    assert "trickster:advantage" not in await _roll_keys(client, cid, "skill", skill="stealth")
    r = await _use(client, cid, "cleric.blessing_of_the_trickster", params={"self": True})
    assert r.status_code == 200, r.text
    assert "trickster:advantage" in await _roll_keys(client, cid, "skill", skill="stealth")
    assert "trickster:advantage" not in await _roll_keys(client, cid, "skill", skill="athletics")
    assert (await _states(client, cid))[0]["rounds_left"] is None
    await _rest(client, cid, "long")
    assert "trickster:advantage" not in await _roll_keys(client, cid, "skill", skill="stealth")


async def test_blessing_of_the_trickster_on_an_ally_replaces_the_previous_one(client, test_session_factory):
    sid, cleric, hero = await _table(client, test_session_factory, 3, "trickery")
    r = await _use(client, cleric, "cleric.blessing_of_the_trickster", params={"target_character_id": hero})
    assert r.status_code == 200, r.text
    as_user(PLAYER_ID)
    assert "trickster:advantage" in await _roll_keys(client, hero, "skill", skill="stealth")
    as_user(GM_ID)
    await client.post(f"/characters/{cleric}/turn/new")
    assert (await _use(client, cleric, "cleric.blessing_of_the_trickster", params={"self": True})).status_code == 200
    as_user(PLAYER_ID)
    assert "trickster:advantage" not in await _roll_keys(client, hero, "skill", skill="stealth")


async def test_invoke_duplicity_is_a_bonus_action_that_spends_the_pool_without_concentration(client):
    cid = await _dom(client, 3, "trickery")
    assert not (await _full(client, cid))["concentrating_spell_id"]
    r = await _use(client, cid, "cleric.invoke_duplicity")
    assert r.status_code == 200, r.text
    state = r.json()["state"]
    assert state["rounds_left"] == 10 and "incapacitated" in state["ends_on"] and "concentration_end" not in state["ends_on"]
    assert (await _turn(client, cid))["bonus_used"] is True and (await _ability(client, cid, POOL))["uses"] == 1
    assert "cleric.invoke_duplicity_move" in await _keys_of(client, cid)
    again = await _use(client, cid, "cleric.invoke_duplicity")
    assert again.status_code == 409  # già attivo (e azione bonus usata)


async def test_moving_the_duplicate_needs_it_and_costs_the_bonus_action_only(client):
    cid = await _dom(client, 3, "trickery")
    assert (await _use(client, cid, "cleric.invoke_duplicity_move")).status_code == 409
    await _use(client, cid, "cleric.invoke_duplicity")
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _use(client, cid, "cleric.invoke_duplicity_move")).status_code == 200
    assert (await _ability(client, cid, POOL))["uses"] == 1


async def test_duplicity_gives_advantage_to_attacks_only_while_it_lasts(client):
    cid = await _dom(client, 3, "trickery", strength=14)
    sword = await _weapon(client, cid, "Mazza", damage_dice="1d6")
    assert "cleric.duplicity_advantage" not in await _roll_keys(client, cid, "attack", item_id=sword)
    await _use(client, cid, "cleric.invoke_duplicity")
    assert "cleric.duplicity_advantage" in await _roll_keys(client, cid, "attack", item_id=sword)


async def test_the_duplicate_ends_when_the_cleric_is_incapacitated(client):
    cid = await _dom(client, 3, "trickery")
    await _use(client, cid, "cleric.invoke_duplicity")
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"incapacitated": True}})
    assert r.status_code == 200, r.text
    assert not [s for s in await _states(client, cid) if s["key"] == "invoke_duplicity"]


async def test_trickster_transposition_is_text_only(client):
    spec = next(f for f in features_for("2024", "cleric") if f.source_title.startswith("Trasposizione dell'Ingannatore"))
    assert spec.passive and spec.on_use is None and spec.level == 6



async def test_improved_duplicity_ends_the_illusion_and_heals_the_cleric_by_level(client):
    cid = await _dom(client, 17, "trickery")
    await _hp(client, cid, 10, 200)
    assert (await _use(client, cid, "cleric.improved_duplicity", params={"mode": "self"})).status_code == 409  # senza illusione
    await _use(client, cid, "cleric.invoke_duplicity")
    state = next(s for s in await _states(client, cid) if s["key"] == "invoke_duplicity")
    assert "cleric.improved_duplicity" in state["data"]["others"]  # vantaggio condiviso, per GM e gruppo
    r = await _use(client, cid, "cleric.improved_duplicity", params={"mode": "self"})
    assert r.status_code == 200, r.text
    assert r.json()["healed"] == 17 and (await _full(client, cid))["current_hit_points"] == 27
    assert not [s for s in await _states(client, cid) if s["key"] == "invoke_duplicity"]


# ---------------------------------------------------------------------------
# Dominio della Guerra
# ---------------------------------------------------------------------------

async def test_war_priest_attacks_as_a_bonus_action_without_a_previous_attack_and_recovers_on_a_short_rest(client):
    cid = await _dom(client, 3, "war", strength=14, wisdom=16)
    sword = await _weapon(client, cid, "Mazza", damage_dice="1d6")
    assert (await _ability(client, cid, "cleric.war_priest"))["max_uses"] == 3
    assert "cleric.war_priest" in await _roll_keys(client, cid, "attack", item_id=sword)  # nessun obbligo di aver attaccato
    await _attack(client, cid, sword, die=12, options=["cleric.war_priest"])
    assert (await _turn(client, cid))["bonus_used"] is True and (await _ability(client, cid, "cleric.war_priest"))["uses"] == 2
    await _rest(client, cid, "short")
    assert (await _ability(client, cid, "cleric.war_priest"))["uses"] == 3


async def test_guided_strike_adds_ten_after_the_roll_and_spends_the_pool(client):
    cid = await _dom(client, 3, "war", strength=14)
    sword = await _weapon(client, cid, "Mazza", damage_dice="1d6")
    first = (await client.post(f"/characters/{cid}/items/{sword}/attack", json={"die": 5, "defer_damage": True})).json()
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": ["cleric.guided_strike"]})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == first["to_hit_total"] + 10
    assert (await _ability(client, cid, POOL))["uses"] == 1


async def test_guided_strike_for_another_creature_is_a_reaction_that_spends_the_pool(client):
    cid = await _dom(client, 3, "war")
    r = await _use(client, cid, "cleric.guided_strike")
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["reaction_used"] is True and (await _ability(client, cid, POOL))["uses"] == 1
    assert r.json()["message"]["it"]


@pytest.mark.parametrize("spell,concentration", [("shield-of-faith", True), ("spiritual-weapon", False)])
async def test_war_gods_blessing_casts_the_spell_free_without_concentration_for_a_minute(client, spell, concentration):
    cid = await _dom(client, 6, "war")
    r = await _use(client, cid, "cleric.war_gods_blessing", params={"spell": spell})
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, POOL))["uses"] == 2 and (await _turn(client, cid))["bonus_used"] is False
    row = (await _spell_rows(client, cid))[spell]
    slots = [(s["total"], s["used"]) for s in (await _full(client, cid))["spell_slots"]]
    r = await client.post(f"/characters/{cid}/spells/{row['id']}/use", json={"free_cast": True})
    assert r.status_code == 200, r.text
    assert [(s["total"], s["used"]) for s in (await _full(client, cid))["spell_slots"]] == slots  # nessuno slot
    full = await _full(client, cid)
    assert not full["concentrating_spell_id"]
    assert (await _turn(client, cid))["bonus_used"] is True
    state = next(s for s in full["active_states"] if s["key"] == "war_gods_blessing")
    assert state["rounds_left"] == 10 and "incapacitated" in state["ends_on"] and state["data"]["spell"] == spell
    again = await client.post(f"/characters/{cid}/spells/{row['id']}/use", json={"free_cast": True})
    assert again.status_code == 409  # l'autorizzazione si chiude col lancio


async def test_war_gods_blessing_refuses_other_spells_and_needs_a_use(client):
    cid = await _dom(client, 6, "war")
    for params in ({"spell": "fireball"}, {}):
        r = await _use(client, cid, "cleric.war_gods_blessing", params=params)
        assert r.status_code == 422, r.text
    assert (await _ability(client, cid, POOL))["uses"] == 3


async def test_a_normal_cast_of_shield_of_faith_still_needs_concentration(client):
    cid = await _dom(client, 6, "war")
    row = (await _spell_rows(client, cid))["shield-of-faith"]
    assert (await client.post(f"/characters/{cid}/spells/{row['id']}/use", json={"slot_level": 1})).status_code == 200
    assert (await _full(client, cid))["concentrating_spell_id"] == row["id"]


async def test_avatar_of_battle_gives_resistance_to_physical_damage_from_level_17(client):
    cid = await _dom(client, 17, "war")
    hp = (await _full(client, cid))["current_hit_points"]
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": "slashing"})).status_code == 200
    assert (await _full(client, cid))["current_hit_points"] == hp - 5
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": "fire"})).status_code == 200
    assert (await _full(client, cid))["current_hit_points"] == hp - 15
    low = await _dom(client, 16, "war")
    hp = (await _full(client, low))["current_hit_points"]
    await client.patch(f"/characters/{low}/hp", json={"op": "damage", "value": 10, "damage_type": "slashing"})
    assert (await _full(client, low))["current_hit_points"] == hp - 10


# ---------------------------------------------------------------------------
# Sottoclasse riconosciuta contro non riconosciuta, e passaggio di edizione
# ---------------------------------------------------------------------------

async def test_an_unrecognized_subclass_gets_no_domain_rows_and_a_recognized_one_only_its_own(client):
    r = await client.post("/characters", json={"name": "X", "initial_class": {"class_name": "cleric", "level": 17, "subclass": "Boh"}})
    cid = r.json()["id"]
    await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})
    keys = await _keys_of(client, cid)
    assert not keys & {"cleric.preserve_life", "cleric.corona_of_light", "cleric.guided_strike"}
    war = await _keys_of(client, await _dom(client, 17, "war"))
    assert "cleric.guided_strike" in war and not war & {"cleric.preserve_life", "cleric.corona_of_light", "cleric.invoke_duplicity"}


async def test_the_2014_life_cleric_keeps_its_spent_pool_when_it_becomes_2024(client):
    r = await client.post("/characters", json={"name": "V", "initial_class": {"class_name": "cleric", "level": 5, "subclass": DOMAINS["life"]}})
    cid = r.json()["id"]
    assert (await _use(client, cid, "cleric.preserve_life")).status_code == 409  # pannello
    await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})
    keys = await _keys_of(client, cid)
    assert {"cleric.preserve_life", "cleric.disciple_of_life", POOL} <= keys
    assert "cleric.life_bonus_proficiency" not in keys  # riga solo 2014 (Competenza Bonus)

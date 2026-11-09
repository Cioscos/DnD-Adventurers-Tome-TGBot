"""Warlock 2024, giro di correzione 2 (Task 41, I7): Dono dei Protettori sugli alleati (R42) e Investitura del Padrone delle Catene.
Nessun d20 casuale: i dadi dei tiri per colpire sono passati dal test."""
from __future__ import annotations

from sqlalchemy import select

from core.db.models import Character, CharacterHistory, SessionParticipant
from tests.integration._encounter_helpers import GM_ID, as_user, seed_session
from tests.integration.rules.test_2014_barbarian import _turn
from tests.integration.rules.test_2014_bard import _ability, _full, _use
from tests.integration.rules.test_2024_warlock import TOME, _caster24

GIFT = "warlock.gift_of_the_protectors"
CHAIN = "pact_of_the_chain"
MASTER = "investment_of_the_chain_master"


# --- Dono dei Protettori sugli alleati (R42) --------------------------------------------------------------------------

async def _table(client, factory, hero_hp=0):
    """Una serata con un warlock del Tomo (GM, livello 9) e un eroe: `(warlock, hero)`."""
    _, hero = await seed_session(factory)
    as_user(GM_ID)
    cid = await _caster24(client, 9, TOME, "gift_of_the_protectors")
    async with factory() as s:
        part = (await s.execute(select(SessionParticipant).where(SessionParticipant.user_id == GM_ID))).scalar_one()
        part.character_id = cid
        char = await s.get(Character, hero)
        char.hit_points, char.current_hit_points = 40, hero_hp
        await s.commit()
    return cid, hero


def _gift(client, cid):
    return _use(client, cid, GIFT, params={})


async def test_gift_of_the_protectors_use_is_a_text_outcome_for_a_non_player_creature_and_spends_the_use(client, test_session_factory):
    # Sui PG della serata il Dono scatta dal danno (test_2024_warlock_gift_ally); «Usa» resta per le altre creature
    cid, _ = await _table(client, test_session_factory)
    r = await _gift(client, cid)
    assert r.status_code == 200, r.text
    assert r.json()["received"] is None and r.json()["notes"] == ["gift_of_the_protectors_other"]
    assert (await _ability(client, cid, GIFT))["uses"] == 0
    assert (await _gift(client, cid)).status_code == 409  # una volta fino al riposo lungo


# --- Investitura del Padrone delle Catene -----------------------------------------------------------------------------

BITE = {"name": "Morso", "attack_bonus": 4, "damage_dice": "1d4", "damage_type": "piercing"}
BURN = {"name": "Fiamma", "attack_bonus": 4, "damage_dice": "1d4", "damage_type": "fire"}


async def _familiar(client, cid, kind="familiar") -> dict:
    r = await client.post(f"/characters/{cid}/companions", json={
        "kind": kind, "name": "Imp", "max_hp": 20, "armor_class": 13, "statblock": {"actions": [BITE, BURN]}})
    assert r.status_code == 201, r.text
    return r.json()


async def _chain(client, with_master=True) -> tuple[int, dict]:
    cid = await _caster24(client, 5, CHAIN, *([MASTER] if with_master else []), charisma=16)
    return cid, await _familiar(client, cid)


async def test_the_familiar_of_a_warlock_with_the_investment_gets_the_derived_statistics(client):
    cid, fam = await _chain(client)
    assert fam["save_dc"] == 14 and fam["fly_or_swim_m"] == 12  # 8 + competenza 3 + Carisma 3
    assert fam["damage_type_options"] == ["necrotic", "radiant"] and fam["can_resist"] is True
    listed = (await client.get(f"/characters/{cid}/companions")).json()[0]
    assert listed["save_dc"] == 14
    other = await _familiar(client, cid, kind="companion")  # un compagno qualunque non è il famiglio
    assert other["save_dc"] is None and other["fly_or_swim_m"] == 0 and other["damage_type_options"] == []


async def test_the_statistics_follow_the_warlocks_charisma_and_need_the_invocation(client):
    cid, fam = await _chain(client)
    assert (await client.patch(f"/characters/{cid}/ability_scores/charisma", json={"value": 20})).status_code == 200
    assert (await client.get(f"/characters/{cid}/companions")).json()[0]["save_dc"] == 16
    _, plain = await _chain(client, with_master=False)
    assert plain["save_dc"] is None and plain["fly_or_swim_m"] == 0 and plain["can_resist"] is False


async def test_the_bonus_action_attack_deals_necrotic_or_radiant_instead_of_physical_damage(client):
    cid, fam = await _chain(client)
    url = f"/characters/{cid}/companions/{fam['id']}/attack"
    r = await client.post(url, json={"action_index": 0, "dice": [12], "bonus": True, "damage_type": "radiant", "damage_rolls": [3]})
    assert r.status_code == 200, r.text
    assert r.json()["damage_type"] == "radiant" and r.json()["damage_total"] == 3
    assert (await _turn(client, cid))["bonus_used"] is True
    again = await client.post(url, json={"action_index": 0, "dice": [12], "bonus": True})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "turn_slot_used"


async def test_only_physical_damage_can_be_turned_into_necrotic_or_radiant(client):
    cid, fam = await _chain(client)
    r = await client.post(f"/characters/{cid}/companions/{fam['id']}/attack",
                          json={"action_index": 1, "dice": [12], "damage_type": "necrotic"})
    assert r.status_code == 422
    assert (await _turn(client, cid))["bonus_used"] is False


async def test_without_the_investment_the_familiar_cannot_attack_on_the_bonus_action_or_change_the_damage_type(client):
    cid, fam = await _chain(client, with_master=False)
    url = f"/characters/{cid}/companions/{fam['id']}/attack"
    for extra in ({"bonus": True}, {"damage_type": "necrotic"}):
        r = await client.post(url, json={"action_index": 0, "dice": [12], **extra})
        assert r.status_code == 409 and r.json()["detail"]["code"] == "feature_unavailable"
    assert (await _turn(client, cid))["bonus_used"] is False


async def test_the_reaction_gives_the_familiar_resistance_to_the_damage_and_is_spent_once(client):
    cid, fam = await _chain(client)
    url = f"/characters/{cid}/companions/{fam['id']}/hp"
    r = await client.patch(url, json={"op": "damage", "value": 9, "resist": True})
    assert r.status_code == 200, r.text
    assert r.json()["current_hp"] == 16  # 9 dimezzato per difetto = 4
    assert (await _turn(client, cid))["reaction_used"] is True
    again = await client.patch(url, json={"op": "damage", "value": 9, "resist": True})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "turn_slot_used"
    plain = await client.patch(url, json={"op": "damage", "value": 9})  # senza reazione il danno è intero
    assert plain.json()["current_hp"] == 7


async def test_the_resistance_needs_the_investment_and_only_applies_to_damage(client):
    cid, fam = await _chain(client, with_master=False)
    r = await client.patch(f"/characters/{cid}/companions/{fam['id']}/hp", json={"op": "damage", "value": 8, "resist": True})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "feature_unavailable"
    assert (await _turn(client, cid))["reaction_used"] is False
    cid2, fam2 = await _chain(client)
    r = await client.patch(f"/characters/{cid2}/companions/{fam2['id']}/hp", json={"op": "heal", "value": 3, "resist": True})
    assert r.status_code == 409

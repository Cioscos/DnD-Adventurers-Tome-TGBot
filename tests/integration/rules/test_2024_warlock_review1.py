"""Warlock 2024, giro di correzione 1 (Task 41, I1-I7 e M6). Nessun d20 casuale: i dadi del server sono fissati."""
from __future__ import annotations

import json

from sqlalchemy import select

from core.db.models import Character, SessionParticipant
from core.rules.catalog import features_for
from tests.integration._encounter_helpers import GM_ID, as_user, seed_session
from tests.integration.rules.test_2014_barbarian import _weapon
from tests.integration.rules.test_2014_bard import _ability, _full, _use
from tests.integration.rules.test_2014_fighter_eldritch_knight import _hit
from tests.integration.rules.test_2014_paladin import _new_turn, _rest
from tests.integration.rules.test_2014_warlock import _choice, _resolve
from tests.integration.rules.test_2024_warlock import BLADE, TOME, _blade, _caster24, _offered, _warlock24
from tests.integration.rules.test_2024_warlock_patrons import _effect, _hp, _make

P = "warlock."
VENGEANCE = P + "searing_vengeance"
VENGEANCE_SAVE = P + "searing_vengeance_save"
HURL = P + "hurl_through_hell"
GIFT = P + "gift_of_the_protectors"


def _meta(item: dict) -> dict:
    meta = item["item_metadata"]
    return json.loads(meta) if isinstance(meta, str) else meta


# --- I1: il livello delle suppliche lo controlla il server ---------------------------------------------------------

async def test_at_level_one_only_the_five_level_one_invocations_are_offered_and_the_others_are_refused(client):
    cid = await _warlock24(client, 1)
    assert await _offered(client, cid) == {"armor_of_shadows", "eldritch_mind", "pact_of_the_blade", "pact_of_the_chain", "pact_of_the_tome"}
    for key in ("devils_sight", "fiendish_vigor", "lessons_of_the_first_ones", "mask_of_many_faces", "misty_visions", "otherworldly_leap"):
        assert (await _resolve(client, cid, "invocations", [key])).status_code == 422, key


# --- I3 e M6 ----------------------------------------------------------------------------------------------------------

async def test_hurl_through_hell_incapacitates_until_the_end_of_the_warlocks_next_turn(client):
    cid = await _make(client, "fiend", 14, charisma=18)
    sword = await _weapon(client, cid, "Spada", "main_hand", damage_dice="1d8")
    hit = await _hit(client, cid, sword)
    r = await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={"options": [HURL]})
    assert r.status_code == 200, r.text
    assert (await _effect(client, cid, HURL))["ends_at"] == {"anchor": "source", "edge": "end", "count": 1}
    assert "tuo prossimo turno" in r.json()["option_result"]["effects"][0]["it"]


def test_healing_light_and_awakened_mind_are_bonus_actions_for_the_turn_page():
    rows = {f.key.split(".")[-1]: f for f in features_for("2024", "warlock")}
    assert rows["healing_light"].action_type == "bonus_action" and rows["awakened_mind"].action_type == "bonus_action"


# --- I2: Vendetta Ardente a 0 PF ------------------------------------------------------------------------------------

async def test_searing_vengeance_is_usable_from_the_turn_page_at_zero_hp_and_offered_before_the_death_save(client):
    cid = await _make(client, "celestial", 14, charisma=16)
    await _hp(client, cid, op="set_max", value=80)
    assert VENGEANCE not in (await _full(client, cid))["computed"]["surprise_exit_features"]
    await _hp(client, cid, op="set_current", value=0)
    assert VENGEANCE in (await _full(client, cid))["computed"]["surprise_exit_features"]  # fuori dal fieldset spento
    options = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "death_save"})).json()
    assert VENGEANCE_SAVE in [o["key"] for o in options]
    r = await client.post(f"/characters/{cid}/death_saves/roll", json={"die": 4, "options": [VENGEANCE_SAVE]})
    assert r.status_code == 200, r.text
    assert r.json()["outcome"] == "revived" and r.json()["revived"] is True and r.json()["failures"] == 0
    assert (await _full(client, cid))["current_hit_points"] == 40
    assert (await _ability(client, cid, VENGEANCE))["uses"] == 0
    assert (await _effect(client, cid, VENGEANCE_SAVE))["condition"] == "blinded"
    again = await client.get(f"/characters/{cid}/roll-options", params={"roll": "death_save"})
    assert VENGEANCE_SAVE not in [o["key"] for o in again.json()]


async def test_searing_vengeance_for_a_seated_ally_brings_them_to_half_their_maximum(client, test_session_factory):
    _, hero = await seed_session(test_session_factory)
    as_user(GM_ID)
    cid = await _make(client, "celestial", 14)
    async with test_session_factory() as s:
        part = (await s.execute(select(SessionParticipant).where(SessionParticipant.user_id == GM_ID))).scalar_one()
        part.character_id = cid
        char = await s.get(Character, hero)
        char.hit_points, char.current_hit_points = 40, 0
        await s.commit()
    before = (await _full(client, cid))["current_hit_points"]
    r = await _use(client, cid, VENGEANCE, params={"mode": "ally", "target_character_id": hero})
    assert r.status_code == 200, r.text
    assert r.json()["received"] == {"name": "Eroe", "healed": 20}
    async with test_session_factory() as s:
        assert (await s.get(Character, hero)).current_hit_points == 20
    assert (await _full(client, cid))["current_hit_points"] == before and (await _ability(client, cid, VENGEANCE))["uses"] == 0


# --- I4: Succhiavita spende il Dado Vita e cura nello stesso uso ---------------------------------------------------

async def test_lifedrinker_spends_a_hit_die_and_heals_the_roll_plus_constitution_in_the_same_use(client, monkeypatch):
    cid = await _caster24(client, 9, BLADE, "lifedrinker", charisma=16, constitution=14)
    blade = await _blade(client, cid)
    await _hp(client, cid, op="set_current", value=10)
    used = (await _full(client, cid))["classes"][0]["hit_dice_used"] or 0
    monkeypatch.setattr("random.randint", lambda _a, b: min(5, b))
    hit = await _hit(client, cid, blade)
    r = await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={"options": [P + "lifedrinker_necrotic_hd"]})
    assert r.status_code == 200, r.text
    assert r.json()["self_healed"] == 5 + 2
    full = await _full(client, cid)
    assert full["current_hit_points"] == 17 and full["classes"][0]["hit_dice_used"] == used + 1


async def test_lifedrinker_without_the_hit_die_option_does_not_touch_the_hit_dice(client):
    cid = await _caster24(client, 9, BLADE, "lifedrinker")
    blade = await _blade(client, cid)
    hit = await _hit(client, cid, blade)
    r = await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={"options": [P + "lifedrinker_radiant"]})
    assert r.status_code == 200 and r.json().get("self_healed", 0) == 0
    assert (await _full(client, cid))["classes"][0]["hit_dice_used"] in (0, None)


# --- I5: il Patto della Lama si lega a un'arma magica ---------------------------------------------------------------

async def test_the_blade_can_bind_a_magic_weapon_already_owned_and_use_charisma_with_it(client):
    cid = await _caster24(client, 3, BLADE, charisma=18, strength=10, dexterity=10)
    magic = await _weapon(client, cid, "Spada +1", "main_hand", magic_bonus=1)
    plain = await _weapon(client, cid, "Ascia", None)
    assert (await _use(client, cid, P + BLADE, params={"weapon": f"bind:{plain}"})).status_code == 422  # non è magica
    assert (await _use(client, cid, P + BLADE, params={"weapon": f"bind:{magic}"})).status_code == 200
    items = {i["id"]: i for i in (await _full(client, cid))["items"]}
    assert magic in items and _meta(items[magic])["pact_weapon"] is True and items[magic]["is_equipped"]
    r = await client.post(f"/characters/{cid}/items/{magic}/attack", json={"die": 12, "confirm_extra_attack": True})
    assert r.status_code == 200, r.text
    assert r.json()["damage_bonus"] >= 4  # Carisma 18 (+4), non Forza 10 (0)


async def test_conjuring_a_new_pact_weapon_releases_the_bound_one_without_deleting_it(client):
    cid = await _caster24(client, 3, BLADE, charisma=18)
    magic = await _weapon(client, cid, "Spada +1", "main_hand", magic_bonus=1, damage_type="slashing")
    assert (await _use(client, cid, P + BLADE, params={"weapon": f"bind:{magic}", "damage_type": "radiant"})).status_code == 200
    await _new_turn(client, cid)
    assert (await _use(client, cid, P + BLADE, params={"weapon": "longsword"})).status_code == 200
    items = {i["id"]: i for i in (await _full(client, cid))["items"]}
    assert magic in items and not _meta(items[magic]).get("pact_weapon") and _meta(items[magic])["damage_type"] == "slashing"
    assert any("del patto" in i["name"] for i in items.values())


# --- I6: le scelte del Tomo si rifanno al riposo --------------------------------------------------------------------

async def _tome_spells(client, cid) -> list[str]:
    cantrips = _choice(await _full(client, cid), "tome_cantrips")
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Trucchetto altrui", "level": 0, "pick_id": cantrips["id"]})
    assert r.status_code == 201, r.text
    rituals = _choice(await _full(client, cid), "tome_rituals")
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Rituale altrui", "level": 1, "is_ritual": True, "pick_id": rituals["id"]})
    assert r.status_code == 201, r.text
    return [s["name"] for s in (await _full(client, cid))["spells"]]


async def test_the_tome_choices_can_be_redone_at_a_long_rest_only_when_asked(client):
    cid = await _caster24(client, 3, TOME)
    names = await _tome_spells(client, cid)
    assert any(a["feature_key"] == "warlock.pact_of_the_tome" for a in (await _full(client, cid))["abilities"])  # il pulsante del riposo lo cerca
    assert {"Trucchetto altrui", "Rituale altrui"} <= set(names)
    await _rest(client, cid, "long")  # senza richiesta non si perde nulla
    assert "Trucchetto altrui" in [s["name"] for s in (await _full(client, cid))["spells"]]
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True, "reopen_tome": True})
    assert r.status_code == 200, r.text
    full = await _full(client, cid)
    assert not {"Trucchetto altrui", "Rituale altrui"} & {s["name"] for s in full["spells"]}
    assert _choice(full, "tome_cantrips")["count"] == 3 and _choice(full, "tome_rituals")["count"] == 2


async def test_reopening_the_tome_without_the_pact_is_refused(client):
    cid = await _caster24(client, 3)
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True, "reopen_tome": True})
    assert r.status_code == 422


# --- I7: Dono dei Protettori ---------------------------------------------------------------------------------------

async def test_gift_of_the_protectors_keeps_me_at_one_hp_once_until_a_long_rest(client):
    cid = await _caster24(client, 9, TOME, "gift_of_the_protectors")
    await _hp(client, cid, op="set_max", value=50)
    await _hp(client, cid, op="set_current", value=20)
    keys = [o["key"] for o in (await client.get(f"/characters/{cid}/roll-options", params={"roll": "damage_taken"})).json()]
    assert GIFT in keys
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 30, "options": [GIFT]})
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["current_hit_points"] == 1 and (await _ability(client, cid, GIFT))["uses"] == 0
    await _hp(client, cid, op="set_current", value=20)
    keys = [o["key"] for o in (await client.get(f"/characters/{cid}/roll-options", params={"roll": "damage_taken"})).json()]
    assert GIFT not in keys


async def test_t10_78_the_blade_binds_only_weapons_that_are_really_magic_not_ones_with_a_rarity_or_charges(client):
    cid = await _caster24(client, 3, BLADE, charisma=18)
    odd = [await _weapon(client, cid, "Strana", None, rarity="rare"), await _weapon(client, cid, "Verga", None, charges={"current": 3, "max": 3})]
    for item in odd:
        assert (await _use(client, cid, P + BLADE, params={"weapon": f"bind:{item}"})).status_code == 422, item
    marked = await _weapon(client, cid, "Spada magica", None, is_magic=True)
    assert (await _use(client, cid, P + BLADE, params={"weapon": f"bind:{marked}"})).status_code == 200

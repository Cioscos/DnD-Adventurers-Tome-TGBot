"""Guerriero 2014 (Task 23): lo Stile di Combattimento, scelto e applicato alla scheda (CA, tiri per colpire, danni)."""
from __future__ import annotations

import pytest

from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _use
from tests.integration.rules.test_2014_fighter import _attack, _fighter, _turn

STYLES = ("archery", "defense", "dueling", "great_weapon", "two_weapon", "protection")
PROTECTION = "fighter.style_protection"


def _pending(full: dict) -> dict | None:
    return next((c for c in full["pending_choices"] if c.get("group") == "fighting_style"), None)


async def _choose(client, cid, *styles: str):
    choice = _pending(await _full(client, cid))
    return await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve",
                             json={"kind": "class_option", "options": list(styles)})


async def _styled(client, style, level=3, subclass=None, **scores) -> int:
    cid = await _fighter(client, level, subclass, **scores)
    r = await _choose(client, cid, style)
    assert r.status_code == 200, r.text
    return cid


async def _item(client, cid, name, item_type="weapon", equip=None, **meta) -> int:
    body = {"name": name, "item_type": item_type, "item_metadata": meta}
    r = await client.post(f"/characters/{cid}/items", json=body)
    assert r.status_code == 201, r.text
    iid = max(i["id"] for i in r.json()["items"])
    if equip:
        r = await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": True, "equipment_slot": equip})
        assert r.status_code == 200, r.text
    return iid


def _sword(client, cid, **kw):
    return _item(client, cid, "Spada", damage_dice="1d8", weapon_type="melee", properties=[], **kw)


# ---------------------------------------------------------------------------
# La scelta
# ---------------------------------------------------------------------------

async def test_the_style_is_a_choice_made_at_level_1(client):
    cid = await _fighter(client, 1)
    choice = _pending(await _full(client, cid))
    assert choice["count"] == 1 and {o["key"] for o in choice["options"]} == {f"{s}" for s in STYLES}
    assert all(o["name"]["it"] and o["name"]["en"] and o["summary"]["it"] for o in choice["options"])


async def test_a_character_born_above_level_1_is_asked_for_the_style_too(client):
    assert _pending(await _full(client, await _fighter(client, 9, "battle_master"))) is not None


async def test_the_chosen_style_becomes_a_row_of_the_sheet_and_the_choice_closes(client):
    cid = await _styled(client, "dueling")
    assert "fighter.style_dueling" in await _keys_of(client, cid) and _pending(await _full(client, cid)) is None
    assert not {f"fighter.style_{s}" for s in STYLES if s != "dueling"} & await _keys_of(client, cid)


@pytest.mark.parametrize("options", [[], ["archery", "defense"], ["nothing"]])
async def test_exactly_one_known_style_is_taken(client, options):
    cid = await _fighter(client, 3)
    assert (await _choose(client, cid, *options)).status_code == 422
    assert _pending(await _full(client, cid)) is not None


async def test_the_champion_second_style_excludes_the_first_and_gives_two_rows(client):
    cid = await _fighter(client, 10, "champion")
    assert (await _choose(client, cid, "archery", "archery")).status_code == 422
    assert (await _choose(client, cid, "archery", "defense")).status_code == 200
    assert {"fighter.style_archery", "fighter.style_defense"} <= await _keys_of(client, cid)
    assert _pending(await _full(client, cid)) is None


async def test_the_second_style_asked_at_level_10_leaves_out_the_first(client):
    cid = await _styled(client, "archery", level=9, subclass="champion")
    klass = (await _full(client, cid))["classes"][0]
    await client.patch(f"/characters/{cid}/classes/{klass['id']}", json={"level": 10})
    choice = _pending(await _full(client, cid))
    assert choice["count"] == 1 and "archery" not in {o["key"] for o in choice["options"]}


# ---------------------------------------------------------------------------
# Tiro
# ---------------------------------------------------------------------------

async def test_archery_adds_two_to_attacks_with_ranged_weapons_only(client):
    cid = await _fighter(client, 3, dexterity=14)
    bow = await _item(client, cid, "Arco lungo", damage_dice="1d8", weapon_type="ranged", properties=["ammunition"])
    sword = await _sword(client, cid)
    axe = await _item(client, cid, "Accetta", damage_dice="1d6", weapon_type="melee", properties=["thrown"])
    before = {w: (await _attack(client, cid, w, confirm_extra_attack=True)).json()["to_hit_bonus"] for w in (bow, sword)}
    before_axe = (await _attack(client, cid, axe, confirm_extra_attack=True, attack_mode="thrown")).json()["to_hit_bonus"]
    assert (await _choose(client, cid, "archery")).status_code == 200
    after = {w: (await _attack(client, cid, w, confirm_extra_attack=True)).json() for w in (bow, sword)}
    assert after[bow]["to_hit_bonus"] == before[bow] + 2 and "feature:fighter.style_archery" in after[bow]["notes"]
    assert after[sword]["to_hit_bonus"] == before[sword]
    assert (await _attack(client, cid, axe, confirm_extra_attack=True, attack_mode="thrown")).json()["to_hit_bonus"] == before_axe


async def test_archery_does_not_touch_a_spell_attack(client):
    cid = await _fighter(client, 3)
    spell = (await client.post(f"/characters/{cid}/spells", json={"name": "Raggio", "level": 0, "attack_save": "ATK"})).json()["id"]
    before = (await client.post(f"/characters/{cid}/spells/{spell}/attack", json={"die": 10})).json()["to_hit_total"]
    await _choose(client, cid, "archery")
    assert (await client.post(f"/characters/{cid}/spells/{spell}/attack", json={"die": 10})).json()["to_hit_total"] == before


# ---------------------------------------------------------------------------
# Difesa
# ---------------------------------------------------------------------------

async def _ac(client, cid) -> int:
    return (await _full(client, cid))["ac"]


async def test_defense_adds_one_to_ac_only_while_wearing_armor(client):
    cid = await _fighter(client, 3)
    await _item(client, cid, "Cuoio", "armor", armor_type="light", ac_value=11)
    plain = await _ac(client, cid)
    await _choose(client, cid, "defense")
    assert await _ac(client, cid) == plain  # l'armatura non è indossata
    iid = next(i["id"] for i in (await _full(client, cid))["items"] if i["name"] == "Cuoio")
    await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": True, "equipment_slot": "body"})
    worn = await _ac(client, cid)
    full = await _full(client, cid)
    assert full["ac_breakdown"]["rules"] == 1 and worn >= plain + 1
    await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": False})
    assert (await _full(client, cid))["ac_breakdown"]["rules"] == 0


async def test_defense_is_not_given_by_a_shield_alone(client):
    cid = await _styled(client, "defense")
    await _item(client, cid, "Scudo", "shield", equip="off_hand", ac_bonus=2)
    assert (await _full(client, cid))["ac_breakdown"]["rules"] == 0


async def test_defense_counts_in_the_session_ac_too(client, test_session_factory):
    sid, cid = await seed_session(test_session_factory)
    as_user(PLAYER_ID)
    await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 3, "hit_die": 10})
    await _choose(client, cid, "defense")
    await _item(client, cid, "Cuoio", "armor", equip="body", armor_type="light", ac_value=11)
    ac = (await _full(client, cid))["ac"]
    as_user(GM_ID)
    live = (await client.get(f"/sessions/{sid}/live")).json()
    assert next(c for c in live["live_characters"] if c["id"] == cid)["ac"] == ac


# ---------------------------------------------------------------------------
# Duellare
# ---------------------------------------------------------------------------

async def _damage_bonus(client, cid, wid, **body) -> int:
    r = await _attack(client, cid, wid, confirm_extra_attack=True, **body)
    assert r.status_code == 200, r.text
    return r.json()["damage_bonus"]


async def test_dueling_adds_two_to_a_one_handed_melee_weapon_alone_in_hand(client):
    cid = await _fighter(client, 3)
    wid = await _sword(client, cid, equip="main_hand")
    plain = await _damage_bonus(client, cid, wid)
    await _choose(client, cid, "dueling")
    assert await _damage_bonus(client, cid, wid) == plain + 2


async def test_dueling_works_with_a_shield_in_the_other_hand(client):
    cid = await _fighter(client, 3)
    wid = await _sword(client, cid, equip="main_hand")
    await _item(client, cid, "Scudo", "shield", equip="off_hand", ac_bonus=2)
    plain = await _damage_bonus(client, cid, wid)
    await _choose(client, cid, "dueling")
    assert await _damage_bonus(client, cid, wid) == plain + 2


async def test_dueling_does_not_work_with_another_weapon_in_hand(client):
    cid = await _fighter(client, 3)
    wid = await _sword(client, cid, equip="main_hand")
    plain = await _damage_bonus(client, cid, wid)
    await _item(client, cid, "Pugnale", damage_dice="1d4", weapon_type="melee", properties=["light"], equip="off_hand")
    await _choose(client, cid, "dueling")
    assert await _damage_bonus(client, cid, wid) == plain


async def test_dueling_does_not_work_with_a_two_handed_weapon_a_versatile_one_held_with_two_hands_or_ranged(client):
    cid = await _fighter(client, 3)
    great = await _item(client, cid, "Spadone", damage_dice="2d6", weapon_type="melee", properties=["heavy", "two-handed"])
    versatile = await _item(client, cid, "Spada lunga", damage_dice="1d8", weapon_type="melee", properties=["versatile"],
                            versatile_dice="1d10")
    bow = await _item(client, cid, "Arco", damage_dice="1d8", weapon_type="ranged", properties=["ammunition"])
    axe = await _item(client, cid, "Accetta", damage_dice="1d6", weapon_type="melee", properties=["thrown"])
    plain = {
        "great": await _damage_bonus(client, cid, great), "two": await _damage_bonus(client, cid, versatile, grip="two"),
        "one": await _damage_bonus(client, cid, versatile), "bow": await _damage_bonus(client, cid, bow),
        "axe": await _damage_bonus(client, cid, axe, attack_mode="thrown")}
    await _choose(client, cid, "dueling")
    assert await _damage_bonus(client, cid, great) == plain["great"]
    assert await _damage_bonus(client, cid, versatile, grip="two") == plain["two"]
    assert await _damage_bonus(client, cid, versatile) == plain["one"] + 2  # una mano, nessun'altra arma
    assert await _damage_bonus(client, cid, bow) == plain["bow"]
    assert await _damage_bonus(client, cid, axe, attack_mode="thrown") == plain["axe"]


# ---------------------------------------------------------------------------
# Combattere con Armi Possenti
# ---------------------------------------------------------------------------

def _dice(monkeypatch, *values):
    it = iter(values)
    monkeypatch.setattr("api.routers.items.random.randint", lambda a, b: next(it))


async def _greatsword(client, cid) -> int:
    return await _item(client, cid, "Spadone", damage_dice="2d6", weapon_type="melee", properties=["heavy", "two-handed"])


async def test_great_weapon_rerolls_a_one_or_a_two_once_and_shows_it(client, monkeypatch):
    cid = await _styled(client, "great_weapon", strength=10)
    wid = await _greatsword(client, cid)
    _dice(monkeypatch, 1, 6, 4)  # il 1 si ritira e dà 4
    body = (await _attack(client, cid, wid, confirm_extra_attack=True)).json()
    assert body["damage_rolls"] == [4, 6] and body["rerolled"] == [[1, 4]] and body["damage_total"] == 10


async def test_great_weapon_keeps_a_new_result_even_if_it_is_still_low(client, monkeypatch):
    cid = await _styled(client, "great_weapon", strength=10)
    wid = await _greatsword(client, cid)
    _dice(monkeypatch, 2, 2, 1, 2)
    body = (await _attack(client, cid, wid, confirm_extra_attack=True)).json()
    assert body["damage_rolls"] == [1, 2] and body["rerolled"] == [[2, 1], [2, 2]]


async def test_great_weapon_rerolls_every_die_of_a_critical(client, monkeypatch):
    cid = await _styled(client, "great_weapon", strength=10)
    wid = await _greatsword(client, cid)
    _dice(monkeypatch, 1, 6, 2, 5, 4, 3)
    body = (await _attack(client, cid, wid, die=20, confirm_extra_attack=True)).json()
    assert body["damage_rolls"] == [4, 6, 3, 5] and body["rerolled"] == [[1, 4], [2, 3]]


async def test_great_weapon_is_for_melee_weapons_held_with_two_hands(client, monkeypatch):
    cid = await _styled(client, "great_weapon", strength=10)
    sword = await _sword(client, cid)
    bow = await _item(client, cid, "Arco", damage_dice="1d8", weapon_type="ranged", properties=["ammunition"])
    versatile = await _item(client, cid, "Spada lunga", damage_dice="1d8", weapon_type="melee", properties=["versatile"],
                            versatile_dice="1d10")
    _dice(monkeypatch, 1)
    assert (await _attack(client, cid, sword, confirm_extra_attack=True)).json().get("rerolled") is None
    _dice(monkeypatch, 1)
    assert (await _attack(client, cid, bow, confirm_extra_attack=True)).json().get("rerolled") is None
    _dice(monkeypatch, 1)
    assert (await _attack(client, cid, versatile, confirm_extra_attack=True)).json().get("rerolled") is None
    _dice(monkeypatch, 1, 3)
    body = (await _attack(client, cid, versatile, confirm_extra_attack=True, grip="two")).json()
    assert body["rerolled"] == [[1, 3]]


# ---------------------------------------------------------------------------
# Combattere con Due Armi
# ---------------------------------------------------------------------------

async def _pair(client, cid) -> tuple[int, int]:
    main = await _item(client, cid, "Spada corta", damage_dice="1d6", weapon_type="melee", properties=["light"], equip="main_hand")
    off = await _item(client, cid, "Pugnale", damage_dice="1d4", weapon_type="melee", properties=["light"], equip="off_hand")
    return main, off


async def test_two_weapon_fighting_adds_the_modifier_to_the_second_attack(client):
    cid = await _fighter(client, 3, strength=16)
    main, off = await _pair(client, cid)
    plain = (await _attack(client, cid, off, attack_mode="offhand")).json()["damage_bonus"]
    await _choose(client, cid, "two_weapon")
    await client.post(f"/characters/{cid}/turn/new")  # l'attacco con l'altra mano costa l'azione bonus
    styled = (await _attack(client, cid, off, attack_mode="offhand")).json()["damage_bonus"]
    first = (await _attack(client, cid, main)).json()["damage_bonus"]
    assert plain == 0 and styled == first == 3


async def test_two_weapon_fighting_keeps_a_negative_modifier(client):
    cid = await _styled(client, "two_weapon", strength=8)
    main, off = await _pair(client, cid)
    assert (await _attack(client, cid, off, attack_mode="offhand")).json()["damage_bonus"] == -1


async def test_two_weapon_fighting_changes_nothing_for_the_main_attack(client):
    cid = await _fighter(client, 3, strength=16)
    main, off = await _pair(client, cid)
    plain = (await _attack(client, cid, main)).json()["damage_bonus"]
    await _choose(client, cid, "two_weapon")
    assert (await _attack(client, cid, main, confirm_extra_attack=True)).json()["damage_bonus"] == plain


# ---------------------------------------------------------------------------
# Protezione
# ---------------------------------------------------------------------------

async def test_protection_is_a_reaction_usable_only_with_a_shield(client):
    cid = await _styled(client, "protection")
    r = await _use(client, cid, PROTECTION)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "feature_unavailable"
    assert (await _turn(client, cid))["reaction_used"] is False
    await _item(client, cid, "Scudo", "shield", equip="off_hand", ac_bonus=2)
    ok = await _use(client, cid, PROTECTION)
    assert ok.status_code == 200 and ok.json()["targets"] == [PROTECTION]
    assert (await _turn(client, cid))["reaction_used"] is True
    again = await _use(client, cid, PROTECTION)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "turn_slot_used"


async def test_protection_is_not_usable_without_the_style(client):
    cid = await _fighter(client, 3)
    await _item(client, cid, "Scudo", "shield", equip="off_hand", ac_bonus=2)
    assert (await _use(client, cid, PROTECTION)).status_code == 404


async def test_protection_effect_says_disadvantage_on_the_attacker_for_the_gm(client, test_session_factory):
    sid, cid = await seed_session(test_session_factory)
    as_user(PLAYER_ID)
    await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 3, "hit_die": 10})
    await _choose(client, cid, "protection")
    await _item(client, cid, "Scudo", "shield", equip="off_hand", ac_bonus=2)
    as_user(GM_ID)
    await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})
    enc = (await client.post(f"/sessions/{sid}/encounter/combatants",
                             json={"name": "Orco", "count": 1, "initiative_mod": 0, "max_hp": 15, "ac": 13})).json()
    orc = next(c for c in enc["combatants"] if c["kind"] == "monster")["id"]
    await client.post(f"/sessions/{sid}/encounter/combatants/{orc}/initiative", json={"die": 10})
    pc = next(c for c in enc["combatants"] if c["kind"] == "pc")["id"]
    as_user(PLAYER_ID)
    await client.post(f"/sessions/{sid}/encounter/combatants/{pc}/initiative", json={"die": 15})
    as_user(GM_ID)
    await client.post(f"/sessions/{sid}/encounter/start", json={})
    as_user(PLAYER_ID)
    assert (await _use(client, cid, PROTECTION)).status_code == 200
    r = await client.post(f"/characters/{cid}/target-effects", json={"effect_key": PROTECTION, "combatant_id": orc})
    assert r.status_code == 200, r.text
    assert r.json()["applied"] is True and r.json()["result"]["condition"] == "custom:protection"
    as_user(GM_ID)
    live = (await client.get(f"/sessions/{sid}/live")).json()["encounter"]
    assert next(c for c in live["combatants"] if c["id"] == orc)["conditions"].get("custom:protection")

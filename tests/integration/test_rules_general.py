"""Regole generali restanti per edizione (Task 17, D7 e D8)."""
from __future__ import annotations

import pytest

from core.data.damage_types import apply_damage_mode, damage_multiplier
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session


async def _char(client, edition="2014", cls="fighter", level=1) -> int:
    r = await client.post("/characters", json={"name": "Prova"})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": cls, "level": level, "hit_die": 10})
    assert r.status_code == 201, r.text
    if edition != "2014":
        r = await client.patch(f"/characters/{cid}", json={"rules_edition": edition})
        assert r.status_code == 200, r.text
    return cid


async def _hp(client, cid, op, value, **extra) -> dict:
    r = await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": value, **extra})
    assert r.status_code == 200, r.text
    return r.json()


async def _full(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


# --- Danni: resistenza e vulnerabilità ---------------------------------------------------------------------------

def test_resistance_then_vulnerability():
    mods = {"resistances": ["fire"], "vulnerabilities": ["fire"]}
    mode = damage_multiplier(mods, "fire")
    assert mode == "half_double"
    assert apply_damage_mode(25, mode) == 24  # prima la metà per difetto (12), poi il doppio
    assert apply_damage_mode(25, "half") == 12 and apply_damage_mode(25, "double") == 50
    assert apply_damage_mode(25, "immune") == 0 and apply_damage_mode(25, "none") == 25


async def test_resistance_then_vulnerability_on_the_sheet(client):
    cid = await _char(client)
    await _hp(client, cid, "set_max", 60)
    await _hp(client, cid, "set_current", 60)
    r = await client.patch(f"/characters/{cid}", json={
        "damage_modifiers": {"resistances": ["fire"], "vulnerabilities": ["fire"]}})
    assert r.status_code == 200, r.text
    body = await _hp(client, cid, "damage", 25, damage_type="fire")
    assert body["current_hit_points"] == 60 - 24


# --- Privo di sensi a 0 PF ---------------------------------------------------------------------------------------

async def test_zero_hp_sets_unconscious_and_clears_on_heal(client):
    cid = await _char(client)
    await _hp(client, cid, "set_max", 20)
    await _hp(client, cid, "set_current", 20)
    body = await _hp(client, cid, "damage", 25)  # 5 oltre: non è morte istantanea
    assert body["current_hit_points"] == 0 and not body["is_dead"]
    assert body["conditions"]["unconscious"] and body["conditions"]["prone"]
    body = await _hp(client, cid, "heal", 4)
    assert body["current_hit_points"] == 4
    assert not body["conditions"].get("unconscious")
    assert body["conditions"]["prone"]  # ci si rialza spendendo movimento: resta finché non lo si dice


async def test_zero_hp_instant_death_does_not_set_unconscious(client):
    cid = await _char(client)
    await _hp(client, cid, "set_max", 10)
    await _hp(client, cid, "set_current", 10)
    body = await _hp(client, cid, "damage", 30)
    assert body["is_dead"] and not body["conditions"].get("unconscious")


async def test_set_current_to_zero_and_back_toggles_unconscious(client):
    cid = await _char(client)
    await _hp(client, cid, "set_max", 12)
    body = await _hp(client, cid, "set_current", 0)
    assert body["conditions"]["unconscious"]
    body = await _hp(client, cid, "set_current", 6)
    assert not body["conditions"].get("unconscious")


async def test_death_save_natural_twenty_wakes_up(client):
    cid = await _char(client)
    await _hp(client, cid, "set_max", 12)
    await _hp(client, cid, "set_current", 0)
    assert (await _full(client, cid))["conditions"]["unconscious"]
    r = await client.post(f"/characters/{cid}/death_saves/roll", json={"die": 20})
    assert r.status_code == 200, r.text
    assert not (await _full(client, cid))["conditions"].get("unconscious")


async def test_hp_undo_restores_conditions(client):
    cid = await _char(client)
    await _hp(client, cid, "set_max", 20)
    await _hp(client, cid, "set_current", 20)
    body = await _hp(client, cid, "damage", 25)
    assert body["conditions"]["unconscious"]
    r = await client.post(f"/characters/{cid}/hp/undo", json={"op_id": body["hp_undo_id"]})
    assert r.status_code == 200, r.text
    assert r.json()["current_hit_points"] == 20
    assert not r.json()["conditions"].get("unconscious") and not r.json()["conditions"].get("prone")


# --- Mettere fuori combattimento ---------------------------------------------------------------------------------

@pytest.mark.parametrize("edition,hp,stable", [("2014", 0, True), ("2024", 1, False)])
async def test_knock_out_by_edition(client, edition, hp, stable):
    cid = await _char(client, edition=edition)
    await _hp(client, cid, "set_max", 20)
    await _hp(client, cid, "set_current", 20)
    body = await _hp(client, cid, "damage", 25, knock_out=True)
    assert body["current_hit_points"] == hp and not body["is_dead"]
    assert body["conditions"]["unconscious"]
    assert body["death_saves"]["stable"] is stable
    assert body["death_saves"]["failures"] == 0


async def test_knock_out_does_not_save_from_massive_damage(client):
    cid = await _char(client)
    await _hp(client, cid, "set_max", 10)
    await _hp(client, cid, "set_current", 10)
    assert (await _hp(client, cid, "damage", 30, knock_out=True))["is_dead"]


async def test_knock_out_2024_ends_with_healing(client):
    cid = await _char(client, edition="2024")
    await _hp(client, cid, "set_max", 20)
    await _hp(client, cid, "set_current", 20)
    await _hp(client, cid, "damage", 25, knock_out=True)
    body = await _hp(client, cid, "heal", 1)
    assert not body["conditions"].get("unconscious")


async def test_knock_out_2024_ends_with_a_short_rest_and_manual_removal(client):
    cid = await _char(client, edition="2024")
    await _hp(client, cid, "set_max", 20)
    await _hp(client, cid, "set_current", 20)
    await _hp(client, cid, "damage", 25, knock_out=True)
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})
    assert r.status_code == 200, r.text
    assert not r.json()["conditions"].get("unconscious")
    await _hp(client, cid, "damage", 25, knock_out=True)
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"unconscious": False}})
    assert r.status_code == 200, r.text
    # tolta a mano: un sonno successivo non viene sciolto dal riposo
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"unconscious": True}})
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})
    assert r.json()["conditions"]["unconscious"]


async def test_knock_out_undo_restores_the_state(client):
    cid = await _char(client, edition="2024")
    await _hp(client, cid, "set_max", 20)
    await _hp(client, cid, "set_current", 20)
    body = await _hp(client, cid, "damage", 25, knock_out=True)
    r = await client.post(f"/characters/{cid}/hp/undo", json={"op_id": body["hp_undo_id"]})
    assert r.status_code == 200, r.text
    assert r.json()["current_hit_points"] == 20 and not r.json()["conditions"].get("unconscious")
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})
    assert r.status_code == 200, r.text


# --- Armatura: Forza richiesta e Furtività -----------------------------------------------------------------------

async def _wear(client, cid, **meta) -> None:
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Piastre", "item_type": "armor", "is_equipped": True,
        "item_metadata": {"armor_type": "heavy", "ac_value": 18, **meta}})
    assert r.status_code == 201, r.text


@pytest.mark.parametrize("edition", ["2014", "2024"])
async def test_armor_strength_requirement_cuts_ten_feet(client, edition):
    cid = await _char(client, edition=edition)  # il guerriero è addestrato alle armature pesanti
    clean = (await _full(client, cid))["computed"]["speed"]
    await _wear(client, cid, strength_req="15")  # Forza di base 10
    assert (await _full(client, cid))["computed"]["speed"] == clean - 10


async def test_armor_strength_requirement_met_or_absent_changes_nothing(client):
    cid = await _char(client)
    clean = (await _full(client, cid))["computed"]["speed"]
    await _wear(client, cid, strength_req="0")
    assert (await _full(client, cid))["computed"]["speed"] == clean
    await client.patch(f"/characters/{cid}/ability_scores/strength", json={"value": 16})
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Cotta", "item_type": "armor", "is_equipped": True,
        "item_metadata": {"armor_type": "heavy", "ac_value": 16, "strength_req": 13}})
    assert r.status_code == 201, r.text
    assert (await _full(client, cid))["computed"]["speed"] == clean


async def test_stealth_disadvantage_only_on_stealth_checks_even_if_trained(client):
    cid = await _char(client)
    await _wear(client, cid, stealth_disadvantage=True)
    r = await client.post(f"/characters/{cid}/skills/stealth/roll")
    assert r.status_code == 200, r.text
    assert r.json()["mode_applied"] == "disadvantage" and "armor:stealth" in r.json()["notes"]
    r = await client.post(f"/characters/{cid}/skills/athletics/roll")
    assert r.json()["mode_applied"] == "normal"


# --- Sorpresa (D7) -----------------------------------------------------------------------------------------------

async def _surprise_setup(client, factory, edition):
    from core.db.models import Character
    sid, cid = await seed_session(factory)
    async with factory() as s:
        (await s.get(Character, cid)).rules_edition = edition
        await s.commit()
    as_user(GM_ID)
    r = await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})
    assert r.status_code == 201, r.text
    pc = next(c for c in r.json()["combatants"] if c["kind"] == "pc")
    r = await client.post(f"/sessions/{sid}/encounter/combatants",
                          json={"name": "Goblin", "count": 1, "initiative_mod": 0, "max_hp": 7, "ac": 13})
    monster = next(c for c in r.json()["combatants"] if c["kind"] == "monster")
    return sid, cid, pc, monster


async def _surprise(client, sid, comb_id, value=True):
    as_user(GM_ID)
    r = await client.patch(f"/sessions/{sid}/encounter/combatants/{comb_id}", json={"surprised": value})
    assert r.status_code == 200, r.text
    return next(c for c in r.json()["combatants"] if c["id"] == comb_id)


async def test_surprise_flag_is_set_by_the_gm_only(client, test_session_factory):
    sid, cid, pc, monster = await _surprise_setup(client, test_session_factory, "2014")
    assert pc["surprised"] is False
    assert (await _surprise(client, sid, monster["id"]))["surprised"] is True
    as_user(PLAYER_ID)
    r = await client.patch(f"/sessions/{sid}/encounter/combatants/{pc['id']}", json={"surprised": True})
    assert r.status_code == 403


async def test_surprise_2024_gives_disadvantage_on_initiative(client, test_session_factory, monkeypatch):
    import random
    sid, cid, pc, monster = await _surprise_setup(client, test_session_factory, "2024")
    await _surprise(client, sid, pc["id"])
    monkeypatch.setattr(random, "randint", lambda a, b: 4)
    as_user(PLAYER_ID)
    r = await client.post(f"/sessions/{sid}/encounter/combatants/{pc['id']}/initiative", json={"die": 15})
    assert r.status_code == 200, r.text
    assert r.json()["initiative_roll"]["mode_applied"] == "disadvantage"
    assert "condition:surprised" in r.json()["initiative_roll"]["notes"]
    row = next(c for c in r.json()["combatants"] if c["id"] == pc["id"])
    assert row["initiative_die"] == 4  # il server ha aggiunto un secondo dado e tenuto il più basso


async def test_surprise_2014_does_not_touch_initiative(client, test_session_factory):
    sid, cid, pc, monster = await _surprise_setup(client, test_session_factory, "2014")
    await _surprise(client, sid, pc["id"])
    as_user(PLAYER_ID)
    r = await client.post(f"/sessions/{sid}/encounter/combatants/{pc['id']}/initiative", json={"die": 15})
    assert r.json()["initiative_roll"]["mode_applied"] == "normal"


async def _me(client, cid) -> dict:
    as_user(PLAYER_ID)
    r = await client.get(f"/characters/{cid}")
    assert r.status_code == 200, r.text
    as_user(GM_ID)
    return r.json()["computed"]


async def _start(client, sid, pc, monster, pc_die, monster_die):
    as_user(PLAYER_ID)
    await client.post(f"/sessions/{sid}/encounter/combatants/{pc['id']}/initiative", json={"die": pc_die})
    as_user(GM_ID)
    await client.post(f"/sessions/{sid}/encounter/combatants/{monster['id']}/initiative", json={"die": monster_die})
    r = await client.post(f"/sessions/{sid}/encounter/start", json={})
    assert r.status_code == 200, r.text
    return r.json()


async def test_surprise_2014_skips_turn_2024_disadvantage_for_character(client, test_session_factory):
    sid, cid, pc, monster = await _surprise_setup(client, test_session_factory, "2014")
    await _surprise(client, sid, pc["id"])
    enc = await _start(client, sid, pc, monster, 20, 1)  # il PG è primo, ma sorpreso
    assert enc["active_combatant_id"] == pc["id"]
    me = await _me(client, cid)
    assert me["incapacitated"] is True and me["speed"] == 0
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 15})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "incapacitated"
    # fine del suo primo turno: la sorpresa cade, il turno dopo agisce
    as_user(GM_ID)
    enc = (await client.post(f"/sessions/{sid}/encounter/next-turn")).json()
    assert next(c for c in enc["combatants"] if c["id"] == pc["id"])["surprised"] is False
    me = await _me(client, cid)
    assert me["incapacitated"] is False and me["speed"] > 0
    # un secondo giro non lo ferma più
    await client.post(f"/sessions/{sid}/encounter/next-turn")
    assert (await _me(client, cid))["incapacitated"] is False


async def test_surprise_2014_later_in_order_and_undo(client, test_session_factory):
    sid, cid, pc, monster = await _surprise_setup(client, test_session_factory, "2014")
    await _surprise(client, sid, pc["id"])
    await _start(client, sid, pc, monster, 1, 20)  # il mostro apre
    as_user(GM_ID)
    await client.post(f"/sessions/{sid}/encounter/next-turn")
    assert (await _me(client, cid))["incapacitated"] is True
    await client.post(f"/sessions/{sid}/encounter/next-turn")  # fine turno del PG
    assert (await _me(client, cid))["incapacitated"] is False
    live = (await client.post(f"/sessions/{sid}/encounter/prev-turn")).json()  # tornare indietro rimette la sorpresa
    assert (await _me(client, cid))["incapacitated"] is True
    assert next(c for c in live["combatants"] if c["id"] == pc["id"])["surprised"] is True


async def test_surprise_2024_does_not_skip_the_turn(client, test_session_factory):
    sid, cid, pc, monster = await _surprise_setup(client, test_session_factory, "2024")
    await _surprise(client, sid, pc["id"])
    await _start(client, sid, pc, monster, 20, 1)
    assert (await _me(client, cid))["incapacitated"] is False


async def test_monster_surprise_is_only_a_flag_the_gm_clears_at_end_of_turn(client, test_session_factory):
    sid, cid, pc, monster = await _surprise_setup(client, test_session_factory, "2014")
    await _surprise(client, sid, monster["id"])
    await _start(client, sid, pc, monster, 1, 20)
    as_user(GM_ID)
    enc = (await client.post(f"/sessions/{sid}/encounter/next-turn")).json()
    assert next(c for c in enc["combatants"] if c["id"] == monster["id"])["surprised"] is False


def test_migrations_declare_the_surprise_column():
    from core.db.engine import _MIGRATIONS
    assert ("combatants", "surprised", "BOOLEAN NOT NULL", "0") in _MIGRATIONS


# --- Ispirazione Eroica 2024: ritiro dei dadi di danno ------------------------------------------------------------

async def _spell_damage_setup(client, edition):
    from tests.integration.test_rules_spells import _char as spell_char, _spell
    cid = await spell_char(client, ("wizard", 5), edition=edition)
    spell = await _spell(client, cid, damage_dice="3d6", attack_save="SAVE")
    r = await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
    assert r.status_code == 200, r.text
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/roll_damage", json={"main_rolls": [1, 2, 6]})
    assert r.status_code == 200, r.text
    return cid


async def test_inspiration_2024_rerolls_one_damage_die(client, monkeypatch):
    cid = await _spell_damage_setup(client, "2024")
    listed = await client.get(f"/characters/{cid}/roll-options", params={"roll": "spell_damage", "spell_id": 1})
    assert any(o["key"] == "inspiration:reroll_damage" and o["reroll_limit"] == 1 for o in listed.json())
    monkeypatch.setattr("api.routers.spells.random.randint", lambda _a, _b: 5)
    r = await client.post(f"/characters/{cid}/last-damage/options",
                          json={"options": ["inspiration:reroll_damage"], "reroll": [0]})
    assert r.status_code == 200, r.text
    assert r.json()["main_rolls"] == [5, 2, 6] and r.json()["total"] == 13
    assert (await _full(client, cid))["heroic_inspiration"] is False
    r = await client.post(f"/characters/{cid}/last-damage/options",
                          json={"options": ["inspiration:reroll_damage"], "reroll": [1]})
    assert r.status_code == 409  # spesa: non c'è più


async def test_inspiration_2014_has_no_damage_reroll(client):
    cid = await _spell_damage_setup(client, "2014")
    listed = await client.get(f"/characters/{cid}/roll-options", params={"roll": "spell_damage", "spell_id": 1})
    assert all(o["key"] != "inspiration:reroll_damage" for o in listed.json())


# --- Ispirazione Eroica 2024: cederla a un alleato -----------------------------------------------------------------

async def _two_players(factory, edition="2024", sender_has=True, recipient_has=False):
    from core.db.models import Character, SessionParticipant, SessionRole
    sid, cid = await seed_session(factory)
    other = 9999
    async with factory() as s:
        mine = await s.get(Character, cid)
        mine.rules_edition, mine.heroic_inspiration = edition, sender_has
        friend = Character(user_id=other, name="Amico", heroic_inspiration=recipient_has)
        s.add(friend)
        await s.flush()
        s.add(SessionParticipant(session_id=sid, user_id=other, character_id=friend.id, role=SessionRole.PLAYER,
                                 display_name="Amico", joined_at="2026-06-09T10:00:00"))
        await s.commit()
        return sid, cid, friend.id, other


async def test_give_inspiration_to_an_ally(client, test_session_factory):
    sid, cid, friend, other = await _two_players(test_session_factory)
    as_user(PLAYER_ID)
    r = await client.post(f"/sessions/{sid}/inspiration/give", json={"from_character_id": cid, "to_user_id": other})
    assert r.status_code == 200, r.text
    assert r.json()["heroic_inspiration"] is False
    as_user(other)
    assert (await client.get(f"/characters/{friend}")).json()["heroic_inspiration"] is True


@pytest.mark.parametrize("edition,sender,recipient,status,code", [
    ("2014", True, False, 422, "inspiration_give_2024_only"),
    ("2024", False, False, 409, "inspiration_unavailable"),
    ("2024", True, True, 409, "recipient_has_inspiration"),
])
async def test_give_inspiration_refusals(client, test_session_factory, edition, sender, recipient, status, code):
    sid, cid, friend, other = await _two_players(test_session_factory, edition, sender, recipient)
    as_user(PLAYER_ID)
    r = await client.post(f"/sessions/{sid}/inspiration/give", json={"from_character_id": cid, "to_user_id": other})
    assert r.status_code == status and r.json()["detail"]["code"] == code


async def test_give_inspiration_only_from_your_own_character_to_a_player(client, test_session_factory):
    sid, cid, friend, other = await _two_players(test_session_factory)
    as_user(PLAYER_ID)
    r = await client.post(f"/sessions/{sid}/inspiration/give", json={"from_character_id": friend, "to_user_id": other})
    assert r.status_code == 403
    r = await client.post(f"/sessions/{sid}/inspiration/give", json={"from_character_id": cid, "to_user_id": GM_ID})
    assert r.status_code == 422


# --- Azione Nascondersi 2024 --------------------------------------------------------------------------------------

async def test_hide_2024_makes_invisible_and_breaks_on_attack(client):
    cid = await _char(client, edition="2024")
    r = await client.post(f"/characters/{cid}/hide", json={"total": 14})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "hide_failed"
    r = await client.post(f"/characters/{cid}/hide", json={"total": 17})
    assert r.status_code == 200, r.text
    assert r.json()["conditions"]["invisible"] is True
    r = await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 12})
    assert r.status_code == 200, r.text
    assert r.json()["mode_applied"] == "advantage"  # l'attacco da nascosto ha vantaggio
    assert not (await _full(client, cid))["conditions"].get("invisible")


async def test_hide_2014_is_only_the_stealth_check(client):
    cid = await _char(client)
    r = await client.post(f"/characters/{cid}/hide", json={"total": 20})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "hide_2024_only"


async def test_hide_ends_on_verbal_spell_but_not_on_somatic_only(client):
    cid = await _char(client, edition="2024", cls="wizard")
    mute = await client.post(f"/characters/{cid}/spells", json={"name": "Gesto", "level": 0, "components": "S"})
    loud = await client.post(f"/characters/{cid}/spells", json={"name": "Parola", "level": 0, "components": "V, S"})
    await client.post(f"/characters/{cid}/hide", json={"total": 18})
    r = await client.post(f"/characters/{cid}/spells/{mute.json()['id']}/use", json={})
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["conditions"]["invisible"] is True
    r = await client.post(f"/characters/{cid}/spells/{loud.json()['id']}/use", json={})
    assert r.status_code == 200, r.text
    assert not (await _full(client, cid))["conditions"].get("invisible")


async def test_hide_removed_by_hand_does_not_linger(client):
    cid = await _char(client, edition="2024")
    await client.post(f"/characters/{cid}/hide", json={"total": 18})
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"invisible": False}})
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"invisible": True}})  # un incantesimo vero
    r = await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 12})
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["conditions"]["invisible"] is True

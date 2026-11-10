"""Ranger 2024 (Task 38, parte B): Signore delle Bestie, Viandante Fatato, Stalker delle Tenebre, Cacciatore.
Valori dalla scheda ``docs/superpowers/rules/2024/classes/ranger.md``."""
from __future__ import annotations

import pytest

from core.db.models import Character
from core.rules.catalog import features_for
from core.rules.catalog.granted_spells import GRANTED_SPELLS
from tests.integration.rules.test_2014_bard import _ability, _choice, _full, _keys_of, _resolve, _roll_keys, _skills, _states, _use
from tests.integration.rules.test_2014_fighter_styles import _item
from tests.integration.rules.test_2014_paladin import _new_turn, _rest, _turn
from tests.integration.rules.test_2014_rogue import _save
from tests.integration.rules.test_2014_paladin_combat import _attack, _damage, _deferred, _listed, _slots
from tests.integration.rules.test_2024_paladin import _conditions
from tests.integration.rules.test_2014_ranger_beast import _companion as _companion14, _master as _master14
from tests.integration.rules.test_2024_ranger import _cast_mark, _hit, _ranger24, _spell_id

NAMES = {"beast_master": "Signore delle Bestie", "fey_wanderer": "Viandante Fatato", "gloom_stalker": "Stalker delle Tenebre",
         "hunter": "Cacciatore"}
TIERS = {
    "fey_wanderer": (("charm-person",), ("misty-step",), ("summon-fey",), ("dimension-door",), ("mislead",)),
    "gloom_stalker": (("disguise-self",), ("rope-trick",), ("fear",), ("greater-invisibility",), ("seeming",)),
}
PC = "ranger.primal_companion"
DREAD, MARK = "ranger.dread_ambusher", "ranger.hunters_mark_damage"


async def _sub(client, level, sub, **scores) -> int:
    cid = await _ranger24(client, level, **scores)
    klass = (await _full(client, cid))["classes"][0]["id"]
    r = await client.patch(f"/characters/{cid}/classes/{klass}", json={"subclass": NAMES[sub]})
    assert r.status_code == 200, r.text
    return cid


async def _weapon(client, cid, **kw) -> int:
    return await _item(client, cid, "Spada", damage_dice="1d8", weapon_type="melee", properties=[], **kw)


async def _companions(client, cid) -> list[dict]:
    return (await client.get(f"/characters/{cid}/companions")).json()


async def _beast(client, cid, kind="land", damage="slashing", level_pay="use") -> dict:
    r = await _use(client, cid, PC, params={"pay": level_pay, "kind": kind, "damage_type": damage})
    assert r.status_code == 200, r.text
    return next(c for c in await _companions(client, cid) if c["feature_key"] == PC)


# ---------------------------------------------------------------------------
# Struttura: righe e incantesimi
# ---------------------------------------------------------------------------

def test_each_subclass_has_the_rows_of_the_sheet():
    keys = {(f.subclass, f.key.split(".")[1]) for f in features_for("2024", "ranger") if f.subclass}
    assert {subclass for subclass, _ in keys} == set(NAMES)
    expected = {
        "beast_master": {"primal_companion", "beast_of_the_land", "beast_of_the_sky", "beast_of_the_sea", "exceptional_training",
                         "bestial_fury", "share_spells"},
        "fey_wanderer": {"dreadful_strikes", "fey_wanderer_spells", "feywild_gifts", "otherworldly_glamour", "beguiling_twist",
                         "fey_reinforcements", "misty_wanderer"},
        "gloom_stalker": {"dread_ambusher", "gloom_stalker_spells", "umbral_sight", "iron_mind", "stalkers_flurry", "sudden_strike",
                          "mass_fear", "shadowy_dodge"},
        "hunter": {"hunters_lore", "hunters_prey", "colossus_slayer", "horde_breaker", "defensive_tactics", "escape_the_horde",
                   "multiattack_defense", "superior_hunters_prey", "superior_hunters_defense"},
    }
    for subclass, rows in expected.items():
        assert {k for s, k in keys if s == subclass} >= rows, subclass


def test_the_granted_spells_new_to_the_catalog_have_data_the_app_can_use():
    for key in ("summon-fey", "mislead", "rope-trick", "seeming", "fear"):
        spell = GRANTED_SPELLS[key]
        assert spell.name["it"] and spell.name["en"] and spell.casting_time and spell.components and spell.school, key


@pytest.mark.parametrize("sub", sorted(TIERS))
@pytest.mark.parametrize("level,tiers", [(3, 1), (4, 1), (5, 2), (9, 3), (13, 4), (17, 5), (20, 5)])
async def test_subclass_spells_follow_the_level(client, sub, level, tiers):
    cid = await _sub(client, level, sub)
    expected = {k for tier in TIERS[sub][:tiers] for k in tier}
    got = {s["srd_index"] for s in (await client.get(f"/characters/{cid}/spells")).json() if s.get("always_prepared")}
    assert expected <= got
    assert not ({k for tier in TIERS[sub][tiers:] for k in tier} & got)


# ---------------------------------------------------------------------------
# Signore delle Bestie
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kind,hp,ac,speed_key", [("land", 30, 16, "climb_ft"), ("sky", 24, 16, "fly_ft"), ("sea", 30, 16, "swim_ft")])
async def test_primal_companion_is_summoned_with_the_stat_block_of_the_chosen_beast(client, kind, hp, ac, speed_key):
    cid = await _sub(client, 5, "beast_master", wisdom=16)  # SAG +3, PB +3
    comp = await _beast(client, cid, kind, "piercing" if kind == "sea" else "slashing")
    assert (comp["max_hp"], comp["current_hp"], comp["armor_class"]) == (hp, hp, ac)
    assert comp["attack_bonus_extra"] == 6 and comp["damage_bonus_extra"] == 3  # incantesimi = PB + SAG; danno + SAG
    action = comp["statblock"]["actions"][0]
    assert comp["statblock"]["primal_type"] == kind and comp["statblock"]["speed"][speed_key] and action["damage_type"]
    assert (await _ability(client, cid, PC))["uses"] == 0 and not (await _turn(client, cid)).get("action_used")


async def test_the_damage_of_the_beast_is_chosen_among_those_of_its_form(client):
    cid = await _sub(client, 3, "beast_master")
    bad = await _use(client, cid, PC, params={"pay": "use", "kind": "sky", "damage_type": "bludgeoning"})  # il Cielo è solo tagliente
    assert bad.status_code == 422 and not await _companions(client, cid)
    assert (await _use(client, cid, PC, params={"pay": "use", "kind": "sea", "damage_type": "bludgeoning"})).status_code == 200


async def test_a_new_summon_replaces_the_beast_and_a_long_rest_returns_the_use(client):
    cid = await _sub(client, 3, "beast_master")
    await _beast(client, cid)
    assert (await _use(client, cid, PC, params={"pay": "use", "kind": "sea", "damage_type": "piercing"})).status_code == 409  # nessun uso
    await _rest(client, cid, "long")
    await _beast(client, cid, "sky")
    beasts = [c for c in await _companions(client, cid) if c["feature_key"] == PC]
    assert len(beasts) == 1 and beasts[0]["statblock"]["primal_type"] == "sky"


async def test_a_dead_beast_is_restored_with_a_slot_and_the_magic_action(client):
    cid = await _sub(client, 5, "beast_master")
    comp = await _beast(client, cid)
    assert (await client.patch(f"/characters/{cid}/companions/{comp['id']}/hp", json={"op": "damage", "value": 99})).status_code == 200
    r = await _use(client, cid, PC, params={"pay": "slot", "slot_level": "1"})
    assert r.status_code == 200, r.text
    back = next(c for c in await _companions(client, cid) if c["feature_key"] == PC)
    assert back["id"] == comp["id"] and back["current_hp"] == back["max_hp"]
    assert (await _slots(client, cid))[1] == 1 and (await _turn(client, cid))["action_used"] is True
    assert (await _ability(client, cid, PC))["uses"] == 0  # il ripristino non tocca l'uso del riposo lungo


async def _order(client, cid, comp, command, bonus=False):
    return await client.post(f"/characters/{cid}/companions/{comp['id']}/command", json={"command": command, "bonus": bonus})


async def _strike(client, cid, comp, **body):
    return await client.post(f"/characters/{cid}/companions/{comp['id']}/attack", json={"action_index": 0, "dice": [12], **body})


async def test_the_beast_attacks_only_on_command_forgoing_an_attack_or_with_the_bonus_action(client):
    cid = await _sub(client, 5, "beast_master")
    comp = await _beast(client, cid)
    assert (await _strike(client, cid, comp)).status_code == 409  # nessun ordine
    assert (await _order(client, cid, comp, "help")).status_code == 422  # rinunciando a un attacco si ordina solo il Colpo
    r = await _order(client, cid, comp, "attack")
    assert r.status_code == 200 and r.json()["attacks_left"] == 1, r.text
    turn = await _turn(client, cid)
    assert not turn.get("bonus_used") and turn["action_attacks"] >= 1  # ha rinunciato a un attacco dell'azione Attacco
    assert (await _strike(client, cid, comp)).status_code == 200
    assert (await _strike(client, cid, comp)).status_code == 409
    await _new_turn(client, cid)
    r = await _order(client, cid, comp, "attack", bonus=True)
    assert r.status_code == 200 and (await _turn(client, cid))["bonus_used"] is True


async def test_exceptional_training_adds_a_strike_to_a_bonus_order_and_allows_force_damage(client):
    early, cid = await _sub(client, 6, "beast_master"), await _sub(client, 7, "beast_master")
    for who, left in ((early, 0), (cid, 1)):
        comp = await _beast(client, who)
        r = await _order(client, who, comp, "dash", bonus=True)
        assert r.status_code == 200 and r.json()["attacks_left"] == left, r.text
    assert (await _strike(client, cid, comp)).status_code == 200
    assert "ranger.beast_force" in await _roll_keys(client, cid, "attack", attack_mode="beast")
    assert "ranger.beast_force" not in await _roll_keys(client, early, "attack", attack_mode="beast")


async def test_bestial_fury_gives_two_strikes_and_extra_mark_damage_once_per_turn(client):
    cid = await _sub(client, 11, "beast_master")
    comp = await _beast(client, cid)
    assert (await _order(client, cid, comp, "attack")).json()["attacks_left"] == 2
    assert "ranger.bestial_fury_damage" not in await _roll_keys(client, cid, "attack", attack_mode="beast")  # senza Hunter's Mark
    await _cast_mark(client, cid)
    assert "ranger.bestial_fury_damage" in await _roll_keys(client, cid, "attack", attack_mode="beast")
    r = await _strike(client, cid, comp, options=["ranger.bestial_fury_damage"])
    assert r.status_code == 200 and r.json()["option_result"]["extra_total"] >= 1, r.text
    assert "ranger.bestial_fury_damage" not in await _roll_keys(client, cid, "attack", attack_mode="beast")  # una volta per turno


async def test_bestial_fury_adds_exactly_one_mark_die_and_the_mark_itself_does_not_reach_the_beast(client):
    cid = await _sub(client, 17, "beast_master")
    comp = await _beast(client, cid)
    await _cast_mark(client, cid)
    keys = await _roll_keys(client, cid, "attack", attack_mode="beast")
    assert "ranger.bestial_fury_damage" in keys
    assert not {"ranger.hunters_mark_damage", "ranger.precise_hunter"} & set(keys)  # il marchio e il Vantaggio sono del ranger
    assert {"ranger.hunters_mark_damage", "ranger.precise_hunter"} <= set(await _roll_keys(client, cid, "attack"))  # i suoi attacchi li hanno
    await _order(client, cid, comp, "attack")
    r = await _strike(client, cid, comp, options=["ranger.bestial_fury_damage"])
    assert r.status_code == 200, r.text
    assert len(r.json()["option_result"]["extra_rolls"]) == 1  # un solo d6: quello di Furia Bestiale
    for key in ("ranger.hunters_mark_damage", "ranger.precise_hunter"):
        assert (await _strike(client, cid, comp, options=[key])).status_code == 409


async def test_hunters_mark_does_not_reach_the_attack_of_another_companion(client):
    cid = await _sub(client, 17, "beast_master")
    await _cast_mark(client, cid)
    assert not {"ranger.hunters_mark_damage", "ranger.precise_hunter"} & set(await _roll_keys(client, cid, "attack", attack_mode="companion"))
    r = await client.post(f"/characters/{cid}/companions", json={
        "kind": "familiar", "name": "Gufo", "max_hp": 5, "armor_class": 11,
        "statblock": {"size": "Tiny", "type": "beast", "actions": [{"name": "Artigli", "attack_bonus": 3, "damage_dice": "1d4"}]}})
    assert r.status_code == 201, r.text
    hit = await client.post(f"/characters/{cid}/companions/{r.json()['id']}/attack",
                            json={"action_index": 0, "dice": [12], "options": ["ranger.hunters_mark_damage"]})
    assert hit.status_code == 409, hit.text


async def test_a_missed_strike_of_the_beast_does_not_spend_bestial_fury(client):
    cid = await _sub(client, 11, "beast_master")
    comp = await _beast(client, cid)
    await _cast_mark(client, cid)
    await _order(client, cid, comp, "attack")
    assert (await _strike(client, cid, comp, dice=[1], options=["ranger.bestial_fury_damage"])).status_code == 200  # un 1: manca
    assert "ranger.bestial_fury_damage" in await _roll_keys(client, cid, "attack", attack_mode="beast")  # l'uso torna
    r = await _strike(client, cid, comp, options=["ranger.bestial_fury_damage"])
    assert r.status_code == 200 and len(r.json()["option_result"]["extra_rolls"]) == 1, r.text
    assert "ranger.bestial_fury_damage" not in await _roll_keys(client, cid, "attack", attack_mode="beast")  # colpito: speso


async def test_the_strikes_of_the_orders_add_up_and_a_bonus_order_gives_the_strikes_of_bestial_fury(client):
    five, seven, eleven = [await _sub(client, lvl, "beast_master") for lvl in (5, 7, 11)]
    comp = await _beast(client, five)
    assert (await _order(client, five, comp, "attack")).json()["attacks_left"] == 1
    assert (await _order(client, five, comp, "attack")).json()["attacks_left"] == 2  # due attacchi ceduti: due Colpi, non uno
    comp = await _beast(client, seven)
    assert (await _order(client, seven, comp, "attack")).json()["attacks_left"] == 1
    assert (await _order(client, seven, comp, "dash", bonus=True)).json()["attacks_left"] == 2  # il Colpo dell'azione bonus si aggiunge
    comp = await _beast(client, eleven)
    assert (await _order(client, eleven, comp, "dash", bonus=True)).json()["attacks_left"] == 2  # Furia Bestiale: due Colpi


async def test_the_beast_of_the_land_adds_a_die_when_it_charges_twenty_feet(client):
    land, sky = await _sub(client, 5, "beast_master"), await _sub(client, 5, "beast_master")
    await _beast(client, land, "land")
    await _beast(client, sky, "sky")
    assert "ranger.beast_charge" in await _roll_keys(client, land, "attack", attack_mode="beast")
    assert "ranger.beast_charge" not in await _roll_keys(client, sky, "attack", attack_mode="beast")


async def test_the_beast_of_the_sea_grapples_with_the_spell_save_dc(client):
    cid = await _sub(client, 5, "beast_master", wisdom=16)  # CD 8 + 3 + 3
    comp = await _beast(client, cid, "sea", "piercing")
    assert "ranger.beast_grapple" in await _roll_keys(client, cid, "attack", attack_mode="beast")
    await _order(client, cid, comp, "attack")
    r = await _strike(client, cid, comp, options=["ranger.beast_grapple"])
    assert r.status_code == 200 and "14" in r.text, r.text


def test_share_spells_extends_a_spell_on_the_ranger_from_level_15():
    row = next(f for f in features_for("2024", "ranger") if f.key == "ranger.share_spells")
    assert row.level == 15 and row.subclass == "beast_master" and [o.key for o in row.roll_options] == ["ranger.share_spells_extend"]


# ---------------------------------------------------------------------------
# Viandante Fatato
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,dice", [(3, "1d4"), (11, "1d6")])
async def test_dreadful_strikes_add_psychic_damage_once_per_turn(client, level, dice):
    cid = await _sub(client, level, "fey_wanderer")
    sword = await _weapon(client, cid)
    listed = await _listed(client, cid, sword)
    option = next(o for o in listed if o["key"] == "ranger.dreadful_strikes")
    assert option["dice"] == dice
    hit = await _deferred(client, cid, sword)
    r = await _damage(client, cid, hit, ["ranger.dreadful_strikes"])
    assert r.status_code == 200, r.text
    assert "ranger.dreadful_strikes" not in [o["key"] for o in await _listed(client, cid, sword)]


async def test_otherworldly_glamour_adds_wisdom_to_charisma_skills_and_asks_for_a_proficiency(client):
    cid = await _sub(client, 3, "fey_wanderer", wisdom=16, charisma=10)
    persuasion = (await client.post(f"/characters/{cid}/skills/persuasion/roll", json={"die": 10})).json()["bonus"]
    athletics = (await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 10})).json()["bonus"]
    assert (persuasion, athletics) == (3, 0)
    choice = _choice(await _full(client, cid), "otherworldly_glamour")
    assert choice["count"] == 1 and {o["key"] for o in choice["options"]} == {"deception", "performance", "persuasion"}
    assert (await _resolve(client, cid, "otherworldly_glamour", ["persuasion"])).status_code == 200
    assert (await _full(client, cid))["skills"]["persuasion"] is True


async def test_otherworldly_glamour_adds_wisdom_to_a_pure_charisma_check(client):
    cid = await _sub(client, 3, "fey_wanderer", wisdom=16, charisma=10)
    bonus = {}
    for ability in ("charisma", "strength"):
        r = await client.post(f"/characters/{cid}/ability_checks/{ability}/roll", json={"dice": [10]})
        assert r.status_code == 200, r.text
        bonus[ability] = r.json()["bonus"]
    assert bonus == {"charisma": 3, "strength": 0}


async def test_beguiling_twist_gives_advantage_against_charm_and_fear_and_a_reaction_with_the_spell_dc(client):
    early, cid = await _sub(client, 6, "fey_wanderer", wisdom=16), await _sub(client, 7, "fey_wanderer", wisdom=16)
    assert "ranger.beguiling_twist" not in await _keys_of(client, early)
    assert "ranger.beguiling_twist_advantage" in await _roll_keys(client, cid, "save")
    r = await _use(client, cid, "ranger.beguiling_twist", params={"condition": "charmed"})
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["reaction_used"] is True


@pytest.mark.parametrize("key,spell,level,slot,uses", [
    ("ranger.fey_reinforcements", "summon-fey", 11, "action_used", 1),
    ("ranger.misty_wanderer", "misty-step", 15, "bonus_used", 3)])
async def test_the_free_casts_of_the_fey_wanderer_authorise_a_slotless_cast_once_per_long_rest(client, key, spell, level, slot, uses):
    cid = await _sub(client, level, "fey_wanderer", wisdom=16)
    assert (await _ability(client, cid, key))["max_uses"] == uses
    assert (await _use(client, cid, key)).status_code == 200
    assert (await _ability(client, cid, key))["uses"] == uses - 1
    state = next(s for s in await _states(client, cid) if s["data"].get("free_cast") == spell)
    assert state["data"]["free_cast_slot"] == slot.replace("_used", "").replace("bonus", "bonus")
    r = await client.post(f"/characters/{cid}/spells/{await _spell_id(client, cid, spell)}/use", json={"free_cast": True})
    assert r.status_code == 200, r.text
    assert all(s["used"] == 0 for s in (await _full(client, cid))["spell_slots"])
    assert not any(s["data"].get("free_cast") == spell for s in await _states(client, cid))


async def test_fey_reinforcements_can_give_up_concentration(client):
    cid = await _sub(client, 11, "fey_wanderer")
    assert (await _use(client, cid, "ranger.fey_reinforcements", params={"no_concentration": True})).status_code == 200
    r = await client.post(f"/characters/{cid}/spells/{await _spell_id(client, cid, 'summon-fey')}/use", json={"free_cast": True})
    assert r.status_code == 200 and not (await _full(client, cid)).get("concentrating_spell_id")


# ---------------------------------------------------------------------------
# Stalker delle Tenebre
# ---------------------------------------------------------------------------

async def test_dread_ambusher_adds_wisdom_to_initiative_and_has_wisdom_uses(client):
    cid = await _sub(client, 3, "gloom_stalker", wisdom=16)
    assert (await _full(client, cid))["initiative_bonus"] == 3 + 0  # DES 10
    row = await _ability(client, cid, DREAD)
    assert (row["max_uses"], row["restoration_type"]) == (3, "long_rest")


@pytest.mark.parametrize("level,dice", [(3, "2d6"), (11, "2d8")])
async def test_dreadful_strike_costs_a_use_adds_psychic_dice_once_per_turn(client, level, dice):
    cid = await _sub(client, level, "gloom_stalker", wisdom=16)
    sword = await _weapon(client, cid)
    option = next(o for o in await _listed(client, cid, sword) if o["key"] == "ranger.dreadful_strike")
    assert option["dice"] == dice
    hit = await _deferred(client, cid, sword)
    assert (await _damage(client, cid, hit, ["ranger.dreadful_strike"])).status_code == 200
    assert (await _ability(client, cid, DREAD))["uses"] == 2
    assert "ranger.dreadful_strike" not in [o["key"] for o in await _listed(client, cid, sword)]


async def test_the_first_turn_of_a_fight_gives_ten_feet_of_speed(client):
    cid = await _sub(client, 3, "gloom_stalker")
    assert "ranger.dread_ambusher_speed" in await _roll_keys(client, cid, "initiative")
    r = await client.post(f"/characters/{cid}/dice/initiative", json={"die": 9, "options": ["ranger.dread_ambusher_speed"]})
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["computed"]["speed"] == 40


@pytest.mark.parametrize("level,darkvision", [(3, 60)])
async def test_umbral_sight_gives_sixty_feet_of_darkvision(client, level, darkvision):
    cid = await _sub(client, level, "gloom_stalker")
    assert {"type": "darkvision", "range_ft": darkvision} in (await _full(client, cid))["computed"].get("senses", []) or any(
        s["type"] == "darkvision" and s["range_ft"] == darkvision for s in (await _full(client, cid))["senses"])


async def test_iron_mind_gives_wisdom_save_proficiency_from_level_7(client):
    early, cid = await _sub(client, 6, "gloom_stalker", wisdom=14), await _sub(client, 7, "gloom_stalker", wisdom=14)
    assert (await _save(client, early, "wisdom"))["bonus"] == 2
    assert (await _save(client, cid, "wisdom"))["bonus"] == 2 + 3  # SAG +2, competenza +3
    await client.patch(f"/characters/{cid}/saving_throws", json={"saving_throws": {"wisdom": True}})
    assert (await _save(client, cid, "wisdom"))["bonus"] == 2 + 3  # non si somma due volte


async def test_iron_mind_asks_for_intelligence_or_charisma_when_wisdom_is_already_a_proficient_save(client):
    plain = await _sub(client, 7, "gloom_stalker", wisdom=14)
    assert _choice(await _full(client, plain), "iron_mind") is None  # il Ranger puro prende la Saggezza e basta
    cid = await _sub(client, 6, "gloom_stalker", wisdom=14)
    await client.patch(f"/characters/{cid}/saving_throws", json={"saving_throws": {"wisdom": True}})  # per esempio da un Chierico
    klass = (await _full(client, cid))["classes"][0]["id"]
    assert (await client.patch(f"/characters/{cid}/classes/{klass}", json={"level": 7})).status_code == 200
    choice = _choice(await _full(client, cid), "iron_mind")
    assert choice["count"] == 1 and {o["key"] for o in choice["options"]} == {"intelligence", "charisma"}
    assert all(o["name"]["it"] and o["name"]["en"] for o in choice["options"])
    assert (await _resolve(client, cid, "iron_mind", ["charisma"])).status_code == 200
    assert (await _full(client, cid))["saving_throws"]["charisma"] is True
    assert (await _save(client, cid, "charisma"))["bonus"] == 0 + 3  # CAR 10, competenza +3


async def test_stalkers_flurry_offers_a_sudden_strike_or_mass_fear_after_a_dreadful_strike_once_per_turn(client):
    early, cid = await _sub(client, 10, "gloom_stalker", wisdom=16), await _sub(client, 11, "gloom_stalker", wisdom=16)
    listed = {}
    for who in (early, cid):
        sword = await _weapon(client, who)
        hit = await _deferred(client, who, sword)
        assert (await _damage(client, who, hit, ["ranger.dreadful_strike"])).status_code == 200
        listed[who] = {o["key"] for o in await _listed(client, who, sword)}
    assert "ranger.sudden_strike" in listed[cid]
    assert not {"ranger.sudden_strike", "ranger.mass_fear"} & listed[early]


async def test_mass_fear_is_offered_on_the_hit_of_the_dreadful_strike_and_states_the_wisdom_save(client):
    cid = await _sub(client, 11, "gloom_stalker", wisdom=16)
    sword = await _weapon(client, cid)
    hit = await _deferred(client, cid, sword)
    assert {"ranger.dreadful_strike", "ranger.mass_fear"} <= {o["key"] for o in await _listed(client, cid, sword)}  # sullo stesso colpo
    r = await _damage(client, cid, hit, ["ranger.dreadful_strike", "ranger.mass_fear"])
    assert r.status_code == 200 and "14" in r.text, r.text
    assert (await _ability(client, cid, DREAD))["uses"] == 2  # un solo uso per i due effetti
    assert "ranger.mass_fear" not in [o["key"] for o in await _listed(client, cid, sword)]  # non su un colpo successivo


async def test_shadowy_dodge_spends_the_reaction_from_level_15(client):
    early, cid = await _sub(client, 14, "gloom_stalker"), await _sub(client, 15, "gloom_stalker")
    assert "ranger.shadowy_dodge" not in await _keys_of(client, early)
    assert (await _use(client, cid, "ranger.shadowy_dodge")).status_code == 200
    assert (await _turn(client, cid))["reaction_used"] is True
    assert (await _use(client, cid, "ranger.shadowy_dodge")).status_code == 409


# ---------------------------------------------------------------------------
# Cacciatore
# ---------------------------------------------------------------------------

async def test_hunters_prey_is_chosen_at_level_3_and_only_the_chosen_one_works(client):
    cid = await _sub(client, 3, "hunter")
    choice = _choice(await _full(client, cid), "hunters_prey")
    assert choice["count"] == 1 and {o["key"] for o in choice["options"]} == {"colossus_slayer", "horde_breaker"}
    assert (await _resolve(client, cid, "hunters_prey", ["colossus_slayer"])).status_code == 200
    sword = await _weapon(client, cid)
    keys = [o["key"] for o in await _listed(client, cid, sword)]
    assert "ranger.colossus_slayer" in keys and "ranger.horde_breaker" not in keys


async def test_hunters_prey_is_replaceable_after_a_rest(client):
    cid = await _sub(client, 3, "hunter")
    await _resolve(client, cid, "hunters_prey", ["colossus_slayer"])
    klass = (await _full(client, cid))["classes"][0]["id"]
    await _rest(client, cid, "long")
    r = await client.post(f"/characters/{cid}/classes/{klass}/options/replace",
                          json={"group": "hunters_prey", "old_key": "colossus_slayer", "new_key": "horde_breaker"})
    assert r.status_code == 200, r.text
    state = (await client.get(f"/characters/{cid}/classes/{klass}/options/hunters_prey")).json()
    assert [o["key"] for o in state["chosen"]] == ["horde_breaker"]
    assert "ranger.colossus_slayer" not in [o["key"] for o in await _listed(client, cid, await _weapon(client, cid))]


async def test_defensive_tactics_are_chosen_at_level_7(client):
    assert _choice(await _full(client, await _sub(client, 6, "hunter")), "defensive_tactics") is None
    cid = await _sub(client, 7, "hunter")
    choice = _choice(await _full(client, cid), "defensive_tactics")
    assert {o["key"] for o in choice["options"]} == {"escape_the_horde", "multiattack_defense"}
    assert (await _resolve(client, cid, "defensive_tactics", ["multiattack_defense"])).status_code == 200
    assert "ranger.multiattack_defense" in await _roll_keys(client, cid, "damage_taken")


async def test_escape_the_horde_shows_a_permanent_note(client):
    cid = await _sub(client, 7, "hunter")
    await _resolve(client, cid, "defensive_tactics", ["escape_the_horde"])
    assert "ranger.multiattack_defense" not in await _roll_keys(client, cid, "damage_taken")
    assert any(s["key"] == "escape_the_horde" for s in await _states(client, cid))


async def test_multiattack_defense_starts_a_state_until_the_end_of_the_turn(client):
    cid = await _sub(client, 7, "hunter")
    await _resolve(client, cid, "defensive_tactics", ["multiattack_defense"])
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 3, "options": ["ranger.multiattack_defense"]})
    assert r.status_code == 200, r.text
    assert any(s["key"] == "multiattack_defense" for s in await _states(client, cid))
    await _new_turn(client, cid)
    assert not any(s["key"] == "multiattack_defense" for s in await _states(client, cid))


async def test_superior_hunters_prey_adds_the_mark_die_to_a_second_creature_once_per_turn(client):
    early, cid = await _sub(client, 10, "hunter"), await _sub(client, 11, "hunter")
    for who in (early, cid):
        await _cast_mark(client, who)
    sword = await _weapon(client, cid)
    assert "ranger.superior_hunters_prey" not in [o["key"] for o in await _listed(client, early, await _weapon(client, early))]
    for die in (10, 20):  # anche al critico: il dado è di un'altra creatura e non si raddoppia
        hit = await _deferred(client, cid, sword, die=die)
        plain = hit["damage_total"]
        body = (await _damage(client, cid, hit, ["ranger.superior_hunters_prey"])).json()
        block = body["option_result"]
        assert len(block["separate_rolls"]) == 1 and not block["extra_rolls"], block  # un dado a parte, fuori dal totale
        assert body["damage_total"] == plain
        await _new_turn(client, cid)


async def test_superior_hunters_prey_needs_hunters_mark(client):
    cid = await _sub(client, 11, "hunter")
    sword = await _weapon(client, cid)
    assert "ranger.superior_hunters_prey" not in [o["key"] for o in await _listed(client, cid, sword)]


async def _hp_now(client, cid) -> int:
    return (await _full(client, cid))["current_hit_points"]


async def _hurt(client, cid, value, **body):
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": value, "raw_value": value, **body})
    assert r.status_code == 200, r.text
    return r


async def _tough_hunter(client, cid):
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 300})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 300})


DEFENSE = "ranger.superior_hunters_defense"


async def test_superior_hunters_defense_halves_the_triggering_damage_with_the_reaction_from_level_15(client):
    early, cid = await _sub(client, 14, "hunter"), await _sub(client, 15, "hunter")
    assert DEFENSE not in await _roll_keys(client, early, "damage_taken")
    assert DEFENSE in await _roll_keys(client, cid, "damage_taken")
    await _tough_hunter(client, cid)
    await _hurt(client, cid, 20, damage_type="slashing", options=[DEFENSE])
    assert await _hp_now(client, cid) == 290
    assert (await _turn(client, cid))["reaction_used"] is True


async def test_superior_hunters_defense_resists_that_type_until_the_end_of_the_turn(client):
    cid = await _sub(client, 15, "hunter")
    await _tough_hunter(client, cid)
    await _hurt(client, cid, 20, damage_type="slashing", options=[DEFENSE])
    await _hurt(client, cid, 20, damage_type="slashing")  # altro danno dello stesso tipo, stesso turno: resistenza
    assert await _hp_now(client, cid) == 280
    await _hurt(client, cid, 20, damage_type="fire")  # un altro tipo no
    assert await _hp_now(client, cid) == 260
    await _new_turn(client, cid)
    await _hurt(client, cid, 20, damage_type="slashing")  # a fine turno la resistenza finisce
    assert await _hp_now(client, cid) == 240


async def test_superior_hunters_defense_does_not_stack_with_a_resistance_the_character_already_has(client, test_session_factory):
    cid = await _sub(client, 15, "hunter")
    await _tough_hunter(client, cid)
    async with test_session_factory() as s:
        char = await s.get(Character, cid)
        char.damage_modifiers = {"resistances": ["fire"]}
        await s.commit()
    await _hurt(client, cid, 20, damage_type="fire", options=[DEFENSE])
    assert await _hp_now(client, cid) == 290  # 10, non 5


# ---------------------------------------------------------------------------
# Minori rinviati (punti 17 e 18)
# ---------------------------------------------------------------------------

async def test_ranger_17_the_beast_vanishes_when_the_ranger_dies(client):
    cid = await _sub(client, 5, "beast_master")
    await _beast(client, cid)
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 999})).status_code == 200
    assert (await _full(client, cid))["is_dead"] and not await _companions(client, cid)


async def test_ranger_17_a_slot_only_raises_a_fallen_beast_never_replaces_a_living_one(client):
    cid = await _sub(client, 5, "beast_master")
    comp = await _beast(client, cid)
    slots = await _slots(client, cid)
    r = await _use(client, cid, PC, params={"pay": "slot", "slot_level": "1", "kind": "sky", "damage_type": "slashing"})
    assert r.status_code == 409, r.text
    beasts = [c for c in await _companions(client, cid) if c["feature_key"] == PC]
    assert [b["id"] for b in beasts] == [comp["id"]] and beasts[0]["statblock"]["primal_type"] == "land"
    assert await _slots(client, cid) == slots  # nessuno slot speso


async def test_ranger_17_switching_edition_drops_the_beast_of_the_other_edition(client):
    cid = await _master14(client)
    assert (await _companion14(client, cid)).status_code == 201
    assert len(await _companions(client, cid)) == 1
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    assert not await _companions(client, cid)


async def test_ranger_18_a_negative_wisdom_never_lowers_the_initiative(client):
    cid = await _sub(client, 3, "gloom_stalker", wisdom=6)  # SAG -2, DES 10
    assert (await _full(client, cid))["initiative_bonus"] == 0

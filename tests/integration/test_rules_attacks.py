"""Regole d'attacco per edizione: critico, Arti Marziali, altra mano, Pesante, Ispirazione, limite e Weapon Mastery."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from core.db.models import CharacterClass
from core.rules.types import FeatureSpec, Modifier, OnUse, Uses
from core.rules.weapons import MASTERY_OPTIONS, mastery_choice, weapon_mastery


async def _char(client, edition="2014", cls="fighter", level=1, strength=14, dexterity=10, race=None) -> int:
    r = await client.post("/characters", json={"name": "Prova"})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": cls, "level": level, "hit_die": 10})
    assert r.status_code == 201, r.text
    for ability, value in (("strength", strength), ("dexterity", dexterity)):
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    if edition != "2014" or race:
        fields = {"rules_edition": edition, **({"race": race} if race else {})}
        r = await client.patch(f"/characters/{cid}", json=fields)
        assert r.status_code == 200, r.text
    return cid


async def _weapon(client, cid, name="Spada", equip=None, **meta) -> int:
    meta = {"damage_dice": "1d8", "weapon_type": "melee", "properties": [], **meta}
    r = await client.post(f"/characters/{cid}/items", json={"name": name, "item_type": "weapon", "item_metadata": meta})
    assert r.status_code == 201, r.text
    wid = max(i["id"] for i in r.json()["items"] if i["name"] == name)
    if equip:
        r = await client.patch(f"/characters/{cid}/items/{wid}", json={"is_equipped": True, "equipment_slot": equip})
        assert r.status_code == 200, r.text
    return wid


async def _attack(client, cid, wid, die=10, **body):
    return await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": die, **body})


async def _turn(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]


async def _keys(client, cid, wid, **query) -> list[str]:
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": wid, **query})
    assert r.status_code == 200, r.text
    return [o["key"] for o in r.json()]


async def _feature_with(rules_catalog, edition="2014", **fields) -> None:
    rules_catalog(FeatureSpec(
        key="fighter.prova", class_key="fighter", edition=edition, level=1, source_title="Prova",
        name={"it": "Prova", "en": "Test"}, summary={"it": "x", "en": "x"}, action_type=None, **fields))


def _mastery_feature(edition="2024") -> FeatureSpec:
    return FeatureSpec(
        key="fighter.weapon_mastery", class_key="fighter", edition=edition, level=1, source_title="Weapon Mastery",
        name={"it": "Padronanza delle Armi", "en": "Weapon Mastery"}, summary={"it": "x", "en": "x"}, action_type=None,
        choices=(mastery_choice({1: 3}),), roll_options=MASTERY_OPTIONS)


async def _master(factory, cid, *weapons) -> None:
    async with factory() as s:
        row = (await s.execute(select(CharacterClass).where(CharacterClass.character_id == cid))).scalars().first()
        row.options = {**(row.options or {}), "weapon_mastery": list(weapons)}
        await s.commit()


async def _master_char(client, factory, rules_catalog, *weapons, **kw) -> int:
    rules_catalog(_mastery_feature())
    cid = await _char(client, edition="2024", **kw)
    await _master(factory, cid, *weapons)
    return cid


# --- Soglia del critico ------------------------------------------------------------------------------------------

async def test_crit_threshold_from_modifier(client, rules_catalog):
    await _feature_with(rules_catalog, modifiers=(Modifier("crit_min", 19),))
    cid = await _char(client)
    wid = await _weapon(client, cid)
    body = (await _attack(client, cid, wid, die=19, confirm_extra_attack=True)).json()
    assert body["is_critical"] is True
    assert len(body["damage_rolls"]) == 2
    assert (await _attack(client, cid, wid, die=18, confirm_extra_attack=True)).json()["is_critical"] is False


# --- Arti Marziali ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("edition,level,die", [
    ("2014", 1, "1d4"), ("2014", 5, "1d6"), ("2014", 11, "1d8"), ("2014", 17, "1d10"),
    ("2024", 1, "1d6"), ("2024", 5, "1d8"), ("2024", 11, "1d10"), ("2024", 17, "1d12"),
])
async def test_martial_arts_die_by_edition(client, edition, level, die):
    cid = await _char(client, edition=edition, cls="monk", level=level)
    r = await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 10})
    assert r.status_code == 200, r.text
    assert r.json()["damage_dice"] == die


async def test_armor_or_shield_cancels_martial_arts(client):
    cid = await _char(client, cls="monk", strength=10, dexterity=16)
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Cotta", "item_type": "armor", "item_metadata": {"armor_type": "light", "ac_value": 11}, "is_equipped": True})
    assert r.status_code == 201, r.text
    body = (await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 10})).json()
    assert body["damage_dice"] == "1"
    assert body["damage_bonus"] == 0  # Forza 10, non Destrezza 16


async def test_monk_weapon_uses_dex_and_martial_die(client):
    cid = await _char(client, edition="2024", cls="monk", level=5, strength=10, dexterity=16)
    wid = await _weapon(client, cid, "Pugnale", damage_dice="1d4", weapon_category="simple", properties=["prop_light"])
    body = (await _attack(client, cid, wid, die=10)).json()
    assert body["damage_dice"] == "1d8"
    assert body["damage_bonus"] == 3
    assert body["to_hit_bonus"] == 3 + 3


async def test_non_monk_weapon_stays_strength_and_own_die(client):
    cid = await _char(client, cls="monk", level=5, strength=10, dexterity=16)
    wid = await _weapon(client, cid, "Ascia bipenne", damage_dice="1d12", weapon_category="martial",
                        properties=["prop_heavy", "prop_two_handed"])
    body = (await _attack(client, cid, wid)).json()
    assert body["damage_dice"] == "1d12"
    assert body["damage_bonus"] == 0


async def test_monk_weapon_2014_shortsword_but_not_two_handed_simple(client):
    cid = await _char(client, cls="monk", level=1, strength=10, dexterity=16)
    short = await _weapon(client, cid, "Spada corta", damage_dice="1d6", weapon_category="martial")
    body = (await _attack(client, cid, short)).json()
    assert (body["damage_dice"], body["damage_bonus"]) == ("1d6", 3)  # il d6 dell'arma resta: è più alto del d4
    great = await _weapon(client, cid, "Randello pesante", damage_dice="1d8", weapon_category="simple",
                          properties=["prop_two_handed"])
    assert (await _attack(client, cid, great, confirm_extra_attack=True)).json()["damage_bonus"] == 0


async def test_non_monk_weapon_equipped_cancels_martial_arts_on_unarmed(client):
    cid = await _char(client, cls="monk", strength=10, dexterity=16)
    await _weapon(client, cid, "Spadone", damage_dice="2d6", weapon_category="martial",
                  properties=["prop_heavy", "prop_two_handed"], equip="main_hand")
    assert (await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 10})).json()["damage_dice"] == "1"


async def test_ability_choice_on_finesse_only(client):
    cid = await _char(client, strength=16, dexterity=12)
    rapier = await _weapon(client, cid, "Stocco", properties=["prop_finesse"])
    assert (await _attack(client, cid, rapier)).json()["damage_bonus"] == 3  # senza scelta, la migliore
    chosen = (await _attack(client, cid, rapier, ability="dexterity", confirm_extra_attack=True)).json()
    assert chosen["damage_bonus"] == 1
    sword = await _weapon(client, cid, "Spada lunga")
    ignored = (await _attack(client, cid, sword, ability="dexterity", confirm_extra_attack=True)).json()
    assert ignored["damage_bonus"] == 3  # non accurata: la scelta non vale


# --- Altra mano ---------------------------------------------------------------------------------------------------

async def _two_light(client, cid, first="Pugnale", second="Spada corta", **meta) -> tuple[int, int]:
    a = await _weapon(client, cid, first, properties=["prop_light"], equip="main_hand", **meta)
    b = await _weapon(client, cid, second, properties=["prop_light"], equip="off_hand", **meta)
    return a, b


async def test_offhand_no_modifier_uses_bonus_action(client):
    cid = await _char(client, strength=16)
    _, off = await _two_light(client, cid)
    r = await _attack(client, cid, off, attack_mode="offhand")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["damage_bonus"] == 0
    assert body["to_hit_bonus"] == 3 + 2
    turn = await _turn(client, cid)
    assert turn["bonus_used"] is True
    assert turn["attacks_made"] == 0  # non consuma un attacco dell'azione
    r = await _attack(client, cid, off, attack_mode="offhand")
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "turn_slot_used")


async def test_offhand_keeps_negative_modifier(client):
    cid = await _char(client, strength=8)
    _, off = await _two_light(client, cid)
    assert (await _attack(client, cid, off, attack_mode="offhand")).json()["damage_bonus"] == -1


async def test_offhand_requires_two_light_weapons(client):
    cid = await _char(client)
    heavy = await _weapon(client, cid, "Spada lunga", equip="main_hand")
    r = await _attack(client, cid, heavy, attack_mode="offhand")
    assert (r.status_code, r.json()["detail"]) == (422, "offhand_not_light")
    alone = await _weapon(client, cid, "Pugnale", properties=["prop_light"], equip="off_hand")
    r = await _attack(client, cid, alone, attack_mode="offhand")
    assert (r.status_code, r.json()["detail"]) == (422, "offhand_needs_second_light_weapon")


# --- Pesante ------------------------------------------------------------------------------------------------------

async def test_heavy_disadvantage_2024_below_13(client):
    weak = await _char(client, edition="2024", strength=12)
    wid = await _weapon(client, weak, "Spadone", properties=["prop_heavy"])
    body = (await _attack(client, weak, wid, die=10)).json()
    assert body["mode"] == "disadvantage"
    assert "weapon:heavy" in body["notes"]
    strong = await _char(client, edition="2024", strength=13)
    wid = await _weapon(client, strong, "Spadone", properties=["prop_heavy"])
    assert (await _attack(client, strong, wid)).json()["mode"] == "normal"


async def test_heavy_ranged_reads_dexterity_2024(client):
    cid = await _char(client, edition="2024", strength=18, dexterity=10)
    wid = await _weapon(client, cid, "Arco lungo", weapon_type="ranged", properties=["prop_heavy"])
    assert (await _attack(client, cid, wid)).json()["mode"] == "disadvantage"


async def test_heavy_2014_depends_on_small_size(client):
    medium = await _char(client, race="Umano", strength=8)
    wid = await _weapon(client, medium, "Spadone", properties=["prop_heavy"])
    assert "weapon:heavy_small" not in await _keys(client, medium, wid)
    assert (await _attack(client, medium, wid)).json()["mode"] == "normal"

    small = await _char(client, race="Halfling")
    wid = await _weapon(client, small, "Spadone", properties=["prop_heavy"])
    assert (await _attack(client, small, wid)).json()["mode"] == "disadvantage"

    unknown = await _char(client, race="Razza inventata")
    wid = await _weapon(client, unknown, "Spadone", properties=["prop_heavy"])
    assert "weapon:heavy_small" in await _keys(client, unknown, wid)
    body = (await _attack(client, unknown, wid, options=["weapon:heavy_small"])).json()
    assert body["mode"] == "disadvantage"


# --- Weapon Mastery -----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name,meta,expected", [
    ("Spadone +1", {}, "graze"), ("Greatsword", {}, "graze"), ("Lancia da cavaliere", {}, "topple"),
    ("Lancia", {}, "sap"), ("Mazzafrusto", {}, "sap"), ("Mazza", {}, "sap"), ("longsword of flame", {}, "sap"),
    ("Pugnale", {}, "nick"), ("Balestra a mano", {}, "vex"), ("Balestra pesante", {}, "push"),
    ("Lama di famiglia", {}, None), ("Lama di famiglia", {"base_weapon": "greataxe"}, "cleave"),
    ("Spadone", {"base_weapon": "non_esiste"}, "graze"),
    ("Glaive", {}, "graze"), ("Falcione", {}, "graze"), ("Gliaia", {}, "graze"), ("Gliaia +1", {}, "graze"),
])
def test_weapon_mastery_table(name, meta, expected):
    assert weapon_mastery(SimpleNamespace(name=name, item_metadata=meta)) == expected


async def test_item_read_exposes_mastery(client):
    cid = await _char(client)
    await _weapon(client, cid, "Spadone")
    items = (await client.get(f"/characters/{cid}/items")).json()
    assert items[0]["mastery"] == "graze"


async def test_mastery_hidden_in_2014(client, test_session_factory, rules_catalog):
    rules_catalog(_mastery_feature("2014"))  # anche con un privilegio dichiarato per errore nel catalogo 2014
    cid = await _char(client)
    await _master(test_session_factory, cid, "greatsword")
    wid = await _weapon(client, cid, "Spadone")
    assert await _keys(client, cid, wid) == []


async def test_mastery_needs_privilege_and_chosen_weapon(client, test_session_factory, rules_catalog):
    no_privilege = await _char(client, edition="2024")
    wid = await _weapon(client, no_privilege, "Spadone")
    assert await _keys(client, no_privilege, wid) == []

    cid = await _master_char(client, test_session_factory, rules_catalog, "longsword")
    other = await _weapon(client, cid, "Spadone")
    assert await _keys(client, cid, other) == []
    sword = await _weapon(client, cid, "Spada lunga")
    assert await _keys(client, cid, sword) == ["mastery_sap"]


async def test_mastery_choice_lists_proficient_weapons_with_names(client, rules_catalog):
    rules_catalog(_mastery_feature())
    cid = await _char(client, edition="2024")
    body = (await client.get(f"/characters/{cid}")).json()
    choice = next(c for c in body["pending_choices"] if c.get("group") == "weapon_mastery")
    assert choice["count"] == 3
    names = {o["key"]: o["name"]["it"] for o in choice["options"]}
    assert names["greatsword"] == "Spadone"
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve",
                          json={"kind": "class_option", "options": ["greatsword", "longsword", "dagger"]})
    assert r.status_code == 200, r.text
    row = r.json()["classes"][0]
    assert row["options"]["weapon_mastery"] == ["greatsword", "longsword", "dagger"]


async def test_mastery_choice_melee_only(client, rules_catalog):
    rules_catalog(FeatureSpec(
        key="fighter.weapon_mastery", class_key="fighter", edition="2024", level=1, source_title="x",
        name={"it": "x", "en": "x"}, summary={"it": "x", "en": "x"}, action_type=None,
        choices=(mastery_choice({1: 2}, melee_only=True),)))
    cid = await _char(client, edition="2024")
    body = (await client.get(f"/characters/{cid}")).json()
    keys = {o["key"] for o in next(c for c in body["pending_choices"] if c.get("group") == "weapon_mastery")["options"]}
    assert "greatsword" in keys and "longbow" not in keys


async def _graze_attack(client, cid, wid, die=10) -> dict:
    r = await _attack(client, cid, wid, die=die, defer_damage=True)
    assert r.status_code == 200, r.text
    return r.json()


async def test_graze_on_miss_deals_modifier(client, test_session_factory, rules_catalog):
    cid = await _master_char(client, test_session_factory, rules_catalog, "greatsword", strength=16)
    wid = await _weapon(client, cid, "Spadone", damage_dice="2d6")
    first = await _graze_attack(client, cid, wid)
    assert first["attack_id"]
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": ["mastery_graze"]})
    assert r.status_code == 200, r.text
    attack = r.json()["attack"]
    assert attack["grazed"] is True
    assert attack["damage_rolls"] == []
    assert attack["damage_total"] == 3
    assert "attack_id" not in attack
    r = await client.post(f"/characters/{cid}/attack/{first['attack_id']}/damage", json={})
    assert r.status_code == 404  # l'attacco si è chiuso con il mancato


async def test_graze_works_on_natural_one(client, test_session_factory, rules_catalog):
    cid = await _master_char(client, test_session_factory, rules_catalog, "greatsword", strength=16)
    wid = await _weapon(client, cid, "Spadone", damage_dice="2d6")
    first = await _graze_attack(client, cid, wid, die=1)
    assert first["is_fumble"] is True
    assert first["attack_id"]
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": ["mastery_graze"]})
    assert r.json()["attack"]["damage_total"] == 3


async def test_graze_not_offered_on_critical_or_without_modifier(client, test_session_factory, rules_catalog):
    cid = await _master_char(client, test_session_factory, rules_catalog, "greatsword", strength=16)
    wid = await _weapon(client, cid, "Spadone", damage_dice="2d6")
    await _graze_attack(client, cid, wid, die=20)
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": ["mastery_graze"]})
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "option_unavailable")
    weak = await _master_char(client, test_session_factory, rules_catalog, "greatsword", strength=10)
    wid = await _weapon(client, weak, "Spadone", damage_dice="2d6")
    assert await _keys(client, weak, wid) == []


async def test_cleave_rolls_second_attack_without_modifier_once_per_turn(client, test_session_factory, rules_catalog):
    cid = await _master_char(client, test_session_factory, rules_catalog, "greataxe", strength=16, level=5)
    wid = await _weapon(client, cid, "Ascia bipenne", damage_dice="1d12")
    assert "mastery_cleave" in await _keys(client, cid, wid)
    first = (await _attack(client, cid, wid, defer_damage=True)).json()
    r = await client.post(f"/characters/{cid}/attack/{first['attack_id']}/damage", json={"options": ["mastery_cleave"]})
    assert r.status_code == 200, r.text
    body = r.json()
    block = body["option_result"]
    assert block["keys"] == ["mastery_cleave"]
    assert 1 <= block["second_die"] <= 20
    assert block["second_total"] == block["second_die"] + first["to_hit_bonus"]
    assert body["damage_total"] == first["damage_total"]  # il danno della seconda creatura è a parte
    if block["second_die"] == 1:
        assert block["separate_rolls"] == []
    else:
        assert 1 <= block["separate_total"] <= (24 if block["second_die"] == 20 else 12)  # niente Forza
    assert "mastery_cleave" not in await _keys(client, cid, wid)  # una volta per turno


async def test_nick_extra_attack_once_per_turn(client, test_session_factory, rules_catalog):
    cid = await _master_char(client, test_session_factory, rules_catalog, "dagger")
    _, off = await _two_light(client, cid, first="Spada corta", second="Pugnale")
    assert "mastery_nick" in await _keys(client, cid, off, attack_mode="offhand")
    assert "mastery_nick" not in await _keys(client, cid, off)  # solo sull'attacco extra
    r = await _attack(client, cid, off, attack_mode="offhand", options=["mastery_nick"])
    assert r.status_code == 200, r.text
    assert r.json()["damage_bonus"] == 0
    turn = await _turn(client, cid)
    assert turn["bonus_used"] is False
    assert turn["attacks_made"] == 0
    r = await _attack(client, cid, off, attack_mode="offhand", options=["mastery_nick"])
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "option_unavailable")
    r = await _attack(client, cid, off, attack_mode="offhand")  # senza Nick costa l'azione bonus
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["bonus_used"] is True


async def test_topple_reports_dc_and_sap_reports_effect(client, test_session_factory, rules_catalog):
    cid = await _master_char(client, test_session_factory, rules_catalog, "maul", "mace", strength=16)
    wid = await _weapon(client, cid, "Maglio", damage_dice="2d6")
    first = (await _attack(client, cid, wid, defer_damage=True)).json()
    r = await client.post(f"/characters/{cid}/attack/{first['attack_id']}/damage", json={"options": ["mastery_topple"]})
    effects = r.json()["option_result"]["effects"]
    assert "13" in effects[0]["it"] and "13" in effects[0]["en"]  # 8 + 3 + 2
    await client.post(f"/characters/{cid}/turn/new")
    mace = await _weapon(client, cid, "Mazza", damage_dice="1d6")
    first = (await _attack(client, cid, mace, defer_damage=True)).json()
    r = await client.post(f"/characters/{cid}/attack/{first['attack_id']}/damage", json={"options": ["mastery_sap"]})
    assert r.json()["option_result"]["effects"][0]["en"]


async def test_vex_gives_advantage_on_next_attack_until_end_of_next_turn(client, test_session_factory, rules_catalog):
    cid = await _master_char(client, test_session_factory, rules_catalog, "rapier", level=5)
    wid = await _weapon(client, cid, "Stocco", properties=["prop_finesse"])
    first = (await _attack(client, cid, wid, defer_damage=True)).json()
    r = await client.post(f"/characters/{cid}/attack/{first['attack_id']}/damage", json={"options": ["mastery_vex"]})
    assert r.status_code == 200, r.text
    assert "mastery_vex_advantage" in await _keys(client, cid, wid)
    await client.post(f"/characters/{cid}/turn/new")  # vale ancora nel turno seguente
    r = await _attack(client, cid, wid, options=["mastery_vex_advantage"])
    assert r.json()["mode"] == "advantage"
    assert "mastery_vex_advantage" not in await _keys(client, cid, wid)  # consumato

    first = (await _attack(client, cid, wid, defer_damage=True)).json()
    await client.post(f"/characters/{cid}/attack/{first['attack_id']}/damage", json={"options": ["mastery_vex"]})
    await client.post(f"/characters/{cid}/turn/new")
    await client.post(f"/characters/{cid}/turn/new")  # il turno seguente è finito
    assert "mastery_vex_advantage" not in await _keys(client, cid, wid)


# --- Ispirazione --------------------------------------------------------------------------------------------------

async def _inspired(client, edition) -> int:
    cid = await _char(client, edition=edition)
    r = await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
    assert r.status_code == 200, r.text
    return cid


async def test_inspiration_2014_advantage_2024_reroll(client):
    old = await _inspired(client, "2014")
    wid = await _weapon(client, old, "Spada")
    assert "inspiration:advantage" in await _keys(client, old, wid)
    r = await _attack(client, old, wid, with_inspiration=True)
    assert (r.status_code, r.json()["detail"]) == (409, "inspiration_before_roll")  # nel 2014 niente rilancio
    body = (await _attack(client, old, wid, options=["inspiration:advantage"])).json()
    assert body["mode"] == "advantage"
    assert "inspiration:advantage" in body["notes"]
    assert (await client.get(f"/characters/{old}")).json()["heroic_inspiration"] is False
    assert "inspiration:advantage" not in await _keys(client, old, wid)

    new = await _inspired(client, "2024")
    wid = await _weapon(client, new, "Spada")
    assert "inspiration:advantage" not in await _keys(client, new, wid)
    await _attack(client, new, wid)
    r = await _attack(client, new, wid, die=15, with_inspiration=True)
    assert r.status_code == 200, r.text
    assert r.json()["to_hit_die"] == 15
    assert (await _turn(client, new))["attacks_made"] == 1  # il rilancio è lo stesso attacco
    assert (await client.get(f"/characters/{new}")).json()["heroic_inspiration"] is False


async def test_inspiration_2014_on_skill_save_and_death(client):
    cid = await _inspired(client, "2014")
    r = await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 5, "with_inspiration": True})
    assert (r.status_code, r.json()["detail"]) == (409, "inspiration_before_roll")
    r = await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 5, "options": ["inspiration:advantage"]})
    assert r.json()["mode"] == "advantage"


# --- Dimezzare per difetto ----------------------------------------------------------------------------------------

async def test_half_up_replaced_by_floor(client):
    cid = await _char(client)
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Fuoco", "level": 1, "damage_dice": "2d6"})
    sid = r.json()["id"]
    r = await client.post(f"/characters/{cid}/spells/{sid}/roll_damage", json={"casting_level": 1, "main_rolls": [3, 4]})
    assert r.json()["half_damage"] == 3


# --- Limite di attacchi e Incapacitato ----------------------------------------------------------------------------

async def test_attack_count_enforced_with_confirm(client):
    cid = await _char(client, level=5)  # due attacchi
    wid = await _weapon(client, cid)
    for _ in range(2):
        assert (await _attack(client, cid, wid)).status_code == 200
    r = await _attack(client, cid, wid)
    assert r.status_code == 409
    assert r.json()["detail"] == {"code": "attack_limit", "made": 2, "allowed": 2}
    assert (await _turn(client, cid))["attacks_made"] == 2
    r = await _attack(client, cid, wid, confirm_extra_attack=True)  # privilegi aggiuntivi o reazione
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["attacks_made"] == 3
    assert (await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 5})).status_code == 409
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _attack(client, cid, wid)).status_code == 200


_SURGE = {"uses": Uses(table={1: 2}), "restoration": "long_rest", "on_use": OnUse(grants_action=True)}


async def _allowed(client, cid) -> int:
    return (await client.get(f"/characters/{cid}/turn-state")).json()["attacks_allowed"]


async def _surge(client, cid) -> None:
    r = await client.post(f"/characters/{cid}/features/fighter.prova/use", json={})
    assert r.status_code == 200, r.text


async def test_extra_action_attacks_need_no_confirmation(client, rules_catalog):
    await _feature_with(rules_catalog, **_SURGE)
    cid = await _char(client, level=5)  # due attacchi per azione
    wid = await _weapon(client, cid)
    for _ in range(2):
        assert (await _attack(client, cid, wid)).status_code == 200
    assert (await _attack(client, cid, wid)).status_code == 409
    await _surge(client, cid)
    assert await _allowed(client, cid) == 4
    for _ in range(2):
        r = await _attack(client, cid, wid)
        assert r.status_code == 200, r.text
    r = await _attack(client, cid, wid)
    assert r.json()["detail"] == {"code": "attack_limit", "made": 4, "allowed": 4}
    await client.post(f"/characters/{cid}/turn/new")
    assert await _allowed(client, cid) == 2


async def test_extra_action_multiplies_the_best_attack_count_once(client, rules_catalog):
    await _feature_with(rules_catalog, attacks_per_action=3, **_SURGE)
    cid = await _char(client, level=5)  # la classe ne dà 2, il privilegio 3: vale il massimo
    await _surge(client, cid)
    assert await _allowed(client, cid) == 6


async def test_extra_action_spent_elsewhere_no_longer_counts(client, rules_catalog):
    await _feature_with(rules_catalog, **_SURGE)
    cid = await _char(client, level=5)
    await _surge(client, cid)
    for _ in range(2):  # l'azione, poi quella in più
        r = await client.post(f"/characters/{cid}/turn/use", json={"slot": "action", "used": True})
        assert r.status_code == 200, r.text
    assert await _allowed(client, cid) == 2


@pytest.mark.parametrize("condition", ["incapacitated", "stunned", "unconscious", "paralyzed", "petrified"])
async def test_incapacitated_attacks_are_refused(client, condition):
    cid = await _char(client)
    wid = await _weapon(client, cid)
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {condition: True}})
    assert r.status_code == 200, r.text
    r = await _attack(client, cid, wid)
    assert (r.status_code, r.json()["detail"]) == (409, {"code": "incapacitated"})
    r = await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 5})
    assert (r.status_code, r.json()["detail"]) == (409, {"code": "incapacitated"})
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Dardo", "level": 0, "attack_save": "ATK"})
    sid = r.json()["id"]
    r = await client.post(f"/characters/{cid}/spells/{sid}/attack", json={"die": 5})
    assert (r.status_code, r.json()["detail"]) == (409, {"code": "incapacitated"})
    assert (await _turn(client, cid))["attacks_made"] == 0


# --- Afferrare e Spingere -----------------------------------------------------------------------------------------

@pytest.mark.parametrize("effect", ["grapple", "shove"])
async def test_unarmed_effect_2024_gives_dc_and_spends_attack(client, effect):
    cid = await _char(client, edition="2024", strength=16)
    r = await client.post(f"/characters/{cid}/attack/unarmed", json={"effect": effect})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["effect"] == effect
    assert body["save_dc"] == 8 + 3 + 2
    assert body["damage_total"] == 0
    assert (await _turn(client, cid))["attacks_made"] == 1
    r = await client.post(f"/characters/{cid}/attack/unarmed", json={"effect": effect})
    assert r.json()["detail"]["code"] == "attack_limit"


async def test_unarmed_effect_uses_dex_for_monk(client):
    cid = await _char(client, edition="2024", cls="monk", strength=10, dexterity=18)
    r = await client.post(f"/characters/{cid}/attack/unarmed", json={"effect": "grapple"})
    assert r.json()["save_dc"] == 8 + 4 + 2


async def test_unarmed_effect_only_in_2024(client):
    cid = await _char(client)
    r = await client.post(f"/characters/{cid}/attack/unarmed", json={"effect": "grapple"})
    assert (r.status_code, r.json()["detail"]) == (422, "unarmed_effect_2024_only")


async def test_plain_unarmed_response_has_no_effect_fields(client):
    cid = await _char(client, edition="2024")
    body = (await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 10})).json()
    assert "effect" not in body and "save_dc" not in body and "grazed" not in body

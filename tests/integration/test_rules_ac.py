"""CA secondo l'armatura: calcolo, Difesa Senza Armatura dai privilegi, migrazione una tantum."""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.db.engine import _migrate_armor_class
from core.db.models import AbilityScore, Character, EquipmentSlot, Item
from core.rules.sample_characters import SAMPLE_SPECS, _spec, build_rules_character
from core.rules.types import FeatureSpec, UnarmoredAc


async def _new(client, class_name: str | None = None, **scores) -> int:
    body = {"name": "Prova"}
    if class_name:
        body["initial_class"] = {"class_name": class_name}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for ability, value in scores.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    return cid


async def _equip(client, cid: int, slot: str = "body", **fields) -> dict:
    r = await client.post(f"/characters/{cid}/items", json=fields)
    assert r.status_code == 201, r.text
    item = next(i for i in r.json()["items"] if i["name"] == fields["name"])
    r = await client.patch(f"/characters/{cid}/items/{item['id']}", json={"is_equipped": True, "equipment_slot": slot})
    assert r.status_code == 200, r.text
    return {**r.json(), "item_id": item["id"]}


def _armor(armor_type: str | None, value: int) -> dict:
    meta = {"ac_value": value, **({"armor_type": armor_type} if armor_type else {})}
    return {"name": f"Armatura {armor_type}", "item_type": "armor", "item_metadata": meta}


SHIELD = {"name": "Scudo", "item_type": "shield", "item_metadata": {"ac_bonus": 2}}


def _unarmored_spec(class_key: str, **unarmored) -> FeatureSpec:
    return FeatureSpec(
        key=f"{class_key}.unarmored", class_key=class_key, edition="2014", level=1, source_title="Prova",
        name={"it": "Difesa", "en": "Defense"}, summary={"it": "x", "en": "x"}, action_type=None, passive=True,
        unarmored=UnarmoredAc(**unarmored),
    )


async def test_light_armor_adds_dex(client):
    cid = await _new(client, dexterity=18)
    body = await _equip(client, cid, **_armor("light", 11))
    assert body["ac_breakdown"]["base"] == 15  # 11 + 4


async def test_medium_armor_caps_dex_at_two(client):
    cid = await _new(client, dexterity=18)
    body = await _equip(client, cid, **_armor("medium", 14))
    assert body["ac_breakdown"]["base"] == 16  # 14 + min(4, 2)


async def test_medium_armor_keeps_negative_dex(client):
    cid = await _new(client, dexterity=8)
    body = await _equip(client, cid, **_armor("medium", 14))
    assert body["ac_breakdown"]["base"] == 13


async def test_heavy_armor_ignores_dex(client):
    cid = await _new(client, dexterity=18)
    body = await _equip(client, cid, **_armor("heavy", 18))
    assert body["ac_breakdown"]["base"] == 18


async def test_armor_without_type_or_with_bad_value_never_breaks_the_sheet(client):
    cid = await _new(client, dexterity=18)
    assert (await _equip(client, cid, **_armor(None, 16)))["ac_breakdown"]["base"] == 16
    body = await _equip(client, cid, name="Rotta", item_type="armor", item_metadata={"ac_value": "boh", "armor_type": "heavy"})
    assert body["ac_breakdown"]["base"] == 10


async def test_no_armor_is_ten_plus_dex(client):
    cid = await _new(client, dexterity=16)
    r = await client.get(f"/characters/{cid}")
    assert r.json()["ac_breakdown"]["base"] == 13
    assert r.json()["ac"] == 13


async def test_unequip_returns_to_ten_plus_dex(client):
    cid = await _new(client, dexterity=16)
    equipped = await _equip(client, cid, **_armor("light", 11))
    r = await client.patch(f"/characters/{cid}/items/{equipped['item_id']}", json={"is_equipped": False})
    assert r.json()["ac_breakdown"]["base"] == 13


async def test_dex_item_recomputes_ac(client):
    cid = await _new(client, dexterity=10)
    await _equip(client, cid, **_armor("light", 11))
    belt = await _equip(client, cid, slot="ring1", name="Anello", item_type="accessory", item_metadata={
        "ability_modifiers": [{"ability": "dexterity", "kind": "absolute", "value": 18}]})
    assert belt["ac_breakdown"]["base"] == 15
    r = await client.patch(f"/characters/{cid}/items/{belt['item_id']}", json={"is_equipped": False})
    assert r.json()["ac_breakdown"]["base"] == 11


async def test_dex_score_change_recomputes_ac(client):
    cid = await _new(client, dexterity=10)
    await _equip(client, cid, **_armor("light", 12))
    r = await client.patch(f"/characters/{cid}/ability_scores/dexterity", json={"value": 14})
    assert r.json()["ac_breakdown"]["base"] == 14


async def test_manual_override_survives_dex_and_armor(client):
    cid = await _new(client, dexterity=18)
    await client.patch(f"/characters/{cid}/ac", json={"base": 20})
    body = await _equip(client, cid, **_armor("light", 11))
    assert body["ac_breakdown"]["base"] == 20
    r = await client.patch(f"/characters/{cid}/ability_scores/dexterity", json={"value": 10})
    assert r.json()["ac_breakdown"]["base"] == 20
    r = await client.post(f"/characters/{cid}/ac/reset-override")
    assert r.json()["ac_breakdown"]["base"] == 11  # armatura leggera + DES 0


async def test_monk_unarmored_only_without_armor_and_shield(client, rules_catalog):
    rules_catalog(_unarmored_spec("monk", abilities=("dexterity", "wisdom"), no_shield=True))
    cid = await _new(client, "monk", dexterity=16, wisdom=16)
    r = await client.get(f"/characters/{cid}")
    assert r.json()["ac_breakdown"]["base"] == 16  # 10 + 3 + 3
    assert r.json()["unarmored_formula"] == ["dexterity", "wisdom"]

    shield = await _equip(client, cid, slot="off_hand", **SHIELD)
    assert shield["ac_breakdown"]["base"] == 13  # con lo scudo: 10 + DES
    assert shield["unarmored_formula"] is None
    r = await client.patch(f"/characters/{cid}/items/{shield['item_id']}", json={"is_equipped": False})
    assert r.json()["ac_breakdown"]["base"] == 16

    armor = await _equip(client, cid, **_armor("light", 11))
    assert armor["ac_breakdown"]["base"] == 14
    assert armor["unarmored_formula"] is None


async def test_barbarian_unarmored_keeps_shield(client, rules_catalog):
    rules_catalog(_unarmored_spec("barbarian", abilities=("dexterity", "constitution")))
    cid = await _new(client, "barbarian", dexterity=14, constitution=16)
    body = await _equip(client, cid, slot="off_hand", **SHIELD)
    assert body["ac_breakdown"]["base"] == 15  # 10 + 2 + 3
    assert body["ac"] == 17


async def test_unarmored_never_worse_than_ten_plus_dex(client, rules_catalog):
    rules_catalog(_unarmored_spec("monk", abilities=("dexterity", "wisdom"), no_shield=True))
    cid = await _new(client, "monk", dexterity=16, wisdom=8)
    assert (await client.get(f"/characters/{cid}")).json()["ac_breakdown"]["base"] == 13


async def test_unarmored_formula_with_fixed_base(client, rules_catalog):
    rules_catalog(_unarmored_spec("sorcerer", abilities=("dexterity",), base=13))
    cid = await _new(client, "sorcerer", dexterity=14)
    assert (await client.get(f"/characters/{cid}")).json()["ac_breakdown"]["base"] == 15


async def test_manual_toggle_uses_effective_scores(client):
    cid = await _new(client, dexterity=10, wisdom=14)
    r = await client.post(f"/characters/{cid}/ac/unarmored-defense", json={"ability": "wisdom"})
    assert r.json()["ac_breakdown"]["base"] == 12
    body = await _equip(client, cid, slot="ring1", name="Anello", item_type="accessory", item_metadata={
        "ability_modifiers": [{"ability": "dexterity", "kind": "absolute", "value": 18}]})
    assert body["ac_breakdown"]["base"] == 16


# --- Migrazione -------------------------------------------------------------------------------

async def _character(factory, *, base: int, dex: int = 18, items=(), **fields) -> int:
    settings = fields.pop("settings", {})
    override = fields.pop("override", False)
    async with factory() as s:
        char = await build_rules_character(
            s, _spec("Migrazione", [("Guerriero", 5, None, 10)], base_ac=base, ac_override=override, settings=settings), 1)
        next(a for a in char.ability_scores if a.name == "dexterity").value = dex
        for name, value in fields.items():
            setattr(char, name, value)
        for it in items:
            s.add(Item(character_id=char.id, **it))
        await s.commit()
        return char.id


async def _migrated(factory, cid: int) -> Character:
    async with factory() as s:
        await (await s.connection()).run_sync(_migrate_armor_class)
        await s.commit()
    async with factory() as s:
        return (await s.execute(select(Character).where(Character.id == cid).options(
            selectinload(Character.ability_scores), selectinload(Character.items)))).scalar_one()


def _worn(armor_type: str, value: int) -> dict:
    return dict(name="Armatura", item_type="armor", is_equipped=True, equipment_slot=EquipmentSlot.BODY,
                item_metadata=json.dumps({"ac_value": value, "armor_type": armor_type}))


async def test_migration_keeps_displayed_ac_for_manual_value(test_session_factory):
    cid = await _character(test_session_factory, base=18, dex=14)
    char = await _migrated(test_session_factory, cid)
    assert char.base_armor_class == 18 and char.base_armor_class_override is True
    assert char.settings["ac_migrated"] is True


async def test_migration_keeps_ddb_ac_with_dex(test_session_factory):
    """La CA da Beyond include già la Destrezza: 17 resta 17, non 17 + 4 né 10 + 4."""
    spec = next(s for s in SAMPLE_SPECS if s["name"].endswith("CA da Beyond"))
    assert spec["base_ac"] == 17 and spec["scores"]["dexterity"] == 18
    async with test_session_factory() as s:
        cid = (await build_rules_character(s, spec, 1)).id
        await s.commit()
    char = await _migrated(test_session_factory, cid)
    assert char.base_armor_class == 17 and char.base_armor_class_override is True


async def test_migration_import_marker_keeps_value_even_if_it_looks_derived(test_session_factory):
    cid = await _character(test_session_factory, base=10, settings={"import_source": "dndbeyond"})
    char = await _migrated(test_session_factory, cid)
    assert char.base_armor_class == 10 and char.base_armor_class_override is True


async def test_migration_keeps_ddb_light_armor_value_with_dex(test_session_factory):
    """Senza marcatore (i personaggi DDB reali non ne hanno): 15 ≠ 11, si conserva. E coincide col calcolo."""
    cid = await _character(test_session_factory, base=15, items=[_worn("light", 11)])
    char = await _migrated(test_session_factory, cid)
    assert char.base_armor_class == 15 and char.base_armor_class_override is False


async def test_migration_armor_copied_without_dex_moves_to_new_formula(test_session_factory):
    cid = await _character(test_session_factory, base=11, items=[_worn("light", 11)])
    char = await _migrated(test_session_factory, cid)
    assert char.base_armor_class == 15 and char.base_armor_class_override is False


async def test_migration_default_ten_without_armor_moves_to_new_formula(test_session_factory):
    cid = await _character(test_session_factory, base=10)
    char = await _migrated(test_session_factory, cid)
    assert char.base_armor_class == 14 and char.base_armor_class_override is False


async def test_migration_armor_value_that_may_include_dex_is_kept(test_session_factory):
    """Un'armatura leggera da 15 non esiste senza bonus: il valore può già contenere la Destrezza."""
    cid = await _character(test_session_factory, base=15, dex=14, items=[_worn("light", 15)])
    char = await _migrated(test_session_factory, cid)
    assert char.base_armor_class == 15 and char.base_armor_class_override is True


async def test_migration_keeps_existing_override(test_session_factory):
    cid = await _character(test_session_factory, base=18, override=True, items=[_worn("light", 11)])
    char = await _migrated(test_session_factory, cid)
    assert char.base_armor_class == 18 and char.base_armor_class_override is True


async def test_migration_toggle_with_armor_keeps_displayed_ac(test_session_factory):
    cid = await _character(test_session_factory, base=16, dex=16, items=[_worn("heavy", 18)],
                           unarmored_defense_ability="wisdom")
    char = await _migrated(test_session_factory, cid)
    assert char.base_armor_class == 16 and char.base_armor_class_override is True
    assert char.unarmored_defense_ability == "wisdom"


async def test_migration_toggle_without_armor_stays_automatic(test_session_factory):
    cid = await _character(test_session_factory, base=12, dex=14, unarmored_defense_ability="wisdom")
    char = await _migrated(test_session_factory, cid)
    assert char.base_armor_class == 14 and char.base_armor_class_override is False  # 10 + 2 + SAG 14 (+2)


async def test_migration_is_one_shot(test_session_factory):
    cid = await _character(test_session_factory, base=10)
    char = await _migrated(test_session_factory, cid)
    assert char.base_armor_class == 14
    async with test_session_factory() as s:
        row = await s.get(Character, cid)
        row.base_armor_class = 19  # un valore successivo non viene più toccato dalla migrazione
        await s.commit()
    char = await _migrated(test_session_factory, cid)
    assert char.base_armor_class == 19 and char.base_armor_class_override is False


async def test_character_created_after_migration_is_not_pinned_at_next_startup(client, test_session_factory):
    cid = await _new(client, dexterity=18)
    await _equip(client, cid, **_armor("light", 11))
    char = await _migrated(test_session_factory, cid)
    assert char.base_armor_class == 15 and char.base_armor_class_override is False
    r = await client.patch(f"/characters/{cid}/ability_scores/dexterity", json={"value": 10})
    assert r.json()["ac_breakdown"]["base"] == 11


async def test_first_read_of_unmigrated_character_keeps_manual_value(client, test_session_factory):
    """Personaggi arrivati dopo l'avvio senza passare dalla migrazione: la prima lettura non deve perdere la CA."""
    async with test_session_factory() as s:
        char = Character(user_id=1234, name="Vecchio", base_armor_class=17, hit_points=10, current_hit_points=10)
        char.ability_scores = [AbilityScore(name="dexterity", value=18)]
        s.add(char)
        await s.commit()
        cid = char.id
    body = (await client.get(f"/characters/{cid}")).json()
    assert body["ac_breakdown"]["base"] == 17 and body["base_armor_class_override"] is True


async def test_import_of_old_export_keeps_value_with_dex(client):
    cid = await _new(client, dexterity=18)
    data = (await client.get(f"/characters/{cid}/export")).json()
    data["character"]["base_armor_class"] = 17
    data["character"]["settings"] = {}
    r = await client.post("/characters/import", json=data)
    assert r.status_code in (200, 201), r.text
    new_id = r.json()["id"]
    body = (await client.get(f"/characters/{new_id}")).json()
    assert body["ac_breakdown"]["base"] == 17 and body["base_armor_class_override"] is True


async def test_export_after_migration_roundtrips_computed_ac(client):
    cid = await _new(client, dexterity=18)
    await _equip(client, cid, **_armor("light", 11))
    data = (await client.get(f"/characters/{cid}/export")).json()
    r = await client.post("/characters/import", json=data)
    assert r.status_code in (200, 201), r.text
    body = (await client.get(f"/characters/{r.json()['id']}")).json()
    assert body["ac_breakdown"]["base"] == 15 and body["base_armor_class_override"] is False

"""Sync delle feature di classe dal catalogo per edizione: nessuna perdita di dati."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from api.services.class_features import sync_class_feature_abilities
from core.db.models import Ability, AbilityScore, Character, CharacterClass, EquipmentSlot, Item
from core.rules.catalog import active_features
from core.rules.sample_characters import SAMPLE_SPECS, build_rules_character
from core.rules.types import FeatureSpec, Uses
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user
from tests.integration._telegram_stub import install_fake_telegram
from tests.integration.test_campaigns_api import _enrolled, act
from tests.integration.test_session_trade import PLAYER2_ID, _seed_trade


def _spec(key, edition="2014", uses=None, **kw) -> FeatureSpec:
    name = kw.pop("name", key)
    return FeatureSpec(
        key=key, class_key=key.split(".")[0], edition=edition, level=kw.pop("level", 1), source_title=name,
        name={"it": f"{name} it", "en": f"{name} en"}, summary=kw.pop("summary", {"it": f"{key} {edition} it", "en": f"{key} {edition} en"}),
        action_type="bonus_action", uses=uses, **kw)


async def _char(s, class_name="bard", level=1, subclass=None, subclass_key=None, cha=10, edition="2014"):
    char = Character(user_id=1, name="Prova", rules_edition=edition)
    char.ability_scores = [AbilityScore(name="charisma", value=cha)]
    char.items, char.abilities = [], []
    cls = CharacterClass(class_name=class_name, level=level, subclass=subclass, subclass_key=subclass_key)
    char.classes = [cls]
    s.add(char)
    await s.flush()
    return char, cls


def _row(char, key):
    return next((a for a in char.abilities if a.feature_key == key), None)


# --- filtro dei privilegi attivi -----------------------------------------------------------------

def test_active_features_filters_level_subclass_and_options(rules_catalog):
    rules_catalog(_spec("fighter.base", level=3), _spec("fighter.dice", subclass="battle_master"),
                  _spec("fighter.style", option_group="style", option_key="archery"))

    def keys(level=3, **kw):
        row = SimpleNamespace(class_name="fighter", level=level, subclass_key=kw.get("subclass_key"), options=kw.get("options"))
        return [s.key for s, r in active_features(SimpleNamespace(rules_edition="2014", classes=[row])) if r is row]

    assert keys(level=2) == []
    assert keys() == ["fighter.base"]
    assert keys(subclass_key="battle_master") == ["fighter.base", "fighter.dice"]
    assert keys(subclass_key="champion") == ["fighter.base"]
    assert keys(options={"style": ["archery"]}) == ["fighter.base", "fighter.style"]
    assert keys(options={"style": ["defense"]}) == ["fighter.base"]


def test_active_features_ignores_custom_class_and_other_edition(rules_catalog):
    rules_catalog(_spec("fighter.base"))
    custom = SimpleNamespace(class_name="Cacciatore di Taglie", level=5, subclass_key=None)
    assert active_features(SimpleNamespace(rules_edition="2014", classes=[custom])) == []
    row = SimpleNamespace(class_name="fighter", level=5, subclass_key=None)
    assert active_features(SimpleNamespace(rules_edition="2024", classes=[row])) == []


# --- sync ----------------------------------------------------------------------------------------

async def test_sync_updates_restoration_type(test_session_factory, rules_catalog):
    # Ispirazione Bardica 2014: lungo al 4, breve al 5
    rules_catalog(_spec("bard.bardic_inspiration", uses=Uses(ability="charisma"),
                        restoration={1: "long_rest", 5: "short_rest"}))
    async with test_session_factory() as s:
        char, cls = await _char(s, level=4, cha=16)
        await sync_class_feature_abilities(s, char, cls)
        row = _row(char, "bard.bardic_inspiration")
        assert row.restoration_type == "long_rest" and row.max_uses == 3 and row.is_class_feature
        cls.level = 5
        await sync_class_feature_abilities(s, char, cls)
        assert row.restoration_type == "short_rest"


async def test_legacy_row_follows_catalog_restoration(test_session_factory, rules_catalog):
    """Un personaggio esistente (Ispirazione breve, riga cha_based) riceve la correzione."""
    async with test_session_factory() as s:
        char, cls = await _char(s, level=3, cha=16)
        await sync_class_feature_abilities(s, char, cls)  # catalogo vuoto: CLASS_RESOURCES
        row = _row(char, "bard.bardic_inspiration")
        assert row.restoration_type == "short_rest"
        await s.flush()
        row.uses = 1
        rules_catalog(_spec("bard.bardic_inspiration", uses=Uses(ability="charisma"),
                            restoration={1: "long_rest", 5: "short_rest"}))
        await sync_class_feature_abilities(s, char, cls)
        assert _row(char, "bard.bardic_inspiration") is row
        assert row.restoration_type == "long_rest" and (row.max_uses, row.uses) == (3, 1)


async def test_sync_removes_feature_only_with_recognized_subclass(test_session_factory, rules_catalog):
    """Dadi Superiorità di un Campione: spariscono; quelli del Maestro di Battaglia restano."""
    dice = _spec("fighter.superiority_dice", uses=Uses(table={3: 4}), subclass="battle_master")
    surge = _spec("fighter.action_surge", uses=Uses(table={2: 1}))
    async with test_session_factory() as s:
        for sub, kept in (("champion", False), ("battle_master", True)):
            char, cls = await _char(s, "fighter", 5, subclass=sub, subclass_key=sub)
            await sync_class_feature_abilities(s, char, cls)  # righe legacy di tutti i guerrieri
            await s.flush()
            assert _row(char, "fighter.superiority_dice") is not None
            rules_catalog(dice, surge)
            await sync_class_feature_abilities(s, char, cls)
            await s.flush()
            assert (_row(char, "fighter.superiority_dice") is not None) is kept, sub
            assert _row(char, "fighter.action_surge") is not None
            rules_catalog.clear()


async def test_sync_keeps_features_with_unknown_subclass(test_session_factory, rules_catalog):
    dice = _spec("fighter.superiority_dice", uses=Uses(table={3: 4}), subclass="battle_master")
    async with test_session_factory() as s:
        char, cls = await _char(s, "fighter", 5, subclass="Scuola Inventata")
        await sync_class_feature_abilities(s, char, cls)
        await s.flush()
        row = _row(char, "fighter.superiority_dice")
        row.uses, before = 1, row.max_uses
        rules_catalog(dice)
        await sync_class_feature_abilities(s, char, cls)
        await s.flush()
        assert _row(char, "fighter.superiority_dice") is row
        assert (row.max_uses, row.uses) == (before, 1)


async def test_sync_removes_base_feature_below_level_and_restores_it(test_session_factory, rules_catalog):
    rules_catalog(_spec("fighter.action_surge", uses=Uses(table={2: 2}), level=2))
    async with test_session_factory() as s:
        char, cls = await _char(s, "fighter", 5)
        await sync_class_feature_abilities(s, char, cls)
        await s.flush()
        row = _row(char, "fighter.action_surge")
        row.uses, row.description = 1, "Mia nota"
        cls.level = 1
        await sync_class_feature_abilities(s, char, cls)
        await s.flush()
        assert _row(char, "fighter.action_surge") is None
        cls.level = 5
        await sync_class_feature_abilities(s, char, cls)
        await s.flush()
        back = _row(char, "fighter.action_surge")
        assert (back.description, back.uses, back.max_uses) == ("Mia nota", 1, 2)


async def test_sync_preserves_spent_uses_and_description(test_session_factory, rules_catalog):
    rules_catalog(_spec("barbarian.rage", uses=Uses(table={1: 2, 3: 3})))
    async with test_session_factory() as s:
        char, cls = await _char(s, "barbarian", 1)
        await sync_class_feature_abilities(s, char, cls)
        await s.flush()
        row = _row(char, "barbarian.rage")
        row.uses, row.description = 0, "Testo mio"
        cls.level = 3
        await sync_class_feature_abilities(s, char, cls)
        assert (row.max_uses, row.uses, row.description) == (3, 1, "Testo mio")
        await sync_class_feature_abilities(s, char, cls)  # idempotente
        assert (row.max_uses, row.uses) == (3, 1)


async def test_sync_never_touches_feat_and_user_rows(test_session_factory, rules_catalog):
    rules_catalog(_spec("fighter.action_surge", uses=Uses(table={2: 1})))
    async with test_session_factory() as s:
        char, cls = await _char(s, "fighter", 5)
        feat = Ability(character_id=char.id, name="Fortunato", feature_key="feat.lucky", max_uses=3, uses=1)
        user = Ability(character_id=char.id, name="Mia", description="d", max_uses=9, uses=2)
        odd = Ability(character_id=char.id, name="Importata", feature_key="custom", is_class_feature=True,
                      source_class_id=cls.id, max_uses=4, uses=4)
        char.abilities.extend([feat, user, odd])
        await s.flush()
        await sync_class_feature_abilities(s, char, cls)
        await s.flush()
        assert (feat.name, feat.max_uses, feat.uses) == ("Fortunato", 3, 1)
        assert (user.name, user.description, user.max_uses, user.uses) == ("Mia", "d", 9, 2)
        assert odd in char.abilities and odd.max_uses == 4


async def test_description_follows_edition_unless_edited(test_session_factory, rules_catalog):
    rules_catalog(_spec("barbarian.rage", uses=Uses(table={1: 2})), _spec("barbarian.rage", "2024", uses=Uses(table={1: 2})))
    async with test_session_factory() as s:
        char, cls = await _char(s, "barbarian", 1)
        await sync_class_feature_abilities(s, char, cls)
        row = _row(char, "barbarian.rage")
        assert row.description == "barbarian.rage 2014 it"
        char.rules_edition = "2024"
        await sync_class_feature_abilities(s, char, cls)
        assert row.description == "barbarian.rage 2024 it"


async def test_counterless_feature_has_no_restoration_and_unlimited_keeps_it(test_session_factory, rules_catalog):
    """Criterio dell'etichetta «illimitato»: ricarica presente e nessun massimo."""
    rules_catalog(_spec("rogue.cunning_action", restoration="short_rest"),
                  _spec("rogue.tricks", uses=Uses(table={1: 2}, unlimited_from=5), restoration="long_rest"))
    async with test_session_factory() as s:
        char, cls = await _char(s, "rogue", 5)
        await sync_class_feature_abilities(s, char, cls)
        cunning, tricks = _row(char, "rogue.cunning_action"), _row(char, "rogue.tricks")
        assert cunning.max_uses is None and cunning.restoration_type == "none"
        assert tricks.max_uses is None and tricks.restoration_type == "long_rest"


async def test_passive_feature_row_has_no_counter(test_session_factory, rules_catalog):
    rules_catalog(_spec("rogue.sneak", passive=True))
    async with test_session_factory() as s:
        char, cls = await _char(s, "rogue", 1)
        await sync_class_feature_abilities(s, char, cls)
        row = _row(char, "rogue.sneak")
        assert row.is_passive and row.max_uses is None and row.uses is None


async def test_unlimited_drops_counter_and_restores_spent(test_session_factory, rules_catalog):
    rules_catalog(_spec("barbarian.rage", uses=Uses(table={1: 6}, unlimited_from=20)))
    async with test_session_factory() as s:
        char, cls = await _char(s, "barbarian", 19)
        await sync_class_feature_abilities(s, char, cls)
        row = _row(char, "barbarian.rage")
        row.uses = 4
        cls.level = 20
        await sync_class_feature_abilities(s, char, cls)
        assert row.max_uses is None and row.uses is None
        cls.level = 19
        await sync_class_feature_abilities(s, char, cls)
        assert (row.max_uses, row.uses) == (6, 4)


async def test_multiclass_proficiency_uses_follow_other_class_level(test_session_factory, rules_catalog):
    rules_catalog(_spec("bard.tricks", uses=Uses(proficiency=True)))
    async with test_session_factory() as s:
        char, bard = await _char(s, "bard", 4)
        await sync_class_feature_abilities(s, char, bard)
        assert _row(char, "bard.tricks").max_uses == 2
        fighter = CharacterClass(character_id=char.id, class_name="fighter", level=1)
        char.classes.append(fighter)
        await s.flush()
        await sync_class_feature_abilities(s, char, fighter)
        assert _row(char, "bard.tricks").max_uses == 3


async def test_custom_class_without_catalog_does_nothing(test_session_factory, rules_catalog):
    rules_catalog(_spec("fighter.action_surge", uses=Uses(table={2: 1})))
    async with test_session_factory() as s:
        char, cls = await _char(s, "Cacciatore di Taglie", 5)
        await sync_class_feature_abilities(s, char, cls)
        assert char.abilities == []


async def test_sample_builder_creates_feature_rows(test_session_factory, rules_catalog):
    spec = next(s for s in SAMPLE_SPECS if s["name"] == "[prova] Usi spesi")
    async with test_session_factory() as s:
        char = await build_rules_character(s, spec, 99)
        rows = (await s.execute(select(Ability).where(Ability.character_id == char.id))).scalars().all()
        rage = [a for a in rows if a.feature_key == "barbarian.rage"]
        assert len(rage) == 1 and rage[0].uses < rage[0].max_uses


# --- endpoint ------------------------------------------------------------------------------------

async def _api_char(client, class_name="bard", level=1, **cls_kw) -> tuple[int, dict]:
    r = await client.post("/characters", json={"name": "Prova", "initial_class": {"class_name": class_name, "level": level, **cls_kw}})
    assert r.status_code == 201, r.text
    return r.json()["id"], r.json()


def _by_key(body: dict, key: str) -> dict | None:
    return next((a for a in body["abilities"] if a["feature_key"] == key), None)


async def _get(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


async def test_edition_roundtrip_keeps_data(client, rules_catalog):
    rules_catalog(
        _spec("barbarian.rage", uses=Uses(table={1: 3})),
        _spec("barbarian.rage", "2024", uses=Uses(table={1: 2})),
        _spec("barbarian.old", uses=Uses(table={1: 4})),  # esiste solo nel 2014
        _spec("barbarian.new", "2024", uses=Uses(table={1: 1})),  # esiste solo nel 2024
    )
    cid, body = await _api_char(client, "barbarian", 1, subclass="Cammino del Combattente Totemico")
    rage, old = _by_key(body, "barbarian.rage"), _by_key(body, "barbarian.old")
    assert _by_key(body, "barbarian.new") is None
    await client.patch(f"/characters/{cid}/abilities/{rage['id']}", json={"uses": 2, "description": "Ira mia"})
    await client.patch(f"/characters/{cid}/abilities/{old['id']}", json={"uses": 1, "description": "Vecchio mio"})

    r = await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert _by_key(body, "barbarian.old") is None and _by_key(body, "barbarian.new") is not None
    now = _by_key(body, "barbarian.rage")
    assert (now["max_uses"], now["uses"], now["description"]) == (2, 1, "Ira mia")  # 1 speso resta speso
    assert body["classes"][0]["subclass"] == "Cammino del Combattente Totemico"
    assert body["classes"][0]["subclass_key"] is None

    body = (await client.patch(f"/characters/{cid}", json={"rules_edition": "2014"})).json()
    now = _by_key(body, "barbarian.rage")
    assert (now["max_uses"], now["uses"], now["description"]) == (3, 2, "Ira mia")
    back = _by_key(body, "barbarian.old")
    assert (back["max_uses"], back["uses"], back["description"]) == (4, 1, "Vecchio mio")
    assert _by_key(body, "barbarian.new") is None
    assert body["classes"][0]["subclass_key"] == "totem_warrior"


async def test_edition_change_clamps_spent_to_new_max(client, rules_catalog):
    rules_catalog(_spec("barbarian.rage", uses=Uses(table={1: 5})), _spec("barbarian.rage", "2024", uses=Uses(table={1: 2})))
    cid, body = await _api_char(client, "barbarian")
    rage = _by_key(body, "barbarian.rage")
    await client.patch(f"/characters/{cid}/abilities/{rage['id']}", json={"uses": 1})
    now = _by_key((await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).json(), "barbarian.rage")
    assert (now["max_uses"], now["uses"]) == (2, 0)


async def test_archive_survives_stale_settings_snapshot(client, rules_catalog):
    rules_catalog(_spec("barbarian.old", uses=Uses(table={1: 4})), _spec("barbarian.rage", "2024", uses=Uses(table={1: 2})))
    cid, body = await _api_char(client, "barbarian")
    old = _by_key(body, "barbarian.old")
    await client.patch(f"/characters/{cid}/abilities/{old['id']}", json={"uses": 1})
    await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})
    await client.patch(f"/characters/{cid}", json={"settings": {}})  # il client rimanda una copia vecchia
    body = (await client.patch(f"/characters/{cid}", json={"rules_edition": "2014"})).json()
    assert _by_key(body, "barbarian.old")["uses"] == 1


async def test_edition_change_without_catalog_changes_nothing(client, rules_catalog):
    cid, body = await _api_char(client, "fighter", 5)
    rows = sorted(body["abilities"], key=lambda a: a["id"])
    assert rows
    body = (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).json()
    assert sorted(body["abilities"], key=lambda a: a["id"]) == rows


async def test_subclass_change_syncs_catalog(client, rules_catalog):
    rules_catalog(_spec("fighter.superiority_dice", uses=Uses(table={3: 4}), subclass="battle_master"))
    cid, body = await _api_char(client, "fighter", 5)
    cls_id = body["classes"][0]["id"]
    assert _by_key(body, "fighter.superiority_dice") is None
    body = (await client.patch(f"/characters/{cid}/classes/{cls_id}", json={"subclass": "Maestro di Battaglia"})).json()
    assert _by_key(body, "fighter.superiority_dice")["max_uses"] == 4
    body = (await client.patch(f"/characters/{cid}/classes/{cls_id}", json={"subclass": "Campione"})).json()
    assert _by_key(body, "fighter.superiority_dice") is None


async def test_ability_change_and_equip_update_uses(client, rules_catalog):
    rules_catalog(_spec("bard.bardic_inspiration", uses=Uses(ability="charisma")))
    cid, body = await _api_char(client, "bard")
    assert _by_key(body, "bard.bardic_inspiration")["max_uses"] == 1
    r = await client.patch(f"/characters/{cid}/ability_scores/charisma", json={"value": 16})
    assert r.status_code == 200, r.text
    assert _by_key(r.json(), "bard.bardic_inspiration")["max_uses"] == 3
    meta = {"ability_modifiers": [{"ability": "charisma", "kind": "absolute", "value": 20}]}
    r = await client.post(f"/characters/{cid}/items", json={"name": "Fascia", "item_type": "wondrous", "item_metadata": meta})
    assert r.status_code in (200, 201), r.text
    item = next(i for i in r.json()["items"] if i["name"] == "Fascia")
    r = await client.patch(f"/characters/{cid}/items/{item['id']}", json={"is_equipped": True})
    assert r.status_code == 200, r.text
    assert _by_key(r.json(), "bard.bardic_inspiration")["max_uses"] == 5
    r = await client.patch(f"/characters/{cid}/items/{item['id']}", json={"is_equipped": False})
    assert _by_key(r.json(), "bard.bardic_inspiration")["max_uses"] == 3


CHA_BAND = {"ability_modifiers": [{"ability": "charisma", "kind": "absolute", "value": 20}]}


async def test_add_equipped_and_delete_item_update_uses(client, rules_catalog):
    rules_catalog(_spec("bard.bardic_inspiration", uses=Uses(ability="charisma")))
    cid, _ = await _api_char(client, "bard")
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Fascia", "item_type": "wondrous", "item_metadata": CHA_BAND, "is_equipped": True})
    assert r.status_code == 201, r.text
    assert _by_key(r.json(), "bard.bardic_inspiration")["max_uses"] == 5
    item = next(i for i in r.json()["items"] if i["name"] == "Fascia")
    r = await client.delete(f"/characters/{cid}/items/{item['id']}")
    assert r.status_code == 200, r.text
    assert _by_key(r.json(), "bard.bardic_inspiration")["max_uses"] == 1


async def test_session_trade_of_worn_item_updates_uses(client, test_session_factory, rules_catalog, monkeypatch):
    install_fake_telegram(monkeypatch)
    rules_catalog(_spec("fighter.vigor", uses=Uses(ability="constitution")))
    sid, hero, _lyra, item_id = await _seed_trade(test_session_factory, equipped_con=True)
    async with test_session_factory() as s:
        score = (await s.execute(select(AbilityScore).where(
            AbilityScore.character_id == hero, AbilityScore.name == "constitution"))).scalar_one()
        score.value = 14  # 16 con l'anello: 3 usi; senza: 2
        await s.commit()
    as_user(PLAYER_ID)
    r = await client.post(f"/sessions/{sid}/trade", json={
        "from_character_id": hero, "to_user_id": PLAYER2_ID, "item_id": item_id})
    assert r.status_code == 200, r.text
    assert _by_key(r.json(), "fighter.vigor")["max_uses"] == 2


async def test_stash_put_of_worn_item_updates_uses(client, test_session_factory, rules_catalog):
    rules_catalog(_spec("wizard.tricks", uses=Uses(ability="charisma")))
    camp, pg = await _enrolled(client, test_session_factory)
    act(GM_ID)
    sid = (await client.post("/sessions", json={"campaign_id": camp["id"]})).json()["id"]
    act(PLAYER_ID)
    assert (await client.post(f"/campaigns/{camp['id']}/session/join", json={"character_id": pg})).status_code == 200
    async with test_session_factory() as s:
        s.add(AbilityScore(character_id=pg, name="charisma", value=14))
        band = Item(character_id=pg, name="Fascia", item_type="accessory", item_metadata=json.dumps(CHA_BAND),
                    is_equipped=True, equipment_slot=EquipmentSlot.RING1)
        s.add(band)
        await s.commit()
        band_id = band.id
    r = await client.post(f"/sessions/{sid}/stash/put", json={"from_character_id": pg, "item_id": band_id})
    assert r.status_code == 200, r.text
    assert _by_key(r.json(), "wizard.tricks")["max_uses"] == 2


async def test_remove_class_updates_uses_of_remaining_classes(client, rules_catalog):
    rules_catalog(_spec("bard.tricks", uses=Uses(proficiency=True)))
    cid, body = await _api_char(client, "bard", 4)
    body = (await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 1})).json()
    assert _by_key(body, "bard.tricks")["max_uses"] == 3
    fighter = next(c for c in body["classes"] if c["class_name"] == "fighter")
    r = await client.delete(f"/characters/{cid}/classes/{fighter['id']}")
    assert r.status_code == 200, r.text
    assert _by_key(r.json(), "bard.tricks")["max_uses"] == 2


async def test_asi_updates_uses(client, rules_catalog):
    rules_catalog(_spec("bard.bardic_inspiration", uses=Uses(ability="charisma")))
    cid, body = await _api_char(client, "bard", 3)
    cls_id = body["classes"][0]["id"]
    await client.patch(f"/characters/{cid}/ability_scores/charisma", json={"value": 14})
    body = (await client.patch(f"/characters/{cid}/classes/{cls_id}", json={"level": 4})).json()
    assert _by_key(body, "bard.bardic_inspiration")["max_uses"] == 2
    r = await client.post(f"/characters/{cid}/choices/{body['pending_choices'][0]['id']}/resolve",
                          json={"kind": "asi", "increases": {"charisma": 2}})
    assert r.status_code == 200, r.text
    assert _by_key(r.json(), "bard.bardic_inspiration")["max_uses"] == 3


async def test_short_rest_recovers_one_when_configured(client, rules_catalog):
    rules_catalog(_spec("barbarian.rage", uses=Uses(table={1: 3}), restoration="long_rest", short_rest_recovers=1))
    cid, body = await _api_char(client, "barbarian")
    rage = _by_key(body, "barbarian.rage")
    await client.patch(f"/characters/{cid}/abilities/{rage['id']}", json={"uses": 1})
    preview = (await client.get(f"/characters/{cid}/rest/preview", params={"rest_type": "short"})).json()
    assert rage["name"] in preview["abilities"]
    body = (await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})).json()
    assert _by_key(body, "barbarian.rage")["uses"] == 2
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})
    body = (await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})).json()
    assert _by_key(body, "barbarian.rage")["uses"] == 3  # mai oltre il massimo
    await client.patch(f"/characters/{cid}/abilities/{rage['id']}", json={"uses": 0})
    body = (await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})).json()
    assert _by_key(body, "barbarian.rage")["uses"] == 3


async def test_rest_leaves_unlimited_rows_without_counter(client, rules_catalog):
    rules_catalog(_spec("barbarian.rage", uses=Uses(table={1: 6}, unlimited_from=20), restoration="long_rest", short_rest_recovers=1))
    cid, body = await _api_char(client, "barbarian", 20)
    for kind in ("short", "long"):
        preview = (await client.get(f"/characters/{cid}/rest/preview", params={"rest_type": kind})).json()
        assert preview["abilities"] == []
        row = _by_key((await client.post(f"/characters/{cid}/rest", json={"rest_type": kind})).json(), "barbarian.rage")
        assert row["max_uses"] is None and row["uses"] is None


async def test_patch_uses_on_unlimited_row_keeps_no_counter(client, rules_catalog):
    rules_catalog(_spec("barbarian.rage", uses=Uses(table={1: 6}, unlimited_from=20)))
    cid, body = await _api_char(client, "barbarian", 20)
    rage = _by_key(body, "barbarian.rage")
    r = await client.patch(f"/characters/{cid}/abilities/{rage['id']}", json={"uses": 3})
    assert r.status_code == 200 and r.json()["uses"] is None


async def test_wild_shape_unlimited_activates_without_uses(client, rules_catalog):
    rules_catalog(_spec("druid.wild_shape", uses=Uses(table={2: 2}, unlimited_from=20)))
    cid, body = await _api_char(client, "druid", 20)
    assert _by_key(body, "druid.wild_shape")["max_uses"] is None
    form = (await client.post(f"/characters/{cid}/companions", json={
        "kind": "wild_shape", "name": "Orso", "statblock": {"size": "Medium", "type": "beast", "actions": []},
        "max_hp": 10, "current_hp": 10, "armor_class": 11})).json()
    r = await client.post(f"/characters/{cid}/companions/{form['id']}/activate", json={})
    assert r.status_code == 200, r.text


async def _export(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}/export")).json()


async def test_import_syncs_only_with_rules_edition_in_file(client, rules_catalog):
    rules_catalog(_spec("barbarian.rage", uses=Uses(table={1: 5})))
    cid, body = await _api_char(client, "barbarian")
    rage = _by_key(body, "barbarian.rage")
    await client.patch(f"/characters/{cid}/abilities/{rage['id']}", json={"uses": 2})
    data = await _export(client, cid)
    next(a for a in data["abilities"] if a["feature_key"] == "barbarian.rage")["max_uses"] = 9

    # con il campo: sync (massimo dal catalogo, spesi conservati)
    r = await client.post("/characters/import", json=data)
    assert r.status_code == 201, r.text
    assert _by_key(r.json(), "barbarian.rage")["max_uses"] == 5

    # senza il campo: il file resta com'è
    del data["character"]["rules_edition"]
    r = await client.post("/characters/import", json=data)
    assert r.status_code == 201, r.text
    assert _by_key(r.json(), "barbarian.rage")["max_uses"] == 9


@pytest.mark.parametrize("archive", [
    "x",
    None,
    ["barbarian.rage"],
    {"barbarian.rage": "x"},
    {"barbarian.rage": {"spent": "x"}},
    {"barbarian.rage": {"spent": -5}},
    {"barbarian.rage": {"spent": True}},
    {"barbarian.rage": {"spent": 1.5}},
    {"barbarian.rage": {"description": 5}},
])
@pytest.mark.parametrize("with_edition", [True, False])
async def test_import_discards_malformed_archive(client, rules_catalog, archive, with_edition):
    rules_catalog(_spec("barbarian.rage", uses=Uses(table={1: 5})))
    cid, _ = await _api_char(client, "barbarian")
    data = await _export(client, cid)
    data["abilities"] = []  # riga assente: il sync legge l'archivio
    data["character"]["settings"]["archived_features"] = archive
    if not with_edition:
        del data["character"]["rules_edition"]
    r = await client.post("/characters/import", json=data)
    assert r.status_code == 201, r.text
    new_id = r.json()["id"]
    assert not r.json()["settings"].get("archived_features")
    # il personaggio resta sincronizzabile
    r = await client.patch(f"/characters/{new_id}/ability_scores/strength", json={"value": 12})
    assert r.status_code == 200, r.text
    assert (await _export(client, new_id))["character"]["settings"].get("archived_features") in (None, {})


async def test_import_keeps_valid_archive_fields_only(client, rules_catalog):
    rules_catalog(_spec("barbarian.rage", uses=Uses(table={1: 5})))
    cid, _ = await _api_char(client, "barbarian")
    data = await _export(client, cid)
    data["abilities"] = []
    data["character"]["settings"]["archived_features"] = {
        "barbarian.rage": {"spent": 2, "description": "Mia", "junk": 1},
        "barbarian.half": {"spent": "x", "description": "Solo testo"},
        "barbarian.bad": 7,
    }
    body = (await client.post("/characters/import", json=data)).json()
    rage = _by_key(body, "barbarian.rage")
    assert (rage["max_uses"], rage["uses"], rage["description"]) == (5, 3, "Mia")
    assert body["settings"]["archived_features"] == {"barbarian.half": {"description": "Solo testo"}}


async def test_duplicate_keeps_archive(client, rules_catalog):
    rules_catalog(_spec("barbarian.old", uses=Uses(table={1: 4})), _spec("barbarian.rage", "2024", uses=Uses(table={1: 2})))
    cid, body = await _api_char(client, "barbarian")
    old = _by_key(body, "barbarian.old")
    await client.patch(f"/characters/{cid}/abilities/{old['id']}", json={"uses": 1, "description": "Mia"})
    await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})
    r = await client.post(f"/characters/{cid}/duplicate")
    assert r.status_code == 201, r.text
    assert r.json()["settings"]["archived_features"] == {"barbarian.old": {"spent": 3, "description": "Mia"}}
    body = (await client.patch(f"/characters/{r.json()['id']}", json={"rules_edition": "2014"})).json()
    back = _by_key(body, "barbarian.old")
    assert (back["uses"], back["description"]) == (1, "Mia")


async def test_short_rest_recovers_survives_export_import(client, rules_catalog):
    rules_catalog(_spec("barbarian.rage", uses=Uses(table={1: 3}), restoration="long_rest", short_rest_recovers=1))
    cid, _ = await _api_char(client, "barbarian")
    data = await _export(client, cid)
    assert next(a for a in data["abilities"] if a["feature_key"] == "barbarian.rage")["short_rest_recovers"] == 1
    rules_catalog.clear()
    del data["character"]["rules_edition"]
    new = (await client.post("/characters/import", json=data)).json()
    new_id = new["id"]
    rage = _by_key(new, "barbarian.rage")
    await client.patch(f"/characters/{new_id}/abilities/{rage['id']}", json={"uses": 0})
    body = (await client.post(f"/characters/{new_id}/rest", json={"rest_type": "short"})).json()
    assert _by_key(body, "barbarian.rage")["uses"] == 1

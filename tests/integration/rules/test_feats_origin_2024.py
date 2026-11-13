"""Talenti d'Origine 2024: catalogo ed effetti (PR 1 talenti, Task 5)."""
from __future__ import annotations

from core.data.feats_2024 import ALL_FEATS
from core.db.models import Ability
from core.rules.catalog.feats import FEAT_FEATURES
from tests.integration.rules.test_2014_bard import _ability, _full, _roll_keys
from tests.integration.rules.test_2014_fighter import _attack
from tests.integration.rules.test_2014_fighter_styles import _dice, _item

ORIGIN = {"2024_alert", "2024_crafter", "2024_healer", "2024_lucky", "2024_magic_initiate", "2024_musician",
          "2024_savage_attacker", "2024_skilled", "2024_tavern_brawler", "2024_tough"}


async def _hero(client, level=1) -> int:
    r = await client.post("/characters", json={"name": "Origine", "rules_edition": "2024",
                                               "initial_class": {"class_name": "fighter", "level": level}})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _give(factory, client, cid, key, options=None) -> dict:
    """Il talento scritto sulla scheda, poi lo sync dei privilegi (come dopo una scelta)."""
    from api.services.character_load import get_owned_full
    from core.rules.feature_sync import sync_cataloged_features
    from tests.integration.conftest import TEST_USER_ID
    async with factory() as s:
        s.add(Ability(character_id=cid, name=key, is_passive=True, feature_key=f"feat.{key}", options=options))
        await s.commit()
    async with factory() as s:
        await sync_cataloged_features(s, await get_owned_full(cid, TEST_USER_ID, s))
        await s.commit()
    return await _full(client, cid)


def test_origin_feats_catalog():
    origin = {k for k, f in ALL_FEATS.items() if f.category == "origin"}
    assert origin == ORIGIN
    for key in ORIGIN:
        f = ALL_FEATS[key]
        assert f.edition == "2024" and f.min_level == 0 and not f.ability_increase
        assert f.repeatable == (key in ("2024_magic_initiate", "2024_skilled"))
        assert f"feat.{key}" in FEAT_FEATURES and FEAT_FEATURES[f"feat.{key}"].edition == "2024"
        assert len(f.summary["it"]) <= 200 and len(f.summary["en"]) <= 200


async def test_alert_2024_adds_proficiency_to_initiative(client, test_session_factory):
    cid = await _hero(client, 1)
    before = (await _full(client, cid))["initiative_bonus"]
    assert (await _give(test_session_factory, client, cid, "2024_alert"))["initiative_bonus"] == before + 2
    cid5 = await _hero(client, 5)
    before5 = (await _full(client, cid5))["initiative_bonus"]
    assert (await _give(test_session_factory, client, cid5, "2024_alert"))["initiative_bonus"] == before5 + 3


async def test_tough_2024(client, test_session_factory):
    cid = await _hero(client, 3)
    before = (await _full(client, cid))["computed"]["hp_max_effective"]
    out = await _give(test_session_factory, client, cid, "2024_tough")
    assert out["computed"]["hp_max_effective"] == before + 6


async def test_lucky_2024_points_equal_proficiency_and_give_advantage(client, test_session_factory):
    cid = await _hero(client, 5)
    await _give(test_session_factory, client, cid, "2024_lucky")
    row = await _ability(client, cid, "feat.2024_lucky")
    assert (row["max_uses"], row["uses"], row["restoration_type"]) == (3, 3, "long_rest")
    assert "feat.2024_lucky" in await _roll_keys(client, cid, "save", ability="wisdom")
    r = await client.post(f"/characters/{cid}/saving_throws/wisdom/roll",
                          json={"dice": [4, 15], "options": ["feat.2024_lucky"]})
    assert r.status_code == 200, r.text
    assert r.json()["mode_applied"] == "advantage" and r.json()["die"] == 15
    assert (await _ability(client, cid, "feat.2024_lucky"))["uses"] == 2


async def test_savage_attacker_keeps_best_weapon_roll_once_per_turn(client, test_session_factory, monkeypatch):
    cid = await _hero(client, 1)
    await _give(test_session_factory, client, cid, "2024_savage_attacker")
    wid = await _item(client, cid, "Spada", damage_dice="1d8", weapon_type="melee", properties=[], equip="main_hand")
    _dice(monkeypatch, 2, 7)  # primo tiro 2, secondo 7: vale 7
    body = (await _attack(client, cid, wid, die=15)).json()
    assert body["damage_rolls"] == [7], body
    _dice(monkeypatch, 2, 7)  # stesso turno: un solo tiro
    r = await _attack(client, cid, wid, die=15, confirm_extra_attack=True)
    assert r.json()["damage_rolls"] == [2], r.text


async def test_tavern_brawler_unarmed_d4(client, test_session_factory):
    cid = await _hero(client, 1)
    assert (await _full(client, cid))["unarmed_damage_dice"] in ("1", "")
    out = await _give(test_session_factory, client, cid, "2024_tavern_brawler")
    assert out["unarmed_damage_dice"] == "1d4"

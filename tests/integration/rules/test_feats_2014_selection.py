"""I 42 talenti 2014: scheda di selezione e prerequisiti (PR 3 talenti, Task 1)."""
from __future__ import annotations

from core.data.feats_2024 import ALL_FEATS
from api.services.catalog_migration import migrate_catalog
from core.db.models import Ability, AppMeta
from core.rules.catalog.feats import FEAT_FEATURES
from tests.integration.rules.test_2014_bard import _full
from tests.integration.rules.test_feats_take_complete import _take

SCORES = {"strength": 10, "dexterity": 14, "constitution": 14, "intelligence": 13, "wisdom": 13, "charisma": 13}


async def _char14(client, class_name: str, level: int = 4, edition: str = "2014", **scores) -> dict:
    r = await client.post("/characters", json={
        "name": "Talenti 2014", "rules_edition": edition, "ability_scores": {**SCORES, **scores},
        "initial_class": {"class_name": class_name, "level": level}})
    assert r.status_code == 201, r.text
    return r.json()


def _score(body: dict, name: str) -> int:
    return next(s["value"] for s in body["ability_scores"] if s["name"] == name)


def test_catalog_has_42_feats():
    keys = [k for k, f in ALL_FEATS.items() if f.edition == "2014"]
    assert len(keys) == 42
    assert all(f"feat.{k}" in FEAT_FEATURES for k in keys)


async def test_ability_prerequisite(client):
    weak = await _char14(client, "wizard")
    r = await _take(client, weak["id"], "grappler")
    assert r.status_code == 422 and "feat_prerequisite_ability" in r.text
    strong = await _char14(client, "wizard", strength=13)
    assert (await _take(client, strong["id"], "grappler")).status_code == 201


async def test_armor_prerequisite(client):
    wizard = await _char14(client, "wizard")
    r = await _take(client, wizard["id"], "moderately_armored", "dexterity")
    assert r.status_code == 422 and "feat_prerequisite_armor" in r.text
    fighter = await _char14(client, "fighter")
    assert (await _take(client, fighter["id"], "moderately_armored", "dexterity")).status_code == 201


async def test_spellcasting_prerequisite(client):
    fighter = await _char14(client, "fighter")
    r = await _take(client, fighter["id"], "spell_sniper")
    assert r.status_code == 422 and "feat_prerequisite_spellcasting" in r.text


async def test_half_feat_plus_one(client):
    ch = await _char14(client, "fighter")
    r = await _take(client, ch["id"], "athlete", "dexterity")
    assert r.status_code == 201, r.text
    assert _score(r.json(), "dexterity") == 15
    assert (await _take(client, (await _char14(client, "fighter"))["id"], "athlete", "wisdom")).status_code == 422


async def test_only_elemental_adept_repeats(client):
    ch = await _char14(client, "wizard")
    assert (await _take(client, ch["id"], "elemental_adept")).status_code == 201
    assert (await _take(client, ch["id"], "elemental_adept")).status_code == 201
    assert (await _take(client, ch["id"], "actor", "charisma")).status_code == 201
    r = await _take(client, ch["id"], "actor", "charisma")
    assert r.status_code == 422 and "feat_already_taken" in r.text


async def test_2024_character_cannot_take_2014_feat(client):
    ch = await _char14(client, "fighter", edition="2024")
    r = await _take(client, ch["id"], "sentinel")
    assert r.status_code == 422 and "feat_wrong_edition" in r.text


async def test_old_rows_are_renamed(client, test_session_factory):
    ch = await _char14(client, "fighter")
    old_summary = ("+10 feet speed; Dash ignores difficult terrain; creatures you attack in melee get no "
                   "opportunity attack on you.")
    async with test_session_factory() as s:
        s.add(Ability(character_id=ch["id"], name="Mobile", description=old_summary, is_passive=True,
                      feature_key="feat.mobile"))
        s.add(Ability(character_id=ch["id"], name="Incantatore Bellico", description="scritta a mano", is_passive=True,
                      feature_key="feat.war_caster"))
        meta = await s.get(AppMeta, "catalog_version")
        if meta is None:
            s.add(AppMeta(key="catalog_version", value="0"))
        else:
            meta.value = "0"
        await s.commit()
    await migrate_catalog(test_session_factory)  # la 3.6.0 cambia CATALOG_VERSION: le righe passano dallo sync
    out = await _full(client, ch["id"])
    mobile = next(a for a in out["abilities"] if a["feature_key"] == "feat.mobile")
    caster = next(a for a in out["abilities"] if a["feature_key"] == "feat.war_caster")
    assert mobile["name"] == "Mobilità" and mobile["description"] != old_summary
    assert caster["name"] == "Incantatore da Guerra" and caster["description"] == "scritta a mano"

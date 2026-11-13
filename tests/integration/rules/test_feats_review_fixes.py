"""Correzioni della revisione finale della PR 1 talenti: import di vecchi export, elenco personaggi, cap dei PF."""
from __future__ import annotations

from sqlalchemy import select

from api.services.effects import cap_current_hp
from core.db.models import Character
from tests.integration.rules.test_feats_2014_engine import _l4
from tests.integration.test_level_choices import _take

_WHEN = {"path": "$character.id", "op": "gt", "value": 0}


def _old_rule(key: str, target: str, value: int) -> dict:
    """La regola `feat:<chiave>` come la creava l'app prima della 3.4.0."""
    return {"name": key, "version": 1, "enabled": True, "template_id": f"feat:{key}", "dsl": {
        "version": 1, "subject": {"type": "character"}, "triggers": [],
        "passive_modifiers": [{"when": _WHEN, "target": f"character.{target}", "value": value,
                               "label_i18n": {"it": key, "en": key}}]}}


async def test_import_of_old_export_does_not_double_alert(client):
    body = await _l4(client)
    out = await _take(client, body, "alert")
    data = (await client.get(f"/characters/{body['id']}/export")).json()
    data["homebrew_rules"].append(_old_rule("alert", "initiative", 5))
    r = await client.post("/characters/import", json=data)
    assert r.status_code == 201, r.text
    assert r.json()["initiative_bonus"] == out["initiative_bonus"]
    rules = (await client.get(f"/characters/{r.json()['id']}/homebrew/rules")).json()
    assert not [x for x in rules if (x.get("template_id") or "").startswith("feat:")]


async def test_character_list_counts_tough(client):
    body = await _l4(client)
    out = await _take(client, body, "tough")
    row = next(c for c in (await client.get("/characters")).json() if c["id"] == body["id"])
    assert row["hp_max_effective"] == out["computed"]["hp_max_effective"]


async def test_cap_current_hp_keeps_tough_without_loaded_abilities(client, test_session_factory):
    body = await _l4(client)
    out = await _take(client, body, "tough")
    full = out["computed"]["hp_max_effective"]
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).where(Character.id == body["id"]))).scalar_one()
        char.current_hit_points = full
        await cap_current_hp(s, char, always=True)
        assert char.current_hit_points == full

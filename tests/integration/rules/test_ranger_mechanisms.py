"""Meccanismi comuni aggiunti per il Ranger 2014 (Task 26): slot spesi da un uso, opzione «nessun linguaggio», gruppi elencati."""
from __future__ import annotations

from types import SimpleNamespace

from core.rules.level_choices import apply_grants
from core.rules.types import ChoiceSpec
from tests.integration.rules.test_2014_bard import _full, _use
from tests.integration.rules.test_2014_ranger import AWARENESS, _choice, _ranger, _resolve


def test_an_option_that_skips_adds_no_language_and_a_real_one_does():
    skip = ChoiceSpec(group="g", levels={1: 1}, options=lambda _c: [], grants="language",
                      label=lambda k: {"name": {"it": "Nessuno", "en": "None"}, "skip": True} if k == "none" else
                      {"name": {"it": "Gigante", "en": "Giant"}})
    char = SimpleNamespace(languages=["Comune"])
    apply_grants(char, skip, ["none"])
    assert char.languages == ["Comune"]
    apply_grants(char, skip, ["giant"])
    assert char.languages == ["Comune", "Gigante"]
    apply_grants(char, skip, ["giant"])  # lo stesso linguaggio non si ripete
    assert char.languages == ["Comune", "Gigante"]


async def test_a_use_that_spends_a_slot_needs_the_level_choice(client):
    cid = await _ranger(client, 3)
    for params in (None, {}, {"slot_level": "9"}, {"slot_level": 1}, {"slot_level": "uno"}):
        r = await _use(client, cid, AWARENESS, **({"params": params} if params is not None else {}))
        assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_choice", params
    assert {s["level"]: s["used"] for s in (await _full(client, cid))["spell_slots"]} == {1: 0}


async def test_the_class_options_endpoint_says_which_groups_are_only_listed(client):
    cid = await _ranger(client, 2)
    await _resolve(client, cid, "favored_enemy", "undead")
    await _resolve(client, cid, "fighting_style", "archery")
    full = await _full(client, cid)
    class_id = full["classes"][0]["id"]
    enemies = (await client.get(f"/characters/{cid}/classes/{class_id}/options/favored_enemy")).json()
    assert (enemies["replaceable"], enemies["listed"]) == (False, True)
    assert [o["key"] for o in enemies["chosen"]] == ["undead"] and enemies["chosen"][0]["name"]["it"] == "Non morti"
    style = (await client.get(f"/characters/{cid}/classes/{class_id}/options/fighting_style")).json()
    assert (style["replaceable"], style["listed"]) == (False, False)


async def test_an_old_ranger_file_can_declare_the_language_it_already_has(client):
    """R39: chi ha già un linguaggio del nemico sulla scheda lo dichiara, senza aggiungerne un altro."""
    cid = await _ranger(client, 1)
    await client.patch(f"/characters/{cid}", json={"languages": ["Gigante"]})
    exported = (await client.get(f"/characters/{cid}/export")).json()
    exported["character"].pop("rules_edition", None)
    r = await client.post("/characters/import", json=exported)
    assert r.status_code == 201, r.text
    new = r.json()["id"]
    choice = _choice(await _full(client, new), "favored_enemy_language")
    assert choice["retrofit"] is True
    assert next(o for o in choice["options"] if o["key"] == "giant").get("owned") is True
    done = await client.post(f"/characters/{new}/choices/{choice['id']}/resolve", json={"kind": "class_option", "options": ["giant"]})
    assert done.status_code == 200, done.text
    assert (await _full(client, new))["languages"] == ["Gigante"]

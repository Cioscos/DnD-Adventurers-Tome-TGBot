"""Classi che scelgono strumenti dal catalogo: Bardo, Monaco, Maestro di Battaglia, Maestria del Ladro 2014."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.data.tools import TOOLS
from core.db.models import Ability, Character
from tests.integration.rules.test_2014_bard import _bard, _choice, _full, _resolve, _skills
from tests.integration.rules.test_2014_rogue import _rogue
from tests.integration.rules.test_2024_fighter_subclasses import _sub


def _keys(choice) -> set[str]:
    return {o["key"] for o in choice["options"]}


def _category(*cats) -> set[str]:
    return {f"tool:{k}" for k, t in TOOLS.items() if t.category in cats}


async def _new(client, class_name, level=1, edition="2014") -> int:
    r = await client.post("/characters", json={"name": "Prova", "initial_class": {"class_name": class_name, "level": level}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    if edition == "2024":
        assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    return cid


async def test_new_bard_gets_three_instruments_choice(client):
    cid = await _bard(client, 1)
    choice = _choice(await _full(client, cid), "bard_instruments")
    assert choice["count"] == 3 and _keys(choice) == _category("instrument")
    assert choice["options"][0]["summary"]["it"] == "Strumento musicale"
    r = await _resolve(client, cid, "bard_instruments", ["tool:lute", "tool:flute", "tool:viol"])
    assert r.status_code == 200, r.text
    assert r.json()["tool_proficiencies"] == {"lute": True, "flute": True, "viol": True}
    assert _choice(r.json(), "bard_instruments") is None


async def test_bard_as_second_class_chooses_one_instrument(client):
    cid = await _new(client, "fighter")
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "bard", "level": 1, "hit_die": 8})
    assert r.status_code == 201, r.text
    assert _choice(await _full(client, cid), "bard_instruments")["count"] == 1


async def test_monk_2024_chooses_artisan_or_instrument(client):
    cid = await _new(client, "monk", edition="2024")
    choice = _choice(await _full(client, cid), "monk_tool")
    assert choice["count"] == 1 and _keys(choice) == _category("artisan", "instrument")


async def test_battle_master_2024_has_tool_and_skill_choices(client):
    cid = await _sub(client, "battle_master", 3)
    full = await _full(client, cid)
    assert _choice(full, "student_of_war") is not None
    assert _keys(_choice(full, "student_of_war_tool")) == _category("artisan")


async def test_battle_master_2014_chooses_an_artisan_tool(client):
    from tests.integration.rules.test_2014_fighter_battle_master import _pending  # noqa: F401  (modulo caricato)
    r = await client.post("/characters", json={"name": "BM", "initial_class": {
        "class_name": "fighter", "level": 3, "subclass": "Maestro di Battaglia"}})
    cid = r.json()["id"]
    assert _keys(_choice(await _full(client, cid), "student_of_war")) == _category("artisan")


async def test_rogue_2014_expertise_offers_thieves_tools(client):
    cid = await _rogue(client, 1)
    await _skills(client, cid, stealth=True, acrobatics=True)
    assert (await client.patch(f"/characters/{cid}", json={"tool_proficiencies": {"thieves_tools": True}})).status_code == 200
    choice = _choice(await _full(client, cid), "expertise")
    assert "tool:thieves_tools" in _keys(choice)
    r = await _resolve(client, cid, "expertise", ["stealth", "tool:thieves_tools"])
    assert r.status_code == 200, r.text
    assert r.json()["tool_proficiencies"]["thieves_tools"] == "expert"
    assert r.json()["skills"]["stealth"] == "expert"


async def test_rogue_2024_expertise_has_no_tools(client):
    cid = await _rogue(client, 1)
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    await _skills(client, cid, stealth=True, acrobatics=True)
    await client.patch(f"/characters/{cid}", json={"tool_proficiencies": {"thieves_tools": True}})
    choice = _choice(await _full(client, cid), "expertise")
    assert not any(k.startswith("tool:") for k in _keys(choice))


async def _as_existing(test_session_factory, cid, tools: dict, feat_instruments=None) -> None:
    """Un personaggio già passato dal catalogo prima di questa versione: strumenti sulla scheda, scelte nuove mai viste."""
    from api.services.catalog_migration import migrate_catalog

    async with test_session_factory() as s:
        char = (await s.execute(select(Character).options(selectinload(Character.classes)).where(Character.id == cid))).scalar_one()
        char.tool_proficiencies = tools
        char.pending_choices = [c for c in char.pending_choices if c["kind"] != "class_option"]
        char.settings = {k: v for k, v in (char.settings or {}).items() if k != "tool_choices_seeded"}
        for cls in char.classes:
            cls.options = {}
        if feat_instruments:
            s.add(Ability(character_id=cid, name="Musicista", feature_key="feat.2024_musician",
                          options={"instruments": feat_instruments}))
        await s.commit()
    assert await migrate_catalog(test_session_factory) >= 1


async def test_existing_bard_with_instruments_is_seeded_not_asked(client, test_session_factory):
    cid = await _bard(client, 1)
    await _as_existing(test_session_factory, cid, {"lute": True, "flute": True, "viol": True})
    full = await _full(client, cid)
    assert _choice(full, "bard_instruments") is None
    assert full["tool_proficiencies"] == {"lute": True, "flute": True, "viol": True}


async def test_seed_skips_feat_instruments(client, test_session_factory):
    cid = await _bard(client, 1)
    await _as_existing(test_session_factory, cid, {"lute": True, "flute": True, "viol": True},
                       feat_instruments=["lute", "Flauto", "viol"])
    assert _choice(await _full(client, cid), "bard_instruments")["count"] == 3


async def test_imported_rogue_expert_thieves_tools_counts_as_expertise(client, test_session_factory):
    cid = await _rogue(client, 1)
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).options(selectinload(Character.classes)).where(Character.id == cid))).scalar_one()
        char.skills = {**(char.skills or {}), "stealth": "expert"}
        char.tool_proficiencies = {"thieves_tools": "expert"}
        char.pending_choices = [c for c in char.pending_choices if c["kind"] != "class_option"]
        char.settings = {k: v for k, v in (char.settings or {}).items() if k != "retrofit_done"}  # mai passato dal catalogo
        for cls in char.classes:
            cls.options = {}
        await s.commit()
    from api.services.catalog_migration import migrate_catalog
    assert await migrate_catalog(test_session_factory) >= 1
    assert _choice(await _full(client, cid), "expertise") is None

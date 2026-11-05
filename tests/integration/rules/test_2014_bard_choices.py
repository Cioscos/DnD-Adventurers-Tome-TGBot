"""Bardo 2014, giro 1: scelte di livello che non bloccano (I2, R39) e Bardo già salvato (I3, R39)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.db.models import Character, Spell
from tests.integration.rules.test_2014_bard import (
    LORE, _add_spell, _bard, _choice, _full, _resolve, _skills,
)


def _kinds(full) -> list[str]:
    return [c.get("group") or c["kind"] for c in full["pending_choices"]]


async def test_a_lore_bard_created_at_10_does_not_deadlock(client):
    cid = await _bard(client, 10, LORE)
    full = await _full(client, cid)
    kinds = _kinds(full)
    assert kinds.index("lore_skills") < kinds.index("expertise")  # le abilità di Sapienza sbloccano la Maestria
    expertise = _choice(full, "expertise")
    assert expertise["count"] == 4 and expertise["options"] == [] and expertise["resolvable"] is False
    assert _choice(full, "lore_skills")["resolvable"] is True
    assert _choice(full, "magical_secrets")["resolvable"] is True


async def test_expertise_is_resolvable_with_the_skills_available_and_the_rest_waits(client):
    cid = await _bard(client, 10, LORE)
    await _skills(client, cid, acrobatics=True, arcana=True, history=True)
    choice = _choice(await _full(client, cid), "expertise")
    assert (choice["count"], choice["pick_count"], choice["resolvable"]) == (4, 3, True)
    assert (await _resolve(client, cid, "expertise", ["acrobatics"])).status_code == 422  # ne vanno prese 3
    r = await _resolve(client, cid, "expertise", ["acrobatics", "arcana", "history"])
    assert r.status_code == 200, r.text
    left = _choice(r.json(), "expertise")
    assert (left["count"], left["pick_count"], left["resolvable"]) == (1, 0, False)  # aspetta altre competenze
    await _skills(client, cid, insight=True)
    again = _choice(await _full(client, cid), "expertise")
    assert (again["pick_count"], again["resolvable"]) == (1, True)
    assert (await _resolve(client, cid, "expertise", ["insight"])).status_code == 200


async def test_an_option_choice_without_a_shortfall_still_wants_exactly_count(client):
    cid = await _bard(client, 3)
    await _skills(client, cid, acrobatics=True, arcana=True, history=True)
    assert (await _resolve(client, cid, "expertise", ["arcana"])).status_code == 422


async def test_lore_skills_before_expertise_lets_a_new_lore_bard_finish_the_queue(client):
    cid = await _bard(client, 3, LORE)
    r = await _resolve(client, cid, "lore_skills", ["arcana", "history", "insight"])
    assert r.status_code == 200, r.text
    expertise = _choice(r.json(), "expertise")
    assert expertise["resolvable"] is True and {o["key"] for o in expertise["options"]} == {"arcana", "history", "insight"}


# ---------------------------------------------------------------------------
# I3: un Bardo già salvato non riceve due volte ciò che ha già
# ---------------------------------------------------------------------------

async def _existing_bard(client, test_session_factory, level, subclass=LORE, expert=(), proficient=()) -> int:
    """Un Bardo salvato prima del catalogo: competenze e maestrie già scritte, nessuna scelta in sospeso."""
    from api.services.catalog_migration import migrate_catalog

    cid = await _bard(client, level, subclass)
    skills = {**{s: True for s in proficient}, **{s: "expert" for s in expert}}
    await _skills(client, cid, **skills)
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).options(selectinload(Character.classes)).where(Character.id == cid))).scalar_one()
        char.pending_choices = [c for c in char.pending_choices if c["kind"] != "class_option"]
        for cls in char.classes:
            cls.options = {}
        await s.commit()
    assert await migrate_catalog(test_session_factory) >= 1
    return cid


async def test_existing_expertise_seeds_the_choice(client, test_session_factory):
    cid = await _existing_bard(client, test_session_factory, 7, expert=("arcana", "history"), proficient=("insight",))
    full = await _full(client, cid)
    assert _choice(full, "expertise") is None  # le 2 maestrie che deve avere ci sono già
    assert full["skills"]["arcana"] == "expert" and full["skills"]["insight"] is True


async def test_existing_expertise_seeds_only_up_to_the_limit(client, test_session_factory):
    cid = await _existing_bard(client, test_session_factory, 7, expert=("arcana", "history", "insight"))
    assert _choice(await _full(client, cid), "expertise") is None
    async with test_session_factory() as s:
        cls = (await s.execute(select(Character).options(selectinload(Character.classes)).where(Character.id == cid))
               ).scalar_one().classes[0]
        assert len(cls.options["expertise"]) == 2


async def test_existing_bard_can_say_the_lore_skills_are_already_on_the_sheet(client, test_session_factory):
    cid = await _existing_bard(client, test_session_factory, 7, proficient=("arcana", "history", "insight"))
    choice = _choice(await _full(client, cid), "lore_skills")
    assert choice["count"] == 3 and choice["retrofit"] is True
    assert {"arcana", "history", "insight"} <= {o["key"] for o in choice["options"]}  # già competenti: ammesse
    r = await _resolve(client, cid, "lore_skills", ["arcana", "history", "insight"])
    assert r.status_code == 200, r.text
    assert {k: r.json()["skills"][k] for k in ("arcana", "history", "insight")} == {k: True for k in ("arcana", "history", "insight")}
    assert _choice(r.json(), "lore_skills") is None


async def test_a_new_lore_bard_still_only_picks_skills_it_does_not_have(client):
    cid = await _bard(client, 3, LORE)
    await _skills(client, cid, acrobatics=True)
    choice = _choice(await _full(client, cid), "lore_skills")
    assert "acrobatics" not in {o["key"] for o in choice["options"]} and not choice.get("retrofit")


async def test_existing_bard_marks_a_known_spell_as_already_a_secret(client, test_session_factory):
    cid = await _existing_bard(client, test_session_factory, 10, subclass=None)
    bard_class = (await _full(client, cid))["classes"][0]["id"]
    known = (await _add_spell(client, cid, "Palla di fuoco", 3, class_id=bard_class)).json()
    other = (await _add_spell(client, cid, "Volare", 3, class_id=bard_class)).json()
    full = await _full(client, cid)
    choice = _choice(full, "magical_secrets")
    assert choice["count"] == 2 and choice["retrofit"] is True
    before = len((await client.get(f"/characters/{cid}/spells")).json())
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve",
                          json={"kind": "class_option", "options": [str(known["id"]), str(other["id"])]})
    assert r.status_code == 200, r.text
    assert _choice(r.json(), "magical_secrets") is None
    assert len((await client.get(f"/characters/{cid}/spells")).json()) == before  # nessun incantesimo aggiunto né duplicato
    assert r.json()["spellcasting"]["limits"][0]["known_count"] == 2  # restano fra i conosciuti


async def test_an_already_known_spell_is_free_when_the_secret_is_an_additional_one(client, test_session_factory):
    cid = await _existing_bard(client, test_session_factory, 6)
    bard_class = (await _full(client, cid))["classes"][0]["id"]
    known = (await _add_spell(client, cid, "Palla di fuoco", 3, class_id=bard_class)).json()
    await _add_spell(client, cid, "Incantesimo base", 1, class_id=bard_class)
    choice = _choice(await _full(client, cid), "additional_secrets")
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve",
                          json={"kind": "class_option", "options": [str(known["id"])]})
    assert r.status_code == 200, r.text
    assert _choice(r.json(), "additional_secrets")["count"] == 1  # ne resta uno
    assert r.json()["spellcasting"]["limits"][0]["known_count"] == 1  # quello segnato non conta più fra i conosciuti


async def test_a_new_bard_cannot_resolve_a_spell_pick_with_existing_spells(client):
    cid = await _bard(client, 10)
    bard_class = (await _full(client, cid))["classes"][0]["id"]
    known = (await _add_spell(client, cid, "Palla di fuoco", 3, class_id=bard_class)).json()
    choice = _choice(await _full(client, cid), "magical_secrets")
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve",
                          json={"kind": "class_option", "options": [str(known["id"])]})
    assert r.status_code == 422  # la scorciatoia vale solo per chi esisteva prima del catalogo


# Giro 2, N1: gli incantesimi di un Bardo salvato hanno `class_id` nullo

async def _spell_classes(client, cid) -> dict[str, int | None]:
    return {s["name"]: s["class_id"] for s in (await client.get(f"/characters/{cid}/spells")).json()}


async def test_a_saved_bard_with_unassigned_spells_can_declare_them_as_secrets(client, test_session_factory):
    cid = await _existing_bard(client, test_session_factory, 10, subclass=None)
    a = (await _add_spell(client, cid, "Palla di fuoco", 3)).json()
    b = (await _add_spell(client, cid, "Volare", 3)).json()
    assert a["class_id"] is None
    choice = _choice(await _full(client, cid), "magical_secrets")
    assert {o["id"] for o in choice["spell_pick"]["owned"]} == {a["id"], b["id"]}
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve",
                          json={"kind": "class_option", "options": [str(a["id"]), str(b["id"])]})
    assert r.status_code == 200, r.text
    assert _choice(r.json(), "magical_secrets") is None
    assert len(await _spell_classes(client, cid)) == 2  # nessun duplicato
    bard_class = (await _full(client, cid))["classes"][0]["id"]
    assert set((await _spell_classes(client, cid)).values()) == {bard_class}  # la dichiarazione assegna la classe


async def test_an_unassigned_spell_is_free_for_an_additional_secret(client, test_session_factory):
    cid = await _existing_bard(client, test_session_factory, 6)
    known = (await _add_spell(client, cid, "Palla di fuoco", 3)).json()
    choice = _choice(await _full(client, cid), "additional_secrets")
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve",
                          json={"kind": "class_option", "options": [str(known["id"])]})
    assert r.status_code == 200, r.text
    assert _choice(r.json(), "additional_secrets")["count"] == 1


async def test_in_a_multiclass_a_spell_of_another_class_stays_excluded(client, test_session_factory):
    cid = await _existing_bard(client, test_session_factory, 10, subclass=None)
    await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 3, "hit_die": 6})
    wizard = next(c["id"] for c in (await _full(client, cid))["classes"] if c["class_name"] == "wizard")
    mine = (await _add_spell(client, cid, "Volare", 3)).json()
    other = (await _add_spell(client, cid, "Dardo magico", 1, class_id=wizard)).json()
    choice = _choice(await _full(client, cid), "magical_secrets")
    assert {o["id"] for o in choice["spell_pick"]["owned"]} == {mine["id"]}
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve",
                          json={"kind": "class_option", "options": [str(other["id"])]})
    assert r.status_code == 422

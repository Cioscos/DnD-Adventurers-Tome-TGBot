"""Druido 2014, giro di correzione 1: componenti degli incantesimi concessi, immunità del Circolo della Terra,
scelte di incantesimi (livello, retrofit, rilascio), territorio, mutazioni di Recupero Naturale, cura e lancio a volontà."""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.db.models import Character
from core.rules.catalog.granted_spells import GRANTED_SPELLS
from core.rules.catalog.y2014.druid import TERRITORY_SPELLS
from tests.integration._encounter_helpers import GM_ID, NOW, as_user, seed_session
from tests.integration.rules.test_2014_bard import _full, _spells
from tests.integration.rules.test_2014_bard_inspiration import _seat
from tests.integration.rules.test_2014_druid import _activate, _beast, _druid, _form, _turn
from tests.integration.rules.test_2014_druid_land import _add, _choice, _pick_territory, _short, _spend, _used
from tests.integration.rules.test_2014_druid_moon import _active_form, _fixed, _heal, _hurt, _slots


# ---------------------------------------------------------------------------
# I6: gli incantesimi concessi portano le componenti
# ---------------------------------------------------------------------------

def test_every_granted_spell_carries_its_components():
    assert GRANTED_SPELLS
    for key, spell in GRANTED_SPELLS.items():
        tokens = [t.strip() for t in (spell.components or "").split(",")]
        assert tokens and all(t in {"V", "S", "M"} for t in tokens), key


async def _warnings(client, cid, spell_id) -> list[str]:
    return (await client.get(f"/characters/{cid}/spells/{spell_id}/cast-check")).json()


async def test_circle_spells_with_materials_are_checked_in_beast_form(client):
    cid = await _druid(client, 18, "land")
    await _pick_territory(client, cid, "forest")
    spells = {s["srd_index"]: s for s in (await _spells(client, cid)).values()}
    assert spells["barkskin"]["components"] == "V, S, M" and spells["plant-growth"]["components"] == "V, S"
    await _activate(client, cid, await _form(client, cid, _beast(1, 30, 60)))
    assert await _warnings(client, cid, spells["barkskin"]["id"]) == ["form_materials"]
    assert await _warnings(client, cid, spells["plant-growth"]["id"]) == []


async def test_a_cleric_domain_spell_carries_its_components_too(client):
    from tests.integration.rules.test_2014_cleric import _cleric
    cid = await _cleric(client, 1, "life")
    spells = {s["srd_index"]: s for s in (await _spells(client, cid)).values()}
    assert spells["bless"]["components"] == "V, S, M" and spells["cure-wounds"]["components"] == "V, S"


async def test_a_spell_synced_before_the_components_receives_them(client):
    cid = await _druid(client, 18, "land")
    await _pick_territory(client, cid, "forest")
    bark = next(s for s in (await _spells(client, cid)).values() if s["srd_index"] == "barkskin")
    assert (await client.patch(f"/characters/{cid}/spells/{bark['id']}", json={"components": None})).status_code == 200
    cls = (await _full(client, cid))["classes"][0]["id"]
    await client.patch(f"/characters/{cid}/classes/{cls}", json={"level": 19})
    again = next(s for s in (await _spells(client, cid)).values() if s["srd_index"] == "barkskin")
    assert again["components"] == "V, S, M"


# ---------------------------------------------------------------------------
# I7: l'Interdizione della Natura vale anche per chi applica il GM
# ---------------------------------------------------------------------------

async def _druid_at_the_table(client, test_session_factory, level=10, circle="land"):
    sid, _hero = await seed_session(test_session_factory)
    as_user(GM_ID)
    cid = await _druid(client, level, circle)
    await _seat(test_session_factory, cid)
    r = await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})
    assert r.status_code == 201, r.text
    comb = next(c for c in r.json()["combatants"] if c.get("character_id") == cid)
    return sid, cid, comb["id"]


@pytest.mark.parametrize("body", [{"slug": "poisoned", "value": True}, {"slug": "poisoned"}], ids=["flag", "rich"])
async def test_the_gm_cannot_poison_a_druid_with_natures_ward(client, test_session_factory, body):
    sid, cid, comb = await _druid_at_the_table(client, test_session_factory)
    r = await client.post(f"/sessions/{sid}/encounter/combatants/{comb}/conditions", json=body)
    assert r.status_code == 200, r.text
    assert not (await _full(client, cid))["conditions"].get("poisoned")


async def test_the_gm_can_poison_a_druid_without_the_ward(client, test_session_factory):
    sid, cid, comb = await _druid_at_the_table(client, test_session_factory, level=9)
    r = await client.post(f"/sessions/{sid}/encounter/combatants/{comb}/conditions", json={"slug": "poisoned", "value": True})
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["conditions"]["poisoned"] is True


def test_reading_the_immunities_of_a_character_without_classes_fails_loudly():
    from types import SimpleNamespace
    from core.rules.states import immune_conditions
    with pytest.raises(AttributeError):
        immune_conditions(SimpleNamespace(active_states=[]))


# ---------------------------------------------------------------------------
# I8/I9/M11: scelta del trucchetto bonus
# ---------------------------------------------------------------------------

async def _existing_druid(client, test_session_factory, level=5, circle="land") -> int:
    """Un Druido salvato prima del catalogo: nessuna scelta in sospeso né opzioni."""
    from api.services.catalog_migration import migrate_catalog

    cid = await _druid(client, level, circle)
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).options(selectinload(Character.classes)).where(Character.id == cid))).scalar_one()
        char.pending_choices = [c for c in char.pending_choices if c["kind"] != "class_option"]
        char.settings = {k: v for k, v in (char.settings or {}).items() if k != "retrofit_done"}
        for cls in char.classes:
            cls.options = {}
        await s.commit()
    assert await migrate_catalog(test_session_factory) >= 1
    return cid


async def test_the_retrofit_lists_only_cantrips_for_the_bonus_cantrip(client, test_session_factory):
    cid = await _existing_druid(client, test_session_factory, 5)
    await _pick_territory(client, cid, "forest")  # i suoi incantesimi (2° e 3° livello) sono già sulla scheda
    cantrip = (await _add(client, cid, "Frusta di spine", 0)).json()
    leveled = (await _add(client, cid, "Fulmine", 3)).json()
    choice = _choice(await _full(client, cid), "bonus_cantrip")
    assert choice["retrofit"] is True
    owned = {o["id"] for o in choice["spell_pick"]["owned"]}
    assert owned == {cantrip["id"]}
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve",
                          json={"kind": "class_option", "options": [str(leveled["id"])]})
    assert r.status_code == 422 and r.json()["detail"] == "spell_not_known"
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve",
                          json={"kind": "class_option", "options": [str(cantrip["id"])]})
    assert r.status_code == 200, r.text


async def test_the_retrofit_of_the_acolyte_of_nature_also_lists_only_cantrips(client, test_session_factory):
    from api.services.catalog_migration import migrate_catalog
    from tests.integration.rules.test_2014_cleric import _cleric
    cid = await _cleric(client, 1, "nature")
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).options(selectinload(Character.classes)).where(Character.id == cid))).scalar_one()
        char.pending_choices = [c for c in char.pending_choices if c["kind"] != "class_option"]
        char.settings = {k: v for k, v in (char.settings or {}).items() if k != "retrofit_done"}
        for cls in char.classes:
            cls.options = {}
        await s.commit()
    assert await migrate_catalog(test_session_factory) >= 1
    cantrip = (await _add(client, cid, "Frusta di spine", 0)).json()
    leveled = (await _add(client, cid, "Fulmine", 3)).json()
    choice = _choice(await _full(client, cid), "nature_cantrip")
    assert {o["id"] for o in choice["spell_pick"]["owned"]} == {cantrip["id"]}
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve",
                          json={"kind": "class_option", "options": [str(leveled["id"])]})
    assert r.status_code == 422


async def test_deleting_the_bonus_cantrip_brings_the_choice_back(client):
    cid = await _druid(client, 5, "land")
    pick = _choice(await _full(client, cid), "bonus_cantrip")
    spell = (await _add(client, cid, "Randello", 0, pick_id=pick["id"], srd_index="shillelagh")).json()
    assert _choice(await _full(client, cid), "bonus_cantrip") is None
    assert (await client.delete(f"/characters/{cid}/spells/{spell['id']}")).status_code == 204
    again = _choice(await _full(client, cid), "bonus_cantrip")
    assert again is not None and again["count"] == 1
    assert (await _add(client, cid, "Randello", 0, pick_id=again["id"], srd_index="shillelagh")).status_code == 201


# ---------------------------------------------------------------------------
# I10: ogni territorio dice quali incantesimi dà
# ---------------------------------------------------------------------------

async def test_each_territory_option_lists_its_own_circle_spells_by_level(client):
    cid = await _druid(client, 2, "land")
    options = {o["key"]: o for o in _choice(await _full(client, cid), "territory")["options"]}
    assert set(options) == set(TERRITORY_SPELLS)
    for key, tiers in TERRITORY_SPELLS.items():
        for lang in ("it", "en"):
            text = options[key]["summary"][lang]
            assert 0 < len(text) <= 200, (key, lang)
            for level, tier in zip((3, 5, 7, 9), tiers):
                assert f"{level}" in text, (key, lang, level)
                for spell in tier:
                    assert GRANTED_SPELLS[spell].name[lang] in text, (key, lang, spell)
    assert options["forest"]["summary"]["it"] != options["desert"]["summary"]["it"]


async def test_the_territory_is_not_replaceable(client):
    cid = await _druid(client, 3, "land")
    await _pick_territory(client, cid, "forest")
    cls = (await _full(client, cid))["classes"][0]["id"]
    state = (await client.get(f"/characters/{cid}/classes/{cls}/options/territory")).json()
    assert state["replaceable"] is False


# ---------------------------------------------------------------------------
# M14: mutazioni di Recupero Naturale, cura e lancio a volontà
# ---------------------------------------------------------------------------

async def test_natural_recovery_never_counts_pact_slots_as_spent_slots(client):
    cid = await _druid(client, 6, "land")
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "warlock", "level": 3, "hit_die": 8})
    assert r.status_code in (200, 201), r.text
    slots = (await _full(client, cid))["spell_slots"]
    pact = next(s for s in slots if s.get("is_pact"))
    assert not any(s["level"] == pact["level"] and not s.get("is_pact") and s["used"] for s in slots)
    await client.patch(f"/characters/{cid}/spell_slots/{pact['id']}", json={"used": pact["total"]})
    r = await _short(client, cid, {str(pact["level"]): 1})  # solo il Patto è speso: gli slot normali no
    assert r.status_code == 422 and r.json()["detail"]["code"] == "natural_recovery_unspent"


async def test_the_budget_counts_druid_levels_only_in_a_multiclass(client):
    cid = await _druid(client, 3, "land")  # budget (3+1)//2 = 2
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 5, "hit_die": 6})
    assert r.status_code in (200, 201), r.text
    for s in (await _full(client, cid))["spell_slots"]:
        await client.patch(f"/characters/{cid}/spell_slots/{s['id']}", json={"used": s["total"]})
    refused = await _short(client, cid, {"3": 1})
    assert refused.status_code == 422 and refused.json()["detail"]["code"] == "natural_recovery_cap"
    assert (await _short(client, cid, {"2": 1})).status_code == 200


async def test_the_heal_spends_a_regular_slot_before_a_pact_slot(client, monkeypatch):
    _fixed(monkeypatch, 3)
    cid = await _druid(client, 4, "moon")
    await client.post(f"/characters/{cid}/classes", json={"class_name": "warlock", "level": 2, "hit_die": 8})
    form = await _active_form(client, cid, hp=40)
    await _hurt(client, cid, form, 20)
    assert (await _heal(client, cid, form, 1)).status_code == 200
    by_kind = {(s["level"], bool(s.get("is_pact"))): s["used"] for s in (await _full(client, cid))["spell_slots"]}
    assert by_kind[(1, False)] == 1 and by_kind.get((1, True), 0) == 0


async def test_a_spell_with_an_srd_index_is_not_at_will_unless_granted(client):
    cid = await _druid(client, 14, "moon")
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Palla di fuoco", "level": 3, "srd_index": "fireball"})
    assert r.status_code == 201, r.text
    assert r.json()["at_will"] is False
    listed = {s["srd_index"]: s for s in (await _spells(client, cid)).values()}
    assert listed["fireball"]["at_will"] is False and listed["alter-self"]["at_will"] is True
    use = await client.post(f"/characters/{cid}/spells/{r.json()['id']}/use", json={"free_cast": True})
    assert use.status_code == 409


# ---------------------------------------------------------------------------
# M12: la semina una tantum dà il Druidico a un druido esistente
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("edition", ["2014", "2024"])
def test_seeding_an_existing_druid_adds_druidic(edition):
    from core.db.models import CharacterClass
    from core.rules.proficiencies import seed_character
    char = Character(user_id=1, name="Vecchio druido", rules_edition=edition, languages=["Comune"], settings={})
    char.classes = [CharacterClass(class_name="druid", level=4)]
    seed_character(char)
    assert char.languages == ["Comune", "Druidico"]
    assert char.settings["proficiencies_seeded"] is True


# ---------------------------------------------------------------------------
# I8: la scelta dice da quale elenco di classe si pesca (il client filtra il catalogo)
# ---------------------------------------------------------------------------

async def test_the_cantrip_picks_name_the_druid_spell_list(client):
    from tests.integration.rules.test_2014_cleric import _cleric
    land = _choice(await _full(client, await _druid(client, 3, "land")), "bonus_cantrip")
    assert land["spell_pick"]["list"] == "druid" and land["spell_pick"]["max_level"] == 0
    nature = _choice(await _full(client, await _cleric(client, 1, "nature")), "nature_cantrip")
    assert nature["spell_pick"]["list"] == "druid" and nature["spell_pick"]["max_level"] == 0


async def test_a_pick_from_any_class_names_no_list(client):
    from tests.integration.rules.test_2014_bard import _bard
    secrets = _choice(await _full(client, await _bard(client, 10)), "magical_secrets")
    assert secrets["spell_pick"]["list"] is None


# ---------------------------------------------------------------------------
# Giro 2, m3: una condizione respinta per immunita non lascia effetti ne TS
# ---------------------------------------------------------------------------

async def test_a_rich_condition_refused_by_the_ward_leaves_no_effect_and_no_save(client, test_session_factory):
    from core.db.models import ConditionEffect, PendingSave
    sid, cid, comb = await _druid_at_the_table(client, test_session_factory)
    body = {"slug": "poisoned", "expiry": {"anchor": "owner", "edge": "end", "count": 3},
            "save": {"ability": "constitution", "dc": 14, "edge": "end"}}
    r = await client.post(f"/sessions/{sid}/encounter/combatants/{comb}/conditions", json=body)
    assert r.status_code == 200, r.text
    assert not (await _full(client, cid))["conditions"].get("poisoned")
    async with test_session_factory() as s:
        assert (await s.execute(select(ConditionEffect))).scalars().all() == []
        assert (await s.execute(select(PendingSave))).scalars().all() == []


async def test_a_rich_condition_the_druid_can_suffer_still_leaves_its_effect(client, test_session_factory):
    from core.db.models import ConditionEffect
    sid, cid, comb = await _druid_at_the_table(client, test_session_factory)
    body = {"slug": "prone", "expiry": {"anchor": "owner", "edge": "end", "count": 3}}
    assert (await client.post(f"/sessions/{sid}/encounter/combatants/{comb}/conditions", json=body)).status_code == 200
    async with test_session_factory() as s:
        assert len((await s.execute(select(ConditionEffect))).scalars().all()) == 1


async def test_a_failed_save_for_a_condition_the_druid_is_immune_to_leaves_no_effect(client, test_session_factory):
    from api.services.rules_targets import activate_pending_effect
    from core.db.models import ConditionEffect
    cid = await _druid(client, 10, "land")
    async with test_session_factory() as s:
        s.add(ConditionEffect(character_id=cid, slug="poisoned", pending=True, created_at=NOW))
        s.add(ConditionEffect(character_id=cid, slug="prone", pending=True, created_at=NOW))
        await s.commit()
        for eff in (await s.execute(select(ConditionEffect).order_by(ConditionEffect.id))).scalars().all():
            await activate_pending_effect(s, eff)
        await s.commit()
    async with test_session_factory() as s:
        left = [e.slug for e in (await s.execute(select(ConditionEffect))).scalars().all()]
    assert left == ["prone"]
    conditions = (await _full(client, cid))["conditions"]
    assert conditions.get("prone") is True and not conditions.get("poisoned")

"""Minori rinviati, Task 5, giro 1: i rilievi della revisione (I1-I3, M9, M10, M14b)."""
from __future__ import annotations

from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, setup_full_encounter
from tests.integration._telegram_stub import install_fake_telegram
from tests.integration.rules.test_2014_bard import _full, _use
from tests.integration.rules.test_2024_warlock_patrons import VENGEANCE, _hp, _make
from tests.integration.rules.test_2024_warlock_review2 import _chain


async def test_giro1_i1_the_companion_history_writes_the_damage_that_was_applied(client):
    cid, fam = await _chain(client)
    r = await client.patch(f"/characters/{cid}/companions/{fam['id']}/hp", json={"op": "damage", "value": 9, "resist": True})
    assert r.status_code == 200, r.text
    hist = [h["description"] for h in (await client.get(f"/characters/{cid}/history")).json() if h["event_type"] == "companion_hp"]
    assert hist and "damage 4 " in hist[0] and "damage 9" not in hist[0], hist


async def test_giro1_i3_a_patron_spell_without_a_stored_school_still_gets_the_no_components_option(client):
    from tests.integration.rules.test_2014_bard import _roll_keys
    cid = await _make(client, "great_old_one", 5)
    spells = (await _full(client, cid))["spells"]
    by_index = {s["srd_index"]: s["id"] for s in spells if s.get("srd_index")}
    for index in ("tashas-hideous-laughter", "dissonant-whispers", "phantasmal-force"):
        assert "warlock.psychic_spells_silent" in await _roll_keys(client, cid, "cast", spell_id=by_index[index]), index
    assert "warlock.psychic_spells_silent" not in await _roll_keys(client, cid, "cast", spell_id=by_index["detect-thoughts"])


async def _vengeance_fight(client, factory, monkeypatch):
    """Una serata con un incontro attivo (turno del PG) in cui il PG è un warlock Celestiale 2024 a 0 PF."""
    install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, factory)
    pc = (await client.post(f"/sessions/{sid}/encounter/start", json={})).json()["combatants"][0]
    cid = pc["character_id"]
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "warlock", "level": 14, "hit_die": 8, "subclass": "Patrono Celestiale"})
    assert r.status_code == 201, r.text
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    await _hp(client, cid, op="set_max", value=80)
    await _hp(client, cid, op="set_current", value=0)
    return sid, cid


async def _blinded(client, sid, target) -> bool:
    as_user(GM_ID)
    live = (await client.get(f"/sessions/{sid}/live")).json()["encounter"]
    as_user(PLAYER_ID)
    return bool(next(c for c in live["combatants"] if c["id"] == target)["conditions"].get("blinded"))


async def _next(client, sid) -> None:
    as_user(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/next-turn")).status_code == 200
    as_user(PLAYER_ID)


async def _vengeance_on(client, sid, cid, mode, target, advance_first=0):
    for _ in range(advance_first):
        await _next(client, sid)
    assert (await _use(client, cid, VENGEANCE, params={"mode": mode})).status_code == 200
    r = await client.post(f"/characters/{cid}/target-effects", json={"combatant_id": target, "effect_key": VENGEANCE})
    assert r.status_code == 200, r.text


async def test_giro1_i2_searing_vengeance_blinds_until_the_end_of_the_turn_in_progress(client, test_session_factory, monkeypatch):
    sid, cid = await _vengeance_fight(client, test_session_factory, monkeypatch)
    as_user(GM_ID)
    enc = (await client.get(f"/sessions/{sid}/live")).json()["encounter"]
    as_user(PLAYER_ID)
    g1 = [c["id"] for c in enc["combatants"] if c["kind"] == "monster"][0]
    await _vengeance_on(client, sid, cid, "self", g1)  # turno del warlock
    assert await _blinded(client, sid, g1)
    await _next(client, sid)  # fine del turno del warlock
    assert not await _blinded(client, sid, g1)


async def test_giro1_i2_searing_vengeance_for_an_ally_ends_with_the_turn_of_whoever_is_acting(client, test_session_factory, monkeypatch):
    sid, cid = await _vengeance_fight(client, test_session_factory, monkeypatch)
    as_user(GM_ID)
    enc = (await client.get(f"/sessions/{sid}/live")).json()["encounter"]
    as_user(PLAYER_ID)
    g1, g2 = [c["id"] for c in enc["combatants"] if c["kind"] == "monster"]
    await _next(client, sid)  # tocca a g1: l'alleato in fin di vita agisce nel suo turno, non nel mio
    await _vengeance_on(client, sid, cid, "ally", g2)
    assert await _blinded(client, sid, g2)
    await _next(client, sid)  # fine del turno di g1
    assert not await _blinded(client, sid, g2)


async def test_giro1_m9_the_resilience_row_lists_the_types_the_rest_accepts(client):
    cid = await _make(client, "fiend", 10)
    row = next(a for a in (await _full(client, cid))["abilities"] if a["feature_key"] == "warlock.fiendish_resilience")
    assert "slashing" in row["rest_damage_choices"] and "force" not in row["rest_damage_choices"] and not row["has_on_use"]


async def _beyond_options(factory, cid, names):
    from sqlalchemy import select
    from api.services.character_load import refresh_char_full
    from api.services.ddb_import import apply_class_options
    from api.services.ddb_import import ImportReport
    from core.db.models import Character
    async with factory() as s:
        owner = (await s.execute(select(Character.user_id).where(Character.id == cid))).scalar_one()
        char = await refresh_char_full(s, cid, owner)
        report = ImportReport()
        apply_class_options(char, [{"class_index": 0, "name": n} for n in names], report, "it")
        return char.classes[0].options.get("invocations", []), [e.name for e in report.approximated]


async def test_giro1_m14b_beyond_repeatable_invocations_pick_the_only_allowed_cantrip(client, test_session_factory):
    from tests.integration.rules.test_2024_warlock import _cantrip, _warlock24
    cid = await _warlock24(client, 5, charisma=16)
    await _cantrip(client, cid, "eldritch-blast")
    options, approximated = await _beyond_options(test_session_factory, cid, ["Agonizing Blast", "Repelling Blast", "Armor of Shadows"])
    assert set(options) == {"agonizing_blast__eldritch_blast", "repelling_blast__eldritch_blast", "armor_of_shadows"} and approximated == []


async def test_giro1_m14b_with_two_allowed_cantrips_the_repeatable_stays_approximated(client, test_session_factory):
    from tests.integration.rules.test_2024_warlock import _cantrip, _warlock24
    cid = await _warlock24(client, 5, charisma=16)
    await _cantrip(client, cid, "eldritch-blast")
    await _cantrip(client, cid, "chill-touch")
    options, approximated = await _beyond_options(test_session_factory, cid, ["Agonizing Blast"])
    assert options == [] and approximated == ["Agonizing Blast"]


async def test_giro1_m10_magical_cunning_previews_the_slots_that_come_back_before_the_touch(client):
    from tests.integration.rules.test_2024_warlock import CUNNING, _set_used, _warlock24
    from tests.integration.rules.test_2014_warlock import _pact_slots
    cid = await _warlock24(client, 11)
    row = lambda full: next(a for a in full["abilities"] if a["feature_key"] == CUNNING)
    assert row(await _full(client, cid))["use_preview"] is None  # nessuno slot speso: niente da far tornare
    [pact] = await _pact_slots(client, cid)
    await _set_used(client, cid, pact["id"], 3)
    preview = row(await _full(client, cid))["use_preview"]
    assert "2 slot di Patto" in preview["it"] and "2 Pact slots" in preview["en"]


def test_giro1_m3_a_new_find_steed_cast_keeps_the_name_of_the_steed_it_replaces():
    from types import SimpleNamespace
    from core.db.models import Companion
    from core.rules.catalog.y2024.paladin import STEED, make_steed
    char = SimpleNamespace(id=1, companions=[Companion(kind="mount", name="Fulmine", feature_key=STEED)])
    make_steed(char, "", 4)
    assert [c.name for c in char.companions] == ["Fulmine"] and char.companions[0].max_hp == 45
    make_steed(char, "Tuono", 4)
    assert [c.name for c in char.companions] == ["Tuono"]


async def test_giro1_m4_an_unrecognised_subclass_does_not_take_the_proficiencies_away(client, test_session_factory):
    from sqlalchemy import select, update
    from core.db.models import CharacterClass
    r = await client.post("/characters", json={"name": "Guerra", "initial_class": {
        "class_name": "cleric", "level": 3, "subclass": "Dominio della Guerra"}})
    cid = r.json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2014"})).status_code == 200
    assert "Armature pesanti" in (await client.get(f"/characters/{cid}")).json()["general_proficiencies"]["armor"]
    async with test_session_factory() as s:
        await s.execute(update(CharacterClass).where(CharacterClass.character_id == cid).values(subclass="Dominio Segreto", subclass_key=None))
        await s.commit()
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    assert "Armature pesanti" in (await client.get(f"/characters/{cid}")).json()["general_proficiencies"]["armor"]

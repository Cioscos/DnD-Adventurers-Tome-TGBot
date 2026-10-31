"""Il GM applica condizioni ricche dalla stanza della sessione (spec §3)."""
from __future__ import annotations

from sqlalchemy import select

from api.services.condition_effects import ExpirySpec, SaveSpec, upsert_effect
from core.db.models import (
    Character, Combatant, ConditionEffect, Encounter, PendingSave, Spell,
)
from tests.integration._encounter_helpers import (
    GM_ID, PLAYER_ID, as_user, setup_full_encounter,
)
from tests.integration._telegram_stub import install_fake_telegram


async def _start(client, test_session_factory, monkeypatch):
    """Incontro attivo, turno del PG. Ritorna (captured, sid, char_id, pc_id, g1_id, g2_id)."""
    captured = install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, test_session_factory)
    r = await client.post(f"/sessions/{sid}/encounter/start", json={})
    assert r.status_code == 200, r.text
    pc, g1, g2 = r.json()["combatants"]
    return captured, sid, pc["character_id"], pc["id"], g1["id"], g2["id"]


def _url(sid, cid, *rest):
    return "/".join([f"/sessions/{sid}/encounter/combatants/{cid}/conditions", *rest])


async def _effects(test_session_factory, **where):
    async with test_session_factory() as s:
        q = select(ConditionEffect)
        for k, v in where.items():
            q = q.where(getattr(ConditionEffect, k) == v)
        return list((await s.execute(q)).scalars())


async def test_gm_applies_condition_to_pc_sheet(client, test_session_factory, monkeypatch):
    captured, sid, char_id, pc_id, g1, _ = await _start(client, test_session_factory, monkeypatch)
    captured.clear()
    r = await client.post(_url(sid, pc_id), json={
        "slug": "frightened", "expiry": {"anchor": "source", "edge": "end", "count": 1},
        "save": {"ability": "wisdom", "dc": 13, "edge": "end"}, "source_combatant_id": g1,
    })
    assert r.status_code == 200, r.text
    pc = next(c for c in r.json()["combatants"] if c["id"] == pc_id)
    assert pc["conditions"] == {}  # la fonte per i PG è la scheda
    async with test_session_factory() as s:
        assert (await s.get(Character, char_id)).conditions == {"frightened": True}
    [eff] = await _effects(test_session_factory, character_id=char_id)
    assert eff.applied_by_gm and eff.encounter_id is not None
    assert eff.source_combatant_id == g1 and eff.save_dc == 13 and eff.expiry_count == 1
    msgs = [c["json"] for c in captured if c["json"]["chat_id"] == PLAYER_ID]
    assert len(msgs) == 1 and "🌀" in msgs[0]["text"] and "Spaventato" in msgs[0]["text"]
    as_user(PLAYER_ID)
    hist = (await client.get(f"/characters/{char_id}/history")).json()
    assert any("Spaventato" in h["description"] for h in hist)


async def test_gm_applies_to_monster(client, test_session_factory, monkeypatch):
    _, sid, _, _, g1, _ = await _start(client, test_session_factory, monkeypatch)
    r = await client.post(_url(sid, g1), json={
        "slug": "prone", "expiry": {"anchor": "owner", "edge": "start", "count": 2},
    })
    assert r.status_code == 200, r.text
    mon = next(c for c in r.json()["combatants"] if c["id"] == g1)
    assert mon["conditions"] == {"prone": True}
    assert mon["condition_effects"][0]["slug"] == "prone"
    assert mon["condition_effects"][0]["expiry_count"] == 2
    # Sostituzione: riapplicare rimpiazza l'effetto
    await client.post(_url(sid, g1), json={"slug": "prone"})
    [eff] = await _effects(test_session_factory, combatant_id=g1)
    assert eff.expiry_count is None
    # DELETE spegne e cancella l'effetto
    r = await client.delete(_url(sid, g1, "prone"))
    assert r.status_code == 200, r.text
    mon = next(c for c in r.json()["combatants"] if c["id"] == g1)
    assert not mon["conditions"].get("prone") and mon["condition_effects"] == []
    assert await _effects(test_session_factory, combatant_id=g1) == []


async def test_gm_delete_on_pc_clears_sheet(client, test_session_factory, monkeypatch):
    captured, sid, char_id, pc_id, *_ = await _start(client, test_session_factory, monkeypatch)
    await client.post(_url(sid, pc_id), json={"slug": "poisoned"})
    captured.clear()
    r = await client.delete(_url(sid, pc_id, "poisoned"))
    assert r.status_code == 200, r.text
    async with test_session_factory() as s:
        assert not (await s.get(Character, char_id)).conditions.get("poisoned")
    assert await _effects(test_session_factory, character_id=char_id) == []
    assert len([c for c in captured if c["json"]["chat_id"] == PLAYER_ID]) == 1


async def test_player_cannot_apply(client, test_session_factory, monkeypatch):
    _, sid, _, pc_id, *_ = await _start(client, test_session_factory, monkeypatch)
    as_user(PLAYER_ID)
    r = await client.post(_url(sid, pc_id), json={"slug": "prone"})
    assert r.status_code == 403
    r = await client.delete(_url(sid, pc_id, "prone"))
    assert r.status_code == 403


async def test_concentration_link_requires_concentrating_source(
    client, test_session_factory, monkeypatch,
):
    _, sid, _, pc_id, g1, g2 = await _start(client, test_session_factory, monkeypatch)
    for src in (pc_id, g2):  # PG non concentrato, poi un mostro
        r = await client.post(_url(sid, g1), json={
            "slug": "charmed", "source_combatant_id": src, "ends_with_concentration": True,
        })
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["code"] == "source_not_concentrating"
    r = await client.post(_url(sid, g1), json={"slug": "charmed", "ends_with_concentration": True})
    assert r.status_code == 422


async def test_link_records_spell(client, test_session_factory, monkeypatch):
    _, sid, char_id, pc_id, g1, _ = await _start(client, test_session_factory, monkeypatch)
    async with test_session_factory() as s:
        sp = Spell(character_id=char_id, name="Blocca persone", level=2)
        s.add(sp)
        await s.flush()
        (await s.get(Character, char_id)).concentrating_spell_id = sp.id
        await s.commit()
        spell_id = sp.id
    live = (await client.get(f"/sessions/{sid}/live")).json()["live_characters"]
    assert next(c for c in live if c["id"] == char_id)["is_concentrating"] is True
    r = await client.post(_url(sid, g1), json={
        "slug": "paralyzed", "source_combatant_id": pc_id, "ends_with_concentration": True,
    })
    assert r.status_code == 200, r.text
    [eff] = await _effects(test_session_factory, combatant_id=g1)
    assert eff.source_spell_id == spell_id and eff.source_character_id == char_id
    assert eff.ends_with_concentration
    mon = next(c for c in r.json()["combatants"] if c["id"] == g1)
    assert mon["condition_effects"][0]["source_name"] == "Eroe"


async def test_gm_sets_exhaustion_value(client, test_session_factory, monkeypatch):
    _, sid, char_id, pc_id, *_ = await _start(client, test_session_factory, monkeypatch)
    r = await client.post(_url(sid, pc_id), json={"slug": "exhaustion"})
    assert r.status_code == 422  # spossatezza: solo con value
    r = await client.post(_url(sid, pc_id), json={"slug": "exhaustion", "value": 2})
    assert r.status_code == 200, r.text
    async with test_session_factory() as s:
        assert (await s.get(Character, char_id)).conditions["exhaustion"] == 2
    assert await _effects(test_session_factory, character_id=char_id) == []
    r = await client.post(_url(sid, pc_id), json={
        "slug": "custom:maledetto", "value": True,
        "expiry": {"anchor": "owner", "edge": "start", "count": 1},
    })
    assert r.status_code == 422  # value esclude i campi ricchi


async def test_patch_pc_conditions_rejected(client, test_session_factory, monkeypatch):
    _, sid, _, pc_id, g1, _ = await _start(client, test_session_factory, monkeypatch)
    r = await client.patch(f"/sessions/{sid}/encounter/combatants/{pc_id}",
                           json={"conditions": {"prone": True}})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "pc_conditions_on_sheet"
    # Mostro: il PATCH resta, e spegnere una condizione cancella l'effetto
    await client.post(_url(sid, g1), json={"slug": "prone",
                                           "expiry": {"anchor": "owner", "edge": "start", "count": 2}})
    r = await client.patch(f"/sessions/{sid}/encounter/combatants/{g1}",
                           json={"conditions": {"prone": False}})
    assert r.status_code == 200, r.text
    assert await _effects(test_session_factory, combatant_id=g1) == []


async def _monster_save(client, test_session_factory, sid, g1):
    """Mostro trattenuto con TS a fine turno; si arriva al suo turno e lo si chiude."""
    r = await client.post(_url(sid, g1), json={
        "slug": "restrained", "save": {"ability": "strength", "dc": 12, "edge": "end"},
    })
    assert r.status_code == 200, r.text
    for _ in range(2):  # PG -> g1 -> g2: fine turno di g1
        r = await client.post(f"/sessions/{sid}/encounter/next-turn")
        assert r.status_code == 200, r.text
    mon = next(c for c in r.json()["combatants"] if c["id"] == g1)
    [ps] = mon["pending_saves"]
    return ps


async def test_resolve_monster_save_passed_removes_condition(
    client, test_session_factory, monkeypatch,
):
    _, sid, char_id, _, g1, _ = await _start(client, test_session_factory, monkeypatch)
    ps = await _monster_save(client, test_session_factory, sid, g1)
    url = f"/sessions/{sid}/encounter/pending-saves/{ps['id']}/resolve"
    as_user(PLAYER_ID)
    assert (await client.post(url, json={"passed": True})).status_code == 403
    as_user(GM_ID)
    r = await client.post(url, json={"passed": True})
    assert r.status_code == 200, r.text
    mon = next(c for c in r.json()["combatants"] if c["id"] == g1)
    assert not mon["conditions"].get("restrained")
    assert mon["condition_effects"] == [] and mon["pending_saves"] == []
    # TS di un PG: 422
    async with test_session_factory() as s:
        eff = await upsert_effect(s, ("character", char_id), "poisoned",
                                  save=SaveSpec("constitution", 10, "end"))
        pc_ps = PendingSave(effect_id=eff.id, character_id=char_id, ability="constitution",
                            dc=10, status="pending", created_at="2026-10-31T10:00:00")
        s.add(pc_ps)
        await s.commit()
        pc_ps_id = pc_ps.id
    r = await client.post(f"/sessions/{sid}/encounter/pending-saves/{pc_ps_id}/resolve",
                          json={"passed": True})
    assert r.status_code == 422


async def test_resolve_monster_save_failed_keeps_condition(
    client, test_session_factory, monkeypatch,
):
    _, sid, _, _, g1, _ = await _start(client, test_session_factory, monkeypatch)
    ps = await _monster_save(client, test_session_factory, sid, g1)
    r = await client.post(f"/sessions/{sid}/encounter/pending-saves/{ps['id']}/resolve",
                          json={"passed": False})
    assert r.status_code == 200, r.text
    mon = next(c for c in r.json()["combatants"] if c["id"] == g1)
    assert mon["conditions"]["restrained"] is True and mon["pending_saves"] == []


async def test_live_exposes_effects_and_pending_flag(client, test_session_factory, monkeypatch):
    _, sid, char_id, pc_id, g1, _ = await _start(client, test_session_factory, monkeypatch)
    await client.post(_url(sid, pc_id), json={
        "slug": "poisoned", "save": {"ability": "constitution", "dc": 11, "edge": "end"},
        "source_combatant_id": g1,
    })
    as_user(PLAYER_ID)
    pc = next(c for c in (await client.get(f"/sessions/{sid}/live")).json()["live_characters"])
    assert pc["condition_effects"][0]["slug"] == "poisoned"
    assert pc["condition_effects"][0]["source_name"] == "Goblin 1"
    assert pc["has_pending_save"] is False
    as_user(GM_ID)
    # Applicato sul turno del PG con TS a fine turno: il primo bordo si salta
    for _ in range(3):  # PG -> g1 -> g2 -> PG
        await client.post(f"/sessions/{sid}/encounter/next-turn")
    r = await client.post(f"/sessions/{sid}/encounter/next-turn")  # fine turno PG
    assert r.status_code == 200, r.text
    as_user(PLAYER_ID)
    pc = next(c for c in (await client.get(f"/sessions/{sid}/live")).json()["live_characters"])
    assert pc["has_pending_save"] is True


async def test_monster_pending_saves_hidden_from_players(
    client, test_session_factory, monkeypatch,
):
    _, sid, _, _, g1, _ = await _start(client, test_session_factory, monkeypatch)
    await _monster_save(client, test_session_factory, sid, g1)
    async with test_session_factory() as s:
        [ps] = list((await s.execute(select(PendingSave))).scalars())
        assert ps.character_id is None and ps.combatant_id == g1
    as_user(PLAYER_ID)
    enc = (await client.get(f"/sessions/{sid}/live")).json()["encounter"]
    mon = next(c for c in enc["combatants"] if c["id"] == g1)
    assert mon["pending_saves"] == []
    assert mon["condition_effects"][0]["slug"] == "restrained"  # l'effetto resta visibile
    as_user(GM_ID)
    enc = (await client.get(f"/sessions/{sid}/live")).json()["encounter"]
    assert len(next(c for c in enc["combatants"] if c["id"] == g1)["pending_saves"]) == 1


async def test_monster_owner_start_expiry_on_its_turn(client, test_session_factory, monkeypatch):
    """Motore del tempo (Task 3) sui mostri: owner/start/1 scade all'inizio del suo turno."""
    _, sid, _, _, g1, _ = await _start(client, test_session_factory, monkeypatch)
    async with test_session_factory() as s:
        comb = await s.get(Combatant, g1)
        comb.conditions = {"blinded": True}
        await upsert_effect(s, ("combatant", g1), "blinded",
                            expiry=ExpirySpec("owner", "start", 1),
                            save=SaveSpec("constitution", 12, "end"))
        await s.commit()
    r = await client.post(f"/sessions/{sid}/encounter/next-turn")  # PG -> g1
    assert r.status_code == 200, r.text
    mon = next(c for c in r.json()["combatants"] if c["id"] == g1)
    assert not mon["conditions"].get("blinded") and mon["condition_effects"] == []
    async with test_session_factory() as s:
        assert list((await s.execute(select(PendingSave))).scalars()) == []
        assert (await s.get(Encounter, (await s.get(Combatant, g1)).encounter_id)) \
            .last_advance_undo["expired"][0]["slug"] == "blinded"

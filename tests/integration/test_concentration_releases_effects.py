"""Fine (o cambio) della concentrazione di un PG → fine delle condizioni collegate (spec §5)."""
from __future__ import annotations

import random

from sqlalchemy import select

from api.services.condition_effects import SaveSpec, upsert_effect
from core.data.labels import condition_label
from core.db.models import Character, Combatant, ConditionEffect, PendingSave
from tests.integration._encounter_helpers import PLAYER_ID, as_user
from tests.integration.test_condition_time import _advance, _start
from tests.integration.test_condition_undo import _back
from tests.integration.test_item_charges import _ch
from tests.integration.test_magic_items import _item

SLUG = "frightened"


def _force_d20(monkeypatch, value: int) -> None:
    monkeypatch.setattr(random, "randint", lambda a, b: value)


async def _hp(client, cid, op, value):
    r = await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": value})
    assert r.status_code == 200, r.text
    return r.json()


async def _char(client, name="Gandalf") -> int:
    r = await client.post("/characters", json={"name": name})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    await _hp(client, cid, "set_max", 20)
    await _hp(client, cid, "set_current", 20)
    return cid


async def _spell(client, cid, name="Bless", **kw) -> int:
    r = await client.post(f"/characters/{cid}/spells",
                          json={"name": name, "level": 1, "is_concentration": True, **kw})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _concentrate(client, cid, spell_id, rounds=None):
    body = {"spell_id": spell_id} | ({"rounds": rounds} if rounds is not None else {})
    r = await client.patch(f"/characters/{cid}/concentration", json=body)
    assert r.status_code == 200, r.text


async def _link(factory, caster, spell_id, target=None, combatant=None):
    """Condizione SLUG sul bersaglio, collegata alla concentrazione di caster su spell_id."""
    async with factory() as s:
        owner = await s.get(Character if target else Combatant, target or combatant)
        owner.conditions = {**(owner.conditions or {}), SLUG: True}
        await upsert_effect(s, ("character", target) if target else ("combatant", combatant),
                            SLUG, source_character_id=caster, source_spell_id=spell_id,
                            ends_with_concentration=True,
                            save=SaveSpec("wisdom", 13, "end") if combatant else None)
        await s.commit()


async def _linked(factory, target=None, combatant=None) -> tuple[object, bool]:
    async with factory() as s:
        owner = await s.get(Character if target else Combatant, target or combatant)
        col = ConditionEffect.character_id if target else ConditionEffect.combatant_id
        eff = (await s.execute(select(ConditionEffect.id).where(
            col == (target or combatant), ConditionEffect.slug == SLUG))).first()
        return (owner.conditions or {}).get(SLUG), eff is not None


async def _setup(client, factory):
    caster = await _char(client)
    target = await _char(client, "Frodo")
    spell = await _spell(client, caster)
    await _concentrate(client, caster, spell)
    await _link(factory, caster, spell, target)
    return caster, target, spell


async def _assert_released(client, factory, target):
    assert await _linked(factory, target) == (False, False)
    hist = (await client.get(f"/characters/{target}/history")).json()
    want = f"Terminata (fine concentrazione di Gandalf): {condition_label(SLUG)}"
    assert any(h["description"] == want for h in hist)


async def test_release_on_damage_failed_save(client, test_session_factory, monkeypatch):
    caster, target, _ = await _setup(client, test_session_factory)
    _force_d20(monkeypatch, 1)
    assert (await _hp(client, caster, "damage", 5))["concentrating_spell_id"] is None
    await _assert_released(client, test_session_factory, target)


async def test_release_on_zero_hp(client, test_session_factory):
    caster, target, _ = await _setup(client, test_session_factory)
    await _hp(client, caster, "damage", 20)
    await _assert_released(client, test_session_factory, target)


async def test_release_on_short_rest(client, test_session_factory):
    caster, target, _ = await _setup(client, test_session_factory)
    r = await client.post(f"/characters/{caster}/rest", json={"rest_type": "short"})
    assert r.status_code == 200, r.text
    await _assert_released(client, test_session_factory, target)


async def test_release_on_long_rest(client, test_session_factory):
    caster, target, _ = await _setup(client, test_session_factory)
    r = await client.post(f"/characters/{caster}/rest", json={"rest_type": "long"})
    assert r.status_code == 200, r.text
    await _assert_released(client, test_session_factory, target)


async def test_release_on_manual_removal(client, test_session_factory):
    caster, target, _ = await _setup(client, test_session_factory)
    await _concentrate(client, caster, None)
    await _assert_released(client, test_session_factory, target)


async def test_release_on_manual_switch(client, test_session_factory):
    caster, target, _ = await _setup(client, test_session_factory)
    await _concentrate(client, caster, await _spell(client, caster, "Hold Person"))
    await _assert_released(client, test_session_factory, target)


async def test_switch_keeps_effect_of_new_spell(client, test_session_factory):
    caster, target, _ = await _setup(client, test_session_factory)
    b = await _spell(client, caster, "Hold Person")
    async with test_session_factory() as s:
        (await s.execute(select(ConditionEffect))).scalar_one().source_spell_id = b
        await s.commit()
    await _concentrate(client, caster, b)
    assert await _linked(test_session_factory, target) == (True, True)


async def test_release_on_hp_undo_switch(client, test_session_factory, monkeypatch):
    caster, target, a = await _setup(client, test_session_factory)
    _force_d20(monkeypatch, 1)
    dmg = await _hp(client, caster, "damage", 5)  # A persa: il suo effetto è già rilasciato
    b = await _spell(client, caster, "Hold Person")
    await _link(test_session_factory, caster, b, target)
    r = await client.post(f"/characters/{caster}/hp/undo", json={"op_id": dmg["hp_undo_id"]})
    assert r.status_code == 200, r.text
    assert r.json()["concentrating_spell_id"] == a
    assert await _linked(test_session_factory, target) == (False, False)


async def test_release_on_new_concentration_cast(client, test_session_factory):
    caster, target, _ = await _setup(client, test_session_factory)
    rs = await client.post(f"/characters/{caster}/spell_slots", json={"level": 1, "total": 1})
    assert rs.status_code == 201, rs.text
    b = await _spell(client, caster, "Hold Person")
    r = await client.post(f"/characters/{caster}/spells/{b}/use", json={"slot_level": 1})
    assert r.status_code == 200, r.text
    await _assert_released(client, test_session_factory, target)


async def test_release_on_cantrip_attack(client, test_session_factory):
    caster, target, _ = await _setup(client, test_session_factory)
    b = await _spell(client, caster, "Raggio", level=0, attack_save="ATK")
    r = await client.post(f"/characters/{caster}/spells/{b}/attack", json={})
    assert r.status_code == 200, r.text
    await _assert_released(client, test_session_factory, target)


async def test_release_on_item_cast(client, test_session_factory):
    caster, target, _ = await _setup(client, test_session_factory)
    spell = {"name": "Foschia", "level": 1, "charges_cost": 1, "is_concentration": True}
    iid = await _item(client, caster, charges=_ch(), granted_spells=[spell])
    r = await client.post(f"/characters/{caster}/items/{iid}/cast", json={"spell_index": 0})
    assert r.status_code == 200, r.text
    await _assert_released(client, test_session_factory, target)


async def test_release_on_spell_delete(client, test_session_factory):
    caster, target, spell = await _setup(client, test_session_factory)
    r = await client.delete(f"/characters/{caster}/spells/{spell}")
    assert r.status_code == 204, r.text
    await _assert_released(client, test_session_factory, target)
    async with test_session_factory() as s:
        ch = await s.get(Character, caster)
        assert ch.concentrating_spell_id is None
        assert "concentration_rounds_left" not in (ch.settings or {})


async def test_release_on_revive(client, test_session_factory):
    caster, target, _ = await _setup(client, test_session_factory)
    async with test_session_factory() as s:
        (await s.get(Character, caster)).is_dead = True
        await s.commit()
    r = await client.post(f"/characters/{caster}/revive")
    assert r.status_code == 200, r.text
    await _assert_released(client, test_session_factory, target)


async def test_release_on_concentration_save_helper(client, test_session_factory, monkeypatch):
    caster, target, _ = await _setup(client, test_session_factory)
    _force_d20(monkeypatch, 1)
    r = await client.post(f"/characters/{caster}/concentration/save", json={"damage": 30})
    assert r.status_code == 200 and r.json()["lost_concentration"] is True, r.text
    await _assert_released(client, test_session_factory, target)


async def test_release_on_manual_tick_expiry(client, test_session_factory):
    caster = await _char(client)
    target = await _char(client, "Frodo")
    spell = await _spell(client, caster)
    await _concentrate(client, caster, spell, rounds=1)
    await _link(test_session_factory, caster, spell, target)
    r = await client.post(f"/characters/{caster}/rounds/tick")
    assert r.status_code == 200, r.text
    assert condition_label(SLUG) in r.json()["expired_effects"]
    await _assert_released(client, test_session_factory, target)


async def _edge_setup(client, factory, monkeypatch):
    _, sid, enc_id, cid, _pc, g1, _g2 = await _start(client, factory, monkeypatch)
    as_user(PLAYER_ID)
    spell = await _spell(client, cid)
    await _concentrate(client, cid, spell, rounds=1)
    await _link(factory, cid, spell, combatant=g1)
    await _advance(client, sid)  # fine turno PG
    await _advance(client, sid)  # fine turno g1: TS creato
    async with factory() as s:
        assert len((await s.execute(select(PendingSave))).scalars().all()) == 1
    await _advance(client, sid)  # -> PG: concentrazione scade
    return sid, cid, spell, g1


async def test_release_on_turn_edge_expiry(client, test_session_factory, monkeypatch):
    _, _, _, g1 = await _edge_setup(client, test_session_factory, monkeypatch)
    assert await _linked(test_session_factory, combatant=g1) == (None, False)


async def test_back_restores_concentration_and_linked_effects(
    client, test_session_factory, monkeypatch,
):
    sid, cid, spell, g1 = await _edge_setup(client, test_session_factory, monkeypatch)
    await _back(client, sid)
    async with test_session_factory() as s:
        ch = await s.get(Character, cid)
        assert ch.concentrating_spell_id == spell
        assert ch.settings["concentration_rounds_left"] == 1
        assert [p.status for p in (await s.execute(select(PendingSave))).scalars()] == ["pending"]
    assert await _linked(test_session_factory, combatant=g1) == (True, True)

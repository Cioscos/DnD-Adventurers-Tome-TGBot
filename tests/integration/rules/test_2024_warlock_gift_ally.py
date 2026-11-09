"""Task 49: il Dono dei Protettori del warlock scatta sul danno di un alleato della serata e spende l'uso sulla scheda del warlock
(opzione `for_ally`, R42)."""
from __future__ import annotations

from sqlalchemy import select

from core.db.models import Ability, Character, CharacterHistory, SessionParticipant, SessionRole
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard import _ability, _full
from tests.integration.rules.test_2024_warlock import TOME, _caster24

GIFT = "warlock.gift_of_the_protectors"


async def _table(client, factory, hero_hp=40):
    """Una serata con un warlock del Tomo (GM, livello 9) e un eroe: `(warlock, hero, key)`."""
    _, hero = await seed_session(factory)
    as_user(GM_ID)
    cid = await _caster24(client, 9, TOME, "gift_of_the_protectors")
    async with factory() as s:
        part = (await s.execute(select(SessionParticipant).where(SessionParticipant.user_id == GM_ID))).scalar_one()
        part.character_id = cid
        char = await s.get(Character, hero)
        char.hit_points, char.current_hit_points = max(40, hero_hp), hero_hp
        await s.commit()
    return cid, hero, f"ally:{cid}:{GIFT}"


async def _second_hero(factory) -> int:
    async with factory() as s:
        sess_id = (await s.execute(select(SessionParticipant.session_id))).scalars().first()
        char = Character(user_id=9002, name="Eroina", hit_points=40, current_hit_points=40)
        s.add(char)
        await s.flush()
        s.add(SessionParticipant(session_id=sess_id, user_id=9002, character_id=char.id, role=SessionRole.PLAYER,
                                 display_name="Eroina", joined_at="2026-06-09T10:00:00"))
        await s.commit()
        return char.id


async def _hit(client, hero, uid, value, options):
    as_user(uid)
    return await client.patch(f"/characters/{hero}/hp", json={"op": "damage", "value": value, "options": options})


async def _offered(client, hero, uid, damage=60) -> list[str]:
    as_user(uid)
    r = await client.get(f"/characters/{hero}/roll-options", params={"roll": "damage_taken", "damage": damage})
    assert r.status_code == 200, r.text
    return [o["key"] for o in r.json()]


async def test_the_gift_is_offered_to_a_seated_ally_only_while_the_warlock_has_the_use(client, test_session_factory):
    cid, hero, key = await _table(client, test_session_factory)
    assert key in await _offered(client, hero, PLAYER_ID)
    assert (await _hit(client, hero, PLAYER_ID, 60, [key])).status_code == 200
    assert key not in await _offered(client, hero, PLAYER_ID)  # l'uso è speso


async def test_accepted_the_ally_stays_at_one_hp_and_the_use_is_spent_on_the_warlocks_sheet(client, test_session_factory):
    cid, hero, key = await _table(client, test_session_factory)
    r = await _hit(client, hero, PLAYER_ID, 60, [key])
    assert r.status_code == 200, r.text
    assert r.json()["current_hit_points"] == 1 and r.json()["is_dead"] is False
    as_user(GM_ID)
    assert (await _ability(client, cid, GIFT))["uses"] == 0
    async with test_session_factory() as s:
        mine = (await s.execute(select(CharacterHistory).where(CharacterHistory.character_id == hero))).scalars().all()
        theirs = (await s.execute(select(CharacterHistory).where(CharacterHistory.character_id == cid))).scalars().all()
    assert any("resta a 1 PF grazie a" in e.description for e in mine)
    assert any("speso per Eroe" in e.description for e in theirs)


async def test_with_two_allies_only_the_first_gets_it(client, test_session_factory):
    cid, hero, key = await _table(client, test_session_factory)
    second = await _second_hero(test_session_factory)
    assert (await _hit(client, hero, PLAYER_ID, 60, [key])).json()["current_hit_points"] == 1
    r = await _hit(client, second, 9002, 60, [key])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable"
    async with test_session_factory() as s:
        assert (await s.get(Character, second)).current_hit_points == 40
    as_user(GM_ID)
    assert (await _ability(client, cid, GIFT))["uses"] == 0


async def test_a_warlock_who_is_not_in_the_evening_offers_nothing(client, test_session_factory):
    cid, hero, key = await _table(client, test_session_factory)
    async with test_session_factory() as s:
        part = (await s.execute(select(SessionParticipant).where(SessionParticipant.user_id == GM_ID))).scalar_one()
        await s.delete(part)
        await s.commit()
    assert key not in await _offered(client, hero, PLAYER_ID)
    r = await _hit(client, hero, PLAYER_ID, 60, [key])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable"


async def test_a_blow_that_kills_outright_does_not_spend_the_use(client, test_session_factory):
    cid, hero, key = await _table(client, test_session_factory)
    r = await _hit(client, hero, PLAYER_ID, 85, [key])  # 85 - 40 PF >= 40 massimi: morte sul colpo
    assert r.status_code == 200, r.text
    assert r.json()["is_dead"] is True
    as_user(GM_ID)
    assert (await _ability(client, cid, GIFT))["uses"] == 1


async def test_damage_that_does_not_reach_zero_spends_nothing(client, test_session_factory):
    cid, hero, key = await _table(client, test_session_factory)
    r = await _hit(client, hero, PLAYER_ID, 10, [key])
    assert r.status_code == 200 and r.json()["current_hit_points"] == 30
    as_user(GM_ID)
    assert (await _ability(client, cid, GIFT))["uses"] == 1


async def test_undoing_the_damage_gives_the_warlock_his_use_back(client, test_session_factory):
    cid, hero, key = await _table(client, test_session_factory)
    r = await _hit(client, hero, PLAYER_ID, 60, [key])
    assert r.status_code == 200 and r.json()["current_hit_points"] == 1
    as_user(PLAYER_ID)
    undo = await client.post(f"/characters/{hero}/hp/undo", json={"op_id": r.json()["hp_undo_id"]})
    assert undo.status_code == 200, undo.text
    assert undo.json()["current_hit_points"] == 40
    as_user(GM_ID)
    assert (await _ability(client, cid, GIFT))["uses"] == 1


async def test_a_blow_that_kills_outright_is_not_offered_the_gift(client, test_session_factory):
    cid, hero, key = await _table(client, test_session_factory)
    assert key in await _offered(client, hero, PLAYER_ID, damage=60)
    assert key not in await _offered(client, hero, PLAYER_ID, damage=85)
    as_user(GM_ID)
    assert "warlock.gift_of_the_protectors" not in await _offered(client, cid, GM_ID, damage=1000)


async def test_the_refund_is_one_atomic_update_capped_at_max_uses(client, test_session_factory):
    from api.services.session_allies import refund_donor_tokens
    cid, hero, key = await _table(client, test_session_factory)
    async with test_session_factory() as s:
        row = (await s.execute(select(Ability).where(Ability.character_id == cid, Ability.feature_key == GIFT))).scalar_one()
        row_id, row.max_uses, row.uses = row.id, 2, 0
        await s.commit()
    token = f"donor:{cid}:{row_id}:1"
    async with test_session_factory() as stale, test_session_factory() as other:
        receiver = await stale.get(Character, hero)
        assert (await stale.get(Ability, row_id)).uses == 0  # la riga letta resta ferma a 0
        (await other.get(Ability, row_id)).uses = 1  # un'altra richiesta intanto ha già restituito un uso
        await other.commit()
        await refund_donor_tokens(stale, receiver, [token])
        await stale.commit()
    async with test_session_factory() as s:
        assert (await s.get(Ability, row_id)).uses == 2  # 1 + 1: niente aggiornamento perso
        await refund_donor_tokens(s, receiver, [token])  # un terzo rimborso non supera il tetto
        await s.commit()
        assert (await s.get(Ability, row_id)).uses == 2
        theirs = (await s.execute(select(CharacterHistory).where(CharacterHistory.character_id == cid))).scalars().all()
    assert any("uso restituito" in e.description for e in theirs)


async def test_the_kill_threshold_uses_the_effective_maximum_with_a_hit_point_bonus(client, test_session_factory):
    from tests.integration.homebrew.test_passive_modifiers import _ALWAYS_TRUE_CHAR, _build_passive_rule
    cid, hero, key = await _table(client, test_session_factory)
    as_user(PLAYER_ID)
    rule = _build_passive_rule("+10 PF", {"type": "character"}, "character.hit_points_max", 10, _ALWAYS_TRUE_CHAR)
    assert (await client.post(f"/characters/{hero}/homebrew/rules", json=rule)).status_code in (200, 201)
    # 85 - 40 PF = 45: sopra i 40 base, sotto i 50 effettivi: non uccide sul colpo
    assert key in await _offered(client, hero, PLAYER_ID, damage=85)
    r = await _hit(client, hero, PLAYER_ID, 85, [key])
    assert r.status_code == 200 and r.json()["current_hit_points"] == 1 and r.json()["is_dead"] is False


async def test_a_damage_with_options_loads_the_seated_allies_once(client, test_session_factory, monkeypatch):
    import api.services.session_allies as allies
    cid, hero, key = await _table(client, test_session_factory)
    calls = []
    real = allies.seated_allies

    async def counting(session, char):
        calls.append(char.id)
        return await real(session, char)

    monkeypatch.setattr(allies, "seated_allies", counting)
    assert (await _hit(client, hero, PLAYER_ID, 10, [key])).status_code == 200
    assert len(calls) == 1
    calls.clear()
    await _offered(client, hero, PLAYER_ID)
    assert len(calls) == 1


async def test_holding_at_one_has_no_fake_reduction_and_the_history_shows_the_hit_points_really_lost(client, test_session_factory):
    cid, hero, key = await _table(client, test_session_factory)
    r = await _hit(client, hero, PLAYER_ID, 60, [key])
    assert r.status_code == 200 and r.json()["current_hit_points"] == 1
    block = r.json()["option_result"]
    assert block["damage_before"] is None and block["damage_after"] is None  # il danno non è stato ridotto
    history = (await client.get(f"/characters/{hero}/history")).json()
    assert any("Danni: -39 HP (40 → 1)" in e["description"] for e in history)


async def _lines(factory, hero):
    async with factory() as s:
        return (await s.execute(select(CharacterHistory).where(CharacterHistory.character_id == hero,
                                                               CharacterHistory.event_type == "hp_change"))).scalars().all()


async def test_held_at_one_the_history_and_the_recap_count_the_hit_points_really_lost(client, test_session_factory):
    cid, hero, key = await _table(client, test_session_factory, hero_hp=44)
    r = await _hit(client, hero, PLAYER_ID, 50, [key])
    assert r.status_code == 200 and r.json()["current_hit_points"] == 1
    rows = await _lines(test_session_factory, hero)
    assert any("Danni: -43 HP (44 → 1)" in e.description for e in rows)
    assert [e.meta["amount"] for e in rows if e.meta and e.meta.get("op") == "DAMAGE"] == [43]


async def test_held_at_one_with_resistance_the_arrow_shows_the_damage_after_resistance(client, test_session_factory):
    cid, hero, key = await _table(client, test_session_factory, hero_hp=30)
    as_user(PLAYER_ID)
    r = await client.patch(f"/characters/{hero}/hp", json={"op": "damage", "value": 30, "raw_value": 60, "damage_type": "fire",
                                                         "damage_modifier": "half", "options": [key]})
    assert r.status_code == 200 and r.json()["current_hit_points"] == 1
    descriptions = [e.description for e in await _lines(test_session_factory, hero)]
    assert any("→ 30 (resistenza)" in d and "-29 HP (30 → 1)" in d for d in descriptions), descriptions


async def test_held_at_one_the_response_says_how_many_hit_points_were_lost(client, test_session_factory):
    cid, hero, key = await _table(client, test_session_factory, hero_hp=44)
    r = await _hit(client, hero, PLAYER_ID, 50, [key])
    assert r.json()["option_result"]["hp_lost"] == 43


async def test_the_auras_alone_do_not_load_the_allies_abilities(client, test_session_factory):
    from sqlalchemy import inspect
    from api.services.session_allies import _party
    cid, hero, key = await _table(client, test_session_factory)
    async with test_session_factory() as s:
        char = await s.get(Character, hero)
        (warlock,) = await _party(s, char)
        assert "abilities" in inspect(warlock).unloaded
    async with test_session_factory() as s:
        char = await s.get(Character, hero)
        (warlock,) = await _party(s, char, donors=True)
        assert "abilities" not in inspect(warlock).unloaded

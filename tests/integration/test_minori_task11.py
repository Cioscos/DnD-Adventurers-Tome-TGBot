"""Task 11 dei minori rinviati: punti 52, 81, 92, 101."""
from __future__ import annotations

from sqlalchemy import event, select

from core.db.models import Character, SessionParticipant, SessionRole
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session


class _Queries:
    """Conta le istruzioni SQL (letture e scritture) eseguite sul database."""

    def __init__(self, factory):
        self.engine = factory.kw["bind"].sync_engine
        self.n = 0

    def _on(self, conn, cursor, statement, *a):
        if statement.lstrip().split(None, 1)[0].upper() not in {"BEGIN", "COMMIT", "ROLLBACK", "PRAGMA"}:
            self.n += 1

    def __enter__(self):
        event.listen(self.engine, "before_cursor_execute", self._on)
        return self

    def __exit__(self, *exc):
        event.remove(self.engine, "before_cursor_execute", self._on)


async def _five_at_the_table(factory) -> int:
    _, hero = await seed_session(factory)
    async with factory() as s:
        sess_id = (await s.execute(select(SessionParticipant.session_id))).scalars().first()
        for i in range(3):
            c = Character(user_id=9100 + i, name=f"Eroe{i}", hit_points=40, current_hit_points=40)
            s.add(c)
            await s.flush()
            s.add(SessionParticipant(session_id=sess_id, user_id=9100 + i, character_id=c.id, role=SessionRole.PLAYER,
                                     display_name=f"Eroe{i}", joined_at="2026-06-09T10:00:00"))
        await s.commit()
    return hero


async def test_minori_92_the_turn_start_loads_only_the_spell_auras_of_the_allies(client, test_session_factory):
    hero = await _five_at_the_table(test_session_factory)
    as_user(PLAYER_ID)
    await client.post(f"/characters/{hero}/turn/new")  # scalda
    with _Queries(test_session_factory) as q:
        r = await client.post(f"/characters/{hero}/turn/new")
    assert r.status_code == 200
    assert q.n <= LIMIT_92


LIMIT_92 = 7  # prima della correzione 19


async def test_minori_52_a_damage_with_options_at_a_table_of_five(client, test_session_factory):
    from tests.integration.rules.test_2024_warlock_gift_ally import _hit, _table
    _, hero, key = await _table(client, test_session_factory)
    for _ in range(3):
        await _second_hero_n(test_session_factory)
    with _Queries(test_session_factory) as q:
        r = await _hit(client, hero, PLAYER_ID, 10, [key])
    assert r.status_code == 200, r.text
    assert q.n <= LIMIT_52


async def _second_hero_n(factory) -> None:
    async with factory() as s:
        sess_id = (await s.execute(select(SessionParticipant.session_id))).scalars().first()
        n = len((await s.execute(select(Character))).scalars().all())
        c = Character(user_id=9300 + n, name=f"Altro{n}", hit_points=40, current_hit_points=40)
        s.add(c)
        await s.flush()
        s.add(SessionParticipant(session_id=sess_id, user_id=9300 + n, character_id=c.id, role=SessionRole.PLAYER,
                                 display_name=f"Altro{n}", joined_at="2026-06-09T10:00:00"))
        await s.commit()


LIMIT_52 = 40  # SELECT+scritture; prima della correzione le sole SELECT erano 116


async def test_minori_81_death_ward_spend_and_refund_have_no_query_in_between(client, test_session_factory, monkeypatch):
    """Una query fra la spesa del gettone e il rimborso farebbe un flush a metà: il rimborso non rimetterebbe l'orologio del lanciatore."""
    import api.routers.hp as hp
    import core.rules.roll_options as ro
    from tests.integration.rules.test_spell_effects_hp import DEATH_WARD, _cast, _hit, _hp, _table
    hero, caster, spell = await _table(client, test_session_factory, "Death Ward", "death-ward", 4)
    await _hp(client, caster, 30, 30)
    await _cast(client, caster, spell, [hero], level=4)
    as_user(PLAYER_ID)
    marks: dict[str, int] = {}
    with _Queries(test_session_factory) as q:
        real_spend, real_refund = ro._spend_state_token, hp.refund_spent

        def spend(*a, **kw):
            marks["spend"] = q.n
            return real_spend(*a, **kw)

        def refund(*a, **kw):
            marks["refund"] = q.n
            return real_refund(*a, **kw)

        monkeypatch.setattr(ro, "_spend_state_token", spend)
        monkeypatch.setattr(hp, "refund_spent", refund)
        assert await _hit(client, hero, 50, "slashing", options=[DEATH_WARD]) == 50
    assert marks.keys() == {"spend", "refund"}
    assert marks["spend"] == marks["refund"]

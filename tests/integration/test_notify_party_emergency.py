"""Notifiche 🩸/💀 ai compagni della sessione attiva quando un PG cade.

Hook in hp.py: PATCH /hp (caduta a 0, morte istantanea, 3° fallimento da
danno a 0) e death saves. Destinatari = GM + altri giocatori; la pref
`party_emergency` è del destinatario (sul suo PG).
"""
from __future__ import annotations

from core.db.models import (
    AbilityScore, Character, GameSession, SessionParticipant,
    SessionRole, SessionStatus,
)
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, NOW, as_user
from tests.integration._telegram_stub import install_fake_telegram

BUDDY_ID = 9999


async def _seed(test_session_factory, *, buddy_prefs: dict | None = None,
                in_session: bool = True) -> int:
    """Sessione attiva: GM + vittima (PLAYER_ID) + compagno (BUDDY_ID).

    Ritorna l'id del PG vittima (10/10 PF).
    """
    async with test_session_factory() as s:
        victim = Character(user_id=PLAYER_ID, name="Eroe",
                           hit_points=10, current_hit_points=10)
        buddy = Character(user_id=BUDDY_ID, name="Compagno",
                          settings={"notifications": buddy_prefs} if buddy_prefs else None)
        s.add_all([victim, buddy])
        await s.flush()
        s.add(AbilityScore(character_id=victim.id, name="constitution", value=10))
        if in_session:
            sess = GameSession(code="EMG123", gm_user_id=GM_ID,
                               status=SessionStatus.ACTIVE,
                               created_at=NOW, last_activity_at=NOW)
            s.add(sess)
            await s.flush()
            s.add_all([
                SessionParticipant(session_id=sess.id, user_id=GM_ID,
                                   role=SessionRole.GAME_MASTER, joined_at=NOW),
                SessionParticipant(session_id=sess.id, user_id=PLAYER_ID,
                                   role=SessionRole.PLAYER,
                                   character_id=victim.id, joined_at=NOW),
                SessionParticipant(session_id=sess.id, user_id=BUDDY_ID,
                                   role=SessionRole.PLAYER,
                                   character_id=buddy.id, joined_at=NOW),
            ])
        await s.commit()
        return victim.id


def _texts_by_chat(captured: list[dict]) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    for c in captured:
        out.setdefault(c["json"]["chat_id"], []).append(c["json"]["text"])
    return out


async def test_drop_to_zero_notifies_gm_and_buddy(client, test_session_factory, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    cid = await _seed(test_session_factory)
    as_user(PLAYER_ID)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10})
    assert r.status_code == 200, r.text
    by_chat = _texts_by_chat(captured)
    assert any("a terra" in t for t in by_chat.get(GM_ID, []))
    assert any("a terra" in t for t in by_chat.get(BUDDY_ID, []))
    assert PLAYER_ID not in by_chat  # la vittima non si auto-notifica


async def test_massive_damage_death_text(client, test_session_factory, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    cid = await _seed(test_session_factory)
    as_user(PLAYER_ID)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 99})
    assert r.status_code == 200, r.text
    assert any("morto" in t for t in _texts_by_chat(captured).get(GM_ID, []))


async def test_buddy_opt_out_silences_only_buddy(client, test_session_factory, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    cid = await _seed(test_session_factory, buddy_prefs={"party_emergency": False})
    as_user(PLAYER_ID)
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10})
    by_chat = _texts_by_chat(captured)
    assert GM_ID in by_chat
    assert BUDDY_ID not in by_chat


async def test_no_active_session_no_messages(client, test_session_factory, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    cid = await _seed(test_session_factory, in_session=False)
    as_user(PLAYER_ID)
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10})
    assert captured == []


async def test_damage_at_zero_without_death_is_silent(client, test_session_factory, monkeypatch):
    """Fallimento aggiunto (non 3°) a 0 PF: niente nuovo avviso."""
    captured = install_fake_telegram(monkeypatch)
    cid = await _seed(test_session_factory)
    as_user(PLAYER_ID)
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10})
    n_after_drop = len(captured)
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 1})
    assert len(captured) == n_after_drop

"""Unit tests for api/services/telegram_notify.py (no network, no DB)."""
from __future__ import annotations

import api.services.telegram_notify as tn
from core.db.models import Character


class _FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code
        self.text = "stub"

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300


def _install_fake_client(monkeypatch, *, status_code=200, raise_exc=False) -> list[dict]:
    captured: list[dict] = []

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            if raise_exc:
                raise RuntimeError("boom")
            captured.append({"url": url, "json": json})
            return _FakeResponse(status_code)

    monkeypatch.setattr(tn, "_BOT_TOKEN", "fake-token")
    monkeypatch.setattr(tn.httpx, "AsyncClient", _FakeClient)
    return captured


def test_miniapp_url_joins_hash_route(monkeypatch):
    monkeypatch.setattr(tn, "_MINIAPP_BASE_URL", "https://example.test/app/")
    assert tn.miniapp_url("/char/5/xp") == "https://example.test/app/#/char/5/xp"


def test_notifications_enabled_defaults_true():
    char = Character(user_id=1, name="X")  # settings None
    assert tn.notifications_enabled(char, "level_up") is True
    assert tn.notifications_enabled(None, "level_up") is True  # GM senza PG


def test_notifications_enabled_respects_opt_out():
    char = Character(user_id=1, name="X",
                     settings={"notifications": {"level_up": False}})
    assert tn.notifications_enabled(char, "level_up") is False
    assert tn.notifications_enabled(char, "encounter") is True


async def test_send_builds_payload_with_web_app_button(monkeypatch):
    captured = _install_fake_client(monkeypatch)
    ok = await tn.send_telegram_message(
        42, "ciao", button=("Apri", "https://example.test/app/#/char/1/xp"))
    assert ok is True
    assert captured[0]["json"] == {
        "chat_id": 42,
        "text": "ciao",
        "reply_markup": {"inline_keyboard": [[
            {"text": "Apri", "web_app": {"url": "https://example.test/app/#/char/1/xp"}}
        ]]},
    }
    assert "fake-token/sendMessage" in captured[0]["url"]


async def test_send_without_button_and_with_parse_mode(monkeypatch):
    captured = _install_fake_client(monkeypatch)
    ok = await tn.send_telegram_message(42, "*x*", parse_mode="Markdown")
    assert ok is True
    assert captured[0]["json"] == {"chat_id": 42, "text": "*x*", "parse_mode": "Markdown"}


async def test_send_returns_false_on_http_error(monkeypatch):
    _install_fake_client(monkeypatch, status_code=500)
    assert await tn.send_telegram_message(42, "x") is False


async def test_send_swallows_exceptions(monkeypatch):
    _install_fake_client(monkeypatch, raise_exc=True)
    assert await tn.send_telegram_message(42, "x") is False


async def test_send_returns_false_without_token(monkeypatch):
    monkeypatch.setattr(tn, "_BOT_TOKEN", "")
    assert await tn.send_telegram_message(42, "x") is False

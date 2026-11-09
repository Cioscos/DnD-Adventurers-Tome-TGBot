"""I test non devono mai parlare con Telegram, nemmeno con un BOT_TOKEN vero in `.env` (CLAUDE.md)."""
from __future__ import annotations

import socket

import httpx
import pytest

from api.services import telegram_notify


@pytest.fixture
def lookups(monkeypatch):
    """Registra ogni risoluzione DNS (e la fa fallire): è il primo passo di qualunque richiesta vera."""
    seen: list[str] = []

    def fake(host, *args, **kwargs):
        seen.append(str(host))
        raise OSError("rete chiusa nel test")

    monkeypatch.setattr(socket, "getaddrinfo", fake)
    return seen


async def test_send_telegram_message_makes_no_network_request(monkeypatch, lookups):
    monkeypatch.setattr(telegram_notify, "_BOT_TOKEN", "token-finto-del-test")
    assert await telegram_notify.send_telegram_message(1234, "ciao") is False
    assert [h for h in lookups if "telegram" in h] == []


async def test_any_request_to_telegram_is_refused_at_the_transport(lookups):
    with pytest.raises(httpx.ConnectError):
        async with httpx.AsyncClient() as client:
            await client.post("https://api.telegram.org/botfinto/getMe")
    with pytest.raises(httpx.ConnectError):
        httpx.get("https://api.telegram.org/botfinto/getMe")
    assert [h for h in lookups if "telegram" in h] == []

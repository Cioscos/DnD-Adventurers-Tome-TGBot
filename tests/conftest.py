"""Fixture valide per tutta la suite."""
from __future__ import annotations

import httpx
import pytest

_TELEGRAM_HOST = "api.telegram.org"


def _refuse_telegram(request: httpx.Request) -> None:
    if request.url.host == _TELEGRAM_HOST:
        raise httpx.ConnectError("i test non parlano con Telegram", request=request)


@pytest.fixture(autouse=True)
def _never_reach_telegram(monkeypatch):
    """CLAUDE.md: le API locali e i test non scrivono mai agli utenti, ma `BOT_TOKEN` arriva da `.env`.

    Si chiude il livello più basso, i transport di httpx, per ogni punto che usa il token (`telegram_notify`, `maps`,
    `bot/`). Un test che mocka già l'invio (client o funzione sostituiti) continua a funzionare: non arriva al transport.
    I client dei test (`ASGITransport`, `MockTransport`) non passano da qui."""
    real_async = httpx.AsyncHTTPTransport.handle_async_request
    real_sync = httpx.HTTPTransport.handle_request

    async def guarded_async(self, request):
        _refuse_telegram(request)
        return await real_async(self, request)

    def guarded_sync(self, request):
        _refuse_telegram(request)
        return real_sync(self, request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", guarded_async)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", guarded_sync)

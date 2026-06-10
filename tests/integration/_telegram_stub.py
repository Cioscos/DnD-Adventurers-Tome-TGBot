"""Fake transport for api.services.telegram_notify (not collected by pytest).

Sostituisce gli stub locali dei singoli moduli di test: ora tutto l'invio
Telegram passa dal servizio, quindi si patcha SOLO lì.
"""
from __future__ import annotations

import api.services.telegram_notify as tn


class FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code
        self.text = "stub"

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300


def install_fake_telegram(monkeypatch, *, status_code: int = 200) -> list[dict]:
    """No HTTP reale: cattura i payload sendMessage come {'url':…, 'json':…}."""
    captured: list[dict] = []

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            captured.append({"url": url, "json": json})
            return FakeResponse(status_code)

    monkeypatch.setattr(tn, "_BOT_TOKEN", "fake-token")
    monkeypatch.setattr(tn.httpx, "AsyncClient", _FakeClient)
    return captured


def clear_bot_token(monkeypatch) -> None:
    monkeypatch.setattr(tn, "_BOT_TOKEN", "")

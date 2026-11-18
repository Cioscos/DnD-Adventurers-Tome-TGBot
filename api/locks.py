"""Una richiesta che scrive alla volta per personaggio (o per serata, nelle rotte ``/sessions/{session_id}/...``: scambi, deposito, incontri): un doppio tocco rilegge ciò che la prima ha già scritto, così lo stesso
uso o lo stesso dado non vale per due tiri. Gli invii a Telegram delle richieste che scrivono partono staccati (telegram_notify.send_detached),
così il lock non aspetta la rete. shortcut: un solo processo API, con più worker serve un lock nel DB."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncGenerator

from fastapi import Request

_READ_ONLY_POSTS = ("/dice/post-to-chat", "/export/send")  # leggono soltanto e aspettano Telegram per darne l'esito
_LOCKS: defaultdict[tuple[int, str], asyncio.Lock] = defaultdict(asyncio.Lock)  # (event loop, "char:<id>" | "session:<id>")


async def character_write_lock(request: Request) -> AsyncGenerator[None, None]:
    """Dipendenza globale: tiene il lock fino alla fine della richiesta, commit della sessione compreso (si chiude per ultima)."""
    key = lock_key(request.url.path, request.path_params)
    if request.method in ("GET", "HEAD", "OPTIONS") or key is None or request.url.path.endswith(_READ_ONLY_POSTS):
        yield
        return
    async with _LOCKS[id(asyncio.get_running_loop()), key]:
        yield


def lock_key(path: str, params: dict) -> str | None:
    """Chiave del lock, solo per id numerici: un id qualsiasi nel percorso non deve far crescere ``_LOCKS``.

    shortcut: una scrittura di serata e una sulla scheda dello stesso personaggio usano lock diversi e possono ancora
    incrociarsi; da rivedere se compaiono doppioni fra uno scambio e una modifica dell'inventario."""
    char_id, session_id = str(params.get("char_id", "")), str(params.get("session_id", ""))
    if char_id.isdigit():
        return f"char:{char_id}"
    if session_id.isdigit() and path.startswith("/sessions/"):
        return f"session:{session_id}"
    return None

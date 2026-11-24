"""Una richiesta che scrive alla volta per personaggio (o per serata, nelle rotte ``/sessions/{session_id}/...``: scambi, deposito, incontri): un doppio tocco rilegge ciò che la prima ha già scritto, così lo stesso
uso o lo stesso dado non vale per due tiri. Gli invii a Telegram delle richieste che scrivono partono staccati (telegram_notify.send_detached),
così il lock non aspetta la rete. shortcut: un solo processo API, con più worker serve un lock nel DB."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncGenerator, Iterable
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import Depends, Request

from api.auth import get_current_user

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


async def user_write_lock(user_id: int = Depends(get_current_user)) -> AsyncGenerator[None, None]:
    """Come ``character_write_lock`` ma per utente, per le rotte senza ``char_id`` (apri serata, entra, iscriviti): la
    richiesta gemella di un doppio tocco aspetta il commit della prima e riceve il 409 previsto, non un doppione."""
    async with _LOCKS[id(asyncio.get_running_loop()), f"user:{user_id}"]:
        yield


@asynccontextmanager
async def character_locks(char_ids: Iterable[int]) -> AsyncGenerator[None, None]:
    """I lock di più personaggi, per chi ne cambia le schede da una rotta senza ``char_id``. Da prendere prima di ogni scrittura
    sul database e in ordine di id: chi tiene un lock di personaggio aspetta il database, mai il contrario."""
    async with AsyncExitStack() as stack:
        for char_id in sorted(set(char_ids)):
            await stack.enter_async_context(_LOCKS[id(asyncio.get_running_loop()), f"char:{char_id}"])
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

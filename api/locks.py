"""Una richiesta che scrive alla volta per personaggio: un doppio tocco rilegge ciò che la prima ha già scritto, così lo stesso
uso o lo stesso dado non vale per due tiri. shortcut: un solo processo API, con più worker serve un lock nel DB."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncGenerator

from fastapi import Request

_LOCKS: defaultdict[tuple[int, str], asyncio.Lock] = defaultdict(asyncio.Lock)  # (event loop, personaggio)


async def character_write_lock(request: Request) -> AsyncGenerator[None, None]:
    """Dipendenza globale: tiene il lock fino alla fine della richiesta, commit della sessione compreso (si chiude per ultima)."""
    char_id = request.path_params.get("char_id")
    if request.method in ("GET", "HEAD", "OPTIONS") or char_id is None:
        yield
        return
    async with _LOCKS[id(asyncio.get_running_loop()), str(char_id)]:
        yield

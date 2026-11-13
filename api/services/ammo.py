"""Recupero delle munizioni spese: metà, per difetto (stessa regola 2014 e 2024)."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from api.services.history import add_history
from core.db.models import Character, Item


def recover_ammo(session: AsyncSession, char: Character, item: Item) -> int:
    """Rimette sulla pila metà delle munizioni spese e azzera il contatore; ritorna i pezzi recuperati."""
    n = (item.ammo_spent or 0) // 2
    item.quantity += n
    item.ammo_spent = 0
    if n:
        add_history(session, char.id, "item_used", f"Munizioni recuperate: {n} {item.name}")
    return n

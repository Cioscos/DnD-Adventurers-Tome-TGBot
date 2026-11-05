"""Preservare Vita (Chierico 2014, Dominio della Vita): 5 × livello PF distribuiti fra le creature scelte (R42).

Tutto passa da una sola richiesta: il server convalida ogni destinatario e ogni importo prima di toccare qualcosa, poi
spende azione e uso e cura. Chi riceve è chi usa il privilegio o un partecipante della stessa serata attiva; si scrive solo
un aumento dei PF, con lo storico sulla scheda del ricevente."""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.services.effects import apply_heal
from api.services.rules_turn import refuse_if_incapacitated, spend
from api.services.session_allies import seated_allies
from core.db.models import Character
from core.rules.catalog import active_features
from core.rules.modifiers import effective_hp_max

FEATURE = "cleric.preserve_life"
POOL = "cleric.channel_divinity"


def _refuse(code: int, name: str) -> HTTPException:
    return HTTPException(code, detail={"code": name})


@dataclass
class Healed:
    character_id: int
    name: str
    healed: int
    current_hit_points: int


def pool_for(level: int) -> int:
    return 5 * level


def half_cap(char: Character) -> int:
    """PF che si possono ancora restituire: fino alla metà dei PF massimi, mai oltre."""
    return max(0, effective_hp_max(char) // 2 - char.current_hit_points)


async def _load(session: AsyncSession, char_id: int) -> Character:
    row = await session.execute(select(Character).options(
        selectinload(Character.classes), selectinload(Character.ability_scores), selectinload(Character.spells),
        selectinload(Character.spell_slots), selectinload(Character.items), selectinload(Character.abilities),
    ).where(Character.id == char_id))
    return row.scalar_one()


async def preserve_life(session: AsyncSession, char: Character, allocations: list[tuple[int, int]],
                        confirm_living: bool) -> tuple[int, list[Healed]]:
    """Distribuisce la riserva. Restituisce (riserva, curati). Ogni rifiuto avviene prima di modificare qualcosa."""
    found = next(((spec, row) for spec, row in active_features(char) if spec.key == FEATURE), None)
    if found is None:
        raise _refuse(status.HTTP_404_NOT_FOUND, "feature_not_usable")
    pool = pool_for(found[1].level)
    if not confirm_living:  # non su costrutti né non morti: lo dichiara il giocatore
        raise _refuse(status.HTTP_422_UNPROCESSABLE_ENTITY, "confirm_required")
    ids = [cid for cid, _ in allocations]
    if not allocations or len(set(ids)) != len(ids) or any(type(a) is not int or a < 1 for _, a in allocations):
        raise _refuse(status.HTTP_422_UNPROCESSABLE_ENTITY, "bad_allocation")
    if sum(a for _, a in allocations) > pool:
        raise _refuse(status.HTTP_422_UNPROCESSABLE_ENTITY, "over_pool")
    refuse_if_incapacitated(char)

    allowed = {a.id: a for a in await seated_allies(session, char)}
    receivers: dict[int, Character] = {}
    for cid, amount in allocations:
        if cid == char.id:
            target = char
        elif cid in allowed:
            target = await _load(session, cid)
        else:  # non partecipante, o serata chiusa: non è un bersaglio
            raise _refuse(status.HTTP_403_FORBIDDEN, "invalid_target")
        if target.is_dead:
            raise _refuse(status.HTTP_409_CONFLICT, "target_dead")
        if amount > half_cap(target):
            raise _refuse(status.HTTP_422_UNPROCESSABLE_ENTITY, "over_half")
        receivers[cid] = target

    row = next((a for a in char.abilities if a.feature_key == POOL), None)
    if row is None or (row.max_uses is not None and (row.uses or 0) < 1):
        raise _refuse(status.HTTP_409_CONFLICT, "no_uses")
    spend(char, "action")  # 409 turn_slot_used: ancora nulla di scritto
    if row.max_uses is not None:
        row.uses = (row.uses or 0) - 1

    done: list[Healed] = []
    for cid, amount in allocations:
        target = receivers[cid]
        result = await apply_heal(session, target, amount)
        done.append(Healed(cid, target.name, result["healed"], target.current_hit_points))
    return pool, done

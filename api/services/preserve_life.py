"""Preservare Vita (Chierico 2014, Dominio della Vita): 5 × livello PF distribuiti fra le creature scelte (R42).

Tutto passa da una sola richiesta: il server convalida ogni destinatario e ogni importo prima di toccare qualcosa, poi
spende azione e uso e cura. Chi riceve è chi usa il privilegio o un partecipante della stessa serata attiva; si scrive solo
un aumento dei PF, con lo storico sulla scheda del ricevente."""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.services.effects import apply_heal
from api.services.rules_turn import refuse_if_incapacitated, spend
from api.services.session_allies import seated_allies
from core.db.models import Ability, Character
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


def pool_for(level: int) -> int:
    return 5 * level


def half_cap(char: Character) -> int:
    """PF che si possono ancora restituire: fino alla metà dei PF massimi, mai oltre."""
    return max(0, effective_hp_max(char) // 2 - char.current_hit_points)


async def _load(session: AsyncSession, char_id: int) -> Character:
    row = await session.execute(select(Character).options(
        selectinload(Character.classes), selectinload(Character.ability_scores), selectinload(Character.spells),
        selectinload(Character.spell_slots), selectinload(Character.items), selectinload(Character.abilities),
    ).where(Character.id == char_id).execution_options(populate_existing=True))
    return row.scalar_one()


@dataclass
class Target:
    id: int
    name: str
    cap: int
    self: bool


@dataclass
class Info:
    pool: int
    uses_left: int | None
    targets: list[Target]


def _usable(char: Character):
    found = next(((spec, row) for spec, row in active_features(char) if spec.key == FEATURE), None)
    if found is None:
        raise _refuse(status.HTTP_404_NOT_FOUND, "feature_not_usable")
    return found


def _pool_row(char: Character):
    return next((a for a in char.abilities if a.feature_key == POOL), None)


async def info(session: AsyncSession, char: Character) -> Info:
    """Chi si può curare e fino a quanto, calcolato dal server. Del tetto si dà il minimo: mai oltre la riserva, e nulla
    a chi non può usare il privilegio ora, così il pannello non lascia leggere i PF degli altri giocatori."""
    pool = pool_for(_usable(char)[1].level)
    row = _pool_row(char)
    if row is None or (row.max_uses is not None and (row.uses or 0) < 1):
        raise _refuse(status.HTTP_409_CONFLICT, "no_uses")
    people = [char, *[await _load(session, a.id) for a in await seated_allies(session, char)]]
    return Info(pool, row.uses, [Target(p.id, p.name, min(half_cap(p), pool), p.id == char.id) for p in people if not p.is_dead])


async def preserve_life(session: AsyncSession, char: Character, allocations: list[tuple[int, int]],
                        confirm_living: bool) -> tuple[int, list[Healed]]:
    """Distribuisce la riserva. Restituisce (riserva, curati). Ogni rifiuto annulla tutto: la riserva si spende con un
    UPDATE condizionato, che prende la scrittura prima di rileggere i PF dei riceventi, così due richieste insieme o due
    chierici sullo stesso ricevente non superano né la riserva né la metà dei PF."""
    pool = pool_for(_usable(char)[1].level)
    if not confirm_living:  # non su costrutti né non morti: lo dichiara il giocatore
        raise _refuse(status.HTTP_422_UNPROCESSABLE_ENTITY, "confirm_required")
    ids = [cid for cid, _ in allocations]
    if not allocations or len(set(ids)) != len(ids) or any(type(a) is not int or a < 1 for _, a in allocations):
        raise _refuse(status.HTTP_422_UNPROCESSABLE_ENTITY, "bad_allocation")
    if sum(a for _, a in allocations) > pool:
        raise _refuse(status.HTTP_422_UNPROCESSABLE_ENTITY, "over_pool")
    refuse_if_incapacitated(char)
    row = _pool_row(char)
    if row is None:
        raise _refuse(status.HTTP_409_CONFLICT, "no_uses")

    allowed = {a.id for a in await seated_allies(session, char)}
    for cid in ids:
        if cid != char.id and cid not in allowed:  # non partecipante, o serata chiusa: non è un bersaglio
            raise _refuse(status.HTTP_403_FORBIDDEN, "invalid_target")

    # Primo atto di scrittura: da qui nessun'altra richiesta modifica uso o PF finché non si chiude questa.
    if row.max_uses is None:
        spent = await session.execute(update(Ability).where(Ability.id == row.id).values(uses=Ability.uses))
    else:
        spent = await session.execute(
            update(Ability).where(Ability.id == row.id, Ability.uses >= 1).values(uses=Ability.uses - 1))
    if spent.rowcount != 1:
        raise _refuse(status.HTTP_409_CONFLICT, "no_uses")
    char = await _load(session, char.id)  # riletta dopo il blocco: turno, PF e usi sono quelli veri
    receivers: dict[int, Character] = {char.id: char}
    for cid, amount in allocations:
        target = receivers.get(cid) or await _load(session, cid)
        if target.is_dead:
            raise _refuse(status.HTTP_409_CONFLICT, "target_dead")
        if amount > half_cap(target):
            raise _refuse(status.HTTP_422_UNPROCESSABLE_ENTITY, "over_half")
        receivers[cid] = target
    spend(char, "action")  # 409 turn_slot_used: la risposta annulla anche la spesa dell'uso

    done: list[Healed] = []
    for cid, amount in allocations:
        target = receivers[cid]
        result = await apply_heal(session, target, amount)
        done.append(Healed(cid, target.name, result["healed"]))
    return pool, done

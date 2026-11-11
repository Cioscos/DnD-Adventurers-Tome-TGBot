"""Reazioni degli alleati a un danno: Intercettazione (guerriero 2024) e Parole Taglienti (Sapienza). Il ricevente apre una
richiesta, i donatori presenti rispondono con il loro lock, la richiesta si chiude con tutte le risposte, a mano o dopo 30 s."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.history import add_history
from api.services.rules_states import use_feature
from api.services.rules_turn import get_turn, refuse_if_incapacitated, release
from api.services.session_allies import load_receiver, seated_allies
from core.db.models import Ability, AllyReactionRequest as Req, Character, GameSession, SessionParticipant, SessionStatus
from core.rules.catalog import active_features
from core.rules.edition import character_edition
from core.rules.modifiers import is_incapacitated
from core.rules.types import RuleContext
from core.rules.uses import pool_key

INTERCEPTION = "fighter.style_interception"
CUTTING_WORDS = "bard.cutting_words"
logger = logging.getLogger(__name__)
REACTIONS = (INTERCEPTION, CUTTING_WORDS)
LABELS = {INTERCEPTION: "Intercettazione", CUTTING_WORDS: "Parole Taglienti"}
OPEN_SECONDS = 30  # dopo, la richiesta si chiude da sola
UNUSED_SECONDS = 120  # chiusa e mai usata da così: le reazioni dei donatori tornano
KEEP_DAYS = 1  # poi la riga (già usata o rimborsata) si cancella
PRESENCE_SECONDS = 15  # un donatore è «presente» se ha letto i suoi popup da meno di così

# shortcut: presenza in memoria, un solo processo uvicorn; passare a una colonna se si scala a più worker
_SEEN: dict[int, datetime] = {}
SWEEP_SECONDS = 30  # la pulizia globale dal poll dei donatori non parte più spesso di così
# shortcut: ultimo giro in memoria, per processo; con più worker ognuno ne fa uno ogni 30 s (innocuo, le scritture sono condizionate)
_LAST_SWEEP: datetime | None = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def mark_seen(char_id: int) -> None:
    _SEEN[char_id] = utc_now()


def sweep_due() -> bool:
    """Vero al massimo una volta ogni ``SWEEP_SECONDS``: la scadenza delle richieste non gira a ogni poll di ogni donatore."""
    global _LAST_SWEEP
    now = utc_now()
    if _LAST_SWEEP is not None and now - _LAST_SWEEP < timedelta(seconds=SWEEP_SECONDS):
        return False
    _LAST_SWEEP = now
    return True


def is_present(char_id: int) -> bool:
    seen = _SEEN.get(char_id)
    return seen is not None and utc_now() - seen <= timedelta(seconds=PRESENCE_SECONDS)


def _err(code: str, http: int = status.HTTP_409_CONFLICT) -> HTTPException:
    return HTTPException(http, detail={"code": code})


def _found(char, key: str):
    return next(((s, r) for s, r in active_features(char) if s.key == key and s.on_use), None)


def _pool(char, on_use):
    """La riga degli usi che il privilegio spende (Ispirazione Bardica per Parole Taglienti), se spende quelli di un altro."""
    if not on_use.spends:
        return None
    key = pool_key(char, on_use.spends)
    return next((a for a in char.abilities if a.feature_key == key), None)


def _can_react(char, key: str) -> bool:
    """Come i controlli di ``use_feature`` che non costano niente: reazione libera, privilegio disponibile, usi sufficienti."""
    found = _found(char, key)
    if found is None or char.is_dead or is_incapacitated(char) or get_turn(char)["reaction_used"]:
        return False
    spec, row = found
    on_use = spec.on_use
    if on_use.available and not on_use.available(RuleContext(char=char, edition=character_edition(char), class_row=row, class_level=row.level)):
        return False
    if on_use.spends:
        pool = _pool(char, on_use)
        return pool is not None and (pool.max_uses is None or (pool.uses or 0) >= on_use.cost)
    return True


async def eligible_reactions(session: AsyncSession, receiver: Character) -> list[tuple[Character, str]]:
    """(donatore, chiave) di chi, seduto alla serata del ricevente e diverso da lui, può reagire ora. Non scrive niente."""
    out: list[tuple[Character, str]] = []
    for ally in await seated_allies(session, receiver):
        donor = await load_receiver(session, ally.id)
        out += [(donor, key) for key in REACTIONS if _can_react(donor, key)]
    return out


async def _fresh(session: AsyncSession, request_id: int) -> Req | None:
    return (await session.execute(select(Req).where(Req.id == request_id).execution_options(populate_existing=True))).scalar_one_or_none()


async def open_request(session: AsyncSession, receiver: Character, damage: int, damage_type: str | None) -> Req | None:
    """Apre la richiesta ai donatori idonei e presenti; ``None`` se non ce ne sono (o fuori serata): il danno prosegue come oggi."""
    if damage <= 0:
        return None
    session_id = (await session.execute(
        select(SessionParticipant.session_id).join(GameSession, GameSession.id == SessionParticipant.session_id)
        .where(SessionParticipant.character_id == receiver.id, GameSession.status == SessionStatus.ACTIVE)
        .order_by(SessionParticipant.session_id.desc()).limit(1))).scalar_one_or_none()
    if session_id is None:
        return None
    donors = [(d, k) for d, k in await eligible_reactions(session, receiver) if is_present(d.id)]
    if not donors:
        return None
    req = Req(session_id=session_id, receiver_id=receiver.id, damage=damage, damage_type=damage_type, created_at=utc_now(), rev=0,
              answers=[{"donor_id": d.id, "feature_key": k, "status": "waiting", "reduction": None, "rolls": [], "spent": None}
                       for d, k in donors])
    session.add(req)
    await session.flush()
    return req


def total_reduction(req: Req) -> int:
    return sum(a.get("reduction") or 0 for a in req.answers if a["status"] == "used")


async def _close(session: AsyncSession, request_id: int, at: datetime) -> None:
    await session.execute(update(Req).where(Req.id == request_id, Req.closed_at.is_(None)).values(closed_at=at)
                          .execution_options(synchronize_session=False))


async def close_if_due(session: AsyncSession, req: Req) -> None:
    """Chiude la richiesta se tutti hanno risposto o sono passati 30 s (allora ``closed_at`` è la scadenza, non l'istante della lettura)."""
    req = await _fresh(session, req.id)
    if req is None or req.closed_at is not None:
        return
    deadline = req.created_at + timedelta(seconds=OPEN_SECONDS)
    if utc_now() >= deadline:
        await _close(session, req.id, deadline)
    elif not any(a["status"] == "waiting" for a in req.answers):
        await _close(session, req.id, utc_now())


async def close_now(session: AsyncSession, req: Req) -> None:
    """«Applica senza aspettare»: chiude, una volta sola (le risposte arrivate dopo sono rifiutate)."""
    await _close(session, req.id, utc_now())


async def _record(session: AsyncSession, request_id: int, donor_id: int, entry: dict) -> bool:
    """Scrive la risposta del donatore con un UPDATE condizionato (richiesta aperta e ``rev`` letta): due risposte insieme non si
    perdono, si riprova sulla riga riletta. ``False`` se la richiesta è chiusa o il donatore non ha più nulla da dire."""
    for _ in range(10):
        row = (await session.execute(select(Req.answers, Req.rev, Req.closed_at).where(Req.id == request_id))).one()
        if row.closed_at is not None:
            return False
        new, hit = [], False
        for a in row.answers:
            if a["donor_id"] == donor_id and a["status"] == "waiting":
                new.append({**a, "status": "declined"} if hit else entry)  # una risposta per donatore: l'altra reazione decade
                hit = True
            else:
                new.append(a)
        if not hit:
            return False
        done = await session.execute(update(Req).where(Req.id == request_id, Req.rev == row.rev, Req.closed_at.is_(None))
                                     .values(answers=new, rev=row.rev + 1).execution_options(synchronize_session=False))
        if done.rowcount == 1:
            return True
    raise _err("request_busy")


async def answer(session: AsyncSession, donor: Character, request_id: int, use: bool) -> dict:
    """La risposta del donatore. «Usa» spende reazione e usi con ``use_feature`` (tutto o niente) e registra la riduzione; se la
    richiesta si è chiusa nel frattempo non resta speso nulla (409 ``request_closed``)."""
    donor_id = donor.id
    req = await _fresh(session, request_id)
    if req is None or not any(a["donor_id"] == donor_id for a in req.answers):
        raise _err("request_not_found", status.HTTP_404_NOT_FOUND)
    await close_if_due(session, req)
    req = await _fresh(session, request_id)
    if req.closed_at is not None:
        raise _err("request_closed")
    mine = next((a for a in req.answers if a["donor_id"] == donor_id and a["status"] == "waiting"), None)
    if mine is None:
        raise _err("already_answered")
    if (await session.get(GameSession, req.session_id)).status != SessionStatus.ACTIVE:  # serata chiusa nei 30 s
        raise _err("request_closed")
    key = mine["feature_key"]
    receiver_name = (await session.get(Character, req.receiver_id)).name
    entry = {**mine, "status": "declined"}
    result = {"reduction": 0, "rolls": []}
    if use:
        found = _found(donor, key)
        pool = _pool(donor, found[0].on_use) if found else None
        pool_id, cost = (pool.id, found[0].on_use.cost) if pool is not None else (None, 0)
        slot = found[0].on_use.slot if found else None
        try:
            if donor.is_dead:  # ricontrollo: dall'apertura il donatore può essere caduto o incapacitato
                raise _err("dead")
            refuse_if_incapacitated(donor)
            res = await use_feature(session, donor, key)
        except HTTPException:  # es. reazione già spesa nel frattempo: niente resta speso, la risposta vale «Lascia»
            await session.rollback()
            recorded = await _record(session, request_id, donor_id, entry)
            await session.commit()
            if not recorded:
                raise _err("request_closed")
            raise
        reduction = res.given if res.given is not None else sum(res.rolls)
        entry = {**mine, "status": "used", "reduction": reduction, "rolls": res.rolls,
                 "spent": {"slot": slot, "ability_id": pool_id, "uses": cost, "turn": get_turn(donor).get("turn_no", 0)}}
        result = {"reduction": reduction, "rolls": res.rolls}
    if not await _record(session, request_id, donor_id, entry):
        await session.rollback()  # chiusa mentre rispondeva: né reazione né usi restano spesi
        raise _err("request_closed")
    if use:
        add_history(session, donor_id, "ally_reaction", f"{LABELS[key]}: -{result['reduction']} al danno di {receiver_name}",
                    {"request_id": request_id})
    await close_if_due(session, req)
    return result


async def describe(session: AsyncSession, req: Req) -> dict:
    """La richiesta com'è ora, per il ricevente: chi manca, chi ha risposto e quanto si riduce."""
    req = await _fresh(session, req.id)
    names = dict((await session.execute(select(Character.id, Character.name).where(
        Character.id.in_([a["donor_id"] for a in req.answers])))).all())
    is_open = req.closed_at is None
    return {
        "status": "open" if is_open else "closed",
        "waiting": [{"character_id": a["donor_id"], "name": names[a["donor_id"]], "feature_key": a["feature_key"]}
                    for a in req.answers if is_open and a["status"] == "waiting" and a["donor_id"] in names],
        "answers": [{"name": names[a["donor_id"]], "feature_key": a["feature_key"], "status": a["status"], "reduction": a["reduction"]}
                    for a in req.answers if a["status"] != "waiting" and a["donor_id"] in names],
        "total_reduction": total_reduction(req),
    }


async def prompts_for(session: AsyncSession, donor: Character) -> list[dict]:
    """I popup del donatore: richieste ancora aperte in cui deve rispondere."""
    cutoff = utc_now() - timedelta(seconds=OPEN_SECONDS)
    rows = (await session.execute(select(Req).where(Req.closed_at.is_(None), Req.created_at > cutoff).order_by(Req.id)
                                  .execution_options(populate_existing=True))).scalars().all()
    out: list[dict] = []
    for req in rows:
        mine = next((a for a in req.answers if a["donor_id"] == donor.id and a["status"] == "waiting"), None)
        found = _found(donor, mine["feature_key"]) if mine else None
        if found is None:
            continue
        spec, row = found
        rolls = spec.on_use.rolls
        dice = rolls(RuleContext(char=donor, edition=character_edition(donor), class_row=row, class_level=row.level)) if callable(rolls) else rolls
        if spec.key == INTERCEPTION:
            dice = f"{dice}+{donor.proficiency_bonus}"
        out.append({"request_id": req.id, "receiver_name": (await session.get(Character, req.receiver_id)).name, "damage": req.damage,
                    "damage_type": req.damage_type, "feature_key": spec.key, "dice": dice})
    return out


async def consume(session: AsyncSession, receiver: Character, request_id: int) -> Req:
    """La richiesta del ricevente che il danno sta per usare: sua, chiusa, mai usata né rimborsata (altrimenti 409
    ``request_unusable``). Si segna usata con un UPDATE condizionato, quindi una volta sola anche con due PATCH insieme."""
    req = await _fresh(session, request_id)
    if req is not None and req.receiver_id == receiver.id:
        await close_if_due(session, req)  # scaduta i suoi 30 s senza che nessuno la leggesse
    done = await session.execute(
        update(Req).where(Req.id == request_id, Req.receiver_id == receiver.id, Req.closed_at.is_not(None),
                          Req.used_at.is_(None), Req.refunded_at.is_(None))
        .values(used_at=utc_now()).execution_options(synchronize_session=False))
    if done.rowcount != 1:
        raise _err("request_unusable")
    return await _fresh(session, request_id)


async def donors_of(session: AsyncSession, req: Req) -> list[dict]:
    """Chi ha ridotto il danno e di quanto, per il blocco dei risultati."""
    names = dict((await session.execute(select(Character.id, Character.name).where(
        Character.id.in_([a["donor_id"] for a in req.answers])))).all())
    return [{"name": names[a["donor_id"]], "feature_key": a["feature_key"], "reduction": a["reduction"] or 0}
            for a in req.answers if a["status"] == "used" and a["donor_id"] in names]  # un donatore cancellato non c'è più


async def refund(session: AsyncSession, req: Req, reason: str) -> list[str]:
    """Restituisce ai donatori reazione e usi spesi per questa richiesta, con storico. Una volta sola (UPDATE condizionato su
    ``refunded_at``); ``reason`` ``"annullo"`` vale anche dopo l'uso, ``"scadenza"`` solo se mai usata. La reazione torna solo se il
    donatore è ancora nel turno in cui l'ha spesa; gli usi tornano sempre. Restituisce i nomi dei donatori rimborsati."""
    cond = [Req.id == req.id, Req.refunded_at.is_(None)]
    if reason != "annullo":
        cond.append(Req.used_at.is_(None))
    done = await session.execute(update(Req).where(*cond).values(refunded_at=utc_now()).execution_options(synchronize_session=False))
    if done.rowcount != 1:
        return []
    returned: list[str] = []
    receiver = await session.get(Character, req.receiver_id)
    why = "il danno è stato annullato" if reason == "annullo" else "la richiesta è scaduta senza danno"
    for a in (await _fresh(session, req.id)).answers:
        spent = a.get("spent")
        if a["status"] != "used" or not spent:
            continue
        donor = await session.get(Character, a["donor_id"])
        if donor is None:
            continue
        # shortcut: il rimborso scrive il turno del donatore senza il suo lock (finestra di millisecondi), come ``rules_turn._save``
        if spent.get("slot") and get_turn(donor).get("turn_no", 0) == spent.get("turn", 0):
            release(donor, spent["slot"])
        if spent.get("ability_id"):
            await session.execute(
                update(Ability).where(Ability.id == spent["ability_id"], Ability.character_id == donor.id, Ability.max_uses.is_not(None))
                .values(uses=func.min(Ability.max_uses, func.coalesce(Ability.uses, 0) + spent["uses"])))
            row = await session.get(Ability, spent["ability_id"])
            if row is not None:  # la riga può essere stata cancellata (talento tolto, cambio di livello)
                await session.refresh(row)
        add_history(session, donor.id, "ally_reaction",
                    f"{LABELS[a['feature_key']]}: reazione e usi rimborsati per {receiver.name}, {why}", {"request_id": req.id})
        returned.append(donor.name)
    return returned


async def expire_unused(session: AsyncSession, now: datetime) -> int:
    """Chiude le richieste aperte oltre i 30 s, rimborsa quelle chiuse da più di 2 minuti e mai usate, cancella le vecchie già
    usate o rimborsate. Non fa commit. Restituisce i rimborsi."""
    for req in (await session.execute(select(Req).where(Req.closed_at.is_(None), Req.created_at < now - timedelta(seconds=OPEN_SECONDS))
                                       .execution_options(populate_existing=True))).scalars().all():
        await _close(session, req.id, req.created_at + timedelta(seconds=OPEN_SECONDS))
    due = (await session.execute(select(Req).where(
        Req.closed_at < now - timedelta(seconds=UNUSED_SECONDS), Req.used_at.is_(None), Req.refunded_at.is_(None))
        .execution_options(populate_existing=True))).scalars().all()
    for req in due:
        try:
            async with session.begin_nested():  # una richiesta rotta non ferma le altre (riprova al giro dopo)
                await refund(session, req, "scadenza")
        except Exception:
            logger.exception("rimborso della richiesta %s fallito", req.id)
    await session.execute(delete(Req).where(Req.closed_at < now - timedelta(days=KEEP_DAYS),
                                            (Req.used_at.is_not(None)) | (Req.refunded_at.is_not(None)))
                          .execution_options(synchronize_session=False))
    return len(due)

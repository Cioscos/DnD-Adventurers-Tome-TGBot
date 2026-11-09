"""Chi siede alla stessa serata di un personaggio: il bersaglio dei privilegi che aiutano un alleato (R38)."""
from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.services.homebrew.passive import get_passive_modifiers
from core.rules.modifiers import effective_hp_max
from core.db.models import Ability, Character, CharacterHistory, GameSession, SessionParticipant, SessionStatus


async def seated_allies(session: AsyncSession, char: Character) -> list[Character]:
    """Gli altri personaggi seduti alle serate attive in cui siede ``char``. Conta il personaggio seduto, non l'utente:
    un secondo PG dello stesso giocatore, rimasto a casa, non è al tavolo."""
    mine = select(SessionParticipant.session_id).join(GameSession, GameSession.id == SessionParticipant.session_id).where(
        SessionParticipant.character_id == char.id, GameSession.status == SessionStatus.ACTIVE)
    rows = await session.execute(
        select(Character).join(SessionParticipant, SessionParticipant.character_id == Character.id)
        .where(SessionParticipant.session_id.in_(mine), Character.id != char.id).order_by(Character.id))
    return list(dict.fromkeys(rows.scalars().all()))


async def load_receiver(session: AsyncSession, char_id: int) -> Character:
    """La scheda di chi riceve una cura, riletta da zero con ciò che serve a calcolare i suoi PF massimi: da usare dopo
    la spesa atomica della riserva, così la cura parte dai PF veri e non da quelli letti prima."""
    row = await session.execute(select(Character).options(
        selectinload(Character.classes), selectinload(Character.ability_scores), selectinload(Character.spells),
        selectinload(Character.spell_slots), selectinload(Character.items), selectinload(Character.abilities),
    ).where(Character.id == char_id).execution_options(populate_existing=True))
    return row.scalar_one()


async def _party(session: AsyncSession, char: Character) -> list[Character]:
    """Gli alleati seduti, con ciò che servono aure e doni (un solo caricamento per alleato)."""
    allies = await seated_allies(session, char)
    for ally in allies:
        await session.refresh(ally, ["classes", "ability_scores", "items", "abilities"])
    return allies


def _auras(allies: list[Character]) -> list[dict]:
    from core.rules.auras import projected_auras  # import locale: auras usa il catalogo
    return [aura for ally in allies for aura in projected_auras(ally)]


async def attach_party_auras(session: AsyncSession, char: Character) -> None:
    """Mette su ``char`` le aure che i compagni della serata proiettano su di lui (``char.party_auras``, transitorio):
    le opzioni al tiro `aura:*` le leggono. Fuori serata non ce ne sono."""
    char.party_auras = _auras(await _party(session, char))


async def attach_party(session: AsyncSession, char: Character) -> None:
    """Per un danno subito: le aure (come ``attach_party_auras``) e le opzioni che i compagni gli offrono
    (``RollOptionSpec.for_ally``, es. Dono dei Protettori: ``char.party_donors``, il costo resta sul donatore), con un solo
    caricamento degli alleati. Mette anche ``char.party_hp_max``, i PF massimi con i bonus passivi, che il catalogo
    (senza sessione) usa per la soglia «uccide sul colpo». Tutto transitorio."""
    from core.rules.catalog import active_features  # import locale: il catalogo importa i tipi
    allies = await _party(session, char)
    char.party_auras = _auras(allies)
    char.party_donors = [{"donor": ally, "spec": option, "row": row} for ally in allies if not ally.is_dead
                         for spec, row in active_features(ally) for option in spec.roll_options if option.for_ally]
    char.party_hp_max = effective_hp_max(char, await get_passive_modifiers(session, char, "character.hit_points_max"))


async def spend_donor_tokens(session: AsyncSession, receiver: Character, spent: list[str]) -> list[Character]:
    """Spende sulle schede dei donatori i gettoni ``donor:<pg>:<riga>:<usi>`` delle opzioni confermate, con un UPDATE condizionato
    (stesso uso mai speso due volte: 409 ``option_unavailable``), e scrive lo storico sulla scheda del donatore. Restituisce i donatori."""
    from api.services.rules_states import _spend_atomically  # import locale: rules_states importa questo modulo
    donors: list[Character] = []
    for token in (t for t in spent if t.startswith("donor:")):
        _, donor_id, row_id, amount = token.split(":")
        donor = await session.get(Character, int(donor_id))
        row = await session.get(Ability, int(row_id))
        if donor is None or row is None or row.character_id != donor.id:
            raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "option_unavailable"})
        try:
            await _spend_atomically(session, row, int(amount))
        except HTTPException:  # l'uso è già andato (un altro danno, un altro alleato): la risposta è la stessa dell'opzione
            raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "option_unavailable"}) from None
        session.add(CharacterHistory(
            character_id=donor.id, timestamp=datetime.utcnow().isoformat(timespec="seconds"), event_type="roll_option",
            description=f"{row.name or row.feature_key}: speso per {receiver.name}, che resta a 1 PF"))
        donors.append(donor)
    return donors


async def refund_donor_tokens(session: AsyncSession, receiver: Character, spent: list[str]) -> None:
    """Rimette sulle schede dei donatori gli usi dei gettoni ``donor:`` annullati, con un UPDATE atomico
    (``uses = MIN(max_uses, uses + n)``, come la spesa); scrive lo storico sul donatore."""
    for token in (t for t in spent if t.startswith("donor:")):
        _, donor_id, row_id, amount = token.split(":")
        row = await session.get(Ability, int(row_id))
        if row is None or row.character_id != int(donor_id):
            continue
        await session.execute(
            update(Ability).where(Ability.id == row.id, Ability.max_uses.is_not(None))
            .values(uses=func.min(Ability.max_uses, func.coalesce(Ability.uses, 0) + int(amount))))
        await session.refresh(row)
        session.add(CharacterHistory(
            character_id=row.character_id, timestamp=datetime.utcnow().isoformat(timespec="seconds"), event_type="roll_option",
            description=f"{row.name or row.feature_key}: uso restituito, il danno di {receiver.name} è stato annullato"))


async def ally_target(session: AsyncSession, char: Character, target_id: object) -> Character:
    """Il bersaglio scelto, se siede alla stessa serata e non è ``char``; altrimenti 422 ``invalid_target``."""
    if type(target_id) is int:
        found = next((a for a in await seated_allies(session, char) if a.id == target_id), None)
        if found is not None:
            return found
    raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "invalid_target"})


async def deliver_temp_gifts(session: AsyncSession, char: Character, opts) -> None:
    """PF temporanei che le opzioni al tiro confermate danno a un PG della serata (``RollOptionSpec.temp_hp_gift``). Il bersaglio
    è controllato come per ogni privilegio che aiuta un alleato (422 ``invalid_target``, 409 ``target_dead``); il valore è del
    server. Un errore annulla l'intero tiro: le opzioni già pagate tornano con il rollback della richiesta."""
    from api.services.effects import grant_temp_hp  # import locale: effects non conosce la serata
    for gift in opts.gifts:
        target = await ally_target(session, char, gift["target"])
        receiver = await load_receiver(session, target.id)
        if receiver.is_dead:
            raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "target_dead"})
        out = grant_temp_hp(session, receiver, gift["value"])
        opts.effects.append(
            {"it": f"{receiver.name} ora ha {out['new']} PF temporanei.", "en": f"{receiver.name} now has {out['new']} temporary hit points."}
            if out["applied"] else
            {"it": f"{receiver.name} ha già {out['old']} PF temporanei, più dei {gift['value']} offerti: li conserva.",
             "en": f"{receiver.name} already has {out['old']} temporary hit points, more than the {gift['value']} offered: they keep them."})
    opts.gifts = []


async def temp_hp_receivers(session: AsyncSession, char: Character, wanted: list[int], limit: int) -> list[Character]:
    """Le creature scelte per i PF temporanei di un riposo: partecipanti della serata, senza doppioni, al massimo ``limit``."""
    if len(wanted) != len(set(wanted)) or len(wanted) > limit:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "invalid_target"})
    return [await ally_target(session, char, tid) for tid in wanted]

"""Impulso di Magia Selvaggia (Stregone 2014, Magia Selvaggia 1): d20 una volta per turno, con 1 la tabella dei 50 impulsi.

Il GM chiede l'impulso dopo un incantesimo di 1° livello o più; il giocatore lo conferma nel pannello. Il server tira il d20
(una volta per turno), poi il d100 (due volte dal 14° livello, Caos Controllato: il giocatore sceglie) e applica ciò che si
può applicare: PF, slot, punti stregoneria, azione extra, CA, resistenza e gli stati con timer. Onde di Caos spesa: il GM può
far tirare la tabella senza il d20 e l'uso torna disponibile. L'incantesimo prodotto dalla tabella non subisce Metamagia.
"""
from __future__ import annotations

import random
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.dice_stats import record_dice
from api.services.effects import apply_heal
from api.services.rules_turn import get_turn, grant_action, mark_once, once_used
from core.db.models import CharacterHistory
from core.game.stats import effective_ability_mod
from core.rules.catalog import active_features
from core.rules.catalog.y2014.sorcerer import CK, SP, SURGE, TIDES
from core.rules.catalog.y2014.sorcerer_wild_magic import SURGES, Surge
from core.rules.catalog.y2024.sorcerer_wild_magic import SURGES as SURGES_2024
from core.rules.edition import character_edition
from core.rules.states import begin_state, has_state
from core.rules.types import StateSpec, parse_dice

PENDING = "pending_surge"
REPEAT = "wild_repeat"  # stato dell'impulso 01-02: a ogni turno si tira la tabella
CONTROLLED_CHAOS = f"{CK}.controlled_chaos"
TAMED = f"{CK}.tamed_surge"  # 2024: l'effetto si sceglie invece di tirare, una volta per riposo lungo
LAST_ROW = 97  # 2024: la riga 97-00 non si può scegliere con Impulso Domato


def _err(code: int, name: str) -> HTTPException:
    return HTTPException(code, detail={"code": name})


def _bucket(char, percentile: int) -> Surge:
    table = SURGES_2024 if character_edition(char) == "2024" else SURGES
    return next(s for s in table if s.lo <= percentile <= s.hi)


def _entry(char, percentile: int) -> dict:
    s = _bucket(char, percentile)
    return {"roll": percentile, "lo": s.lo, "hi": s.hi, "label": s.label, "name": dict(s.name), "text": dict(s.text)}


def _owner(char):
    found = next(((s, r) for s, r in active_features(char) if s.key == SURGE), None)
    if found is None:
        raise _err(status.HTTP_404_NOT_FOUND, "feature_not_usable")
    return found[1]


def _has_controlled_chaos(char) -> bool:
    return any(s.key == CONTROLLED_CHAOS for s, _r in active_features(char))


def _roll_dice(char, expr: str) -> list[int]:
    count, sides = parse_dice(expr)
    rolls = [random.randint(1, sides) for _ in range(count)]
    record_dice(char, [(f"d{sides}", v) for v in rolls])
    return rolls


def _state_for(s: Surge) -> StateSpec | None:
    if s.rounds is None and not s.end_of_next_turn:
        return None
    key = s.state_key or ("wild_regeneration" if s.heal_each_turn else "wild_shield" if s.ac else "wild_resistance" if s.resist_all else s.key)
    if s.end_of_next_turn:  # salta il «Nuovo turno» che apre il turno dopo e finisce alla fine di quello (Colpo Mistico)
        return StateSpec(key, ends_on=("new_turn", "turn_end_counted", "manual"), data={"skip_new_turns": 1}, condition=s.condition)
    ends = ("manual", "new_turn") if s.next_turn else ("manual", "attack", "cast") if s.ends_on_act else ("manual",)
    return StateSpec(key, rounds=s.rounds, ends_on=ends, condition=s.condition)


async def _apply(session: AsyncSession, char, percentile: int, repeat: bool = False) -> dict:
    s = _bucket(char, percentile)
    out = {**_entry(char, percentile), "healed": 0, "slot_level": None, "points": False, "state": None, "damage": None,
           "extra_roll": None, "dc": None, "extra_action": False, "ignored": False}
    if repeat and s.state_key == REPEAT:  # tirato a ogni turno dello stato 01-02: un nuovo 01-02 si ignora
        out["ignored"] = True
        return out
    if s.heal:
        out["healed"] = (await apply_heal(session, char, sum(_roll_dice(char, s.heal))))["healed"]
    if s.slot:
        used = sorted((x for x in char.spell_slots if not x.is_pact and x.used > 0), key=lambda x: x.level)
        if used:
            used[0].used -= 1
            out["slot_level"] = used[0].level
    if s.points:
        pool = next((a for a in char.abilities if a.feature_key == SP), None)
        if pool is not None and pool.max_uses is not None and (pool.uses or 0) < pool.max_uses:
            pool.uses = pool.max_uses
            out["points"] = True
    if s.action:
        grant_action(char)
        out["extra_action"] = True
    if s.damage:
        rolls = _roll_dice(char, s.damage[0])
        out["damage"] = {"dice": s.damage[0], "type": s.damage[1], "rolls": rolls, "total": sum(rolls)}
    if s.roll:
        rolls = _roll_dice(char, s.roll)
        out["extra_roll"] = {"dice": s.roll, "rolls": rolls, "total": sum(rolls)}
    if s.dc:
        out["dc"] = 8 + char.proficiency_bonus + effective_ability_mod(char, "charisma")
    spec = _state_for(s)
    if s.state_key == REPEAT:  # nato in questo turno: il primo tiro della ripetizione spetta al turno dopo
        mark_once(char, REPEAT)
    if spec is not None:  # il nome dell'impulso, non quello del privilegio: la barra degli stati mostra cosa è successo
        out["state"] = begin_state(char, spec, f"{SURGE}:{s.lo}", s.name["it"])
    session.add(CharacterHistory(
        character_id=char.id, timestamp=datetime.utcnow().isoformat(timespec="seconds"), event_type="wild_magic",
        description=f"Impulso di Magia Selvaggia {s.label}: {s.name['it']}"))
    return out


def _restore_tides(char) -> bool:
    row = next((a for a in char.abilities if a.feature_key == TIDES), None)
    if row is None or row.max_uses is None:
        return False
    row.uses = row.max_uses
    return True


async def _tamed(session: AsyncSession, char, percentile: list[int] | None) -> dict:
    """Impulso Domato (2024, 18°): l'effetto si sceglie fra quelli della tabella, tranne 97-00; spende l'unico uso."""
    _owner(char)
    row = next((a for a in char.abilities if a.feature_key == TAMED), None)
    if row is None:
        raise _err(status.HTTP_404_NOT_FOUND, "feature_not_usable")
    if not percentile or not 1 <= percentile[0] < LAST_ROW:
        raise _err(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid_choice")
    if (row.uses or 0) <= 0:
        raise _err(status.HTTP_409_CONFLICT, "no_uses")
    row.uses -= 1
    applied = await _apply(session, char, percentile[0])
    return {"die": None, "triggered": True, "pending": False, "options": [_entry(char, percentile[0])], "applied": applied,
            "tides_restored": False}


async def roll_surge(session: AsyncSession, char, die: int | None, percentile: list[int] | None, tides: bool,
                     repeat: bool = False, tamed: bool = False) -> dict:
    if tamed:
        return await _tamed(session, char, percentile)
    owner = _owner(char)
    trigger = 20 if character_edition(char) == "2024" else 1  # 2014: un 1 apre la tabella; 2024: un 20
    tides_row = next((a for a in char.abilities if a.feature_key == TIDES), None)
    if repeat:  # lo stato 01-02: tabella senza d20, una volta per turno
        if not has_state(char, REPEAT):
            raise _err(status.HTTP_409_CONFLICT, "no_repeat")
        if not mark_once(char, REPEAT):
            raise _err(status.HTTP_409_CONFLICT, "once_per_turn")
        d20 = None
    elif tides:  # il GM fa tirare la tabella dopo Onde di Caos: nessun d20, e l'uso torna disponibile
        if tides_row is None or tides_row.max_uses is None or (tides_row.uses or 0) >= tides_row.max_uses:
            raise _err(status.HTTP_409_CONFLICT, "tides_not_spent")
        d20 = None
    else:
        if once_used(char, SURGE):
            raise _err(status.HTTP_409_CONFLICT, "once_per_turn")
        mark_once(char, SURGE)
        d20 = die if die is not None else random.randint(1, 20)
        record_dice(char, [("d20", d20)])
        if d20 != trigger:
            return {"die": d20, "triggered": False, "pending": False, "options": [], "applied": None, "tides_restored": False}
    wanted = 2 if _has_controlled_chaos(char) else 1
    given = [p for p in (percentile or []) if 1 <= p <= 100][:wanted]
    rolls = given + [random.randint(1, 100) for _ in range(wanted - len(given))]
    record_dice(char, [("d100", v) for v in rolls[len(given):]])
    options = [_entry(char, p) for p in rolls]
    if wanted == 2:  # Caos Controllato: il giocatore sceglie, e nulla si applica prima
        turn = get_turn(char)
        turn[PENDING] = {"rolls": rolls, "tides": tides, "repeat": repeat}
        char.turn_state = turn
        return {"die": d20, "triggered": True, "pending": True, "options": options, "applied": None, "tides_restored": False}
    applied = await _apply(session, char, rolls[0], repeat)
    return {"die": d20, "triggered": True, "pending": False, "options": options, "applied": applied,
            "tides_restored": _restore_tides(char) if tides else False}


async def choose_surge(session: AsyncSession, char, index: int) -> dict:
    _owner(char)
    turn = get_turn(char)
    pending = turn.pop(PENDING, None)
    if not pending:
        raise _err(status.HTTP_409_CONFLICT, "no_pending_surge")
    if not 0 <= index < len(pending["rolls"]):
        raise _err(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid_choice")
    char.turn_state = turn
    applied = await _apply(session, char, pending["rolls"][index], bool(pending.get("repeat")))
    return {"die": None, "triggered": True, "pending": False, "options": [_entry(char, p) for p in pending["rolls"]],
            "applied": applied, "tides_restored": _restore_tides(char) if pending.get("tides") else False}

"""Togliere condizioni a sé o a un PG della serata (Task 48): l'unico servizio che legge ``core.rules.condition_removal``,
per i privilegi (``OnUse.removal``) e per gli incantesimi (``SPELL_REMOVAL``). Nessuna logica per singolo incantesimo."""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.condition_effects import effect_snapshot, effects_for_character
from api.services.session_allies import ally_target, load_receiver
from core.data.labels import condition_label
from core.db.models import Character
from core.rules.condition_removal import ConditionRemoval, outcome_lines, resolve_picks
from core.rules.states import RETURNED_FROM, SUSPENDED_BACK, SUSPENDED_EFFECTS, SUSPENDED_KEY, SUSPENDED_ON, begin_state, has_state
from core.rules.types import StateSpec


def plan(removal: ConditionRemoval, chosen: list[str] | None, allowed: tuple[str, ...]) -> tuple[list[str], list[str]]:
    """Cosa si toglie, già controllato contro la regola: 422 ``invalid_condition`` / ``invalid_choice`` prima di spendere."""
    try:
        return resolve_picks(removal, chosen, allowed)
    except ValueError as err:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": str(err)}) from err


async def resolve_targets(session: AsyncSession, caster: Character, removal: ConditionRemoval, wanted: list) -> list[Character | None]:
    """``"self"`` è chi lancia, un id è un partecipante della serata (come per le cure), ``"other"`` una creatura fuori dalla
    serata (``None``: solo una nota). Doppioni, troppe creature o un PG altrui quando la regola non lo ammette: 422."""
    bad = HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "invalid_target"})
    if not wanted or len(wanted) != len(set(map(str, wanted))) or len(wanted) > removal.max_targets:
        raise bad
    out: list[Character | None] = []
    for w in wanted:
        if w == "self":
            out.append(caster)
        elif w == "other":
            if not removal.ally:
                raise bad
            out.append(None)
        elif removal.ally:
            out.append(await ally_target(session, caster, w))
        else:
            raise bad
    return out


async def _suspended_effects(session: AsyncSession, target: Character, present: list[str]) -> dict[str, dict]:
    return {e.slug: {k: v for k, v in effect_snapshot(e).items() if k != "id"}
            for e in await effects_for_character(session, target.id) if e.slug in present and not e.pending}


def _mark_suspended(caster: Character, target: Character, present: list[str], effects: dict[str, dict]) -> None:
    settings = target.settings or {}
    target.settings = {**settings, SUSPENDED_ON: {**(settings.get(SUSPENDED_ON) or {}), **{c: caster.id for c in present}},
                       SUSPENDED_EFFECTS: {**{k: v for k, v in (settings.get(SUSPENDED_EFFECTS) or {}).items() if k not in present}, **effects}}


async def resuspend(session: AsyncSession, caster: Character) -> None:
    """Un annullo ha ridato la concentrazione a chi sospendeva delle condizioni (Calmare Emozioni): quelle tornate con la sua fine,
    se sono ancora attive, si sospendono di nuovo."""
    from api.services.durations import is_concentrating  # import locali, come sopra
    from api.services.effects import apply_conditions
    settings = caster.settings or {}
    if not settings.get(SUSPENDED_BACK) or settings.get(SUSPENDED_KEY) or not has_state(caster, SUSPENDED_KEY) or not is_concentrating(caster):
        return
    held: list[dict] = []
    for entry in settings[SUSPENDED_BACK]:
        if await session.get(Character, entry["id"]) is None:
            continue
        target = await load_receiver(session, entry["id"])
        returned = (target.settings or {}).get(RETURNED_FROM) or {}  # tolta e ripresa nel frattempo: è un'altra, resta
        present = [c for c in entry["conditions"] if (target.conditions or {}).get(c) and returned.get(c) == caster.id]
        if not present:
            continue
        effects = await _suspended_effects(session, target, present)
        await apply_conditions(session, target, {c: False for c in present})
        _mark_suspended(caster, target, present, effects)
        held.append({"id": target.id, "conditions": present})
    caster.settings = {**{k: v for k, v in (caster.settings or {}).items() if k != SUSPENDED_BACK}, **({SUSPENDED_KEY: held} if held else {})}


async def apply_removal(session: AsyncSession, caster: Character, removal: ConditionRemoval, conds: list[str], untracked: list[str],
                        targets: list[Character | None], *, explicit: bool) -> list[dict[str, str]]:
    """Toglie ``conds`` a ogni bersaglio che le ha. Sulla scheda di un altro PG lo storico dice «Condizione X tolta da <nome>»
    (non si annulla, come le cure). Ritorna gli esiti nelle due lingue, comprese le note per ciò che l'app non traccia."""
    from api.services.history import add_history
    from api.services.effects import apply_conditions  # import locale: effects richiama rules_states
    lines: list[dict[str, str]] = []
    held: list[dict] = []  # condizioni sospese, non cancellate: tornano quando finisce la concentrazione di chi lancia
    for target in targets:
        if target is None:
            lines += outcome_lines(removal, target="", removed=[], absent=[], untracked=untracked or list(removal.untracked if removal.quiet else ()), wanted=conds)  # fuori serata lo segna il GM
            continue
        if target.id != caster.id:  # le relazioni che servono a ricalcolare PF e velocità (Sfinimento) vanno caricate
            target = await load_receiver(session, target.id)
        have = target.conditions or {}
        present = [c for c in conds if have.get(c)]
        changes = {c: (int(have[c]) - 1 if c == "exhaustion" else False) for c in present}
        effects = {}
        if removal.suppress:  # la riga cade con la condizione: si mette da parte per quando torna
            effects = await _suspended_effects(session, target, present)
        if changes:
            await apply_conditions(session, target, changes)
        mine = target.id == caster.id
        if removal.suppress and present:
            held.append({"id": target.id, "conditions": present})
            _mark_suspended(caster, target, present, effects)
        if not mine:
            for c in present:
                add_history(session, target.id, "condition_change", f"Condizione {condition_label(c)} tolta da {caster.name}",
                             meta={"slug": c, "active": False, "by": caster.name})
        lines += outcome_lines(removal, target=None if mine else target.name, removed=present,
                               absent=[c for c in conds if c not in present] if explicit else [], untracked=untracked, wanted=conds)
    if held:  # la stessa concentrazione chiude lo stato (end_concentration) e rimette le condizioni
        caster.settings = {**(caster.settings or {}), SUSPENDED_KEY: [*((caster.settings or {}).get(SUSPENDED_KEY) or []), *held]}
        begin_state(caster, StateSpec(SUSPENDED_KEY, ends_on=("concentration_end", "manual")), "removal")
    return lines

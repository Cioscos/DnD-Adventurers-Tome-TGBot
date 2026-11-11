"""Shared, endpoint-agnostic effect appliers.

Extracted so the HP/conditions endpoints AND the consumable "use" endpoint
apply identical D&D 5e rules (heal clamp to effective max, death-save reset on
rising from 0, condition history logging) without duplicating logic.
"""
from __future__ import annotations


from sqlalchemy import event, inspect, update
from sqlalchemy.ext.asyncio import AsyncSession, async_object_session
from sqlalchemy.util import await_only
from sqlalchemy.orm import Session, attributes

from core.db.models import Character, Companion
from core.data.labels import condition_label
from api.services.history import add_history
from api.services.beast_companion import drop_primal_beast
from api.services.telegram_notify import notify_party_emergency
from api.services.condition_effects import clear_effects_for, release_concentration_effects
from api.services.homebrew.passive import get_passive_modifiers
from api.services.homebrew.dispatcher import dispatch
from core.rules.catalog.spells import SPELL_EFFECTS
from core.rules.edition import character_edition
from core.rules.modifiers import INCAPACITATING, effective_hp_max, exhaustion_level, modifiers_for
from core.rules.spell_effects import SPELL_CLOCK_PREFIX, SPELL_STATE_PREFIX
from core.rules.states import COND_RELEASE, SPELL_RELEASE, SPELL_SPENT, SPELL_TEMP_DROPPED, SUSPENDED_ON, TEMP_RELEASE, immune_conditions, settle_closed


async def cap_current_hp(session: AsyncSession, char: Character, *, always: bool = False) -> None:
    """Con il massimo dimezzato (Indebolimento 4) i PF correnti non lo superano.

    Da chiamare dopo ogni scrittura di `hit_points`: quel valore resta il massimo reale e torna
    effettivo quando la penalità finisce. Senza penalità non cambia nulla."""
    # I chiamanti non caricano sempre le relazioni (GM, scadenze, homebrew): servono per i privilegi.
    unloaded = {"classes", "items"} & inspect(char).unloaded
    if unloaded:
        await session.refresh(char, attribute_names=list(unloaded))
    if always or modifiers_for(char, "hp_max").hp_half:  # always: il massimo base è cambiato, si taglia al massimo effettivo (Aiuto compreso)
        bonus = await get_passive_modifiers(session, char, "character.hit_points_max")
        char.current_hit_points = min(char.current_hit_points, effective_hp_max(char, bonus))


def raises_hp_max(closed: list[dict], char: Character) -> bool:
    """Tra gli stati chiusi c'è un incantesimo che alzava i PF massimi (Aiuto, Banchetto degli Eroi). Senza edizione salvata nello stato vale quella di ``char``."""
    for state in closed:
        data = state.get("data") or {}
        effect = SPELL_EFFECTS.get(data.get("spell_key") or str(state.get("key", ""))[len(SPELL_STATE_PREFIX):])
        variant = effect and effect.variants.get(data.get("edition") or character_edition(char))
        if variant and any(m.target == "hp_max" for m in variant.modifiers(data)):
            return True
    return False


def cap_hp_to_max(char: Character, closed: list[dict], bonus: int | None = None) -> None:
    """Finito un effetto che alzava il massimo (Aiuto, Banchetto degli Eroi) i PF attuali non lo superano; per gli altri non cambia nulla.

    ``bonus`` è il bonus PF homebrew; ``None`` lo legge dal database (solo dentro il flush, dove la greenlet permette l'attesa)."""
    if not raises_hp_max(closed, char) or char.hit_points <= 0:
        return
    if bonus is None:
        aio = async_object_session(char)
        bonus = await_only(get_passive_modifiers(aio, char, "character.hit_points_max")) if aio is not None else 0
    char.current_hit_points = min(char.current_hit_points, effective_hp_max(char, bonus))


async def apply_heal(session: AsyncSession, char: Character, amount: int) -> dict:
    """Heal `char` by `amount` HP, clamped to effective max (base + passive
    homebrew bonus). Resets death saves if HP rises from 0. Logs history and
    dispatches the `hp_healed` homebrew event.

    Returns {"old", "new", "healed", "firing"}; the caller collects
    notifications from "firing" via collect_homebrew_notifications.
    """
    was_at_zero = char.current_hit_points == 0
    old = char.current_hit_points
    hb_hp_bonus = await get_passive_modifiers(session, char, "character.hit_points_max")
    effective_max = effective_hp_max(char, hb_hp_bonus)
    # max(old, ...): una cura non abbassa mai i PF.
    char.current_hit_points = max(old, min(effective_max, char.current_hit_points + amount))
    healed = char.current_hit_points - old
    if amount > 0:  # una cura da 0 non è un evento da ricordare
        add_history(session, char.id, "hp_change",
                     f"Cura: +{amount} HP ({old} → {char.current_hit_points})",
                     meta={"op": "HEAL", "amount": healed})
    firing = await dispatch(session, char, "hp_healed", {
        "amount": amount,
        "current_hp_before": old,
        "current_hp_after": char.current_hit_points,
    })
    if was_at_zero and char.current_hit_points > 0:
        ds = dict(char.death_saves or {})
        if ds.get("successes", 0) > 0 or ds.get("failures", 0) > 0 or ds.get("stable", False):
            char.death_saves = {"successes": 0, "failures": 0, "stable": False}
            add_history(session, char.id, "death_save",
                         "Tiri salvezza morte azzerati (HP risaliti sopra 0)")
    await sync_zero_hp(session, char, was_at_zero)
    if amount > 0:
        await end_knock_out(session, char)
    return {"old": old, "new": char.current_hit_points, "healed": healed, "firing": firing}


def grant_temp_hp(session: AsyncSession, char: Character, amount: int) -> dict:
    """PF temporanei dati a ``char`` da un altro: non si sommano, resta il maggiore (2014 e 2024). Storico sulla sua scheda.

    Ritorna ``{"old", "new", "applied"}``; ``applied`` è falso se ne aveva già altrettanti o di più."""
    old = char.temp_hp or 0
    char.temp_hp = max(old, amount)
    add_history(session, char.id, "hp_change",
                 f"PF temporanei: {amount} ({old} → {char.temp_hp})" if char.temp_hp > old
                 else f"PF temporanei offerti: {amount}, tenuti i {old} che aveva già",
                 meta={"op": "TEMP_HP", "amount": amount, "applied": char.temp_hp > old})
    return {"old": old, "new": char.temp_hp, "applied": char.temp_hp > old}


async def sync_zero_hp(session: AsyncSession, char: Character, was_at_zero: bool) -> None:
    """A 0 PF, ancora vivo, il personaggio è Privo di sensi e Prono; risalendo sopra 0 la prima condizione cade.

    Prono resta: ci si rialza spendendo movimento (Turno). Da chiamare dopo ogni scrittura dei PF correnti."""
    if char.is_dead or char.hit_points <= 0:  # senza massimo non c'è «0 PF»
        return
    conditions = char.conditions or {}
    if char.current_hit_points == 0:
        new = {c: True for c in ("unconscious", "prone") if not conditions.get(c)}
        if new:
            await apply_conditions(session, char, new)
    elif was_at_zero and conditions.get("unconscious"):
        await apply_conditions(session, char, {"unconscious": False})


def end_hide(session: AsyncSession, char: Character) -> None:
    """2024: nascosti si è Invisibili finché non si fa rumore, un nemico ti trova, si tira per colpire o si lancia un
    incantesimo con componente Verbale. Chi chiama sa che è accaduto uno di questi."""
    settings = char.settings or {}
    if "hiding" not in settings:
        return
    char.settings = {k: v for k, v in settings.items() if k != "hiding"}
    char.turn_state = {**(char.turn_state or {}), "hide_broken": settings["hiding"]}  # Furtività Suprema lo ripristina
    if settings["hiding"].get("was_invisible"):
        return  # era già Invisibile per un'altra fonte: finisce solo il nascondiglio
    char.conditions = {**(char.conditions or {}), "invisible": False}
    add_history(session, char.id, "condition_change", "Non sei più nascosto: l'Invisibilità finisce",
                 meta={"slug": "invisible", "active": False})


def casts_verbally(spell) -> bool:
    return "V" in {c.strip().upper() for c in (spell.components or "").replace(";", ",").split(",")}


async def end_knock_out(session: AsyncSession, char: Character) -> None:
    """2024: il colpo per tramortire dura finché non c'è una cura, un riposo o un tocco di primo soccorso."""
    settings = dict(char.settings or {})
    if not settings.pop("knocked_out", None):
        return
    char.settings = settings
    if (char.conditions or {}).get("unconscious"):
        await apply_conditions(session, char, {"unconscious": False})


async def apply_conditions(session: AsyncSession, char: Character,
                           changes: dict[str, bool | int]) -> dict:
    """Set/clear conditions on `char` (merging into the existing dict). Logs one
    history row per actual change. `exhaustion` is treated as an integer level;
    all other conditions are booleans. Returns {"changed": bool}.
    """
    old_conditions = dict(char.conditions or {})
    # Uno stato attivo (Ira Incontenibile) impedisce di aggiungere quelle condizioni; toglierle resta possibile.
    immune = immune_conditions(char) if any(changes.values()) else set()  # solo chi aggiunge ha da guardare le immunità
    changes = {c: v for c, v in changes.items() if not (v and c in immune)}
    current = dict(old_conditions)
    current.update(changes)
    char.conditions = current
    if marks := (char.settings or {}).get(SUSPENDED_ON):  # cambiata per altra via: la sospensione non vale più
        left = {c: by for c, by in marks.items() if c not in changes}
        char.settings = {**{k: v for k, v in char.settings.items() if k != SUSPENDED_ON}, **({SUSPENDED_ON: left} if left else {})}
    for flag, slug in (("knocked_out", "unconscious"), ("hiding", "invisible")):
        if changes.get(slug, True) is False and (char.settings or {}).get(flag):
            char.settings = {k: v for k, v in char.settings.items() if k != flag}  # tolta a mano: finito
    from api.services.rules_states import on_conditions  # import locale: rules_states usa apply_heal
    from api.services.durations import end_concentration, is_concentrating  # import locale: durations importa effects
    on_conditions(char, changes)
    # Solo le appena attivate: la webapp rimanda tutta la mappa a ogni modifica.
    if is_concentrating(char) and any(changes.get(c) and not old_conditions.get(c) for c in INCAPACITATING):
        end_concentration(char)
        await release_concentration_effects(session, char)

    changed = False
    for cond, new_val in changes.items():
        is_exhaustion = cond == "exhaustion"
        default = 0 if is_exhaustion else False
        old_val = old_conditions.get(cond, default)
        if is_exhaustion:
            old_val = int(old_val) if isinstance(old_val, (int, bool)) and old_val is not None else 0
            new_disp = int(new_val) if isinstance(new_val, (int, bool)) and new_val is not None else 0
        else:
            new_disp = new_val
        if new_disp != old_val:
            changed = True
            if is_exhaustion:
                add_history(session, char.id, "condition_change",
                             f"Spossatezza: livello {old_val} → {new_disp}",
                             meta={"slug": cond, "active": new_disp > old_val})
            elif new_val:
                add_history(session, char.id, "condition_change",
                             f"Condizione attivata: {condition_label(cond)}",
                             meta={"slug": cond, "active": True})
            else:
                add_history(session, char.id, "condition_change",
                             f"Condizione rimossa: {condition_label(cond)}",
                             meta={"slug": cond, "active": False})
    await clear_effects_for(session, ("character", char.id),
                            [c for c, v in changes.items() if not v])
    if "exhaustion" in changes:
        if exhaustion_level(char) >= 6 and not char.is_dead:
            char.is_dead = True
            await drop_primal_beast(session, char)
            add_history(session, char.id, "death_save", "Morto — spossatezza al 6° livello")
            await notify_party_emergency(session, char, f"💀 {char.name} è morto!")  # come la morte per tiri salvezza
            return {"changed": changed}
        await cap_current_hp(session, char)
    return {"changed": changed}


def _restore_suspended(session: Session, char: Character) -> None:
    """La concentrazione di chi ha sospeso delle condizioni è finita: tornano sul ricevente, se nessuno le ha cambiate nel frattempo."""
    pending = (char.settings or {}).get(COND_RELEASE)
    if not pending:
        return
    char.settings = {k: v for k, v in char.settings.items() if k != COND_RELEASE}
    for entry in pending:
        receiver = session.get(Character, entry["id"])
        if receiver is None:
            continue
        marks = dict((receiver.settings or {}).get(SUSPENDED_ON) or {})
        back = [c for c in entry["conditions"] if marks.get(c) == char.id and c not in immune_conditions(receiver)]
        for c in entry["conditions"]:
            if marks.get(c) == char.id:
                marks.pop(c)
        if receiver.settings and SUSPENDED_ON in receiver.settings:
            receiver.settings = {**{k: v for k, v in receiver.settings.items() if k != SUSPENDED_ON}, **({SUSPENDED_ON: marks} if marks else {})}
        if back:
            receiver.conditions = {**(receiver.conditions or {}), **{c: True for c in back}}
            for c in back:
                add_history(session, receiver.id, "condition_change", f"Condizione tornata: {condition_label(c)} (la concentrazione di {char.name} è finita)",
                             meta={"slug": c, "active": True, "restored": True})


def _end_incapacitated_concentration(session: Session, char: Character) -> None:
    """Uno stato ha appena reso ``char`` Incapacitato senza passare da ``apply_conditions`` (la Letargia 2024 di Velocità, ``drops_concentration``):
    come ogni Incapacitato fa cadere la concentrazione. shortcut: gli effetti a condizione legati alla concentrazione (``ConditionEffect``)
    restano finché non si ricarica la concentrazione, qui non c'è una sessione asincrona; da rivedere se serve."""
    states = char.active_states or []
    if not any((s.get("data") or {}).get("drops_concentration") for s in states):
        return
    char.active_states = [{**s, "data": {k: v for k, v in (s.get("data") or {}).items() if k != "drops_concentration"}} for s in states]
    from api.services.durations import end_concentration, is_concentrating  # import locale: durations importa questo modulo
    if is_concentrating(char):
        end_concentration(char)
        _drop_given_spells(session, char)


def _drop_given_spells(session: Session, char: Character) -> None:
    """L'orologio di un incantesimo è finito, da qualunque via: i bersagli perdono lo stato, ma solo se è ancora di ``char``
    (un altro lanciatore può averlo rinnovato). Un bersaglio cancellato si salta."""
    pending = (char.settings or {}).get(SPELL_RELEASE)
    if not pending:
        return
    char.settings = {k: v for k, v in char.settings.items() if k != SPELL_RELEASE}
    for entry in pending:
        receiver = session.get(Character, entry["id"])
        states = (receiver.active_states or []) if receiver is not None else []
        kept = [s for s in states if not (s.get("key") == entry["key"] and (s.get("data") or {}).get("caster_id") == char.id)]
        if len(kept) != len(states):
            receiver.active_states = kept
            settle_closed(receiver, [x for x in states if x not in kept])  # la condizione imposta (Invisibile) cade con lo stato
            cap_hp_to_max(receiver, [x for x in states if x not in kept])
            _end_incapacitated_concentration(session, receiver)


def _end_spent_spells(session: Session, char: Character) -> None:
    """Un'opzione ha speso lo stato ``spell:*`` di ``char`` e l'incantesimo termina: il lanciatore perde il suo orologio (e la concentrazione solo se è quella dell'incantesimo)."""
    pending = (char.settings or {}).get(SPELL_SPENT)
    if not pending:
        return
    char.settings = {k: v for k, v in char.settings.items() if k != SPELL_SPENT}
    for entry in pending:
        caster = char if entry["caster_id"] == char.id else session.get(Character, entry["caster_id"])
        clock = SPELL_CLOCK_PREFIX + entry["key"][len(SPELL_STATE_PREFIX):]
        if caster is None or not any(s.get("key") == clock for s in caster.active_states or []):
            continue
        if "concentration_end" in next(s for s in caster.active_states if s.get("key") == clock).get("ends_on", ()):
            from api.services.durations import end_concentration  # import locale: durations importa i servizi degli effetti
            end_concentration(caster)  # solo un incantesimo di concentrazione: l'orologio ancora aperto è quello della concentrazione in corso
        left = [s for s in caster.active_states or [] if s.get("key") == clock]  # un incantesimo senza concentrazione: l'orologio si chiude qui
        if left:
            caster.active_states = [s for s in caster.active_states if s.get("key") != clock]
            settle_closed(caster, left)
        _drop_given_spells(session, caster)


def _close_ended_wild_shape(session: Session, char: Character) -> None:
    """Lo stato «wild_shape» è sparito da qualunque via (turno dell'incontro, tick, stato chiuso su un altro PG): la riga della forma
    si chiude qui, senza caricare i compagni nel caso comune (le letture e l'attacco del compagno si fidano della riga)."""
    old = [s for v in attributes.get_history(char, "active_states").deleted for s in v or []]
    if any(s.get("key") == "wild_shape" for s in old) and not any(s.get("key") == "wild_shape" for s in char.active_states or []):
        session.execute(update(Companion).where(Companion.character_id == char.id, Companion.kind == "wild_shape", Companion.is_active.is_(True))
                        .values(is_active=False).execution_options(synchronize_session=False))


@event.listens_for(Session, "before_flush")
def _release_given_temp_hp(session: Session, _ctx, _instances) -> None:
    """Un'Ira (o un altro stato) è finita, da qualunque via: i PF temporanei che chi la viveva ha consegnato svaniscono.

    Si toglie ciò che resta solo se non supera quanto fu consegnato: se il ricevente ne ha presi di più alti nel frattempo, restano.
    shortcut: un valore uguale o minore preso dopo da un'altra fonte svanisce insieme a questo; da rivedere se serve la provenienza."""
    for char in [o for o in session.dirty if isinstance(o, Character)]:
        _close_ended_wild_shape(session, char)
        _restore_suspended(session, char)
        _drop_given_spells(session, char)
        _end_spent_spells(session, char)
        _end_incapacitated_concentration(session, char)
        dropped = (char.settings or {}).get(SPELL_TEMP_DROPPED) or {}
        if any(not e.get("logged") for e in dropped.values()):
            for e in dropped.values():
                if not e.get("logged"):
                    add_history(session, char.id, "hp_change", f"PF temporanei svaniti: {e.get('name')} è finito ({e['amount']} → 0)",
                                 meta={"op": "TEMP_HP", "amount": 0, "released": True})
            kept = {k: {**e, "logged": True} for k, e in dropped.items() if not e.get("log_only")}  # la voce che non serve più si toglie dopo la riga
            char.settings = {**{k: v for k, v in char.settings.items() if k != SPELL_TEMP_DROPPED}, **({SPELL_TEMP_DROPPED: kept} if kept else {})}
        pending = (char.settings or {}).get(TEMP_RELEASE)
        if not pending:
            continue
        char.settings = {k: v for k, v in char.settings.items() if k != TEMP_RELEASE}
        for entry in pending:
            receiver = session.get(Character, entry["id"])
            if receiver is not None and 0 < (receiver.temp_hp or 0) <= entry["amount"]:
                add_history(session, receiver.id, "hp_change", f"PF temporanei svaniti: l'Ira di {char.name} è finita ({receiver.temp_hp} → 0)",
                             meta={"op": "TEMP_HP", "amount": 0, "released": True})
                receiver.temp_hp = 0

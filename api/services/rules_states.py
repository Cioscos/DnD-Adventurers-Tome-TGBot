"""Stati attivi dei privilegi (``Character.active_states``) e uso reale dei privilegi."""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.dice_stats import record_dice
from api.services.rules_turn import (
    attacks_allowed, forgo_attack, get_turn, grant_action, mark_once, once_used, set_damaged, spend,
)
from api.services.session_allies import ally_target, load_receiver
from core.db.models import Ability, SpellSlot
from core.rules.catalog import active_features
from core.rules.edition import character_edition
from core.rules.roll_options import keep_target_effect
from core.rules.states import begin_state, has_state, settle_closed
from core.rules.types import RuleContext, StateSpec, parse_dice
from core.rules.uses import pool_key


def _err(code: int, name: str) -> HTTPException:
    return HTTPException(code, detail={"code": name})


# Stato senza riga del privilegio né nome (Forma Selvatica): come la barra del client.
GENERIC_STATE_NAME = "Effetto attivo"


def get_states(char) -> list[dict]:
    return list(char.active_states or [])


SHORT_REST_ROUNDS = 600  # un'ora, a 6 secondi per round
LONG_REST_ROUNDS = 4800  # otto ore


COUNTED_TURNS = "skip_new_turns"  # data dello stato: quanti «nuovi turni» deve ancora attraversare prima di poter finire


def _turns_to_skip(state: dict) -> int | None:
    """Turni che lo stato deve ancora attraversare; ``None`` se non è uno stato che li conta."""
    return (state.get("data") or {}).get(COUNTED_TURNS)


def end_states(char, *reasons: str, within: int | None = None, keep: set[str] = frozenset()) -> list[str]:
    """Chiude gli stati che finiscono per uno dei ``reasons`` e, con ``within``, quelli che hanno a tempo al più ``within``
    round da vivere; gli stati con la chiave in ``keep`` restano. Restituisce le chiavi chiuse."""
    states = get_states(char)
    kept = [s for s in states if s["key"] in keep or not set(s["ends_on"]) & set(reasons)
            and not (within is not None and s["rounds_left"] is not None and s["rounds_left"] <= within)]
    # chi sopravvive a un riposo ne ha attraversato la durata: gli stati a tempo la perdono (durano più del riposo, quindi restano > 0)
    left = [{**s, "rounds_left": s["rounds_left"] - within} if within is not None and s["rounds_left"] is not None else s
            for s in kept]
    if len(kept) != len(states) or left != kept:
        char.active_states = left  # nuova lista: SQLAlchemy non vede le mutazioni in place
        settle_closed(char, [s for s in states if s not in kept])
    return [s["key"] for s in states if s not in kept]


def end_on_new_turn(char, *, advances: bool = True) -> list[str]:
    """Comincia un turno nuovo: finiscono gli stati di ``new_turn``. Quelli che contano i turni (Colpo Mistico) ne saltano
    uno: il primo «nuovo turno» li fa scalare, il successivo li chiude. ``advances`` è falso per il pulsante «Nuovo turno»
    dentro un incontro, dove il turno lo fa avanzare il GM: non tocca gli stati che contano i turni."""
    counted = {s["key"]: _turns_to_skip(s) for s in get_states(char)
               if _turns_to_skip(s) is not None and "new_turn" in s["ends_on"]}
    if advances and any(counted.values()):
        char.active_states = [{**s, "data": {**s["data"], COUNTED_TURNS: counted[s["key"]] - 1}} if counted.get(s["key"]) else s
                              for s in get_states(char)]
    keep = set(counted) if not advances else {k for k, left in counted.items() if left}
    return end_states(char, "new_turn", keep=keep)


def end_counted_at_turn_end(char) -> list[str]:
    """Fine del turno di chi porta lo stato: chiude quelli che contano i turni e li hanno già attraversati tutti."""
    waiting = {s["key"] for s in get_states(char) if _turns_to_skip(s)}
    return end_states(char, "turn_end_counted", keep=waiting)


EXTENDED = "extended"  # turn_state: nel turno in corso lo stato è stato prolungato senza un attacco (TS imposto o azione bonus)


def end_unextended(char) -> list[str]:
    """Fine del turno di chi porta lo stato: chiude gli stati ``turn_end_unextended`` che nel turno non sono stati prolungati
    (nessun attacco, nessun prolungamento dichiarato). Lo stato nato in questo turno (``data["fresh"]``) vive fino alla
    fine del turno seguente: qui perde solo il segno. Va chiamata prima di azzerare il turno."""
    turn = get_turn(char)
    extended = bool(turn["attacks_made"]) or bool(turn.get(EXTENDED))
    states, kept, closed = get_states(char), [], []
    for s in states:
        if "turn_end_unextended" not in s["ends_on"]:
            kept.append(s)
        elif (s.get("data") or {}).get("fresh"):
            kept.append({**s, "data": {**s["data"], "fresh": False}})
        elif extended:
            kept.append(s)
        else:
            closed.append(s)
    if kept != states:
        char.active_states = kept  # nuova lista: SQLAlchemy non vede le mutazioni in place
        settle_closed(char, closed)
    return [s["key"] for s in closed]


def end_states_on_rest(char, rest: str) -> list[str]:
    """Il riposo chiude gli stati che lo nominano e quelli che durano meno di lui: un'ora per il riposo breve, otto per il
    lungo. Restano gli stati senza durata (a mano, come i sette giorni di Intervento Divino) e quelli a tempo che durano
    oltre, ai quali il riposo toglie la sua durata (600 round il breve, 4800 il lungo). ``rest`` è il riposo che vale
    davvero: un riposo interrotto che non dà benefici non arriva qui (2014 lungo, 2024 breve), il lungo 2024 interrotto
    vale un breve e arriva come ``short``."""
    closed = (end_states(char, "rest_short", "rest_long", within=LONG_REST_ROUNDS) if rest == "long"
              else end_states(char, "rest_short", within=SHORT_REST_ROUNDS))
    # la concentrazione legata a uno stato chiuso finisce con lui (quella degli incantesimi resta, D8)
    held = ((char.settings or {}).get("concentration_item_spell") or {}).get("feature_key")
    if held and held not in {s.get("feature_key") for s in get_states(char)}:
        from api.services.durations import end_concentration  # import locale: durations importa questo modulo
        end_concentration(char)
    return closed


def end_on_action(char, action: str) -> None:
    """Chi attacca (``attack``) o lancia (``cast``) chiude gli stati che finiscono così (Manto di Ombre)."""
    end_states(char, action)


def state_name(char, state: dict) -> str:
    """Nome da mostrare: quello della riga del privilegio (come lo vede il giocatore), poi quello salvato nello stato,
    altrimenti il testo generico: mai la chiave."""
    ability = next((a for a in char.abilities if a.feature_key == state.get("feature_key")), None)
    return (ability.name if ability is not None and ability.name else None) or state.get("name") or GENERIC_STATE_NAME


def tick_states(char) -> list[str]:
    """Un round: scala ``rounds_left``; gli stati a 0 finiscono. Restituisce i nomi degli stati scaduti."""
    states, expired, closed = [], [], []
    for s in get_states(char):
        if s["rounds_left"] is None:
            states.append(s)
        elif s["rounds_left"] > 1:
            states.append({**s, "rounds_left": s["rounds_left"] - 1})
        else:
            expired.append(state_name(char, s))
            closed.append(s)
    if any(s["rounds_left"] is not None for s in get_states(char)):
        char.active_states = states
        settle_closed(char, closed)
    return expired


def on_damage(char, applied: int) -> None:
    """Unico punto per il danno ai PF (`update_hp`, homebrew): segna il danno e chiude gli stati a 0 PF."""
    if applied > 0:
        set_damaged(char)
    if char.current_hit_points == 0:
        end_states(char, "unconscious", "incapacitated")


_INCAPACITATING = {"incapacitated", "paralyzed", "stunned", "petrified"}


def on_conditions(char, changes: dict) -> None:
    """Unico punto per le condizioni impostate (`apply_conditions`): chiude gli stati che non reggono."""
    on = {c for c, v in changes.items() if v}
    if "unconscious" in on:
        end_states(char, "unconscious", "incapacitated")
    elif on & _INCAPACITATING:
        end_states(char, "incapacitated")


def extend_state(char, key: str, rounds: int) -> None:
    """Riporta `rounds_left` a `rounds` senza spendere usi (prolungamento a fine turno, Ira 2024)."""
    states = get_states(char)
    if all(s["key"] != key for s in states):
        raise _err(status.HTTP_404_NOT_FOUND, "state_not_found")
    char.active_states = [{**s, "rounds_left": rounds} if s["key"] == key else s for s in states]


def remove_state(char, key: str, *, by_player: bool = False) -> None:
    """Chiude lo stato. ``by_player``: lo chiude il giocatore, e se lo stato dichiara ``end_slot`` ne spende lo slot;
    con lo slot già speso lo stato finisce lo stesso (un tocco sbagliato si corregge)."""
    states = get_states(char)
    if all(s["key"] != key for s in states):
        raise _err(status.HTTP_404_NOT_FOUND, "state_not_found")
    closed = [s for s in states if s["key"] == key]
    if by_player and any((s.get("data") or {}).get("internal") for s in closed):  # un segno interno non è del giocatore
        raise _err(status.HTTP_404_NOT_FOUND, "state_not_found")
    if by_player and any((s.get("data") or {}).get("locked") for s in closed):  # il conto lo chiude solo il riposo lungo
        raise _err(status.HTTP_409_CONFLICT, "state_locked")
    char.active_states = [s for s in states if s["key"] != key]
    settle_closed(char, closed)
    slot = closed[0].get("end_slot")
    if by_player and slot:
        try:
            spend(char, slot)
        except HTTPException:
            pass  # già speso: nessun costo in più


def start_state(char, spec: StateSpec, feature_key: str, name: str | None = None) -> dict:
    """Avvia lo stato; se la chiave è già attiva lo rinnova. ``name``: come lo chiama il giocatore (``None``: nome generico)."""
    return begin_state(char, spec, feature_key, name)


async def _swap_exclusive_target(session: AsyncSession, char, feature_key: str, target) -> None:
    """Un nuovo uso toglie lo stato dal bersaglio precedente (id scritto dal server, mai dal client) e segna il nuovo."""
    from core.db.models import Character  # import locale
    from core.rules.states import ALLY_EXCLUSIVE
    held = dict((char.settings or {}).get(ALLY_EXCLUSIVE) or {})
    previous = held.get(feature_key)
    if type(previous) is int and previous != (target.id if target is not None else None):
        old = await session.get(Character, previous)
        if old is not None:
            old.active_states = [s for s in old.active_states or [] if s.get("feature_key") != feature_key]
    # ciò che lo stesso privilegio aveva lasciato su chi lo usa cade: lo stato nuovo sta su un alleato o lo rimpiazza (nota, su di sé)
    char.active_states = [s for s in char.active_states or [] if s.get("feature_key") != feature_key]
    if target is not None:
        held[feature_key] = target.id
    else:
        held.pop(feature_key, None)
    char.settings = {**(char.settings or {}), ALLY_EXCLUSIVE: held}


async def _spend_atomically(session: AsyncSession, ability, cost: int) -> None:
    """Spende ``cost`` usi con un UPDATE condizionato (come Preservare Vita): due richieste insieme non spendono gli stessi
    punti. È il primo atto di scrittura, prima di rileggere chi riceve la cura."""
    spent = await session.execute(
        update(Ability).where(Ability.id == ability.id, Ability.uses >= cost).values(uses=Ability.uses - cost))
    if spent.rowcount != 1:
        raise _err(status.HTTP_409_CONFLICT, "no_uses")
    await session.refresh(ability)


async def _spend_slot(session: AsyncSession, char, level: int) -> None:
    """Spende uno slot incantesimo di ``level`` (prima i normali, poi quelli del Patto) con un UPDATE condizionato: due
    richieste insieme non prendono lo stesso slot. 409 ``no_slot`` se non ce n'è uno libero."""
    candidates = sorted((s for s in char.spell_slots if s.level == level and s.used < s.total), key=lambda s: bool(s.is_pact))
    for slot in candidates:
        taken = await session.execute(
            update(SpellSlot).where(SpellSlot.id == slot.id, SpellSlot.used < SpellSlot.total).values(used=SpellSlot.used + 1))
        if taken.rowcount == 1:
            await session.refresh(slot)
            return
    raise _err(status.HTTP_409_CONFLICT, "no_slot")


@dataclass
class UseResult:
    rolls: list[int] = field(default_factory=list)
    healed: int = 0
    state: dict | None = None
    notes: list[str] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)  # chiavi per ``POST /target-effects``
    given: int | None = None  # valore da dare a un altro (``OnUse.gives``): l'app lo mostra e non scrive nulla
    received: dict | None = None  # chi ha ricevuto una cura dal privilegio (Imposizione delle Mani): ``{name, healed}``
    temp_hp: int | None = None  # PF temporanei che il privilegio ha dato a chi lo usa (il maggiore fra attuali e nuovi)
    message: dict | None = None  # esito scritto dal privilegio (``OnUse.message``), nelle due lingue
    attack: dict | None = None  # il tiro per colpire di ``OnUse.spell_attack``: die, bonus, total, mode, is_critical, is_fumble


def _feature_attack(char, ability: str) -> dict:
    """Attacco con incantesimo a distanza di un privilegio: d20 con i modificatori dell'attacco, competenza e caratteristica."""
    from api.services.d20 import d20_records, resolve_applied  # import locale
    from core.game.stats import effective_ability_mod
    from core.rules.modifiers import modifiers_for
    applied = modifiers_for(char, "attack", ability=ability, attack_mode="ranged")
    outcome = resolve_applied("normal", None, None, applied)
    record_dice(char, d20_records(outcome))
    bonus = char.proficiency_bonus + effective_ability_mod(char, ability) + applied.flat
    fumble = outcome.kept == 1
    return {"die": outcome.kept, "dice": outcome.dice, "mode": outcome.mode, "bonus": bonus, "total": outcome.kept + bonus,
            "is_fumble": fumble, "is_critical": outcome.kept >= applied.crit_min and not fumble, "notes": applied.notes}


async def use_feature(session: AsyncSession, char, feature_key: str, amount: int = 1,
                      params: dict | None = None) -> UseResult:
    """Usa un privilegio a catalogo con ``on_use``: spende gli usi della sua riga ``Ability``,
    lo slot di turno e applica cura, stato e azione extra. Tutti i controlli prima di ogni modifica."""
    found = next(((s, r) for s, r in active_features(char) if s.key == feature_key and s.on_use), None)
    if found is None:
        raise _err(status.HTTP_404_NOT_FOUND, "feature_not_usable")
    spec, row = found
    on_use = spec.on_use
    if on_use.panel:
        raise _err(status.HTTP_409_CONFLICT, "needs_panel")
    if on_use.max_amount is not None and amount > on_use.max_amount:
        raise _err(status.HTTP_409_CONFLICT, "amount_too_high")
    if amount < on_use.min_amount:
        raise _err(status.HTTP_409_CONFLICT, "amount_too_low")
    if on_use.once_per_turn and once_used(char, feature_key):
        raise _err(status.HTTP_409_CONFLICT, "once_per_turn")
    if on_use.forgoes_attack and get_turn(char)["action_attacks"] >= attacks_allowed(char):
        raise _err(status.HTTP_409_CONFLICT, "no_attack_left")
    if on_use.available and not on_use.available(
            RuleContext(char=char, edition=character_edition(char), class_row=row, class_level=row.level)):
        raise _err(status.HTTP_409_CONFLICT, "feature_unavailable")
    ctx_choice = RuleContext(char=char, edition=character_edition(char), class_row=row, class_level=row.level)
    for choice in on_use.choices:  # prima di spendere: un valore fuori elenco non costa nulla
        if choice.applies and not choice.applies(ctx_choice):
            continue
        given = (params or {}).get(choice.key)
        if choice.optional and given is None:
            continue
        if given not in choice.options(ctx_choice):
            raise _err(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid_choice")
    for text in on_use.texts:  # come le scelte: un testo non valido non costa nulla
        given = (params or {}).get(text.key)
        needed = not text.optional or (text.required is not None and text.required(params or {}))
        if given is None and not needed:
            continue
        if not isinstance(given, str) or not given.strip() or len(given.strip()) > text.max_len:
            raise _err(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid_text")
    if on_use.check and (refusal := on_use.check(ctx_choice, params or {})) is not None:
        raise _err(*refusal)
    if on_use.amount_ok and not on_use.amount_ok(ctx_choice, amount, params or {}):
        raise _err(status.HTTP_409_CONFLICT, "amount_invalid")
    if on_use.gold_cost:  # l'oro si controlla prima di toccare slot, usi e turno
        from api.services.containers import withdraw  # import locale: containers importa il modello degli oggetti
        await session.refresh(char, attribute_names=["currency"])
        withdraw(char, "gold", on_use.gold_cost)
    maximize = False
    extra = None
    if on_use.maximize_if and on_use.maximize_if(
            RuleContext(char=char, edition=character_edition(char), class_row=row, class_level=row.level), params or {}):
        maximize = True
    if maximize and on_use.maximize_cost:  # senza costo (Guarigione Suprema) i dadi valgono il massimo e basta
        extra = next((a for a in char.abilities if a.feature_key == pool_key(char, on_use.maximize_cost)), None)
        if extra is None or (extra.max_uses is not None and (extra.uses or 0) < 1):
            raise _err(status.HTTP_409_CONFLICT, "no_uses")
    target = None
    for_other = (params or {}).get("mode") in on_use.ally_modes  # una scelta rivolta a un'altra creatura (R46)
    if (on_use.ally_state or for_other) and (params or {}).get("target_character_id") is not None:
        target = await ally_target(session, char, params["target_character_id"])
    heals_ally = bool(for_other and on_use.heal_ally_when and on_use.heal_ally_when(ctx_choice, params or {}))
    ability = next((a for a in char.abilities if a.feature_key == feature_key and a.source_class_id == row.id), None)
    cost = on_use.cost_by(ctx_choice, params or {}) if on_use.cost_by else on_use.cost * amount
    # «Ripristina» spendendo un uso di un altro privilegio (Presenza Intimidatoria: un uso di Ira)
    spends = on_use.alt_spends if on_use.alt_spends and (params or {}).get(on_use.alt_param) else on_use.spends
    if spends:  # gli usi sono di un altro privilegio (Parole Taglienti spende l'Ispirazione Bardica)
        ability = next((a for a in char.abilities if a.feature_key == pool_key(char, spends)), None)
        if ability is None or (ability.max_uses is not None and (ability.uses or 0) < cost):
            raise _err(status.HTTP_409_CONFLICT, "no_uses")
    elif spec.uses is not None:
        # senza riga o con usi a None il contatore è illimitato solo se la formula lo dichiara (max_uses None)
        if ability is None or (ability.max_uses is not None and (ability.uses or 0) < cost):
            raise _err(status.HTTP_409_CONFLICT, "no_uses")
    slot = on_use.slot_by(ctx_choice, params or {}) if on_use.slot_by else on_use.slot
    if slot:
        spend(char, slot)  # 409 turn_slot_used prima di toccare gli usi
    if on_use.spends_slot and (on_use.spends_slot_when is None or on_use.spends_slot_when(ctx_choice, params or {})):
        await _spend_slot(session, char, int((params or {})[on_use.spends_slot]))
    if on_use.once_per_turn:
        mark_once(char, feature_key)
    if on_use.forgoes_attack:
        forgo_attack(char)
    if ability is not None and ability.max_uses is not None and ability.uses is not None:
        await _spend_atomically(session, ability, cost)  # UPDATE condizionato: un doppio tocco non spende due volte gli stessi usi
    if heals_ally and target is not None:  # dopo la spesa atomica il bersaglio si rilegge: i suoi PF sono quelli veri
        target = await load_receiver(session, target.id)
        if target.is_dead:
            raise _err(status.HTTP_409_CONFLICT, "target_dead")
    if extra is not None and extra.max_uses is not None and extra.uses is not None:
        extra.uses -= 1

    result = UseResult()
    ctx = RuleContext(char=char, edition=character_edition(char), class_row=row, class_level=row.level)
    healed = 0
    healed_ally = 0
    if on_use.rolls_by_amount:  # i dadi dipendono da quanto si spende e non si ripetono per unità
        formula = on_use.rolls_by_amount(ctx, amount)
    else:
        formula = on_use.rolls(ctx) if callable(on_use.rolls) else on_use.rolls
    dice = parse_dice(formula) if formula else None
    if on_use.spell_attack:  # il d20 prima dei dadi: un mancato non fa danno, un critico li raddoppia
        result.attack = _feature_attack(char, on_use.spell_attack)
        end_on_action(char, "attack")
        if dice:
            dice = (0 if result.attack["is_fumble"] else dice[0] * (2 if result.attack["is_critical"] else 1), dice[1])
    for _ in range(1 if on_use.rolls_by_amount else amount):  # l'effetto è per unità: un pool (Imposizione delle Mani) lo ripete N volte
        rolled = ([dice[1]] * dice[0] if maximize else [random.randint(1, dice[1]) for _ in range(dice[0])]) if dice else []
        result.rolls += rolled
        if on_use.heal and (on_use.heal_when is None or on_use.heal_when(ctx, params or {})):
            healed += max(0, on_use.heal(ctx, sum(rolled)))
        if on_use.heal and heals_ally:
            healed_ally += max(0, on_use.heal(ctx, sum(rolled)))
        if on_use.grants_action:
            grant_action(char)
    if dice:
        record_dice(char, [(f"d{dice[1]}", r) for r in result.rolls])
    if on_use.gives:
        result.given = max(0, on_use.gives(ctx, sum(result.rolls)))
    if on_use.notes:
        result.notes += on_use.notes(ctx, params or {})
    if heals_ally:
        if target is None:  # fuori serata, o un'altra creatura: il giocatore lo riporta al GM (D1)
            result.given = healed_ally
        else:
            from api.services.effects import apply_heal  # import locale: effects richiama on_conditions
            if on_use.heal_ally_to:
                healed_ally = max(0, healed_ally - target.current_hit_points)
            got = (await apply_heal(session, target, healed_ally))["healed"]
            result.received = {"name": target.name, "healed": got}
    if on_use.clears_ally and for_other and target is not None:
        from api.services.effects import apply_conditions  # import locale, come sopra
        target = await load_receiver(session, target.id)
        removed = {c: False for c in on_use.clears_ally(ctx, params or {}) if (target.conditions or {}).get(c)}
        if removed:
            await apply_conditions(session, target, removed)
    if on_use.clears:
        from api.services.effects import apply_conditions  # import locale, come sopra
        removed = {c: False for c in on_use.clears(ctx, params or {}) if (char.conditions or {}).get(c)}
        if removed:
            await apply_conditions(session, char, removed)
    if on_use.heal_by:
        healed += max(0, on_use.heal_by(ctx, params or {}))
    if on_use.heal or on_use.heal_by:
        from api.services.effects import apply_heal  # import locale: effects richiama on_conditions
        result.healed = (await apply_heal(session, char, healed))["healed"]
    if on_use.temp_hp or on_use.temp_hp_by:  # i PF temporanei non si sommano: vale il maggiore
        granted = max(0, on_use.temp_hp_by(ctx, sum(result.rolls), params or {}) if on_use.temp_hp_by
                      else on_use.temp_hp(ctx, sum(result.rolls)))
        if granted:  # niente toast «PF temporanei: 0» a ogni uso che non ne dà
            result.temp_hp = granted
            char.temp_hp = max(char.temp_hp or 0, granted)
    if on_use.ends_concentration:
        from api.services.durations import end_concentration  # import locale: durations importa questo modulo
        end_concentration(char)
    if on_use.concentration:
        from api.services.durations import start_concentration  # import locale, come sopra
        spell_state = on_use.state(ctx, {}) if callable(on_use.state) else on_use.state
        start_concentration(char, None, spell_state.rounds if spell_state else None,
                            {"feature_key": feature_key, "name": spec.name["it"]})
    if on_use.ends_concentration or on_use.concentration:  # come /spells/{id}/use: cadono gli effetti dell'incantesimo di prima
        from api.services.condition_effects import release_concentration_effects  # import locale
        await release_concentration_effects(session, char)
    if on_use.ally_exclusive:
        await _swap_exclusive_target(session, char, feature_key, target)
    if on_use.state:
        own = next((a for a in char.abilities if a.feature_key == feature_key and a.source_class_id == row.id), None)
        name = (own.name if own is not None and own.name else None) or spec.name["it"]
        # `rolled`: il tiro del privilegio, per chi decide lo stato dall'esito (Intervento Divino); mai dal client
        given = {**(params or {}), "rolled": sum(result.rolls), "maximized": maximize}
        state_spec = on_use.state(ctx, given) if callable(on_use.state) else on_use.state
        if state_spec is not None:  # ``None``: l'uso non avvia nulla (il prolungamento dell'Ira)
            result.state = start_state(target if target is not None else char, state_spec, feature_key, name)
    if on_use.clears_condition and (params or {}).get(on_use.clears_condition) is not None:  # Mente Lucida: la condizione scelta cade
        from api.services.effects import apply_conditions  # import locale: effects richiama on_conditions
        await apply_conditions(session, char, {params[on_use.clears_condition]: False})
    if on_use.ends_state and has_state(char, on_use.ends_state):  # già finito (Duplicato Migliorato dopo la fine): niente da chiudere
        remove_state(char, on_use.ends_state)
    if on_use.target_effect:
        keep_target_effect(char, feature_key, on_use.target_effect(ctx, params or {}))
        result.targets.append(feature_key)
    if on_use.message:  # prima dell'effetto: vede la scheda com'era (i PF dell'interdizione prima dell'assorbimento)
        result.message = on_use.message(ctx, params or {})
    if on_use.effect:
        on_use.effect(ctx, params or {})
    return result

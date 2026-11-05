"""Stato del turno salvato sul server (``Character.turn_state``)."""
from __future__ import annotations

from fastapi import HTTPException, status

from core.game.actions import attacks_per_action
from core.rules.catalog import active_features
from core.rules.modifiers import is_incapacitated
from core.rules.types import TURN_FLAGS as _FLAGS

SLOTS = (*_FLAGS, "attack")


def _default() -> dict:
    return {
        "action_used": False, "bonus_used": False, "reaction_used": False,
        "attacks_made": 0, "action_attacks": 0, "extra_actions": 0, "once_per_turn": [],
        "spell_slot_cast": False, "bonus_spell_cast": False, "free_interaction_used": False,
        "damaged": False, "surprised": False,
    }


def get_turn(char) -> dict:
    """Stato del turno con tutti i campi (i personaggi senza dati partono da zero)."""
    return {**_default(), **(char.turn_state or {})}


# shortcut: read-modify-write sul JSON, più dispositivi insieme possono sovrascriversi; usare un
# UPDATE atomico o un lock di riga se serve il multi-dispositivo.
def _save(char, state: dict) -> None:
    char.turn_state = state  # nuovo dict: SQLAlchemy non vede le mutazioni in place


def spend(char, slot: str, *, own_slot: bool = False) -> dict:
    """Segna ``slot`` come usato; 409 ``turn_slot_used`` se lo era già.

    ``attack``: ``attacks_made`` conta ogni attacco del turno (l'Ira ne ha bisogno), ``action_attacks`` solo quelli
    dell'azione Attacco; ``own_slot`` (Frenesia, Ritorsione: costano la loro azione bonus o reazione) non la consuma.

    L'azione già usata consuma un'azione extra (Azione Impetuosa) se ce n'è una."""
    if slot not in SLOTS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "bad_slot"})
    st = get_turn(char)
    if slot == "attack":
        st["attacks_made"] += 1
        if not own_slot:
            st["action_attacks"] += 1
    elif slot == "action" and st["action_used"] and st["extra_actions"] > 0:
        st["extra_actions"] -= 1
    elif st[_FLAGS[slot]]:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "turn_slot_used"})
    else:
        st[_FLAGS[slot]] = True
    _save(char, st)
    return st


def release(char, slot: str) -> dict:
    """Annulla l'uso di ``slot`` (correzione manuale)."""
    if slot not in SLOTS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "bad_slot"})
    st = get_turn(char)
    if slot == "attack":
        st["attacks_made"] = max(0, st["attacks_made"] - 1)
        st["action_attacks"] = min(st["action_attacks"], st["attacks_made"])
    else:
        st[_FLAGS[slot]] = False
    _save(char, st)
    return st


def grant_action(char) -> dict:
    """+1 azione extra per questo turno (Azione Impetuosa)."""
    st = get_turn(char)
    st["extra_actions"] += 1
    _save(char, st)
    return st


def once_used(char, key: str) -> bool:
    """L'effetto «una volta per turno» ``key`` è già stato usato in questo turno."""
    return key in get_turn(char)["once_per_turn"]


def forgo_attack(char) -> dict:
    """Rinuncia a un attacco dell'azione Attacco (Colpo del Comandante): conta fra quelli dell'azione, non fra quelli fatti
    (l'Ira 2014 guarda gli attacchi fatti). 409 ``no_attack_left`` se non ne restano."""
    st = get_turn(char)
    if st["action_attacks"] >= attacks_allowed(char):
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "no_attack_left"})
    st["action_attacks"] += 1
    _save(char, st)
    return st


def mark_once(char, key: str) -> bool:
    """Registra un effetto «una volta per turno»; False se era già stato usato."""
    st = get_turn(char)
    if key in st["once_per_turn"]:
        return False
    st["once_per_turn"] = [*st["once_per_turn"], key]
    _save(char, st)
    return True


def clear_once_per_turn(char) -> list[str]:
    """Comincia il turno di un altro: tornano gli effetti «una volta per turno», reazione esclusa.
    Restituisce la lista svuotata."""
    used = get_turn(char)["once_per_turn"]
    if used:
        _save(char, {**get_turn(char), "once_per_turn": []})
    return used


def reset_turn(char, keep_surprise: bool = True, advances: bool = True) -> dict:
    """Nuovo turno: tutto a zero (anche reazione, azioni extra e attacco in sospeso).

    ``damaged`` resta: il danno preso fra un turno e l'altro conta a fine turno (Ira 2014). ``surprised`` resta: lo
    toglie la fine del primo turno del combattente, non «Nuovo turno», ma solo se c'è un incontro attivo
    (``keep_surprise``): fuori da un incontro non c'è nessuno che la tolga. ``vex`` arriva fino alla
    fine del turno seguente a quello del colpo. ``advances`` è falso per il pulsante «Nuovo turno» dentro un incontro:
    il turno lo fa avanzare il GM e gli stati che contano i turni non scalano."""
    from api.services.rules_states import end_on_new_turn  # import locale: rules_states importa questo modulo
    end_on_new_turn(char, advances=advances)  # il Canto di Riposo del bardo finisce al prossimo «Nuovo turno»
    previous = get_turn(char)
    vex = {"vex": previous["vex"] - 1} if previous.get("vex", 0) > 1 else {}
    notice = {} if advances or not previous.get("start_heal") else {"start_heal": previous["start_heal"]}
    _save(char, {**_default(), "damaged": previous["damaged"],
                 "surprised": previous["surprised"] and keep_surprise, **vex, **notice})
    return char.turn_state


def set_start_heal(char, notices: list[dict]) -> None:
    """Avviso della cura d'inizio turno (Sopravvissuto): resta sul turno fino al prossimo ``reset_turn``."""
    st = get_turn(char)
    if st.get("start_heal", []) != notices:
        _save(char, {**st, "start_heal": notices})


def set_damaged(char, value: bool = True) -> None:
    """Segna (o azzera, dopo la valutazione di fine turno) il danno subito dall'ultimo turno."""
    st = get_turn(char)
    if st["damaged"] != value:
        _save(char, {**st, "damaged": value})


def set_surprised(char, value: bool = True) -> None:
    """2014: il turno in corso è quello della sorpresa (nessuna azione, movimento o reazione)."""
    st = get_turn(char)
    if st["surprised"] != value:
        _save(char, {**st, "surprised": value})


def refuse_if_incapacitated(char) -> None:
    """Chi non può compiere azioni né reazioni non attacca."""
    if is_incapacitated(char):
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "incapacitated"})


def attacks_allowed(char) -> int:
    """Attacchi del turno: per azione il massimo fra 1 e i privilegi attivi, mai somma fra classi, per le azioni disponibili."""
    per_action = max(
        attacks_per_action(char.classes),
        *(spec.attacks_per_action for spec, _ in active_features(char)), 1,
    )
    return per_action * (1 + get_turn(char)["extra_actions"])

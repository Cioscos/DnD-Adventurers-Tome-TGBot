"""Stato del turno salvato sul server (``Character.turn_state``)."""
from __future__ import annotations

from fastapi import HTTPException, status

from core.game.actions import attacks_per_action
from core.rules.catalog import active_features

# slot di turno -> chiave booleana dello stato
_FLAGS = {
    "action": "action_used",
    "bonus": "bonus_used",
    "reaction": "reaction_used",
    "free_interaction": "free_interaction_used",
    "spell_slot": "spell_slot_cast",
    "bonus_spell": "bonus_spell_cast",
}
SLOTS = (*_FLAGS, "attack")


def _default() -> dict:
    return {
        "action_used": False, "bonus_used": False, "reaction_used": False,
        "attacks_made": 0, "extra_actions": 0, "once_per_turn": [],
        "spell_slot_cast": False, "bonus_spell_cast": False, "free_interaction_used": False,
    }


def get_turn(char) -> dict:
    """Stato del turno con tutti i campi (i personaggi senza dati partono da zero)."""
    return {**_default(), **(char.turn_state or {})}


# shortcut: read-modify-write sul JSON, più dispositivi insieme possono sovrascriversi; usare un
# UPDATE atomico o un lock di riga se serve il multi-dispositivo.
def _save(char, state: dict) -> None:
    char.turn_state = state  # nuovo dict: SQLAlchemy non vede le mutazioni in place


def spend(char, slot: str) -> dict:
    """Segna ``slot`` come usato; 409 ``turn_slot_used`` se lo era già.

    L'azione già usata consuma un'azione extra (Azione Impetuosa) se ce n'è una."""
    if slot not in SLOTS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "bad_slot"})
    st = get_turn(char)
    if slot == "attack":
        st["attacks_made"] += 1
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


def mark_once(char, key: str) -> bool:
    """Registra un effetto «una volta per turno»; False se era già stato usato."""
    st = get_turn(char)
    if key in st["once_per_turn"]:
        return False
    st["once_per_turn"] = [*st["once_per_turn"], key]
    _save(char, st)
    return True


def reset_turn(char) -> dict:
    """Nuovo turno: tutto a zero (anche reazione, azioni extra e attacco in sospeso)."""
    _save(char, _default())
    return char.turn_state


def attacks_allowed(char) -> int:
    """Attacchi per azione Attacco: massimo fra 1 e i privilegi attivi, mai somma fra classi."""
    return max(
        attacks_per_action(char.classes),
        *(spec.attacks_per_action for spec, _ in active_features(char)), 1,
    )

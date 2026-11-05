"""Stati attivi dei privilegi, funzioni pure su ``Character.active_states`` (nessun import da ``api/``)."""
from __future__ import annotations

from typing import Any

from core.rules.types import StateSpec


def get_states(char: Any) -> list[dict]:
    return list(char.active_states or [])


def has_state(char: Any, key: str) -> bool:
    return any(s.get("key") == key for s in char.active_states or [])


def begin_state(char: Any, spec: StateSpec, feature_key: str, name: str | None = None) -> dict:
    """Avvia lo stato; se la chiave è già attiva lo rinnova. ``name``: come lo chiama il giocatore (``None``: nome generico)."""
    state = {"key": spec.key, "feature_key": feature_key, "rounds_left": spec.rounds,
             "ends_on": list(spec.ends_on), "data": dict(spec.data), "name": name,
             "blocks_casting": spec.blocks_casting, "exhaustion_on_end": spec.exhaustion_on_end,
             "immune_conditions": list(spec.immune_conditions), "end_slot": spec.end_slot}
    if spec.condition:
        # rinnovare lo stato non cambia di chi era l'invisibilità: la prima volta ricorda se c'era già
        previous = next((s for s in get_states(char) if s["key"] == spec.key and s.get("condition")), None)
        was_on = previous["condition_was_on"] if previous else bool((char.conditions or {}).get(spec.condition))
        state.update(condition=spec.condition, condition_was_on=was_on)
        char.conditions = {**(char.conditions or {}), spec.condition: True}
    char.active_states = [*(s for s in get_states(char) if s["key"] != spec.key), state]
    return state


def free_cast_state(char: Any, spell: Any) -> dict | None:
    """Lo stato attivo che autorizza a lanciare ``spell`` senza slot (``data["free_cast"]`` = ``srd_index``): R43.
    L'autorizzazione sta sul server e si chiude col lancio."""
    key = getattr(spell, "srd_index", None)
    return next((s for s in char.active_states or [] if key and (s.get("data") or {}).get("free_cast") == key), None)


def immune_conditions(char: Any) -> set[str]:
    """Condizioni che gli stati attivi e i privilegi (Interdizione della Natura) impediscono, sospendendo quelle già presenti."""
    from core.rules.catalog import active_features  # import locale: il catalogo importa questo modulo
    from_states = {c for s in char.active_states or [] for c in s.get("immune_conditions") or []}
    return from_states | {c for spec, _row in active_features(char) for c in spec.condition_immunities}


def casting_blocked_by(char: Any) -> bool:
    return any(s.get("blocks_casting") for s in char.active_states or [])


def settle_closed(char: Any, closed: list[dict]) -> None:
    """Ciò che lasciano gli stati appena chiusi: la spossatezza dichiarata e la fine della condizione che imponevano."""
    charge_exhaustion(char, closed)
    gone = {s["condition"] for s in closed if s.get("condition") and not s.get("condition_was_on")}
    gone -= {s["condition"] for s in char.active_states or [] if s.get("condition")}  # un altro stato la impone ancora
    if gone:
        char.conditions = {**(char.conditions or {}), **{c: False for c in gone}}


def charge_exhaustion(char: Any, closed: list[dict]) -> None:
    """Gli stati appena chiusi lasciano la spossatezza che dichiaravano (Frenesia). Al 6° livello si muore.

    shortcut: nessuna riga di cronologia (gli stati si chiudono anche dove non c'è una sessione di database)."""
    levels = sum(int(s.get("exhaustion_on_end") or 0) for s in closed)
    if not levels:
        return
    conditions = dict(char.conditions or {})
    current = conditions.get("exhaustion", 0)
    new = min(6, (int(current) if isinstance(current, (int, bool)) else 0) + levels)
    char.conditions = {**conditions, "exhaustion": new}
    if new >= 6:
        char.is_dead = True


def exhaustion_level(char: Any) -> int:
    """Livello di spossatezza della scheda (0 se assente o non numerico)."""
    value = (char.conditions or {}).get("exhaustion", 0)
    return int(value) if isinstance(value, (int, bool)) else 0


def restore_exhaustion(char: Any, level: int) -> None:
    """Rimette la spossatezza com'era prima di un'operazione annullata."""
    conditions = {k: v for k, v in (char.conditions or {}).items() if k != "exhaustion"}
    char.conditions = {**conditions, "exhaustion": level} if level else conditions


ZERO_HP_USES = "zero_hp_save_uses"  # settings: {feature_key: usi dal riposo}


ALLY_EXCLUSIVE = "ally_exclusive"  # settings: {chiave del privilegio: id del personaggio che ha il suo stato}, scritto dal server


TARGET_IMMUNITY = "target_immunity"  # settings: {chiave dell'effetto: ["combatant:3", "character:7"]}


def target_key(combatant: Any) -> str:
    return f"character:{combatant.character_id}" if combatant.kind == "pc" else f"combatant:{combatant.id}"


def is_target_immune(char: Any, effect_key: str, combatant: Any) -> bool:
    return target_key(combatant) in ((char.settings or {}).get(TARGET_IMMUNITY) or {}).get(effect_key, [])


def add_target_immunity(char: Any, effect_key: str, target: str) -> None:
    immune = {k: list(v) for k, v in ((char.settings or {}).get(TARGET_IMMUNITY) or {}).items()}
    if target not in immune.setdefault(effect_key, []):
        immune[effect_key].append(target)
    char.settings = {**(char.settings or {}), TARGET_IMMUNITY: immune}


def reset_target_immunity(char: Any) -> None:
    """Il riposo lungo chiude le «24 ore» delle immunità di un effetto su altri."""
    settings = char.settings or {}
    if settings.get(TARGET_IMMUNITY):
        char.settings = {k: v for k, v in settings.items() if k != TARGET_IMMUNITY}


def reset_zero_hp_uses(char: Any) -> None:
    """Un riposo, breve o lungo, azzera la CD crescente dei TS a 0 PF (Ira Implacabile)."""
    settings = char.settings or {}
    if settings.get(ZERO_HP_USES):
        char.settings = {k: v for k, v in settings.items() if k != ZERO_HP_USES}

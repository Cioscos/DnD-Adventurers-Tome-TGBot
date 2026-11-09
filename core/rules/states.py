"""Stati attivi dei privilegi, funzioni pure su ``Character.active_states`` (nessun import da ``api/``)."""
from __future__ import annotations

from typing import Any

from core.rules.spell_effects import SPELL_CLOCK_PREFIX, SPELL_STATE_PREFIX
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
        previous = next((s for s in get_states(char) if s.get("key") == spec.key and s.get("condition")), None)
        was_on = previous.get("condition_was_on", False) if previous else bool((char.conditions or {}).get(spec.condition))
        state.update(condition=spec.condition, condition_was_on=was_on)
        char.conditions = {**(char.conditions or {}), spec.condition: True}
    char.active_states = [*(s for s in get_states(char) if s.get("key") != spec.key), state]
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
    specs = [spec for spec, _row in active_features(char)]
    conscious = is_conscious(char) if any(s.needs_conscious for s in specs) else True
    return from_states | {c for spec in specs if conscious or not spec.needs_conscious for c in spec.condition_immunities}


def is_conscious(char: Any) -> bool:
    """Cosciente: vivo, con almeno 1 PF e non Privo di sensi (le aure del paladino valgono solo così). Nel 2024 le aure
    sono inattive con qualunque condizione che incapacita (Aura di Protezione), non solo a 0 PF."""
    from core.rules.catalog._common import INCAPACITATING  # import locale: il catalogo importa questo modulo
    from core.rules.edition import character_edition
    conditions = char.conditions or {}
    if getattr(char, "is_dead", False) or (char.current_hit_points or 0) <= 0 or conditions.get("unconscious"):
        return False
    return not (character_edition(char) == "2024" and any(conditions.get(c) for c in INCAPACITATING))


def casting_blocked_by(char: Any) -> bool:
    return any(s.get("blocks_casting") for s in char.active_states or [])


STOLEN_SPELL = "stolen:"  # prefisso dello `srd_index` di un incantesimo rubato (Ladro di Incantesimi); lo stato lo ricorda in `data`


def drop_stolen_spells(char: Any, closed: list[dict]) -> None:
    """Gli incantesimi rubati da uno stato appena chiuso si tolgono dalla scheda (l'eliminazione la fa la cascata sulla
    relazione). Se gli incantesimi non sono caricati si salta: la sincronizzazione del catalogo li toglie comunque."""
    tags = {(s.get("data") or {}).get("stolen_spell") for s in closed} - {None}
    orm = getattr(char, "_sa_instance_state", None)
    if not tags or (orm is not None and "spells" in orm.unloaded) or getattr(char, "spells", None) is None:
        return
    char.spells[:] = [sp for sp in char.spells if sp.srd_index not in tags]


def settle_closed(char: Any, closed: list[dict]) -> None:
    """Ciò che lasciano gli stati appena chiusi: la spossatezza dichiarata, la fine della condizione che imponevano e gli
    incantesimi che avevano portato."""
    charge_exhaustion(char, closed)
    drop_stolen_spells(char, closed)
    release_given_temp_hp(char, closed)
    drop_spell_temp_hp(char, closed)
    release_given_spells(char, closed)
    release_suspended(char, closed)
    for s in closed:  # alla fine dello stato resta ciò che dichiarava (la cura di fine illusione, Duplicato Migliorato)
        offer = (s.get("data") or {}).get("on_close")
        if offer:
            begin_state(char, StateSpec(offer["key"], ends_on=tuple(offer["ends_on"])), s["feature_key"], offer.get("name"))
    gone = {s["condition"] for s in closed if s.get("condition") and not s.get("condition_was_on")}
    gone -= {s["condition"] for s in char.active_states or [] if s.get("condition")}  # un altro stato la impone ancora
    if gone:
        char.conditions = {**(char.conditions or {}), **{c: False for c in gone}}


def release_given_temp_hp(char: Any, closed: list[dict]) -> None:
    """I PF temporanei che chi ha avviato questi stati ha consegnato ad altri svaniscono con lo stato: li segna da togliere."""
    settings = getattr(char, "settings", None) or {}
    given = dict(settings.get(TEMP_GIVEN) or {})
    gone = [entry for s in closed for entry in given.pop(s.get("key"), [])]
    if gone:
        char.settings = {**settings, TEMP_GIVEN: given, TEMP_RELEASE: [*(settings.get(TEMP_RELEASE) or []), *gone]}


def note_spell_temp_hp(char: Any, state_key: str, amount: int) -> None:
    """Lo stato ``state_key`` di ``char`` ricorda i PF temporanei che ha appena dato (l'ultimo valore vince)."""
    char.active_states = [{**s, "data": {**(s.get("data") or {}), "temp_given": amount}} if s.get("key") == state_key else s
                         for s in char.active_states or []]


def drop_spell_temp_hp(char: Any, closed: list[dict]) -> None:
    """Alla fine di un incantesimo i PF temporanei che aveva dato svaniscono, ma solo se non superano quanto diede: se ora ne ha di più
    alti da un'altra fonte restano. shortcut: un valore uguale o minore preso dopo da un'altra fonte svanisce insieme a questo."""
    given = [g for g in ((s.get("data") or {}).get("temp_given") for s in closed) if g]
    temp = getattr(char, "temp_hp", 0) or 0
    if given and 0 < temp <= max(given):
        char.temp_hp = 0
        # ricordati per l'annullo (``regrant_spells``) e per lo storico (il flush scrive la riga: qui non c'è una sessione)
        dropped = {s["key"]: {"caster_id": (s.get("data") or {}).get("caster_id"), "amount": temp, "name": s.get("name"), "logged": False}
                   for s in closed if (s.get("data") or {}).get("temp_given")}
        settings = getattr(char, "settings", None) or {}  # le voci d'altri incantesimi non ancora annullate restano
        char.settings = {**settings, SPELL_TEMP_DROPPED: {**(settings.get(SPELL_TEMP_DROPPED) or {}), **dropped}}


def forget_spell_temp_drop(char: Any, key: str | None = None) -> None:
    """La voce di ``SPELL_TEMP_DROPPED`` per lo stato ``key`` (tutte con ``None``) non serve più: un nuovo lancio, l'annullo o il riposo lungo."""
    settings = getattr(char, "settings", None) or {}
    dropped = settings.get(SPELL_TEMP_DROPPED)
    if dropped and (key is None or key in dropped):
        left = {k: v for k, v in dropped.items() if key is not None and k != key}
        char.settings = {**{k: v for k, v in settings.items() if k != SPELL_TEMP_DROPPED}, **({SPELL_TEMP_DROPPED: left} if left else {})}


def release_given_spells(char: Any, closed: list[dict]) -> None:
    """Gli effetti che chi lancia ha dato ad altri con un incantesimo finiscono con il suo orologio ``spell_cast:*``: i bersagli
    passano in ``SPELL_RELEASE``, che il flush della richiesta applica togliendo loro lo stato ``spell:*``."""
    settings = getattr(char, "settings", None) or {}
    given = dict(settings.get(SPELL_GIVEN) or {})
    gone = [{"id": t, "key": SPELL_STATE_PREFIX + s["key"][len(SPELL_CLOCK_PREFIX):]}
            for s in closed if str(s.get("key")).startswith(SPELL_CLOCK_PREFIX) for t in given.pop(s["key"], [])]
    if gone:
        char.settings = {**settings, SPELL_GIVEN: given, SPELL_RELEASE: [*(settings.get(SPELL_RELEASE) or []), *gone]}


def release_suspended(char: Any, closed: list[dict]) -> None:
    """Le condizioni sospese da chi lancia (Calmare Emozioni) tornano quando la concentrazione, da qualunque via, chiude lo stato:
    passano in ``COND_RELEASE``, che il flush della richiesta applica ai riceventi."""
    settings = getattr(char, "settings", None) or {}
    held = settings.get(SUSPENDED_KEY)
    if held and any(s.get("key") == SUSPENDED_KEY for s in closed):
        char.settings = {**{k: v for k, v in settings.items() if k != SUSPENDED_KEY}, COND_RELEASE: [*(settings.get(COND_RELEASE) or []), *held]}


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


# settings, scritti dal server. TEMP_GIVEN: {chiave dello stato: [{"id": ricevente, "amount": PF}]} dei PF temporanei consegnati che
# svaniscono con quello stato (Forza Vivificante e l'Ira); alla chiusura dello stato passano in TEMP_RELEASE, che il flush della
# richiesta (``api.services.effects``) applica ai riceventi. Gli id valgono solo in questo database.
TEMP_GIVEN, TEMP_RELEASE = "temp_hp_given", "temp_hp_release"
# PF temporanei tolti al ricevente dalla fine di un incantesimo: {chiave dello stato: {caster_id, amount, name, logged}}, per ridarli con l'annullo.
SPELL_TEMP_DROPPED = "spell_temp_dropped"
# Effetti di incantesimi dati ad altri. SPELL_GIVEN: {"spell_cast:<chiave>": [id dei bersagli]}; alla chiusura dell'orologio passano in
# SPELL_RELEASE ([{"id", "key"}]), che il flush toglie ai bersagli solo se lo stato è ancora di chi lancia (``data["caster_id"]``).
SPELL_GIVEN, SPELL_RELEASE = "spell_given", "spell_release"
# Ultimo lancio con un tipo di danno scelto: {"spell": chiave dell'effetto, "damage_type"}. Il tiro di danno legge il tipo da qui; ogni nuovo lancio lo sostituisce o lo toglie.
SPELL_CAST_TYPE = "spell_cast_type"
# Sul bersaglio: [{"caster_id", "key"}] degli stati ``spell:*`` spesi da un'opzione (Guida e Resistenza 2014: «poi l'incantesimo termina»);
# il flush chiude la concentrazione e l'orologio di chi ha lanciato.
SPELL_SPENT = "spell_spent"
# Condizioni sospese (Calmare Emozioni). Su chi lancia: stato ``SUSPENDED_KEY`` che finisce con la concentrazione e, in settings,
# ``SUSPENDED_KEY``: [{"id": ricevente, "conditions": [...]}] che alla chiusura passano in ``COND_RELEASE``. Sul ricevente
# ``SUSPENDED_ON``: {condizione: id di chi la sospende}, cancellato se la condizione cambia per altra via (allora non torna).
SUSPENDED_KEY, COND_RELEASE, SUSPENDED_ON = "suspended_conditions", "conditions_release", "conditions_suspended_on"
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

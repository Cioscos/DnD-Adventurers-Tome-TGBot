"""Togliere condizioni (Task 48): un solo meccanismo dichiarativo per privilegi (``OnUse.removal``) e incantesimi
(``SPELL_REMOVAL``). Dice cosa si può togliere, quante cose per volta, a quante creature e cosa l'app non traccia
(malattie, maledizioni...): quello diventa una nota visibile. Dati nostri, non testo dei manuali.

Il servizio che scrive sulle schede è ``api/services/condition_removal.py``; qui nessuna dipendenza da API o DB."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable

Text = dict[str, str]

# Ciò che l'app non traccia: resta una nota, mai un ripiego silenzioso.
UNTRACKED: dict[str, Text] = {
    "disease": {"it": "malattia", "en": "disease"},
    "poison": {"it": "veleno", "en": "poison"},
    "curse": {"it": "maledizione", "en": "curse"},
    "ability_reduction": {"it": "riduzione di un punteggio di caratteristica", "en": "ability score reduction"},
    "hp_max_reduction": {"it": "riduzione dei PF massimi", "en": "hit point maximum reduction"},
}

CONDITION_NAMES: dict[str, Text] = {
    "blinded": {"it": "Accecato", "en": "Blinded"}, "charmed": {"it": "Affascinato", "en": "Charmed"},
    "deafened": {"it": "Assordato", "en": "Deafened"}, "frightened": {"it": "Spaventato", "en": "Frightened"},
    "paralyzed": {"it": "Paralizzato", "en": "Paralyzed"}, "petrified": {"it": "Pietrificato", "en": "Petrified"},
    "poisoned": {"it": "Avvelenato", "en": "Poisoned"}, "stunned": {"it": "Stordito", "en": "Stunned"},
    "exhaustion": {"it": "Sfinimento (un livello)", "en": "Exhaustion (one level)"},
}


@dataclass(frozen=True)
class ConditionRemoval:
    """``conditions``: condizioni dell'app che si possono togliere; ``untracked``: chiavi di ``UNTRACKED`` che il privilegio o
    l'incantesimo toglie ma l'app non scrive. ``count``: quante cose a scelta per volta (``None``: tutte quelle ammesse).
    ``ally``: può andare a un altro PG della serata; ``max_targets``: quante creature insieme. ``suppress``: sospende senza
    chiudere (Calmare Emozioni). Solo privilegi: ``allowed(ctx)`` restringe per livello o per ciò che la scheda ha;
    ``modes``: valori di ``mode`` per cui l'uso apre il foglio (``None``: sempre); ``bound``: il bersaglio segue la ``mode``
    (``self``: te stesso, ``other``: un altro, anche per i PF); ``optional``: si può usare anche senza togliere nulla;
    ``cost_each``: usi spesi per ogni voce tolta (Imposizione delle Mani: 5); ``auto(ctx, params)``: condizioni che cadono da
    sole su chi usa il privilegio, senza foglio (Ira), con lo stesso servizio."""
    conditions: tuple[str, ...] = ()
    untracked: tuple[str, ...] = ()
    count: int | None = 1
    ally: bool = True
    max_targets: int = 1
    suppress: bool = False
    footer: Text | None = None
    allowed: "Callable[[Any], tuple[str, ...]] | None" = None
    modes: tuple[str, ...] | None = None
    bound: bool = False
    optional: bool = False
    cost_each: int = 0
    auto: "Callable[[Any, dict], list[str]] | None" = None
    quiet: bool = False  # senza scelta esplicita le voci non tracciate non fanno nota (Panacea: il testo del privilegio le dice già)

    def allowed_for(self, ctx: Any = None) -> tuple[str, ...]:
        return self.allowed(ctx) if self.allowed and ctx is not None else self.conditions


def view(removal: ConditionRemoval, ctx: Any = None) -> dict:
    """Ciò che la UI mostra nel foglio comune: lo stesso per un incantesimo e per un privilegio."""
    return {"count": removal.count, "max_targets": removal.max_targets, "ally": removal.ally, "optional": removal.optional,
            "bound": removal.bound, "modes": list(removal.modes) if removal.modes else None, "cost_each": removal.cost_each,
            "conditions": [{"key": c, "label": _name(c, CONDITION_NAMES)} for c in removal.allowed_for(ctx)],
            "untracked": [{"key": u, "label": UNTRACKED[u]} for u in removal.untracked]}


def resolve_picks(removal: ConditionRemoval, chosen: list[str] | None, allowed: tuple[str, ...]) -> tuple[list[str], list[str]]:
    """``(condizioni, voci non tracciate)`` da togliere. ``chosen`` ``None``: tutto ciò che è ammesso (solo se ``count`` è ``None``).
    ``ValueError('invalid_condition')`` per ciò che la regola non ammette, ``ValueError('invalid_choice')`` per quantità sbagliate."""
    if chosen is None:
        if removal.count is not None:
            raise ValueError("invalid_choice")
        return list(allowed), [] if removal.quiet else list(removal.untracked)
    picks = list(dict.fromkeys(chosen))
    if any(p not in allowed and p not in removal.untracked for p in picks):
        raise ValueError("invalid_condition")
    if removal.count is not None and len(picks) > removal.count:
        raise ValueError("invalid_choice")
    if removal.count is not None and not picks:
        raise ValueError("invalid_choice")
    return [p for p in picks if p in allowed], [p for p in picks if p in removal.untracked]


def _name(key: str, table: dict[str, Text]) -> Text:
    if key in table:
        return table[key]
    from core.data.labels import condition_label  # import locale: condizione personalizzata o di un effetto
    return {"it": condition_label(key), "en": key.removeprefix("custom:").replace("_", " ").title()}


def _names(keys: list[str], table: dict[str, Text], lang: str) -> str:
    return ", ".join(_name(k, table)[lang] for k in keys)


def outcome_lines(removal: ConditionRemoval, *, target: str | None, removed: list[str], absent: list[str], untracked: list[str],
                  wanted: list[str]) -> list[Text]:
    """Esiti da mostrare. ``target`` ``None``: chi lancia; ``""``: una creatura fuori dalla serata (``wanted`` tutto ciò che
    si doveva togliere, lo segna il GM)."""
    lines: list[Text] = []
    if target == "":
        every = [*(_name(c, CONDITION_NAMES) for c in wanted), *(UNTRACKED[u] for u in untracked)]
        if every:
            lines.append({lg: f"Da togliere alla creatura: {', '.join(n[lg] for n in every)}. L'app non ha la sua scheda: lo segna il GM."
                          if lg == "it" else f"To remove from the creature: {', '.join(n[lg] for n in every)}. The app has no sheet for it: the GM tracks it."
                          for lg in ("it", "en")})
    else:
        for lg_texts in ((removed, "removed"), (absent, "absent")):
            keys, kind = lg_texts
            if not keys:
                continue
            lines.append({lg: _line(kind, lg, _names(keys, CONDITION_NAMES, lg), target) for lg in ("it", "en")})
        if untracked:
            lines.append({lg: _line("untracked", lg, _names(untracked, UNTRACKED, lg), target) for lg in ("it", "en")})
    if removal.suppress and (removed or target == ""):
        lines.append({"it": "Sospeso finché dura la concentrazione: quando finisce, le condizioni tornano da sole.",
                      "en": "Suppressed while the concentration lasts: when it ends, the conditions come back on their own."})
    if removal.footer and lines:
        lines.append(removal.footer)
    return lines


def _line(kind: str, lang: str, what: str, target: str | None) -> str:
    it = lang == "it"
    who = (f" a {target}" if it else f" from {target}") if target else ""  # su sé stessi non si nomina nessuno
    if kind == "removed":
        return f"Tolto{who}: {what}." if it else f"Removed{who}: {what}."
    if kind == "absent":
        return f"{target or 'Il bersaglio'} non aveva: {what}." if it else f"{target or 'The target'} did not have: {what}."
    whom = f" per {target}" if it and target else f" for {target}" if target else ""
    return (f"{what.capitalize()}{whom}: l'app non la traccia, la toglie il tavolo." if it
            else f"{what.capitalize()}{whom}: the app does not track it, the table removes it.")


# ---------------------------------------------------------------------------
# Incantesimi che terminano o tolgono qualcosa, per edizione e ``srd_index``
# ---------------------------------------------------------------------------

_BODY = ("blinded", "deafened", "paralyzed", "poisoned")
_MANY = 12  # «qualsiasi numero di creature»: il tetto vero è la serata

SPELL_REMOVAL: dict[str, dict[str, ConditionRemoval]] = {
    "2014": {
        # una malattia o una condizione
        "lesser-restoration": ConditionRemoval(_BODY, ("disease",)),
        # un livello di Sfinimento, oppure uno fra: Affascinato, Pietrificato, maledizione, riduzioni
        "greater-restoration": ConditionRemoval(("exhaustion", "charmed", "petrified"), ("curse", "ability_reduction", "hp_max_reduction")),
        "heal": ConditionRemoval(("blinded", "deafened"), ("disease",), count=None),
        "mass-heal": ConditionRemoval(("blinded", "deafened"), ("disease",), count=None, max_targets=_MANY),
        "power-word-heal": ConditionRemoval(("charmed", "paralyzed", "frightened", "stunned"), count=None),
        "protection-from-poison": ConditionRemoval(("poisoned",), ("poison",), count=None),
        "remove-curse": ConditionRemoval((), ("curse",), count=None),
        "calm-emotions": ConditionRemoval(("charmed", "frightened"), count=None, max_targets=_MANY, suppress=True),
        "heroes-feast": ConditionRemoval(("poisoned",), ("disease",), count=None, max_targets=_MANY),
    },
    "2024": {
        "lesser-restoration": ConditionRemoval(_BODY),
        "greater-restoration": ConditionRemoval(("exhaustion", "charmed", "petrified"), ("curse", "ability_reduction", "hp_max_reduction")),
        "heal": ConditionRemoval(("blinded", "deafened", "poisoned"), count=None),
        "mass-heal": ConditionRemoval(("blinded", "deafened", "poisoned"), count=None, max_targets=_MANY),
        "power-word-heal": ConditionRemoval(("charmed", "frightened", "paralyzed", "poisoned", "stunned"), count=None),
        "protection-from-poison": ConditionRemoval(("poisoned",), count=None),
        "remove-curse": ConditionRemoval((), ("curse",), count=None),
        "calm-emotions": ConditionRemoval(("charmed", "frightened"), count=None, max_targets=_MANY, suppress=True),
    },
}


# Nomi (it e en) per riconoscere gli incantesimi inseriti a mano o importati senza ``srd_index``
_NAMES = {
    "lesser-restoration": ("Ristorare Inferiore", "Lesser Restoration"), "greater-restoration": ("Ristorare Superiore", "Greater Restoration"),
    "heal": ("Guarigione", "Heal"), "mass-heal": ("Guarigione di Massa", "Mass Heal"),
    "power-word-heal": ("Parola del Potere Guarire", "Power Word Heal"), "protection-from-poison": ("Protezione dal Veleno", "Protection from Poison"),
    "remove-curse": ("Rimuovi Maledizione", "Remove Curse"), "calm-emotions": ("Calmare Emozioni", "Calm Emotions"),
    "heroes-feast": ("Banchetto degli Eroi", "Heroes' Feast"),
}


def _norm(name: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower())


_BY_NAME = {_norm(n): idx for idx, names in _NAMES.items() for n in names}
_RESTORE_HINT = re.compile(r"ristor|restor")
NOT_RECOGNIZED: Text = {
    "it": "Questo incantesimo sembra togliere condizioni ma l'app non lo riconosce: toglile a mano dalla scheda.",
    "en": "This spell looks like it removes conditions but the app does not recognize it: remove them by hand on the sheet.",
}


def spell_removal(edition: str, srd_index: str | None, name: str | None = None) -> ConditionRemoval | None:
    """Per ``srd_index`` e, in mancanza, per nome (it o en, normalizzato)."""
    rules = SPELL_REMOVAL.get(edition, {})
    return rules.get(srd_index or "") or rules.get(_BY_NAME.get(_norm(name), ""))


def looks_like_removal(name: str | None) -> bool:
    return bool(_RESTORE_HINT.search(_norm(name)))

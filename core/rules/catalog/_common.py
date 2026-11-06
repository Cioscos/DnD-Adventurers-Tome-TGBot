"""Predicati e costruttori comuni ai cataloghi di classe (foglia: nessun import da ``core.rules.modifiers``)."""
from __future__ import annotations

from typing import Any

from core.data.labels import SKILL_LABELS_IT
from core.rules.states import has_state
from core.rules.types import FeatureSpec, RuleContext
from core.utils.session_view import armor_category

INCAPACITATING = ("incapacitated", "paralyzed", "petrified", "stunned", "unconscious")


def heavy_armor(char: Any) -> bool:
    return armor_category(char) == "heavy"


def state_on(ctx: RuleContext, key: str) -> bool:
    return has_state(ctx.char, key)


def cannot_perceive_or_act(char: Any) -> bool:
    """Accecato, assordato o incapacitato (Percezione del Pericolo non funziona)."""
    conditions = char.conditions or {}
    return any(conditions.get(c) for c in ("blinded", "deafened", *INCAPACITATING))


def save_spell(spell: Any) -> bool:
    """L'incantesimo fa fare un TS al bersaglio (non un tiro per colpire e non senza tiri)."""
    return (spell.attack_save or "").strip().upper() not in ("", "ATK")


def once_used(char: Any, key: str) -> bool:
    return key in ((getattr(char, "turn_state", None) or {}).get("once_per_turn") or [])


def attacks_made(ctx: RuleContext) -> int:
    return int((ctx.turn or {}).get("attacks_made") or 0)


FIGHTING_STYLE_GROUP = "fighting_style"


def style_options(styles: Any) -> Any:
    """Le opzioni di una scelta di stile di combattimento: ``styles`` meno quelli che un'altra classe del personaggio ha già.
    Il manuale vieta di prendere due volte lo stesso stile anche quando una seconda classe dà il diritto di sceglierne uno
    (vale per ogni classe con lo stile: Guerriero, Paladino e le future). Gli stili della stessa classe li esclude già la scelta."""
    def options(ctx: RuleContext) -> list[str]:
        mine = getattr(ctx.class_row, "id", None)
        taken = {k for row in ctx.char.classes if row.id != mine for k in (row.options or {}).get(FIGHTING_STYLE_GROUP, [])}
        return [s for s in styles if s not in taken]
    return options


def skill_label(slug: str) -> dict:
    """Etichetta bilingue di un'abilità per le opzioni di una `ChoiceSpec` (Maestria, competenze a scelta)."""
    english = slug.replace("_", " ").title().replace(" Of ", " of ")
    return {"name": {"it": SKILL_LABELS_IT.get(slug, english), "en": english}, "summary": {"it": "", "en": ""}}


def feature(key: str, class_key: str, edition: str, level: int, title: str, name: tuple[str, str],
            summary: tuple[str, str], action_type: str | None = None, **kw: Any) -> FeatureSpec:
    """Scorciatoia per le righe del catalogo: ``name`` e ``summary`` sono coppie (it, en)."""
    kw.setdefault("passive", action_type is None and kw.get("on_use") is None)
    return FeatureSpec(
        key=f"{class_key}.{key}", class_key=class_key, edition=edition, level=level, source_title=title,
        name={"it": name[0], "en": name[1]}, summary={"it": summary[0], "en": summary[1]},
        action_type=action_type, **kw)

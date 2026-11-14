"""Predicati e costruttori comuni ai cataloghi di classe (foglia: nessun import da ``core.rules.modifiers``)."""
from __future__ import annotations

from typing import Any

from core.data.labels import SKILL_LABELS_IT
from core.rules.states import has_state
from core.rules.types import ChoiceSpec, FeatureSpec, RuleContext
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


def unarmored_unshielded(char: Any) -> bool:
    """Né armatura né Scudo indossati (Collegio della Danza)."""
    from core.game.stats import _worn  # import locale: stats usa il catalogo
    return _worn(char, "armor") is None and _worn(char, "shield") is None


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
        taken = styles_taken(ctx.char, but=getattr(ctx.class_row, "id", None))
        return [s for s in styles if s not in taken]
    return options


STYLE_FEAT_PREFIX = "feat.2024_fs_"


def styles_taken(char: Any, but: Any = None) -> set[str]:
    """Stili di combattimento già presi: dalle classi (tranne la riga ``but``) e come talento (``feat.2024_fs_<stile>``)."""
    rows = {k for row in char.classes if row.id != but for k in (row.options or {}).get(FIGHTING_STYLE_GROUP, [])}
    feats = {a.feature_key[len(STYLE_FEAT_PREFIX):] for a in _loaded_abilities(char)
             if (a.feature_key or "").startswith(STYLE_FEAT_PREFIX)}
    return rows | feats


def _loaded_abilities(char: Any) -> list:
    from core.rules.catalog.feats import _abilities  # import locale: il registro dei talenti importa questo modulo
    return _abilities(char)


def has_fighting_style(char: Any) -> bool:
    """Il personaggio ha il privilegio Stile di Combattimento (una scelta del gruppo ``fighting_style`` attiva)."""
    from core.rules.catalog import active_features
    return any(c.group == FIGHTING_STYLE_GROUP for spec, _row in active_features(char) for c in spec.choices)


def skill_label(slug: str) -> dict:
    """Etichetta bilingue di un'abilità per le opzioni di una `ChoiceSpec` (Maestria, competenze a scelta)."""
    english = slug.replace("_", " ").title().replace(" Of ", " of ")
    return {"name": {"it": SKILL_LABELS_IT.get(slug, english), "en": english}, "summary": {"it": "", "en": ""}}


TOOL_PREFIX = "tool:"  # le opzioni di classe che sono strumenti: ``tool:<chiave del catalogo>``
_TOOL_CATEGORY = {
    "artisan": ("Strumento da artigiano", "Artisan's tools"), "gaming": ("Gioco", "Gaming set"),
    "instrument": ("Strumento musicale", "Musical instrument"), "kit": ("Kit", "Kit"),
    "thieves": ("Arnesi da scasso", "Thieves' tools"), "vehicle": ("Veicolo", "Vehicle"),
}


def tool_choice_label(key: str) -> dict:
    """Etichetta di un'opzione che può essere uno strumento (``tool:<chiave>``: nome e categoria) o un'abilità."""
    from core.data.tools import TOOLS  # import locale: il modulo resta una foglia
    if not key.startswith(TOOL_PREFIX):
        return skill_label(key)
    tool = TOOLS[key[len(TOOL_PREFIX):]]
    it, en = _TOOL_CATEGORY[tool.category]
    return {"name": {"it": tool.it, "en": tool.en}, "summary": {"it": it, "en": en}}


def tool_option_keys(ctx: RuleContext, categories: tuple[str, ...]) -> list[str]:
    """Strumenti delle categorie in cui il personaggio non è ancora competente."""
    from core.data.tools import TOOLS
    have = getattr(ctx.char, "tool_proficiencies", None) or {}
    return [f"{TOOL_PREFIX}{k}" for k, t in TOOLS.items() if t.category in categories and not have.get(k)]


def owned_tool_keys(ctx: RuleContext, categories: tuple[str, ...]) -> list[str]:
    """Strumenti delle categorie già sulla scheda (R39: si dichiarano «già sulla scheda»)."""
    from core.data.tools import TOOLS
    have = getattr(ctx.char, "tool_proficiencies", None) or {}
    return [f"{TOOL_PREFIX}{k}" for k, t in TOOLS.items() if t.category in categories and have.get(k)]


def tool_choice(group: str, levels: dict[int, int], categories: tuple[str, ...], applies=None) -> ChoiceSpec:
    """Scelta di strumenti del catalogo (``tool:<chiave>``) che diventano competenze nella colonna."""
    return ChoiceSpec(group=group, levels=levels, options=lambda ctx: tool_option_keys(ctx, categories),
                      label=tool_choice_label, grants="proficient", owned=lambda ctx: owned_tool_keys(ctx, categories),
                      applies=applies)


def first_class(ctx: RuleContext) -> bool:
    """La classe è quella di partenza: la riga con l'id più basso (una riga non ancora salvata viene dopo le altre)."""
    rows = list(getattr(ctx.char, "classes", None) or [])
    first = min(rows, key=lambda c: (c.id is None, c.id or 0), default=None)
    return first is None or first is ctx.class_row


def feature(key: str, class_key: str, edition: str, level: int, title: str, name: tuple[str, str],
            summary: tuple[str, str], action_type: str | None = None, **kw: Any) -> FeatureSpec:
    """Scorciatoia per le righe del catalogo: ``name`` e ``summary`` sono coppie (it, en)."""
    kw.setdefault("passive", action_type is None and kw.get("on_use") is None)
    return FeatureSpec(
        key=f"{class_key}.{key}", class_key=class_key, edition=edition, level=level, source_title=title,
        name={"it": name[0], "en": name[1]}, summary={"it": summary[0], "en": summary[1]},
        action_type=action_type, **kw)

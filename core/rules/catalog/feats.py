"""Effetti dei talenti nel motore delle regole di classe.

Un talento preso è una riga ``Ability`` con ``feature_key = "feat.<chiave>"`` (chiave di ``core.data.feats*``). Qui ogni
talento ha una ``FeatureSpec`` con la stessa chiave: ``active_features`` la restituisce insieme a un ``FeatSource``, che
fa le veci della riga di classe (livello = livello totale, ``id`` nullo come ``source_class_id`` delle righe dei talenti).
``FeatSpec`` resta la scheda di selezione (prerequisiti, +1 alla caratteristica, ripetibilità).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from core.rules.edition import character_edition
from core.rules.types import Edition, FeatureSpec

FEAT_FEATURES: dict[str, FeatureSpec] = {}
# Chiavi di ``Ability.options`` senza le quali il talento non agisce («da completare»)
FEAT_NEEDS: dict[str, tuple[str, ...]] = {}

FeatStatus = Literal["active", "incomplete", "other_edition"]


def feat(key: str, edition: Edition, it: str, en: str, sit: str, sen: str, **kw: Any) -> FeatureSpec:
    """Voce del registro: ``key`` è la chiave del talento (``2024_alert``), la spec ha chiave ``feat.<key>``."""
    kw.setdefault("passive", kw.get("on_use") is None)
    return FeatureSpec(key=f"feat.{key}", class_key="feat", edition=edition, level=1, source_title=f"{it} / {en} (talento)",
                       name={"it": it, "en": en}, summary={"it": sit, "en": sen}, action_type=kw.pop("action_type", None), **kw)


def _register(*specs: FeatureSpec, needs: dict[str, tuple[str, ...]] | None = None) -> None:
    for spec in specs:
        FEAT_FEATURES[spec.key] = spec
    FEAT_NEEDS.update(needs or {})


@dataclass(frozen=True)
class FeatSource:
    """Al posto della riga di classe per i privilegi dei talenti."""
    ability: Any
    level: int

    @property
    def id(self) -> None:
        return None

    @property
    def class_name(self) -> str:
        return "feat"

    @property
    def subclass_key(self) -> None:
        return None

    @property
    def options(self) -> dict:
        return getattr(self.ability, "options", None) or {}


def _abilities(char: Any) -> list:
    """Le righe del personaggio, se caricate: un ORM non caricato non deve scatenare un lazy load asincrono."""
    try:
        from sqlalchemy import inspect as sa_inspect
        state = sa_inspect(char, raiseerr=False)
    except ImportError:  # pragma: no cover
        state = None
    if state is not None and "abilities" in state.unloaded:
        return []
    return list(getattr(char, "abilities", None) or [])


def feat_status(char: Any, ability: Any) -> FeatStatus | None:
    spec = FEAT_FEATURES.get(getattr(ability, "feature_key", None) or "")
    if spec is None:
        return None
    if spec.edition != character_edition(char):
        return "other_edition"
    opts = getattr(ability, "options", None) or {}
    if any(not opts.get(k) for k in FEAT_NEEDS.get(spec.key, ())):
        return "incomplete"
    return "active"


def owned_feats(char: Any) -> list[tuple[FeatureSpec, FeatSource]]:
    level = max(1, sum(getattr(c, "level", 0) or 0 for c in getattr(char, "classes", None) or []))
    return [(FEAT_FEATURES[a.feature_key], FeatSource(a, level)) for a in _abilities(char)
            if feat_status(char, a) == "active"]

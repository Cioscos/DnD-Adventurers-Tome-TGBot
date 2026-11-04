"""Registro dei privilegi di classe per edizione; i Task 19-42 lo riempiono."""
from __future__ import annotations

from typing import Any

from core.rules.edition import character_edition, class_key
from core.rules.types import FeatureSpec

_REGISTRY: dict[tuple[str, str], tuple[FeatureSpec, ...]] = {}


def features_for(edition: str, key: str | None) -> tuple[FeatureSpec, ...]:
    return _REGISTRY.get((edition, key), ())


def _applies(spec: FeatureSpec, row: Any) -> bool:
    if spec.level > row.level:
        return False
    if spec.subclass is not None and spec.subclass != row.subclass_key:
        return False
    if spec.option_group is not None:
        # la colonna `options` nasce al Task 5: fino ad allora nessuna opzione è scelta
        chosen = (getattr(row, "options", None) or {}).get(spec.option_group, [])
        return spec.option_key in chosen
    return True


def active_features(char: Any) -> list[tuple[FeatureSpec, Any]]:
    """Privilegi attivi di tutte le classi: filtro su livello di classe, `subclass_key` e opzioni scelte."""
    edition = character_edition(char)
    return [(spec, row) for row in char.classes
            for spec in features_for(edition, class_key(row)) if _applies(spec, row)]

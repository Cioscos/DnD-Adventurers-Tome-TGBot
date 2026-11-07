"""Registro dei privilegi di classe per edizione; i Task 19-42 lo riempiono."""
from __future__ import annotations

from typing import Any

from core.rules.edition import character_edition, class_key
from core.rules.types import FeatureSpec

# Aumenta ogni task che aggiunge o cambia un catalogo di classe (R33): all'avvio dell'API, se la versione salvata in
# `app_meta` è diversa, i personaggi esistenti passano una volta dal sync (`api/services/catalog_migration.py`).
CATALOG_VERSION = 51

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


def _register() -> None:
    """Carica i cataloghi di classe a mano a mano che i Task 19-42 li scrivono."""
    from core.rules.catalog.y2014 import barbarian as barbarian_2014
    from core.rules.catalog.y2014 import bard as bard_2014
    from core.rules.catalog.y2014 import cleric as cleric_2014
    from core.rules.catalog.y2014 import druid as druid_2014
    from core.rules.catalog.y2014 import fighter as fighter_2014
    from core.rules.catalog.y2014 import monk as monk_2014
    from core.rules.catalog.y2014 import paladin as paladin_2014
    from core.rules.catalog.y2014 import ranger as ranger_2014
    from core.rules.catalog.y2014 import rogue as rogue_2014
    from core.rules.catalog.y2014 import sorcerer as sorcerer_2014
    from core.rules.catalog.y2014 import warlock as warlock_2014
    from core.rules.catalog.y2014 import wizard as wizard_2014
    from core.rules.catalog.y2024 import barbarian as barbarian_2024
    from core.rules.catalog.y2024 import bard as bard_2024
    from core.rules.catalog.y2024 import cleric as cleric_2024
    from core.rules.catalog.y2024 import druid as druid_2024

    for module in (barbarian_2014, bard_2014, cleric_2014, druid_2014, fighter_2014, monk_2014, paladin_2014, ranger_2014, rogue_2014, sorcerer_2014, warlock_2014, wizard_2014, barbarian_2024, bard_2024, cleric_2024, druid_2024):
        for spec in module.FEATURES:
            _REGISTRY[(spec.edition, spec.class_key)] = _REGISTRY.get((spec.edition, spec.class_key), ()) + (spec,)


_register()

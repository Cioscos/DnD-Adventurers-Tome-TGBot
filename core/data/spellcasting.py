"""D&D 5e (2014) — regole di preparazione incantesimi e Ritual Casting.

Complementare a ``core.data.spell_slots`` (stessa normalizzazione dei nomi
classe IT/EN). Qui vivono solo regole pure, senza DB né settings: l'override
manuale del tetto è applicato a livello servizio
(``api.services.spellcasting``).

Tetto aggregato multiclasse: la somma dei contributi delle classi preparanti
(approssimazione documentata in spec — nessun vincolo per-classe).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from core.data.spell_slots import normalize_class_name

if TYPE_CHECKING:
    from core.db.models import CharacterClass

# Classi che PREPARANO: chiave canonica -> (caratteristica default, progressione piena).
# Progressione piena -> mod + livello; metà (Paladino) -> mod + livello // 2,
# e solo dal livello 2 (al 1° il Paladino non ha ancora Spellcasting).
PREPARING_CLASSES: dict[str, tuple[str, bool]] = {
    "cleric": ("wisdom", True),
    "druid": ("wisdom", True),
    "wizard": ("intelligence", True),
    "paladin": ("charisma", False),
}

# Classi con il privilegio Ritual Casting (PHB 2014). Il Mago può inoltre
# ritualare dal libro anche incantesimi non preparati (has_wizard).
RITUAL_CASTER_KEYS: frozenset[str] = frozenset({"bard", "cleric", "druid", "wizard"})

_WIZARD_KEY = "wizard"


def _prep_entry(cls: "CharacterClass") -> tuple[str, bool] | None:
    """(caratteristica, progressione_piena) se la classe prepara, altrimenti None."""
    key = normalize_class_name(cls.class_name)
    if key is None or key not in PREPARING_CLASSES:
        return None
    default_ability, full = PREPARING_CLASSES[key]
    if not full and cls.level < 2:
        return None
    return (cls.spellcasting_ability or default_ability, full)


def has_preparing_class(classes: Iterable["CharacterClass"]) -> bool:
    return any(_prep_entry(c) is not None for c in classes)


def compute_prepared_cap(
    classes: Iterable["CharacterClass"], modifiers: dict[str, int]
) -> int | None:
    """Tetto aggregato di preparazione; ``None`` se nessuna classe prepara.

    ``modifiers`` mappa il nome caratteristica (inglese lowercase) al
    modificatore; una caratteristica assente vale 0 (punteggio 10).
    """
    total: int | None = None
    for cls in classes:
        entry = _prep_entry(cls)
        if entry is None:
            continue
        ability, full = entry
        mod = modifiers.get(ability, 0)
        contribution = mod + (cls.level if full else cls.level // 2)
        total = (total or 0) + max(1, contribution)
    return total


def has_ritual_caster(classes: Iterable["CharacterClass"]) -> bool:
    return any(normalize_class_name(c.class_name) in RITUAL_CASTER_KEYS for c in classes)


def has_wizard(classes: Iterable["CharacterClass"]) -> bool:
    return any(normalize_class_name(c.class_name) == _WIZARD_KEY for c in classes)

"""Canonical Italian labels for D&D 5e slugs (skills, conditions, abilities).

Used by the API to localize server-generated, IT-only strings (notably the
character history log) so they never expose raw English slugs like
``athletics`` or ``poisoned``. These mirror the bot's i18n labels
(``bot/locales/it.yaml``) but live in ``core/`` because the API must not import
from the bot package. Default project language is Italian.

Unknown slugs fall back to a title-cased version of the slug so the output is
always human-readable, never blank.
"""

from __future__ import annotations

# Skill slug → Italian label (18 standard D&D 5e skills)
SKILL_LABELS_IT: dict[str, str] = {
    "acrobatics":      "Acrobazie",
    "animal_handling": "Gestione Animali",
    "arcana":          "Arcana",
    "athletics":       "Atletica",
    "deception":       "Inganno",
    "history":         "Storia",
    "insight":         "Intuizione",
    "intimidation":    "Intimidazione",
    "investigation":   "Indagare",
    "medicine":        "Medicina",
    "nature":          "Natura",
    "perception":      "Percezione",
    "performance":     "Intrattenere",
    "persuasion":      "Persuasione",
    "religion":        "Religione",
    "sleight_of_hand": "Rapidità di Mano",
    "stealth":         "Furtività",
    "survival":        "Sopravvivenza",
}

# Condition slug → Italian label (standard 5e conditions + exhaustion)
CONDITION_LABELS_IT: dict[str, str] = {
    "blinded":       "Accecato",
    "charmed":       "Affascinato",
    "deafened":      "Assordato",
    "frightened":    "Spaventato",
    "grappled":      "Afferrato",
    "incapacitated": "Incapacitato",
    "invisible":     "Invisibile",
    "paralyzed":     "Paralizzato",
    "petrified":     "Pietrificato",
    "poisoned":      "Avvelenato",
    "prone":         "A Terra",
    "restrained":    "Trattenuto",
    "stunned":       "Stordito",
    "unconscious":   "Privo di Sensi",
    "exhaustion":    "Esaurimento",
}

# Ability slug → full Italian name
ABILITY_LABELS_IT: dict[str, str] = {
    "strength":     "Forza",
    "dexterity":    "Destrezza",
    "constitution": "Costituzione",
    "intelligence": "Intelligenza",
    "wisdom":       "Saggezza",
    "charisma":     "Carisma",
}


def _fallback(slug: str) -> str:
    """Human-readable fallback for an unknown slug (e.g. 'sleight_of_hand')."""
    return slug.replace("_", " ").title()


def skill_label(slug: str) -> str:
    """Italian label for a skill slug, with a title-cased fallback."""
    return SKILL_LABELS_IT.get(slug, _fallback(slug))


def condition_label(slug: str) -> str:
    """Italian label for a condition slug, with a title-cased fallback."""
    return CONDITION_LABELS_IT.get(slug, _fallback(slug))


def ability_label(slug: str) -> str:
    """Full Italian name for an ability slug, with a title-cased fallback."""
    return ABILITY_LABELS_IT.get(slug, _fallback(slug))

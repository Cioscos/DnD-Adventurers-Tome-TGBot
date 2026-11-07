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


# Condizioni ``custom:<slug>`` che il catalogo dei privilegi imposta su altri (un'etichetta con durata, non una regola)
CUSTOM_CONDITION_LABELS: dict[str, dict[str, str]] = {
    "turned": {"it": "Scacciato", "en": "Turned"},
    "thoughts_read": {"it": "Pensieri letti", "en": "Thoughts read"},
    "nature_ward": {"it": "Dissuaso", "en": "Warded off"},
    "goaded": {"it": "Adescato", "en": "Goaded"},
    "protection": {"it": "Attacco ostacolato", "en": "Attack hindered"},
    "eldritch_strike": {"it": "Colpo Mistico", "en": "Eldritch Strike"},
    "magical_ambush": {"it": "Imboscata Magica", "en": "Magical Ambush"},
    "heightened_spell": {"it": "Incantesimo Intensificato", "en": "Heightened Spell"},
    "no_reactions": {"it": "Senza reazioni", "en": "No reactions"},
    "no_opportunity_attacks": {"it": "Niente attacchi di opportunità", "en": "No opportunity attacks"},
    "hurled": {"it": "Nei piani inferiori", "en": "Hurled through Hell"},
    "entropic_ward": {"it": "Attacco in svantaggio", "en": "Attack at disadvantage"},
    "instinctive_charm": {"it": "Attacco deviato", "en": "Attack redirected"},
    "altered_memory": {"it": "Ricordi alterati", "en": "Altered memory"},
    "commanded_undead": {"it": "Non morto comandato", "en": "Commanded undead"},
    "hamstring": {"it": "Colpo alle Gambe", "en": "Hamstrung"},
    "staggered": {"it": "Colpo Stordente", "en": "Staggered"},
    "sundered": {"it": "Colpo Spezzante", "en": "Sundered"},
}


def _fallback(slug: str) -> str:
    """Human-readable fallback for an unknown slug (e.g. 'sleight_of_hand')."""
    return slug.replace("_", " ").title()


def skill_label(slug: str) -> str:
    """Italian label for a skill slug, with a title-cased fallback."""
    return SKILL_LABELS_IT.get(slug, _fallback(slug))


def condition_label(slug: str) -> str:
    """Italian label for a condition slug, with a title-cased fallback.

    Homebrew conditions are keyed ``custom:<name>``: the prefix is internal and
    must not leak into user-facing text (history showed "Custom:Sanguinamento").
    """
    custom = CUSTOM_CONDITION_LABELS.get(slug.removeprefix("custom:")) if slug.startswith("custom:") else None
    return CONDITION_LABELS_IT.get(slug) or (custom["it"] if custom else _fallback(slug.removeprefix("custom:")))


def ability_label(slug: str) -> str:
    """Full Italian name for an ability slug, with a title-cased fallback."""
    return ABILITY_LABELS_IT.get(slug, _fallback(slug))

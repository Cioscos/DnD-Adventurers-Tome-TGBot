"""D&D 5e class configuration: predefined class list and class-specific resource formulas.

This module provides:
- DND_CLASSES: list of Italian-named D&D 5e classes for guided selection
- ResourceConfig: dataclass describing a class resource with a level-scaling formula
- CLASS_RESOURCES: dict mapping class name to its list of ResourceConfig
- get_class_feature_specs(): build class-feature spec dicts for a given class/level/character
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.db.models import Character

from core.db.models import RestorationType

# ---------------------------------------------------------------------------
# Predefined D&D 5e classes (Italian names)
# ---------------------------------------------------------------------------

DND_CLASSES: list[str] = [
    "Barbaro",
    "Bardo",
    "Chierico",
    "Druido",
    "Guerriero",
    "Ladro",
    "Mago",
    "Monaco",
    "Paladino",
    "Ranger",
    "Stregone",
    "Warlock",
]

# Spellcasting ability per class (None = non-caster / depends on subclass)
CLASS_SPELLCASTING: dict[str, str | None] = {
    "Barbaro":   None,
    "Bardo":     "charisma",
    "Chierico":  "wisdom",
    "Druido":    "wisdom",
    "Guerriero": None,        # Eldritch Knight uses INT, but depends on subclass
    "Ladro":     None,        # Arcane Trickster uses INT, but depends on subclass
    "Mago":      "intelligence",
    "Monaco":    None,
    "Paladino":  "charisma",
    "Ranger":    "wisdom",
    "Stregone":  "charisma",
    "Warlock":   "charisma",
}

# Saving throw proficiencies granted by the *starting* class (D&D 5e PHB).
# Each class grants proficiency in exactly two ability saving throws. These are
# seeded ONLY by the first (starting) class at character creation; multiclassing
# does NOT grant additional saving throw proficiencies (PHB multiclass rules).
# Ability slugs match core.db.models.ABILITY_NAMES (full English lowercase).
CLASS_SAVING_THROWS: dict[str, tuple[str, str]] = {
    "Barbaro":   ("strength", "constitution"),
    "Bardo":     ("dexterity", "charisma"),
    "Chierico":  ("wisdom", "charisma"),
    "Druido":    ("intelligence", "wisdom"),
    "Guerriero": ("strength", "constitution"),
    "Ladro":     ("dexterity", "intelligence"),
    "Mago":      ("intelligence", "wisdom"),
    "Monaco":    ("strength", "dexterity"),
    "Paladino":  ("wisdom", "charisma"),
    "Ranger":    ("strength", "dexterity"),
    "Stregone":  ("constitution", "charisma"),
    "Warlock":   ("wisdom", "charisma"),
}

# Hit die per class
CLASS_HIT_DIE: dict[str, int] = {
    "Barbaro":   12,
    "Bardo":     8,
    "Chierico":  8,
    "Druido":    8,
    "Guerriero": 10,
    "Ladro":     8,
    "Mago":      6,
    "Monaco":    8,
    "Paladino":  10,
    "Ranger":    10,
    "Stregone":  6,
    "Warlock":   8,
}


# ---------------------------------------------------------------------------
# ResourceConfig dataclass
# ---------------------------------------------------------------------------

@dataclass
class ResourceConfig:
    """Descrive una feature di classe con formula a livello.

    Attributes:
        key: Identificatore stabile di catalogo (es. "monk.ki"). Usato dal
            re-sync al level-up per ritrovare l'Ability corrispondente.
        name: Nome visualizzato (italiano).
        formula: Callable (level:int)->int che ritorna il max usi a quel livello.
            Ritorna 0 quando la feature non è ancora disponibile.
        restoration_type: Quando la feature si ricarica.
        description: Descrizione regolistica bilingue, chiavi "it"/"en".
        note: Nota opzionale legacy (mantenuta per compatibilità; non più usata).
        cha_based: Se True il max = modificatore di Carisma (formula ignorata).
    """
    key: str
    name: str
    formula: Callable[[int], int]
    restoration_type: RestorationType
    description: dict[str, str]
    note: Optional[str] = None
    cha_based: bool = False


# ---------------------------------------------------------------------------
# Per-class resource configurations
# ---------------------------------------------------------------------------

# Level-indexed lookup tables (index = level - 1)
_BARBARO_FURIE = [2, 2, 3, 3, 3, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 5, 6, 6, 6, 99]
_CHIERICO_CD   = [0, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3]
_GUERRIERO_AS  = [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 3]
_GUERRIERO_IN  = [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3]
_GUERRIERO_DS  = [0, 0, 4, 4, 4, 4, 5, 5, 5, 5, 5, 5, 5, 5, 6, 6, 6, 6, 6, 6]
_PALADINO_CD   = [0, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2]
_WARLOCK_PATTO = [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4]


def _lookup(table: list[int], level: int) -> int:
    idx = max(0, min(level - 1, len(table) - 1))
    return table[idx]


CLASS_RESOURCES: dict[str, list[ResourceConfig]] = {
    "Barbaro": [
        ResourceConfig(
            key="barbarian.rage",
            name="Furia",
            formula=lambda lv: _lookup(_BARBARO_FURIE, lv),
            restoration_type=RestorationType.LONG_REST,
            description={
                "it": "Come azione bonus entri in Furia: vantaggio alle prove e ai TS di Forza, bonus ai danni con armi da mischia basate sulla Forza e resistenza a danni contundenti, perforanti e taglienti. Dura 1 minuto.",
                "en": "As a bonus action you enter a Rage: advantage on Strength checks and saves, bonus damage on Strength-based melee weapon attacks, and resistance to bludgeoning, piercing and slashing damage. Lasts 1 minute.",
            },
        ),
    ],
    "Bardo": [
        ResourceConfig(
            key="bard.bardic_inspiration",
            name="Ispirazione Bardica",
            formula=lambda lv: lv,  # ignorata: cha_based=True
            restoration_type=RestorationType.SHORT_REST,
            cha_based=True,
            description={
                "it": "Come azione bonus concedi a una creatura un dado Ispirazione Bardica; entro 10 minuti può aggiungerlo a una prova di caratteristica, tiro per colpire o tiro salvezza.",
                "en": "As a bonus action, grant a creature a Bardic Inspiration die; within 10 minutes they can add it to one ability check, attack roll, or saving throw.",
            },
        ),
    ],
    "Chierico": [
        ResourceConfig(
            key="cleric.channel_divinity",
            name="Incanalare la Divinità",
            formula=lambda lv: _lookup(_CHIERICO_CD, lv),
            restoration_type=RestorationType.SHORT_REST,
            description={
                "it": "Incanali l'energia divina per alimentare effetti magici, come Scacciare Non Morti, oltre alle opzioni concesse dal tuo dominio divino.",
                "en": "You channel divine energy to fuel magical effects such as Turn Undead, plus the options granted by your divine domain.",
            },
        ),
    ],
    "Druido": [
        ResourceConfig(
            key="druid.wild_shape",
            name="Forma Selvatica",
            formula=lambda lv: 2 if lv >= 2 else 0,
            restoration_type=RestorationType.SHORT_REST,
            description={
                "it": "Come azione puoi trasformarti magicamente in una bestia che hai già visto, entro i limiti di grado di sfida e capacità di movimento previsti dal tuo livello.",
                "en": "As an action you can magically assume the shape of a beast you have seen before, within the challenge-rating and movement limits set by your level.",
            },
        ),
    ],
    "Guerriero": [
        ResourceConfig(
            key="fighter.superiority_dice",
            name="Dadi Superiorità",
            formula=lambda lv: _lookup(_GUERRIERO_DS, lv),
            restoration_type=RestorationType.SHORT_REST,
            note="⚠️ I Dadi Superiorità sono inclusi per semplicità. Sono disponibili solo per il Battle Master.",
            description={
                "it": "Riserva di dadi che alimenta le manovre da combattimento del Maestro di Guerra. ⚠️ Inclusi per semplicità: disponibili solo per la sottoclasse Battle Master.",
                "en": "A pool of dice that powers the Battle Master's combat maneuvers. ⚠️ Included for convenience: only available to the Battle Master subclass.",
            },
        ),
        ResourceConfig(
            key="fighter.action_surge",
            name="Azione Impetuosa",
            formula=lambda lv: _lookup(_GUERRIERO_AS, lv),
            restoration_type=RestorationType.SHORT_REST,
            description={
                "it": "Nel tuo turno puoi compiere un'azione aggiuntiva oltre a quella normale (e all'eventuale azione bonus).",
                "en": "On your turn you can take one additional action on top of your regular action (and any bonus action).",
            },
        ),
        ResourceConfig(
            key="fighter.second_wind",
            name="Secondo Vento",
            formula=lambda lv: 1,
            restoration_type=RestorationType.SHORT_REST,
            description={
                "it": "Come azione bonus recuperi punti ferita pari a 1d10 + il tuo livello da guerriero.",
                "en": "As a bonus action you regain hit points equal to 1d10 + your fighter level.",
            },
        ),
        ResourceConfig(
            key="fighter.indomitable",
            name="Indomabile",
            formula=lambda lv: _lookup(_GUERRIERO_IN, lv),
            restoration_type=RestorationType.LONG_REST,
            description={
                "it": "Puoi ripetere un tiro salvezza che hai appena fallito; devi usare il nuovo risultato.",
                "en": "You can reroll a saving throw you just failed; you must use the new roll.",
            },
        ),
    ],
    "Monaco": [
        ResourceConfig(
            key="monk.ki",
            name="Punti Ki",
            formula=lambda lv: lv if lv >= 2 else 0,
            restoration_type=RestorationType.SHORT_REST,
            description={
                "it": "Energia mistica che alimenta le tue tecniche da monaco: Raffica di Colpi, Difesa Attenta, Passo del Vento e altre capacità.",
                "en": "Mystical energy that fuels your monk techniques: Flurry of Blows, Patient Defense, Step of the Wind, and other features.",
            },
        ),
    ],
    "Paladino": [
        ResourceConfig(
            key="paladin.lay_on_hands",
            name="Imposizione delle Mani",
            formula=lambda lv: 5 * lv,
            restoration_type=RestorationType.LONG_REST,
            note="Pool di PF curabili (non usi singoli).",
            description={
                "it": "Riserva di punti cura pari a 5 × il tuo livello da paladino. Con un'azione puoi toccare una creatura e spendere punti per curarla, o spenderne 5 per neutralizzare una malattia o un veleno.",
                "en": "A pool of healing points equal to 5 × your paladin level. As an action you can touch a creature and spend points to heal it, or spend 5 to cure a disease or neutralize a poison.",
            },
        ),
        ResourceConfig(
            key="paladin.channel_divinity",
            name="Incanalare la Divinità",
            formula=lambda lv: _lookup(_PALADINO_CD, lv),
            restoration_type=RestorationType.SHORT_REST,
            description={
                "it": "Incanali energia divina per alimentare gli effetti concessi dal tuo Giuramento Sacro.",
                "en": "You channel divine energy to fuel the effects granted by your Sacred Oath.",
            },
        ),
    ],
    "Stregone": [
        ResourceConfig(
            key="sorcerer.sorcery_points",
            name="Punti Stregoneria",
            formula=lambda lv: lv if lv >= 2 else 0,
            restoration_type=RestorationType.LONG_REST,
            description={
                "it": "Carburante della Metamagia: puoi convertire punti in slot incantesimo (e viceversa) e applicare effetti metamagici ai tuoi incantesimi.",
                "en": "Fuel for Metamagic: you can convert points into spell slots (and vice versa) and apply metamagic effects to your spells.",
            },
        ),
    ],
    "Warlock": [
        ResourceConfig(
            key="warlock.pact_slots",
            name="Slot Patto",
            formula=lambda lv: _lookup(_WARLOCK_PATTO, lv),
            restoration_type=RestorationType.SHORT_REST,
            note="Gli Slot Patto si recuperano con il riposo breve, a differenza degli altri caster.",
            description={
                "it": "I tuoi slot incantesimo della Magia del Patto: sempre dello stesso livello (il più alto disponibile) e recuperati con un riposo breve, a differenza degli altri incantatori.",
                "en": "Your Pact Magic spell slots: all of the same (highest available) level and recovered on a short rest, unlike other casters.",
            },
        ),
    ],
    "Mago": [
        ResourceConfig(
            key="wizard.arcane_recovery",
            name="Recupero Arcano",
            formula=lambda lv: 1,
            restoration_type=RestorationType.LONG_REST,
            note="Permette di recuperare slot incantesimo durante un riposo breve (una volta per riposo lungo).",
            description={
                "it": "Una volta al giorno, durante un riposo breve, recuperi slot incantesimo spesi con livelli combinati fino a metà del tuo livello da mago (arrotondato per eccesso).",
                "en": "Once per day, during a short rest, you recover expended spell slots with a combined level up to half your wizard level (rounded up).",
            },
        ),
    ],
    # Ranger and Ladro have no base class resources
    "Ranger": [],
    "Ladro": [],
}


# ---------------------------------------------------------------------------
# Helper: build resource dicts for DB insertion
# ---------------------------------------------------------------------------

def get_class_feature_specs(
    class_name: str,
    level: int,
    char: Optional["Character"] = None,
    lang: str = "it",
) -> list[dict]:
    """Ritorna le spec delle feature di classe disponibili a un dato livello.

    Ogni dict: {key, name, description, max_uses, restoration_type, cha_based}.
    Le feature con max_uses == 0 (non ancora disponibili) sono escluse.
    `lang` seleziona la lingua della description (fallback "it").
    """
    configs = CLASS_RESOURCES.get(class_name, [])
    result: list[dict] = []
    for cfg in configs:
        if cfg.cha_based and char is not None:
            cha_score = next(
                (a.value for a in char.ability_scores if a.name == "charisma"), 10
            )
            total = max(1, (cha_score - 10) // 2)
        elif cfg.cha_based:
            total = 3  # default sensato se il personaggio non è disponibile
        else:
            total = cfg.formula(level)

        if total <= 0:
            continue

        result.append({
            "key": cfg.key,
            "name": cfg.name,
            "description": cfg.description.get(lang) or cfg.description.get("it"),
            "max_uses": total,
            "restoration_type": cfg.restoration_type,
            "cha_based": cfg.cha_based,
        })
    return result


def get_saving_throw_proficiencies(class_name: str) -> dict[str, bool]:
    """Return the saving throw proficiencies granted by a starting class.

    Returns a dict mapping ability slug → True for the two saves the class
    grants. Empty dict for unknown/custom classes (no proficiencies seeded).
    Only the starting (first) class should call this — multiclassing does not
    grant saving throw proficiencies in D&D 5e.
    """
    abilities = CLASS_SAVING_THROWS.get(class_name)
    if not abilities:
        return {}
    return {ability: True for ability in abilities}



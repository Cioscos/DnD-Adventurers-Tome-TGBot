"""Personaggi di prova per le regole di classe (solo DB locale di sviluppo, prefisso `[prova]`)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import Ability, AbilityScore, Character, CharacterClass, RestorationType
from core.rules.edition import CLASS_KEYS, class_key
from core.rules.feature_sync import sync_class_feature_abilities
from core.rules.subclasses import match_subclass

PREFIX = "[prova]"
HIT_DICE = {
    "barbarian": 12, "bard": 8, "cleric": 8, "druid": 8, "fighter": 10, "monk": 8,
    "paladin": 10, "ranger": 10, "rogue": 8, "sorcerer": 6, "warlock": 8, "wizard": 6,
}
# Prima sottoclasse a catalogo per edizione (testo italiano come lo scrive l'utente).
FIRST_SUBCLASS = {
    "2014": {
        "barbarian": "Cammino del Berserker", "bard": "Collegio della Sapienza", "cleric": "Dominio della Conoscenza",
        "druid": "Circolo della Terra", "fighter": "Campione", "monk": "Via della Mano Aperta",
        "paladin": "Giuramento di Devozione", "ranger": "Cacciatore", "rogue": "Furfante",
        "sorcerer": "Discendenza Draconica", "warlock": "Il Signore Fatato", "wizard": "Scuola di Abiurazione",
    },
    "2024": {
        "barbarian": "Cammino del Berserker", "bard": "Collegio della Danza", "cleric": "Dominio della Vita",
        "druid": "Circolo della Terra", "fighter": "Maestro di Battaglia", "monk": "Guerriero della Misericordia",
        "paladin": "Giuramento di Devozione", "ranger": "Signore delle Bestie", "rogue": "Mistificatore Arcano",
        "sorcerer": "Stregoneria Aberrante", "warlock": "Patrono Fatato", "wizard": "Abiuratore",
    },
}


def _spec(name: str, classes: list[tuple], edition: str = "2014", **extra) -> dict:
    return {"name": f"{PREFIX} {name}", "edition": edition, "classes": classes, **extra}


SAMPLE_SPECS: list[dict] = [
    _spec(f"{key} {ed}", [(key, 20, FIRST_SUBCLASS[ed][key], HIT_DICE[key])], ed, kind="class")
    for ed in ("2014", "2024") for key in CLASS_KEYS
] + [
    _spec("Multiclasse Mago/Warlock", [("Mago", 17, None, 6), ("warlock", 3, None, 8)]),
    _spec("Ladro sottoclasse ignota", [("Ladro", 5, "Ladro Acrobata", 8)]),
    _spec("Guerriero CA manuale", [("Guerriero", 5, None, 10)], base_ac=18, ac_override=True),
    # la CA importata da Beyond include già la Destrezza: 17, né 17 + 4 (doppia somma) né 10 + 4 (calcolo)
    _spec("Ladro CA da Beyond", [("Ladro", 5, None, 8)], base_ac=17, scores={"dexterity": 18},
          settings={"import_source": "dndbeyond"}),
    _spec("Proficienze vuote", [("Guerriero", 5, None, 10)], proficiencies=[]),
    _spec("Usi spesi", [("Barbaro", 5, "Cammino del Berserker", 12)], spent_uses=("barbarian.rage", "Ira", 3, 1)),
    _spec("Classe custom", [("Cacciatore di Taglie", 5, None, None)]),
]


async def build_rules_character(session: AsyncSession, spec: dict, user_id: int) -> Character:
    char = Character(
        user_id=user_id, name=spec["name"], rules_edition=spec["edition"], race="Umano",
        hit_points=40, current_hit_points=40,
        base_armor_class=spec.get("base_ac", 10), base_armor_class_override=spec.get("ac_override", False),
        general_proficiencies=spec.get("proficiencies", ["Armi semplici", "Armi da guerra"]),
        settings=spec.get("settings", {}),
    )
    # Relazioni assegnate prima del flush: il sync le legge senza lazy-load in contesto async.
    char.ability_scores = [
        AbilityScore(name=ab, value=spec.get("scores", {}).get(ab, 14))
        for ab in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
    ]
    char.items, char.abilities, char.classes = [], [], []
    for name, level, subclass, die in spec["classes"]:
        row = CharacterClass(class_name=name, level=level, subclass=subclass, hit_die=die)
        row.subclass_key = match_subclass(subclass, class_key(row), spec["edition"])
        char.classes.append(row)
    session.add(char)
    await session.flush()
    if "spent_uses" in spec:
        key, label, max_uses, uses = spec["spent_uses"]
        char.abilities.append(Ability(
            name=label, max_uses=max_uses, uses=uses, is_class_feature=True,
            feature_key=key, source_class_id=char.classes[0].id, restoration_type=RestorationType.LONG_REST,
        ))
    for row in char.classes:
        await sync_class_feature_abilities(session, char, row)
    await session.flush()
    return char


async def seed_rules_characters(session: AsyncSession, user_id: int) -> int:
    """Crea i personaggi di prova mancanti (per nome); ritorna quanti ne ha creati."""
    existing = set((await session.execute(
        select(Character.name).where(Character.user_id == user_id, Character.name.like(f"{PREFIX}%"))
    )).scalars())
    created = 0
    for spec in SAMPLE_SPECS:
        if spec["name"] not in existing:
            await build_rules_character(session, spec, user_id)
            created += 1
    return created

"""Sync delle feature di classe (ex-ClassResource) come righe Ability.

Chiamato ai punti che variano il livello di una classe (creazione classe,
level-up, distribute, XP). Crea le feature appena disponibili e aggiorna
``max_uses`` (clampando ``uses``) di quelle esistenti, ritrovandole via
``(source_class_id, feature_key)``. Non tocca mai la ``description`` (è
editabile dall'utente) né le feature ``cha_based`` al level-up.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.data.classes import get_class_feature_specs
from core.db.models import Ability, Character, CharacterClass


async def sync_class_feature_abilities(
    session: AsyncSession,
    char: Character,
    cls: CharacterClass,
    *,
    lang: str = "it",
) -> None:
    """Crea/aggiorna le Ability auto-generate dalla classe ``cls``.

    Richiede che ``char.abilities``, ``char.classes`` e ``char.ability_scores``
    siano già caricati (selectinload).
    """
    specs = get_class_feature_specs(cls.class_name, cls.level, char, lang)
    existing = {
        a.feature_key: a
        for a in char.abilities
        if a.is_class_feature and a.source_class_id == cls.id
    }

    for spec in specs:
        ability = existing.get(spec["key"])
        if ability is None:
            ability = Ability(
                character_id=char.id,
                source_class_id=cls.id,
                is_class_feature=True,
                feature_key=spec["key"],
                name=spec["name"],
                description=spec["description"],
                max_uses=spec["max_uses"],
                uses=spec["max_uses"],
                is_active=True,
                is_passive=False,
                restoration_type=spec["restoration_type"],
            )
            session.add(ability)
            char.abilities.append(ability)
            continue

        # Aggiorna il nome (il catalogo è la fonte di verità per le feature).
        ability.name = spec["name"]

        # Le feature CHA-based non si ricalcolano al level-up (parità col vecchio
        # update_resources_for_level): il loro max dipende dal mod CAR, non dal livello.
        if spec["cha_based"]:
            continue

        new_max = spec["max_uses"]
        old_max = ability.max_uses if ability.max_uses is not None else new_max
        ability.max_uses = new_max
        current = ability.uses if ability.uses is not None else new_max
        delta = new_max - old_max
        if delta > 0:
            # Il level-up concede capacità: gli usi spesi restano spesi, ma i
            # punti appena guadagnati sono subito disponibili.
            ability.uses = min(new_max, current + delta)
        elif current > new_max:
            ability.uses = new_max

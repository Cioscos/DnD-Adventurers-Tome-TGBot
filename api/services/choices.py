"""Scelte di livello (ASI / talento): creazione al level-up e applicazione degli effetti."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.homebrew.dsl import RuleDSL
from core.data.classes import ASI_LEVELS, ASI_LEVELS_DEFAULT, class_table_key
from core.data.feats import ALL_ABILITIES, FEATS
from core.db.models import Ability, Character, CharacterHistory, HomebrewRule, RestorationType

_WHEN = {"path": "$character.id", "op": "gt", "value": 0}


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _bad(msg: str) -> HTTPException:
    return HTTPException(422, msg)


def add_asi_choices(char: Character, class_name: str, old_level: int, new_level: int) -> None:
    """Crea una scelta per ogni livello ASI attraversato verso l'alto (mai duplicata)."""
    if new_level <= old_level:
        return
    key = class_table_key(class_name) or class_name
    choices = list(char.pending_choices or [])
    for lvl in ASI_LEVELS.get(key, ASI_LEVELS_DEFAULT):
        if old_level < lvl <= new_level and not any(
            c["class_key"] == key and c["level"] == lvl for c in choices
        ):
            choices.append({"id": uuid.uuid4().hex, "kind": "asi", "class_key": key,
                            "level": lvl, "created_at": _now()})
    char.pending_choices = choices


def _score_row(char: Character, ability: str):
    return next(a for a in char.ability_scores if a.name == ability)


def _bump(char: Character, ability: str, amount: int) -> None:
    row = _score_row(char, ability)
    if row.value + amount > 20:
        raise _bad(f"{ability} cannot exceed 20")
    row.value += amount


def _history(session: AsyncSession, char: Character, text: str) -> None:
    session.add(CharacterHistory(character_id=char.id, timestamp=_now(),
                                 event_type="level_choice", description=f"Scelta di livello: {text}"))


def resolve_asi(session: AsyncSession, char: Character, increases: dict[str, int]) -> None:
    if (set(increases) - set(ALL_ABILITIES) or sum(increases.values()) != 2
            or any(v not in (1, 2) for v in increases.values())):
        raise _bad("ASI must distribute exactly 2 points across known abilities")
    for ability, amount in increases.items():
        _bump(char, ability, amount)
    _history(session, char, ", ".join(f"{a} +{n}" for a, n in increases.items()))


def resolve_feat(
    session: AsyncSession, char: Character, feat_key: str, ability: Optional[str],
    custom_name: Optional[str], custom_text: Optional[str], lang: str,
) -> None:
    now = _now()
    if feat_key == "custom":
        name = (custom_name or "").strip()
        if not name:
            raise _bad("custom_name is required")
        session.add(Ability(character_id=char.id, name=name[:200], description=custom_text or None,
                            is_passive=True, feature_key="feat.custom"))
        _history(session, char, name)
        return
    spec = FEATS.get(feat_key)
    if spec is None:
        raise _bad(f"Unknown feat '{feat_key}'")
    if spec.ability_increase:
        if ability not in spec.ability_increase:
            raise _bad(f"ability must be one of {spec.ability_increase}")
        _bump(char, ability, 1)
        if spec.save_proficiency_from_increase:
            saves = dict(char.saving_throws or {})
            saves[ability] = True
            char.saving_throws = saves
    name = spec.name.get(lang) or spec.name["it"]
    summary = spec.summary.get(lang) or spec.summary["it"]
    if spec.passive_modifiers:
        dsl = RuleDSL.model_validate({
            "version": 1, "subject": {"type": "character"}, "triggers": [],
            "passive_modifiers": [
                {"when": _WHEN, "target": f"character.{m['target']}", "value": m["value"],
                 "label_i18n": dict(spec.name)} for m in spec.passive_modifiers],
        })
        session.add(HomebrewRule(
            character_id=char.id, name=name, description=summary, enabled=True,
            dsl=dsl.model_dump(mode="json"), version=1, template_id=f"feat:{spec.key}",
            created_at=now, updated_at=now))
    if spec.setting:
        s = dict(char.settings or {})
        s[spec.setting] = True
        char.settings = s
    c = spec.counter
    session.add(Ability(
        character_id=char.id, name=(c["name"].get(lang) or c["name"]["it"]) if c else name,
        description=summary, is_passive=c is None, feature_key=f"feat.{spec.key}",
        max_uses=c["max"] if c else None, uses=c["max"] if c else None,
        restoration_type=RestorationType(c["restoration"]) if c else RestorationType.NONE))
    _history(session, char, name)

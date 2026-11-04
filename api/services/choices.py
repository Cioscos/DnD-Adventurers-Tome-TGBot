"""Scelte di livello (ASI / talento): creazione al level-up e applicazione degli effetti."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.homebrew.dsl import RuleDSL
from core.data.classes import class_table_key
from core.data.feats import ALL_ABILITIES
from core.data.feats_2024 import ALL_FEATS as FEATS
from core.db.models import Ability, Character, CharacterClass, CharacterHistory, HomebrewRule, RestorationType
from core.rules.catalog import features_for
from core.rules.level_choices import active_choice_specs, mark_resolved, pending_key, sync_level_choices  # noqa: F401
from core.rules.edition import character_edition, class_key
from core.rules.types import RuleContext

_WHEN = {"path": "$character.id", "op": "gt", "value": 0}


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _bad(msg: str) -> HTTPException:
    return HTTPException(422, msg)


def _class_by_key(char: Character, key: str | None) -> CharacterClass | None:
    return next((c for c in char.classes if pending_key(c) == key), None)


def _choice_spec(char: Character, cls: CharacterClass, group: str | None):
    return next((ch for ch in active_choice_specs(char, cls) if ch.group == group), None)


def _entries(char: Character, cls: CharacterClass, group: str, keys: list[str]) -> list[dict]:
    specs = {s.option_key: s for s in features_for(character_edition(char), class_key(cls)) if s.option_group == group}
    choice = _choice_spec(char, cls, group)
    labelled = choice.label if choice and choice.label else None

    def entry(k: str) -> dict:
        if labelled and k not in specs:
            return {"key": k, **labelled(k)}
        return {"key": k, "name": specs[k].name if k in specs else {"it": k, "en": k},
                "summary": specs[k].summary if k in specs else {"it": "", "en": ""}}
    return [entry(k) for k in keys]


def _available(char: Character, cls: CharacterClass, ch) -> list[str]:
    ctx = RuleContext(char=char, edition=character_edition(char), class_row=cls, class_level=cls.level)
    chosen = (cls.options or {}).get(ch.group, [])
    return [k for k in ch.options(ctx) if k not in chosen]


def option_catalog(char: Character, choice: dict) -> list[dict]:
    """Opzioni ancora scegliibili di una scelta `class_option`: `{key, name, summary}` bilingui."""
    cls = _class_by_key(char, choice.get("class_key"))
    ch = _choice_spec(char, cls, choice.get("group")) if cls else None
    return _entries(char, cls, ch.group, _available(char, cls, ch)) if ch else []


def class_options_state(char: Character, cls: CharacterClass, group: str) -> dict:
    ch = _choice_spec(char, cls, group)
    if ch is None:
        raise HTTPException(404, "Option group not found")
    return {"replaceable": ch.replaceable,
            "chosen": _entries(char, cls, group, list((cls.options or {}).get(group, []))),
            "available": _entries(char, cls, group, _available(char, cls, ch))}


def replace_class_option(session: AsyncSession, char: Character, cls: CharacterClass,
                         group: str, old_key: str, new_key: str) -> None:
    """Sostituisce un'opzione scelta con un'altra del catalogo; solo se la ChoiceSpec è `replaceable`."""
    ch = _choice_spec(char, cls, group)
    chosen = list((cls.options or {}).get(group, []))
    if ch is None or not ch.replaceable:
        raise _bad("option_not_replaceable")
    if old_key not in chosen or new_key not in _available(char, cls, ch):
        raise _bad("invalid_replacement")
    chosen[chosen.index(old_key)] = new_key
    cls.options = {**(cls.options or {}), group: chosen}
    _history(session, char, f"{group}: {old_key} -> {new_key}")


def resolve_class_option(session: AsyncSession, char: Character, choice: dict, picked: list[str]) -> None:
    cls = _class_by_key(char, choice.get("class_key"))
    group, count = choice.get("group"), choice.get("count")
    valid = {o["key"] for o in option_catalog(char, choice)}
    if (cls is None or not group or not count or len(picked) != count
            or len(set(picked)) != len(picked) or not set(picked) <= valid):
        raise _bad(f"Pick exactly {count} distinct valid options")
    cls.options = {**(cls.options or {}), group: [*(cls.options or {}).get(group, []), *picked]}
    _history(session, char, f"{group}: {', '.join(picked)}")


def _check_feat(char: Character, spec, boon: bool) -> None:
    """Edizione, categoria e prerequisiti (livello, caratteristica, incantesimi) di un talento."""
    if spec.edition != character_edition(char):
        raise _bad("feat_wrong_edition")
    if (spec.category == "epic_boon") != boon:
        raise _bad("feat_wrong_category")
    if char.total_level < spec.min_level:
        raise _bad("feat_prerequisite_level")
    if spec.prereq_abilities:
        names, minimum = spec.prereq_abilities
        if not any(_score_row(char, n).value >= minimum for n in names):
            raise _bad("feat_prerequisite_ability")
    if spec.needs_spellcasting and not any(c.spellcasting_ability for c in char.classes):
        raise _bad("feat_prerequisite_spellcasting")


def _score_row(char: Character, ability: str):
    row = next((a for a in char.ability_scores if a.name == ability), None)
    if row is None:
        raise _bad(f"Missing ability score '{ability}'")
    return row


def _bump(char: Character, ability: str, amount: int, cap: int = 20) -> None:
    row = _score_row(char, ability)
    if row.value + amount > cap:
        raise _bad(f"{ability} cannot exceed {cap}")
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
    custom_name: Optional[str], custom_text: Optional[str], lang: str, boon: bool = False,
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
    _check_feat(char, spec, boon)
    if any(a.feature_key == f"feat.{feat_key}" for a in char.abilities):
        raise _bad("feat_already_taken")
    if spec.ability_increase:
        if ability not in spec.ability_increase:
            raise _bad(f"ability must be one of {spec.ability_increase}")
        if spec.edition == "2024" and spec.save_proficiency_from_increase and (char.saving_throws or {}).get(ability):
            raise _bad("save_already_proficient")
        _bump(char, ability, 1, spec.max_score)
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


async def remove_feat(session: AsyncSession, char: Character, ability: Ability) -> None:
    """Rimuove un talento: abilita, regola homebrew, impostazione. Gli aumenti di
    caratteristica e la competenza nei TS NON vengono annullati (stato precedente non tracciato)."""
    key = (ability.feature_key or "")[len("feat."):]
    name = ability.name
    if key == "custom":
        await session.execute(delete(Ability).where(Ability.id == ability.id))
    else:
        await session.execute(delete(Ability).where(
            Ability.character_id == char.id, Ability.feature_key == f"feat.{key}"))
        await session.execute(delete(HomebrewRule).where(
            HomebrewRule.character_id == char.id, HomebrewRule.template_id == f"feat:{key}"))
        setting = FEATS[key].setting if key in FEATS else None
        still_set = any(
            a.id != ability.id and (a.feature_key or "")[5:] in FEATS
            and FEATS[a.feature_key[5:]].setting == setting for a in char.abilities)
        if setting and not still_set:
            s = dict(char.settings or {})
            s.pop(setting, None)
            char.settings = s
    session.add(CharacterHistory(character_id=char.id, timestamp=_now(),
                                 event_type="level_choice", description=f"Talento rimosso: {name}"))

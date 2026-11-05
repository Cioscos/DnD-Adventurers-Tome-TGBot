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
from core.rules.level_choices import (  # noqa: F401
    FREE_KNOWN_KEY, active_choice_specs, apply_grants, mark_resolved, pending_key, reconcile_choices, sync_level_choices,
)
from core.rules.edition import character_edition, class_key
from core.rules.spellcasting import slots_for
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


def _entries(char: Character, cls: CharacterClass, group: str, keys: list[str], owned: frozenset = frozenset()) -> list[dict]:
    specs = {s.option_key: s for s in features_for(character_edition(char), class_key(cls)) if s.option_group == group}
    choice = _choice_spec(char, cls, group)
    labelled = choice.label if choice and choice.label else None

    def entry(k: str) -> dict:
        if labelled and k not in specs:
            base = {"key": k, **labelled(k)}
        else:
            base = {"key": k, "name": specs[k].name if k in specs else {"it": k, "en": k},
                    "summary": specs[k].summary if k in specs else {"it": "", "en": ""}}
        return {**base, "owned": True} if k in owned else base
    return [entry(k) for k in keys]


def _available(char: Character, cls: CharacterClass, ch, retrofit: bool = False) -> tuple[list[str], list[str]]:
    """Opzioni scegliibili e, solo per una scelta di un personaggio esistente prima del catalogo (``retrofit``, R39), quelle
    «già sulla scheda» che si possono dichiarare invece di sceglierne altre."""
    ctx = RuleContext(char=char, edition=character_edition(char), class_row=cls, class_level=cls.level)
    chosen = (cls.options or {}).get(ch.group, [])
    fresh = [k for k in ch.options(ctx) if k not in chosen]
    owned = [k for k in (ch.owned(ctx) if retrofit and ch.owned else []) if k not in chosen and k not in fresh]
    return fresh, owned


def option_catalog(char: Character, choice: dict) -> list[dict]:
    """Opzioni ancora scegliibili di una scelta `class_option`: `{key, name, summary}` bilingui."""
    cls = _class_by_key(char, choice.get("class_key"))
    ch = _choice_spec(char, cls, choice.get("group")) if cls else None
    if not ch:
        return []
    fresh, owned = _available(char, cls, ch, bool(choice.get("retrofit")))
    return _entries(char, cls, ch.group, [*fresh, *owned], frozenset(owned))


def pick_count(char: Character, choice: dict) -> int | None:
    """Quante opzioni si prendono adesso: con ``grants`` (abilità) meno di ``count`` se la scheda non ne ha abbastanza (R39,
    il resto aspetta). ``None`` per gli incantesimi, che si scelgono dalla loro pagina."""
    if choice.get("kind") != "class_option":
        return None
    cls = _class_by_key(char, choice.get("class_key"))
    ch = _choice_spec(char, cls, choice.get("group")) if cls else None
    if ch is None or ch.spell_pick:
        return None
    count = int(choice.get("count") or 0)
    return min(count, len(option_catalog(char, choice))) if ch.grants else count


def is_resolvable(char: Character, choice: dict) -> bool:
    """Una scelta senza opzioni in elenco non blocca le successive (R39)."""
    picks = pick_count(char, choice)
    return True if picks is None else picks > 0


def class_options_state(char: Character, cls: CharacterClass, group: str) -> dict:
    ch = _choice_spec(char, cls, group)
    if ch is None:
        raise HTTPException(404, "Option group not found")
    return {"replaceable": ch.replaceable,
            "chosen": _entries(char, cls, group, list((cls.options or {}).get(group, []))),
            "available": _entries(char, cls, group, _available(char, cls, ch)[0])}


def replace_class_option(session: AsyncSession, char: Character, cls: CharacterClass,
                         group: str, old_key: str, new_key: str) -> None:
    """Sostituisce un'opzione scelta con un'altra del catalogo; solo se la ChoiceSpec è `replaceable`."""
    ch = _choice_spec(char, cls, group)
    chosen = list((cls.options or {}).get(group, []))
    if ch is None or not ch.replaceable:
        raise _bad("option_not_replaceable")
    if old_key not in chosen or new_key not in _available(char, cls, ch)[0]:
        raise _bad("invalid_replacement")
    chosen[chosen.index(old_key)] = new_key
    cls.options = {**(cls.options or {}), group: chosen}
    _history(session, char, f"{group}: {old_key} -> {new_key}")


def resolve_class_option(session: AsyncSession, char: Character, choice: dict, picked: list[str]) -> None:
    cls = _class_by_key(char, choice.get("class_key"))
    group, count = choice.get("group"), choice.get("count")
    ch = _choice_spec(char, cls, group) if cls else None
    if ch is not None and ch.spell_pick:  # gli incantesimi si scelgono dalla pagina degli incantesimi
        if not choice.get("retrofit"):
            raise _bad("spell_pick_via_spells")
        return _resolve_known_spells(session, char, cls, ch, count, picked)
    valid = {o["key"] for o in option_catalog(char, choice)}
    need = pick_count(char, choice)
    if (cls is None or not group or not count or not need or len(picked) != need
            or len(set(picked)) != len(picked) or not set(picked) <= valid):
        raise _bad(f"Pick exactly {need or count} distinct valid options")
    cls.options = {**(cls.options or {}), group: [*(cls.options or {}).get(group, []), *picked]}
    if ch is not None:
        apply_grants(char, ch, picked)
    _history(session, char, f"{group}: {', '.join(picked)}")


def _resolve_known_spells(session: AsyncSession, char: Character, cls: CharacterClass, ch, count: int,
                          picked: list[str]) -> None:
    """R39: un personaggio esistente prima del catalogo dichiara «già sulla scheda» incantesimi che conosce: nessuno è
    aggiunto né duplicato. Un Segreto Magico resta fra i conosciuti; uno Aggiuntivo esce dal loro conteggio."""
    try:
        ids = [int(p) for p in picked]
    except ValueError:
        raise _bad("spell_not_known") from None
    owned = {s.id: s for s in char.spells if s.class_id in (None, cls.id)}  # nullo: salvato prima delle classi sugli incantesimi
    taken = (cls.options or {}).get(ch.group, [])
    free = list((char.settings or {}).get(FREE_KNOWN_KEY) or [])
    if (not ids or len(ids) > count or len(set(ids)) != len(ids) or not set(ids) <= set(owned)
            or any((owned[i].srd_index or owned[i].name) in taken for i in ids)
            or (ch.spell_pick == "known" and any(i in free for i in ids))):
        raise _bad("spell_not_known")
    cls.options = {**(cls.options or {}), ch.group: [*taken, *(owned[i].srd_index or owned[i].name for i in ids)]}
    for i in ids:
        owned[i].class_id = cls.id  # la dichiarazione assegna la classe
    if ch.spell_pick == "extra":
        char.settings = {**(char.settings or {}), FREE_KNOWN_KEY: [*free, *(i for i in ids if i not in free)]}
    _history(session, char, f"{ch.group}: {', '.join(owned[i].name for i in ids)}")


def max_pick_level(char: Character, cls: CharacterClass) -> int:
    """Livello più alto che la classe ``cls`` lancia secondo la sua tabella degli slot: in multiclasse la scheda dice
    «per classe», non la tabella sommata."""
    regular = slots_for(character_edition(char), [cls]).regular
    return max((level for level, total in regular.items() if total > 0), default=0)


def spell_pick_info(char: Character, choice: dict) -> dict | None:
    """Per una scelta di incantesimi: se non conta fra i conosciuti e il livello massimo ammesso; altrimenti ``None``."""
    if choice.get("kind") != "class_option":
        return None
    cls = _class_by_key(char, choice.get("class_key"))
    ch = _choice_spec(char, cls, choice.get("group")) if cls else None
    if ch is None or not ch.spell_pick:
        return None
    info = {"free": ch.spell_pick == "extra", "max_level": max_pick_level(char, cls)}
    if choice.get("retrofit"):  # R39: gli incantesimi che il personaggio ha già e può dichiarare «già sulla scheda»
        taken = (cls.options or {}).get(ch.group, [])
        free = (char.settings or {}).get(FREE_KNOWN_KEY) or []
        info["owned"] = [{"id": sp.id, "name": sp.name, "level": sp.level} for sp in sorted(char.spells, key=lambda x: (x.level, x.name))
                         if sp.class_id in (None, cls.id) and (sp.srd_index or sp.name) not in taken
                         and not (ch.spell_pick == "known" and sp.id in free)]
    return info


def spell_pick_target(char: Character, pick_id: str, level: int, class_id: int | None, name: str,
                      srd_index: str | None) -> tuple[CharacterClass, object]:
    """Controlla che la scelta esista e che l'incantesimo sia ammesso; restituisce classe e ``ChoiceSpec``."""
    choice = next((c for c in char.pending_choices or [] if c.get("id") == pick_id), None)
    cls = _class_by_key(char, choice.get("class_key")) if choice else None
    ch = _choice_spec(char, cls, choice.get("group")) if cls else None
    if ch is None or not ch.spell_pick:
        raise HTTPException(404, detail={"code": "choice_not_found"})
    if class_id is not None and class_id != cls.id:
        raise HTTPException(400, detail={"code": "bad_class"})
    if level > max_pick_level(char, cls):
        raise HTTPException(422, detail={"code": "spell_pick_level"})
    lowered = name.strip().lower()
    if any((srd_index and s.srd_index == srd_index) or s.name.strip().lower() == lowered for s in char.spells):
        raise HTTPException(409, detail={"code": "spell_already_known"})
    return cls, ch


def consume_spell_pick(session: AsyncSession, char: Character, cls: CharacterClass, ch, spell) -> None:
    """L'incantesimo è stato aggiunto: la scelta scala di uno; un extra non entra nel conteggio dei conosciuti."""
    cls.options = {**(cls.options or {}), ch.group: [*(cls.options or {}).get(ch.group, []), spell.srd_index or spell.name]}
    if ch.spell_pick == "extra":
        free = [*((char.settings or {}).get(FREE_KNOWN_KEY) or []), spell.id]
        char.settings = {**(char.settings or {}), FREE_KNOWN_KEY: free}
    _history(session, char, f"{ch.group}: {spell.name}")
    reconcile_choices(char)


def release_spell_pick(char: Character, spell) -> bool:
    """L'incantesimo sta per essere cancellato: se era una scelta (Segreti Magici) la scelta torna da fare, e il suo id esce
    dagli incantesimi che non contano fra i conosciuti (SQLite riassegna gli id). ``True`` se qualcosa è cambiato."""
    changed = False
    free = list((char.settings or {}).get(FREE_KNOWN_KEY) or [])
    if spell.id in free:
        char.settings = {**(char.settings or {}), FREE_KNOWN_KEY: [i for i in free if i != spell.id]}
        changed = True
    key = spell.srd_index or spell.name
    for cls in char.classes:
        for ch in active_choice_specs(char, cls):
            taken = list((cls.options or {}).get(ch.group, []))
            if ch.spell_pick and key in taken:
                taken.remove(key)
                cls.options = {**(cls.options or {}), ch.group: taken}
                changed = True
                break
    return changed


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

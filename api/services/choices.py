"""Scelte di livello (ASI / talento): creazione al level-up e applicazione degli effetti."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.data.classes import class_table_key
from core.data.feats import ALL_ABILITIES
from core.data.feats_2024 import ALL_FEATS as FEATS
from api.services.history import add_history
from core.data.skills import SKILL_ABILITY_MAP
from core.db.models import Ability, Character, CharacterClass, HomebrewRule, RestorationType, Spell
from core.rules.catalog._common import has_fighting_style, styles_taken
from core.rules.proficiencies import armor_trained, normalize
from core.rules.catalog import features_for
from core.rules.level_choices import (  # noqa: F401
    FREE_KNOWN_KEY, active_choice_specs, apply_grants, mark_resolved, pending_key, reconcile_choices, sync_level_choices,
)
from core.rules.edition import character_edition, class_key
from core.rules.feature_sync import REPLACED_AT_REST
from core.rules.schools import normalize_school
from core.rules.spellcasting import slots_for
from core.rules.types import RuleContext



def _bad(msg: str) -> HTTPException:
    return HTTPException(422, msg)


def _class_by_key(char: Character, key: str | None) -> CharacterClass | None:
    return next((c for c in char.classes if pending_key(c) == key), None)


def _choice_spec(char: Character, cls: CharacterClass, group: str | None):
    return next((ch for ch in active_choice_specs(char, cls) if ch.group == group), None)


def _entries(char: Character, cls: CharacterClass, group: str, keys: list[str], owned: frozenset = frozenset()) -> list[dict]:
    specs: dict = {}
    for s in features_for(character_edition(char), class_key(cls)):
        if s.option_group == group:
            specs.setdefault(s.option_key, s)  # la prima riga (livello più basso) è quella che si sceglie
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
    return {"replaceable": ch.replaceable, "listed": ch.listed,
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
    if ch.protected and old_key in ch.protected(RuleContext(char=char, edition=character_edition(char), class_row=cls, class_level=cls.level)):
        raise HTTPException(422, detail={"code": "option_is_prerequisite"})
    if ch.replace_per_long_rest:  # cambi per riposo lungo (`replace_per_long_rest`: 1 per Guerriero, Barbaro e Mago; 2 per Paladino, Ranger e Ladro), per classe; il primo di sempre è libero (nessun riposo registrato)
        swaps = (char.settings or {}).get(REPLACED_AT_REST) or {}
        last = swaps.get(str(cls.id), {})
        used = last.get("n", 1) if last.get("at", "-") == (char.last_long_rest_at or "") else 0
        if used >= int(ch.replace_per_long_rest):
            raise HTTPException(409, detail={"code": "replace_after_long_rest"})
        char.settings = {**(char.settings or {}), REPLACED_AT_REST: {**swaps, str(cls.id): {"at": char.last_long_rest_at or "", "n": used + 1}}}
    chosen[chosen.index(old_key)] = new_key
    cls.options = {**(cls.options or {}), group: chosen}
    if ch.always_prepared:  # Maestria negli Incantesimi: il nuovo è sempre preparato, il vecchio torna un incantesimo qualsiasi
        for spell in char.spells:
            if spell.name == old_key:
                spell.always_prepared = spell.is_prepared = False
            elif spell.name == new_key:
                spell.always_prepared = spell.is_prepared = True
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
    if ch is not None and ch.batch_ok and not ch.batch_ok(RuleContext(char=char, edition=character_edition(char), class_row=cls,
                                                                        class_level=cls.level), picked):
        raise HTTPException(422, detail={"code": "option_prerequisite"})
    cls.options = {**(cls.options or {}), group: [*(cls.options or {}).get(group, []), *picked]}
    if ch is not None:
        apply_grants(char, ch, picked)
        if ch.always_prepared:  # Incantesimi Personali: sempre preparati e fuori dal limite dei preparati
            for spell in char.spells:
                if spell.name in picked:
                    spell.always_prepared = spell.is_prepared = True
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
            or any(owned[i].level > _pick_cap(char, cls, ch) for i in ids)  # un trucchetto resta un trucchetto
            or (ch.spell_exact and any(owned[i].level != ch.spell_level for i in ids))  # un Arcanum è del suo grado
            or (ch.spell_school and any(normalize_school(owned[i].school) != ch.spell_school for i in ids))  # un Sapiente, la sua scuola
            or (ch.spell_pick == "known" and any(i in free for i in ids))):
        raise _bad("spell_not_known")
    cls.options = {**(cls.options or {}), ch.group: [*taken, *(owned[i].srd_index or owned[i].name for i in ids)]}
    for i in ids:
        owned[i].class_id = cls.id  # la dichiarazione assegna la classe
        if ch.spell_pick == "book":
            owned[i].in_spellbook = True  # un incantesimo già sulla scheda è già nel libro
    if ch.spell_pick == "extra":
        char.settings = {**(char.settings or {}), FREE_KNOWN_KEY: [*free, *(i for i in ids if i not in free)]}
    _history(session, char, f"{ch.group}: {', '.join(owned[i].name for i in ids)}")


def max_pick_level(char: Character, cls: CharacterClass) -> int:
    """Livello più alto che la classe ``cls`` lancia secondo la sua tabella degli slot: in multiclasse la scheda dice
    «per classe», non la tabella sommata."""
    regular = slots_for(character_edition(char), [cls]).regular
    return max((level for level, total in regular.items() if total > 0), default=0)


def _pick_cap(char: Character, cls: CharacterClass, ch) -> int:
    """Livello massimo dell'incantesimo di una scelta: quello della classe, o meno se la scelta è di soli trucchetti.
    ``spell_exact`` (Arcanum Mistico): il livello della scelta, qualunque siano gli slot della classe."""
    if ch.spell_exact:
        return ch.spell_level
    top = max_pick_level(char, cls)
    return top if ch.spell_level is None else min(top, ch.spell_level)


def spell_pick_info(char: Character, choice: dict) -> dict | None:
    """Per una scelta di incantesimi: se non conta fra i conosciuti e il livello massimo ammesso; altrimenti ``None``."""
    if choice.get("kind") != "class_option":
        return None
    cls = _class_by_key(char, choice.get("class_key"))
    ch = _choice_spec(char, cls, choice.get("group")) if cls else None
    if ch is None or not ch.spell_pick:
        return None
    info = {"free": ch.spell_pick == "extra", "max_level": _pick_cap(char, cls, ch), "list": ch.spell_list,
            **({"book": True} if ch.spell_pick == "book" else {}), **({"school": ch.spell_school} if ch.spell_school else {}),
            **({"exact": True} if ch.spell_exact else {}), **({"ritual": True} if ch.spell_ritual else {})}
    if choice.get("retrofit"):  # R39: gli incantesimi che il personaggio ha già e può dichiarare «già sulla scheda»
        taken = (cls.options or {}).get(ch.group, [])
        free = (char.settings or {}).get(FREE_KNOWN_KEY) or []
        info["owned"] = [{"id": sp.id, "name": sp.name, "level": sp.level} for sp in sorted(char.spells, key=lambda x: (x.level, x.name))
                         if sp.class_id in (None, cls.id) and (sp.srd_index or sp.name) not in taken
                         and sp.level <= info["max_level"] and (not ch.spell_exact or sp.level == ch.spell_level)
                         and (not ch.spell_school or normalize_school(sp.school) == ch.spell_school)
                         and not (ch.spell_pick == "known" and sp.id in free)]
    return info


def spell_pick_target(char: Character, pick_id: str, level: int, class_id: int | None, name: str,
                      srd_index: str | None, is_ritual: bool = True, school: str | None = None) -> tuple[CharacterClass, object]:
    """Controlla che la scelta esista e che l'incantesimo sia ammesso; restituisce classe e ``ChoiceSpec``."""
    choice = next((c for c in char.pending_choices or [] if c.get("id") == pick_id), None)
    cls = _class_by_key(char, choice.get("class_key")) if choice else None
    ch = _choice_spec(char, cls, choice.get("group")) if cls else None
    if ch is None or not ch.spell_pick:
        raise HTTPException(404, detail={"code": "choice_not_found"})
    if class_id is not None and class_id != cls.id:
        raise HTTPException(400, detail={"code": "bad_class"})
    if level > _pick_cap(char, cls, ch) or (ch.spell_exact and level != ch.spell_level):
        raise HTTPException(422, detail={"code": "spell_pick_level"})
    if ch.spell_ritual and not is_ritual:
        raise HTTPException(422, detail={"code": "spell_pick_ritual"})
    if ch.spell_school and normalize_school(school) != ch.spell_school:  # Sapienti del Mago 2024: solo la propria scuola
        raise HTTPException(422, detail={"code": "spell_pick_school"})
    lowered = name.strip().lower()
    if any((srd_index and s.srd_index == srd_index) or s.name.strip().lower() == lowered for s in char.spells):
        raise HTTPException(409, detail={"code": "spell_already_known"})
    return cls, ch


def consume_spell_pick(session: AsyncSession, char: Character, cls: CharacterClass, ch, spell) -> None:
    """L'incantesimo è stato aggiunto: la scelta scala di uno; un extra non entra nel conteggio dei conosciuti."""
    cls.options = {**(cls.options or {}), ch.group: [*(cls.options or {}).get(ch.group, []), spell.srd_index or spell.name]}
    if ch.spell_pick == "book":
        spell.in_spellbook = True
    if ch.always_prepared:  # Scoperte Magiche: sempre preparato e fuori dal limite
        spell.always_prepared = spell.is_prepared = True
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


TOME_GROUPS = ("tome_cantrips", "tome_rituals")


async def reopen_tome(session: AsyncSession, char: Character) -> None:
    """Patto del Tomo (a ogni riposo): il Libro delle Ombre si evoca di nuovo e le sue scelte tornano da fare. Gli incantesimi
    scelti per il Libro (quelli fuori dal limite dei conosciuti) si tolgono, le scelte tornano in coda."""
    from core.rules.catalog import active_features  # import locale
    if not any(spec.key == "warlock.pact_of_the_tome" for spec, _row in active_features(char)):
        raise HTTPException(422, detail={"code": "no_pact_of_the_tome"})
    free = set((char.settings or {}).get(FREE_KNOWN_KEY) or [])
    for cls in char.classes:
        options = dict(cls.options or {})
        for group in TOME_GROUPS:
            taken = options.get(group) or []
            for spell in [s for s in char.spells or [] if (s.srd_index or s.name) in taken and s.id in free]:
                free.discard(spell.id)
                await session.delete(spell)
            options[group] = []
        cls.options = options
    char.settings = {**(char.settings or {}), FREE_KNOWN_KEY: sorted(free)}
    await session.flush()
    await session.refresh(char, attribute_names=["spells"])
    reconcile_choices(char)
    _history(session, char, "Libro delle Ombre: scelte da rifare")


def _check_feat(char: Character, spec, boon: bool, origin: str = "level") -> None:
    """Edizione, categoria e prerequisiti (livello, caratteristica, incantesimi) di un talento.

    ``origin``: ``level`` (scelta ASI o Dono Epico), ``manual`` («Aggiungi talento»: nessuna categoria né livello minimo,
    salvo i Doni Epici) o ``creation`` (solo talenti d'Origine)."""
    if spec.edition != character_edition(char):
        raise _bad("feat_wrong_edition")
    if origin == "creation" and spec.category != "origin":
        raise _bad("feat_wrong_category")
    if origin == "level" and (spec.category == "epic_boon") != boon:
        raise _bad("feat_wrong_category")
    if (origin == "level" or spec.category == "epic_boon") and char.total_level < spec.min_level:
        raise _bad("feat_prerequisite_level")
    if spec.prereq_abilities:
        names, minimum = spec.prereq_abilities
        if not any(_score_row(char, n).value >= minimum for n in names):
            raise _bad("feat_prerequisite_ability")
    if spec.needs_spellcasting and not any(c.spellcasting_ability for c in char.classes):
        raise _bad("feat_prerequisite_spellcasting")
    if spec.prereq_armor and not armor_trained(char, spec.prereq_armor):
        raise _bad("feat_prerequisite_armor")
    if spec.needs_fighting_style:
        if not has_fighting_style(char):
            raise _bad("feat_prerequisite_style")
        if spec.key[len("2024_fs_"):] in styles_taken(char):
            raise _bad("feat_style_taken")


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
    add_history(session, char.id, "level_choice", f"Scelta di livello: {text}")


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
    if feat_key == "custom":
        name = (custom_name or "").strip()
        if not name:
            raise _bad("custom_name is required")
        session.add(Ability(character_id=char.id, name=name[:200], description=custom_text or None,
                            is_passive=True, feature_key="feat.custom"))
        _history(session, char, name)
        return
    take_feat(session, char, feat_key, ability, lang, "level", boon=boon)


def take_feat(session: AsyncSession, char: Character, feat_key: str, ability: Optional[str], lang: str,
              origin: Literal["level", "manual", "creation"], boon: bool = False) -> Ability:
    """Il talento entra sulla scheda per intero (+1 alla caratteristica, TS di Resiliente); effetti e usi dal motore
    al sync che segue. Le scelte proprie del talento (``FEAT_NEEDS``) si completano dopo, con ``complete_feat``."""
    spec = FEATS.get(feat_key)
    if spec is None:
        raise _bad(f"Unknown feat '{feat_key}'")
    _check_feat(char, spec, boon, origin)
    if not spec.repeatable and any(a.feature_key == f"feat.{feat_key}" for a in char.abilities):
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
    ability_row = Ability(
        character_id=char.id, name=name, description=spec.summary.get(lang) or spec.summary["it"], is_passive=True,
        feature_key=f"feat.{spec.key}", restoration_type=RestorationType.NONE,
        options={"ability": ability} if spec.ability_increase else None)
    session.add(ability_row)
    char.abilities.append(ability_row)  # gli effetti e gli usi li dà il motore al sync che segue
    if origin == "level":
        _history(session, char, name)
    else:
        add_history(session, char.id, "level_choice", f"Talento aggiunto: {name}")
    return ability_row


_MI_LISTS = ("cleric", "druid", "wizard")
_MI_ABILITIES = ("intelligence", "wisdom", "charisma")


_SRD_DIR = Path(__file__).resolve().parents[2] / "webapp" / "src" / "data" / "srd"


@dataclass(frozen=True)
class SrdSpell:
    level: int
    classes: frozenset[str]
    school: str
    ritual: bool


@lru_cache(maxsize=2)
def _srd_spells(edition: str) -> dict[str, SrdSpell]:
    """Catalogo SRD della webapp, per indice. Lo stesso file da cui la webapp sceglie."""
    name = "spells-2024.json" if edition == "2024" else "spells.json"
    items = json.loads((_SRD_DIR / name).read_text(encoding="utf-8"))["items"]
    return {e["index"]: SrdSpell(e["level"], frozenset(e.get("classes") or []), str(e.get("school") or ""), bool(e.get("ritual")))
            for e in items}


def _text_list(value: Any, count: int) -> list[str]:
    items = [str(v).strip()[:50] for v in value] if isinstance(value, list) else []
    if len(items) != count or not all(items) or len({i.lower() for i in items}) != count:
        raise _bad("feat_options_invalid")
    return items


def _add_tools(char: Character, names: list[str]) -> None:
    cats = normalize(char.general_proficiencies)
    have = {t.lower() for t in cats["tools"]}
    cats["tools"] = [*cats["tools"], *(n for n in names if n.lower() not in have)]
    char.general_proficiencies = cats  # riassegnato: la colonna JSON non traccia le mutazioni


# Scelte di abilità dei talenti 2024: quelle ammesse (None = tutte)
_SKILL_CHOICES: dict[str, tuple[str, ...] | None] = {
    "feat.2024_keen_mind": ("arcana", "history", "investigation", "nature", "religion"),
    "feat.2024_observant": ("insight", "investigation", "perception"),
    "feat.2024_skill_expert": None,
}
_ADEPT_TYPES = ("acid", "cold", "fire", "lightning", "thunder")
_TOUCHED_SCHOOLS = {"feat.2024_fey_touched": ("divination", "enchantment"),
                    "feat.2024_shadow_touched": ("illusion", "necromancy")}


def _checked_spells(char: Character, spells: list, ok) -> list[str]:
    """Indici SRD degli incantesimi scelti, validati sul catalogo (livello e scuola dal catalogo, non dal client)."""
    catalog = _srd_spells(character_edition(char))
    indexes = [(sp.srd_index or "").strip() for sp in spells]
    if (len(set(indexes)) != len(indexes) or any(i not in catalog or not ok(catalog[i]) for i in indexes)
            or any(sp.level != catalog[i].level for sp, i in zip(spells, indexes))):
        raise _bad("feat_options_invalid")
    return indexes


def _add_feat_spells(session: AsyncSession, char: Character, spells: list, indexes: list[str]) -> list[str]:
    """Righe degli incantesimi del talento, sempre preparate e senza duplicati. Restituisce quelli che il talento ha reso
    sempre preparati (gli altri lo erano già per un'altra fonte e lo restano alla rimozione)."""
    granted: list[str] = []
    for data, index in zip(spells, indexes):
        have = next((sp for sp in char.spells if sp.srd_index == index or sp.name == data.name), None)
        if have is None:
            have = Spell(character_id=char.id, **data.model_dump(exclude={"pick_id", "class_id", "always_prepared", "is_prepared"}))
            session.add(have)
            char.spells.append(have)
        if not have.always_prepared:
            granted.append(index)
        have.always_prepared = have.is_prepared = True
    return granted


def _choose_skill(char: Character, key: str, options: dict, needs: tuple[str, ...]) -> dict[str, Any]:
    """Mente acuta, Osservatore: competenza, o Maestria se già competente. Esperto di abilità: una competenza nuova e
    una Maestria in un'abilità in cui si è competenti (anche quella appena presa)."""
    allowed = _SKILL_CHOICES.get(key, ())
    skill = options.get("skill")
    if skill not in (allowed if allowed is not None else SKILL_ABILITY_MAP):
        raise _bad("feat_options_invalid")
    current = dict(char.skills or {})
    if "expertise" in needs:  # Esperto di abilità
        expertise = options.get("expertise")
        if current.get(skill) or expertise not in SKILL_ABILITY_MAP or not (current.get(expertise) or expertise == skill):
            raise _bad("feat_options_invalid")
        current[skill] = True
        current[expertise] = "expert"
        char.skills = current
        return {"skill": skill, "expertise": expertise}
    current[skill] = "expert" if current.get(skill) else True
    char.skills = current
    return {"skill": skill}


def complete_feat(session: AsyncSession, char: Character, ability: Ability, options: dict, spells: list) -> None:
    """Le scelte di un talento (``FEAT_NEEDS``), una volta sola: abilità, strumenti, tipo di danno, padronanza e
    incantesimi (sempre preparati, senza duplicati, validati sul catalogo SRD)."""
    from core.rules.catalog.feats import FEAT_NEEDS, feat_status  # import locale come in active_features
    from core.rules.catalog.feats_2024 import ENERGY_TYPES
    from core.rules.weapons import WEAPONS
    key = ability.feature_key or ""
    needs = FEAT_NEEDS.get(key, ())
    if not needs:
        raise _bad("feat_has_no_options")
    if feat_status(char, ability) != "incomplete":
        raise HTTPException(409, detail={"code": "feat_already_complete"})
    others = [a for a in char.abilities if a is not ability and a.feature_key == key]  # le altre istanze (ripetibili)
    saved: dict[str, Any] = {}
    if "picks" in needs:
        picks = _text_list(options.get("picks"), 3)
        skills = [p for p in picks if not p.startswith("tool:")]
        tools = [p[len("tool:"):].strip() for p in picks if p.startswith("tool:")]
        if any(s not in SKILL_ABILITY_MAP for s in skills) or not all(tools):
            raise _bad("feat_options_invalid")
        current = dict(char.skills or {})
        for s in skills:
            current[s] = "expert" if current.get(s) == "expert" else True
        char.skills = current
        _add_tools(char, tools)
        saved["picks"] = picks
    for name in ("tools", "instruments"):
        if name in needs:
            saved[name] = _text_list(options.get(name), 3)
            _add_tools(char, saved[name])
    if "skill" in needs:
        saved.update(_choose_skill(char, key, options, needs))
    elif "expertise" in needs:  # Dono dell'Abilità: competenza in tutte (dal motore) e Maestria in una
        expertise = options.get("expertise")
        if expertise not in SKILL_ABILITY_MAP:
            raise _bad("feat_options_invalid")
        char.skills = {**(char.skills or {}), expertise: "expert"}
        saved["expertise"] = expertise
    if "damage_types" in needs:  # Dono della Resistenza all'energia: due tipi diversi
        types = options.get("damage_types")
        if not isinstance(types, list) or len(set(types)) != 2 or len(types) != 2 or any(t not in ENERGY_TYPES for t in types):
            raise _bad("feat_options_invalid")
        saved["damage_types"] = list(types)
    if "damage_type" in needs:  # Adepto elementale: un tipo per istanza
        chosen = options.get("damage_type")
        if chosen not in _ADEPT_TYPES:
            raise _bad("feat_options_invalid")
        if any((a.options or {}).get("damage_type") == chosen for a in others):
            raise _bad("feat_type_taken")
        saved["damage_type"] = chosen
    if "weapon_mastery" in needs:  # Maestro d'armi
        weapons = options.get("weapon_mastery")
        if not isinstance(weapons, list) or len(weapons) != 1 or weapons[0] not in WEAPONS:
            raise _bad("feat_options_invalid")
        saved["weapon_mastery"] = list(weapons)
    if "list" in needs:  # Iniziato alla magia
        chosen, stat = options.get("list"), options.get("ability")
        if chosen not in _MI_LISTS or stat not in _MI_ABILITIES:
            raise _bad("feat_options_invalid")
        if any((a.options or {}).get("list") == chosen for a in others):
            raise _bad("feat_list_taken")
        # il lancio gratuito vale solo per un incantesimo della lista scelta
        indexes = _checked_spells(char, spells, lambda s: chosen in s.classes)
        if len(indexes) != 3 or sorted(sp.level for sp in spells) != [0, 0, 1]:
            raise _bad("feat_options_invalid")
        granted = _add_feat_spells(session, char, spells, indexes)
        saved.update({"list": chosen, "ability": stat, "granted": granted,
                      "cantrips": [i for sp, i in zip(spells, indexes) if sp.level == 0],
                      "spell": [i for sp, i in zip(spells, indexes) if sp.level == 1]})
    elif "spell" in needs:  # Toccato dalle fate / dall'ombra: un incantesimo di 1º livello delle due scuole
        schools = _TOUCHED_SCHOOLS[key]
        indexes = _checked_spells(char, spells, lambda s: s.level == 1 and s.school in schools)
        if len(indexes) != 1:
            raise _bad("feat_options_invalid")
        saved.update({"spell": indexes, "granted": _add_feat_spells(session, char, spells, indexes)})
    if "rituals" in needs:  # Incantatore rituale: tanti rituali di 1º livello quanto il bonus di competenza
        indexes = _checked_spells(char, spells, lambda s: s.level == 1 and s.ritual)
        if len(indexes) != char.proficiency_bonus:
            raise _bad("feat_options_invalid")
        saved.update({"rituals": indexes, "granted": _add_feat_spells(session, char, spells, indexes)})
    ability.options = {**(ability.options or {}), **saved}
    add_history(session, char.id, "level_choice", f"Talento completato: {ability.name}")


def _feat_spells(ability: Ability) -> set[str]:
    opts = ability.options or {}
    return {*(opts.get("cantrips") or []), *(opts.get("spell") or []), *(opts.get("rituals") or [])}


async def remove_feat(session: AsyncSession, char: Character, ability: Ability) -> None:
    """Rimuove un talento: la riga (e con lei gli effetti del motore) ed eventuali regole homebrew `feat:*` rimaste.
    Gli aumenti di caratteristica e la competenza nei TS NON vengono annullati (stato precedente non tracciato)."""
    key = (ability.feature_key or "")[len("feat."):]
    name = ability.name
    if key == "custom":
        await session.execute(delete(Ability).where(Ability.id == ability.id))
    else:
        # Iniziato alla magia: gli incantesimi restano; non più sempre preparati quelli che il talento aveva reso tali
        # e che nessun altro talento concede ancora
        others = set().union(*(_feat_spells(a) for a in char.abilities if a is not ability and a.id != ability.id))
        mine = set((ability.options or {}).get("granted") or []) - others
        for spell in char.spells:
            if (spell.srd_index or spell.name) in mine:
                spell.always_prepared = False
        await session.execute(delete(Ability).where(Ability.id == ability.id))  # una sola istanza (talenti ripetibili)
        # Regole `feat:*` di personaggi non ancora migrati al motore (vedi ``catalog_migration``)
        await session.execute(delete(HomebrewRule).where(
            HomebrewRule.character_id == char.id, HomebrewRule.template_id == f"feat:{key}"))
    add_history(session, char.id, "level_choice", f"Talento rimosso: {name}")

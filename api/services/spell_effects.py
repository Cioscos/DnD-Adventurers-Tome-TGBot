"""Lancio di un incantesimo con effetto sui bersagli: validazione prima della spesa, stati sui bersagli e orologio sul lanciatore.

Ogni stato ``spell:<chiave>`` sul bersaglio non ha durata propria: la scandisce lo stato ``spell_cast:<chiave>`` di chi lancia
(round, concentrazione, riposo). Alla chiusura dell'orologio ``settle_closed`` segna i bersagli da liberare e il flush
della richiesta (``api.services.effects``) toglie loro lo stato."""
from __future__ import annotations

from types import SimpleNamespace

from fastapi import HTTPException, status
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.spell import SpellEffectsRead
from api.services.effects import apply_heal, cap_hp_to_max, grant_temp_hp
from api.services.homebrew.passive import get_passive_modifiers
from api.services.session_allies import ally_target
from core.db.models import Character, GameSession, Item, SessionParticipant, SessionStatus
from core.game.item_bonuses import is_magic_item
from core.rules.catalog.spells import SPELL_EFFECTS, spell_effect
from core.rules.edition import character_edition
from core.game.stats import effective_ability_mod
from core.rules.spellcasting import best_caster, spell_stats
from core.rules.roll_options import _spend_state_token
from core.rules.spell_effects import SPELL_CLOCK_PREFIX, SPELL_STATE_PREFIX, SpellEffect, SpellVariant
from core.data.damage_types import canonical_damage_type
from core.rules.states import SPELL_CAST_TYPE, SPELL_GIVEN, SPELL_RELEASE, SPELL_TEMP_DROPPED, begin_state, forget_spell_temp_drop, note_spell_temp_hp, settle_closed
from core.rules.types import StateSpec

_OUTSIDE_TEXT = {"it": "Fuori da una serata l'effetto non si applica da solo: lo applica il GM ai bersagli.",
                 "en": "Outside an evening the effect is not applied automatically: the GM applies it to the targets."}
_AURA_TEXT = {"it": "L'aura vale per tutti i personaggi seduti alla serata finché dura: sta al GM escludere chi è lontano.",
              "en": "The aura applies to everyone seated at the evening while it lasts: the GM leaves out whoever is far away."}
_NO_SHEET_TEXT = {"it": "L'effetto non è sulla scheda di nessun personaggio: riferiscilo al GM.",
                  "en": "The effect is not on any character's sheet: tell the GM."}


def cast_level(char: Character, spell, slot_id: int | None, slot_level: int | None) -> int:
    """Il livello a cui si lancia: quello dello slot scelto (per id o per livello), altrimenti il livello dell'incantesimo."""
    if slot_id is not None:
        slot_level = next((s.level for s in char.spell_slots if s.id == slot_id), slot_level)
    return slot_level if slot_level and slot_level >= spell.level else spell.level


def _invalid(code: str, http: int = status.HTTP_422_UNPROCESSABLE_ENTITY) -> HTTPException:
    return HTTPException(http, detail={"code": code})


async def _seated(session: AsyncSession, char: Character) -> bool:
    row = await session.execute(
        select(SessionParticipant.id).join(GameSession, GameSession.id == SessionParticipant.session_id)
        .where(SessionParticipant.character_id == char.id, GameSession.status == SessionStatus.ACTIVE).limit(1))
    return row.first() is not None


def _check_choices(variant: SpellVariant, edition: str, choices: dict[str, str] | None) -> dict[str, str]:
    chosen = dict(choices or {})
    item = chosen.pop("item_id", None) if variant.weapon_choice else None  # l'arma è del bersaglio: si controlla quando i bersagli sono noti
    if item is not None and not (isinstance(item, str) and item.isdigit()):
        raise _invalid("invalid_choice")
    wanted = {c.key: c.options(edition) for c in variant.choices}
    if set(chosen) != set(wanted) or any(chosen[k] not in opts for k, opts in wanted.items()):
        raise _invalid("invalid_choice")
    if item is not None:
        chosen["item_id"] = item
    return chosen


async def plain_weapons(session: AsyncSession, char_id: int) -> list[Item]:
    """Le armi senza bonus magico di un personaggio: quelle che Arma Magica e Arma Elementale possono incantare."""
    rows = await session.execute(select(Item).where(Item.character_id == char_id, Item.item_type == "weapon").order_by(Item.id))
    return [i for i in rows.scalars() if not is_magic_item(i)]


async def _check_weapon(session: AsyncSession, variant: SpellVariant, target: Character, chosen: dict[str, str]) -> None:
    """422 ``invalid_choice`` se l'arma scelta manca o non è un'arma non magica del bersaglio."""
    if variant.weapon_choice and "item_id" not in chosen:
        raise _invalid("invalid_choice")
    if variant.weapon_choice and int(chosen["item_id"]) not in {i.id for i in await plain_weapons(session, target.id)}:
        raise _invalid("invalid_choice")


async def _resolve(session: AsyncSession, caster: Character, spell, slot_level: int,
                   targets: list[int] | None, choices: dict[str, str] | None):
    """``(effetto, variante, bersagli, scelte, fuori_serata)`` o ``None`` se l'incantesimo non è nel catalogo.
    Tutti i rifiuti (422 ``invalid_target`` / ``invalid_choice``, 409 ``target_dead``) escono da qui, prima di spendere."""
    edition = character_edition(caster)
    found = spell_effect(edition, spell.srd_index, spell.name)
    if found is None:
        return None
    effect, variant = found
    chosen = _check_choices(variant, edition, choices)
    if effect.target.kind in ("self", "aura") or targets is None:  # l'aura è del lanciatore: nessun bersaglio
        await _check_weapon(session, variant, caster, chosen)
        return effect, variant, [caster], chosen, False
    if len(targets) != len(set(targets)) or len(targets) > effect.max_targets(edition, slot_level):
        raise _invalid("invalid_target")
    others = [t for t in targets if t != caster.id]
    outside = bool(others) and not await _seated(session, caster)
    chars = [caster] if caster.id in targets else []
    if not outside:
        for tid in others:
            ally = await ally_target(session, caster, tid)
            if ally.is_dead:
                raise _invalid("target_dead", status.HTTP_409_CONFLICT)
            chars.append(ally)
    if not outside and chars:
        await _check_weapon(session, variant, chars[0], chosen)
    else:
        chosen.pop("item_id", None)  # nessuna scheda bersaglio: nessuna scelta d'arma, l'effetto va al GM come testo
    return effect, variant, chars, chosen, outside


async def validate_spell_targets(session: AsyncSession, caster: Character, spell, slot_level: int,
                                 targets: list[int] | None, choices: dict[str, str] | None
                                 ) -> tuple[SpellEffect, SpellVariant, list[Character]] | None:
    """Da chiamare prima della spesa del lancio. ``None``: l'incantesimo non ha un effetto nel catalogo."""
    resolved = await _resolve(session, caster, spell, slot_level, targets, choices)
    return resolved and resolved[:3]


def _damage_choice(char: Character, spell):
    """``(effetto, scelta del tipo di danno inflitto)`` dell'incantesimo nell'edizione di chi lancia, o ``None``."""
    found = spell_effect(character_edition(char), spell.srd_index, spell.name)
    choice = next((c for c in found[1].choices if c.key == "damage_type" and c.inflicts), None) if found else None
    return (found[0], choice) if choice else None


def resists_chosen_type(char: Character, spell) -> bool:
    """Il tipo scelto al lancio è un tipo a cui si resiste (Protezione dall'Energia), non un danno inflitto."""
    found = spell_effect(character_edition(char), spell.srd_index, spell.name)
    return bool(found) and any(c.key == "damage_type" and not c.inflicts for c in found[1].choices)


def cast_damage_type(char: Character, spell, choices: dict[str, str] | None) -> str | None:
    """Il tipo di danno inflitto scelto in un lancio (non quello a cui si resiste): per le opzioni del lancio."""
    return canonical_damage_type((choices or {}).get("damage_type")) if _damage_choice(char, spell) else None


def chosen_damage_type(char: Character, spell, requested: str | None) -> str | None:
    """Il tipo di danno scelto al lancio, per il tiro di danno: quello dell'ultimo lancio di questo incantesimo o, per uno con durata,
    quello dell'orologio. 422 ``invalid_choice`` se manca o se la richiesta ne indica un altro. ``None``: l'incantesimo non offre la scelta."""
    found = _damage_choice(char, spell)
    if found is None:
        if requested is not None:
            raise _invalid("invalid_choice")
        return None
    effect = found[0]
    stored = ((char.settings or {}).get(SPELL_CAST_TYPE) or {}).get(effect.key)
    if stored is None:
        clock = next((s for s in char.active_states or [] if s.get("key") == f"{SPELL_CLOCK_PREFIX}{effect.key}"), None)
        stored = (((clock or {}).get("data") or {}).get("state_data") or {}).get("choices", {}).get("damage_type")
    if stored is None or (requested is not None and requested != stored):
        raise _invalid("invalid_choice")
    return stored


def _remember_cast_type(caster: Character, effect_key: str | None, choice_type: str | None) -> None:
    """Il tipo scelto in un lancio, per incantesimo: scrive solo la voce di questo incantesimo (un lancio senza scelta la toglie,
    gli altri non la toccano). Resta piccolo: ha solo gli incantesimi del catalogo con scelta del tipo."""
    if not effect_key:
        return
    types = dict((caster.settings or {}).get(SPELL_CAST_TYPE) or {})
    if choice_type:
        types[effect_key] = choice_type
    elif not types.pop(effect_key, None):
        return
    caster.settings = {**(caster.settings or {}), SPELL_CAST_TYPE: types}


def end_unarmored_spells(char: Character) -> None:
    """Chi indossa un'armatura perde Armatura Magica: l'incantesimo termina (il flush chiude anche l'orologio di chi l'ha lanciato)."""
    if any(s.get("key") == "spell:mage_armor" for s in char.active_states or []):
        _spend_state_token(char, "spell:mage_armor")


async def _drop_state(session: AsyncSession, target: Character, key: str, caster_id: int) -> None:
    states = target.active_states or []
    kept = [s for s in states if not (s.get("key") == key and (s.get("data") or {}).get("caster_id") == caster_id)]
    if len(kept) != len(states):
        target.active_states = kept
        settle_closed(target, [s for s in states if s not in kept])  # la condizione imposta (Invisibile) cade con lo stato
        cap_hp_to_max(target, [s for s in states if s not in kept], await get_passive_modifiers(session, target, "character.hit_points_max"))


def _stateful(variant: SpellVariant, data: dict) -> bool:
    return bool(variant.modifiers(data) or variant.options or variant.track or variant.condition
                or variant.turn_heal or variant.turn_temp_hp)


async def _give_hp(session: AsyncSession, target: Character, variant: SpellVariant, data: dict, state_key: str | None = None) -> None:
    """I PF dell'incantesimo al bersaglio: i temporanei (il maggiore vince) e la cura, dopo che lo stato ha alzato il massimo."""
    if variant.temp_hp and (amount := variant.temp_hp(data)) > 0:
        if grant_temp_hp(session, target, amount)["applied"] and variant.temp_hp_ends and state_key:
            note_spell_temp_hp(target, state_key, amount)  # a fine incantesimo svaniscono solo se sono ancora questi
    if variant.heal and (amount := variant.heal(data)) > 0:
        if missing := {"classes", "items", "ability_scores"} & inspect(target).unloaded:  # un alleato arriva senza le relazioni dei massimi
            await session.refresh(target, attribute_names=list(missing))
        await apply_heal(session, target, amount)


def spell_state_spec(key: str, data: dict) -> StateSpec:
    """Lo stato ``spell:*`` di un bersaglio con ciò che la variante dell'edizione impone (condizione, immunità, fini)."""
    effect = SPELL_EFFECTS.get(data.get("spell_key"))
    variant = effect and effect.variants.get(data.get("edition", "2014"))
    extra = {"condition": variant.condition, "immune_conditions": variant.immune_conditions, "ends_on": variant.ends_on} if variant else {}
    return StateSpec(key, data=dict(data), **{"ends_on": ("manual",), **extra})


async def apply_spell_effects(session: AsyncSession, caster: Character, spell, slot_level: int,
                              targets: list[int] | None, choices: dict[str, str] | None) -> SpellEffectsRead | None:
    """Dopo la spesa: uno stato per bersaglio e l'orologio su chi lancia. Fuori serata (o per un effetto solo descrittivo)
    nessuno stato e un testo per il GM."""
    resolved = await _resolve(session, caster, spell, slot_level, targets, choices)
    if resolved is None:
        _remember_cast_type(caster, None, None)
        return None
    effect, variant, chars, chosen, outside = resolved
    inflicts = any(c.key == "damage_type" and c.inflicts for c in variant.choices)
    _remember_cast_type(caster, effect.key, chosen.get("damage_type") if inflicts else None)
    data = {"spell_key": effect.key, "slot_level": slot_level, "choices": chosen, "caster_id": caster.id,
            "caster_name": caster.name, "edition": character_edition(caster),
            "duration": {"rounds": variant.duration(slot_level), "concentration": variant.concentration, "until_rest": variant.until_rest},
            "targets": len(chars)}
    if variant.turn_temp_hp:  # Eroismo: il modificatore da incantatore di chi lancia, fissato ora
        stats = spell_stats(caster, spell) if hasattr(spell, "class_id") else best_caster(caster)  # l'oggetto concede un incantesimo senza classe
        data["cast_mod"] = effective_ability_mod(caster, stats.ability) if stats else 0
    if variant.weapon_choice and chars and chosen.get("item_id") and (weapon := await session.get(Item, int(chosen["item_id"]))):
        data["weapon_name"] = weapon.name  # lo stato dice quale arma è incantata
    if variant.on_close:  # Velocità: la letargia che il bersaglio avrà alla fine
        data["on_close"] = variant.on_close(data)
    if variant.needs_dc:  # la CD dei TS delle punizioni, fissata ora
        stats = spell_stats(caster, spell) if hasattr(spell, "class_id") else best_caster(caster)
        data["save_dc"] = stats.save_dc if stats else 8 + caster.proficiency_bonus
    if variant.choices and not variant.text and not (_stateful(variant, data) or variant.temp_hp or variant.heal):
        return SpellEffectsRead(applied=[])  # solo una scelta (il tipo di danno): viaggia con il tiro di danno, nulla da dire al GM
    if not chars or not (_stateful(variant, data) or variant.temp_hp or variant.heal):  # nessun personaggio: l'effetto lo applica il GM
        return SpellEffectsRead(applied=[], text=variant.text or (_OUTSIDE_TEXT if outside else _NO_SHEET_TEXT))
    if not _stateful(variant, data):  # istantaneo: solo PF, nessuno stato né orologio
        for target in chars:
            await _give_hp(session, target, variant, {**data, **(variant.per_target(data) if variant.per_target else {})})
        return SpellEffectsRead(applied=[{"id": c.id, "name": c.name} for c in chars], text=variant.text or (_OUTSIDE_TEXT if outside else None))
    key, clock = f"{SPELL_STATE_PREFIX}{effect.key}", f"{SPELL_CLOCK_PREFIX}{effect.key}"
    settings = dict(caster.settings or {})
    given = dict(settings.get(SPELL_GIVEN) or {})
    for old in set(given.get(clock, [])) - {c.id for c in chars}:  # lanciato di nuovo su altri: i vecchi bersagli lo perdono
        previous = caster if old == caster.id else await session.get(Character, old)
        if previous is not None:
            await _drop_state(session, previous, key, caster.id)
    aura = effect.target.kind == "aura"  # l'aura è viva: solo l'orologio del lanciatore, nessuno stato sui bersagli
    applied = []
    for target in [] if aura else chars:
        mine = {**data, **(variant.per_target(data) if variant.per_target else {})}
        begin_state(target, spell_state_spec(key, mine), key, spell.name)
        forget_spell_temp_drop(target, key)  # la voce del lancio precedente non vale per l'annullo di questo
        if variant.on_apply:
            variant.on_apply(target, mine)
        await _give_hp(session, target, variant, mine, key)
        applied.append({"id": target.id, "name": target.name})
    ends = [*(["concentration_end"] if variant.concentration else []), *(["rest_long"] if variant.until_rest else []), *variant.clock_ends_on]
    begin_state(caster, StateSpec(clock, rounds=variant.duration(slot_level), ends_on=tuple(ends) or ("manual",), data={"spell_key": effect.key, "state_data": data}),
                clock, spell.name)
    settings = dict(caster.settings or {})  # riletto: la chiusura del lancio precedente può averlo cambiato
    regranted = {(a["id"], key) for a in applied}
    pending = [e for e in settings.get(SPELL_RELEASE) or [] if (e["id"], e["key"]) not in regranted]  # chiuso e riaperto nella stessa richiesta
    settings[SPELL_GIVEN] = {**(settings.get(SPELL_GIVEN) or {}), clock: [a["id"] for a in applied]}  # per l'aura: vuoto
    if pending:
        settings[SPELL_RELEASE] = pending
    else:
        settings.pop(SPELL_RELEASE, None)
    caster.settings = settings
    text = {k: f"{variant.text[k]} {_AURA_TEXT[k]}" for k in _AURA_TEXT} if aura and variant.text else _AURA_TEXT if aura else variant.text  # l'aura non è «su <lanciatore>»
    return SpellEffectsRead(applied=applied, text=text or (_OUTSIDE_TEXT if outside else None))


async def regrant_spells(session: AsyncSession, caster: Character, before_given: dict | None) -> None:
    """Un annullo ha riaperto l'orologio ``spell_cast:*`` che la chiusura aveva spento: i bersagli riavuti ritrovano lo stato
    (ricostruito dai dati dell'orologio) e ``SPELL_GIVEN`` torna. Un bersaglio cancellato o con lo stato di un altro lanciatore si salta."""
    settings = dict(caster.settings or {})
    given = dict(settings.get(SPELL_GIVEN) or {})
    for clock, ids in (before_given or {}).items():
        state = next((s for s in caster.active_states or [] if s.get("key") == clock), None)
        if clock in given or state is None or not (state.get("data") or {}).get("state_data"):
            continue
        key = SPELL_STATE_PREFIX + state["data"]["spell_key"]
        back = []
        for tid in ids:
            target = caster if tid == caster.id else await session.get(Character, tid)
            held = next((s for s in (target.active_states or []) if s.get("key") == key), None) if target is not None else None
            if target is None or (held and (held.get("data") or {}).get("caster_id") != caster.id):
                continue
            if held is None:
                begin_state(target, spell_state_spec(key, state["data"]["state_data"]), key, state.get("name"))
                if offer := state["data"]["state_data"].get("on_close"):  # lo stato che la chiusura aveva lasciato (la letargia) non ha più motivo di esserci
                    await _drop_state(session, target, offer["key"], caster.id)
                lost = (target.settings or {}).get(SPELL_TEMP_DROPPED, {}).get(key)  # i PF temporanei che la chiusura le aveva tolto
                if lost and lost["caster_id"] == caster.id and not target.temp_hp:
                    target.temp_hp = lost["amount"]
                    note_spell_temp_hp(target, key, lost["amount"])
                forget_spell_temp_drop(target, key)
            back.append(tid)
        given[clock] = back
    caster.settings = {**settings, SPELL_GIVEN: given} if given else settings


def item_spell(spell: dict) -> SimpleNamespace:
    """L'incantesimo concesso da un oggetto (un dict dei metadati) con la forma che il servizio si aspetta."""
    return SimpleNamespace(name=spell.get("name"), srd_index=spell.get("srd_index"), level=int(spell.get("level") or 1))

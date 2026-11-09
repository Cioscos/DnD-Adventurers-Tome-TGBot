"""PF e incantesimi in corso: inizio turno del bersaglio (Rigenerazione, Eroismo), danno condiviso, ritorsione e fine a PF temporanei esauriti."""
from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.effects import _add_history, apply_heal, grant_temp_hp, sync_zero_hp
from api.services.rules_states import on_damage
from core.db.models import Character
from core.rules.catalog.spells import SPELL_EFFECTS
from core.rules.modifiers import effective_hp_max
from core.rules.roll_options import _spend_state_token
from core.rules.spell_effects import SPELL_STATE_PREFIX, SpellVariant


def spell_states(char: Character) -> list[tuple[dict, SpellVariant, dict]]:
    """Gli stati ``spell:*`` della scheda con la variante dell'edizione di chi ha lanciato e i loro ``data``."""
    out = []
    for state in char.active_states or []:
        key = str(state.get("key", ""))
        if not key.startswith(SPELL_STATE_PREFIX):
            continue
        data = state.get("data") or {}
        effect = SPELL_EFFECTS.get(data.get("spell_key") or key[len(SPELL_STATE_PREFIX):])
        variant = effect and effect.variants.get(data.get("edition", "2014"))
        if variant:
            out.append((state, variant, data))
    return out


async def spell_turn_start(session: AsyncSession, char: Character) -> tuple[int, list[dict]]:
    """Inizio del turno di ``char``: la cura nel tempo e i PF temporanei degli incantesimi su di lui.
    Restituisce i PF curati davvero e gli avvisi per il giocatore."""
    healed, notices = 0, []
    for state, variant, data in spell_states(char):
        name = state.get("name") or data.get("spell_key")
        if variant.turn_heal and (amount := variant.turn_heal(data, char)) > 0:
            got = (await apply_heal(session, char, amount))["healed"]
            healed += got
            if got:
                notices.append({"feature_key": state["key"], "name": {"it": name, "en": name}, "amount": got})
        if variant.turn_temp_hp and (amount := variant.turn_temp_hp(data)) > 0:
            if grant_temp_hp(session, char, amount)["applied"]:
                notices.append({"feature_key": state["key"], "name": {"it": name, "en": name}, "amount": 0, "message": {
                    "it": f"{name}: ottieni {amount} PF temporanei.", "en": f"{name}: you gain {amount} temporary HP."}})
    return healed, notices


async def _share(session: AsyncSession, char: Character, name: str, caster_id: int | None, amount: int) -> None:
    """Il lanciatore subisce lo stesso danno del bersaglio: prima i suoi PF temporanei, poi i PF; a 0 PF l'incantesimo finisce."""
    caster = await session.get(Character, caster_id) if caster_id and caster_id != char.id else None
    if caster is None or caster.is_dead or amount <= 0:
        return
    if missing := {"classes", "items"} & inspect(caster).unloaded:  # servono per i PF massimi
        await session.refresh(caster, attribute_names=list(missing))
    soaked = min(caster.temp_hp or 0, amount)
    caster.temp_hp = (caster.temp_hp or 0) - soaked
    old = caster.current_hit_points
    caster.current_hit_points = max(0, old - (amount - soaked))
    _add_history(session, caster.id, "hp_change",
                 f"{name}: -{amount} PF condivisi con {char.name} ({old} → {caster.current_hit_points})",
                 meta={"op": "DAMAGE", "amount": amount, "shared_with": char.id, "to_zero": old > 0 and caster.current_hit_points == 0})
    if old > 0 and caster.current_hit_points == 0:
        if amount - soaked - old >= effective_hp_max(caster):
            caster.is_dead = True
            _add_history(session, caster.id, "death_save", "Morte istantanea (danno massiccio)")
        else:
            caster.death_saves = {"successes": 0, "failures": 0, "stable": False}
        await sync_zero_hp(session, caster, False)
        from api.services.durations import end_concentration  # import locale: durations importa questo modulo
        end_concentration(caster)
    on_damage(caster, amount - soaked)  # a 0 PF chiude l'orologio dell'incantesimo: il bersaglio perde lo stato al flush


async def spell_damage_effects(session: AsyncSession, char: Character, applied: int, had_temp: bool, lang: str) -> list[dict]:
    """Dopo un danno a ``char``: i promemoria di ritorsione per il GM, il danno condiviso col lanciatore e gli incantesimi
    che finiscono con i PF temporanei esauriti. Restituisce le notifiche da mostrare."""
    notes: list[dict] = []
    if applied <= 0:
        return notes
    for state, variant, data in spell_states(char):
        name = state.get("name") or data.get("spell_key")
        if variant.retaliation and (text := variant.retaliation(data, had_temp)):
            notes.append({"severity": "info", "message": text.get(lang) or text["it"], "rule_id": None, "rule_name": name})
        if variant.shares_damage:
            await _share(session, char, name, data.get("caster_id"), applied)
        if variant.ends_at_zero_temp and (char.temp_hp or 0) == 0:
            _spend_state_token(char, state["key"])  # l'incantesimo finisce: il flush chiude l'orologio di chi l'ha lanciato
    return notes

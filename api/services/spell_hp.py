"""PF e incantesimi in corso: inizio turno del bersaglio (Rigenerazione, Eroismo), danno condiviso, ritorsione e fine a PF temporanei esauriti."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.common import HPOp, HPUpdate
from api.services.effects import apply_heal, grant_temp_hp
from api.services.session_allies import load_receiver
from core.db.models import Character
from core.rules.catalog.spells import SPELL_EFFECTS
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


async def _share(session: AsyncSession, char: Character, name: str, caster_id: int | None, amount: int, lang: str, log: list[dict]) -> None:
    """Il lanciatore subisce lo stesso danno del bersaglio, per la stessa strada di ogni danno (PF temporanei, TS di concentrazione,
    morte, fine dell'incantesimo a 0 PF). Lo snapshot di annullo del lanciatore va in ``log``, nell'annullo del bersaglio."""
    if not caster_id or caster_id == char.id or amount <= 0:
        return
    caster = await load_receiver(session, caster_id)
    if caster.is_dead:
        return
    from api.routers.hp import apply_hp_update  # import locale: il router importa questo modulo
    await apply_hp_update(session, caster, HPUpdate(op=HPOp.DAMAGE, value=amount, damage_modifier="none"), lang,
                          shared_from=f"{name}: condivisi con {char.name}")
    if caster.hp_undo:
        log.append({"id": caster.id, **caster.hp_undo})
        caster.hp_undo = None  # si annulla dal bersaglio, non dal lanciatore


async def spell_damage_effects(session: AsyncSession, char: Character, applied: int, had_temp: bool, lang: str,
                               share: bool = True, shared_log: list[dict] | None = None) -> list[dict]:
    """Dopo un danno a ``char``: i promemoria di ritorsione per il GM, il danno condiviso col lanciatore e gli incantesimi
    che finiscono con i PF temporanei esauriti. Restituisce le notifiche da mostrare."""
    notes: list[dict] = []
    if applied <= 0:
        return notes
    for state, variant, data in spell_states(char):
        name = state.get("name") or data.get("spell_key")
        if variant.retaliation and (text := variant.retaliation(data, had_temp)):
            notes.append({"severity": "info", "message": text.get(lang) or text["it"], "rule_id": None, "rule_name": name})
        if variant.shares_damage and share:
            await _share(session, char, name, data.get("caster_id"), applied, lang, shared_log if shared_log is not None else [])
        if variant.ends_at_zero_temp and (char.temp_hp or 0) == 0:
            _spend_state_token(char, state["key"])  # l'incantesimo finisce: il flush chiude l'orologio di chi l'ha lanciato
    return notes

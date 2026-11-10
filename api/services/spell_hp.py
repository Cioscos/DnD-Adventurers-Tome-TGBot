"""PF e incantesimi in corso: inizio turno del bersaglio (Rigenerazione, Eroismo), danno condiviso, ritorsione e fine a PF temporanei esauriti."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.common import HPOp, HPUpdate
from api.services.effects import apply_heal, grant_temp_hp
from api.services.session_allies import attach_party_auras, load_receiver
from core.db.models import Character
from core.rules.roll_options import _spend_state_token
from core.rules.spell_effects import SPELL_CLOCK_PREFIX, SPELL_STATE_PREFIX, SpellVariant, spell_instances
from core.rules.states import SPELL_GIVEN, note_spell_temp_hp


def spell_states(char: Character) -> list[tuple[dict, SpellVariant, dict]]:
    """Gli incantesimi su ``char`` (stati ``spell:*`` e aure vive) con la variante dell'edizione di chi ha lanciato e i loro ``data``."""
    return [(state, variant, data) for state, _effect, variant, data in spell_instances(char)]


async def spell_turn_start(session: AsyncSession, char: Character) -> tuple[int, list[dict]]:
    """Inizio del turno di ``char``: la cura nel tempo e i PF temporanei degli incantesimi su di lui.
    Restituisce i PF curati davvero e gli avvisi per il giocatore."""
    healed, notices = 0, []
    await attach_party_auras(session, char)  # le aure vive dei compagni (Aura di Vita)
    for state, variant, data in spell_states(char):
        name = state.get("name") or data.get("spell_key")
        if variant.turn_heal and (amount := variant.turn_heal(data, char)) > 0:
            got = (await apply_heal(session, char, amount))["healed"]
            healed += got
            if got:
                notices.append({"feature_key": state["key"], "name": {"it": name, "en": name}, "amount": got})
        if variant.turn_temp_hp and (amount := variant.turn_temp_hp(data)) > 0:
            if grant_temp_hp(session, char, amount)["applied"]:
                note_spell_temp_hp(char, state["key"], amount)
                notices.append({"feature_key": state["key"], "name": {"it": name, "en": name}, "amount": 0, "message": {
                    "it": f"{name}: ottieni {amount} PF temporanei.", "en": f"{name}: you gain {amount} temporary HP."}})
    return healed, notices


async def foreign_spell_clocks(session: AsyncSession, char: Character) -> list[dict]:
    """Gli orologi (e ``SPELL_GIVEN``) dei lanciatori degli incantesimi altrui su ``char``, letti prima che un'opzione ne spenda lo stato
    (che chiude l'orologio): l'annullo del danno li riapre con ``reopen_spell_clocks``."""
    out = []
    for state in char.active_states or []:
        key, caster_id = str(state.get("key", "")), (state.get("data") or {}).get("caster_id")
        if not key.startswith(SPELL_STATE_PREFIX) or caster_id in (None, char.id):
            continue
        caster = await load_receiver(session, caster_id)
        clock = next((s for s in caster.active_states or [] if s.get("key") == SPELL_CLOCK_PREFIX + key[len(SPELL_STATE_PREFIX):]), None)
        if clock is not None:
            out.append({"key": key, "caster_id": caster_id, "clock": clock, "given": (caster.settings or {}).get(SPELL_GIVEN)})
    return out


async def reopen_spell_clocks(session: AsyncSession, saved: list[dict]) -> None:
    """Un annullo ha rimesso lo stato di un incantesimo altrui sul bersaglio: l'orologio del lanciatore si riapre e i suoi bersagli ritrovano lo stato."""
    from api.services.spell_effects import regrant_spells  # import locale: il servizio importa questo modulo
    for entry in saved:
        caster = await load_receiver(session, entry["caster_id"])
        if not any(s.get("key") == entry["clock"]["key"] for s in caster.active_states or []):
            caster.active_states = [*(caster.active_states or []), entry["clock"]]
        await regrant_spells(session, caster, entry["given"])


async def _share(session: AsyncSession, char: Character, name: str, caster_id: int | None, amount: int, lang: str, log: list[dict],
                 info: list[dict]) -> None:
    """Il lanciatore subisce lo stesso danno del bersaglio, per la stessa strada di ogni danno (PF temporanei, TS di concentrazione,
    morte, fine dell'incantesimo a 0 PF). Lo snapshot di annullo del lanciatore va in ``log``, nell'annullo del bersaglio."""
    if not caster_id or caster_id == char.id or amount <= 0:
        return
    caster = await load_receiver(session, caster_id)
    if caster.is_dead:
        return
    from api.routers.hp import apply_hp_update  # import locale: il router importa questo modulo
    out: dict = {}
    await apply_hp_update(session, caster, HPUpdate(op=HPOp.DAMAGE, value=amount, damage_modifier="none"), lang,
                          shared_from=f"{name}: condivisi con {char.name}", shared_out=out)
    info.append({"amount": amount, "caster_name": caster.name, "concentration_save": out.get("concentration_save")})
    if caster.hp_undo:
        log.append({"id": caster.id, **caster.hp_undo})
        caster.hp_undo = None  # si annulla dal bersaglio, non dal lanciatore


async def spell_damage_effects(session: AsyncSession, char: Character, applied: int, had_temp: bool, lang: str,
                               share: bool = True, shared_log: list[dict] | None = None,
                               shared_info: list[dict] | None = None) -> list[dict]:
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
            await _share(session, char, name, data.get("caster_id"), applied, lang, shared_log if shared_log is not None else [],
                         shared_info if shared_info is not None else [])
        if variant.ends_at_zero_temp and (char.temp_hp or 0) == 0:
            _spend_state_token(char, state["key"])  # l'incantesimo finisce: il flush chiude l'orologio di chi l'ha lanciato
    return notes

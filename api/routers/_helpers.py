"""Shared helpers for router logic (avoid circular imports)."""
import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.common import ConcentrationSaveResult, RollMode
from api.services.d20 import d20_history_label, d20_records, resolve_applied
from api.services.rules_options import remember_roll
from core.rules.roll_options import AppliedOptions
from api.services.dice_stats import record_dice
from api.services.durations import end_concentration, is_concentrating
from api.services.effects import cap_current_hp, sync_zero_hp
from api.services.condition_effects import release_concentration_effects, restore_released
from api.services.homebrew.passive import get_passive_modifiers
from api.services.history import add_history, prune
from core.db.models import Character
from core.game.attacks import unarmed_strike_profile
from core.game.item_bonuses import item_bonus_total
from core.game.skills import save_roll_part
from core.game.stats import con_hp_delta, effective_ability_mod, roll_ability_mod
from api.services.hp_rolls import stored_rolls
from core.rules.catalog import active_features
from core.rules.edition import character_edition
from core.rules.spell_effects import enchanted_weapon
from core.rules.spellcasting import concentration_dc
from core.rules.modifiers import modifiers_for
from core.rules.weapons import best_damage_dice, has_property, martial_arts_level

async def prune_history(session: AsyncSession, char: Character) -> int:
    """Trim a character's history per `settings.history_retention_*`.

    Modes:
      - "off" (default): no-op.
      - "events": keep at most `history_retention_events` rows
        (default 100), deleting the oldest by `timestamp`.
      - "days": delete rows whose `timestamp` is older than
        `history_retention_days` (default 30).

    Returns the number of rows deleted (for logging/telemetry).
    Best-effort: errors are swallowed and logged to avoid breaking the
    primary action that triggered the prune.
    """
    return await session.run_sync(lambda s: prune(s, char.id, char.settings))


async def apply_con_hp(session: AsyncSession, char, old_con_mod: int) -> None:
    """Auto-recompute HP when the effective CON modifier changed (equip/unequip/move/trade); la capacità di carico
    segue la Forza allo stesso modo."""
    char.recalculate_carry_capacity()
    if (char.settings or {}).get("hp_auto_calc", True):
        delta = con_hp_delta(char.classes, old_con_mod, effective_con_mod(char), stored_rolls(char))
        if delta != 0:
            was_at_zero = char.current_hit_points == 0
            char.hit_points = max(0, char.hit_points + delta)
            char.current_hit_points = max(0, char.current_hit_points + delta)  # il tetto lo mette cap_current_hp (Aiuto supera il massimo base)
            await cap_current_hp(session, char)
            await sync_zero_hp(session, char, was_at_zero)


def weapon_attack_profile(
    char: Character, item: Any, attack_mode: str = "melee", chosen: str | None = None,
) -> tuple[int, str, str]:
    """Modificatore, caratteristica e modalità (`melee`, `thrown`, `ranged`) di un attacco con ``item``.

    ``chosen`` vale solo dove la regola lascia la scelta (Accurata, armi da monaco); senza, la migliore."""
    meta = json.loads(item.item_metadata) if item.item_metadata else {}
    mods = {a: roll_ability_mod(char, a) for a in ("strength", "dexterity")}
    is_ranged = meta.get("weapon_type", "melee") == "ranged" and attack_mode != "thrown"
    if has_property(item, "finesse") or martial_arts_level(char, item):
        best = "dexterity" if mods["dexterity"] > mods["strength"] else "strength"
        ability = chosen if chosen in mods else best
    else:
        ability = "dexterity" if is_ranged else "strength"
    mode = "ranged" if is_ranged else "melee" if attack_mode == "offhand" else attack_mode
    if (enchanted := enchanted_weapon(char, item)) and enchanted[0].weapon_ability and enchanted[1].get("ability"):
        cast = enchanted[1]["ability"]  # Randello Incantato: al posto di Forza o Destrezza (2024: solo se è meglio, edizione del lanciatore)
        if enchanted[1].get("edition") != "2024" or roll_ability_mod(char, cast) > mods[ability]:
            return roll_ability_mod(char, cast), cast, mode
    if meta.get("pact_weapon") and character_edition(char) == "2024" and any(
            spec.key == "warlock.pact_of_the_blade" for spec, _ in active_features(char)):
        charisma = roll_ability_mod(char, "charisma")  # Patto della Lama: Carisma al posto di Forza o Destrezza, se e meglio
        if charisma > mods[ability]:
            return charisma, "charisma", mode
    return mods[ability], ability, mode


def unarmed_attack_profile(char: Character, ranged: bool = False) -> tuple[int, str, str]:
    """Modificatore, dadi di danno e caratteristica del colpo senz'armi. ``ranged``: il lancio di un proiettile
    (Deviare Proiettili) è sempre con Destrezza, con il dado di Arti Marziali."""
    str_mod = roll_ability_mod(char, "strength")
    dex_mod = roll_ability_mod(char, "dexterity")
    ability_mod, damage_dice = unarmed_strike_profile(
        str_mod, dex_mod, martial_arts_level(char, ignore_held=ranged), character_edition(char))
    for spec, _row in active_features(char):  # dado minimo di un privilegio o talento (Attaccabrighe da taverna)
        if spec.unarmed_die and not ranged:
            die = spec.unarmed_die(char) if callable(spec.unarmed_die) else spec.unarmed_die
            damage_dice = best_damage_dice(damage_dice, die)
    if ranged:
        return dex_mod, damage_dice, "dexterity"
    return ability_mod, damage_dice, "strength" if ability_mod == str_mod else "dexterity"


async def initiative_bonus(session: AsyncSession, char: Character, snapshot=None) -> int:
    """Bonus d'iniziativa come sulla scheda: Destrezza effettiva, oggetti, homebrew e regole."""
    return (
        roll_ability_mod(char, "dexterity")
        + item_bonus_total(char.items, "initiative")
        + await get_passive_modifiers(session, char, "character.initiative", snapshot)
        + modifiers_for(char, "initiative", ability="dexterity").flat
    )


async def saving_throw_bonus(session: AsyncSession, char: Character, ability: str, roll: str = "save") -> int:
    """Saving throw bonus as the sheet shows it: effective modifier,
    proficiency, homebrew passive modifiers and rule modifiers."""
    return (
        save_roll_part(char, ability)
        + await get_passive_modifiers(session, char, f"character.saving_throw.{ability}")
        + item_bonus_total(char.items, f"save.{ability}")
        + modifiers_for(char, roll, ability=ability).flat
    )


def effective_con_mod(char) -> int:
    """Effective CON modifier (base CON + modifiers from equipped items)."""
    return effective_ability_mod(char, "constitution")


def _append_concentration_history(
    session: AsyncSession,
    char_id: int,
    damage: int,
    dc: int,
    label: str,
    con_mod: int,
    total: int,
    success: bool,
    lost_concentration: bool,
) -> None:
    """Local history helper (avoids depending on router's private _add_history)."""
    outcome = "SUCCESSO" if success else "FALLIMENTO"
    desc = (
        f"TS Concentrazione (danno {damage}, DC {dc}): "
        f"{label}+{con_mod}={total}: {outcome}"
        + (" → concentrazione persa" if lost_concentration else "")
    )
    add_history(session, char_id, "concentration_save", desc)


async def _lose_concentration(session: AsyncSession, char: Character) -> dict:
    """Fa cadere la concentrazione e restituisce ciò che serve per ripristinarla dopo un ritiro riuscito."""
    settings = char.settings or {}
    snapshot = {"spell_id": char.concentrating_spell_id, "item_spell": settings.get("concentration_item_spell"),
                "rounds": settings.get("concentration_rounds_left"), "level": settings.get("concentration_level"), "active_states": list(char.active_states or []),
                "released": []}
    end_concentration(char)
    await release_concentration_effects(session, char, snapshot["released"])
    return snapshot


async def retouch_concentration(
    session: AsyncSession, char: Character, conc: dict, roll: dict,
) -> tuple[ConcentrationSaveResult, dict]:
    """Il TS è cambiato dopo un privilegio: un successo ripristina ciò che il fallimento aveva fatto cadere."""
    conc = dict(conc)
    success = roll["total"] >= conc["dc"]
    if success and conc["lost"]:
        snap = conc["snapshot"]
        # L'incantesimo può essere stato eliminato nel frattempo.
        char.concentrating_spell_id = (snap["spell_id"] if any(s.id == snap["spell_id"] for s in char.spells)
                                       else None)
        settings = dict(char.settings or {})
        if snap["item_spell"] is not None:
            settings["concentration_item_spell"] = snap["item_spell"]
        if snap["rounds"] is not None:
            settings["concentration_rounds_left"] = snap["rounds"]
        if snap.get("level") is not None:
            settings["concentration_level"] = snap["level"]
        char.settings = settings
        char.active_states = list(snap["active_states"])
        await restore_released(session, snap["released"])
        conc.update(lost=False, snapshot=None)
    elif not success and not conc["lost"] and is_concentrating(char):
        conc.update(lost=True, snapshot=await _lose_concentration(session, char))
    return ConcentrationSaveResult(**roll, description=f"DC {conc['dc']}", dc=conc["dc"], success=success,
                                   lost_concentration=conc["lost"]), conc


async def roll_concentration_save(
    char: Character,
    damage: int,
    session: AsyncSession,
    mode: RollMode = "normal",
    dice: list[int] | None = None,
) -> ConcentrationSaveResult:
    """Roll a CON save vs ``concentration_dc`` (2024: capped at 30). RAW: natural 20 and 1 have
    no special effect on saving throws, only the total counts.

    Side effects:
    - Clears char.concentrating_spell_id on failure (if it was set).
    - Appends a history entry describing the roll.

    Returns a ConcentrationSaveResult with die, bonus, total, is_critical,
    is_fumble, description, dc, success, lost_concentration.
    """
    dc = concentration_dc(character_edition(char), damage)
    con_mod = await saving_throw_bonus(session, char, "constitution", "concentration")

    applied = modifiers_for(char, "concentration", ability="constitution")
    outcome = resolve_applied(mode, dice, None, applied)
    die = outcome.kept
    total = die + con_mod
    record_dice(char, d20_records(outcome), total)
    is_crit = die == 20 and not applied.auto_fail
    is_fumble = die == 1
    success = total >= dc and not applied.auto_fail

    lost_concentration = not success and is_concentrating(char)
    snapshot = await _lose_concentration(session, char) if lost_concentration else None

    _append_concentration_history(
        session, char.id, damage, dc, d20_history_label(outcome), con_mod, total, success, lost_concentration,
    )
    remember_roll(char, "save", AppliedOptions(), {
        "die": die, "dice": outcome.dice, "mode": outcome.mode, "bonus": con_mod, "total": total,
        "notes": applied.notes, "auto_fail": applied.auto_fail, "description": f"DC {dc}",
    }, ability="constitution", modifier_roll="concentration",
        concentration={"dc": dc, "lost": lost_concentration, "snapshot": snapshot})

    return ConcentrationSaveResult(
        die=die,
        dice=outcome.dice,
        mode=outcome.mode,
        mode_applied=outcome.mode,
        notes=applied.notes,
        auto_fail=applied.auto_fail,
        bonus=con_mod,
        total=total,
        is_critical=is_crit,
        is_fumble=is_fumble,
        description=f"DC {dc}",
        dc=dc,
        success=success,
        lost_concentration=lost_concentration,
    )


def collect_homebrew_notifications(firing_results) -> list[dict]:
    """Flatten a list of RuleFiringResult into the dict shape exposed by responses."""
    return [
        {
            "severity": n.severity,
            "message": n.message,
            "rule_id": n.rule_id,
            "rule_name": n.rule_name,
        }
        for rfr in firing_results
        for n in rfr.notifications
    ]

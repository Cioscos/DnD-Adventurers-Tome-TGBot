"""Canonical CharacterFull response builder.

Populates the homebrew passive-modifier breakdown fields (ac_breakdown,
hp_max_homebrew_modifier, speed_homebrew_modifier, skills_homebrew_modifiers,
saves_homebrew_modifiers) by calling get_passive_modifiers for each relevant
target_path. Replaces bare CharacterFull.model_validate(char) usages across
the routers.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.character import AcBreakdown, ActiveForm, CharacterFull
from api.services.condition_effects import character_effect_payload
from api.services.wild_shape import get_active_form
from api.services.homebrew.passive import get_passive_modifiers, passive_modifier
from api.services.spellcasting import build_spellcasting_info
from core.data.skills import SKILL_ABILITY_MAP
from core.db.models import ABILITY_NAMES, Character
from core.game.actions import attacks_per_action
from core.game.item_bonuses import item_bonus_total
from core.game.skills import PASSIVE_SKILLS, has_jack_of_all_trades, skill_proficiency_part
from core.game.stats import effective_ability_score
from api.routers._helpers import effective_ability_mod


async def build_character_response(
    session: AsyncSession, char: Character,
) -> CharacterFull:
    """Build a CharacterFull response with homebrew breakdown populated."""
    # Flush any pending mutations on `char` BEFORE serializing. CharacterFull.model_validate
    # reads ORM attributes synchronously; if the session is still dirty, that access can
    # trigger an autoflush from inside pydantic (a sync context) and blow up with
    # "greenlet_spawn has not been called" under async SQLAlchemy. Callers that mutate the
    # character and then call us without a prior awaited flush (e.g. hp.py SET_MAX/SET_CURRENT,
    # death-save and skill/save PATCH endpoints) would otherwise 500. Flushing here within the
    # awaited context keeps serialization side-effect-free. No-op on read-only (clean) sessions.
    await session.flush()

    # TODO (perf): each get_passive_modifiers call issues 2 SELECTs (rules + items).
    # At 27 calls/response this is 54 SELECTs. Batch by preloading rules+items once
    # and exposing a sum_modifiers(rules, items, target_path) helper.
    response = CharacterFull.model_validate(char)
    response.condition_effects, response.pending_saves = await character_effect_payload(
        session, char.id)
    response.has_custom_silhouette =bool(getattr(char, "silhouette_path", None))
    response.spellcasting = build_spellcasting_info(char)
    response.attacks_per_action = attacks_per_action(char.classes)
    form = await get_active_form(session, char.id)
    if form is not None:
        response.active_form = ActiveForm(
            companion_id=form.id, name=form.name, current_hp=form.current_hp,
            max_hp=form.max_hp, temp_hp=form.temp_hp, armor_class=form.armor_class)

    hb_ac = await get_passive_modifiers(session, char, "character.ac")
    response.ac_breakdown = AcBreakdown(
        base=char.base_armor_class,
        shield=char.shield_armor_class,
        magic=char.magic_armor,
        homebrew=hb_ac,
        items=item_bonus_total(char.items, "ac"),
    )

    response.hp_max_homebrew_modifier = await get_passive_modifiers(
        session, char, "character.hit_points_max"
    )
    response.speed_homebrew_modifier = await get_passive_modifiers(
        session, char, "character.speed"
    )

    response.speed_items_modifier = item_bonus_total(char.items, "speed")
    response.initiative_bonus = (
        effective_ability_mod(char, "dexterity")
        + item_bonus_total(char.items, "initiative")
        + await get_passive_modifiers(session, char, "character.initiative")
    )
    _apply_encumbrance(char, response)
    response.pending_choices = list(char.pending_choices or [])

    response.jack_of_all_trades = has_jack_of_all_trades(char)
    # Same formula as api.services.skills.skill_bonus / passive_score, reusing the
    # homebrew lookup once per skill instead of re-querying it.
    for slug, ability in SKILL_ABILITY_MAP.items():
        val = await get_passive_modifiers(session, char, f"character.skill.{slug}")
        if val:
            response.skills_homebrew_modifiers[slug] = val
        response.skill_bonuses[slug] = (
            effective_ability_mod(char, ability) + skill_proficiency_part(char, slug) + val
        )
    for slug in PASSIVE_SKILLS:
        response.passives[slug] = (
            10 + response.skill_bonuses[slug] + await passive_modifier(session, char, slug)
        )

    for slug in ABILITY_NAMES:
        val = await get_passive_modifiers(session, char, f"character.saving_throw.{slug}")
        if val:
            response.saves_homebrew_modifiers[slug] = val
        item_val = item_bonus_total(char.items, f"save.{slug}")
        if item_val:
            response.saves_items_modifiers[slug] = item_val

    return response


def _apply_encumbrance(char: Character, response: CharacterFull) -> None:
    """Total carried weight (+ coins at 50/lb if enabled) and the optional variant level."""
    cfg = char.settings or {}
    # Live sum: the stored column can lag when items were just added/changed in this request.
    total = float(sum(i.weight * i.quantity for i in char.items))
    response.encumbrance = total
    cur = char.currency
    if cfg.get("coin_weight") and cur is not None:
        total += (cur.copper + cur.silver + cur.electrum + cur.gold + cur.platinum) / 50
    response.encumbrance_total = total
    if not cfg.get("encumbrance_variant"):
        return
    row = next((a for a in char.ability_scores if a.name == "strength"), None)
    strength, _ = effective_ability_score(
        "strength", row.value if row else 10, [i for i in char.items if i.is_equipped]
    )
    if total > strength * 10:
        response.encumbrance_level, response.speed_encumbrance_penalty_ft = "heavily", 20
    elif total > strength * 5:
        response.encumbrance_level, response.speed_encumbrance_penalty_ft = "encumbered", 10

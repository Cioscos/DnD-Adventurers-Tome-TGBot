"""Canonical CharacterFull response builder.

Populates the homebrew passive-modifier breakdown fields (ac_breakdown,
hp_max_homebrew_modifier, speed_homebrew_modifier, skills_homebrew_modifiers,
saves_homebrew_modifiers) by calling get_passive_modifiers for each relevant
target_path. Replaces bare CharacterFull.model_validate(char) usages across
the routers.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.container import CoinLocationRead, ContainerStatsRead
from api.schemas.character import AcBreakdown, ActiveForm, CharacterFull, ComputedStats
from api.services.choices import is_resolvable, option_catalog, pick_count, spell_pick_info
from api.services.condition_effects import character_effect_payload
from api.services.wild_shape import form_own_hp, get_active_form
from api.services.homebrew.passive import get_passive_modifiers, passive_modifier
from api.services.item_charges import attunement_limit, has_use_magic_device
from api.services.spellcasting import build_spellcasting_info, effect_view, fill_spell_stats
from core.data.skills import SKILL_ABILITY_MAP
from core.db.models import ABILITY_NAMES, Character
from core.game.actions import attacks_per_action
from core.game.containers import COINS, carried_weight, coin_locations, container_coins, container_stats
from core.game.item_bonuses import item_bonus_total
from core.game.skills import PASSIVE_SKILLS, has_jack_of_all_trades, skill_roll_part
from core.rules.condition_removal import view as removal_view
from core.rules.catalog import active_features
from core.rules.edition import character_edition
from core.rules.types import RuleContext
from core.rules.uses import pool_key
from core.rules.modifiers import (
    ac_delta, effective_hp_max, effective_speed, is_incapacitated, modifiers_for, passive_adjustment, surprise_exit_features, surprised_turn,
)
from core.game.stats import effective_ability_mod, effective_ability_score, migrate_character_ac, sync_base_ac, unarmored_formula
from api.routers._helpers import initiative_bonus


async def build_character_response(
    session: AsyncSession, char: Character,
) -> CharacterFull:
    """Build a CharacterFull response with homebrew breakdown populated."""
    # Copre ogni percorso che cambia caratteristiche o oggetti senza passare da `apply_equip_ac`.
    migrate_character_ac(char)
    sync_base_ac(char)

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
    formula = unarmored_formula(char)
    response.unarmored_formula = list(formula) if formula else None
    response.has_custom_silhouette = bool(getattr(char, "silhouette_path", None))
    response.spellcasting = build_spellcasting_info(char)
    fill_spell_stats(char, response.spells)
    response.attacks_per_action = attacks_per_action(char.classes)
    response.inspiration_extra = bool((char.settings or {}).get("inspiration_extra"))
    response.hiding_dc = ((char.settings or {}).get("hiding") or {}).get("dc")
    form = await get_active_form(session, char.id)
    if form is not None:
        response.active_form = ActiveForm(
            companion_id=form.id, name=form.name, current_hp=form.current_hp,
            max_hp=form.max_hp, temp_hp=form.temp_hp, armor_class=form.armor_class,
            own_hp=form_own_hp(char))

    hb_ac = await get_passive_modifiers(session, char, "character.ac")
    response.ac_breakdown = AcBreakdown(
        base=char.base_armor_class,
        shield=char.shield_armor_class,
        magic=char.magic_armor,
        homebrew=hb_ac,
        items=item_bonus_total(char.items, "ac"),
        rules=ac_delta(char, response.ac, item_bonus_total(char.items, "ac") + hb_ac),
    )
    response.ac += response.ac_breakdown.rules

    response.hp_max_homebrew_modifier = await get_passive_modifiers(
        session, char, "character.hit_points_max"
    )
    response.speed_homebrew_modifier = await get_passive_modifiers(
        session, char, "character.speed"
    )

    response.speed_items_modifier = item_bonus_total(char.items, "speed")
    response.initiative_bonus = await initiative_bonus(session, char)
    _apply_encumbrance(char, response)
    _apply_containers(char, response)
    response.pending_choices = [
        {**c, "options": option_catalog(char, c), "pick_count": pick_count(char, c), "resolvable": is_resolvable(char, c),
         **({"spell_pick": pick} if (pick := spell_pick_info(char, c)) else {})}
        if c.get("kind") == "class_option" else c
        for c in (char.pending_choices or [])]

    usable = {spec.key: (spec.on_use, row) for spec, row in active_features(char) if spec.on_use}
    edition = character_edition(char)
    pools = {spec.key for spec, _ in active_features(char) if spec.uses is not None and not spec.on_use}
    dc_of = {spec.key: spec.dc_ability for spec, _ in active_features(char) if spec.dc_ability}
    for ab in response.abilities:
        on_use, owner = usable.get(ab.feature_key, (None, None))
        ab.is_pool = ab.feature_key in pools
        if ab.feature_key in dc_of:
            ab.dc = 8 + char.proficiency_bonus + effective_ability_mod(char, dc_of[ab.feature_key])
        ab.has_on_use = on_use is not None
        ab.gives_to_ally = bool(on_use and on_use.ally_state)
        if on_use and on_use.temp_hp_ally and owner is not None:  # PF temporanei a un PG della serata (Task 46)
            ab.ally_max = on_use.ally_count(RuleContext(char=char, edition=edition, class_row=owner, class_level=owner.level)) if on_use.ally_count else 1
            ab.gives_to_ally = ab.ally_max > 0
        ab.ally_modes = list(on_use.ally_modes) if on_use else []
        ab.use_panel = on_use.panel if on_use else None
        # Un uso gratuito nasce solo con lo stato del privilegio già attivo (prolungare l'Ira 2024); gli altri `cost_by` chiedono
        # parametri (il livello dello slot) che qui non ci sono: non sono un uso libero.
        if on_use and on_use.cost_by and owner is not None and any(s.get("feature_key") == ab.feature_key for s in char.active_states or []):
            free_ctx = RuleContext(char=char, edition=edition, class_row=owner, class_level=owner.level)
            ab.free_use = on_use.cost_by(free_ctx, {}) == 0 and (on_use.available is None or bool(on_use.available(free_ctx)))
        # Uno slot di turno che dipende dal momento (Arciere): gratuito ora se non ne chiede nessuno, anche con l'azione bonus spesa
        elif on_use and on_use.slot_by and owner is not None:
            free_ctx = RuleContext(char=char, edition=edition, class_row=owner, class_level=owner.level)
            ab.free_use = on_use.slot_by(free_ctx, {}) is None and (on_use.available is None or bool(on_use.available(free_ctx)))
        # Un uso che spende un'altra riserva non tocca il contatore della riga (Magia Ammaliante: lo ripristina spendendo Ispirazione)
        elif on_use and on_use.spends and ab.max_uses is not None and owner is not None:
            free_ctx = RuleContext(char=char, edition=edition, class_row=owner, class_level=owner.level)
            ab.free_use = on_use.available is None or bool(on_use.available(free_ctx))
        if on_use and on_use.spends:
            held = pool_key(char, on_use.spends)
            pool = next((a for a in response.abilities if a.feature_key == held), None)
            ab.spends_left = (pool.uses or 0) if pool is not None and pool.max_uses is not None else None
        ab.choose_amount = bool(on_use and on_use.choose_amount)
        ab.max_amount = on_use.max_amount if on_use and on_use.choose_amount else None
        ab.min_amount = on_use.min_amount if on_use and on_use.choose_amount else 1
        if on_use and on_use.removal and not on_use.removal.auto and owner is not None:
            shown = removal_view(on_use.removal, RuleContext(char=char, edition=edition, class_row=owner, class_level=owner.level))
            ab.removal = shown if shown["conditions"] or shown["untracked"] else None
        if on_use and (on_use.toggles or on_use.choices or on_use.texts):
            ctx = RuleContext(char=char, edition=edition, class_row=owner, class_level=owner.level)
            ab.use_toggles = [{"key": t.key, "label": dict(t.label)} for t in on_use.toggles if t.available(ctx)]
            ab.use_choices = [{"key": c.key, "label": dict(c.label),
                               "options": [{"key": o, "label": c.option_label_ctx(ctx, o) if c.option_label_ctx else c.option_label(o)}
                                           for o in c.options(ctx)],
                               **({"optional": True} if c.optional else {})}
                              for c in on_use.choices if c.applies is None or c.applies(ctx)]
            ab.use_texts = [{"key": t.key, "label": dict(t.label), "max_len": t.max_len, **({"optional": True} if t.optional else {})}
                            for t in on_use.texts]

    response.jack_of_all_trades = has_jack_of_all_trades(char)
    # Same formula as api.services.skills.skill_bonus / passive_score, reusing the
    # homebrew lookup once per skill instead of re-querying it.
    for slug, ability in SKILL_ABILITY_MAP.items():
        val = await get_passive_modifiers(session, char, f"character.skill.{slug}")
        if val:
            response.skills_homebrew_modifiers[slug] = val
        response.skill_bonuses[slug] = (
            skill_roll_part(char, slug, ability) + val
            + modifiers_for(char, "skill", skill=slug, ability=ability).flat
        )
    for slug in PASSIVE_SKILLS:
        response.passives[slug] = (
            10 + response.skill_bonuses[slug] + await passive_modifier(session, char, slug)
            + passive_adjustment(char, slug)
        )

    for slug in ABILITY_NAMES:
        val = await get_passive_modifiers(session, char, f"character.saving_throw.{slug}")
        if val:
            response.saves_homebrew_modifiers[slug] = val
        item_val = item_bonus_total(char.items, f"save.{slug}")
        if item_val:
            response.saves_items_modifiers[slug] = item_val

    owned = {i.id: i for i in char.items}
    for it in response.items:  # effetti degli incantesimi concessi, anche se il personaggio non li conosce
        granted = (it.item_metadata or {}).get("granted_spells")
        if isinstance(granted, list) and granted:
            it.granted_effects = [effect_view(char, g.get("srd_index"), g.get("name"), int(g.get("level") or 1))
                                  if isinstance(g, dict) else None for g in granted]
    for it in response.items:  # portata in più di un'arma (Radici Percuotenti)
        if it.item_type == "weapon" and it.id in owned:
            it.reach_bonus_ft = modifiers_for(char, "reach", item=owned[it.id]).flat or None

    rule_damage = modifiers_for(char, None)
    stored = char.damage_modifiers if isinstance(char.damage_modifiers, dict) else {}
    walk = effective_speed(char, (
        char.speed + response.speed_homebrew_modifier + response.speed_items_modifier
        - response.speed_encumbrance_penalty_ft
    ))
    if rule_damage.carry_double:
        response.carry_capacity *= 2
    response.computed = ComputedStats(
        speed=walk,
        fly_speed=(max(walk if rule_damage.fly_speed else 0, rule_damage.fly_speed_value) or None),
        climb_speed=walk if rule_damage.climb_speed else None,
        swim_speed=walk if rule_damage.swim_speed else None,
        hp_max_effective=effective_hp_max(char, response.hp_max_homebrew_modifier),
        resistances=sorted({*(stored.get("resistances") or []), *rule_damage.resistances}),
        immunities=sorted({*(stored.get("immunities") or []), *rule_damage.immunities}),
        vulnerabilities=sorted({*(stored.get("vulnerabilities") or []), *rule_damage.vulnerabilities}),
        incapacitated=is_incapacitated(char),
        surprised=surprised_turn(char),
        surprise_exit_features=surprise_exit_features(char),
        save_flat={a: modifiers_for(char, "save", ability=a).flat for a in ABILITY_NAMES},
        senses=[{"type": k, "range_ft": v} for k, v in sorted(rule_damage.senses.items())],
        long_jump_bonus_ft=rule_damage.jump_bonus_ft,
        attunement_limit=attunement_limit(char),
        scroll_casting=has_use_magic_device(char),
    )
    return response


def _purse(char: Character) -> dict[str, int]:
    cur = char.currency
    return {c: getattr(cur, c) or 0 for c in COINS} if cur is not None else {}


def _apply_containers(char: Character, response: CharacterFull) -> None:
    """Per-container stats on the items, plus coin totals/breakdown across purse and containers."""
    stats = container_stats(char.items)
    for it in response.items:
        s = stats.get(it.id)
        if s is not None:
            it.container_stats = ContainerStatsRead(**vars(s))
    by_id = {i.id: i for i in char.items}
    places = [(None, None, _purse(char))] + [
        (cid, by_id[cid].name, container_coins(by_id[cid])) for cid in coin_locations(char.items)
    ]
    response.coin_totals = {c: sum(p[2].get(c, 0) for p in places) for c in COINS}
    response.coin_breakdown = [
        CoinLocationRead(container_id=cid, name=name, coins={c: coins.get(c, 0) for c in COINS})
        for cid, name, coins in places if any(coins.get(c, 0) for c in COINS)
    ]


def _apply_encumbrance(char: Character, response: CharacterFull) -> None:
    """Total carried weight (+ coins at 50/lb if enabled) and the optional variant level."""
    cfg = char.settings or {}
    # Live sum: the stored column can lag when items were just added/changed in this request.
    response.encumbrance = float(carried_weight(char.items, {}, False))
    total = float(carried_weight(char.items, _purse(char), bool(cfg.get("coin_weight"))))
    response.encumbrance_total = total
    if not cfg.get("encumbrance_variant"):
        return
    row = next((a for a in char.ability_scores if a.name == "strength"), None)
    strength, _ = effective_ability_score(
        "strength", row.value if row else 10, [i for i in char.items if i.is_equipped]
    )
    if modifiers_for(char, None).carry_double:  # capacità di carico doppia (Orso)
        strength *= 2
    if total > strength * 10:
        response.encumbrance_level, response.speed_encumbrance_penalty_ft = "heavily", 20
    elif total > strength * 5:
        response.encumbrance_level, response.speed_encumbrance_penalty_ft = "encumbered", 10

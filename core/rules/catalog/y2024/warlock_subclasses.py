"""Warlock 2024, parte B (patroni): Fatato, Celestiale, Immondo e Grande Antico.

Valori da ``docs/superpowers/rules/2024/classes/warlock.md``; i testi sono nostri, mai quelli del manuale. Le righe vanno in
``SUBCLASS_ROWS`` con ``subclass=`` (archfey, celestial, fiend, great_old_one). Non importa ``warlock.py`` (che importa questo
modulo in fondo): usa le definizioni del 2014 (``_dc``, ``BLESSING_USE``, ``THOUGHT_REFLECTION``, la scelta di Resilienza Immonda).
Il ripristino con uno slot di Patto (Difese Seducenti, Scagliare all'Inferno, Combattente Chiaroveggente) è uno slot ``pact_only``.
"""
from __future__ import annotations

import random
import re
from dataclasses import replace
from typing import Any

from core.data.damage_types import DAMAGE_TYPES, LABELS_IT, canonical_damage_type, spell_damage_type
from core.rules.condition_removal import ConditionRemoval
from core.rules.catalog._common import feature
from core.rules.catalog.y2014.warlock import (
    BLESSING_USE, THOUGHT_REFLECTION, _dc, _lock_resilience, _resilience_active, _resilience_check, _resilience_state,
)
from core.rules.catalog.y2014.warlock_invocations import _mod
from core.rules.schools import normalize_school
from core.rules.states import begin_state
from core.rules.types import (
    Cost, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, TargetEffect, UseChoice, Uses, UseToggle,
)

ED, CK = "2024", "warlock"
P = f"{CK}."
THRALL_CAST = f"{P}create_thrall_cast"  # letto dal router degli incantesimi (lancio senza Concentrazione)
ABILITIES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
NOTES = ("taunting_step", "terrifying_step", "clairvoyant_combatant", "hurl_through_hell_2024", *(f"eldritch_hex_{a}" for a in ABILITIES))


def _both(it: str, en: str) -> dict[str, str]:
    return {"it": it, "en": en}


def _cha(ctx: RuleContext) -> int:
    return _mod(ctx, "charisma")


def _pact(char: Any) -> list[Any]:
    return [s for s in char.spell_slots or [] if s.is_pact]


def _sub(label: str, subclass: str):
    """Fabbrica delle righe di un patrono: il titolo è quello della scheda."""
    def make(key: str, level: int, it: str, en: str, page: int, summary: tuple[str, str], action_type: str | None = None, **kw: Any):
        return feature(key, CK, ED, level, f"{it} / {en} ({label} {level}, pag. {page})", (it, en), summary, action_type, subclass=subclass, **kw)
    return make


def _spells(sub: str, label: str, key: str, it: str, en: str, page: int, tiers: tuple[tuple[str, ...], ...]) -> list:
    """Incantesimi sempre preparati ai livelli 3, 5, 7 e 9: la riga del 3° è quella della scheda, le altre soglie la ripetono."""
    make = _sub(label, sub)
    title = f"{it} / {en} ({label} 3, pag. {page})"
    out = [make(key, 3, it, en, page, ("Incantesimi sempre preparati ai livelli 3, 5, 7 e 9; non contano nel limite dei preparati.",
                                      "Spells always prepared at levels 3, 5, 7 and 9; they do not count against your prepared limit."),
                granted_spells=tiers[0])]
    for lv, spells in zip((5, 7, 9), tiers[1:]):
        out.append(feature(f"{key}_{lv}", CK, ED, lv, title, (it, en), (f"Incantesimi sempre preparati del {lv}° livello.", f"Always-prepared spells gained at level {lv}."),
                           subclass=sub, granted_spells=spells, no_row=True,
                           covered_by=f"{P}{key} (stessa voce della mappatura) e test_patron_spells_are_always_prepared_from_their_level"))
    return out


def _spell_is(ctx: RuleContext, index: str) -> bool:
    return ctx.spell is not None and (ctx.spell.srd_index or "") == index


# ---------------------------------------------------------------------------
# Ripristino con uno slot di Patto
# ---------------------------------------------------------------------------

def _pact_levels(ctx: RuleContext) -> list[str]:
    return [str(level) for level in sorted({s.level for s in _pact(ctx.char) if s.available > 0})]


def _restore_check(_ctx: RuleContext, params: dict) -> tuple[int, str] | None:
    return (422, "invalid_choice") if params.get("restore") and params.get("slot_level") is None else None


def _restorable(**kw: Any) -> OnUse:
    """Un uso per riposo; «ripristina» spendendo uno slot di Patto (nessuna azione): l'uso non si consuma e lo slot sì."""
    return OnUse(
        spends_slot="slot_level", spends_slot_pact_only=True, spends_slot_when=lambda _c, p: bool(p.get("restore")),
        cost_by=lambda _c, p: 0 if p.get("restore") else 1, check=_restore_check,
        toggles=(UseToggle("restore", _both("Ripristina l'uso spendendo uno slot di Magia del Patto (nessuna azione)",
                                            "Restore the use by spending a Pact Magic slot (no action)")),),
        choices=(UseChoice("slot_level", _both("Slot di Patto da spendere per ripristinare", "Pact slot to spend to restore"), _pact_levels,
                           lambda level: _both(f"Slot di {level}° livello", f"Level {level} slot"), optional=True),), **kw)


def _slot_variant(spec: RollOptionSpec) -> RollOptionSpec:
    """La stessa opzione pagata con uno slot di Patto al posto dell'uso: il giocatore sceglie il livello."""
    return replace(spec, key=f"{spec.key}_slot", cost=Cost(spell_slot_min=1, pact_only=True), requires_input="slot",
                   label=_both(spec.label["it"] + " (ripristino: slot di Patto)", spec.label["en"] + " (restore: Pact slot)"))


# ---------------------------------------------------------------------------
# Patrono Fatato
# ---------------------------------------------------------------------------

ARCHFEY = "Patrono Fatato"
STEPS, ESCAPE, DEFENSES, BEWITCH = f"{P}steps_of_the_fey", f"{P}misty_escape", f"{P}beguiling_defenses", f"{P}bewitching_magic"
ARCHFEY_SPELLS = (("calm-emotions", "faerie-fire", "misty-step", "phantasmal-force", "sleep"), ("blink", "plant-growth"),
                  ("dominate-beast", "greater-invisibility"), ("dominate-person", "seeming"))
archfey = _sub(ARCHFEY, "archfey")
STEP_EFFECTS = {"plain": ("Nessun effetto aggiuntivo", "No added effect"), "refreshing": ("Passo Rinfrescante (PF temporanei a te)", "Refreshing Step (temporary HP to you)"),
                "taunting": ("Passo Provocatorio", "Taunting Step"), "disappearing": ("Passo Scomparso", "Disappearing Step"),
                "terrifying": ("Passo Terrificante", "Terrifying Step")}


def _misty_cast(ctx: RuleContext) -> bool:
    return _spell_is(ctx, "misty-step")


def _d10(given: dict) -> int:
    if not given.get("rolled"):
        given["rolled"] = random.randint(1, 10)
    return given["rolled"]


def _refreshing(mine: bool) -> RollOptionSpec:
    def confirmed(_session: Any, ctx: RuleContext, given: dict) -> None:
        points = _d10(given)
        if mine:
            ctx.char.temp_hp = max(ctx.char.temp_hp or 0, points)

    def effect(_ctx: RuleContext, given: dict) -> dict[str, str]:
        n = given["rolled"]
        if mine:
            return _both(f"Passo Rinfrescante: ottieni {n} PF temporanei.", f"Refreshing Step: you gain {n} temporary hit points.")
        if given.get("target_character_id") is not None:  # la consegna a un PG della serata la scrive il server
            return _both(f"Passo Rinfrescante: una creatura che vedi entro 3 m ottiene {n} PF temporanei.",
                         f"Refreshing Step: a creature you see within 10 ft gains {n} temporary hit points.")
        return _both(f"Passo Rinfrescante: una creatura che vedi entro 3 m ottiene {n} PF temporanei (dillo al GM).",
                     f"Refreshing Step: a creature you see within 10 ft gains {n} temporary hit points (tell the GM).")
    return RollOptionSpec(
        key=f"{STEPS}_refreshing" + ("" if mine else "_other"), phase="before", rolls=("cast",), group="steps", available=_misty_cast,
        on_confirm=confirmed, effect=effect, temp_hp_gift=None if mine else (lambda _c, given: _d10(given)),
        label=_both("Passi del Fatato: Passo Rinfrescante, 1d10 PF temporanei a " + ("te" if mine else "un'altra creatura entro 3 m"),
                    "Steps of the Fey: Refreshing Step, 1d10 temporary HP to " + ("you" if mine else "another creature within 10 ft")))


def _taunting_effect(ctx: RuleContext) -> TargetEffect:
    return TargetEffect(save_ability="wisdom", save_dc=_dc(ctx), ends_at={"anchor": "source", "edge": "start", "count": 1}, note="taunting_step")


def _terrifying_effect(ctx: RuleContext) -> TargetEffect:
    return TargetEffect(save_ability="wisdom", save_dc=_dc(ctx), damage_dice="2d10", note="terrifying_step")


def _taunting_text(ctx: RuleContext) -> dict[str, str]:
    return _both(f"Passo Provocatorio, CD {_dc(ctx)}: le creature entro 1,5 m dallo spazio lasciato fanno un TS Saggezza; se falliscono hanno svantaggio "
                 "agli attacchi contro chi non sei tu fino all'inizio del tuo prossimo turno.",
                 f"Taunting Step, DC {_dc(ctx)}: creatures within 5 ft of the space you left make a Wisdom save; on a failure they have disadvantage "
                 "on attacks against anyone but you until the start of your next turn.")


def _terrifying_text(ctx: RuleContext) -> dict[str, str]:
    return _both(f"Passo Terrificante, CD {_dc(ctx)}: le creature scelte entro 1,5 m dallo spazio lasciato o raggiunto fanno un TS Saggezza; se falliscono subiscono 2d10 danni psichici.",
                 f"Terrifying Step, DC {_dc(ctx)}: chosen creatures within 5 ft of the space you left or reached make a Wisdom save; on a failure they take 2d10 psychic damage.")


def _disappearing_state() -> StateSpec:
    return StateSpec("disappearing_step", condition="invisible", ends_on=("new_turn", "attack", "cast", "rest_short", "rest_long", "manual"),
                     data={"others": [ESCAPE]})


_DISAPPEARED = _both("Passo Scomparso: sei Invisibile fino all'inizio del tuo prossimo turno o finché attacchi, infliggi danni o lanci un incantesimo.",
                     "Disappearing Step: you are Invisible until the start of your next turn or until you attack, deal damage or cast a spell.")
STEP_TAUNTING = RollOptionSpec(
    key=f"{STEPS}_taunting", phase="before", rolls=("cast",), group="steps", available=_misty_cast, effect=lambda c, _i: _taunting_text(c),
    target_effect=lambda c, _i: _taunting_effect(c),
    label=_both("Passi del Fatato: Passo Provocatorio, svantaggio agli attacchi contro altri", "Steps of the Fey: Taunting Step, disadvantage on attacks against others"))
STEP_DISAPPEARING = RollOptionSpec(
    key=f"{ESCAPE}_disappearing", phase="before", rolls=("cast",), group="steps", available=_misty_cast,
    on_confirm=lambda _s, ctx, _i: begin_state(ctx.char, _disappearing_state(), ESCAPE), effect=lambda _c, _i: _DISAPPEARED,
    label=_both("Fuga Velata: Passo Scomparso, Invisibile fino al prossimo turno", "Misty Escape: Disappearing Step, Invisible until your next turn"))
STEP_TERRIFYING = RollOptionSpec(
    key=f"{ESCAPE}_terrifying", phase="before", rolls=("cast",), group="steps", available=_misty_cast, effect=lambda c, _i: _terrifying_text(c),
    target_effect=lambda c, _i: _terrifying_effect(c),
    label=_both("Fuga Velata: Passo Terrificante, 2d10 psichici se falliscono il TS Saggezza", "Misty Escape: Terrifying Step, 2d10 psychic on a failed Wisdom save"))


def _escape_state(_ctx: RuleContext, params: dict) -> StateSpec | None:
    return _disappearing_state() if params.get("effect") == "disappearing" else None


def _escape_target(ctx: RuleContext, params: dict) -> TargetEffect | None:
    make = {"taunting": _taunting_effect, "terrifying": _terrifying_effect}.get(params.get("effect"))
    return make(ctx) if make else None


def _escape_temp(_ctx: RuleContext, _rolled: int, params: dict) -> int:
    return _d10(params) if params.get("effect") == "refreshing" else 0


def _escape_message(ctx: RuleContext, params: dict) -> dict[str, str]:
    effect = params.get("effect")
    cast = _both("Lanci Passo Velato come reazione. ", "You cast Misty Step as a reaction. ")
    if effect == "refreshing":
        return _both(cast["it"] + f"Passo Rinfrescante: ottieni {params['rolled']} PF temporanei.",
                     cast["en"] + f"Refreshing Step: you gain {params['rolled']} temporary hit points.")
    text = {"taunting": _taunting_text, "terrifying": _terrifying_text}.get(effect)
    if text is not None:
        return _both(cast["it"] + text(ctx)["it"], cast["en"] + text(ctx)["en"])
    if effect == "disappearing":
        return _both(cast["it"] + _DISAPPEARED["it"], cast["en"] + _DISAPPEARED["en"])
    return _both(cast["it"].strip(), cast["en"].strip())


ESCAPE_USE = OnUse(
    slot="reaction", spends=STEPS, state=_escape_state, target_effect=_escape_target, temp_hp_by=_escape_temp, message=_escape_message,
    choices=(UseChoice("effect", _both("Effetto aggiunto", "Added effect"), lambda _c: list(STEP_EFFECTS), lambda k: _both(*STEP_EFFECTS[k])),))


def _halved(ctx: RuleContext, _inputs: dict) -> dict[str, str]:
    back = None if ctx.damage is None else ctx.damage // 2
    tail = f": {back}." if back is not None else "."
    return _both(f"Difese Seducenti, CD {_dc(ctx)}: l'attaccante fa un TS Saggezza; se fallisce subisce danni psichici pari al danno che subisci tu" + tail,
                 f"Beguiling Defenses, DC {_dc(ctx)}: the attacker makes a Wisdom save; on a failure it takes psychic damage equal to the damage you take" + tail)


DEFENSES_HIT = RollOptionSpec(
    key=DEFENSES, phase="damage_in", rolls=("damage_taken",), multiplier=0.5, slot="reaction", group="defenses", cost=Cost(feature_key=DEFENSES),
    effect=_halved, target_effect=lambda c, _i: TargetEffect(save_ability="wisdom", save_dc=_dc(c), note="beguiling_defenses"),
    label=_both("Difese Seducenti: dimezza il danno di questo colpo e l'attaccante rischia danni psichici", "Beguiling Defenses: halve the damage of this hit; the attacker risks psychic damage"))


def _charm_or_illusion(ctx: RuleContext) -> bool:
    """Un incantesimo di Ammaliamento o Illusione lanciato con un'azione e uno slot (né un trucchetto, né un lancio gratuito)."""
    return (ctx.spell is not None and ctx.spell.level >= 1 and not ctx.slotless
            and normalize_school(ctx.spell.school) in ("enchantment", "illusion")
            and re.match(r"^\s*1\s*(azione|action)\s*$", ctx.spell.casting_time or "", re.I) is not None)


def _free_misty(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    # parte della stessa azione: nessuno slot di turno (``free_cast_slot`` nullo)
    begin_state(ctx.char, StateSpec("bewitching_magic", ends_on=("new_turn", "rest_short", "rest_long", "manual"),
                                    data={"free_cast": "misty-step", "free_cast_slot": None}), BEWITCH)


BEWITCHING = RollOptionSpec(
    key=BEWITCH, phase="before", rolls=("cast",), available=_charm_or_illusion, on_confirm=_free_misty,
    label=_both("Magia Stregata: dopo questo incantesimo lanci Passo Velato senza slot", "Bewitching Magic: after this spell you cast Misty Step with no slot"),
    effect=lambda _c, _i: _both("Puoi lanciare Passo Velato senza slot nella stessa azione, dalla pagina degli incantesimi.",
                                "You may cast Misty Step with no slot as part of the same action, from the spells page."))

# ---------------------------------------------------------------------------
# Patrono Celestiale
# ---------------------------------------------------------------------------

CELESTIAL = "Patrono Celestiale"
LIGHT, SOUL = f"{P}healing_light", f"{P}radiant_soul"
CELESTIAL_SPELLS = (("aid", "cure-wounds", "guiding-bolt", "lesser-restoration", "light", "sacred-flame"), ("daylight", "revivify"),
                    ("guardian-of-faith", "wall-of-fire"), ("greater-restoration", "summon-celestial"))
celestial = _sub(CELESTIAL, "celestial")
WHO = {"self": ("Te stesso", "Yourself"), "ally": ("Una creatura che vedi entro 18 m", "A creature you see within 60 ft")}
LIGHT_USE = OnUse(
    slot="bonus", choose_amount=True, rolls="1d6", heal=lambda _c, rolled: rolled, heal_when=lambda _c, p: p.get("mode") == "self",
    heal_ally_when=lambda _c, p: p.get("mode") == "ally", ally_modes=("ally",), amount_ok=lambda c, n, _p: n <= max(1, _cha(c)),
    choices=(UseChoice("mode", _both("Chi curi", "Who you heal"), lambda _c: list(WHO), lambda k: _both(*WHO[k])),))


def _fire_or_radiant(ctx: RuleContext) -> bool:
    if ctx.spell is None:
        return False
    kinds = {spell_damage_type(ctx), canonical_damage_type(getattr(ctx.spell, "extra_damage_type", None))}
    return bool(kinds & {"radiant", "fire"})


RADIANT_BONUS = RollOptionSpec(
    key=SOUL, phase="before", rolls=("spell_damage",), once_per_turn=True, available=_fire_or_radiant, bonus=lambda c, _i: _cha(c),
    label=_both("Anima Radiosa: somma il Carisma al danno contro uno dei bersagli (una volta per turno)", "Radiant Soul: add your Charisma to the damage against one target (once per turn)"))


def resilience_hp(ctx: RuleContext) -> int | None:
    """PF temporanei di Resilienza Celestiale (livello + Carisma), o ``None`` senza il privilegio."""
    if getattr(ctx.class_row, "subclass_key", None) != "celestial" or ctx.class_level < 10:
        return None
    return max(0, ctx.class_level + _cha(ctx))


def resilience_ally_points(ctx: RuleContext) -> tuple[int, int]:
    """``(creature, PF temporanei per ciascuna)`` di Resilienza Celestiale: fino a cinque, metà livello + Carisma; ``(0, 0)`` senza."""
    if resilience_hp(ctx) is None:
        return 0, 0
    return 5, max(0, ctx.class_level // 2 + _cha(ctx))


def resilience_ally_text(ctx: RuleContext) -> dict[str, str] | None:
    if resilience_hp(ctx) is None:
        return None
    n = max(0, ctx.class_level // 2 + _cha(ctx))
    return _both(f"Resilienza Celestiale: fino a cinque creature che vedi ottengono {n} PF temporanei (metà livello + Carisma).",
                 f"Celestial Resilience: up to five creatures you see gain {n} temporary hit points (half level + Charisma).")


def _vengeance_check(ctx: RuleContext, params: dict) -> tuple[int, str] | None:
    return (409, "not_dying") if params.get("mode") == "self" and ctx.char.current_hit_points > 0 else None


def _vengeance_effect(ctx: RuleContext, _params: dict) -> TargetEffect:
    mod = _cha(ctx)
    return TargetEffect(condition="blinded", rounds=1, damage_dice=f"2d8+{mod}" if mod > 0 else "2d8")


def _vengeance_message(ctx: RuleContext, params: dict) -> dict[str, str]:
    tail = _both(" Le creature che scegli entro 9 m subiscono 2d8 + Carisma danni radiosi e sono Accecate fino alla fine del turno.",
                 " Creatures you choose within 30 ft take 2d8 + Charisma radiant damage and are Blinded until the end of the turn.")
    if params.get("mode") == "self":
        return _both(f"Recuperi {ctx.char.hit_points // 2} PF, metà del tuo massimo, e ti rialzi." + tail["it"],
                     f"You regain {ctx.char.hit_points // 2} hit points, half your maximum, and stand up." + tail["en"])
    return _both("L'alleato entro 18 m recupera metà dei suoi PF massimi e si rialza: dillo al GM." + tail["it"],
                 "The ally within 60 ft regains half their maximum hit points and stands up: tell the GM." + tail["en"])


def _stand_up(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    ctx.char.conditions = {**(ctx.char.conditions or {}), "prone": False}


VENGEANCE_KEY = f"{P}searing_vengeance"
# Prima del TS contro la morte (modale del tiro): metà dei PF massimi e si rialza, senza tirare. Il costo è l'uso del privilegio
VENGEANCE_SAVE = RollOptionSpec(
    key=f"{VENGEANCE_KEY}_save", phase="before", rolls=("death_save",), cost=Cost(feature_key=VENGEANCE_KEY),
    available=lambda c: c.char.current_hit_points <= 0, self_heal=lambda c, _i: c.char.hit_points // 2, on_confirm=_stand_up,
    target_effect=lambda c, _i: _vengeance_effect(c, {}),
    label=_both("Vendetta Ardente: prima del TS contro la morte torni a metà dei PF massimi e ti rialzi; le creature scelte entro 9 m sono Accecate",
                "Searing Vengeance: before the death save you regain half your maximum HP and stand up; the creatures you choose within 30 ft are Blinded"),
    effect=lambda c, _i: _vengeance_message(c, {"mode": "self"}))

VENGEANCE_USE = OnUse(
    usable_at_zero_hp=True, heal_ally_half_max=True,
    heal=lambda c, _r: c.char.hit_points // 2, heal_when=lambda _c, p: p.get("mode") == "self", check=_vengeance_check,
    heal_ally_when=lambda _c, p: p.get("mode") == "ally", ally_modes=("ally",),
    removal=ConditionRemoval(("prone",), count=None, ally=False, auto=lambda _c, p: ["prone"] if p.get("mode") == "self" else []), target_effect=_vengeance_effect, message=_vengeance_message,
    choices=(UseChoice("mode", _both("Chi sta per tirare contro la morte", "Who is about to roll a death save"), lambda _c: list(WHO),
                       lambda k: _both(*WHO[k])),))

# ---------------------------------------------------------------------------
# Patrono Immondo
# ---------------------------------------------------------------------------

FIEND = "Patrono Immondo"
LUCK, RESILIENCE_F, HURL = f"{P}dark_ones_own_luck", f"{P}fiendish_resilience", f"{P}hurl_through_hell"
FIEND_SPELLS = (("burning-hands", "command", "scorching-ray", "suggestion"), ("fireball", "stinking-cloud"), ("fire-shield", "wall-of-fire"),
                ("geas", "insect-plague"))
fiend = _sub(FIEND, "fiend")
LUCK_OPTION = RollOptionSpec(
    key=LUCK, phase="after_roll", after="add", rolls=("skill", "ability", "save", "death_save", "initiative"), cost=Cost(feature_key=LUCK),
    extra_dice=lambda _c, _i: "1d10", label=_both("Fortuna dell'Oscuro: spendi l'uso e somma 1d10 al tiro", "Dark One's Own Luck: spend the use and add 1d10 to the roll"))
RESISTABLE = [t for t in DAMAGE_TYPES if t != "force"]  # il tipo forza è escluso
RESILIENCE_USE = OnUse(
    state=_resilience_state, effect=_lock_resilience, check=_resilience_check,
    choices=(UseChoice("damage_type", _both("Tipo di danno", "Damage type"), lambda _c: list(RESISTABLE), lambda k: _both(LABELS_IT[k], k.title())),))


def _hurled(ctx: RuleContext, _inputs: dict) -> TargetEffect:
    return TargetEffect(condition="incapacitated", save_ability="charisma", save_dc=_dc(ctx), ends_at={"anchor": "source", "edge": "end", "count": 1},
                        note="hurl_through_hell_2024")


def _hurl(is_fiend: bool) -> RollOptionSpec:
    def text(ctx: RuleContext, _inputs: dict) -> dict[str, str]:
        dc = _dc(ctx)
        if is_fiend:
            return _both(f"TS Carisma, CD {dc}: se fallisce sparisce nei Piani Inferiori ed è Incapacitato fino alla fine del tuo prossimo turno. Nessun danno: è un immondo.",
                         f"Charisma save, DC {dc}: on a failure it vanishes into the Lower Planes and is Incapacitated until the end of your next turn. No damage: it is a fiend.")
        return _both(f"TS Carisma, CD {dc}: se fallisce sparisce nei Piani Inferiori, subisce 8d10 danni psichici (riportati a parte) ed è Incapacitato fino alla fine del tuo prossimo turno.",
                     f"Charisma save, DC {dc}: on a failure it vanishes into the Lower Planes, takes 8d10 psychic damage (reported apart) and is Incapacitated until the end of your next turn.")
    return RollOptionSpec(
        key=HURL + ("_fiend" if is_fiend else ""), phase="after_hit", rolls=("attack",), cost=Cost(feature_key=HURL), group=HURL, once_per_turn=True,
        extra_dice=None if is_fiend else (lambda _c, _i: "8d10"), separate_damage=not is_fiend, crit_doubles=False, target_effect=_hurled, effect=text,
        label=_both("Scagliare all'Inferno: il bersaglio colpito fa un TS Carisma" + (" (è un immondo, nessun danno)" if is_fiend else ", altrimenti 8d10 psichici"),
                    "Hurl Through Hell: the creature you hit makes a Charisma save" + (" (a fiend: no damage)" if is_fiend else ", or takes 8d10 psychic")))


# ---------------------------------------------------------------------------
# Patrono Grande Antico
# ---------------------------------------------------------------------------

OLD_ONE = "Patrono Grande Antico"
MIND, PSYCHIC, CLAIR, HEX, SHIELD = (f"{P}{k}" for k in ("awakened_mind", "psychic_spells", "clairvoyant_combatant", "eldritch_hex", "thought_shield"))
OLD_ONE_SPELLS = (("detect-thoughts", "dissonant-whispers", "phantasmal-force", "tashas-hideous-laughter"), ("clairvoyance", "hunger-of-hadar"),
                  ("confusion", "summon-aberration"), ("modify-memory", "telekinesis"))
oldone = _sub(OLD_ONE, "great_old_one")
MIND_USE = OnUse(
    slot="bonus", state=lambda c, _p: StateSpec("awakened_mind", rounds=c.class_level * 10, ends_on=("rest_long", "manual")),
    message=lambda c, _p: _both(f"Legame telepatico con una creatura che vedi entro 9 m per {c.class_level} minuti; distanza: {max(1, _cha(c))} miglia. Un nuovo legame sostituisce il precedente.",
                                f"Telepathic link with a creature you see within 30 ft for {c.class_level} minutes; range: {max(1, _cha(c))} miles. A new link replaces the old one."))
PSYCHIC_TYPE = RollOptionSpec(
    key=PSYCHIC, phase="before", rolls=("spell_damage",), damage_type_to="psychic",
    available=lambda c: c.spell is not None and bool(c.spell.damage_dice) and spell_damage_type(c) not in (None, "psychic"),
    label=_both("Incantesimi Psichici: il danno di questo incantesimo da warlock è psichico", "Psychic Spells: this warlock spell's damage is psychic"))


def _has_link(ctx: RuleContext) -> bool:
    return any(s.get("key") == "awakened_mind" for s in ctx.char.active_states or [])


CLAIR_USE = _restorable(
    available=_has_link,
    target_effect=lambda c, _p: TargetEffect(save_ability="wisdom", save_dc=_dc(c), rounds=c.class_level * 10, note="clairvoyant_combatant"),
    message=lambda c, _p: _both(f"CD {_dc(c)}: la creatura collegata fa un TS Saggezza; se fallisce ha svantaggio ai tiri per colpire contro di te e tu hai vantaggio contro di lei per la durata del legame.",
                                f"DC {_dc(c)}: the linked creature makes a Wisdom save; on a failure it has disadvantage on attack rolls against you and you have advantage against it for the link's duration."))


def _hex(ability: str) -> RollOptionSpec:
    return RollOptionSpec(
        key=f"{HEX}_{ability}", phase="before", rolls=("cast",), group="eldritch_hex", available=lambda c: _spell_is(c, "hex"),
        target_effect=lambda _c, _i: TargetEffect(note=f"eldritch_hex_{ability}"),
        effect=lambda _c, _i: _both(f"Il bersaglio di Malia ha svantaggio anche ai tiri salvezza di {ability} per la durata.",
                                    f"The target of Hex also has disadvantage on {ability} saving throws for the duration."),
        label=_both(f"Maledizione Occulta: svantaggio anche ai TS di {ability}", f"Eldritch Hex: disadvantage also on {ability} saves"))


def _thrall_text(ctx: RuleContext, _i: dict) -> dict[str, str]:
    n = ctx.class_level + _cha(ctx)
    return _both(f"Evocare Aberrazione senza Concentrazione, per 1 minuto. L'Aberrazione ottiene {n} PF temporanei (livello + Carisma); la prima volta per turno "
                 "che colpisce una creatura sotto Malia infligge danni psichici extra pari al bonus di danno di Malia.",
                 f"Summon Aberration with no Concentration, for 1 minute. The Aberration gains {n} temporary hit points (level + Charisma); the first time each turn "
                 "it hits a creature under Hex it deals extra psychic damage equal to Hex's damage bonus.")


THRALL_OPTION = RollOptionSpec(
    key=THRALL_CAST, phase="before", rolls=("cast",), available=lambda c: _spell_is(c, "summon-aberration"), effect=_thrall_text,
    label=_both("Creare Servitore: senza Concentrazione, per 1 minuto", "Create Thrall: no Concentration, for 1 minute"))

# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

SUBCLASS_ROWS = (
    # Patrono Fatato
    *_spells("archfey", ARCHFEY, "archfey_spells", "Incantesimi del Signore Fatato", "Archfey Spells", 159, ARCHFEY_SPELLS),
    archfey("steps_of_the_fey", 3, "Passi del Fatato", "Steps of the Fey", 159,
            ("Lanci Passo Velato senza slot (azione bonus): usi pari al Carisma, riposo lungo. A ogni lancio un effetto: Passo Rinfrescante o Provocatorio.",
             "Cast Misty Step with no slot (bonus action): uses equal to Charisma, long rest. Each cast adds an effect: Refreshing or Taunting Step."),
            uses=Uses(ability="charisma", minimum=1), restoration="long_rest", free_spell="misty-step", dc_ability="charisma",
            roll_options=(_refreshing(True), _refreshing(False), STEP_TAUNTING), passive=True),
    archfey("misty_escape", 6, "Fuga Velata", "Misty Escape", 159,
            ("Reazione, quando subisci danno: lanci Passo Velato spendendo un uso di Passi del Fatato. Aggiunge Passo Scomparso e Passo Terrificante.",
             "Reaction, when you take damage: cast Misty Step spending a use of Steps of the Fey. Adds Disappearing and Terrifying Step."),
            "reaction", on_use=ESCAPE_USE, roll_options=(STEP_DISAPPEARING, STEP_TERRIFYING), dc_ability="charisma"),
    archfey("beguiling_defenses", 10, "Difese Seducenti", "Beguiling Defenses", 159,
            ("Immune ad Affascinato. Reazione, se una creatura ti colpisce: danno dimezzato e TS Saggezza o subisce psichici. Un uso, riposo lungo o slot di Patto.",
             "Immune to Charmed. Reaction, when a creature hits you: halved damage and a Wisdom save or psychic damage. One use, long rest or a Pact slot."),
            uses=Uses(table={10: 1}), restoration="long_rest", condition_immunities=("charmed",), dc_ability="charisma",
            roll_options=(DEFENSES_HIT, _slot_variant(DEFENSES_HIT)), passive=True),
    archfey("bewitching_magic", 14, "Magia Stregata", "Bewitching Magic", 160,
            ("Dopo un incantesimo di Ammaliamento o Illusione lanciato con un'azione e uno slot, lanci Passo Velato nella stessa azione senza slot.",
             "After an Enchantment or Illusion spell cast with an action and a slot, you cast Misty Step as part of the same action with no slot."),
            roll_options=(BEWITCHING,), passive=True),
    # Patrono Celestiale
    *_spells("celestial", CELESTIAL, "celestial_spells", "Incantesimi Celestiali", "Celestial Spells", 160, CELESTIAL_SPELLS),
    celestial("healing_light", 3, "Luce Guaritrice", "Healing Light", 160,
              ("Riserva di d6 pari a 1 + livello da warlock. Azione bonus: spendi fino a Carisma dadi e curi te o una creatura entro 18 m. Riposo lungo.",
               "A pool of d6s equal to 1 + warlock level. Bonus action: spend up to Charisma dice and heal yourself or a creature within 60 ft. Long rest."),
              "bonus_action", uses=Uses(table={3: 1}, per_level=1), restoration="long_rest", on_use=LIGHT_USE),
    celestial("radiant_soul", 6, "Anima Radiosa", "Radiant Soul", 160,
              ("Resistenza ai danni radiosi. Un incantesimo che infligge danni radiosi o da fuoco somma il Carisma al danno contro un bersaglio, una volta per turno.",
               "Resistance to radiant damage. A spell dealing radiant or fire damage adds your Charisma to its damage against one target, once per turn."),
              roll_options=(RADIANT_BONUS,), modifiers=(Modifier("resistance:radiant", 1, source=f"feature:{SOUL}"),), passive=True),
    celestial("celestial_resilience", 10, "Resilienza Celestiale", "Celestial Resilience", 161,
              ("Con Astuzia Magica e a ogni riposo breve o lungo ottieni PF temporanei pari a livello + Carisma; fino a cinque creature, metà livello + Carisma.",
               "With Magical Cunning and at each short or long rest you gain temporary HP equal to level + Charisma; up to five creatures, half level + Charisma."),
              rest_temp_hp=lambda c: resilience_hp(c) or 0, rest_temp_hp_ally=resilience_ally_points, passive=True),
    celestial("searing_vengeance", 14, "Vendetta Ardente", "Searing Vengeance", 161,
              ("Prima di un TS contro la morte tuo o di un alleato entro 18 m: metà dei PF massimi e si rialza; chi scegli entro 9 m subisce radiosi 2d8 + Carisma e Accecato. Riposo lungo.",
               "Before your or an ally's death save within 60 ft: half maximum HP and stands up; chosen creatures within 30 ft take 2d8 + Charisma radiant and are Blinded. Long rest."),
              "special", uses=Uses(table={14: 1}), restoration="long_rest", on_use=VENGEANCE_USE, roll_options=(VENGEANCE_SAVE,), dc_ability="charisma"),
    # Patrono Immondo
    fiend("dark_ones_blessing", 3, "Benedizione dell'Oscuro", "Dark One's Blessing", 161,
          ("Quando porti a 0 PF un nemico (o lo fa un altro entro 3 m) ottieni PF temporanei pari a Carisma + livello da warlock (minimo 1); non si sommano.",
           "When you reduce an enemy to 0 hit points (or another does within 10 ft) you gain temporary hit points equal to Charisma + warlock level (minimum 1)."),
          "special", on_use=BLESSING_USE),
    *_spells("fiend", FIEND, "fiend_spells", "Incantesimi Immondi", "Fiend Spells", 161, FIEND_SPELLS),
    fiend("dark_ones_own_luck", 6, "Fortuna dell'Oscuro", "Dark One's Own Luck", 162,
          ("Dopo una prova di caratteristica o un TS, anche visto il risultato, aggiungi 1d10. Usi pari al Carisma, riposo lungo; non più di una volta per tiro.",
           "After an ability check or saving throw, even seeing the result, add 1d10. Uses equal to Charisma, long rest; no more than once per roll."),
          uses=Uses(ability="charisma", minimum=1), restoration="long_rest", roll_options=(LUCK_OPTION,)),
    fiend("fiendish_resilience", 10, "Resilienza Immonda", "Fiendish Resilience", 162,
          ("A ogni riposo breve o lungo scegli un tipo di danno, tranne forza: ne hai la resistenza finché ne scegli un altro.",
           "At each short or long rest you choose a damage type other than force: you resist it until you choose another."),
          "special", on_use=RESILIENCE_USE,
          modifiers=tuple(Modifier(f"resistance:{t}", 1, when=_resilience_active(t), source=f"feature:{RESILIENCE_F}") for t in RESISTABLE)),
    fiend("hurl_through_hell", 14, "Scagliare all'Inferno", "Hurl Through Hell", 162,
          ("Su un colpo con attacco: TS Carisma, se fallisce sparisce, subisce 8d10 psichici (non gli immondi) ed è Incapacitato. Un uso, riposo lungo o slot di Patto.",
           "On an attack hit: Charisma save; on a failure it vanishes, takes 8d10 psychic (not fiends) and is Incapacitated. One use, long rest or a Pact slot."),
          uses=Uses(table={14: 1}), restoration="long_rest", dc_ability="charisma",
          roll_options=(_hurl(False), _hurl(True), _slot_variant(_hurl(False)), _slot_variant(_hurl(True))), passive=True),
    # Patrono Grande Antico
    oldone("awakened_mind", 3, "Mente Risvegliata", "Awakened Mind", 162,
           ("Azione bonus: telepatia con una creatura che vedi entro 9 m, a Carisma miglia, per tanti minuti quanti i livelli da warlock. Un nuovo legame sostituisce il vecchio.",
            "Bonus action: telepathy with a creature you see within 30 ft, out to Charisma miles, for minutes equal to your warlock levels. A new link replaces the old."),
           "bonus_action", on_use=MIND_USE),
    *_spells("great_old_one", OLD_ONE, "great_old_one_spells", "Incantesimi del Grande Antico", "Great Old One Spells", 163, OLD_ONE_SPELLS),
    oldone("psychic_spells", 3, "Incantesimi Psichici", "Psychic Spells", 163,
           ("Un incantesimo da warlock che infligge danni può farli psichici. Quelli di Ammaliamento o Illusione si lanciano senza componenti verbali né somatiche.",
            "A warlock spell that deals damage can deal psychic damage. Enchantment or Illusion ones are cast without verbal or somatic components."),
           roll_options=(PSYCHIC_TYPE,), passive=True),
    oldone("clairvoyant_combatant", 6, "Combattente Chiaroveggente", "Clairvoyant Combatant", 163,
           ("Formando il legame di Mente Risvegliata: TS Saggezza; se fallisce, svantaggio ai suoi attacchi contro di te e vantaggio ai tuoi contro di lei. Riposo breve o slot di Patto.",
            "Forming the Awakened Mind link: Wisdom save; on a failure, disadvantage on its attacks against you and advantage on yours against it. Short rest or a Pact slot."),
           "special", uses=Uses(table={6: 1}), restoration="short_rest", on_use=CLAIR_USE, dc_ability="charisma"),
    oldone("eldritch_hex", 10, "Maledizione Occulta", "Eldritch Hex", 163,
           ("Malia è sempre preparato. Lanciandolo scegli una caratteristica: il bersaglio ha svantaggio anche ai suoi tiri salvezza per la durata.",
            "Hex is always prepared. Casting it you choose an ability: the target also has disadvantage on its saving throws for the duration."),
           granted_spells=("hex",), roll_options=tuple(_hex(a) for a in ABILITIES), passive=True),
    oldone("thought_shield", 10, "Scudo del Pensiero", "Thought Shield", 163,
           ("Pensieri illeggibili senza consenso; resistenza ai danni psichici; chi te ne infligge subisce lo stesso ammontare di danni psichici.",
            "Thoughts unreadable without consent; resistance to psychic damage; whoever deals you psychic damage takes the same amount."),
           modifiers=(Modifier("resistance:psychic", 1, source=f"feature:{SHIELD}"),), roll_options=(THOUGHT_REFLECTION,), passive=True),
    oldone("create_thrall", 14, "Creare Servitore", "Create Thrall", 163,
           ("Evocare Aberrazione senza Concentrazione, 1 minuto. L'Aberrazione ottiene PF temporanei (livello + Carisma) e danni psichici extra contro chi è sotto Malia.",
            "Summon Aberration with no Concentration, 1 minute. The Aberration gains temporary HP (level + Charisma) and extra psychic damage against a Hexed creature."),
           roll_options=(THRALL_OPTION,), passive=True),
)

"""Warlock 2014 e i suoi patroni: il Signore Fatato, l'Immondo e il Grande Antico.

Valori dalla scheda ``docs/superpowers/rules/2014/classes/warlock.md``; i testi sono nostri, mai quelli del manuale.
Le suppliche stanno in ``warlock_invocations``; gli slot di Patto in ``core/data/spell_slots.py`` (pool ``is_pact``).
Dono del Patto e suppliche sono scelte di livello (``pact_boon``, ``invocations``); l'Arcanum Mistico e le suppliche
«una volta per riposo lungo» si lanciano dalla pagina degli incantesimi (vedi ``core.rules.pact_casts``).
"""
from __future__ import annotations

import json
from typing import Any

from core.data.damage_types import DAMAGE_TYPES, LABELS_IT
from core.rules.catalog._common import feature, state_on
from core.rules.catalog.y2014 import warlock_invocations as inv
from core.rules.catalog.y2014.warlock_invocations import BOON_GROUP, INVOCATIONS, PACT_WEAPON, PREREQUISITES, is_blast
from core.rules.states import begin_state
from core.rules.types import (
    ChoiceSpec, Cost, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, TargetEffect, UseChoice, Uses, UseToggle,
)

ED, CK = "2014", "warlock"
ARCANUM = (("6", 11, 6), ("7", 13, 7), ("8", 15, 8), ("9", 17, 9))  # chiave, livello da warlock, livello dell'incantesimo
LUCK, HURL = f"{CK}.dark_ones_own_luck", f"{CK}.hurl_through_hell"
LOCK = "fiendish_resilience_lock"


def _say(it: str, en: str):
    return lambda _ctx, _inputs: {"it": it, "en": en}


def _mod(ctx: RuleContext, ability: str) -> int:
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    return effective_ability_mod(ctx.char, ability)


def _dc(ctx: RuleContext) -> int:
    return 8 + ctx.char.proficiency_bonus + _mod(ctx, "charisma")


def _till_my_next_turn() -> dict:
    return {"anchor": "source", "edge": "end", "count": 1}


def _no_options(_ctx: RuleContext) -> list[str]:
    return []


def _mode_choice(key: str = "mode") -> UseChoice:
    return UseChoice(key, {"it": "Effetto", "en": "Effect"}, lambda _c: ["charmed", "frightened"],
                     lambda k: {"it": "Affascinate", "en": "Charmed"} if k == "charmed" else {"it": "Spaventate", "en": "Frightened"})


# ---------------------------------------------------------------------------
# Scelte: suppliche e Dono del Patto
# ---------------------------------------------------------------------------

def available_invocations(ctx: RuleContext) -> list[str]:
    """Le suppliche i cui prerequisiti sono soddisfatti: livello da warlock, Dono del Patto e trucchetto deflagrazione occulta."""
    boons = (getattr(ctx.class_row, "options", None) or {}).get(BOON_GROUP, [])
    blast = any(is_blast(s) for s in ctx.char.spells or [])
    return [key for key, (level, boon, needs_blast) in PREREQUISITES.items()
            if ctx.class_level >= level and (boon is None or boon in boons) and (not needs_blast or blast)]


INVOCATION_CHOICE = ChoiceSpec(group=INVOCATIONS, levels={2: 2, 5: 3, 7: 4, 9: 5, 12: 6, 15: 7, 18: 8}, replaceable=True,
                               options=available_invocations, import_options=lambda _c: list(PREREQUISITES))
BOON_CHOICE = ChoiceSpec(group=BOON_GROUP, levels={3: 1}, options=lambda _c: ["chain", "blade", "tome"])


# ---------------------------------------------------------------------------
# Dono del Patto
# ---------------------------------------------------------------------------

# arma da mischia del patto: chiave -> (dado, tipo di danno, proprietà, dado a due mani)
PACT_WEAPONS: dict[str, tuple[str, str, tuple[str, ...], str | None]] = {
    "club": ("1d4", "bludgeoning", ("light",), None), "dagger": ("1d4", "piercing", ("finesse", "light", "thrown"), None),
    "greatclub": ("1d8", "bludgeoning", ("two-handed",), None), "handaxe": ("1d6", "slashing", ("light", "thrown"), None),
    "javelin": ("1d6", "piercing", ("thrown",), None), "light_hammer": ("1d4", "bludgeoning", ("light", "thrown"), None),
    "mace": ("1d6", "bludgeoning", (), None), "quarterstaff": ("1d6", "bludgeoning", ("versatile",), "1d8"),
    "sickle": ("1d4", "slashing", ("light",), None), "spear": ("1d6", "piercing", ("thrown", "versatile"), "1d8"),
    "battleaxe": ("1d8", "slashing", ("versatile",), "1d10"), "flail": ("1d8", "bludgeoning", (), None),
    "glaive": ("1d10", "slashing", ("heavy", "reach", "two-handed"), None), "greataxe": ("1d12", "slashing", ("heavy", "two-handed"), None),
    "greatsword": ("2d6", "slashing", ("heavy", "two-handed"), None), "halberd": ("1d10", "slashing", ("heavy", "reach", "two-handed"), None),
    "lance": ("1d12", "piercing", ("reach",), None), "longsword": ("1d8", "slashing", ("versatile",), "1d10"),
    "maul": ("2d6", "bludgeoning", ("heavy", "two-handed"), None), "morningstar": ("1d8", "piercing", (), None),
    "pike": ("1d10", "piercing", ("heavy", "reach", "two-handed"), None), "rapier": ("1d8", "piercing", ("finesse",), None),
    "scimitar": ("1d6", "slashing", ("finesse", "light"), None), "shortsword": ("1d6", "piercing", ("finesse", "light"), None),
    "trident": ("1d6", "piercing", ("thrown", "versatile"), "1d8"), "war_pick": ("1d8", "piercing", (), None),
    "warhammer": ("1d8", "bludgeoning", ("versatile",), "1d10"), "whip": ("1d4", "slashing", ("finesse", "reach"), None),
}


def _weapon_label(key: str) -> dict[str, str]:
    from core.rules.weapons import WEAPONS  # import locale: weapons usa i tipi
    found = WEAPONS.get(key)
    return {"it": found.it if found else key, "en": found.en if found else key.replace("_", " ").title()}


def _create_pact_weapon(ctx: RuleContext, params: dict) -> None:
    """Crea l'arma del patto in mano: l'arma di prima del patto (se c'era) scompare, quella in mano torna nello zaino.
    Competente (nessuna categoria) e magica (modificatore ``magic_weapon`` sull'oggetto)."""
    from core.db.models import EquipmentSlot, Item  # import locale: i modelli non si importano dal catalogo
    dice, dtype, props, versatile = PACT_WEAPONS[params["weapon"]]
    label = _weapon_label(params["weapon"])
    char = ctx.char
    for item in [i for i in char.items if _is_pact(i)]:
        char.items.remove(item)
    for item in char.items:
        if item.is_equipped and item.equipment_slot == EquipmentSlot.MAIN_HAND:
            item.is_equipped, item.equipment_slot = False, None
    meta = {"damage_dice": dice, "damage_type": dtype, "properties": list(props), "base_weapon": params["weapon"], PACT_WEAPON: True,
            **({"versatile_dice": versatile} if versatile else {})}
    char.items.append(Item(character_id=char.id, name=f"{label['it']} del patto", item_type="weapon", quantity=1, weight=0.0,
                           item_metadata=json.dumps(meta), is_equipped=True, equipment_slot=EquipmentSlot.MAIN_HAND))


def _is_pact(item: Any) -> bool:
    from core.game.item_bonuses import item_meta  # import locale
    return bool(item_meta(item).get(PACT_WEAPON))


BLADE_USE = OnUse(
    slot="action", effect=_create_pact_weapon,
    choices=(UseChoice("weapon", {"it": "Forma dell'arma", "en": "Weapon form"}, lambda _c: list(PACT_WEAPONS),
                       lambda k: _weapon_label(k)),))
CHAIN_USE = OnUse(forgoes_attack=True)  # rinunci a un attacco: il famiglio attacca con la sua reazione (pagina dei compagni)


# ---------------------------------------------------------------------------
# Arcanum Mistico, Maestro dell'Occulto
# ---------------------------------------------------------------------------

def _restore_pact_slots(ctx: RuleContext, _params: dict) -> None:
    for slot in ctx.char.spell_slots or []:
        if slot.is_pact:
            slot.used = 0


ELDRITCH_MASTER_USE = OnUse(cost=1, effect=_restore_pact_slots)


def _arcanum(grade: str, level: int, spell_level: int):
    return feature(
        f"mystic_arcanum_{grade}", CK, ED, level, "Arcanum Mistico / Mystic Arcanum (Warlock 11, pag. 116)",
        (f"Arcanum Mistico ({spell_level}° livello)", f"Mystic Arcanum (level {spell_level})"),
        (f"Un incantesimo da warlock di {spell_level}° livello scelto da te: lo lanci una volta per riposo lungo senza slot, dalla pagina degli incantesimi.",
         f"A warlock spell of level {spell_level} of your choice: you cast it once per long rest with no slot, from the spells page."),
        uses=Uses(table={level: 1}), restoration="long_rest", arcanum_group=f"arcanum_{grade}",
        choices=(ChoiceSpec(group=f"arcanum_{grade}", levels={level: 1}, options=_no_options, spell_pick="extra", spell_level=spell_level,
                            spell_exact=True),))


# ---------------------------------------------------------------------------
# Il Signore Fatato
# ---------------------------------------------------------------------------

def _fey_state(ctx: RuleContext, params: dict) -> StateSpec:
    return StateSpec("fey_presence", ends_on=("new_turn", "turn_end_counted", "rest_short", "rest_long", "manual"),
                     data={"skip_new_turns": 1, "dc": _dc(ctx), "save": "wisdom", "mode": params.get("mode"),
                           "others": [f"{CK}.fey_presence"]})


FEY_PRESENCE_USE = OnUse(
    slot="action", state=_fey_state, choices=(_mode_choice(),),
    target_effect=lambda ctx, p: TargetEffect(condition=p["mode"], save_ability="wisdom", save_dc=_dc(ctx), ends_at=_till_my_next_turn()))

MISTY_ESCAPE_USE = OnUse(
    slot="reaction",
    state=StateSpec("misty_escape", condition="invisible", ends_on=("new_turn", "attack", "cast", "rest_short", "rest_long", "manual"),
                    data={"others": [f"{CK}.misty_escape"]}))

BEGUILING_DEFENSES_USE = OnUse(
    slot="reaction", target_effect=lambda ctx, _p: TargetEffect(condition="charmed", save_ability="wisdom", save_dc=_dc(ctx), rounds=10))


def _delirium_state(ctx: RuleContext, params: dict) -> StateSpec:
    return StateSpec("dark_delirium", rounds=10, ends_on=("concentration_end", "manual"),
                     data={"dc": _dc(ctx), "save": "wisdom", "mode": params.get("mode"), "others": [f"{CK}.dark_delirium"]})


DARK_DELIRIUM_USE = OnUse(
    slot="action", concentration=True, state=_delirium_state, choices=(_mode_choice(),),
    target_effect=lambda ctx, p: TargetEffect(condition=p["mode"], save_ability="wisdom", save_dc=_dc(ctx), rounds=10))


# ---------------------------------------------------------------------------
# L'Immondo
# ---------------------------------------------------------------------------

def _blessing_temp_hp(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    """PF temporanei = Carisma + livello da warlock (minimo 1); non si sommano a quelli che hai: vale il maggiore."""
    ctx.char.temp_hp = max(ctx.char.temp_hp or 0, _blessing_value(ctx))


def _blessing_value(ctx: RuleContext) -> int:
    return max(1, _mod(ctx, "charisma") + ctx.class_level)


def _blessing(key: str, rolls: str, phase: str, label: tuple[str, str]) -> RollOptionSpec:
    return RollOptionSpec(
        key=f"{CK}.dark_ones_blessing{key}", phase=phase, rolls=(rolls,), on_confirm=_blessing_temp_hp,
        label={"it": label[0], "en": label[1]},
        effect=lambda c, _i: {"it": f"Ottieni {_blessing_value(c)} PF temporanei (se più di quelli che hai).",
                              "en": f"You gain {_blessing_value(c)} temporary hit points (if more than you have)."})


BLESSING_ATTACK = _blessing("", "attack", "after_hit", (
    "Benedizione dell'Oscuro: hai portato a 0 PF una creatura ostile con questo colpo?",
    "Dark One's Blessing: did this hit reduce a hostile creature to 0 hit points?"))
BLESSING_SPELL = _blessing("_spell", "spell_damage", "before", (
    "Benedizione dell'Oscuro: questo danno porta a 0 PF una creatura ostile?",
    "Dark One's Blessing: does this damage reduce a hostile creature to 0 hit points?"))

DARK_LUCK = RollOptionSpec(
    key=LUCK, phase="after_roll", after="add", rolls=("skill", "ability", "save"), cost=Cost(feature_key=LUCK),
    extra_dice=lambda _c, _i: "1d10",
    label={"it": "Fortuna dell'Oscuro: spendi l'uso e somma 1d10 al tiro", "en": "Dark One's Own Luck: spend the use and add 1d10 to the roll"})


def _resilience_active(damage_type: str):
    def active(ctx: RuleContext) -> bool:
        found = next((s for s in ctx.char.active_states or [] if s.get("key") == "fiendish_resilience"), None)
        return found is not None and (found.get("data") or {}).get("damage_type") == damage_type
    return active


def _resilience_state(_ctx: RuleContext, params: dict) -> StateSpec:
    return StateSpec("fiendish_resilience", ends_on=("manual",), data={"damage_type": params["damage_type"]})


def _lock_resilience(ctx: RuleContext, _params: dict) -> None:
    """La scelta si cambia a ogni riposo, breve o lungo: fino ad allora non se ne fa un'altra."""
    begin_state(ctx.char, StateSpec(LOCK, ends_on=("rest_short", "rest_long"), data={"internal": True}), f"{CK}.fiendish_resilience")


def _resilience_check(ctx: RuleContext, _params: dict) -> tuple[int, str] | None:
    return (409, "already_chosen") if state_on(ctx, LOCK) else None


FIENDISH_RESILIENCE_USE = OnUse(
    state=_resilience_state, effect=_lock_resilience, check=_resilience_check,
    choices=(UseChoice("damage_type", {"it": "Tipo di danno", "en": "Damage type"}, lambda _c: list(DAMAGE_TYPES),
                       lambda k: {"it": LABELS_IT[k], "en": k.title()}),))

_HURL_LABEL = ("Scagliare all'Inferno: il bersaglio colpito scompare fino alla fine del tuo prossimo turno",
               "Hurl Through Hell: the creature you hit vanishes until the end of your next turn")


def _hurled(_ctx: RuleContext, _inputs: dict) -> TargetEffect:
    return TargetEffect(condition="custom:hurled", ends_at=_till_my_next_turn(), note="hurl_through_hell")


HURL_NONFIEND = RollOptionSpec(
    key=HURL, phase="after_hit", rolls=("attack",), cost=Cost(feature_key=HURL), group=HURL, extra_dice=lambda _c, _i: "10d10",
    separate_damage=True, crit_doubles=False, target_effect=_hurled,
    label={"it": _HURL_LABEL[0] + " e subisce 10d10 danni psichici (non è un immondo)",
           "en": _HURL_LABEL[1] + " and takes 10d10 psychic damage (it is not a fiend)"},
    effect=_say("Subisce 10d10 danni psichici (riportati a parte) e torna alla fine del tuo prossimo turno.",
                "It takes 10d10 psychic damage (reported apart) and returns at the end of your next turn."))
HURL_FIEND = RollOptionSpec(
    key=f"{HURL}_fiend", phase="after_hit", rolls=("attack",), cost=Cost(feature_key=HURL), group=HURL, target_effect=_hurled,
    label={"it": _HURL_LABEL[0] + ", senza danni (è un immondo)", "en": _HURL_LABEL[1] + ", no damage (it is a fiend)"},
    effect=_say("Nessun danno: è un immondo. Torna alla fine del tuo prossimo turno.", "No damage: it is a fiend. It returns at the end of your next turn."))


# ---------------------------------------------------------------------------
# Il Grande Antico
# ---------------------------------------------------------------------------

def _ward_state(_ctx: RuleContext, params: dict) -> StateSpec:
    return StateSpec("entropic_ward", ends_on=("new_turn", "turn_end_counted", "rest_short", "rest_long", "manual"),
                     data={"skip_new_turns": 1, "missed": bool(params.get("missed")), "others": [f"{CK}.entropic_ward"]})


ENTROPIC_WARD_USE = OnUse(
    slot="reaction", state=_ward_state, target_effect=lambda _c, _p: TargetEffect(condition="custom:entropic_ward"),
    toggles=(UseToggle("missed", {"it": "L'attacco è fallito", "en": "The attack missed"}),))


def _ward_missed(ctx: RuleContext) -> bool:
    found = next((s for s in ctx.char.active_states or [] if s.get("key") == "entropic_ward"), None)
    return found is not None and bool((found.get("data") or {}).get("missed"))


ENTROPIC_ADVANTAGE = RollOptionSpec(
    key=f"{CK}.entropic_ward_advantage", phase="before", rolls=("attack",), mode="advantage", cost=Cost(state_key="entropic_ward"),
    available=_ward_missed,
    label={"it": "Interdizione Entropica: attacchi la creatura che ti ha mancato con vantaggio",
           "en": "Entropic Ward: attack the creature that missed you with advantage"})


def _thought_reflection(ctx: RuleContext, _inputs: dict) -> dict:
    # la resistenza dimezza il danno prima che arrivi a te; l'attaccante subisce quanto subisci tu
    taken = None if ctx.damage is None else ctx.damage // 2
    it = "L'attaccante subisce lo stesso ammontare di danni psichici che subisci tu"
    en = "The attacker takes the same amount of psychic damage that you take"
    return {"it": it + (f": {taken}." if taken is not None else "."), "en": en + (f": {taken}." if taken is not None else ".")}


THOUGHT_REFLECTION = RollOptionSpec(
    key=f"{CK}.thought_shield_reflection", phase="damage_in", rolls=("damage_taken",),
    available=lambda c: c.damage_type == "psychic",
    label={"it": "Scudo del Pensiero: chi ti infligge i danni psichici subisce lo stesso ammontare",
           "en": "Thought Shield: whoever deals you psychic damage takes the same amount"},
    effect=_thought_reflection, target_effect=lambda _c, _i: TargetEffect(note="thought_shield"))

CREATE_THRALL_USE = OnUse(
    slot="action", state=StateSpec("create_thrall", ends_on=("manual",), data={"others": [f"{CK}.create_thrall"]}),
    target_effect=lambda _c, _p: TargetEffect(condition="charmed"))


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

def _patron(key: str, subclass: str, level: int, title: str, name: tuple[str, str], summary: tuple[str, str],
            action_type: str | None = None, **kw: Any):
    return feature(key, CK, ED, level, title, name, summary, action_type, subclass=subclass, **kw)


def _expanded(subclass: str, title: str, summary: tuple[str, str]):
    return _patron(f"expanded_spell_list_{subclass}", subclass, 1, title, ("Lista Ampliata degli Incantesimi", "Expanded Spell List"), summary, passive=True)


def _boon_row(key: str, title: str, name: tuple[str, str], summary: tuple[str, str], action_type: str | None = None, **kw: Any):
    return feature(f"pact_of_the_{key}", CK, ED, 3, title, name, summary, action_type, option_group=BOON_GROUP, option_key=key, **kw)


FEATURES = (
    feature("hit_points", CK, ED, 1, "Punti Ferita e Competenze / Hit Points and Proficiencies (Warlock 1, pag. 114)",
            ("Punti Ferita e Competenze", "Hit Points and Proficiencies"),
            ("Dado vita d8; al 1° livello 8 + Costituzione, poi d8 (o 5) + Costituzione. Armature leggere, armi semplici, TS Saggezza e Carisma, 2 abilità fra sette.",
             "Hit die d8; level 1 gives 8 + Constitution, then d8 (or 5) + Constitution. Light armor, simple weapons, Wisdom and Charisma saves, 2 skills from seven."),
            no_row=True, covered_by="api/routers/classes.py create_class_for_character e total_base_hp; core/rules/proficiencies.py "
                                    "(class_proficiencies e ClassSkillChoice); equipaggiamento: lavori-successivi; test_hit_points_use_the_d8_and_follow_constitution"),
    feature("otherworldly_patron", CK, ED, 1, "Patrono Ultraterreno / Otherworldly Patron (Warlock 1, pag. 115)",
            ("Patrono Ultraterreno", "Otherworldly Patron"),
            ("Al 1° livello si sceglie il Signore Fatato, l'Immondo o il Grande Antico: privilegi ai livelli 1, 6, 10 e 14.",
             "At 1st level you choose the Archfey, the Fiend or the Great Old One: features at levels 1, 6, 10 and 14."),
            no_row=True, covered_by="core/rules/subclasses.py (match_subclass) e il campo sottoclasse della classe"),
    feature("pact_magic", CK, ED, 1, "Magia del Patto / Pact Magic (Warlock 1, pag. 115)", ("Magia del Patto", "Pact Magic"),
            ("Carisma; CD 8 + competenza + Carisma. Pochi slot tutti dello stesso livello, tornano con un riposo breve o lungo; trucchetti 2/3/4, conosciuti 2-15.",
             "Charisma; DC 8 + proficiency + Charisma. A few slots all of one level, back on a short or long rest; cantrips 2/3/4, known spells 2-15."),
            no_row=True, covered_by="core/data/spell_slots.py (compute_pact_slots, pool is_pact), core/rules/spellcasting.py (known_limits) e "
                                    "api/routers/spells.py _consume_cast (slot_id sceglie il pool); test_pact_slots_follow_the_table"),
    feature("eldritch_invocations", CK, ED, 2, "Suppliche Occulte / Eldritch Invocations (Warlock 2, pag. 115)",
            ("Suppliche Occulte", "Eldritch Invocations"),
            ("Due suppliche al 2° livello, fino a otto al 18°: ne sostituisci una a ogni livello. Alcune chiedono un livello, un Dono del Patto o un trucchetto.",
             "Two invocations at 2nd level, up to eight at 18th: you replace one at each level. Some need a level, a Pact Boon or a cantrip."),
            no_row=True, choices=(INVOCATION_CHOICE,),
            covered_by="ChoiceSpec invocations di questa riga e le righe delle suppliche; test_invocations_known_follow_the_level"),
    feature("pact_boon", CK, ED, 3, "Dono del Patto / Pact Boon (Warlock 3, pag. 115)", ("Dono del Patto", "Pact Boon"),
            ("Al 3° livello scegli la Catena, la Lama o il Tomo.", "At 3rd level you choose the Chain, the Blade or the Tome."),
            no_row=True, choices=(BOON_CHOICE,), covered_by="ChoiceSpec pact_boon di questa riga e le tre righe del Dono; test_pact_boon_is_chosen_at_level_3"),
    _boon_row("chain", "Patto della Catena / Pact of the Chain (Warlock 3, pag. 115)", ("Patto della Catena", "Pact of the Chain"),
              ("Trova famiglio come rituale, fuori dai conosciuti: forma normale, imp, pseudodrago, quasit o spiritello. Rinunci a un attacco e il famiglio attacca con la sua reazione.",
               "Find familiar as a ritual, outside your known spells: normal form, imp, pseudodragon, quasit or sprite. Give up an attack and the familiar attacks with its reaction."),
              "special", granted_spells=("find-familiar",), on_use=CHAIN_USE),
    _boon_row("blade", "Patto della Lama / Pact of the Blade (Warlock 3, pag. 115)", ("Patto della Lama", "Pact of the Blade"),
              ("Azione: crei un'arma da mischia del patto in mano, della forma che scegli. Sei competente e conta come magica; una nuova creazione sostituisce la precedente.",
               "Action: you create a pact melee weapon in your hand, in the form you choose. You are proficient and it counts as magical; a new one replaces the old."),
              "action", on_use=BLADE_USE,
              modifiers=(Modifier("magic_weapon", 1, when=inv._is_pact_weapon, source=f"feature:{CK}.pact_of_the_blade"),)),
    _boon_row("tome", "Patto del Tomo / Pact of the Tome (Warlock 3, pag. 116)", ("Patto del Tomo", "Pact of the Tome"),
              ("Il Libro delle Ombre: tre trucchetti da qualsiasi lista, a volontà e fuori dal numero di trucchetti conosciuti.",
               "The Book of Shadows: three cantrips from any list, at will and outside your known cantrips."),
              passive=True,
              choices=(ChoiceSpec(group="tome_cantrips", levels={3: 3}, options=_no_options, spell_pick="extra", spell_level=0),)),
    feature("ability_score_improvement", CK, ED, 4, "Aumento dei Punteggi di Caratteristica / Ability Score Improvement (Warlock 4, pag. 116)",
            ("Aumento dei Punteggi di Caratteristica", "Ability Score Improvement"),
            ("Ai livelli 4, 8, 12, 16 e 19: +2 a un punteggio o +1 a due, oppure un talento; massimo 20.",
             "At levels 4, 8, 12, 16 and 19: +2 to one score or +1 to two, or a feat; maximum 20."), no_row=True,
            covered_by="core/rules/level_choices.py (scelta asi); test_asi_choices_are_pending_at_levels_4_8_12_16_and_19"),
    *(_arcanum(grade, level, spell_level) for grade, level, spell_level in ARCANUM),
    feature("eldritch_master", CK, ED, 20, "Maestro dell'Occulto / Eldritch Master (Warlock 20, pag. 116)", ("Maestro dell'Occulto", "Eldritch Master"),
            ("Invocando il patrono per 1 minuto recuperi tutti gli slot di Patto spesi. Un uso, torna con un riposo lungo.",
             "Calling on your patron for 1 minute you regain all expended Pact slots. One use, back on a long rest."),
            "special", uses=Uses(table={20: 1}), restoration="long_rest", on_use=ELDRITCH_MASTER_USE),

    # Il Signore Fatato
    _expanded("archfey", "Lista Ampliata degli Incantesimi / Expanded Spell List (Signore Fatato 1, pag. 116)",
              ("Luminescenza, sonno; allucinazione di forza, calmare emozioni; crescita vegetale, intermittenza; dominare bestie, invisibilità superiore; dominare persone, sembrare. Solo opzioni.",
               "Faerie fire, sleep; phantasmal force, calm emotions; plant growth, blink; dominate beast, greater invisibility; dominate person, seeming. Only options.")),
    _patron("fey_presence", "archfey", 1, "Presenza Fatata / Fey Presence (Signore Fatato 1, pag. 116)", ("Presenza Fatata", "Fey Presence"),
            ("Azione: cubo di 3 m, TS Saggezza contro la tua CD: affascinate o spaventate (a scelta) fino alla fine del tuo prossimo turno. Riposo breve.",
             "Action: 10 ft cube, Wisdom save against your DC: charmed or frightened (your choice) until the end of your next turn. Short rest."),
            "action", uses=Uses(table={1: 1}), restoration="short_rest", on_use=FEY_PRESENCE_USE, dc_ability="charisma"),
    _patron("misty_escape", "archfey", 6, "Fuga Velata / Misty Escape (Signore Fatato 6, pag. 117)", ("Fuga Velata", "Misty Escape"),
            ("Reazione, quando subisci danni: invisibile e ti teletrasporti fino a 18 m; invisibile fino all'inizio del tuo turno o finché attacchi o lanci. Riposo breve.",
             "Reaction, when you take damage: invisible and you teleport up to 60 ft; invisible until the start of your turn or until you attack or cast. Short rest."),
            "reaction", uses=Uses(table={6: 1}), restoration="short_rest", on_use=MISTY_ESCAPE_USE),
    _patron("beguiling_defenses", "archfey", 10, "Difese Seducenti / Beguiling Defenses (Signore Fatato 10, pag. 117)",
            ("Difese Seducenti", "Beguiling Defenses"),
            ("Sei immune all'essere affascinato. Reazione: ritorci l'effetto, TS Saggezza contro la tua CD o la creatura è affascinata per 1 minuto o finché subisce danni.",
             "You are immune to being charmed. Reaction: turn it back, Wisdom save against your DC or the creature is charmed for 1 minute or until it takes damage."),
            "reaction", condition_immunities=("charmed",), on_use=BEGUILING_DEFENSES_USE, dc_ability="charisma"),
    _patron("dark_delirium", "archfey", 14, "Delirio Oscuro / Dark Delirium (Signore Fatato 14, pag. 117)", ("Delirio Oscuro", "Dark Delirium"),
            ("Azione: una creatura entro 18 m fa un TS Saggezza o è affascinata o spaventata per 1 minuto, in concentrazione; finisce se subisce danni. Riposo breve.",
             "Action: a creature within 60 ft makes a Wisdom save or is charmed or frightened for 1 minute, concentration; it ends if it takes damage. Short rest."),
            "action", uses=Uses(table={14: 1}), restoration="short_rest", on_use=DARK_DELIRIUM_USE, dc_ability="charisma"),

    # L'Immondo
    _expanded("fiend", "Lista Ampliata degli Incantesimi / Expanded Spell List (Immondo 1, pag. 117)",
              ("Comando, mani brucianti; cecità/sordità, raggio rovente; nube maleodorante, palla di fuoco; muro di fuoco, scudo di fuoco; colpo infuocato, santificare. Solo opzioni.",
               "Command, burning hands; blindness/deafness, scorching ray; stinking cloud, fireball; wall of fire, fire shield; flame strike, hallow. Only options.")),
    _patron("dark_ones_blessing", "fiend", 1, "Benedizione dell'Oscuro / Dark One's Blessing (Immondo 1, pag. 117)",
            ("Benedizione dell'Oscuro", "Dark One's Blessing"),
            ("Quando porti a 0 PF una creatura ostile ottieni PF temporanei pari a Carisma + livello da warlock (minimo 1); non si sommano.",
             "When you reduce a hostile creature to 0 hit points you gain temporary hit points equal to Charisma + warlock level (minimum 1); they do not stack."),
            roll_options=(BLESSING_ATTACK, BLESSING_SPELL), passive=True),
    _patron("dark_ones_own_luck", "fiend", 6, "Fortuna dell'Oscuro / Dark One's Own Luck (Immondo 6, pag. 117)",
            ("Fortuna dell'Oscuro", "Dark One's Own Luck"),
            ("Dopo aver visto una prova di caratteristica o un TS, aggiungi 1d10 al tiro. Un uso, riposo breve.",
             "After seeing an ability check or saving throw, add 1d10 to the roll. One use, short rest."),
            uses=Uses(table={6: 1}), restoration="short_rest", roll_options=(DARK_LUCK,)),
    _patron("fiendish_resilience", "fiend", 10, "Resilienza Immonda / Fiendish Resilience (Immondo 10, pag. 117)",
            ("Resilienza Immonda", "Fiendish Resilience"),
            ("A ogni riposo breve o lungo scegli un tipo di danno: ne hai la resistenza finché ne scegli un altro. Le armi magiche e d'argento ignorano la resistenza.",
             "At each short or long rest you choose a damage type: you resist it until you choose another. Magical and silvered weapons ignore the resistance."),
            "special", on_use=FIENDISH_RESILIENCE_USE,
            modifiers=tuple(Modifier(f"resistance:{t}", 1, when=_resilience_active(t), source=f"feature:{CK}.fiendish_resilience") for t in DAMAGE_TYPES)),
    _patron("hurl_through_hell", "fiend", 14, "Scagliare all'Inferno / Hurl Through Hell (Immondo 14, pag. 117)",
            ("Scagliare all'Inferno", "Hurl Through Hell"),
            ("Quando colpisci, il bersaglio scompare fino alla fine del tuo prossimo turno; se non è un immondo subisce 10d10 danni psichici. Un uso, riposo lungo.",
             "When you hit, the target vanishes until the end of your next turn; if it is not a fiend it takes 10d10 psychic damage. One use, long rest."),
            uses=Uses(table={14: 1}), restoration="long_rest", roll_options=(HURL_NONFIEND, HURL_FIEND)),

    # Il Grande Antico
    _expanded("great_old_one", "Lista Ampliata degli Incantesimi / Expanded Spell List (Grande Antico 1, pag. 118)",
              ("Risata incontenibile di Tasha, sussurri dissonanti; allucinazione di forza, individuazione dei pensieri; chiaroveggenza, inviare; dominare bestie, tentacoli di Evard; dominare persone, telecinesi.",
               "Tasha's hideous laughter, dissonant whispers; phantasmal force, detect thoughts; clairvoyance, sending; dominate beast, Evard's black tentacles; dominate person, telekinesis.")),
    _patron("awakened_mind", "great_old_one", 1, "Mente Risvegliata / Awakened Mind (Grande Antico 1, pag. 118)",
            ("Mente Risvegliata", "Awakened Mind"),
            ("Parli telepaticamente con una creatura che vedi entro 9 m; deve capire almeno una lingua.",
             "You speak telepathically with a creature you can see within 30 ft; it must understand at least one language."), passive=True),
    _patron("entropic_ward", "great_old_one", 6, "Interdizione Entropica / Entropic Ward (Grande Antico 6, pag. 118)",
            ("Interdizione Entropica", "Entropic Ward"),
            ("Reazione: svantaggio all'attacco di una creatura contro di te; se manca, hai vantaggio al tuo prossimo attacco contro di essa fino alla fine del tuo turno seguente. Riposo breve.",
             "Reaction: disadvantage on a creature's attack against you; if it misses, you have advantage on your next attack against it until the end of your next turn. Short rest."),
            "reaction", uses=Uses(table={6: 1}), restoration="short_rest", on_use=ENTROPIC_WARD_USE, roll_options=(ENTROPIC_ADVANTAGE,)),
    _patron("thought_shield", "great_old_one", 10, "Scudo del Pensiero / Thought Shield (Grande Antico 10, pag. 118)",
            ("Scudo del Pensiero", "Thought Shield"),
            ("Pensieri illeggibili; resistenza ai danni psichici; chi ti infligge danni psichici subisce lo stesso ammontare.",
             "Your thoughts cannot be read; resistance to psychic damage; whoever deals you psychic damage takes the same amount."),
            modifiers=(Modifier("resistance:psychic", 1, source=f"feature:{CK}.thought_shield"),), roll_options=(THOUGHT_REFLECTION,), passive=True),
    _patron("create_thrall", "great_old_one", 14, "Creare Servitore / Create Thrall (Grande Antico 14, pag. 118)",
            ("Creare Servitore", "Create Thrall"),
            ("Azione: tocchi un umanoide incapacitato, che resta affascinato finché non viene rimossa la maledizione o la condizione, o crei un altro servitore.",
             "Action: you touch an incapacitated humanoid, which stays charmed until remove curse is cast on it, the condition is removed, or you create another thrall."),
            "action", on_use=CREATE_THRALL_USE),

    *inv.INVOCATION_ROWS,

    feature("multiclassing", CK, ED, 1, "Multiclasse: Warlock / Multiclassing: Warlock (Manuale 2014, pag. 163)",
            ("Multiclasse: Warlock", "Multiclassing: Warlock"),
            ("Requisito Carisma 13. Ottieni armature leggere e armi semplici. Gli slot di Patto si usano per gli incantesimi delle altre classi e viceversa.",
             "Requires Charisma 13. You gain light armor and simple weapons. Pact slots are used for other classes' spells and vice versa."),
            no_row=True, covered_by="core/rules/proficiencies.py (as_multiclass), webapp/src/data/multiclassPrereqs.ts (D2) e api/routers/spells.py "
                                    "(_pick_slot, slot_id); test_multiclass_pact_and_regular_slots_are_separate_pools"),
)

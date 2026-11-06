"""Barbaro 2024 e i suoi quattro Cammini: Berserker, Cuore Selvaggio, Albero del Mondo, Zelota.

Valori dalla scheda ``docs/superpowers/rules/2024/classes/barbarian.md``; i testi sono nostri, mai quelli del manuale.
L'Ira 2024 dura fino alla fine del turno seguente e si prolunga (attacco, TS imposto, azione bonus): vedi ``turn_end_unextended``.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from core.data.damage_types import DAMAGE_TYPES
from core.game.item_bonuses import item_meta
from core.rules.catalog._common import (
    INCAPACITATING, attacks_made, feature, heavy_armor, once_used, skill_label, state_on,
)
from core.rules.catalog.y2014.barbarian import RETALIATION, _reckless_confirmed, rage_damage
from core.rules.states import begin_state
from core.rules.types import (
    ChoiceSpec, Cost, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, TargetEffect, UnarmoredAc, Uses, UseChoice,
    UseToggle, ZeroHpSave,
)
from core.rules.weapons import MASTERY_GROUP, MASTERY_OPTIONS, has_property, mastery_choice, weapon_key, weapon_mastery
from core.utils.session_view import armor_category

ED, CK = "2024", "barbarian"
RAGE = f"{CK}.rage"
RECKLESS = f"{CK}.reckless_attack"
BRUTAL = f"{CK}.brutal_strike"
PERSISTENT = f"{CK}.persistent_rage"
GODS = f"{CK}.rage_of_the_gods"
CLASS_SKILLS = ("animal_handling", "athletics", "intimidation", "nature", "perception", "survival")
PRIMAL_SKILLS = ("acrobatics", "intimidation", "perception", "stealth", "survival")
WILD_OPTIONS = ("bear", "eagle", "wolf")
POWER_OPTIONS = ("falcon", "lion", "ram")
EXTENDED = "extended"  # turn_state: il turno in corso ha prolungato l'Ira senza un attacco


def _m(ft: int) -> str:
    """Piedi in metri come nei testi italiani (1,5 m ogni 5 ft)."""
    return f"{ft * 3 / 10:g}".replace(".", ",") + " m"


def _both(it: str, en: str) -> dict[str, str]:
    return {"it": it, "en": en}


# ---------------------------------------------------------------------------
# Predicati e dati dello stato dell'Ira
# ---------------------------------------------------------------------------

def _rage(ctx: RuleContext) -> dict | None:
    return next((s for s in ctx.char.active_states or [] if s.get("key") == "rage"), None)


def _rage_opt(ctx: RuleContext, key: str) -> Any:
    return ((_rage(ctx) or {}).get("data") or {}).get(key)


def raging(ctx: RuleContext) -> bool:
    """In ira e senza armatura pesante (che la finirebbe: il predicato copre anche un'armatura messa da altre vie)."""
    return state_on(ctx, "rage") and not heavy_armor(ctx.char)


def _subclass(ctx: RuleContext, key: str) -> bool:
    return getattr(ctx.class_row, "subclass_key", None) == key


def _strength_attack(ctx: RuleContext) -> bool:
    """Tiro con Forza, di arma (anche lanciata) o Colpo Senz'Armi."""
    return ctx.ability == "strength" and ctx.spell is None


def _incapacitated(char: Any) -> bool:
    return any((char.conditions or {}).get(c) for c in INCAPACITATING)


def _reckless_declared(ctx: RuleContext) -> bool:
    return once_used(ctx.char, RECKLESS)


def _ability_row(ctx: RuleContext, key: str) -> Any:
    return next((a for a in ctx.char.abilities if a.feature_key == key and a.source_class_id == getattr(ctx.class_row, "id", None)), None)


def _set_rage_data(ctx: RuleContext, **fields: Any) -> None:
    ctx.char.active_states = [{**s, "data": {**(s.get("data") or {}), **fields}} if s.get("key") == "rage" else s
                              for s in ctx.char.active_states or []]


# ---------------------------------------------------------------------------
# Ira
# ---------------------------------------------------------------------------

def _rage_state(ctx: RuleContext, params: dict) -> StateSpec | None:
    """Lo stato dell'Ira alla sua attivazione; ``None`` se è già attiva (l'uso è un prolungamento)."""
    if state_on(ctx, "rage"):
        return None
    level = ctx.class_level
    others: list[str] = []  # privilegi che agiscono su altri: sono mostrati sotto lo stato (D1)
    data: dict[str, Any] = {"damage": rage_damage(level), "fresh": True}
    if _subclass(ctx, "wild_heart"):
        data["wild"] = params.get("wild")
        if data["wild"] == "wolf":
            others.append(f"{CK}.wilds_wolf")
        if level >= 14:
            data["power"] = params.get("power")
            if data["power"] == "lion":
                others.append(f"{CK}.power_lion")
    if _subclass(ctx, "world_tree") and level >= 14:
        data["far_used"] = False
    data["others"] = others
    # Ira Persistente (15): dura 10 minuti e finisce solo con la perdita dei sensi o un'armatura pesante
    ends = ("unconscious", "heavy_armor") if level >= 15 else ("unconscious", "incapacitated", "turn_end_unextended", "heavy_armor")
    return StateSpec(
        "rage", rounds=100, ends_on=ends, blocks_casting=True, end_slot="bonus",
        immune_conditions=("charmed", "frightened") if _subclass(ctx, "berserker") and level >= 6 else (), data=data)


def _rage_available(ctx: RuleContext) -> bool:
    if heavy_armor(ctx.char):
        return False
    return not state_on(ctx, "rage") or ctx.class_level < 15  # dal 15° non c'è nulla da prolungare


def _rage_slot(ctx: RuleContext, params: dict) -> str | None:
    """Entrare costa l'azione bonus; prolungare imponendo un TS a un nemico no."""
    return None if state_on(ctx, "rage") and params.get("extend_via") == "save" else "bonus"


def _rage_cost(ctx: RuleContext, _params: dict) -> int:
    return 0 if state_on(ctx, "rage") else 1  # prolungare non spende un uso


def _divine_ready(ctx: RuleContext) -> bool:
    row = _ability_row(ctx, GODS)
    return _subclass(ctx, "zealot") and ctx.class_level >= 14 and row is not None and (row.uses or 0) > 0


def _rage_check(ctx: RuleContext, params: dict) -> tuple[int, str] | None:
    if params.get("divine_form") and _subclass(ctx, "zealot") and ctx.class_level >= 14 and not state_on(ctx, "rage") \
            and not _divine_ready(ctx):
        return 409, "no_uses"
    return None


def _entry_temp_hp(ctx: RuleContext, _rolled: int) -> int:
    """Impeto Vitale: PF temporanei pari al livello da barbaro all'attivazione (il maggiore, i PF temporanei non si sommano)."""
    return ctx.class_level if _subclass(ctx, "world_tree") and not state_on(ctx, "rage") else 0


def _entry_clears(ctx: RuleContext, _params: dict) -> list[str]:
    """Ira Incontenibile: all'attivazione cadono Affascinato e Spaventato già presenti."""
    return ["charmed", "frightened"] if _subclass(ctx, "berserker") and ctx.class_level >= 6 and not state_on(ctx, "rage") else []


def _rage_effect(ctx: RuleContext, params: dict) -> None:
    state = _rage(ctx)
    if state is None:
        return
    if not (state.get("data") or {}).get("fresh"):  # prolungamento (azione bonus o TS imposto)
        ctx.char.turn_state = {**(ctx.char.turn_state or {}), EXTENDED: True}
        return
    if params.get("divine_form") and _divine_ready(ctx):
        _ability_row(ctx, GODS).uses -= 1
        begin_state(ctx.char, StateSpec("divine_form", rounds=10, ends_on=("unconscious", "manual")), GODS, "Ira degli Dei")


def _rage_message(ctx: RuleContext, params: dict) -> dict[str, str] | None:
    """Ciò che l'attivazione concede e l'app non può fare da sola: movimenti e azioni (D1)."""
    if not (_rage_opt(ctx, "fresh")):
        return None
    from core.rules.modifiers import effective_speed  # import locale: modifiers usa il catalogo
    it: list[str] = []
    en: list[str] = []
    if ctx.class_level >= 7:
        half = effective_speed(ctx.char, ctx.char.speed) // 2
        it.append(f"Balzo Istintivo: puoi muoverti fino a {_m(half)} (metà velocità) con questa azione bonus.")
        en.append(f"Instinctive Pounce: you can move up to {half} ft (half your Speed) as part of this bonus action.")
    if _rage_opt(ctx, "wild") == "eagle":
        it.append("Aquila: Disimpegno e Scatto fanno parte di questa azione bonus.")
        en.append("Eagle: Disengage and Dash are part of this bonus action.")
    if _subclass(ctx, "world_tree") and ctx.class_level >= 14:
        it.append(f"Viaggio lungo l'Albero: puoi teletrasportarti fino a {_m(60)} in uno spazio libero che vedi.")
        en.append("Travel along the Tree: you can teleport up to 60 ft to an unoccupied space you can see.")
    return _both(" ".join(it), " ".join(en)) if it else None


def _rage_modifiers() -> tuple[Modifier, ...]:
    src = f"feature:{RAGE}"
    return (
        Modifier("advantage", 1, source=src,
                 when=lambda c: raging(c) and c.ability == "strength" and c.roll in ("skill", "ability", "save")),
        Modifier("damage", lambda c: rage_damage(c.class_level), source=src,
                 when=lambda c: raging(c) and c.roll == "damage" and _strength_attack(c)),
        *(Modifier(f"resistance:{t}", 1, when=raging, source=src) for t in ("bludgeoning", "piercing", "slashing")),
    )


RAGE_USE = OnUse(
    slot="bonus", slot_by=_rage_slot, cost_by=_rage_cost, ends_concentration=True, state=_rage_state, available=_rage_available,
    check=_rage_check, temp_hp=_entry_temp_hp, clears=_entry_clears, effect=_rage_effect, message=_rage_message,
    toggles=(UseToggle("divine_form", _both("Forma divina (Ira degli Dei)", "Divine form (Rage of the Gods)"),
                       available=lambda c: _divine_ready(c) and not state_on(c, "rage")),),
    choices=(
        UseChoice("extend_via", _both("Prolunga l'Ira con", "Extend the Rage by"), options=lambda _c: ["bonus", "save"],
                  option_label=lambda k: {"bonus": _both("Azione bonus", "Bonus action"),
                                          "save": _both("TS imposto a un nemico", "Saving throw forced on an enemy")}[k],
                  optional=True, applies=lambda c: state_on(c, "rage") and c.class_level < 15),
        UseChoice("wild", _both("Ira della Natura Selvaggia", "Rage of the Wilds"), options=lambda _c: list(WILD_OPTIONS),
                  option_label=lambda k: _both(*{"bear": ("Orso", "Bear"), "eagle": ("Aquila", "Eagle"), "wolf": ("Lupo", "Wolf")}[k]),
                  applies=lambda c: _subclass(c, "wild_heart") and not state_on(c, "rage")),
        UseChoice("power", _both("Potere della Natura Selvaggia", "Power of the Wilds"), options=lambda _c: list(POWER_OPTIONS),
                  option_label=lambda k: _both(*{"falcon": ("Falco", "Falcon"), "lion": ("Leone", "Lion"), "ram": ("Ariete", "Ram")}[k]),
                  applies=lambda c: _subclass(c, "wild_heart") and c.class_level >= 14 and not state_on(c, "rage")),
    ),
)


# ---------------------------------------------------------------------------
# Opzioni al tiro
# ---------------------------------------------------------------------------

RECKLESS_ATTACK = RollOptionSpec(
    key=RECKLESS, phase="before", rolls=("attack",), mode="advantage", once_per_turn=True,
    label=_both("Attacco Irruento: vantaggio ai tiri con Forza, ma gli attacchi contro di te hanno vantaggio",
                "Reckless Attack: advantage on Strength attacks, but attacks against you have advantage"),
    available=lambda c: _strength_attack(c) and attacks_made(c) == 0,  # va deciso al primo tiro per colpire del turno
    on_confirm=_reckless_confirmed,
)


def _no_disadvantage(ctx: RuleContext) -> bool:
    """Il tiro scelto non deve avere svantaggio (le condizioni lo impongono da sole)."""
    from core.rules.modifiers import collect_modifiers  # import locale: modifiers usa il catalogo
    return not collect_modifiers(replace(ctx, roll="attack")).disadvantage


def _effects_allowed(ctx: RuleContext) -> int:
    return 2 if ctx.class_level >= 17 else 1  # Colpo Brutale Migliorato: due effetti diversi


# Rinunciare al vantaggio = un svantaggio che lo annulla (il modo diventa normale, qualunque fonte di vantaggio ci sia)
BRUTAL_STRIKE = RollOptionSpec(
    key=BRUTAL, phase="before", rolls=("attack",), mode="disadvantage", once_per_turn=True, needs=RECKLESS,
    extra_dice=lambda c, _i: "2d10" if c.class_level >= 17 else "1d10",
    label=_both("Colpo Brutale: rinunci al vantaggio, +1d10 danni (2d10 dal 17°) se colpisci e un effetto",
                "Brutal Strike: forgo advantage for +1d10 damage (2d10 from 17th) on a hit and an effect"),
    available=lambda c: _strength_attack(c) and _no_disadvantage(c),
)


def _half_speed(ctx: RuleContext) -> int:
    from core.rules.modifiers import effective_speed  # import locale
    return effective_speed(ctx.char, ctx.char.speed) // 2


def _forceful_effect(ctx: RuleContext, _inputs: dict) -> dict[str, str]:
    half = _half_speed(ctx)
    return _both(f"Colpo Poderoso: il bersaglio è spinto di {_m(15)} in linea retta; puoi poi muoverti fino a {_m(half)} verso "
                 "di lui senza provocare attacchi di opportunità.",
                 f"Forceful Blow: the target is pushed 15 ft straight away; you can then move up to {half} ft toward it "
                 "without provoking opportunity attacks.")


def _until_my_turn(slug: str):
    return lambda _c, _i: TargetEffect(condition=slug, ends_at={"anchor": "source", "edge": "start", "count": 1})


def _effect(key: str, it: str, en: str, **kw: Any) -> RollOptionSpec:
    return RollOptionSpec(
        key=f"{CK}.{key}", phase="after_hit", rolls=("attack",), needs=BRUTAL, group="brutal_effect", group_max=_effects_allowed,
        label=_both(it, en), available=lambda c: BRUTAL in c.confirmed, **kw)


FORCEFUL = _effect("forceful_blow", "Colpo Poderoso: spingi il bersaglio di 4,5 m e avanzi", "Forceful Blow: push the target 15 ft and follow",
                   effect=_forceful_effect)
HAMSTRING = _effect("hamstring_blow", "Colpo alle Gambe: velocità del bersaglio -4,5 m", "Hamstring Blow: target's Speed -15 ft",
                    effect=lambda _c, _i: _both("Colpo alle Gambe: velocità del bersaglio -4,5 m fino all'inizio del tuo prossimo turno; vale solo il più recente.",
                                                "Hamstring Blow: target's Speed -15 ft until the start of your next turn; only the latest applies."),
                    target_effect=_until_my_turn("custom:hamstring"))
STAGGERING = _effect("staggering_blow", "Colpo Stordente: svantaggio al prossimo TS, niente attacchi di opportunità",
                     "Staggering Blow: disadvantage on its next save, no opportunity attacks",
                     effect=lambda _c, _i: _both("Colpo Stordente: svantaggio al prossimo TS del bersaglio e niente attacchi di opportunità fino all'inizio del tuo prossimo turno.",
                                                 "Staggering Blow: disadvantage on the target's next saving throw and no opportunity attacks until the start of your next turn."),
                     target_effect=_until_my_turn("custom:staggered"))
SUNDERING = _effect("sundering_blow", "Colpo Spezzante: il prossimo tiro per colpire altrui contro il bersaglio ha +5",
                    "Sundering Blow: the next attack roll by another creature against the target gets +5",
                    effect=lambda _c, _i: _both("Colpo Spezzante: il primo tiro per colpire di un'altra creatura contro il bersaglio, prima del tuo prossimo turno, ha +5 (un solo bonus per tiro).",
                                                "Sundering Blow: the first attack roll by another creature against the target before your next turn gets +5 (one bonus per roll)."),
                    target_effect=_until_my_turn("custom:sundered"))


def _frenzy_dice(ctx: RuleContext, _inputs: dict) -> str:
    return f"{rage_damage(ctx.class_level)}d6"


FRENZY = RollOptionSpec(
    key=f"{CK}.frenzy", phase="after_hit", rolls=("attack",), once_per_turn=True, extra_dice=_frenzy_dice,
    label=_both("Frenesia: danni extra al primo bersaglio colpito del turno", "Frenzy: extra damage to the first target hit this turn"),
    available=lambda c: raging(c) and _strength_attack(c) and _reckless_declared(c),
)


def _divine_fury(kind: str, it: str, en: str) -> RollOptionSpec:
    return RollOptionSpec(
        key=f"{CK}.divine_fury_{kind}", phase="after_hit", rolls=("attack",), group="divine_fury", once_per_turn=True,
        extra_dice=lambda c, _i: f"1d6+{c.class_level // 2}", label=_both(it, en),
        available=lambda c: raging(c) and c.spell is None)


def _fanatical_used(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    _set_rage_data(ctx, fanatical_used=True)


FANATICAL_FOCUS = RollOptionSpec(
    key=f"{CK}.fanatical_focus", phase="after_roll", after="reroll", rolls=("save",), bonus=lambda c, _i: rage_damage(c.class_level),
    label=_both("Concentrazione Fanatica: ripeti il TS fallito con il bonus dell'Ira (vale il nuovo risultato)",
                "Fanatical Focus: reroll the failed save with the Rage bonus (the new result stands)"),
    available=lambda c: state_on(c, "rage") and not _rage_opt(c, "fanatical_used"), on_confirm=_fanatical_used)


def _restore_rage(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    row = _ability_row(ctx, RAGE)
    if row is not None and row.max_uses is not None:
        row.uses = row.max_uses


PERSISTENT_RECOVERY = RollOptionSpec(
    key=PERSISTENT, phase="before", rolls=("initiative",), cost=Cost(feature_key=PERSISTENT), on_confirm=_restore_rage,
    label=_both("Ira Persistente: tirando l'Iniziativa recuperi tutti gli usi dell'Ira",
                "Persistent Rage: rolling Initiative gives back every Rage use"),
    available=lambda c: any(a.feature_key == RAGE and a.max_uses is not None and (a.uses or 0) < a.max_uses for a in c.char.abilities))

PRIMAL_CHECK = RollOptionSpec(
    key=f"{CK}.primal_knowledge", phase="before", rolls=("skill",), ability_override="strength",
    label=_both("Conoscenza Primordiale: fai la prova come prova di Forza", "Primal Knowledge: make the check as a Strength check"),
    available=lambda c: raging(c) and c.skill in PRIMAL_SKILLS and c.ability != "strength")

RAM_PRONE = RollOptionSpec(
    key=f"{CK}.power_ram", phase="after_hit", rolls=("attack",),
    label=_both("Ariete: il bersaglio Grande o più piccolo cade Prono", "Ram: a Large or smaller target falls Prone"),
    available=lambda c: raging(c) and _rage_opt(c, "power") == "ram" and c.attack_mode == "melee" and c.spell is None,
    target_effect=lambda _c, _i: TargetEffect(condition="prone"))


def _knows_weapon(ctx: RuleContext) -> bool:
    key = weapon_key(ctx.item) if ctx.item is not None else None
    return bool(key) and any(key in (getattr(c, "options", None) or {}).get(MASTERY_GROUP, []) for c in ctx.char.classes)


def _versatile(item: Any) -> bool:
    meta = item_meta(item)
    listed = " ".join(str(p).lower() for p in meta.get("properties") or [])
    return "versatile" in listed or "versatil" in listed or bool(meta.get("versatile_dice"))


def _reach_weapon(ctx: RuleContext) -> bool:
    return (ctx.item is not None and item_meta(ctx.item).get("weapon_type", "melee") != "ranged"
            and (has_property(ctx.item, "heavy") or _versatile(ctx.item)))


def _roots(prop: str) -> RollOptionSpec:
    base = next(o for o in MASTERY_OPTIONS if o.key == f"mastery_{prop}")
    return replace(base, key=f"{CK}.battering_roots_{prop}", group="battering_roots",
                   label=_both(f"Radici Percuotenti: aggiungi {prop.capitalize()} alla padronanza dell'arma",
                               f"Battering Roots: add {prop.capitalize()} to the weapon's mastery"),
                   available=lambda c: (c.edition == "2024" and c.attack_mode == "melee" and _reach_weapon(c) and _knows_weapon(c)
                                        and weapon_mastery(c.item) != prop))


# ---------------------------------------------------------------------------
# Scelte
# ---------------------------------------------------------------------------

def _primal_options(ctx: RuleContext) -> list[str]:
    skills = ctx.char.skills or {}
    return [s for s in CLASS_SKILLS if not skills.get(s)]


def _primal_owned(ctx: RuleContext) -> list[str]:
    skills = ctx.char.skills or {}
    return [s for s in CLASS_SKILLS if skills.get(s)]


ASPECT_NAMES = {"owl": "Owl", "panther": "Panther", "salmon": "Salmon"}


def _aspect_choice() -> ChoiceSpec:
    # `label` serve solo all'import da Beyond, che chiama l'opzione col nome nudo
    return ChoiceSpec(group="aspect_of_the_wilds", levels={6: 1}, options=lambda _c: list(ASPECT_NAMES), replaceable=True,
                      label=lambda key: {"name": ASPECT_NAMES[key], "summary": ""})


def _owl_range(ctx: RuleContext) -> int:
    """Scurovisione 60 piedi; se già posseduta, la portata cresce di 60."""
    have = max((int(s.get("range_ft") or 0) for s in (ctx.char.settings or {}).get("senses") or []
                if isinstance(s, dict) and s.get("type") == "darkvision"), default=0)
    return 60 + have


def _wild(key: str, level: int, title: str, name: tuple[str, str], summary: tuple[str, str], action_type: str | None = None, **kw: Any):
    return feature(f"wilds_{key}", CK, ED, level, title, name, summary, action_type, subclass="wild_heart", **kw)


def _intimidation(ctx: RuleContext, _params: dict) -> TargetEffect:
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    return TargetEffect(condition="frightened", save_ability="wisdom",
                        save_dc=8 + ctx.char.proficiency_bonus + effective_ability_mod(ctx.char, "strength"),
                        rounds=10, repeat_save="end")


def _branches(ctx: RuleContext, _params: dict) -> TargetEffect:
    from core.game.stats import effective_ability_mod  # import locale
    return TargetEffect(save_ability="strength", save_dc=8 + ctx.char.proficiency_bonus + effective_ability_mod(ctx.char, "strength"),
                        note="branches_of_the_tree")


def _travel_check(ctx: RuleContext, params: dict) -> tuple[int, str] | None:
    return (409, "already_used_this_rage") if params.get("far") and _rage_opt(ctx, "far_used") else None


def _travel_effect(ctx: RuleContext, params: dict) -> None:
    if params.get("far"):
        _set_rage_data(ctx, far_used=True)


def _travel_message(ctx: RuleContext, params: dict) -> dict[str, str]:
    if params.get("far"):
        return _both(f"Teletrasporto fino a {_m(150)} (una volta per Ira), con fino a sei creature consenzienti entro {_m(10)}, "
                     f"ciascuna in uno spazio libero entro {_m(10)} dalla destinazione.",
                     "Teleport up to 150 ft (once per Rage), bringing up to six willing creatures within 10 ft, each to an "
                     "unoccupied space within 10 ft of the destination.")
    # `effect` non è ancora girato: lo stato dice se la versione da 150 piedi è già stata usata
    if _rage_opt(ctx, "far_used"):
        return _both(f"Teletrasporto fino a {_m(60)} in uno spazio libero che vedi.", "Teleport up to 60 ft to an unoccupied space you can see.")
    return _both(f"Teletrasporto fino a {_m(60)} in uno spazio libero che vedi; una volta per Ira puoi arrivare a {_m(150)} "
                 "portando fino a sei creature consenzienti.",
                 "Teleport up to 60 ft to an unoccupied space you can see; once per Rage you can go up to 150 ft, bringing up to "
                 "six willing creatures.")


def _zealous_state(_ctx: RuleContext, _params: dict) -> StateSpec:
    return StateSpec("zealous_presence", rounds=1, ends_on=("new_turn", "manual"), data={"others": [f"{CK}.zealous_presence"]})


def _in_form(ctx: RuleContext) -> bool:
    return state_on(ctx, "divine_form")


def _depleted(key: str):
    """Il privilegio ha finito i suoi usi: solo allora ha senso «ripristinarlo» spendendo un uso di Ira."""
    def check(ctx: RuleContext) -> bool:
        row = _ability_row(ctx, key)
        return row is not None and (row.uses or 0) == 0
    return check


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

_IT_NO_ROW = "core/rules/proficiencies.py"

FEATURES = (
    feature("core_traits", CK, ED, 1, "Tratti Fondamentali del Barbaro / Core Barbarian Traits (Barbaro 1, pag. 51)",
            ("Tratti Fondamentali del Barbaro", "Core Barbarian Traits"),
            ("d12 come dado vita, TS Forza e Costituzione, 2 abilità, armi semplici e da guerra, armature leggere e medie, scudi.",
             "d12 hit die, Strength and Constitution saves, 2 skills, simple and martial weapons, light and medium armor, shields."),
            no_row=True, covered_by=f"{_IT_NO_ROW} (class_proficiencies, as_multiclass), api/routers/classes.py create_class_for_character e "
                                    "total_base_hp; l'equipaggiamento di partenza è in lavori-successivi (2024-barbarian)"),
    feature("rage", CK, ED, 1, "Ira / Rage (Barbaro 1, pag. 51)", ("Ira", "Rage"),
            ("Azione bonus: resistenza fisica, danni extra e vantaggio con Forza; niente incantesimi. Dura fino alla fine del turno "
             "seguente: attacco, TS imposto o azione bonus la prolungano.",
             "Bonus action: physical resistance, extra damage and advantage with Strength; no spells. Lasts to the end of your next "
             "turn: an attack, a forced save or a bonus action extends it."),
            "bonus_action", uses=Uses(table={1: 2, 3: 3, 6: 4, 12: 5, 17: 6}), restoration="long_rest", short_rest_recovers=1,
            modifiers=_rage_modifiers(), on_use=RAGE_USE),
    feature("unarmored_defense", CK, ED, 1, "Difesa Senza Armatura / Unarmored Defense (Barbaro 1, pag. 51)",
            ("Difesa Senza Armatura", "Unarmored Defense"),
            ("Senza armatura CA = 10 + Destrezza + Costituzione; lo scudo è compatibile.",
             "Without armor AC = 10 + Dexterity + Constitution; a shield is allowed."),
            unarmored=UnarmoredAc(("dexterity", "constitution"))),
    feature("weapon_mastery", CK, ED, 1, "Padronanza delle Armi / Weapon Mastery (Barbaro 1, pag. 52)",
            ("Padronanza delle Armi", "Weapon Mastery"),
            ("Usi le proprietà di padronanza di 2 tipi di arma da mischia (3 dal 4°, 4 dal 10°); dopo un riposo lungo ne cambi uno.",
             "You use the mastery properties of 2 kinds of melee weapon (3 from 4th, 4 from 10th); change one after a long rest."),
            choices=(mastery_choice({1: 2, 4: 3, 10: 4}, melee_only=True),), roll_options=MASTERY_OPTIONS),
    feature("danger_sense", CK, ED, 2, "Percezione del Pericolo / Danger Sense (Barbaro 2, pag. 52)",
            ("Percezione del Pericolo", "Danger Sense"),
            ("Vantaggio ai TS su Destrezza, a meno che tu sia incapacitato.", "Advantage on Dexterity saves unless you are incapacitated."),
            modifiers=(Modifier("advantage", 1, source=f"feature:{CK}.danger_sense",
                                when=lambda c: c.roll == "save" and c.ability == "dexterity" and not _incapacitated(c.char)),)),
    feature("reckless_attack", CK, ED, 2, "Attacco Irruento / Reckless Attack (Barbaro 2, pag. 52)",
            ("Attacco Irruento", "Reckless Attack"),
            ("Al primo tiro per colpire del turno: vantaggio ai tiri con Forza fino al tuo turno seguente, ma chi ti attacca ha vantaggio.",
             "On your first attack roll of the turn: advantage on Strength attacks until your next turn, but attacks against you have advantage."),
            roll_options=(RECKLESS_ATTACK,),
            modifiers=(Modifier("advantage", 1, source=f"feature:{RECKLESS}",
                                when=lambda c: c.roll == "attack" and _strength_attack(c) and _reckless_declared(c)),)),
    feature("subclass", CK, ED, 3, "Sottoclasse del Barbaro / Barbarian Subclass (Barbaro 3, pag. 52)",
            ("Sottoclasse del Barbaro", "Barbarian Subclass"),
            ("Al 3° livello si sceglie il Cammino del Berserker, del Cuore Selvaggio, dell'Albero del Mondo o dello Zelota.",
             "At level 3 you choose the Path of the Berserker, Wild Heart, World Tree or Zealot."),
            no_row=True, covered_by="core/rules/subclasses.py (match_subclass) e il campo sottoclasse della classe"),
    feature("primal_knowledge", CK, ED, 3, "Conoscenza Primordiale / Primal Knowledge (Barbaro 3, pag. 52)",
            ("Conoscenza Primordiale", "Primal Knowledge"),
            ("Una competenza in più tra le abilità del barbaro; con l'Ira, Acrobazia, Intimidire, Percezione, Furtività e Sopravvivenza si possono tirare con Forza.",
             "One more skill from the barbarian list; while raging, Acrobatics, Intimidation, Perception, Stealth and Survival can be rolled with Strength."),
            choices=(ChoiceSpec(group="primal_knowledge", levels={3: 1}, options=_primal_options, label=skill_label,
                                grants="proficient", owned=_primal_owned),),
            roll_options=(PRIMAL_CHECK,)),
    feature("ability_score_improvement", CK, ED, 4, "Aumento dei Punteggi di Caratteristica / Ability Score Improvement (Barbaro 4, 8, 12, 16, pag. 53)",
            ("Aumento dei Punteggi di Caratteristica", "Ability Score Improvement"),
            ("Ai livelli 4, 8, 12 e 16: il talento Aumento dei Punteggi o un altro talento di cui hai i requisiti.",
             "At levels 4, 8, 12 and 16: the Ability Score Improvement feat or another feat you qualify for."),
            no_row=True, covered_by="core/rules/level_choices.py (scelta asi); test_asi_at_4_8_12_16_and_the_19th_is_an_epic_boon_not_an_asi"),
    feature("extra_attack", CK, ED, 5, "Attacco Extra / Extra Attack (Barbaro 5, pag. 53)", ("Attacco Extra", "Extra Attack"),
            ("Due attacchi con l'azione Attacco; non si somma ad altri Attacco Extra.",
             "Two attacks with the Attack action; does not stack with other Extra Attack."), attacks_per_action=2),
    feature("fast_movement", CK, ED, 5, "Movimento Veloce / Fast Movement (Barbaro 5, pag. 53)", ("Movimento Veloce", "Fast Movement"),
            ("Velocità +3 m (+10 ft), non con armatura pesante.", "Speed +10 ft, not in heavy armor."),
            modifiers=(Modifier("speed", 10, when=lambda c: not heavy_armor(c.char), source=f"feature:{CK}.fast_movement"),)),
    feature("feral_instinct", CK, ED, 7, "Istinto Ferino / Feral Instinct (Barbaro 7, pag. 53)", ("Istinto Ferino", "Feral Instinct"),
            ("Vantaggio ai tiri di Iniziativa.", "Advantage on Initiative rolls."),
            modifiers=(Modifier("advantage", 1, when=lambda c: c.roll == "initiative", source=f"feature:{CK}.feral_instinct"),)),
    feature("instinctive_pounce", CK, ED, 7, "Balzo Istintivo / Instinctive Pounce (Barbaro 7, pag. 53)", ("Balzo Istintivo", "Instinctive Pounce"),
            ("Entrando in Ira ti muovi fino a metà velocità come parte dell'azione bonus; l'esito dell'Ira ti dice la distanza.",
             "When you enter the Rage you move up to half your Speed as part of the bonus action; the Rage result tells the distance.")),
    feature("brutal_strike", CK, ED, 9, "Colpo Brutale / Brutal Strike (Barbaro 9, pag. 53)", ("Colpo Brutale", "Brutal Strike"),
            ("Con l'Attacco Irruento, rinunci al vantaggio su un tiro con Forza: se colpisce +1d10 danni (2d10 dal 17°) e un effetto.",
             "With Reckless Attack, forgo advantage on one Strength attack: on a hit +1d10 damage (2d10 from 17th) and an effect."),
            roll_options=(BRUTAL_STRIKE,)),
    feature("forceful_blow", CK, ED, 9, "Colpo Poderoso / Forceful Blow (Colpo Brutale, Barbaro 9, pag. 53)",
            ("Colpo Poderoso", "Forceful Blow"),
            ("Effetto del Colpo Brutale: bersaglio spinto di 4,5 m, poi ti muovi fino a metà velocità verso di lui senza attacchi di opportunità.",
             "Brutal Strike effect: target pushed 15 ft, then you move up to half your Speed toward it without opportunity attacks."),
            roll_options=(FORCEFUL,)),
    feature("hamstring_blow", CK, ED, 9, "Colpo alle Gambe / Hamstring Blow (Colpo Brutale, Barbaro 9, pag. 53)",
            ("Colpo alle Gambe", "Hamstring Blow"),
            ("Effetto del Colpo Brutale: velocità del bersaglio -4,5 m fino al tuo turno seguente; vale solo il più recente.",
             "Brutal Strike effect: target's Speed -15 ft until your next turn; only the latest applies."),
            roll_options=(HAMSTRING,)),
    feature("relentless_rage", CK, ED, 11, "Ira Implacabile / Relentless Rage (Barbaro 11, pag. 53)", ("Ira Implacabile", "Relentless Rage"),
            ("A 0 PF in Ira (senza morte istantanea): TS Costituzione CD 10, +5 a ogni uso fino a un riposo; se riesce, PF pari a due volte il livello.",
             "At 0 HP while raging (not killed outright): Constitution save DC 10, +5 each use until a rest; on success, HP equal to twice your level."),
            zero_hp_save=ZeroHpSave(state="rage", hp=lambda c: 2 * c.class_level)),
    feature("improved_brutal_strike", CK, ED, 13, "Colpo Brutale Migliorato / Improved Brutal Strike (Barbaro 13 e 17, pag. 53)",
            ("Colpo Brutale Migliorato", "Improved Brutal Strike"),
            ("Dal 13° si aggiungono Colpo Stordente e Colpo Spezzante; dal 17° 2d10 di danno e due effetti diversi per colpo.",
             "From 13th Staggering and Sundering Blow join the options; from 17th 2d10 damage and two different effects per hit.")),
    feature("staggering_blow", CK, ED, 13, "Colpo Stordente / Staggering Blow (Colpo Brutale, Barbaro 13, pag. 53)",
            ("Colpo Stordente", "Staggering Blow"),
            ("Effetto del Colpo Brutale: svantaggio al prossimo TS del bersaglio e niente attacchi di opportunità fino al tuo turno seguente.",
             "Brutal Strike effect: disadvantage on the target's next save and no opportunity attacks until your next turn."),
            roll_options=(STAGGERING,)),
    feature("sundering_blow", CK, ED, 13, "Colpo Spezzante / Sundering Blow (Colpo Brutale, Barbaro 13, pag. 53)",
            ("Colpo Spezzante", "Sundering Blow"),
            ("Effetto del Colpo Brutale: il prossimo tiro per colpire di un'altra creatura contro il bersaglio ha +5, prima del tuo turno seguente.",
             "Brutal Strike effect: the next attack roll by another creature against the target gets +5 before your next turn."),
            roll_options=(SUNDERING,)),
    feature("persistent_rage", CK, ED, 15, "Ira Persistente / Persistent Rage (Barbaro 15, pag. 53)", ("Ira Persistente", "Persistent Rage"),
            ("Tirando l'Iniziativa recuperi tutti gli usi dell'Ira (una volta per riposo lungo); l'Ira dura 10 minuti senza prolungarla.",
             "Rolling Initiative gives back all Rage uses (once per long rest); the Rage lasts 10 minutes with no need to extend it."),
            uses=Uses(table={15: 1}), restoration="long_rest", roll_options=(PERSISTENT_RECOVERY,)),
    feature("indomitable_might", CK, ED, 18, "Potenza Indomabile / Indomitable Might (Barbaro 18, pag. 53)", ("Potenza Indomabile", "Indomitable Might"),
            ("Nelle prove e nei TS di Forza il totale minimo è il tuo punteggio di Forza.",
             "On Strength checks and saves your total is at least your Strength score."),
            modifiers=(Modifier("min_total", lambda c: _strength_score(c), source=f"feature:{CK}.indomitable_might",
                                when=lambda c: c.roll in ("skill", "ability", "save") and c.ability == "strength"),)),
    feature("epic_boon", CK, ED, 19, "Dono Epico / Epic Boon (Barbaro 19, pag. 53)", ("Dono Epico", "Epic Boon"),
            ("Al 19° livello un talento Dono Epico o un altro talento di cui hai i requisiti; consigliato Dono dell'Offesa Irresistibile.",
             "At 19th level an Epic Boon feat or another feat you qualify for; Boon of Irresistible Offense is recommended."),
            no_row=True, covered_by="core/rules/level_choices.py (scelta epic_boon); test_asi_at_4_8_12_16_and_the_19th_is_an_epic_boon_not_an_asi"),
    feature("primal_champion", CK, ED, 20, "Campione Primordiale / Primal Champion (Barbaro 20, pag. 53)", ("Campione Primordiale", "Primal Champion"),
            ("Forza e Costituzione +4, massimo 25.", "Strength and Constitution +4, maximum 25."),
            ability_bonus={"strength": 4, "constitution": 4}, ability_cap=25),

    # Cammino del Berserker
    feature("frenzy", CK, ED, 3, "Frenesia / Frenzy (Cammino del Berserker 3, pag. 54)", ("Frenesia", "Frenzy"),
            ("Con Ira e Attacco Irruento, il primo bersaglio colpito nel turno con Forza subisce tanti d6 extra quanto il bonus danni dell'Ira.",
             "With Rage and Reckless Attack, the first target hit each turn with Strength takes extra d6s equal to your Rage damage bonus."),
            subclass="berserker", roll_options=(FRENZY,)),
    feature("mindless_rage", CK, ED, 6, "Ira Incontenibile / Mindless Rage (Cammino del Berserker 6, pag. 54)",
            ("Ira Incontenibile", "Mindless Rage"),
            ("In Ira sei immune ad Affascinato e Spaventato; se lo eri entrando in Ira, la condizione termina.",
             "While raging you are immune to Charmed and Frightened; if you were either when entering the Rage, it ends."),
            subclass="berserker"),
    feature("retaliation", CK, ED, 10, "Ritorsione / Retaliation (Cammino del Berserker 10, pag. 54)", ("Ritorsione", "Retaliation"),
            ("Reazione: dopo il danno di una creatura entro 1,5 m, la attacchi in mischia con un'arma o un Colpo Senz'Armi. Non serve l'Ira.",
             "Reaction: after a creature within 5 ft damages you, you make a melee attack against it. No Rage needed."),
            subclass="berserker", roll_options=(RETALIATION,)),
    feature("intimidating_presence", CK, ED, 14, "Presenza Intimidatoria / Intimidating Presence (Cammino del Berserker 14, pag. 54)",
            ("Presenza Intimidatoria", "Intimidating Presence"),
            ("Azione bonus: chi scegli entro 9 m fa un TS Saggezza (CD 8 + Forza + competenza) o è Spaventato 1 minuto. Si ripristina spendendo un uso di Ira.",
             "Bonus action: creatures you choose within 30 ft make a Wisdom save (DC 8 + Strength + proficiency) or are Frightened for 1 minute. Restore it by spending a Rage use."),
            "bonus_action", subclass="berserker", uses=Uses(table={14: 1}), restoration="long_rest",
            on_use=OnUse(slot="bonus", target_effect=_intimidation, alt_spends=RAGE, alt_param="restore", toggles=(
                UseToggle("restore", _both("Ripristina spendendo un uso di Ira", "Restore by spending a Rage use"),
                          available=_depleted(f"{CK}.intimidating_presence")),))),

    # Cammino del Cuore Selvaggio
    feature("animal_speaker", CK, ED, 3, "Parlante con gli Animali / Animal Speaker (Cammino del Cuore Selvaggio 3, pag. 55)",
            ("Parlante con gli Animali", "Animal Speaker"),
            ("Percepire Bestie e Parlare con gli Animali, solo come rituali, con Saggezza come caratteristica da incantatore.",
             "Beast Sense and Speak with Animals, as rituals only, with Wisdom as spellcasting ability."),
            subclass="wild_heart", granted_spells=("beast-sense", "speak-with-animals"), granted_ritual_only=True),
    feature("rage_of_the_wilds", CK, ED, 3, "Ira della Natura Selvaggia / Rage of the Wilds (Cammino del Cuore Selvaggio 3, pag. 55)",
            ("Ira della Natura Selvaggia", "Rage of the Wilds"),
            ("A ogni attivazione dell'Ira scegli Orso, Aquila o Lupo.", "Each time you activate your Rage you choose Bear, Eagle or Wolf."),
            subclass="wild_heart"),
    _wild("bear", 3, "Orso / Bear (Ira della Natura Selvaggia, Cammino del Cuore Selvaggio 3, pag. 55)", ("Orso", "Bear"),
          ("In Ira resistenza a ogni danno tranne Forza, Necrotico, Psichico e Radioso (assorbe quella dell'Ira).",
           "While raging, resistance to every damage type except Force, Necrotic, Psychic and Radiant."),
          modifiers=tuple(Modifier(f"resistance:{t}", 1, source=f"feature:{CK}.wilds_bear",
                                   when=lambda c: raging(c) and _rage_opt(c, "wild") == "bear")
                          for t in DAMAGE_TYPES if t not in ("force", "necrotic", "psychic", "radiant"))),
    _wild("eagle", 3, "Aquila / Eagle (Ira della Natura Selvaggia, Cammino del Cuore Selvaggio 3, pag. 55)", ("Aquila", "Eagle"),
          ("Entrando in Ira, Disimpegno e Scatto fanno parte dell'azione bonus; in Ira, un'azione bonus per fare entrambe.",
           "When you enter the Rage, Disengage and Dash are part of that bonus action; while raging, a bonus action does both."),
          "bonus_action", on_use=OnUse(
              slot="bonus", available=lambda c: state_on(c, "rage") and _rage_opt(c, "wild") == "eagle",
              message=lambda _c, _p: _both("Disimpegno e Scatto con questa azione bonus.", "Disengage and Dash with this bonus action."))),
    _wild("wolf", 3, "Lupo / Wolf (Ira della Natura Selvaggia, Cammino del Cuore Selvaggio 3, pag. 55)", ("Lupo", "Wolf"),
          ("In Ira, i tuoi alleati hanno vantaggio ai tiri per colpire contro i nemici entro 1,5 m da te.",
           "While raging, your allies have advantage on attack rolls against your enemies within 5 ft of you.")),
    feature("aspect_of_the_wilds", CK, ED, 6, "Aspetto della Natura Selvaggia / Aspect of the Wilds (Cammino del Cuore Selvaggio 6, pag. 55)",
            ("Aspetto della Natura Selvaggia", "Aspect of the Wilds"),
            ("Scegli Gufo, Pantera o Salmone; dopo un riposo lungo puoi cambiare.", "Choose Owl, Panther or Salmon; change it after a long rest."),
            subclass="wild_heart", choices=(_aspect_choice(),), no_row=True,
            covered_by="ChoiceSpec aspect_of_the_wilds di questa riga; test_aspect_of_the_wilds_is_chosen_at_6_and_each_option_gives_its_benefit"),
    feature("aspect_owl", CK, ED, 6, "Gufo / Owl (Aspetto della Natura Selvaggia, Cammino del Cuore Selvaggio 6, pag. 55)",
            ("Gufo (Aspetto della Natura Selvaggia)", "Owl (Aspect of the Wilds)"),
            ("Scurovisione 18 m (60 ft); se ce l'hai già, la portata cresce di 18 m (60 ft).",
             "Darkvision 60 ft; if you already have it, its range grows by 60 ft."),
            subclass="wild_heart", option_group="aspect_of_the_wilds", option_key="owl",
            modifiers=(Modifier("sense:darkvision", _owl_range, source=f"feature:{CK}.aspect_owl"),)),
    feature("aspect_panther", CK, ED, 6, "Pantera / Panther (Aspetto della Natura Selvaggia, Cammino del Cuore Selvaggio 6, pag. 55)",
            ("Pantera (Aspetto della Natura Selvaggia)", "Panther (Aspect of the Wilds)"),
            ("Velocità di scalare pari alla velocità.", "Climb Speed equal to your Speed."),
            subclass="wild_heart", option_group="aspect_of_the_wilds", option_key="panther",
            modifiers=(Modifier("climb_speed", 1, source=f"feature:{CK}.aspect_panther"),)),
    feature("aspect_salmon", CK, ED, 6, "Salmone / Salmon (Aspetto della Natura Selvaggia, Cammino del Cuore Selvaggio 6, pag. 55)",
            ("Salmone (Aspetto della Natura Selvaggia)", "Salmon (Aspect of the Wilds)"),
            ("Velocità di nuotare pari alla velocità.", "Swim Speed equal to your Speed."),
            subclass="wild_heart", option_group="aspect_of_the_wilds", option_key="salmon",
            modifiers=(Modifier("swim_speed", 1, source=f"feature:{CK}.aspect_salmon"),)),
    feature("nature_speaker", CK, ED, 10, "Parlante con la Natura / Nature Speaker (Cammino del Cuore Selvaggio 10, pag. 55)",
            ("Parlante con la Natura", "Nature Speaker"),
            ("Comunione con la Natura, solo come rituale, con Saggezza come caratteristica da incantatore.",
             "Commune with Nature, as a ritual only, with Wisdom as spellcasting ability."),
            subclass="wild_heart", granted_spells=("commune-with-nature",), granted_ritual_only=True),
    feature("power_of_the_wilds", CK, ED, 14, "Potere della Natura Selvaggia / Power of the Wilds (Cammino del Cuore Selvaggio 14, pag. 55)",
            ("Potere della Natura Selvaggia", "Power of the Wilds"),
            ("A ogni attivazione dell'Ira scegli Falco, Leone o Ariete.", "Each time you activate your Rage you choose Falcon, Lion or Ram."),
            subclass="wild_heart"),
    feature("power_falcon", CK, ED, 14, "Falco / Falcon (Potere della Natura Selvaggia, Cammino del Cuore Selvaggio 14, pag. 55)",
            ("Falco", "Falcon"),
            ("In Ira e senza alcuna armatura, velocità di volare pari alla velocità.", "While raging and wearing no armor, Fly Speed equal to your Speed."),
            subclass="wild_heart",
            modifiers=(Modifier("fly_speed", 1, source=f"feature:{CK}.power_falcon",
                                when=lambda c: raging(c) and _rage_opt(c, "power") == "falcon" and armor_category(c.char) == "unarmored"),)),
    feature("power_lion", CK, ED, 14, "Leone / Lion (Potere della Natura Selvaggia, Cammino del Cuore Selvaggio 14, pag. 55)",
            ("Leone", "Lion"),
            ("In Ira, i nemici entro 1,5 m hanno svantaggio ai tiri per colpire contro chi non sia tu o un altro barbaro con Leone.",
             "While raging, enemies within 5 ft have disadvantage on attack rolls against anyone but you or another Barbarian with Lion."),
            subclass="wild_heart"),
    feature("power_ram", CK, ED, 14, "Ariete / Ram (Potere della Natura Selvaggia, Cammino del Cuore Selvaggio 14, pag. 55)",
            ("Ariete", "Ram"),
            ("In Ira, un colpo in mischia può far cadere Prono un bersaglio Grande o più piccolo.",
             "While raging, a melee hit can knock a Large or smaller target Prone."),
            subclass="wild_heart", roll_options=(RAM_PRONE,)),

    # Cammino dell'Albero del Mondo
    feature("vitality_of_the_tree", CK, ED, 3, "Vitalità dell'Albero / Vitality of the Tree (Cammino dell'Albero del Mondo 3, pag. 56)",
            ("Vitalità dell'Albero", "Vitality of the Tree"),
            ("L'Ira ti dà due benefici: Impeto Vitale e Forza Vivificante.", "Your Rage gives two benefits: Vitality Surge and Life-Giving Force."),
            subclass="world_tree"),
    feature("vitality_surge", CK, ED, 3, "Impeto Vitale / Vitality Surge (Vitalità dell'Albero, Cammino dell'Albero del Mondo 3, pag. 56)",
            ("Impeto Vitale", "Vitality Surge"),
            ("Attivando l'Ira ottieni PF temporanei pari al livello da barbaro (il maggiore fra quelli che hai e questi).",
             "When you activate your Rage you gain temporary HP equal to your Barbarian level (the greater of the two)."),
            subclass="world_tree"),
    feature("life_giving_force", CK, ED, 3, "Forza Vivificante / Life-Giving Force (Vitalità dell'Albero, Cammino dell'Albero del Mondo 3, pag. 56)",
            ("Forza Vivificante", "Life-Giving Force"),
            ("A inizio turno in Ira, un'altra creatura entro 3 m ottiene PF temporanei: d6 pari al bonus danni dell'Ira. Svaniscono con l'Ira.",
             "At the start of your turn while raging, another creature within 10 ft gains temporary HP: d6s equal to your Rage damage bonus. They vanish when the Rage ends."),
            "special", subclass="world_tree",
            on_use=OnUse(rolls=lambda c: f"{rage_damage(c.class_level)}d6", gives=lambda _c, rolled: rolled, once_per_turn=True,
                         available=lambda c: state_on(c, "rage"))),
    feature("branches_of_the_tree", CK, ED, 6, "Rami dell'Albero / Branches of the Tree (Cammino dell'Albero del Mondo 6, pag. 56)",
            ("Rami dell'Albero", "Branches of the Tree"),
            ("Reazione in Ira: una creatura che vedi entro 9 m a inizio turno fa un TS Forza (CD 8 + Forza + competenza) o si teletrasporta vicino a te.",
             "Reaction while raging: a creature you see within 30 ft starting its turn makes a Strength save (DC 8 + Strength + proficiency) or teleports next to you."),
            "reaction", subclass="world_tree",
            on_use=OnUse(slot="reaction", target_effect=_branches, available=lambda c: state_on(c, "rage"))),
    feature("battering_roots", CK, ED, 10, "Radici Percuotenti / Battering Roots (Cammino dell'Albero del Mondo 10, pag. 56)",
            ("Radici Percuotenti", "Battering Roots"),
            ("Nel tuo turno, portata +3 m con armi da mischia Pesanti o Versatili; colpendo puoi attivare Spingere o Atterrare oltre a un'altra padronanza.",
             "On your turn, reach +10 ft with Heavy or Versatile melee weapons; on a hit you can activate Push or Topple in addition to another mastery."),
            subclass="world_tree", roll_options=(_roots("push"), _roots("topple")),
            modifiers=(Modifier("reach", 10, source=f"feature:{CK}.battering_roots", when=_reach_weapon),)),
    feature("travel_along_the_tree", CK, ED, 14, "Viaggio lungo l'Albero / Travel along the Tree (Cammino dell'Albero del Mondo 14, pag. 56)",
            ("Viaggio lungo l'Albero", "Travel along the Tree"),
            ("Attivando l'Ira e poi con azione bonus in Ira, teletrasporto fino a 18 m; una volta per Ira 45 m con fino a sei alleati.",
             "When you activate the Rage and then as a bonus action while raging, teleport up to 60 ft; once per Rage 150 ft with up to six allies."),
            "bonus_action", subclass="world_tree",
            on_use=OnUse(slot="bonus", available=lambda c: state_on(c, "rage"), check=_travel_check, effect=_travel_effect,
                         message=_travel_message,
                         toggles=(UseToggle("far", _both("Fino a 45 m, con sei alleati (una volta per Ira)", "Up to 150 ft with six allies (once per Rage)"),
                                            available=lambda c: not _rage_opt(c, "far_used")),))),

    # Cammino dello Zelota
    feature("divine_fury", CK, ED, 3, "Furia Divina / Divine Fury (Cammino dello Zelota 3, pag. 57)", ("Furia Divina", "Divine Fury"),
            ("Nel tuo turno in Ira, la prima creatura colpita subisce 1d6 + metà livello da barbaro danni Necrotici o Radiosi, a scelta.",
             "On your turn while raging, the first creature you hit takes 1d6 + half your Barbarian level Necrotic or Radiant damage, your choice."),
            subclass="zealot", roll_options=(
                _divine_fury("necrotic", "Furia Divina: danni extra Necrotici", "Divine Fury: extra Necrotic damage"),
                _divine_fury("radiant", "Furia Divina: danni extra Radiosi", "Divine Fury: extra Radiant damage"))),
    feature("warrior_of_the_gods", CK, ED, 3, "Guerriero degli Dei / Warrior of the Gods (Cammino dello Zelota 3, pag. 57)",
            ("Guerriero degli Dei", "Warrior of the Gods"),
            ("Riserva di d12 (4, poi 5, 6, 7 ai livelli 6, 12, 17): azione bonus per spenderne e recuperare PF pari al tiro. Si ricarica con un riposo lungo.",
             "Pool of d12s (4, then 5, 6, 7 at levels 6, 12, 17): bonus action to spend dice and regain HP equal to the roll. Refills on a long rest."),
            "bonus_action", subclass="zealot", uses=Uses(table={3: 4, 6: 5, 12: 6, 17: 7}), restoration="long_rest",
            on_use=OnUse(slot="bonus", choose_amount=True, max_amount=7, rolls="1d12", heal=lambda _c, rolled: rolled)),
    feature("fanatical_focus", CK, ED, 6, "Concentrazione Fanatica / Fanatical Focus (Cammino dello Zelota 6, pag. 57)",
            ("Concentrazione Fanatica", "Fanatical Focus"),
            ("Una volta per Ira, dopo un TS fallito lo ripeti con un bonus pari al bonus danni dell'Ira e vale il nuovo risultato.",
             "Once per active Rage, after a failed save you reroll it with a bonus equal to your Rage damage bonus; the new roll stands."),
            subclass="zealot", roll_options=(FANATICAL_FOCUS,)),
    feature("zealous_presence", CK, ED, 10, "Presenza Zelante / Zealous Presence (Cammino dello Zelota 10, pag. 57)",
            ("Presenza Zelante", "Zealous Presence"),
            ("Azione bonus: fino a dieci creature entro 18 m hanno vantaggio ai tiri per colpire e ai TS fino al tuo turno seguente. Si ripristina con un uso di Ira.",
             "Bonus action: up to ten creatures within 60 ft have advantage on attack rolls and saves until your next turn. Restore it with a Rage use."),
            "bonus_action", subclass="zealot", uses=Uses(table={10: 1}), restoration="long_rest",
            on_use=OnUse(slot="bonus", state=_zealous_state, alt_spends=RAGE, alt_param="restore", toggles=(
                UseToggle("restore", _both("Ripristina spendendo un uso di Ira", "Restore by spending a Rage use"),
                          available=_depleted(f"{CK}.zealous_presence")),))),
    feature("rage_of_the_gods", CK, ED, 14, "Ira degli Dei / Rage of the Gods (Cammino dello Zelota 14, pag. 57)",
            ("Ira degli Dei", "Rage of the Gods"),
            ("Attivando l'Ira puoi assumere la forma divina per 1 minuto o fino a 0 PF. Una volta per riposo lungo; si sceglie all'ingresso in Ira.",
             "When you activate the Rage you can take a divine form for 1 minute or until 0 HP. Once per long rest; chosen when entering the Rage."),
            subclass="zealot", uses=Uses(table={14: 1}), restoration="long_rest"),
    feature("divine_flight", CK, ED, 14, "Volo / Flight (Ira degli Dei, Cammino dello Zelota 14, pag. 57)", ("Volo", "Flight"),
            ("Nella forma divina, velocità di volare pari alla velocità, puoi librarti.", "In the divine form, Fly Speed equal to your Speed, and you can hover."),
            subclass="zealot", modifiers=(Modifier("fly_speed", 1, source=f"feature:{CK}.divine_flight", when=_in_form),)),
    feature("divine_resistance", CK, ED, 14, "Resistenza / Resistance (Ira degli Dei, Cammino dello Zelota 14, pag. 57)",
            ("Resistenza", "Resistance"),
            ("Nella forma divina, resistenza ai danni Necrotico, Psichico e Radioso; si somma a quella dell'Ira.",
             "In the divine form, resistance to Necrotic, Psychic and Radiant damage; it adds to the Rage's."),
            subclass="zealot",
            modifiers=tuple(Modifier(f"resistance:{t}", 1, source=f"feature:{CK}.divine_resistance", when=_in_form)
                            for t in ("necrotic", "psychic", "radiant"))),
    feature("revivification", CK, ED, 14, "Rivivificazione / Revivification (Ira degli Dei, Cammino dello Zelota 14, pag. 57)",
            ("Rivivificazione", "Revivification"),
            ("Reazione nella forma divina: spendi un uso di Ira e una creatura entro 9 m che scenderebbe a 0 PF passa a PF pari al tuo livello da barbaro.",
             "Reaction in the divine form: spend a Rage use and a creature within 30 ft that would drop to 0 HP instead has HP equal to your Barbarian level."),
            "reaction", subclass="zealot",
            on_use=OnUse(slot="reaction", spends=RAGE, available=_in_form, gives=lambda c, _r: c.class_level)),

    feature("multiclassing", CK, ED, 1, "Multiclasse: Barbaro / Multiclassing: Barbarian (Barbaro, pag. 51; Multiclassing, pag. 44)",
            ("Multiclasse: Barbaro", "Multiclassing: Barbarian"),
            ("Requisito Forza 13. Da multiclasse: d12, armi da guerra, scudi e i privilegi del 1° livello; Attacco Extra non si somma.",
             "Requires Strength 13. As a multiclass: d12, martial weapons, shields and the level 1 features; Extra Attack does not stack."),
            no_row=True, covered_by=f"{_IT_NO_ROW} (as_multiclass), api/routers/classes.py add_class e webapp/src/data/multiclassPrereqs.ts (D2)"),
)


def _strength_score(ctx: RuleContext) -> int:
    from core.rules.weapons import ability_score  # import locale
    return ability_score(ctx.char, "strength")

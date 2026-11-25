"""Talenti generali 2024 (Manuale del Giocatore 2024, pagg. 202-210) nel motore: quello che l'app sa modellare agisce da
solo, il resto (distanze, spinte, azioni bonus d'attacco, oggetti) resta nel riassunto per il GM (D1).

La riga del talento è un ``FeatSource``: ``ctx.class_row.options["ability"]`` è la caratteristica del +1 scelta."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from core.data.damage_types import DAMAGE_TYPES, canonical_damage_type
from core.data.feats import LIST_ABILITY, MI_ABILITIES, MI_LISTS
from core.data.skills import SKILL_ABILITY_MAP
from core.game.item_bonuses import item_meta
from core.rules.catalog._common import heavy_armor, state_on
from core.rules.catalog.feats import D20_TESTS, _f24, _register
from core.rules.catalog.y2014.fighter import _off_hand_modifier, _weapon_in_hand
from core.rules.catalog.y2024.fighter import STYLE_ROWS
from core.rules.types import Cost, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, Uses
from core.rules.weapons import MASTERY_OPTIONS, has_property, weapon_key
from core.utils.session_view import armor_category

_PHYSICAL = ("bludgeoning", "piercing", "slashing")
_CROSSBOWS = ("light_crossbow", "hand_crossbow", "heavy_crossbow")
_DUELIST = "feat.2024_defensive_duelist"


def _both(it: str, en: str) -> dict[str, str]:
    return {"it": it, "en": en}


def _pb(ctx: RuleContext) -> int:
    return ctx.char.proficiency_bonus


def _feat_mod(ctx: RuleContext) -> int:
    """Modificatore della caratteristica aumentata dal talento (``options["ability"]``)."""
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    ability = (getattr(ctx.class_row, "options", None) or {}).get("ability")
    return effective_ability_mod(ctx.char, ability) if ability else 0


def _total_level(ctx: RuleContext) -> int:
    return ctx.class_level


def _weapon_damage(ctx: RuleContext) -> bool:
    return ctx.roll == "damage" and _weapon_in_hand(ctx)


def _weapon_type(ctx: RuleContext) -> str | None:
    return canonical_damage_type(item_meta(ctx.item).get("damage_type")) if ctx.item is not None else None


def _two_weapon_style(char: Any) -> bool:
    from core.rules.catalog import active_features
    return any(spec.key.endswith(("style_two_weapon", "fs_two_weapon")) for spec, _row in active_features(char))


def _crossbow_offhand(ctx: RuleContext) -> bool:
    """Esperto di balestre: il modificatore sul colpo extra della balestra Leggera, se lo stile non lo dà già."""
    return (_weapon_damage(ctx) and ctx.offhand and weapon_key(ctx.item) in _CROSSBOWS
            and not _two_weapon_style(ctx.char))


def _finesse_in_hand(ctx: RuleContext) -> bool:
    return any(i.is_equipped and i.item_type == "weapon" and has_property(i, "finesse") for i in ctx.char.items or [])


def _medium_armor_dex(ctx: RuleContext) -> bool:
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    return ctx.roll == "ac" and armor_category(ctx.char) == "medium" and effective_ability_mod(ctx.char, "dexterity") >= 3


def _shove_message(ctx: RuleContext, _params: dict) -> dict[str, str]:
    dc = 8 + _pb(ctx) + _feat_mod(ctx)
    return _both(f"Spinta telecinetica: la creatura entro 9 m fa un TS di Forza CD {dc} o viene spostata di 1,5 m.",
                 f"Telekinetic Shove: the creature within 30 ft makes a Strength save DC {dc} or is moved 5 ft.")


def _adept_type(ctx: RuleContext) -> bool:
    """Adepto elementale: dadi del danno di un incantesimo del tipo scelto (``options["damage_type"]``)."""
    chosen = (getattr(ctx.class_row, "options", None) or {}).get("damage_type")
    return ctx.spell is not None and chosen is not None and ctx.damage_type == chosen


def _leader_hp(ctx: RuleContext) -> int:
    return _total_level(ctx) + _feat_mod(ctx)


_register(
    _f24("actor", roll_options=(RollOptionSpec(
        key="feat.2024_actor", phase="before", rolls=("skill",), mode="advantage",
        available=lambda c: c.skill in ("deception", "performance"),
        label=_both("Attore: vantaggio fingendoti un'altra persona", "Actor: advantage while posing as someone else")),)),
    _f24("athlete", modifiers=(Modifier("climb_speed", 0),)),
    _f24("charger", roll_options=(RollOptionSpec(
        key="feat.2024_charger", phase="after_hit", rolls=("attack",), once_per_turn=True, extra_dice=lambda _c, _i: "1d8",
        available=lambda c: c.attack_mode == "melee",
        label=_both("Assalitore: ti sei mosso di almeno 3 m in linea retta, +1d8 al danno",
                    "Charger: you moved at least 10 ft in a straight line, +1d8 damage")),)),
    _f24("chef", passive=False, action_type="bonus_action", uses=Uses(proficiency=True), restoration="long_rest",
         proficiency_grants={"tools": ("cooks_utensils",)},
         on_use=OnUse(slot="bonus", temp_hp=lambda c, _rolled: _pb(c))),
    _f24("crossbow_expert", modifiers=(Modifier("damage", _off_hand_modifier, when=_crossbow_offhand),)),
    _f24("crusher"),
    _f24("elemental_adept", modifiers=(Modifier("damage_min_die", 2, when=_adept_type),)),
    # Toccato dalle fate / dall'ombra: due lanci gratuiti per riposo lungo, condivisi fra l'incantesimo fisso e quello
    # scelto (``options["spell"]``); il manuale ne dà uno per incantesimo (ruling della PR 2)
    _f24("fey_touched", passive=False, granted_spells=("misty-step",), free_spell="misty-step", arcanum_group="spell",
         uses=Uses(table={1: 2}), restoration="long_rest"),
    _f24("keen_mind"),  # competenza o Maestria applicate al completamento; Studio rapido: testo
    _f24("observant"),
    _f24("ritual_caster", ritual_casting=True),
    _f24("shadow_touched", passive=False, granted_spells=("invisibility",), free_spell="invisibility", arcanum_group="spell",
         uses=Uses(table={1: 2}), restoration="long_rest"),
    _f24("skill_expert"),
    # la padronanza scelta (``options["weapon_mastery"]``) la legge ``core.rules.weapons._knows``; le opzioni sono quelle
    # delle classi (stesse chiavi: con una classe che le ha già non si duplicano)
    _f24("weapon_master", roll_options=MASTERY_OPTIONS),
    _f24("defensive_duelist", passive=False, action_type="reaction",
         on_use=OnUse(slot="reaction", available=_finesse_in_hand,
                      state=StateSpec(_DUELIST, rounds=1, ends_on=("new_turn", "manual"))),
         modifiers=(Modifier("ac", _pb, when=lambda c: c.roll == "ac" and state_on(c, _DUELIST)),)),
    _f24("dual_wielder"),
    _f24("durable", modifiers=(Modifier("advantage", 0, when=lambda c: c.roll == "death_save"),)),
    _f24("grappler", roll_options=(RollOptionSpec(
        key="feat.2024_grappler", phase="before", rolls=("attack",), mode="advantage",
        label=_both("Lottatore: vantaggio contro la creatura che stai afferrando",
                    "Grappler: advantage against the creature you are grappling")),)),
    _f24("great_weapon_master", modifiers=(
        Modifier("damage", _pb, when=lambda c: _weapon_damage(c) and has_property(c.item, "heavy")),)),
    _f24("heavily_armored", proficiency_grants={"armor": ("heavy",)}),
    _f24("heavy_armor_master", roll_options=(RollOptionSpec(
        # offerta, non automatica: vale solo per il danno di un attacco che ti colpisce (non cadute o trappole)
        key="feat.2024_heavy_armor_master", phase="damage_in", rolls=("damage_taken",),
        bonus=lambda c, _i: _pb(c), available=lambda c: heavy_armor(c.char) and c.damage_type in _PHYSICAL,
        label=_both("Maestro di armature pesanti: il danno viene da un attacco che ti colpisce, riducilo della competenza",
                    "Heavy Armor Master: the damage comes from an attack that hits you, reduce it by your proficiency bonus")),)),
    _f24("inspiring_leader", rest_temp_hp=_leader_hp, rest_temp_hp_ally=lambda c: (5, _leader_hp(c))),
    _f24("lightly_armored", proficiency_grants={"armor": ("light", "shields")}),
    _f24("mage_slayer", uses=Uses(table={1: 1}), restoration="short_rest", passive=False, roll_options=(RollOptionSpec(
        key="feat.2024_mage_slayer", phase="after_roll", after="succeed", rolls=("save",),
        available=lambda c: c.ability in ("intelligence", "wisdom", "charisma"), cost=Cost(feature_key="feat.2024_mage_slayer"),
        label=_both("Mente protetta: il TS fallito diventa un successo", "Guarded Mind: the failed save becomes a success")),)),
    _f24("martial_weapon_training", proficiency_grants={"weapons": ("martial",)}),
    _f24("medium_armor_master", modifiers=(Modifier("ac", 1, when=_medium_armor_dex),)),
    _f24("moderately_armored", proficiency_grants={"armor": ("medium", "shields")}),
    _f24("mounted_combatant"),
    _f24("piercer",
         modifiers=(Modifier("crit_dice", 1, when=lambda c: _weapon_damage(c) and _weapon_type(c) == "piercing"),),
         roll_options=(RollOptionSpec(
             key="feat.2024_piercer", phase="after_damage", rolls=("weapon_damage",), once_per_turn=True,
             reroll_dice=lambda _c, _i: 1, available=lambda c: _weapon_type(c) == "piercing",
             label=_both("Perforatore: ritira un dado di danno perforante", "Piercer: reroll one piercing damage die")),)),
    _f24("poisoner"),
    _f24("polearm_master"),
    _f24("resilient"),  # +1 e competenza nel TS li applica ``take_feat``
    _f24("sentinel"),
    _f24("sharpshooter"),
    _f24("shield_master"),
    _f24("skulker", modifiers=(Modifier("sense:blindsight", 10),)),
    _f24("slasher"),
    _f24("speedy", modifiers=(Modifier("speed", 10),)),
    _f24("spell_sniper"),
    _f24("telekinetic", passive=False, action_type="bonus_action", granted_spells=("mage-hand",),
         on_use=OnUse(slot="bonus", message=_shove_message)),
    _f24("telepathic", passive=False, granted_spells=("detect-thoughts",), free_spell="detect-thoughts",
         uses=Uses(table={1: 1}), restoration="long_rest"),
    _f24("war_caster", modifiers=(Modifier("advantage", 0, when=lambda c: c.roll == "concentration"),)),
    needs={"feat.2024_keen_mind": ("skill",), "feat.2024_observant": ("skill",), "feat.2024_skill_expert": ("skill", "expertise"),
           "feat.2024_elemental_adept": ("damage_type",), "feat.2024_fey_touched": ("spell",),
           "feat.2024_shadow_touched": ("spell",), "feat.2024_ritual_caster": ("rituals",),
           "feat.2024_weapon_master": ("weapon_mastery",)},
)


# ---------------------------------------------------------------------------
# Stili di Combattimento come talento (pag. 209): gli effetti dello stile del Guerriero, riga del talento
# ---------------------------------------------------------------------------

def _style_feat(spec: Any) -> Any:
    key = f"feat.2024_fs_{spec.option_key}"
    return replace(spec, key=key, class_key="feat", level=1, option_group=None, option_key=None,
                   source_title=f"{spec.name['it']} / {spec.name['en']} (talento)",
                   modifiers=tuple(replace(m, source=f"feature:{key}") for m in spec.modifiers))


_register(*(_style_feat(s) for s in STYLE_ROWS))


# ---------------------------------------------------------------------------
# Doni Epici (pagg. 210-211)
# ---------------------------------------------------------------------------

ENERGY_TYPES = ("acid", "cold", "fire", "lightning", "necrotic", "poison", "psychic", "radiant", "thunder")
ADEPT_TYPES = ("acid", "cold", "fire", "lightning", "thunder")
# Artigiano (pag. 200): gli strumenti della tabella Creazione rapida
FAST_CRAFTING_TOOLS = ("carpenters_tools", "leatherworkers_tools", "masons_tools", "potters_tools", "smiths_tools",
                       "tinkers_tools", "weavers_tools", "woodcarvers_tools")
_NIGHT = "feat.2024_boon_night_spirit"


def _chosen_energy(kind: str):
    return lambda c: kind in ((getattr(c.class_row, "options", None) or {}).get("damage_types") or [])


def _con_mod(ctx: RuleContext) -> int:
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    return effective_ability_mod(ctx.char, "constitution")


def _half_max(ctx: RuleContext) -> int:
    from core.rules.modifiers import effective_hp_max  # import locale: modifiers usa il catalogo
    return effective_hp_max(ctx.char) // 2


def _redirect_effect(ctx: RuleContext, _inputs: dict) -> dict[str, str]:
    mod = _con_mod(ctx)
    dc = 8 + mod + _pb(ctx)
    return _both(f"Reindirizzamento: una creatura visibile entro 18 m (non dietro Copertura Totale) fa un TS Destrezza CD {dc} o subisce 2d12 {mod:+d} danni dello stesso tipo. Tira tu e applica il danno: lo decide il GM.",
                 f"Channel Energy: a creature you can see within 60 ft (not behind Total Cover) makes a Dexterity save DC {dc} or takes 2d12 {mod:+d} damage of the same type. Roll it and apply it: the GM decides.")


REDIRECT = RollOptionSpec(
    key="feat.2024_boon_energy_resistance_redirect", phase="damage_in", rolls=("damage_taken",), slot="reaction",
    available=lambda c: bool(c.damage_type) and _chosen_energy(c.damage_type)(c),
    label=_both("Reindirizzamento: reazione, dirigi il danno subito verso un'altra creatura (2d12 + Cos, TS Destrezza)",
                "Channel Energy: reaction, redirect the damage you took at another creature (2d12 + Con, Dexterity save)"),
    effect=_redirect_effect)


def _natural_20(ctx: RuleContext) -> bool:
    pending = (ctx.char.turn_state or {}).get("pending_attack") or {}
    return (pending.get("result") or {}).get("to_hit_die") == 20


def _offense_score(ctx: RuleContext, _inputs: dict) -> int:
    from core.game.stats import effective_ability_score  # import locale: stats usa il catalogo
    name = (getattr(ctx.class_row, "options", None) or {}).get("ability")
    row = next((a for a in ctx.char.ability_scores if a.name == name), None)
    return effective_ability_score(name, row.value, [i for i in ctx.char.items if i.is_equipped])[0] if row else 0


OVERWHELMING_STRIKE = RollOptionSpec(
    key="feat.2024_boon_irresistible_offense_strike", phase="after_hit", rolls=("attack",), available=_natural_20, bonus=_offense_score,
    label=_both("Colpo travolgente: 20 naturale, danni extra pari al punteggio della caratteristica del Dono",
                "Overwhelming Strike: natural 20, extra damage equal to the Boon's ability score"))

# Ultima resistenza: lo stato «pronto» nasce con il Dono (``take_feat``) e a ogni Riposo Lungo, e si chiude quando scatta
LAST_STAND_STATE = "boon_last_stand"
LAST_STAND = RollOptionSpec(
    key="feat.2024_boon_recovery_last_stand", phase="damage_in", rolls=("damage_taken",), holds_at_one=True, holds_vs_massive=True,
    cost=Cost(state_key=LAST_STAND_STATE),
    # shortcut: metà del massimo senza il bonus homebrew ai PF, che il core non vede; rivederlo se serve
    holds_heal=lambda c: _half_max(c),
    label=_both("Ultima resistenza: se il danno ti porta a 0 PF resti a 1 PF e recuperi metà dei PF massimi (una volta per riposo lungo)",
                "Last Stand: if the damage takes you to 0 HP you stay at 1 HP and regain half your maximum HP (once per long rest)"))


def last_stand_state() -> StateSpec:
    return StateSpec(LAST_STAND_STATE, ends_on=("manual",))


_register(
    _f24("boon_combat_prowess", roll_options=(RollOptionSpec(
        key="feat.2024_boon_combat_prowess", phase="after_roll", after="succeed", rolls=("attack",), once_per_turn=True,
        label=_both("Prodigio in combattimento: l'attacco mancato diventa un colpo (poi non prima del tuo prossimo turno)",
                    "Combat Prowess: the missed attack becomes a hit (then not again until your next turn)")),)),
    _f24("boon_dimensional_travel"),
    _f24("boon_energy_resistance", modifiers=tuple(Modifier(f"resistance:{t}", 0, when=_chosen_energy(t)) for t in ENERGY_TYPES),
         roll_options=(REDIRECT,)),
    _f24("boon_fate", passive=False, uses=Uses(table={1: 1}), restoration="short_rest", roll_options=(RollOptionSpec(
        key="feat.2024_boon_fate", phase="after_roll", after="add", rolls=D20_TESTS, extra_dice=lambda _c, _i: "2d4",
        cost=Cost(feature_key="feat.2024_boon_fate"),
        label=_both("Dono del Fato: somma 2d4 al Test d20", "Boon of Fate: add 2d4 to the d20 Test")),)),
    # Cure extra: nessun gancio su ogni cura, il pulsante «Usa» le dà a mano (una volta fino all'inizio del turno seguente)
    _f24("boon_fortitude", modifiers=(Modifier("hp_max", 40),), passive=False,
         on_use=OnUse(once_per_turn=True, heal=lambda c, _rolled: max(_con_mod(c), 0))),
    # «Supera le difese» (ignora le resistenze) resta testo: le resistenze dei nemici non sono modellate
    _f24("boon_irresistible_offense", roll_options=(OVERWHELMING_STRIKE,)),
    # La riserva di dieci d10 è l'uso della riga; Ultima resistenza usa lo stato «pronto» (una volta per riposo lungo)
    _f24("boon_recovery", passive=False, action_type="bonus_action", uses=Uses(table={1: 10}), restoration="long_rest",
         on_use=OnUse(slot="bonus", choose_amount=True, rolls_by_amount=lambda _c, n: f"{n}d10", heal=lambda _c, rolled: rolled),
         roll_options=(LAST_STAND,), long_rest_state=lambda _c: last_stand_state()),
    _f24("boon_skill"),  # competenze e Maestria le dà ``complete_feat``, che segna quelle nuove (la rimozione le toglie)
    _f24("boon_speed", modifiers=(Modifier("speed", 30),)),
    _f24("boon_spell_recall"),
    _f24("boon_night_spirit", passive=False, action_type="bonus_action",
         on_use=OnUse(slot="bonus", state=StateSpec(_NIGHT, ends_on=("manual",))),
         modifiers=tuple(Modifier(f"resistance:{t}", 0, when=lambda c: state_on(c, _NIGHT))
                         for t in DAMAGE_TYPES if t not in ("psychic", "radiant"))),
    _f24("boon_truesight", modifiers=(Modifier("sense:truesight", 60),)),
    needs={"feat.2024_boon_energy_resistance": ("damage_types",), "feat.2024_boon_skill": ("expertise",)},
)


def _tool(name: str) -> str | None:
    """Chiave del catalogo, o nome riconosciuto (file salvati prima che i talenti scegliessero dal catalogo)."""
    from core.data.tools import TOOLS, tool_key
    return name if name in TOOLS else tool_key(name) if isinstance(name, str) else None


def _tools_ok(values: list, categories: tuple[str, ...] | None) -> bool:
    from core.data.tools import TOOLS
    keys = [_tool(v) for v in values]
    return (len(keys) == 3 and len(set(keys)) == 3 and all(keys)
            and (categories is None or all(TOOLS[k].category in categories for k in keys)))


def _picks_ok(values: list) -> bool:
    skills = [p for p in values if not str(p).startswith("tool:")]
    tools = [str(p)[len("tool:"):] for p in values if str(p).startswith("tool:")]
    return (len(values) == 3 and set(skills) <= set(SKILL_ABILITY_MAP) and all(_tool(t) for t in tools)
            and len({*skills, *(_tool(t) for t in tools)}) == 3)


def options_ok(options: dict, feature_key: str = "") -> bool:
    """Le scelte salvate di un talento rispettano numero e valori ammessi (import di un file: altrimenti si scartano e il
    talento torna «da completare»). Liste di classe e caratteristica dipendono dal talento (``feature_key``)."""
    from core.data.feats_2024 import ALL_FEATS
    from core.rules.catalog.y2014.fighter import MANEUVERS  # import locale come WEAPONS
    from core.rules.weapons import WEAPONS  # import locale: weapons legge il registro dei talenti
    count = lambda n: (lambda v: len(v) == n)  # noqa: E731
    checks = {
        "damage_types": lambda v: len(v) == 2 and len(set(v)) == 2 and set(v) <= set(ENERGY_TYPES),
        "damage_type": lambda v: v in ADEPT_TYPES,
        "weapon_mastery": lambda v: len(v) == 1 and v[0] in WEAPONS,
        "skill": lambda v: v in SKILL_ABILITY_MAP,
        "expertise": lambda v: v in SKILL_ABILITY_MAP,
        "granted_skills": lambda v: set(v) <= set(SKILL_ABILITY_MAP),
        "list": lambda v: v in (MI_LISTS if feature_key.startswith("feat.2024_") else LIST_ABILITY),
        "maneuvers": lambda v: len(v) == 2 and len(set(v)) == 2 and set(v) <= {k for k, _it, _en in MANEUVERS},
        "languages": count(3),
        "weapons": lambda v: len(v) == 4 and len(set(v)) == 4 and set(v) <= set(WEAPONS),
        "rituals": lambda v: len(v) <= 6,
        "picks": _picks_ok, "tools": lambda v: _tools_ok(v, None) and all(_tool(x) in FAST_CRAFTING_TOOLS for x in v), "instruments": lambda v: _tools_ok(v, ("instrument",)),
        "cantrips": lambda v: len(v) <= 2, "spell": lambda v: len(v) <= 1,
    }
    spec = ALL_FEATS.get(feature_key[len("feat."):])
    if "ability" in options:
        ability = options["ability"]
        if "list" in options and not feature_key.startswith("feat.2024_"):  # talenti 2014: la caratteristica della classe
            ok = ability == LIST_ABILITY.get(options["list"])
        elif "list" in options:  # Iniziato alla magia 2024: scelta fra le tre da incantatore
            ok = ability in MI_ABILITIES
        else:  # caratteristica del +1
            ok = spec is None or ability in (spec.ability_increase or ())
        if not ok:
            return False
    return all(check(v) for k, v in options.items() if (check := checks.get(k)))

"""Druido 2024: base della classe (Task 34, parte A). I circoli (Terra, Luna, Mare, Stelle) vengono dopo (parte B).

Valori dalla scheda ``docs/superpowers/rules/2024/classes/druid.md``; i testi sono nostri, mai quelli del manuale.
La Forma Selvatica è la riserva ``druid.wild_shape`` (stessa chiave del 2014): usi, forme conosciute, durata, PF temporanei e CA
stanno in ``core/rules/forms.py`` e ``api/services/wild_shape.py``; qui ci sono gli usi a tabella e le azioni che la spendono.

Parte B: i privilegi di circolo stanno in ``CIRCLE_FEATURES`` (``subclass="land"|"moon"|"sea"|"stars"``) e spendono
``WILD_SHAPE`` con ``OnUse.spends``. GS, CA e PF temporanei della Luna stanno già in ``FormRules``. Il terreno della Terra è la
scelta sostituibile ``land_terrain``; la Forma Stellare è lo stato ``starry_form`` (la costellazione sta nei dati).
"""
from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

from core.rules.catalog._common import feature, state_on
from core.rules.catalog.granted_spells import GRANTED_SPELLS
from core.rules.catalog.y2014.cleric import _no_options, _own_cantrip, _wisdom_mod, spell_dc
from core.rules.states import begin_state
from core.rules.types import (
    ChoiceSpec, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, UseChoice, Uses, UseText,
)

ED, CK = "2024", "druid"
WILD_SHAPE = f"{CK}.wild_shape"
WILD_COMPANION = f"{CK}.wild_companion"
ORDER, FURY = "primal_order", "elemental_fury"
NAME_MAX = 80
_NATURE = ("arcana", "nature")
_ENERGIES = {"cold": ("Freddo", "cold"), "fire": ("Fuoco", "fire"), "lightning": ("Fulmine", "lightning"),
             "thunder": ("Tuono", "thunder")}


def _chosen(ctx: RuleContext, group: str, option: str) -> bool:
    return option in ((getattr(ctx.class_row, "options", None) or {}).get(group) or [])


def _wild_row(ctx: RuleContext) -> Any:
    return next((a for a in ctx.char.abilities if a.feature_key == WILD_SHAPE and a.source_class_id == getattr(ctx.class_row, "id", None)), None)


def _no_uses_left(ctx: RuleContext) -> bool:
    row = _wild_row(ctx)
    return row is not None and row.max_uses is not None and (row.uses or 0) <= 0


def _free_slot_levels(ctx: RuleContext) -> list[str]:
    return [str(n) for n in sorted({s.level for s in ctx.char.spell_slots if s.used < s.total and s.level >= 1})]


def _level_label(key: str) -> dict[str, str]:
    return {"it": f"{key}° livello", "en": f"Level {key}"}


# ---------------------------------------------------------------------------
# Ordine Primordiale: Mago e Custode
# ---------------------------------------------------------------------------

def _magician_bonus(ctx: RuleContext) -> int:
    return max(1, _wisdom_mod(ctx))


MAGICIAN_BONUS = Modifier("skill", _magician_bonus, when=lambda c: c.roll == "skill" and c.skill in _NATURE,
                          source=f"feature:{CK}.primal_order_magician")


# ---------------------------------------------------------------------------
# Compagno Selvatico: Trova Famiglio pagando uno slot o un uso di Forma Selvatica
# ---------------------------------------------------------------------------

_PAYMENTS = {"wild_shape": {"it": "Un uso di Forma Selvatica", "en": "One Wild Shape use"},
             "slot": {"it": "Uno slot incantesimo", "en": "A spell slot"}}


def _companion_check(_ctx: RuleContext, params: dict) -> tuple[int, str] | None:
    return (422, "invalid_choice") if params.get("pay") == "slot" and params.get("slot_level") is None else None


def _companion_effect(ctx: RuleContext, params: dict) -> None:
    """Il famiglio è Fatato e scompare al riposo lungo (``long_rest_familiar``); un nuovo lancio sostituisce il precedente."""
    from core.db.models import Companion  # import locale: i modelli non servono al resto del catalogo
    for old in [c for c in ctx.char.companions if c.feature_key == WILD_COMPANION]:
        ctx.char.companions.remove(old)
    name = str(params.get("name") or "").strip() or "Famiglio"
    ctx.char.companions.append(Companion(
        character_id=ctx.char.id, kind="familiar", name=name, statblock={"type": "fey", "size": "Tiny"}, max_hp=1, current_hp=1,
        armor_class=11, feature_key=WILD_COMPANION, created_at=datetime.now(timezone.utc).isoformat(timespec="seconds")))


def _companion_message(_ctx: RuleContext, _params: dict) -> dict[str, str]:
    return {"it": "Lanci Trova Famiglio senza componenti materiali. Il famiglio è Fatato e scompare al riposo lungo: "
                  "è fra i compagni.",
            "en": "You cast Find Familiar with no Material components. The familiar is a Fey and vanishes on a long rest: "
                  "it is among your companions."}


WILD_COMPANION_USE = OnUse(
    slot="action", spends=WILD_SHAPE, cost_by=lambda _c, p: 1 if p.get("pay") == "wild_shape" else 0,
    spends_slot="slot_level", spends_slot_when=lambda _c, p: p.get("pay") == "slot", check=_companion_check,
    effect=_companion_effect, message=_companion_message,
    choices=(UseChoice("pay", {"it": "Costo", "en": "Cost"}, lambda _c: list(_PAYMENTS), lambda k: _PAYMENTS[k]),
             UseChoice("slot_level", {"it": "Livello dello slot", "en": "Slot level"}, _free_slot_levels, _level_label, optional=True)),
    texts=(UseText("name", {"it": "Nome del famiglio", "en": "Familiar name"}, max_len=NAME_MAX, optional=True),))


# ---------------------------------------------------------------------------
# Rigenerazione Selvatica
# ---------------------------------------------------------------------------

def _resurgence_use(ctx: RuleContext, _params: dict) -> None:
    row = _wild_row(ctx)
    if row is not None:
        row.uses = (row.uses or 0) + 1


RESURGENCE_USE = OnUse(
    once_per_turn=True, available=_no_uses_left, spends_slot="slot_level", effect=_resurgence_use,
    choices=(UseChoice("slot_level", {"it": "Slot da spendere", "en": "Slot to spend"}, _free_slot_levels, _level_label),),
    message=lambda _c, _p: {"it": "Hai recuperato un uso di Forma Selvatica.", "en": "You regained a Wild Shape use."})


def _resurgence_slot(ctx: RuleContext, _params: dict) -> None:
    from core.rules.created_slots import add_created_slot  # import locale: il catalogo si carica prima dei modelli
    add_created_slot(ctx.char, 1)


RESURGENCE_SLOT_STATE = f"{CK}.wild_resurgence_slot_used"
RESURGENCE_SLOT_USE = OnUse(
    spends=WILD_SHAPE, available=lambda c: not state_on(c, RESURGENCE_SLOT_STATE), effect=_resurgence_slot, state=StateSpec(RESURGENCE_SLOT_STATE, ends_on=("rest_long",), data={"locked": True}),
    message=lambda _c, _p: {"it": "Hai uno slot di 1° livello in più fino al riposo lungo. Serve un riposo lungo per rifarlo.",
                            "en": "You have an extra level 1 spell slot until your next long rest. It takes a long rest to do it again."})


# ---------------------------------------------------------------------------
# Furia Elementale: Incantesimi Potenti e Colpo Primordiale
# ---------------------------------------------------------------------------

POTENT = Modifier("damage", _wisdom_mod, when=lambda c: c.roll == "damage" and _own_cantrip(c),
                  source=f"feature:{CK}.elemental_fury_potent")


def _strike_dice(ctx: RuleContext, _inputs: dict) -> str:
    return "1d8" if ctx.class_level < 15 else "2d8"


def _attack_hit(ctx: RuleContext) -> bool:
    """Un colpo con un'arma (la forma Bestia ha le sue opzioni, ``_form_attack``: il suo attacco ha un passaggio solo)."""
    return ctx.spell is None and ctx.item is not None


def _form_attack(ctx: RuleContext) -> bool:
    """L'attacco di una forma di Forma Selvatica (``attack_mode="form"``), che il server tira in un passaggio solo."""
    return ctx.attack_mode == "form" and ctx.spell is None and state_on(ctx, "wild_shape")


def _primal_strike(kind: str) -> RollOptionSpec:
    it, en = _ENERGIES[kind]
    return RollOptionSpec(
        key=f"{CK}.primal_strike_{kind}", phase="after_hit", rolls=("attack",), once_per_turn=True, group="primal_strike",
        extra_dice=_strike_dice, available=_attack_hit,
        label={"it": f"Colpo Primordiale: danni da {it} in più", "en": f"Primal Strike: extra {en} damage"})


def _primal_strike_form(kind: str) -> RollOptionSpec:
    """Lo stesso privilegio sull'attacco della forma: si sceglie prima di tirare (l'attacco non ha il secondo passaggio)."""
    it, en = _ENERGIES[kind]
    return RollOptionSpec(
        key=f"{CK}.primal_strike_{kind}_form", phase="before", rolls=("attack",), once_per_turn=True, group="primal_strike",
        extra_dice=_strike_dice, available=_form_attack, pay_if_success=True,  # il giocatore dice se ha colpito: se no, torna
        label={"it": f"Colpo Primordiale: danni da {it} in più", "en": f"Primal Strike: extra {en} damage"})


def _regain_use(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    _resurgence_use(ctx, {})


EVERGREEN = RollOptionSpec(
    key=f"{CK}.evergreen_wild_shape", phase="before", rolls=("initiative",), on_confirm=_regain_use,
    available=lambda c: _no_uses_left(c) and c.class_level >= 20,
    label={"it": "Forma Selvatica Sempreverde: tirando l'Iniziativa senza usi ne recuperi uno",
           "en": "Archdruid's Evergreen Wild Shape: rolling Initiative with no uses left gives one back"})


# ---------------------------------------------------------------------------
# Arcidruido: Mago della Natura
# ---------------------------------------------------------------------------

NATURE_MAGICIAN_STATE = f"{CK}.nature_magician_used"


def _magician_cost(_ctx: RuleContext, params: dict) -> int:
    return int(params.get("uses") or 1)  # la scheda lo chiama anche senza parametri


def _magician_slot(ctx: RuleContext, params: dict) -> None:
    from core.rules.created_slots import add_created_slot  # import locale: il catalogo si carica prima dei modelli
    add_created_slot(ctx.char, 2 * int(params["uses"]))


def _magician_message(_ctx: RuleContext, params: dict) -> dict[str, str]:
    level = 2 * int(params["uses"])
    return {"it": f"Hai uno slot di {level}° livello in più fino al riposo lungo.",
            "en": f"You have an extra level {level} spell slot until your next long rest."}


NATURE_MAGICIAN_USE = OnUse(
    spends=WILD_SHAPE, cost_by=_magician_cost, available=lambda c: not state_on(c, NATURE_MAGICIAN_STATE),
    effect=_magician_slot, message=_magician_message,
    state=StateSpec(NATURE_MAGICIAN_STATE, ends_on=("rest_long",), data={"locked": True}),
    choices=(UseChoice("uses", {"it": "Usi da convertire (2 livelli ciascuno)", "en": "Uses to convert (2 levels each)"},
                       lambda c: [str(n) for n in range(1, min(4, (_wild_row(c).uses or 0) if _wild_row(c) else 0) + 1)],
                       lambda k: {"it": f"{k} (slot di {2 * int(k)}° livello)", "en": f"{k} (level {2 * int(k)} slot)"}),))


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Circoli (parte B): ausiliari comuni
# ---------------------------------------------------------------------------

def _state_data(ctx: RuleContext, key: str) -> dict:
    return next((s.get("data") or {} for s in ctx.char.active_states or [] if s.get("key") == key), {})


def _row(ctx: RuleContext, key: str) -> Any:
    return next((a for a in ctx.char.abilities if a.feature_key == key and a.source_class_id == getattr(ctx.class_row, "id", None)), None)


def _spell_names(keys: tuple[str, ...], lang: str) -> str:
    return ", ".join(GRANTED_SPELLS[k].name[lang] for k in keys)


def _tier_summary(tiers: tuple[tuple[str, ...], ...]) -> tuple[str, str]:
    return tuple(("Liv. " if lang == "it" else "Lv. ")
                 + "; ".join(f"{lv}: {_spell_names(t, lang)}" for lv, t in zip((3, 5, 7, 9), tiers)) for lang in ("it", "en"))


def _circle_spells(sub: str, title: str, name: tuple[str, str], tiers: tuple, cast_in_form: bool = False) -> list:
    """Incantesimi di circolo: al 3° livello la prima serie, poi 5°, 7° e 9°; sempre preparati, fuori dal limite."""
    def form(spells: tuple) -> dict:
        return {"cast_in_form_spells": spells} if cast_in_form else {}
    out = [feature(f"{sub}_spells", CK, ED, 3, title, name, _tier_summary(tiers), subclass=sub, granted_spells=tiers[0], **form(tiers[0]))]
    for tier, spells in zip((5, 7, 9), tiers[1:]):
        out.append(feature(f"{sub}_spells_{tier}", CK, ED, tier, title, name,
                           (f"Incantesimi di circolo del {tier}° livello.", f"Circle spells gained at level {tier}."),
                           subclass=sub, granted_spells=spells, no_row=True, **form(spells),
                           covered_by=f"{CK}.{sub}_spells (stessa voce della mappatura) e test_moon_and_sea_spells_arrive_at_3_5_7_and_9"))
    return out


def _slot_levels_from(minimum: int):
    return lambda ctx: [k for k in _free_slot_levels(ctx) if int(k) >= minimum]


# ---------------------------------------------------------------------------
# Circolo della Terra
# ---------------------------------------------------------------------------

LAND_TERRAIN = "land_terrain"
LAND_TITLE = "Incantesimi del Circolo della Terra / Circle of the Land Spells (Circolo della Terra 3, pag. 84)"
# terreno -> (nome it, nome en, tipo di danno di Interdizione della Natura, incantesimi ai livelli 3, 5, 7, 9)
TERRAINS: dict[str, tuple] = {
    "arid": ("Arido", "Arid", "fire", (("blur", "burning-hands", "fire-bolt"), ("fireball",), ("blight",), ("wall-of-stone",))),
    "polar": ("Polare", "Polar", "cold", (("fog-cloud", "hold-person", "ray-of-frost"), ("sleet-storm",), ("ice-storm",), ("cone-of-cold",))),
    "temperate": ("Temperato", "Temperate", "lightning",
                  (("misty-step", "shocking-grasp", "sleep"), ("lightning-bolt",), ("freedom-of-movement",), ("tree-stride",))),
    "tropical": ("Tropicale", "Tropical", "poison",
                 (("acid-splash", "ray-of-sickness", "web"), ("stinking-cloud",), ("polymorph",), ("insect-plague",))),
}
LANDS_AID = f"{CK}.lands_aid"
SANCTUARY = "natures_sanctuary"


def _terrain(ctx: RuleContext) -> str | None:
    return next(iter((getattr(ctx.class_row, "options", None) or {}).get(LAND_TERRAIN) or []), None)


def _land_rows() -> list:
    rows = [feature("land_spells", CK, ED, 3, LAND_TITLE, ("Incantesimi del Circolo della Terra", "Circle of the Land Spells"),
                    ("Dopo ogni riposo lungo scegli il terreno: i suoi incantesimi sono sempre preparati, fuori dal limite.",
                     "After each long rest you choose the terrain: its spells are always prepared, outside the limit."),
                    subclass="land", no_row=True,
                    choices=(ChoiceSpec(group=LAND_TERRAIN, levels={3: 1}, options=lambda _c: list(TERRAINS), replaceable=True),),
                    covered_by="ChoiceSpec land_terrain di questa riga e le righe dei terreni; test_land_spells_follow_the_chosen_terrain")]
    for key, (it, en, _res, tiers) in TERRAINS.items():
        name = (f"{it} (terreno)", f"{en} (terrain)")
        rows.append(feature(f"land_{key}", CK, ED, 3, LAND_TITLE, name, _tier_summary(tiers), subclass="land",
                            option_group=LAND_TERRAIN, option_key=key, granted_spells=tiers[0]))
        for tier, spells in zip((5, 7, 9), tiers[1:]):
            rows.append(feature(f"land_{key}_{tier}", CK, ED, tier, LAND_TITLE, name,
                                (f"Incantesimi di circolo del {tier}° livello.", f"Circle spells gained at level {tier}."),
                                subclass="land", option_group=LAND_TERRAIN, option_key=key, granted_spells=spells, no_row=True,
                                covered_by=f"{CK}.land_{key} (stessa voce della mappatura) e test_land_spells_follow_the_chosen_terrain"))
    return rows


def _aid_dice(ctx: RuleContext) -> str:
    return f"{2 if ctx.class_level < 10 else 3 if ctx.class_level < 14 else 4}d6"


LANDS_AID_HEAL = "lands_aid_heal"  # nel turno: la cura tirata, perché il messaggio dica lo stesso numero applicato


def _aid_heal(ctx: RuleContext, _rolled: int) -> int:
    """La cura è un tiro a parte dal danno (stessi dadi): la tira il server e la applica ``OnUse.heal``."""
    healed = sum(random.randint(1, 6) for _ in range(int(_aid_dice(ctx).split("d")[0])))
    ctx.char.turn_state = {**(ctx.char.turn_state or {}), LANDS_AID_HEAL: healed}
    return healed


def _aid_state(ctx: RuleContext, params: dict) -> StateSpec:
    return StateSpec("lands_aid", rounds=1, ends_on=("manual", "new_turn"), data={
        "dc": spell_dc(ctx), "save": "constitution", "damage_type": "necrotic", "damage": int(params.get("rolled") or 0),
        "others": [LANDS_AID]})


def _aid_message(ctx: RuleContext, params: dict) -> dict[str, str]:
    data = _state_data(ctx, "lands_aid")
    healed = (ctx.char.turn_state or {}).get(LANDS_AID_HEAL)
    mine = params.get("mode") == "self"
    told = params.get("ally_healed")  # l'alleato della serata è già curato e ha il suo toast
    text = {"it": f"Sfera di 3 m entro 18 m: ogni creatura scelta fa un TS Costituzione (CD {data.get('dc')}) e subisce "
                  f"{data.get('damage')} danni necrotici, la metà se lo supera. "
                  + (f"Hai recuperato {healed} PF." if mine else "" if told else
                     f"Un'altra creatura scelta recupera {healed} PF: se siede alla serata e l'hai scelta, è già curata; altrimenti riferiscili al GM."),
            "en": f"Sphere of 10 ft within 60 ft: each chosen creature makes a Constitution save (DC {data.get('dc')}) and takes "
                  f"{data.get('damage')} necrotic damage, half on a success. "
                  + (f"You regained {healed} HP." if mine else "" if told else
                     f"Another chosen creature regains {healed} HP: if it sits at the evening and you picked it, it is already healed; "
                     "otherwise tell the GM.")}
    return {lang: line.rstrip() for lang, line in text.items()}  # senza la frase sull'alleato resta lo spazio finale


_AID_MODES = {"self": {"it": "Cura te", "en": "Heal yourself"}, "other": {"it": "Cura un'altra creatura", "en": "Heal another creature"}}
LANDS_AID_USE = OnUse(
    slot="action", spends=WILD_SHAPE, rolls=_aid_dice, state=_aid_state, message=_aid_message, heal=_aid_heal,
    heal_when=lambda _c, p: p.get("mode") == "self", heal_ally_when=lambda _c, p: p.get("mode") == "other", ally_modes=("other",),
    choices=(UseChoice("mode", {"it": "Chi recupera i PF", "en": "Who regains the HP"}, lambda _c: list(_AID_MODES), lambda k: _AID_MODES[k]),))


def _circle_cast_options(ctx: RuleContext) -> list[str]:
    terrain = _terrain(ctx)
    tiers = TERRAINS[terrain][3] if terrain in TERRAINS else ()
    return [s for lv, spells in zip((3, 5, 7, 9), tiers) if ctx.class_level >= lv for s in spells if GRANTED_SPELLS[s].level >= 1]


def _recovery_cast(ctx: RuleContext, params: dict) -> None:
    """Autorizza un lancio gratuito (R43) di un incantesimo di circolo; il lancio chiude l'autorizzazione."""
    spell = str(params["spell"])
    begin_state(ctx.char, StateSpec("natural_recovery_free", ends_on=("manual", "rest_long"), data={"free_cast": spell, "spell": spell}),
                f"{CK}.natural_recovery_cast", "Recupero Naturale")


NATURAL_RECOVERY_CAST = OnUse(
    effect=_recovery_cast,
    choices=(UseChoice("spell", {"it": "Incantesimo del circolo (1° livello o più)", "en": "Circle spell (level 1 or higher)"},
                       _circle_cast_options, lambda k: dict(GRANTED_SPELLS[k].name)),),
    message=lambda _c, _p: {"it": "Lancia l'incantesimo dalla pagina degli incantesimi, senza slot.",
                            "en": "Cast the spell from the spells page, with no slot."})


def _ward_resistance(terrain: str) -> Modifier:
    return Modifier(f"resistance:{TERRAINS[terrain][2]}", 1, when=lambda c: _terrain(c) == terrain, source=f"feature:{CK}.natures_ward")


def _sanctuary_state(ctx: RuleContext, _params: dict) -> StateSpec:
    terrain = _terrain(ctx)
    return StateSpec(SANCTUARY, rounds=10, ends_on=("incapacitated", "manual"), data={
        "cover": "half", "resistance": TERRAINS[terrain][2] if terrain in TERRAINS else None, "others": [f"{CK}.natures_sanctuary"]})


SANCTUARY_USE = OnUse(
    slot="action", spends=WILD_SHAPE, state=_sanctuary_state,
    message=lambda _c, _p: {"it": "Cubo di 4,5 m su terreno entro 36 m, per 1 minuto: tu e gli alleati nell'area avete Copertura Parziale "
                                  "(+2 a CA e TS Destrezza, già sulla scheda) e gli alleati la Resistenza di Interdizione della Natura.",
                            "en": "Cube of 15 ft on ground within 120 ft, for 1 minute: you and allies inside have Half Cover "
                                  "(+2 AC and Dexterity saves, already on the sheet) and allies get Nature's Ward resistance."})


# ---------------------------------------------------------------------------
# Circolo della Luna
# ---------------------------------------------------------------------------

MOON_SPELLS = (("cure-wounds", "moonbeam", "starry-wisp"), ("conjure-animals",), ("fount-of-moonlight",), ("mass-cure-wounds",))


def _in_form(ctx: RuleContext) -> bool:
    return state_on(ctx, "wild_shape")


CON_IN_FORM = Modifier("save", _wisdom_mod, when=lambda c: c.roll in ("save", "concentration") and c.ability == "constitution" and _in_form(c),
                       source=f"feature:{CK}.improved_circle_forms")
RADIANT_MOON = RollOptionSpec(
    key=f"{CK}.radiant_moon", phase="before", rolls=("attack",), available=_form_attack,
    label={"it": "Radianza Lunare: il colpo infligge danni Radiosi invece del tipo normale",
           "en": "Lunar Radiance: the hit deals Radiant damage instead of its normal type"},
    effect=lambda _c, _i: {"it": "Il danno di questo colpo è Radioso.", "en": "This hit's damage is Radiant."})
LUNAR_RADIANCE = RollOptionSpec(
    key=f"{CK}.lunar_radiance", phase="before", rolls=("attack",), once_per_turn=True, extra_dice=lambda _c, _i: "2d10", available=_form_attack,
    pay_if_success=True,
    label={"it": "Radianza Lunare Migliorata: 2d10 danni Radiosi in più (una volta per turno)",
           "en": "Improved Lunar Radiance: 2d10 extra Radiant damage (once per turn)"})
MOONLIGHT_STEP = f"{CK}.moonlight_step"
MOONLIGHT_STATE = "moonlight_step"
STEP_ADVANTAGE = Modifier("advantage", 1, when=lambda c: c.roll == "attack" and state_on(c, MOONLIGHT_STATE), source=f"feature:{MOONLIGHT_STEP}")


def _step_slot(ctx: RuleContext, _params: dict) -> None:
    _row(ctx, MOONLIGHT_STEP).uses += 1


def _step_slot_check(ctx: RuleContext, _params: dict) -> tuple[int, str] | None:
    row = _row(ctx, MOONLIGHT_STEP)
    return None if row is not None and row.max_uses is not None and (row.uses or 0) < row.max_uses else (409, "uses_full")


def _step_message(ctx: RuleContext, _params: dict) -> dict[str, str]:
    carry = ctx.class_level >= 14
    return {"it": "Ti teletrasporti entro 9 m in uno spazio libero visibile." + (
                " Puoi portare con te una creatura consenziente entro 3 m (Forma Lunare)." if carry else ""),
            "en": "You teleport up to 30 ft to an unoccupied space you can see." + (
                " You can bring a willing creature within 10 ft (Lunar Form)." if carry else "")}


# ---------------------------------------------------------------------------
# Circolo del Mare
# ---------------------------------------------------------------------------

SEA_SPELLS = (("fog-cloud", "gust-of-wind", "ray-of-frost", "shatter", "thunderwave"), ("lightning-bolt", "water-breathing"),
              ("control-water", "ice-storm"), ("conjure-elemental", "hold-monster"))
WRATH = "wrath_of_the_sea"
ALLY_WRATH = "oceanic_gift_ally"
_TARGETS = {"ally": {"it": "Una creatura consenziente (1 uso)", "en": "A willing creature (1 use)"},
            "both": {"it": "Te e una creatura consenziente (2 usi)", "en": "You and a willing creature (2 uses)"}}


def _wrath_dice(ctx: RuleContext) -> str:
    return f"{max(1, _wisdom_mod(ctx))}d6"


def _wrath_data(ctx: RuleContext, params: dict, key: str) -> dict:
    return {"dc": spell_dc(ctx), "save": "constitution", "damage_type": "cold", "damage": int(params.get("rolled") or 0),
            "radius_m": 3 if ctx.class_level >= 6 else 1.5, "others": [f"{CK}.{key}"]}


def _only_emanation(ctx: RuleContext, keep: str) -> None:
    """Crearne una nuova chiude l'altra (su di sé o su un alleato): l'Ira del Mare è una sola alla volta."""
    ctx.char.active_states = [s for s in ctx.char.active_states or [] if s.get("key") not in (WRATH, ALLY_WRATH) or s.get("key") == keep]


def _wrath_state(ctx: RuleContext, params: dict) -> StateSpec:
    return StateSpec(WRATH, rounds=100, ends_on=("incapacitated", "manual"), data=_wrath_data(ctx, params, "wrath_of_the_sea"))


def _gift_state(ctx: RuleContext, params: dict) -> StateSpec:
    if params.get("target") == "both":
        return StateSpec(WRATH, rounds=100, ends_on=("incapacitated", "manual"),
                         data={**_wrath_data(ctx, params, "oceanic_gift"), "also_ally": True})
    return StateSpec(ALLY_WRATH, rounds=100, ends_on=("incapacitated", "manual"), data=_wrath_data(ctx, params, "oceanic_gift"))


def _wrath_message(ctx: RuleContext, _params: dict) -> dict[str, str]:
    data = _state_data(ctx, WRATH) or _state_data(ctx, ALLY_WRATH)
    meters = "3" if data.get("radius_m") == 3 else "1,5"
    return {"it": f"Emanazione di {meters} m per 10 minuti: una creatura visibile nell'area fa un TS Costituzione (CD {data.get('dc')}) "
                  "e, se fallisce, subisce danni da Freddo pari al tiro mostrato e, se Grande o più piccola, è spinta fino a 4,5 m.",
            "en": f"Emanation of {meters} m for 10 minutes: a visible creature in it makes a Constitution save (DC {data.get('dc')}) "
                  "and on a failure takes Cold damage equal to the roll shown and, if Large or smaller, is pushed up to 15 ft."}


WRATH_USE = OnUse(slot="bonus", spends=WILD_SHAPE, rolls=_wrath_dice, state=_wrath_state, message=_wrath_message,
                  effect=lambda c, _p: _only_emanation(c, WRATH))
WRATH_AGAIN = OnUse(
    slot="bonus", cost=0, rolls=_wrath_dice, available=lambda c: state_on(c, WRATH) or state_on(c, ALLY_WRATH),
    message=lambda _c, _p: {"it": "Una creatura visibile nell'Emanazione fa un TS Costituzione (CD nello stato): se fallisce subisce il tiro mostrato.",
                            "en": "A visible creature in the Emanation makes a Constitution save (DC in the state): on a failure it takes the roll shown."})
OCEANIC_GIFT_USE = OnUse(
    slot="bonus", spends=WILD_SHAPE, cost_by=lambda _c, p: 2 if p.get("target") == "both" else 1, rolls=_wrath_dice, state=_gift_state,
    message=_wrath_message, effect=lambda c, p: _only_emanation(c, WRATH if p.get("target") == "both" else ALLY_WRATH),
    choices=(UseChoice("target", {"it": "Attorno a", "en": "Around"}, lambda _c: list(_TARGETS), lambda k: _TARGETS[k]),))
STORMBORN = (Modifier("fly_speed", 1, when=lambda c: state_on(c, WRATH), source=f"feature:{CK}.stormborn"),
             *(Modifier(f"resistance:{t}", 1, when=lambda c: state_on(c, WRATH), source=f"feature:{CK}.stormborn")
               for t in ("cold", "lightning", "thunder")))


# ---------------------------------------------------------------------------
# Circolo delle Stelle
# ---------------------------------------------------------------------------

STARRY = "starry_form"
_CONSTELLATIONS = {"archer": {"it": "Arciere", "en": "Archer"}, "chalice": {"it": "Calice", "en": "Chalice"},
                   "dragon": {"it": "Drago", "en": "Dragon"}}
_CONSTELLATION_CHOICE = UseChoice("constellation", {"it": "Costellazione", "en": "Constellation"}, lambda _c: list(_CONSTELLATIONS),
                                  lambda k: _CONSTELLATIONS[k])


def _constellation(ctx: RuleContext) -> str | None:
    return _state_data(ctx, STARRY).get("constellation") if state_on(ctx, STARRY) else None


def _star_dice(ctx: RuleContext) -> str:
    return "2d8" if ctx.class_level >= 10 else "1d8"


def _starry_state(_ctx: RuleContext, params: dict) -> StateSpec:
    return StateSpec(STARRY, rounds=100, ends_on=("incapacitated", "manual"), data={
        "constellation": params["constellation"], "others": [f"{CK}.starry_form"]})


FREE_ARCHER = "free_archer"  # nel turno: il colpo dell'attivazione non costa un'altra azione bonus, e finisce col turno


def _starry_effect(ctx: RuleContext, params: dict) -> None:
    if params["constellation"] == "archer":
        ctx.char.turn_state = {**(ctx.char.turn_state or {}), FREE_ARCHER: True}


def _starry_message(_ctx: RuleContext, params: dict) -> dict[str, str]:
    archer = params.get("constellation") == "archer"
    return {"it": "Luce intensa per 3 m e fioca per altri 3 m." + (" Subito dopo puoi attaccare con Arciere, senza altra azione." if archer else ""),
            "en": "Bright light for 10 ft and dim for 10 ft more." + (" Right after you can attack with Archer, with no other action." if archer else "")}


def _archer_slot(ctx: RuleContext, _params: dict) -> str | None:
    return None if (ctx.char.turn_state or {}).get(FREE_ARCHER) else "bonus"


def _set_star_data(ctx: RuleContext, **changes: Any) -> None:
    ctx.char.active_states = [{**s, "data": {**(s.get("data") or {}), **changes}} if s.get("key") == STARRY else s
                              for s in ctx.char.active_states or []]


def _archer_used(ctx: RuleContext, _params: dict) -> None:
    ctx.char.turn_state = {k: v for k, v in (ctx.char.turn_state or {}).items() if k != FREE_ARCHER}


def _archer_message(ctx: RuleContext, _params: dict) -> dict[str, str]:
    return {"it": "Attacco a distanza con incantesimo entro 18 m: se il tiro per colpire riesce, danni Radiosi pari ai dadi mostrati "
                  f"più Saggezza ({_wisdom_mod(ctx):+d}); se manca, nessun danno.",
            "en": "Ranged spell attack within 60 ft: if the attack roll hits, Radiant damage equal to the dice shown "
                  f"plus Wisdom ({_wisdom_mod(ctx):+d}); on a miss, no damage."}


def _change_constellation(ctx: RuleContext, params: dict) -> None:
    """Cambiare costellazione non rinnova la durata né costa un uso (Costellazioni Scintillanti)."""
    _set_star_data(ctx, constellation=params["constellation"])


def _chalice_heal(ctx: RuleContext) -> int:
    return max(0, sum(random.randint(1, 8) for _ in range(int(_star_dice(ctx)[0]))) + _wisdom_mod(ctx))


def _chalice_effect(ctx: RuleContext, _inputs: dict) -> dict[str, str]:
    healed = _chalice_heal(ctx)
    return {"it": f"Calice: una creatura entro 9 m recupera {healed} PF (riferiscili al GM o al giocatore).",
            "en": f"Chalice: a creature within 30 ft regains {healed} HP (tell the GM or the player)."}


# Il Calice cura te (i PF li applica il server) oppure un'altra creatura (esito testuale: da qui nessun campo altrui è scrivibile)
CHALICE = RollOptionSpec(
    key=f"{CK}.chalice", phase="before", rolls=("spell_healing",), self_heal=lambda c, _i: _chalice_heal(c),
    available=lambda c: _constellation(c) == "chalice" and (c.casting_level or 0) >= 1,
    label={"it": "Calice: ti curi dei dadi del Calice più Saggezza", "en": "Chalice: you regain the Chalice dice plus Wisdom"})
CHALICE_OTHER = RollOptionSpec(
    key=f"{CK}.chalice_other", phase="before", rolls=("spell_healing",), effect=_chalice_effect,
    available=lambda c: _constellation(c) == "chalice" and (c.casting_level or 0) >= 1,
    label={"it": "Calice: un'altra creatura entro 9 m recupera i dadi del Calice più Saggezza",
           "en": "Chalice: another creature within 30 ft regains the Chalice dice plus Wisdom"})


def _dragon(ctx: RuleContext) -> bool:
    return _constellation(ctx) == "dragon"


def _dragon_roll(c: RuleContext) -> bool:
    return _dragon(c) and (c.roll == "concentration" or (c.roll in ("skill", "ability") and c.ability in ("intelligence", "wisdom")))


DRAGON_FLOOR = Modifier("min_d20", 10, when=_dragon_roll, source=f"feature:{CK}.dragon")
DRAGON_FLIGHT = Modifier("fly_speed_value", 20, when=lambda c: _dragon(c) and c.class_level >= 10, source=f"feature:{CK}.dragon")
FULL_OF_STARS = tuple(Modifier(f"resistance:{t}", 1, when=lambda c: state_on(c, STARRY), source=f"feature:{CK}.full_of_stars")
                      for t in ("bludgeoning", "piercing", "slashing"))
OMEN = "cosmic_omen"


def _omen_start(_ctx: RuleContext) -> StateSpec:
    """Dopo ogni riposo lungo si tira un dado: pari Prosperità, dispari Sventura."""
    roll = random.randint(1, 6)
    return StateSpec(OMEN, ends_on=("rest_long",), data={"roll": roll, "omen": "weal" if roll % 2 == 0 else "woe", "others": [f"{CK}.cosmic_omen"]})


def _omen_message(ctx: RuleContext, _params: dict) -> dict[str, str]:
    weal = _state_data(ctx, OMEN).get("omen") == "weal"
    return {"it": "Una creatura entro 9 m sta per fare un Tiro d20: " + ("somma il tiro mostrato al totale." if weal else "sottrai il tiro mostrato dal totale."),
            "en": "A creature within 30 ft is about to make a D20 Test: " + ("add the roll shown to the total." if weal else "subtract the roll shown from the total.")}


COSMIC_OMEN_USE = OnUse(slot="reaction", rolls="1d6", available=lambda c: state_on(c, OMEN), message=_omen_message)

CIRCLE_FEATURES: tuple = (
    # Circolo della Terra
    *_land_rows(),
    feature("lands_aid", CK, ED, 3, "Aiuto della Terra / Land's Aid (Circolo della Terra 3, pag. 85)", ("Aiuto della Terra", "Land's Aid"),
            ("Azione Magia, un uso di Forma Selvatica: sfera di 3 m, 2d6 necrotici (TS Costituzione) e una creatura cura 2d6; 3d6 al 10°, 4d6 al 14°.",
             "Magic action, one Wild Shape use: 10 ft sphere, 2d6 necrotic (Con save) and one creature heals 2d6; 3d6 at 10th, 4d6 at 14th."),
            "action", subclass="land", on_use=LANDS_AID_USE),
    feature("natural_recovery", CK, ED, 6, "Recupero Naturale / Natural Recovery (Circolo della Terra 6, pag. 85)",
            ("Recupero Naturale: slot", "Natural Recovery: slots"),
            ("Dopo un riposo breve recuperi slot spesi per un livello totale fino a metà del livello da druido (per eccesso), nessuno di 6° o più. Una volta per riposo lungo.",
             "After a short rest you regain spent slots totaling up to half your druid level (rounded up), none of 6th or higher. Once per long rest."),
            "special", subclass="land", uses=Uses(table={6: 1}), restoration="long_rest", passive=False),
    feature("natural_recovery_cast", CK, ED, 6, "Recupero Naturale / Natural Recovery (Circolo della Terra 6, pag. 85)",
            ("Recupero Naturale: lancio", "Natural Recovery: cast"),
            ("Lanci senza slot un incantesimo di circolo di 1° livello o più che hai preparato. Una volta per riposo lungo.",
             "You cast a prepared circle spell of level 1 or higher with no slot. Once per long rest."),
            "special", subclass="land", uses=Uses(table={6: 1}), restoration="long_rest", on_use=NATURAL_RECOVERY_CAST),
    feature("natures_ward", CK, ED, 10, "Interdizione della Natura / Nature's Ward (Circolo della Terra 10, pag. 85)",
            ("Interdizione della Natura", "Nature's Ward"),
            ("Non puoi essere Avvelenato; Resistenza al danno del terreno scelto: Fuoco, Freddo, Fulmine o Veleno.",
             "You cannot be Poisoned; Resistance to the chosen terrain's damage: Fire, Cold, Lightning or Poison."),
            subclass="land", condition_immunities=("poisoned",), modifiers=tuple(_ward_resistance(t) for t in TERRAINS)),
    feature("natures_sanctuary", CK, ED, 14, "Rifugio della Natura / Nature's Sanctuary (Circolo della Terra 14, pag. 86)",
            ("Rifugio della Natura", "Nature's Sanctuary"),
            ("Azione Magia, un uso di Forma Selvatica: cubo di alberi spettrali per 1 minuto, Copertura Parziale a te e agli alleati, che hanno anche la Resistenza di Interdizione.",
             "Magic action, one Wild Shape use: a cube of spectral trees for 1 minute, Half Cover for you and allies, who also get Ward resistance."),
            "action", subclass="land", on_use=SANCTUARY_USE,
            modifiers=(Modifier("ac", 2, when=lambda c: state_on(c, SANCTUARY), source=f"feature:{CK}.natures_sanctuary"),
                       Modifier("save", 2, when=lambda c: c.roll == "save" and c.ability == "dexterity" and state_on(c, SANCTUARY),
                                source=f"feature:{CK}.natures_sanctuary"))),
    feature("natures_sanctuary_move", CK, ED, 14, "Rifugio della Natura / Nature's Sanctuary (Circolo della Terra 14, pag. 86)",
            ("Spostare il Rifugio", "Move the Sanctuary"),
            ("Azione bonus, finché il cubo dura: lo sposti fino a 18 m su terreno entro 36 m da te.",
             "Bonus action while the cube lasts: move it up to 60 ft to ground within 120 ft of you."),
            "bonus_action", subclass="land", on_use=OnUse(
                slot="bonus", cost=0, available=lambda c: state_on(c, SANCTUARY),
                message=lambda _c, _p: {"it": "Sposti il cubo fino a 18 m, su terreno entro 36 m da te: lo segni sul tavolo.",
                                        "en": "You move the cube up to 60 ft, to ground within 120 ft of you: mark it on the table."})),

    # Circolo della Luna
    feature("circle_forms", CK, ED, 3, "Forme del Circolo / Circle Forms (Circolo della Luna 3, pag. 86)", ("Forme del Circolo", "Circle Forms"),
            ("In forma: GS massimo pari al livello diviso 3, CA 13 + Saggezza se superiore, PF temporanei pari a 3 volte il livello.",
             "In form: max CR your level divided by 3, AC 13 + Wisdom if higher, temporary HP equal to 3 times your level."),
            subclass="moon", passive=True),
    *_circle_spells("moon", "Incantesimi del Circolo della Luna / Circle of the Moon Spells (Circolo della Luna 3, pag. 86)",
                    ("Incantesimi del Circolo della Luna", "Circle of the Moon Spells"), MOON_SPELLS, cast_in_form=True),
    feature("improved_circle_forms", CK, ED, 6, "Forme del Circolo Migliorate / Improved Circle Forms (Circolo della Luna 6, pag. 87)",
            ("Forme del Circolo Migliorate", "Improved Circle Forms"),
            ("In forma ogni attacco infligge il tipo normale o Radioso, a scelta; sommi Saggezza ai TS su Costituzione.",
             "In form each attack deals its normal type or Radiant, your choice; add Wisdom to Constitution saves."),
            subclass="moon", modifiers=(CON_IN_FORM,), roll_options=(RADIANT_MOON,), passive=True),
    feature("moonlight_step", CK, ED, 10, "Passo Lunare / Moonlight Step (Circolo della Luna 10, pag. 87)", ("Passo Lunare", "Moonlight Step"),
            ("Azione bonus: ti teletrasporti entro 9 m con Vantaggio al prossimo tiro per colpire del turno. Usi pari a Saggezza (minimo 1).",
             "Bonus action: teleport up to 30 ft with Advantage on your next attack roll this turn. Uses equal Wisdom (minimum 1)."),
            "bonus_action", subclass="moon", uses=Uses(ability="wisdom", minimum=1), restoration="long_rest", modifiers=(STEP_ADVANTAGE,),
            on_use=OnUse(slot="bonus", state=StateSpec(MOONLIGHT_STATE, ends_on=("attack", "new_turn")), message=_step_message)),
    feature("moonlight_step_slot", CK, ED, 10, "Passo Lunare / Moonlight Step (Circolo della Luna 10, pag. 87)",
            ("Passo Lunare: uso da uno slot", "Moonlight Step: use from a slot"),
            ("Senza azione spendi uno slot di 2° livello o superiore e recuperi un uso di Passo Lunare.",
             "With no action you spend a level 2 or higher slot and regain a use of Moonlight Step."),
            subclass="moon",
            on_use=OnUse(cost=0, spends_slot="slot_level", check=_step_slot_check, effect=_step_slot,
                         choices=(UseChoice("slot_level", {"it": "Slot da spendere", "en": "Slot to spend"}, _slot_levels_from(2), _level_label),))),
    feature("lunar_form", CK, ED, 14, "Forma Lunare / Lunar Form (Circolo della Luna 14, pag. 87)", ("Forma Lunare", "Lunar Form"),
            ("Una volta per turno, un colpo della forma infligge 2d10 Radiosi in più; con Passo Lunare porti una creatura consenziente entro 3 m.",
             "Once per turn, a form hit deals 2d10 extra Radiant; with Moonlight Step you bring a willing creature within 10 ft."),
            subclass="moon", roll_options=(LUNAR_RADIANCE,), passive=True),

    # Circolo del Mare
    *_circle_spells("sea", "Incantesimi del Circolo del Mare / Circle of the Sea Spells (Circolo del Mare 3, pag. 87)",
                    ("Incantesimi del Circolo del Mare", "Circle of the Sea Spells"), SEA_SPELLS),
    feature("wrath_of_the_sea", CK, ED, 3, "Ira del Mare / Wrath of the Sea (Circolo del Mare 3, pag. 87)", ("Ira del Mare", "Wrath of the Sea"),
            ("Azione bonus, un uso di Forma Selvatica: Emanazione di 1,5 m (3 m dal 6°) per 10 minuti; una creatura fa TS Costituzione e subisce d6 Freddo pari a Saggezza.",
             "Bonus action, one Wild Shape use: a 5 ft Emanation (10 ft from 6th) for 10 minutes; a creature makes a Con save and takes Cold d6s equal to Wisdom."),
            "bonus_action", subclass="sea", on_use=WRATH_USE),
    feature("wrath_of_the_sea_again", CK, ED, 3, "Ira del Mare / Wrath of the Sea (Circolo del Mare 3, pag. 87)",
            ("Ira del Mare: ripetizione", "Wrath of the Sea: again"),
            ("Azione bonus, finché l'Emanazione dura: una creatura visibile nell'area fa di nuovo il TS e subisce il danno.",
             "Bonus action while the Emanation lasts: a visible creature in it makes the save again and takes the damage."),
            "bonus_action", subclass="sea", on_use=WRATH_AGAIN),
    feature("aquatic_affinity", CK, ED, 6, "Affinità Acquatica / Aquatic Affinity (Circolo del Mare 6, pag. 87)",
            ("Affinità Acquatica", "Aquatic Affinity"),
            ("L'Emanazione di Ira del Mare sale a 3 m; hai velocità di Nuotare pari alla Velocità.",
             "The Wrath of the Sea Emanation grows to 10 ft; you have a Swim Speed equal to your Speed."),
            subclass="sea", modifiers=(Modifier("swim_speed", 1, source=f"feature:{CK}.aquatic_affinity"),)),
    feature("stormborn", CK, ED, 10, "Nato dalla Tempesta / Stormborn (Circolo del Mare 10, pag. 87)", ("Nato dalla Tempesta", "Stormborn"),
            ("Con Ira del Mare attiva: velocità di Volare pari alla Velocità e Resistenza a Freddo, Fulmine e Tuono.",
             "While Wrath of the Sea is active: a Fly Speed equal to your Speed and Resistance to Cold, Lightning and Thunder."),
            subclass="sea", modifiers=STORMBORN),
    feature("oceanic_gift", CK, ED, 14, "Dono Oceanico / Oceanic Gift (Circolo del Mare 14, pag. 88)", ("Dono Oceanico", "Oceanic Gift"),
            ("Azione bonus: l'Emanazione si crea attorno a una creatura consenziente entro 18 m (1 uso) o attorno a lei e a te (2 usi).",
             "Bonus action: the Emanation forms around a willing creature within 60 ft (1 use) or around it and you (2 uses)."),
            "bonus_action", subclass="sea", on_use=OCEANIC_GIFT_USE),

    # Circolo delle Stelle
    feature("star_map", CK, ED, 3, "Mappa Stellare / Star Map (Circolo delle Stelle 3, pag. 88)", ("Mappa Stellare", "Star Map"),
            ("Focus da incantatore; Guida e Dardo Guida sempre preparati; Dardo Guida gratis tante volte quanto Saggezza (minimo 1) per riposo lungo.",
             "Spellcasting focus; Guidance and Guiding Bolt always prepared; Guiding Bolt free a number of times equal to Wisdom (minimum 1) per long rest."),
            "special", subclass="stars", uses=Uses(ability="wisdom", minimum=1), restoration="long_rest", granted_spells=("guidance", "guiding-bolt"),
            free_spell="guiding-bolt", passive=True),
    feature("starry_form", CK, ED, 3, "Forma Stellare / Starry Form (Circolo delle Stelle 3, pag. 88)", ("Forma Stellare", "Starry Form"),
            ("Azione bonus, un uso di Forma Selvatica: 10 minuti di luce e una costellazione (Arciere, Calice o Drago); non è una trasformazione.",
             "Bonus action, one Wild Shape use: 10 minutes of light and a constellation (Archer, Chalice or Dragon); not a transformation."),
            "bonus_action", subclass="stars",
            on_use=OnUse(slot="bonus", spends=WILD_SHAPE, state=_starry_state, choices=(_CONSTELLATION_CHOICE,), message=_starry_message,
                         effect=_starry_effect)),
    feature("archer", CK, ED, 3, "Arciere / Archer (Circolo delle Stelle 3, pag. 89)", ("Arciere", "Archer"),
            ("Con la Forma Stellare, azione bonus: attacco a distanza con incantesimo entro 18 m, 1d8 + Saggezza Radiosi (2d8 dal 10°).",
             "With Starry Form, bonus action: ranged spell attack within 60 ft, 1d8 + Wisdom Radiant (2d8 from 10th)."),
            "bonus_action", subclass="stars",
            on_use=OnUse(slot_by=_archer_slot, cost=0, rolls=_star_dice, spell_attack="wisdom", available=lambda c: _constellation(c) == "archer",
                         effect=_archer_used, message=_archer_message)),
    feature("chalice", CK, ED, 3, "Calice / Chalice (Circolo delle Stelle 3, pag. 89)", ("Calice", "Chalice"),
            ("Con la Forma Stellare, se curi con uno slot: tu o una creatura entro 9 m recuperate 1d8 + Saggezza PF (2d8 dal 10°).",
             "With Starry Form, when you heal with a slot: you or a creature within 30 ft regains 1d8 + Wisdom HP (2d8 from 10th)."),
            subclass="stars", roll_options=(CHALICE, CHALICE_OTHER), passive=True),
    feature("dragon", CK, ED, 3, "Drago / Dragon (Circolo delle Stelle 3, pag. 89)", ("Drago", "Dragon"),
            ("Con la Forma Stellare, un d20 di 9 o meno vale 10 nelle prove di Intelligenza e Saggezza e nei TS di concentrazione; volo 6 m dal 10°.",
             "With Starry Form, a d20 of 9 or lower counts as 10 on Intelligence and Wisdom checks and concentration saves; fly 20 ft from 10th."),
            subclass="stars", modifiers=(DRAGON_FLOOR, DRAGON_FLIGHT), passive=True),
    feature("cosmic_omen", CK, ED, 6, "Presagio Cosmico / Cosmic Omen (Circolo delle Stelle 6, pag. 89)", ("Presagio Cosmico", "Cosmic Omen"),
            ("Dopo un riposo lungo: Prosperità (pari) o Sventura (dispari). Reazione, usi pari a Saggezza: 1d6 da sommare o sottrarre al Tiro d20 di una creatura entro 9 m.",
             "After a long rest: Weal (even) or Woe (odd). Reaction, uses equal Wisdom: a d6 added to or subtracted from a creature's D20 Test within 30 ft."),
            "reaction", subclass="stars", uses=Uses(ability="wisdom", minimum=1), restoration="long_rest", long_rest_state=_omen_start,
            on_use=COSMIC_OMEN_USE),
    feature("twinkling_constellations", CK, ED, 10, "Costellazioni Scintillanti / Twinkling Constellations (Circolo delle Stelle 10, pag. 89)",
            ("Costellazioni Scintillanti", "Twinkling Constellations"),
            ("Arciere e Calice salgono a 2d8, Drago vola; a inizio turno in Forma Stellare cambi costellazione.",
             "Archer and Chalice rise to 2d8, Dragon flies; at the start of your turn in Starry Form you change constellation."),
            subclass="stars", on_use=OnUse(cost=0, once_per_turn=True, available=lambda c: state_on(c, STARRY), effect=_change_constellation,
                                           message=lambda _c, p: {lg: (f"La Forma Stellare passa alla costellazione {_CONSTELLATIONS[p['constellation']][lg]}, senza spendere usi né rinnovare la durata." if lg == "it"
                                                                      else f"Starry Form switches to the {_CONSTELLATIONS[p['constellation']][lg]} constellation, with no use spent and no new duration.")
                                                                  for lg in ("it", "en")},
                                           choices=(_CONSTELLATION_CHOICE,))),
    feature("full_of_stars", CK, ED, 14, "Pieno di Stelle / Full of Stars (Circolo delle Stelle 14, pag. 89)", ("Pieno di Stelle", "Full of Stars"),
            ("Con la Forma Stellare: Resistenza ai danni Contundenti, Perforanti e Taglienti.",
             "With Starry Form: Resistance to Bludgeoning, Piercing and Slashing damage."),
            subclass="stars", modifiers=FULL_OF_STARS, passive=True),
)

CLASS_FEATURES = (
    feature("core_traits", CK, ED, 1, "Tratti Base del Druido / Core Druid Traits (Druido 1, pag. 79)", ("Tratti Base del Druido", "Core Druid Traits"),
            ("Dado Vita d8, TS Intelligenza e Saggezza, 2 abilità, armi semplici, Kit da Erborista, armature leggere e scudi.",
             "Hit die d8, Intelligence and Wisdom saves, 2 skills, simple weapons, Herbalism Kit, light armor and shields."),
            # PF, TS, armi, armature, strumenti e abilità: api/routers/classes.py e core/rules/proficiencies.py; equipaggiamento A/B no (R32)
            no_row=True, covered_by="lavori-successivi"),
    feature("spellcasting", CK, ED, 1, "Incantesimi / Spellcasting (Druido 1, pag. 79)", ("Incantesimi", "Spellcasting"),
            ("Saggezza; trucchetti 2/3/4 e incantesimi preparati da 4 a 22; slot da tabella; focus druidico.",
             "Wisdom; cantrips 2/3/4 and prepared spells from 4 to 22; slots by table; a druidic focus."),
            no_row=True, covered_by="core/rules/spellcasting.py (prepared_limit, known_limits, slots_for); "
                                    "test_cantrips_and_prepared_spells_follow_the_2024_table"),
    feature("druidic", CK, ED, 1, "Druidico / Druidic (Druido 1, pag. 80)", ("Druidico", "Druidic"),
            ("Conosci il Druidico; Parlare con gli Animali è sempre preparato e non conta nel limite.",
             "You know Druidic; Speak with Animals is always prepared and does not count against the limit."),
            granted_spells=("speak-with-animals",)),
    feature("primal_order", CK, ED, 1, "Ordine Primordiale / Primal Order (Druido 1, pag. 80)", ("Ordine Primordiale", "Primal Order"),
            ("Al 1° livello si sceglie Mago o Custode.", "At level 1 you choose Magician or Warden."),
            choices=(ChoiceSpec(group=ORDER, levels={1: 1}, options=lambda _c: ["magician", "warden"]),)),
    feature("primal_order_magician", CK, ED, 1, "Mago / Magician (Druido 1, pag. 80)", ("Mago", "Magician"),
            ("Un trucchetto da druido in più, fuori dal limite; alle prove di Arcano e Natura somma Saggezza (minimo +1).",
             "One extra druid cantrip, outside the limit; add Wisdom (minimum +1) to Arcana and Nature checks."),
            option_group=ORDER, option_key="magician", modifiers=(MAGICIAN_BONUS,),
            choices=(ChoiceSpec(group="magician_cantrip", levels={1: 1}, options=_no_options, spell_pick="extra", spell_level=0,
                                spell_list="druid"),)),
    feature("primal_order_warden", CK, ED, 1, "Custode / Warden (Druido 1, pag. 80)", ("Custode", "Warden"),
            ("Competenza nelle armi da guerra e addestramento con le armature medie.",
             "Proficiency with martial weapons and training with medium armor."),
            option_group=ORDER, option_key="warden", proficiency_grants={"armor": ("medium",), "weapons": ("martial",)}),
    feature("wild_shape", CK, ED, 2, "Forma Selvatica / Wild Shape (Druido 2, pag. 80)", ("Forma Selvatica", "Wild Shape"),
            ("Azione bonus: assumi una Bestia conosciuta. Usi 2, 3 dal 6°, 4 dal 17°; un riposo breve ne rende 1, uno lungo tutti.",
             "Bonus action: take a known Beast shape. Uses 2, 3 from 6th, 4 from 17th; a short rest returns 1, a long rest all."),
            "bonus_action", uses=Uses(table={2: 2, 6: 3, 17: 4}), restoration="long_rest", short_rest_recovers=1),
    feature("wild_shape_rules", CK, ED, 2, "Regole della Forma Selvatica / Rules While Shape-Shifted (Druido 2, pag. 81)",
            ("Regole della Forma Selvatica", "Rules While Shape-Shifted"),
            ("PF temporanei pari al livello da druido; PF, Dadi Vita, Int, Sag e Car restano tuoi; vale il modificatore più alto fra druido e Bestia.",
             "Temporary HP equal to your druid level; HP, Hit Dice, Int, Wis and Cha stay yours; the higher modifier of druid and Beast applies."),
            no_row=True, covered_by="api/services/wild_shape.py (start_form), core/game/stats.py e core/rules/forms.py; "
                                    "test_wild_shape_is_a_bonus_action_gives_temporary_hp_equal_to_the_level_and_keeps_the_real_hp"),
    feature("wild_companion", CK, ED, 2, "Compagno Selvatico / Wild Companion (Druido 2, pag. 81)", ("Compagno Selvatico", "Wild Companion"),
            ("Azione Magia: lanci Trova Famiglio senza materiali, pagando uno slot o un uso di Forma Selvatica. Il famiglio è Fatato e sparisce al riposo lungo.",
             "Magic action: cast Find Familiar with no Material components, paying a slot or a Wild Shape use. The familiar is a Fey and vanishes on a long rest."),
            "action", on_use=WILD_COMPANION_USE),
    feature("druid_subclass", CK, ED, 3, "Sottoclasse del Druido / Druid Subclass (Druido 3, pag. 81)",
            ("Sottoclasse del Druido", "Druid Subclass"),
            ("Al 3° livello si sceglie il Circolo della Terra, della Luna, del Mare o delle Stelle.",
             "At level 3 you choose the Circle of the Land, Moon, Sea or Stars."),
            no_row=True, covered_by="core/rules/subclasses.py (match_subclass) e il campo sottoclasse della classe"),
    feature("ability_score_improvement", CK, ED, 4,
            "Aumento dei Punteggi di Caratteristica / Ability Score Improvement (Druido 4, pag. 81)",
            ("Aumento dei Punteggi di Caratteristica", "Ability Score Improvement"),
            ("Ai livelli 4, 8, 12 e 16 il talento Aumento dei Punteggi o un altro talento di cui hai i requisiti.",
             "At levels 4, 8, 12 and 16 the Ability Score Improvement feat or another feat you qualify for."),
            no_row=True, covered_by="core/rules/level_choices.py (scelta asi); test_asi_choice_is_pending_at_each_asi_level_and_the_19th_is_an_epic_boon"),
    feature("wild_resurgence", CK, ED, 5, "Rigenerazione Selvatica / Wild Resurgence (Druido 5, pag. 81)",
            ("Rigenerazione Selvatica: slot in cambio di un uso", "Wild Resurgence: slot for a use"),
            ("Senza azione, una volta per turno, a zero usi di Forma Selvatica spendi uno slot per riavere un uso.",
             "No action, once per turn, with no Wild Shape uses left you spend a slot to regain one use."),
            on_use=RESURGENCE_USE),
    feature("wild_resurgence_slot", CK, ED, 5, "Rigenerazione Selvatica / Wild Resurgence (Druido 5, pag. 81)",
            ("Rigenerazione Selvatica: uso in cambio di uno slot", "Wild Resurgence: use for a slot"),
            ("Senza azione spendi un uso di Forma Selvatica e recuperi uno slot di 1° livello; poi serve un riposo lungo.",
             "No action, you spend a Wild Shape use and regain a level 1 slot; then it takes a long rest."),
            on_use=RESURGENCE_SLOT_USE),
    feature("elemental_fury", CK, ED, 7, "Furia Elementale / Elemental Fury (Druido 7, pag. 81)", ("Furia Elementale", "Elemental Fury"),
            ("Al 7° livello si sceglie Incantesimi Potenti o Colpo Primordiale.", "At level 7 you choose Potent Spellcasting or Primal Strike."),
            choices=(ChoiceSpec(group=FURY, levels={7: 1}, options=lambda _c: ["potent_spellcasting", "primal_strike"]),)),
    feature("elemental_fury_potent", CK, ED, 7, "Incantesimi Potenti / Potent Spellcasting (Druido 7, pag. 81)",
            ("Incantesimi Potenti", "Potent Spellcasting"),
            ("Ai danni di ogni tuo trucchetto da druido si somma il modificatore di Saggezza.",
             "Add your Wisdom modifier to the damage of every druid cantrip you cast."),
            option_group=FURY, option_key="potent_spellcasting", modifiers=(POTENT,)),
    feature("elemental_fury_strike", CK, ED, 7, "Colpo Primordiale / Primal Strike (Druido 7, pag. 81)",
            ("Colpo Primordiale", "Primal Strike"),
            ("Una volta per turno, con un colpo d'arma o della forma Bestia: 1d8 (2d8 dal 15°) di Freddo, Fuoco, Fulmine o Tuono in più.",
             "Once per turn, on a weapon or Beast-form hit: 1d8 (2d8 from level 15) extra Cold, Fire, Lightning or Thunder damage."),
            option_group=FURY, option_key="primal_strike", roll_options=(*(_primal_strike(k) for k in _ENERGIES), *(_primal_strike_form(k) for k in _ENERGIES))),
    feature("improved_elemental_fury_potent", CK, ED, 15, "Furia Elementale Migliorata / Improved Elemental Fury (Druido 15, pag. 81)",
            ("Furia Elementale Migliorata: Incantesimi Potenti", "Improved Elemental Fury: Potent Spellcasting"),
            ("La gittata dei tuoi trucchetti da druido di 3 m o più aumenta di 90 m.",
             "The range of your druid cantrips of 10 feet or more increases by 300 feet."),
            option_group=FURY, option_key="potent_spellcasting", cantrip_range_bonus=90, passive=True),
    feature("improved_elemental_fury_strike", CK, ED, 15, "Furia Elementale Migliorata / Improved Elemental Fury (Druido 15, pag. 81)",
            ("Furia Elementale Migliorata: Colpo Primordiale", "Improved Elemental Fury: Primal Strike"),
            ("Colpo Primordiale infligge 2d8 in più.", "Primal Strike deals 2d8 extra."),
            option_group=FURY, option_key="primal_strike", passive=True),
    feature("beast_spells", CK, ED, 18, "Incantesimi Bestiali / Beast Spells (Druido 18, pag. 81)",
            ("Incantesimi Bestiali", "Beast Spells"),
            ("In Forma Selvatica lanci incantesimi, salvo quelli con un materiale che costa o si consuma (l'app te lo chiede).",
             "While in Wild Shape you cast spells, except those with a Material component that costs or is consumed (the app asks)."),
            cast_in_form=True, ignores_components=True),
    feature("epic_boon", CK, ED, 19, "Dono Epico / Epic Boon (Druido 19, pag. 81)", ("Dono Epico", "Epic Boon"),
            ("Al 19° livello un talento Dono Epico o un altro talento di cui hai i requisiti.",
             "At level 19 an Epic Boon feat or another feat you qualify for."),
            no_row=True, covered_by="core/rules/level_choices.py (reconcile_choices, scelta epic_boon)"),
    feature("archdruid", CK, ED, 20, "Arcidruido / Archdruid (Druido 20, pag. 82)", ("Arcidruido", "Archdruid"),
            ("Forma Selvatica Sempreverde: tirando l'Iniziativa senza usi ne recuperi uno. Longevità: invecchi di 1 anno ogni 10.",
             "Evergreen Wild Shape: rolling Initiative with no uses left gives one back. Longevity: you age 1 year per 10."),
            roll_options=(EVERGREEN,), passive=True),
    feature("nature_magician", CK, ED, 20, "Arcidruido / Archdruid (Druido 20, pag. 82)", ("Mago della Natura", "Nature Magician"),
            ("Senza azione converti usi inutilizzati di Forma Selvatica in un solo slot (2 livelli per uso); una volta fino al riposo lungo.",
             "No action, you convert unexpended Wild Shape uses into one spell slot (2 levels per use); once until a long rest."),
            on_use=NATURE_MAGICIAN_USE),
    feature("multiclassing", CK, ED, 1, "Multiclasse: Druido / Multiclassing: Druid (Regole multiclasse, pag. 44)",
            ("Multiclasse: Druido", "Multiclassing: Druid"),
            ("Requisito Saggezza 13. Da multiclasse: armature leggere e scudi; i livelli contano per intero negli slot.",
             "Requires Wisdom 13. As a multiclass: light armor and shields; levels count in full for slots."),
            no_row=True, covered_by="core/rules/proficiencies.py (as_multiclass) e webapp/src/data/multiclassPrereqs.ts (D2)"),
)

FEATURES = CIRCLE_FEATURES + CLASS_FEATURES

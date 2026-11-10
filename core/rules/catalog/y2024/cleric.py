"""Chierico 2024: base della classe (Task 33, parte A) e sottoclassi Vita, Luce, Inganno, Guerra (parte B).

Valori dalla scheda ``docs/superpowers/rules/2024/classes/cleric.md``; i testi sono nostri, mai quelli del manuale.
Incanalare Divinità è la riserva condivisa ``channel_divinity`` (stessa chiave del 2014 e del Paladino): ogni effetto,
anche quelli di sottoclasse, la spende con ``OnUse.spends=POOL``.

Parte B: i privilegi di sottoclasse stanno in ``DOMAIN_FEATURES`` (``subclass="life"|"light"|"trickery"|"war"``), spendono
``POOL`` e usano ``spell_dc``; Guarigione Suprema agisce anche su Scintilla Divina (``SPARK_USE.maximize_if``, senza costo).
"""
from __future__ import annotations

import random
import uuid
from dataclasses import replace
from typing import Any

from core.rules.catalog._common import feature, state_on
from core.rules.catalog.y2014.cleric import (
    BLESSED_HEALER, DUPLICITY_ADVANTAGE, GUIDED_STRIKE, INVOKE_DUPLICITY, POOL, WAR_PRIEST, WARDING_FLARE, _divine_strike,
    _healing_roll, _no_options, _own_cantrip, _potent, _wisdom_mod, spell_dc,
)
from core.rules.states import STOLEN_SPELL, begin_state
from core.rules.types import (
    TRICKSTER_BLESSING, ChoiceSpec, Cost, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, TargetEffect, UseChoice, Uses,
    UseText, UseToggle,
)

ED, CK = "2024", "cleric"
TURN_UNDEAD = f"{CK}.turn_undead"
DIVINE_SPARK = f"{CK}.divine_spark"
DIVINE_INTERVENTION = f"{CK}.divine_intervention"
WISH_LOCK = "greater_divine_intervention"
ORDER, STRIKES = "divine_order", "blessed_strikes"
NAME_MAX = 80
_KNOWLEDGE = ("arcana", "religion")
_SPARK_MODES = {
    "heal": {"it": "Cura PF a un'altra creatura", "en": "Heal another creature"},
    "damage_necrotic": {"it": "Danni necrotici (TS Costituzione)", "en": "Necrotic damage (Constitution save)"},
    "damage_radiant": {"it": "Danni radiosi (TS Costituzione)", "en": "Radiant damage (Constitution save)"},
}


def _chosen(ctx: RuleContext, group: str, option: str) -> bool:
    return option in ((getattr(ctx.class_row, "options", None) or {}).get(group) or [])


# ---------------------------------------------------------------------------
# Ordine Divino: Taumaturgo
# ---------------------------------------------------------------------------

def _thaumaturge_bonus(ctx: RuleContext) -> int:
    return max(1, _wisdom_mod(ctx))


THAUMATURGE_BONUS = Modifier("skill", _thaumaturge_bonus, when=lambda c: c.roll == "skill" and c.skill in _KNOWLEDGE,
                             source=f"feature:{CK}.divine_order_thaumaturge")


# ---------------------------------------------------------------------------
# Incanalare Divinità: Scintilla Divina
# ---------------------------------------------------------------------------

def _spark_dice(ctx: RuleContext) -> str:
    level = ctx.class_level
    return f"{1 if level < 7 else 2 if level < 13 else 3 if level < 18 else 4}d8"


def _spark_total(ctx: RuleContext, rolled: int) -> int:
    return max(0, rolled + _wisdom_mod(ctx))


def _spark_state(ctx: RuleContext, params: dict) -> StateSpec | None:
    """La cura va al bersaglio dal server (R42) o si riferisce al GM; il danno è un TS Costituzione che segna il GM (D1)."""
    mode = str(params.get("mode"))
    if mode == "heal":
        return None
    return StateSpec("divine_spark", rounds=1, ends_on=("manual", "new_turn"), data={
        "dc": spell_dc(ctx), "save": "constitution", "damage_type": mode.removeprefix("damage_"),
        "damage": _spark_total(ctx, int(params.get("rolled") or 0)), "others": [DIVINE_SPARK]})


def _spark_message(ctx: RuleContext, params: dict) -> dict[str, str]:
    if params.get("mode") == "heal":
        return {"it": "Il bersaglio recupera i PF indicati: se non siede alla serata, riferiscili al GM.",
                "en": "The target regains the HP shown: if it does not sit at the evening, tell the GM."}
    state = next((s for s in ctx.char.active_states or [] if s.get("key") == "divine_spark"), None)
    data = (state or {}).get("data") or {}
    kind_it, kind_en = ("necrotici", "necrotic") if data.get("damage_type") == "necrotic" else ("radiosi", "radiant")
    return {"it": f"Il bersaglio fa un TS Costituzione (CD {data.get('dc')}): se fallisce subisce {data.get('damage')} danni {kind_it}, "
                  "la metà se lo supera.",
            "en": f"The target makes a Constitution save (DC {data.get('dc')}): on a failure it takes {data.get('damage')} {kind_en} "
                  "damage, half on a success."}


def _supreme_healing(ctx: RuleContext, params: dict) -> bool:
    """Guarigione Suprema (Dominio della Vita, 17°): i dadi di cura della Scintilla Divina valgono il massimo."""
    return params.get("mode") == "heal" and ctx.class_level >= 17 and getattr(ctx.class_row, "subclass_key", None) == "life"


SPARK_USE = OnUse(
    slot="action", spends=POOL, maximize_if=_supreme_healing, rolls=_spark_dice, heal=_spark_total, heal_when=lambda _c, _p: False,
    heal_ally_when=lambda _c, p: p.get("mode") == "heal", ally_modes=("heal",), state=_spark_state, message=_spark_message,
    choices=(UseChoice("mode", {"it": "Effetto", "en": "Effect"}, lambda _c: list(_SPARK_MODES), lambda k: _SPARK_MODES[k]),))


# ---------------------------------------------------------------------------
# Incanalare Divinità: Scacciare Non Morti e Bruciare Non Morti
# ---------------------------------------------------------------------------

def _sear_dice(ctx: RuleContext) -> str | None:
    """Dal 5° livello Scacciare Non Morti tira anche N d8 radiosi (N = Saggezza, minimo 1) per i non morti che falliscono."""
    return f"{max(1, _wisdom_mod(ctx))}d8" if ctx.class_level >= 5 else None


def _turn_undead_state(ctx: RuleContext, params: dict) -> StateSpec:
    data: dict[str, Any] = {"dc": spell_dc(ctx), "save": "wisdom", "others": [TURN_UNDEAD]}
    if ctx.class_level >= 5:
        data.update(damage=int(params.get("rolled") or 0), damage_type="radiant")
    return StateSpec("turn_undead", rounds=10, ends_on=("incapacitated", "manual"), data=data)


def _turn_undead_effect(ctx: RuleContext, _params: dict) -> TargetEffect:
    return TargetEffect(condition="frightened", also=("incapacitated",), save_ability="wisdom", save_dc=spell_dc(ctx), rounds=10,
                        note="turn_undead")


def _turn_undead_message(ctx: RuleContext, _params: dict) -> dict[str, str]:
    dc = spell_dc(ctx)
    if ctx.class_level < 5:
        return {"it": f"Ogni non morto entro 9 m fa un TS Saggezza (CD {dc}): se fallisce è Spaventato e Incapacitato per 1 minuto.",
                "en": f"Each undead within 30 ft makes a Wisdom save (DC {dc}): on a failure it is Frightened and Incapacitated for 1 minute."}
    return {"it": f"Ogni non morto entro 9 m fa un TS Saggezza (CD {dc}): se fallisce è Spaventato e Incapacitato per 1 minuto e "
                  "subisce danni radiosi pari al tiro mostrato (non pongono fine all'effetto).",
            "en": f"Each undead within 30 ft makes a Wisdom save (DC {dc}): on a failure it is Frightened and Incapacitated for 1 minute "
                  "and takes radiant damage equal to the roll shown (it does not end the effect)."}


TURN_UNDEAD_USE = OnUse(slot="action", spends=POOL, rolls=_sear_dice, state=_turn_undead_state, target_effect=_turn_undead_effect,
                        message=_turn_undead_message)


# ---------------------------------------------------------------------------
# Colpi Benedetti
# ---------------------------------------------------------------------------

POTENT_TEMP_HP = RollOptionSpec(
    key=f"{CK}.improved_potent_spellcasting", phase="before", rolls=("spell_damage",),
    label={"it": "Incantesimi Potenti: dai PF temporanei a te o a una creatura entro 18 m",
           "en": "Potent Spellcasting: give temporary HP to yourself or a creature within 60 ft"},
    available=lambda c: _chosen(c, STRIKES, "potent_spellcasting") and _own_cantrip(c) and _wisdom_mod(c) >= 1,
    temp_hp_gift=lambda c, _i: 2 * _wisdom_mod(c),
    effect=lambda c, i: ({"it": f"{2 * _wisdom_mod(c)} PF temporanei a una creatura entro 18 m.",
                          "en": f"{2 * _wisdom_mod(c)} temporary HP to a creature within 60 ft."} if i.get("target_character_id") is not None else
                         {"it": f"Dai {2 * _wisdom_mod(c)} PF temporanei a te o a una creatura entro 18 m.",
                          "en": f"Give {2 * _wisdom_mod(c)} temporary HP to yourself or a creature within 60 ft."}))


# ---------------------------------------------------------------------------
# Intervento Divino e Intervento Divino Superiore
# ---------------------------------------------------------------------------

def _di_levels(_ctx: RuleContext) -> list[str]:
    return [str(n) for n in range(1, 6)]


def _di_check(ctx: RuleContext, params: dict) -> tuple[int, str] | None:
    if params.get("wish"):
        return None if ctx.class_level >= 20 else (422, "invalid_choice")
    return None if params.get("spell_level") is not None else (422, "invalid_choice")


def _di_effect(ctx: RuleContext, params: dict) -> None:
    """L'incantesimo scelto sta sulla scheda finché lo stato che autorizza il lancio gratuito dura; il lancio lo chiude
    (R43). Desiderio blocca il privilegio per 2d4 riposi lunghi (tiro e conteggio nello stato)."""
    from core.db.models import Spell  # import locale: i modelli non servono al resto del catalogo
    wish = bool(params.get("wish"))
    tag = f"{STOLEN_SPELL}{uuid.uuid4().hex[:12]}"
    name = "Desiderio / Wish" if wish else str(params["spell"]).strip()
    ctx.char.spells.append(Spell(
        character_id=ctx.char.id, name=name, level=9 if wish else int(params["spell_level"]), srd_index=tag,
        class_id=ctx.class_row.id, is_prepared=True, always_prepared=True))
    begin_state(ctx.char, StateSpec("divine_intervention_free", ends_on=("manual", "rest_long"),
                                    data={"stolen_spell": tag, "free_cast": tag}), DIVINE_INTERVENTION, "Intervento Divino")
    if wish:
        dice = [random.randint(1, 4), random.randint(1, 4)]
        begin_state(ctx.char, StateSpec(WISH_LOCK, ends_on=("manual",), data={"roll": dice, "rests_left": sum(dice), "locked": True}),
                    DIVINE_INTERVENTION, "Intervento Divino")


def _di_message(_ctx: RuleContext, params: dict) -> dict[str, str]:
    if params.get("wish"):
        return {"it": "Lanci Desiderio senza slot né componenti materiali. Intervento Divino resta bloccato per 2d4 riposi lunghi: "
                      "il tiro e i riposi mancanti sono nello stato.",
                "en": "You cast Wish with no slot or material components. Divine Intervention stays blocked for 2d4 long rests: "
                      "the roll and the rests left are in the state."}
    return {"it": "Lanci l'incantesimo senza slot né componenti materiali (azione Magia, livello 5 o inferiore, nessuna Reazione): "
                  "è sulla scheda finché non lo lanci.",
            "en": "You cast the spell with no slot or material components (Magic action, level 5 or lower, no Reaction): "
                  "it stays on the sheet until you cast it."}


DIVINE_INTERVENTION_USE = OnUse(
    available=lambda c: not state_on(c, WISH_LOCK), check=_di_check, effect=_di_effect, message=_di_message,
    toggles=(UseToggle("wish", {"it": "Desiderio (dal 20° livello): blocca il privilegio per 2d4 riposi lunghi",
                                "en": "Wish (from level 20): blocks the feature for 2d4 long rests"},
                       available=lambda c: c.class_level >= 20),),
    choices=(UseChoice("spell_level", {"it": "Livello dell'incantesimo", "en": "Spell level"}, _di_levels,
                       lambda k: {"it": f"{k}° livello", "en": f"Level {k}"}, optional=True),),
    texts=(UseText("spell", {"it": "Incantesimo da chierico (livello 5 o inferiore, senza Reazione)",
                             "en": "Cleric spell (level 5 or lower, no Reaction)"}, max_len=NAME_MAX, optional=True,
                   required=lambda params: not params.get("wish")),))


def _wish_countdown(ctx: RuleContext) -> None:
    """Ogni riposo lungo scala di uno i riposi mancanti dopo Desiderio; a zero lo stato (e il blocco) finisce."""
    states, changed = [], False
    for s in ctx.char.active_states or []:
        if s.get("key") == WISH_LOCK:
            left = int((s.get("data") or {}).get("rests_left") or 0) - 1
            changed = True
            if left > 0:
                states.append({**s, "data": {**(s.get("data") or {}), "rests_left": left}})
            continue
        states.append(s)
    if changed:
        ctx.char.active_states = states


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Domini (parte B)
# ---------------------------------------------------------------------------

DOMAIN_SPELLS = {
    "life": (("aid", "bless", "cure-wounds", "lesser-restoration"), ("mass-healing-word", "revivify"), ("aura-of-life", "death-ward"),
             ("greater-restoration", "mass-cure-wounds")),
    "light": (("burning-hands", "faerie-fire", "scorching-ray", "see-invisibility"), ("daylight", "fireball"),
              ("arcane-eye", "wall-of-fire"), ("flame-strike", "scrying")),
    "trickery": (("charm-person", "disguise-self", "invisibility", "pass-without-trace"), ("hypnotic-pattern", "nondetection"),
                 ("confusion", "dimension-door"), ("dominate-person", "modify-memory")),
    "war": (("guiding-bolt", "magic-weapon", "shield-of-faith", "spiritual-weapon"), ("crusaders-mantle", "spirit-guardians"),
            ("fire-shield", "freedom-of-movement"), ("hold-monster", "steel-wind-strike")),
}


def _domain_spells(domain: str, title: str, name: tuple[str, str]) -> list:
    """Quattro incantesimi al 3° livello, poi due ai livelli 5, 7 e 9: sempre preparati, fuori dal limite."""
    tiers = DOMAIN_SPELLS[domain]
    out = [feature(f"{domain}_spells", CK, ED, 3, title, name,
                   ("Incantesimi di dominio sempre preparati, quattro al 3° livello e due al 5°, 7° e 9°; non contano nel limite.",
                    "Domain spells are always prepared, four at level 3 and two at 5, 7 and 9; they do not count against the limit."),
                   subclass=domain, granted_spells=tiers[0])]
    for tier, spells in zip((5, 7, 9), tiers[1:]):
        out.append(feature(f"{domain}_spells_{tier}", CK, ED, tier, title, name,
                           (f"Incantesimi di dominio del {tier}° livello.", f"Domain spells gained at level {tier}."),
                           subclass=domain, granted_spells=spells, no_row=True,
                           covered_by=f"{CK}.{domain}_spells (stessa voce della mappatura) e test_domain_spells_arrive_at_3_5_7_and_9"))
    return out


# Luce: Fulgore dell'Alba, Lampo di Interdizione, Corona di Luce
def _radiance_state(ctx: RuleContext, params: dict) -> StateSpec:
    return StateSpec("radiance_of_the_dawn", rounds=1, ends_on=("manual", "new_turn"), data={
        "dc": spell_dc(ctx), "save": "constitution", "damage_type": "radiant", "damage": int(params.get("rolled") or 0) + ctx.class_level,
        "others": [f"{CK}.radiance_of_the_dawn"]})


def _radiance_message(ctx: RuleContext, _params: dict) -> dict[str, str]:
    data = next((s.get("data") or {} for s in ctx.char.active_states or [] if s.get("key") == "radiance_of_the_dawn"), {})
    return {"it": f"Ogni creatura a tua scelta entro 9 m fa un TS Costituzione (CD {data.get('dc')}): se fallisce subisce "
                  f"{data.get('damage')} danni radiosi, la metà se lo supera. L'oscurità magica nell'area svanisce.",
            "en": f"Each creature of your choice within 30 ft makes a Constitution save (DC {data.get('dc')}): on a failure it takes "
                  f"{data.get('damage')} radiant damage, half on a success. Magical darkness in the area is dispelled."}


def _flare_state(ctx: RuleContext, _params: dict) -> StateSpec:
    others = [WARDING_FLARE] + ([f"{CK}.improved_warding_flare"] if ctx.class_level >= 6 else [])
    return StateSpec("warding_flare", rounds=1, ends_on=("manual", "new_turn"), data={"others": others})


def _flare_dice(ctx: RuleContext) -> str | None:
    return "2d6" if ctx.class_level >= 6 else None


def _flare_temp_hp(ctx: RuleContext, rolled: int) -> int:
    return max(0, rolled + _wisdom_mod(ctx)) if ctx.class_level >= 6 else 0


def _flare_message(ctx: RuleContext, _params: dict) -> dict[str, str]:
    base = {"it": "Il tiro per colpire della creatura che vedi entro 9 m ha svantaggio, prima dell'esito.",
            "en": "The attack roll of the creature you can see within 30 ft has disadvantage, before the result."}
    if ctx.class_level < 6:
        return base
    return {"it": base["it"] + " Puoi dare al bersaglio dell'attacco i PF temporanei mostrati.",
            "en": base["en"] + " You can give the attack's target the temporary HP shown."}


CORONA_USE = OnUse(slot="action", state=StateSpec("corona_of_light", rounds=10, ends_on=("manual",),
                                                  data={"others": [f"{CK}.corona_of_light"]}))


# Inganno: Benedizione dell'Ingannatore, Invocare Duplicato
def _trickster_state(_ctx: RuleContext, params: dict) -> StateSpec:
    """Vantaggio a Furtività fino al riposo lungo: su di te con ``self``, su un alleato della serata con il bersaglio; senza
    nessuno dei due (una creatura del GM) resta una nota per il gruppo (D1)."""
    ends = ("rest_long", "manual")
    if params.get("self") or params.get("target_character_id") is not None:
        return StateSpec(TRICKSTER_BLESSING, ends_on=ends)
    return StateSpec("trickster_blessing_note", ends_on=ends, data={"others": [f"{CK}.blessing_of_the_trickster"]})


def _trickster_check(_ctx: RuleContext, params: dict) -> tuple[int, str] | None:
    return (422, "invalid_choice") if params.get("self") and params.get("target_character_id") is not None else None


def _duplicity_state(ctx: RuleContext, _params: dict) -> StateSpec:
    """1 minuto, senza Concentrazione: finisce se congedato (a mano) o se il chierico è Incapacitato."""
    others = [INVOKE_DUPLICITY] + ([f"{CK}.improved_duplicity"] if ctx.class_level >= 17 else [])
    data: dict[str, Any] = {"others": others}
    if ctx.class_level >= 17:  # a qualunque fine dell'illusione resta l'offerta della cura (``settle_closed``)
        data["on_close"] = {"key": ILLUSION_ENDED, "ends_on": ["manual", "rest_short", "rest_long"], "name": "Duplicato Migliorato"}
    return StateSpec("invoke_duplicity", rounds=10, ends_on=("incapacitated", "manual"), data=data)


ILLUSION_ENDED = "improved_duplicity_ready"  # l'illusione è finita e la cura di Duplicato Migliorato non è ancora stata presa


def _illusion_offer_taken(ctx: RuleContext, _params: dict) -> None:
    """La cura si prende una volta sola: usarla (con l'illusione in piedi o già finita) toglie anche l'offerta lasciata dalla fine."""
    ctx.char.active_states = [s for s in ctx.char.active_states or [] if s.get("key") != ILLUSION_ENDED]


_ILLUSION_HEAL = {"self": {"it": "Tu", "en": "You"},
                  "ally": {"it": "Una creatura entro 1,5 m dall'illusione", "en": "A creature within 5 ft of the illusion"}}
IMPROVED_DUPLICITY_USE = OnUse(
    cost=0, available=lambda c: state_on(c, "invoke_duplicity") or state_on(c, ILLUSION_ENDED), ends_state="invoke_duplicity",
    effect=_illusion_offer_taken,
    heal=lambda c, _r: c.class_level, heal_when=lambda _c, p: p.get("mode") == "self", ally_modes=("ally",),
    heal_ally_when=lambda _c, p: p.get("mode") == "ally",
    choices=(UseChoice("mode", {"it": "Chi recupera i PF", "en": "Who regains the HP"}, lambda _c: list(_ILLUSION_HEAL),
                       lambda k: _ILLUSION_HEAL[k]),),
    message=lambda c, _p: {"it": f"L'illusione finisce: chi sceglie recupera {c.class_level} PF (se non siede alla serata, riferiscili al GM).",
                           "en": f"The illusion ends: the chosen creature regains {c.class_level} HP (if it does not sit at the evening, tell the GM)."})


# Guerra
WAR_PRIEST_ATTACK = RollOptionSpec(
    key=WAR_PRIEST, phase="before", rolls=("attack",), slot="bonus", cost=Cost(feature_key=WAR_PRIEST),
    label={"it": "Sacerdote di Guerra: attacco con arma o senz'armi come azione bonus", "en": "War Priest: weapon or unarmed attack as a bonus action"},
    available=lambda c: c.spell is None)

_WGB_SPELLS = {"shield-of-faith": {"it": "Scudo della fede", "en": "Shield of Faith"},
               "spiritual-weapon": {"it": "Arma spirituale", "en": "Spiritual Weapon"}}


def _wgb_check(ctx: RuleContext, params: dict) -> tuple[int, str] | None:
    """L'incantesimo scelto deve stare sulla scheda (lo dà il dominio al 3° livello)."""
    return None if any(sp.srd_index == params.get("spell") for sp in ctx.char.spells) else (422, "invalid_choice")


def _wgb_effect(ctx: RuleContext, params: dict) -> None:
    """Autorizza un lancio gratuito (R43) dell'incantesimo scelto: azione bonus, nessuna Concentrazione; il lancio chiude
    l'autorizzazione e avvia lo stato di 1 minuto, che finisce se Incapacitato o se si rilancia."""
    spell = str(params["spell"])
    begin_state(ctx.char, StateSpec("war_gods_blessing_free", ends_on=("manual", "rest_short", "rest_long"), data={
        "free_cast": spell, "free_cast_slot": "bonus", "no_concentration": True, "spell": spell,
        "then": {"key": "war_gods_blessing", "rounds": 10, "ends_on": ["incapacitated", "manual"], "data": {"spell": spell}}}),
        f"{CK}.war_gods_blessing", "Benedizione del Dio della Guerra")


WAR_GODS_BLESSING_USE = OnUse(
    spends=POOL, check=_wgb_check, effect=_wgb_effect,
    choices=(UseChoice("spell", {"it": "Incantesimo", "en": "Spell"}, lambda _c: list(_WGB_SPELLS), lambda k: _WGB_SPELLS[k]),),
    message=lambda _c, _p: {"it": "Lancia l'incantesimo dalla pagina degli incantesimi, senza slot (azione bonus): niente Concentrazione, "
                                  "dura 1 minuto e finisce se sei Incapacitato o se lo rilanci.",
                            "en": "Cast the spell from the spells page with no slot (bonus action): no Concentration, it lasts 1 minute "
                                  "and ends if you are Incapacitated or cast it again."})

GUIDED_STRIKE_ALLY = OnUse(
    slot="reaction", spends=POOL,
    message=lambda _c, _p: {"it": "Una creatura entro 9 m ha mancato: somma 10 al suo tiro per colpire (puoi farlo dopo aver visto l'esito).",
                            "en": "A creature within 30 ft missed: add 10 to its attack roll (you can do it after seeing the result)."})

# 2014: «tu e il duplicato siete entro 1,5 m dal bersaglio»; dal 17° basta il bersaglio accanto all'illusione
_ADVANTAGE_BASE = replace(DUPLICITY_ADVANTAGE, available=lambda c: state_on(c, "invoke_duplicity") and c.class_level < 17)
_ADVANTAGE_17 = replace(
    DUPLICITY_ADVANTAGE, key=f"{CK}.duplicity_advantage_improved", available=lambda c: state_on(c, "invoke_duplicity") and c.class_level >= 17,
    label={"it": "Duplicato Migliorato: il bersaglio è entro 1,5 m dall'illusione?",
           "en": "Improved Duplicity: is the target within 5 ft of the illusion?"})

DOMAIN_FEATURES = (
    # Dominio della Vita
    *_domain_spells("life", "Incantesimi del Dominio della Vita / Life Domain Spells (Vita 3, pag. 73)",
                    ("Incantesimi del Dominio della Vita", "Life Domain Spells")),
    feature("disciple_of_life", CK, ED, 3, "Discepolo della Vita / Disciple of Life (Vita 3, pag. 73)",
            ("Discepolo della Vita", "Disciple of Life"),
            ("Un incantesimo lanciato con uno slot che restituisce PF ne dà 2 in più più il livello dello slot.",
             "A spell cast with a slot that restores HP gives 2 extra HP plus the slot's level."),
            subclass="life", modifiers=(Modifier("healing", lambda c: 2 + (c.casting_level or 0), when=_healing_roll,
                                                 source=f"feature:{CK}.disciple_of_life"),)),
    feature("preserve_life", CK, ED, 3, "Preservare Vita / Preserve Life (Vita 3, pag. 73)", ("Preservare Vita", "Preserve Life"),
            ("Azione Magia, un uso: distribuisci 5 x livello PF fra creature Sanguinanti entro 9 m, fino alla metà dei loro PF massimi.",
             "Magic action, one use: split 5 x level HP among Bloodied creatures within 30 ft, up to half their maximum HP."),
            "action", subclass="life", on_use=OnUse(slot="action", spends=POOL, panel="preserve_life")),
    feature("blessed_healer", CK, ED, 6, "Guaritore Benedetto / Blessed Healer (Vita 6, pag. 74)", ("Guaritore Benedetto", "Blessed Healer"),
            ("Se curi un'altra creatura con uno slot, recuperi 2 PF più il livello dello slot.",
             "When you heal another creature with a slot, you regain 2 HP plus the slot's level."),
            subclass="life", roll_options=(BLESSED_HEALER,)),
    feature("supreme_healing", CK, ED, 17, "Guarigione Suprema / Supreme Healing (Vita 17, pag. 74)", ("Guarigione Suprema", "Supreme Healing"),
            ("I dadi di cura di un incantesimo o di Scintilla Divina valgono sempre il massimo.",
             "The healing dice of a spell or of Divine Spark always count as their maximum."),
            subclass="life", modifiers=(Modifier("maximize_healing", 1, when=lambda c: c.roll == "spell_healing",
                                                 source=f"feature:{CK}.supreme_healing"),)),

    # Dominio della Luce
    *_domain_spells("light", "Incantesimi del Dominio della Luce / Light Domain Spells (Luce 3, pag. 74)",
                    ("Incantesimi del Dominio della Luce", "Light Domain Spells")),
    feature("radiance_of_the_dawn", CK, ED, 3, "Fulgore dell'Alba / Radiance of the Dawn (Luce 3, pag. 74)",
            ("Fulgore dell'Alba", "Radiance of the Dawn"),
            ("Azione Magia, un uso: 2d10 + livello radianti entro 9 m (TS Costituzione, metà); dissolve l'oscurità magica.",
             "Magic action, one use: 2d10 + level radiant within 30 ft (Con save, half); dispels magical darkness."),
            "action", subclass="light",
            on_use=OnUse(slot="action", spends=POOL, rolls="2d10", state=_radiance_state, message=_radiance_message)),
    feature("warding_flare", CK, ED, 3, "Lampo di Interdizione / Warding Flare (Luce 3, pag. 74)", ("Lampo di Interdizione", "Warding Flare"),
            ("Reazione: svantaggio al tiro per colpire di una creatura visibile entro 9 m. Usi pari a Saggezza (minimo 1).",
             "Reaction: disadvantage on the attack roll of a creature you can see within 30 ft. Uses equal Wisdom (minimum 1)."),
            "reaction", subclass="light", uses=Uses(ability="wisdom", minimum=1), restoration={3: "long_rest", 6: "short_rest"},
            on_use=OnUse(slot="reaction", state=_flare_state, rolls=_flare_dice, gives=_flare_temp_hp, message=_flare_message,
                         temp_hp_ally=True, ally_count=lambda c: 1 if c.class_level >= 6 else 0)),
    feature("improved_warding_flare", CK, ED, 6, "Lampo di Interdizione Migliorato / Improved Warding Flare (Luce 6, pag. 75)",
            ("Lampo di Interdizione Migliorato", "Improved Warding Flare"),
            ("Gli usi tornano anche con un riposo breve; a ogni uso 2d6 + Saggezza PF temporanei al bersaglio dell'attacco.",
             "Uses also return on a short rest; each use gives the attack's target 2d6 + Wisdom temporary HP."),
            subclass="light", passive=True),
    feature("corona_of_light", CK, ED, 17, "Corona di Luce / Corona of Light (Luce 17, pag. 75)", ("Corona di Luce", "Corona of Light"),
            ("Azione Magia: 1 minuto di luce solare (18 m, fioca altri 9 m); i nemici nella luce intensa hanno svantaggio ai TS contro Fulgore dell'Alba e incantesimi con danni da fuoco o radiosi. Usi: Saggezza.",
             "Magic action: 1 minute of sunlight (60 ft, dim 30 ft more); enemies in bright light have disadvantage on saves against Radiance of the Dawn and fire or radiant spells. Uses equal Wisdom."),
            "action", subclass="light", uses=Uses(ability="wisdom", minimum=1), restoration="long_rest", on_use=CORONA_USE),

    # Dominio dell'Inganno
    *_domain_spells("trickery", "Incantesimi del Dominio dell'Inganno / Trickery Domain Spells (Inganno 3, pag. 76)",
                    ("Incantesimi del Dominio dell'Inganno", "Trickery Domain Spells")),
    feature("blessing_of_the_trickster", CK, ED, 3, "Benedizione dell'Ingannatore / Blessing of the Trickster (Inganno 3, pag. 75)",
            ("Benedizione dell'Ingannatore", "Blessing of the Trickster"),
            ("Azione Magia: tu o una creatura consenziente entro 9 m avete vantaggio a Furtività fino al riposo lungo o al prossimo uso.",
             "Magic action: you or a willing creature within 30 ft has advantage on Stealth until a long rest or the next use."),
            "action", subclass="trickery",
            on_use=OnUse(slot="action", ally_state=True, ally_exclusive=True, state=_trickster_state, check=_trickster_check,
                         toggles=(UseToggle("self", {"it": "Su te stesso", "en": "On yourself"}),))),
    feature("invoke_duplicity", CK, ED, 3, "Invocare Duplicato / Invoke Duplicity (Inganno 3, pag. 75)", ("Invocare Duplicato", "Invoke Duplicity"),
            ("Azione bonus, un uso: illusione di te per 1 minuto, congedabile; vantaggio agli attacchi se siete entrambi entro 1,5 m dal bersaglio.",
             "Bonus action, one use: an illusion of you for 1 minute, dismissable; advantage on attacks if you are both within 5 ft of the target."),
            "bonus_action", subclass="trickery", roll_options=(_ADVANTAGE_BASE, _ADVANTAGE_17),
            on_use=OnUse(slot="bonus", spends=POOL, state=_duplicity_state, available=lambda c: not state_on(c, "invoke_duplicity"))),
    feature("invoke_duplicity_move", CK, ED, 3, "Invocare Duplicato / Invoke Duplicity (Inganno 3, pag. 75)",
            ("Muovere il Duplicato", "Move the Duplicate"),
            ("Azione bonus, finché l'illusione esiste: la sposti fino a 9 m in uno spazio libero visibile entro 36 m da te.",
             "Bonus action while the illusion exists: move it up to 30 ft to an unoccupied space you can see within 120 ft of you."),
            "bonus_action", subclass="trickery", on_use=OnUse(slot="bonus", cost=0, available=lambda c: state_on(c, "invoke_duplicity"))),
    feature("tricksters_transposition", CK, ED, 6, "Trasposizione dell'Ingannatore / Trickster's Transposition (Inganno 6, pag. 76)",
            ("Trasposizione dell'Ingannatore", "Trickster's Transposition"),
            ("Con l'azione bonus che crea o muove l'illusione puoi scambiare il posto con lei.",
             "With the bonus action that creates or moves the illusion you can swap places with it."),
            subclass="trickery", passive=True),
    feature("improved_duplicity", CK, ED, 17, "Duplicato Migliorato / Improved Duplicity (Inganno 17, pag. 76)",
            ("Duplicato Migliorato", "Improved Duplicity"),
            ("Alleati e tu avete vantaggio contro chi è entro 1,5 m dall'illusione; quando finisce, tu o una creatura vicina recuperate PF pari al livello.",
             "You and your allies have advantage against creatures within 5 ft of the illusion; when it ends, you or a nearby creature regains HP equal to your level."),
            subclass="trickery", on_use=IMPROVED_DUPLICITY_USE),

    # Dominio della Guerra
    *_domain_spells("war", "Incantesimi del Dominio della Guerra / War Domain Spells (Guerra 3, pag. 77)",
                    ("Incantesimi del Dominio della Guerra", "War Domain Spells")),
    feature("guided_strike", CK, ED, 3, "Colpo Guidato / Guided Strike (Guerra 3, pag. 77)", ("Colpo Guidato", "Guided Strike"),
            ("Dopo un tiro per colpire mancato, tuo o di una creatura entro 9 m, spendi un uso di Incanalare Divinità e somma 10 al tiro.",
             "After a missed attack roll, yours or a creature's within 30 ft, spend a Channel Divinity use and add 10 to the roll."),
            "reaction", subclass="war", roll_options=(GUIDED_STRIKE,), on_use=GUIDED_STRIKE_ALLY),
    feature("war_priest", CK, ED, 3, "Sacerdote di Guerra / War Priest (Guerra 3, pag. 77)", ("Sacerdote di Guerra", "War Priest"),
            ("Azione bonus: un attacco con arma o un Colpo Senz'Armi. Usi pari a Saggezza (minimo 1), con riposo breve o lungo.",
             "Bonus action: one weapon attack or Unarmed Strike. Uses equal Wisdom (minimum 1), on a short or long rest."),
            "bonus_action", subclass="war", uses=Uses(ability="wisdom", minimum=1), restoration="short_rest",
            roll_options=(WAR_PRIEST_ATTACK,)),
    feature("war_gods_blessing", CK, ED, 6, "Benedizione del Dio della Guerra / War God's Blessing (Guerra 6, pag. 77)",
            ("Benedizione del Dio della Guerra", "War God's Blessing"),
            ("Un uso di Incanalare Divinità: lanci Scudo della Fede o Arma Spirituale senza slot né Concentrazione, per 1 minuto.",
             "Spend a Channel Divinity use: cast Shield of Faith or Spiritual Weapon with no slot or Concentration, for 1 minute."),
            "bonus_action", subclass="war", on_use=WAR_GODS_BLESSING_USE),
    feature("avatar_of_battle", CK, ED, 17, "Avatar della Battaglia / Avatar of Battle (Guerra 17, pag. 77)",
            ("Avatar della Battaglia", "Avatar of Battle"),
            ("Resistenza ai danni contundenti, perforanti e taglienti.", "Resistance to bludgeoning, piercing and slashing damage."),
            subclass="war", modifiers=tuple(Modifier(f"resistance:{t}", 1, source=f"feature:{CK}.avatar_of_battle")
                                            for t in ("bludgeoning", "piercing", "slashing"))),
)

CLASS_FEATURES = (
    feature("core_traits", CK, ED, 1, "Tratti base / Core Cleric Traits (Chierico 1, pag. 69)", ("Tratti Base del Chierico", "Core Cleric Traits"),
            ("Dado Vita d8, TS Saggezza e Carisma, 2 abilità, armi semplici, armature leggere, medie e scudi.",
             "Hit die d8, Wisdom and Charisma saves, 2 skills, simple weapons, light and medium armor and shields."),
            # PF, TS, armi, armature e abilità: api/routers/classes.py e core/rules/proficiencies.py; equipaggiamento A/B no (R32)
            no_row=True, covered_by="lavori-successivi"),
    feature("spellcasting", CK, ED, 1, "Incantesimi / Spellcasting (Chierico 1, pag. 69)", ("Incantesimi", "Spellcasting"),
            ("Saggezza; trucchetti 3/4/5 e incantesimi preparati da 4 a 22; slot da tabella; simbolo sacro come focus.",
             "Wisdom; cantrips 3/4/5 and prepared spells from 4 to 22; slots by table; a holy symbol as focus."),
            no_row=True, covered_by="core/rules/spellcasting.py (prepared_limit, known_limits, slots_for); "
                                    "test_cantrips_and_prepared_spells_follow_the_2024_table"),
    feature("divine_order", CK, ED, 1, "Ordine Divino / Divine Order (Chierico 1, pag. 70)", ("Ordine Divino", "Divine Order"),
            ("Al 1° livello si sceglie Protettore o Taumaturgo.", "At level 1 you choose Protector or Thaumaturge."),
            choices=(ChoiceSpec(group=ORDER, levels={1: 1}, options=lambda _c: ["protector", "thaumaturge"]),)),
    feature("divine_order_protector", CK, ED, 1, "Ordine Divino: Protettore / Divine Order: Protector (Chierico 1, pag. 70)",
            ("Protettore", "Protector"),
            ("Competenza nelle armi da guerra e addestramento con le armature pesanti.",
             "Proficiency with martial weapons and training with heavy armor."),
            option_group=ORDER, option_key="protector", proficiency_grants={"armor": ("heavy",), "weapons": ("martial",)}),
    feature("divine_order_thaumaturge", CK, ED, 1, "Ordine Divino: Taumaturgo / Divine Order: Thaumaturge (Chierico 1, pag. 70)",
            ("Taumaturgo", "Thaumaturge"),
            ("Un trucchetto da chierico in più, fuori dal limite; alle prove di Arcano e Religione somma Saggezza (minimo +1).",
             "One extra cleric cantrip, outside the limit; add Wisdom (minimum +1) to Arcana and Religion checks."),
            option_group=ORDER, option_key="thaumaturge", modifiers=(THAUMATURGE_BONUS,),
            choices=(ChoiceSpec(group="thaumaturge_cantrip", levels={1: 1}, options=_no_options, spell_pick="extra", spell_level=0,
                                spell_list="cleric"),)),
    feature("channel_divinity", CK, ED, 2, "Incanalare Divinità / Channel Divinity (Chierico 2, pag. 70)",
            ("Incanalare Divinità", "Channel Divinity"),
            ("Usi: 2 al 2°, 3 al 6°, 4 al 18°. Un riposo breve ne rende 1, uno lungo tutti. Ogni effetto, anche di sottoclasse, ne spende uno.",
             "Uses: 2 at 2nd, 3 at 6th, 4 at 18th. A short rest returns 1, a long rest all. Each effect, subclass ones too, spends one."),
            "action", uses=Uses(table={2: 2, 6: 3, 18: 4}), restoration="long_rest", short_rest_recovers=1,
            shared_pool="channel_divinity"),
    feature("divine_spark", CK, ED, 2, "Incanalare Divinità: Scintilla Divina / Channel Divinity: Divine Spark (Chierico 2, pag. 70)",
            ("Scintilla Divina", "Divine Spark"),
            ("Azione Magia, un uso: tira Nd8 + Saggezza (N 1/2/3/4 ai livelli 2/7/13/18). Cura un'altra creatura o la danneggia (TS Cos, metà).",
             "Magic action, one use: roll Nd8 + Wisdom (N 1/2/3/4 at levels 2/7/13/18). Heal another creature or damage it (Con save, half)."),
            "action", on_use=SPARK_USE),
    feature("turn_undead", CK, ED, 2, "Incanalare Divinità: Scacciare Non Morti / Channel Divinity: Turn Undead (Chierico 2, pag. 70)",
            ("Scacciare Non Morti", "Turn Undead"),
            ("Azione Magia, un uso: i non morti entro 9 m fanno un TS Saggezza o sono Spaventati e Incapacitati per 1 minuto.",
             "Magic action, one use: undead within 30 ft make a Wisdom save or are Frightened and Incapacitated for 1 minute."),
            "action", on_use=TURN_UNDEAD_USE),
    feature("cleric_subclass", CK, ED, 3, "Sottoclasse del Chierico / Cleric Subclass (Chierico 3, pag. 71)",
            ("Sottoclasse del Chierico", "Cleric Subclass"),
            ("Al 3° livello si sceglie il Dominio della Vita, della Luce, dell'Inganno o della Guerra.",
             "At level 3 you choose the Life, Light, Trickery or War Domain."),
            no_row=True, covered_by="core/rules/subclasses.py (match_subclass) e il campo sottoclasse della classe"),
    feature("ability_score_improvement", CK, ED, 4,
            "Aumento dei Punteggi di Caratteristica / Ability Score Improvement (Chierico 4, pag. 71)",
            ("Aumento dei Punteggi di Caratteristica", "Ability Score Improvement"),
            ("Ai livelli 4, 8, 12 e 16 il talento Aumento dei Punteggi o un altro talento di cui hai i requisiti.",
             "At levels 4, 8, 12 and 16 the Ability Score Improvement feat or another feat you qualify for."),
            no_row=True, covered_by="core/rules/level_choices.py (scelta asi); test_asi_choice_is_pending_at_each_asi_level_and_the_19th_is_an_epic_boon"),
    feature("sear_undead", CK, ED, 5, "Bruciare Non Morti / Sear Undead (Chierico 5, pag. 71)", ("Bruciare Non Morti", "Sear Undead"),
            ("Con Scacciare Non Morti tiri Saggezza (minimo 1) d8: danni radiosi a ogni non morto che fallisce, senza chiudere l'effetto.",
             "With Turn Undead you roll Wisdom (minimum 1) d8: radiant damage to each undead that fails, without ending the effect."),
            passive=True),
    feature("blessed_strikes", CK, ED, 7, "Colpi Benedetti / Blessed Strikes (Chierico 7, pag. 71)", ("Colpi Benedetti", "Blessed Strikes"),
            ("Al 7° livello si sceglie Colpo Divino o Incantesimi Potenti.", "At level 7 you choose Divine Strike or Potent Spellcasting."),
            choices=(ChoiceSpec(group=STRIKES, levels={7: 1}, options=lambda _c: ["divine_strike", "potent_spellcasting"]),)),
    feature("blessed_strikes_divine_strike", CK, ED, 7, "Colpi Benedetti: Colpo Divino / Blessed Strikes: Divine Strike (Chierico 7, pag. 71)",
            ("Colpo Divino", "Divine Strike"),
            ("Una volta per turno, con un colpo d'arma: 1d8 (2d8 dal 14°) di danni necrotici o radiosi in più, a scelta.",
             "Once per turn, on a weapon hit: 1d8 (2d8 from level 14) extra necrotic or radiant damage, your choice."),
            option_group=STRIKES, option_key="divine_strike",
            roll_options=(_divine_strike("blessed", "necrotici", "necrotic", group="blessed_strike", suffix="_necrotic"),
                          _divine_strike("blessed", "radiosi", "radiant", group="blessed_strike", suffix="_radiant"))),
    feature("blessed_strikes_potent", CK, ED, 7, "Colpi Benedetti: Incantesimi Potenti / Blessed Strikes: Potent Spellcasting (Chierico 7, pag. 71)",
            ("Incantesimi Potenti", "Potent Spellcasting"),
            ("Ai danni di ogni tuo trucchetto da chierico si somma il modificatore di Saggezza.",
             "Add your Wisdom modifier to the damage of every cleric cantrip you cast."),
            option_group=STRIKES, option_key="potent_spellcasting", modifiers=(_potent(),)),
    feature("divine_intervention", CK, ED, 10, "Intervento Divino / Divine Intervention (Chierico 10, pag. 71)",
            ("Intervento Divino", "Divine Intervention"),
            ("Un uso per riposo lungo: lanci senza slot né componenti materiali un incantesimo da chierico di livello 5 o inferiore, senza Reazione.",
             "One use per long rest: cast a cleric spell of level 5 or lower, no Reaction, with no slot or material components."),
            "action", uses=Uses(table={10: 1}), restoration="long_rest", on_use=DIVINE_INTERVENTION_USE, long_rest_state=_wish_countdown),
    feature("improved_blessed_strikes", CK, ED, 14, "Colpi Benedetti Migliorati / Improved Blessed Strikes (Chierico 14, pag. 71)",
            ("Colpi Benedetti Migliorati", "Improved Blessed Strikes"),
            ("Colpo Divino arriva a 2d8; con Incantesimi Potenti un trucchetto che danneggia dà PF temporanei pari al doppio di Saggezza.",
             "Divine Strike reaches 2d8; with Potent Spellcasting a damaging cantrip gives temporary HP equal to twice Wisdom."),
            roll_options=(POTENT_TEMP_HP,), passive=True),
    feature("epic_boon", CK, ED, 19, "Dono Epico / Epic Boon (Chierico 19, pag. 71)", ("Dono Epico", "Epic Boon"),
            ("Al 19° livello un talento Dono Epico o un altro talento di cui hai i requisiti.",
             "At level 19 an Epic Boon feat or another feat you qualify for."),
            no_row=True, covered_by="core/rules/level_choices.py (reconcile_choices, scelta epic_boon)"),
    feature("greater_divine_intervention", CK, ED, 20, "Intervento Divino Superiore / Greater Divine Intervention (Chierico 20, pag. 71)",
            ("Intervento Divino Superiore", "Greater Divine Intervention"),
            ("Con Intervento Divino puoi scegliere Desiderio; se lo lanci il privilegio resta bloccato per 2d4 riposi lunghi.",
             "With Divine Intervention you can choose Wish; if you cast it the feature stays blocked for 2d4 long rests."),
            passive=True),
    feature("multiclassing", CK, ED, 1, "Multiclasse: Chierico / Multiclassing: Cleric (Chierico, pag. 44)",
            ("Multiclasse: Chierico", "Multiclassing: Cleric"),
            ("Requisito Saggezza 13. Da multiclasse: armature leggere, medie e scudi; i livelli contano per intero negli slot.",
             "Requires Wisdom 13. As a multiclass: light and medium armor and shields; levels count in full for slots."),
            no_row=True, covered_by="core/rules/proficiencies.py (as_multiclass) e webapp/src/data/multiclassPrereqs.ts (D2)"),
)

FEATURES = DOMAIN_FEATURES + CLASS_FEATURES

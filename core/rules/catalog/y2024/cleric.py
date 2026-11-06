"""Chierico 2024: base della classe (Task 33, parte A). Le sottoclassi (Vita, Luce, Inganno, Guerra) vengono dopo (parte B).

Valori dalla scheda ``docs/superpowers/rules/2024/classes/cleric.md``; i testi sono nostri, mai quelli del manuale.
Incanalare Divinità è la riserva condivisa ``channel_divinity`` (stessa chiave del 2014 e del Paladino): ogni effetto,
anche quelli di sottoclasse, la spende con ``OnUse.spends=POOL``.

Per la parte B: i privilegi di sottoclasse vanno in ``DOMAIN_FEATURES`` (``subclass="life"|"light"|"trickery"|"war"``),
spendono ``POOL`` e usano ``spell_dc``; Guarigione Suprema deve agire su Scintilla Divina (``SPARK_USE``) oltre che sulle cure
degli incantesimi.
"""
from __future__ import annotations

import random
import uuid
from typing import Any

from core.rules.catalog._common import feature, state_on
from core.rules.catalog.y2014.cleric import (
    POOL, _divine_strike, _no_options, _own_cantrip, _potent, _wisdom_mod, spell_dc,
)
from core.rules.states import STOLEN_SPELL, begin_state
from core.rules.types import (
    ChoiceSpec, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, TargetEffect, UseChoice, Uses, UseText, UseToggle,
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


SPARK_USE = OnUse(
    slot="action", spends=POOL, rolls=_spark_dice, heal=_spark_total, heal_when=lambda _c, _p: False,
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
    effect=lambda c, _i: {"it": f"Dai {2 * _wisdom_mod(c)} PF temporanei a te o a una creatura entro 18 m.",
                          "en": f"Give {2 * _wisdom_mod(c)} temporary HP to yourself or a creature within 60 ft."})


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
    name = "Desiderio" if wish else str(params["spell"]).strip()
    ctx.char.spells.append(Spell(
        character_id=ctx.char.id, name=name, level=9 if wish else int(params["spell_level"]), srd_index=tag,
        class_id=ctx.class_row.id, is_prepared=True, always_prepared=True))
    begin_state(ctx.char, StateSpec("divine_intervention_free", ends_on=("manual", "rest_long"),
                                    data={"stolen_spell": tag, "free_cast": tag}), DIVINE_INTERVENTION, "Intervento Divino")
    if wish:
        dice = [random.randint(1, 4), random.randint(1, 4)]
        begin_state(ctx.char, StateSpec(WISH_LOCK, ends_on=("manual",), data={"roll": dice, "rests_left": sum(dice)}),
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

DOMAIN_FEATURES: tuple = ()  # parte B: Vita, Luce, Inganno, Guerra

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

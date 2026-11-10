"""Paladino 2024, parte A (base della classe). I giuramenti (Devozione, Gloria, Antichi, Vendetta) sono la parte B: le loro righe
vanno in ``SUBCLASS_ROWS`` con ``subclass=`` (chiavi di ``core/rules/subclasses.py``: devotion, glory, ancients, vengeance).

Valori dalla scheda ``docs/superpowers/rules/2024/classes/paladin.md``; i testi sono nostri, mai quelli del manuale.
Le chiavi di Imposizione delle Mani e Incanalare Divinità sono quelle legacy di ``CLASS_RESOURCES`` (R17); Incanalare Divinità è la
riserva condivisa ``channel_divinity`` col Chierico. Per la parte B: ``smite_cast(ctx)`` dice se la Punizione Divina è stata
scelta (con slot o gratuita) in questo colpo; ``POOL`` è la riserva che le opzioni di Incanalare Divinità dei giuramenti spendono.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from core.rules.catalog._common import FIGHTING_STYLE_GROUP, feature, style_options
from core.rules.catalog.y2014.paladin import SAVE_ROLLS, _aura_range, _cha_bonus, _cha_mod, _permanent_note, _say, _spell_dc
from core.rules.catalog.y2024.fighter import STYLE_ROWS as FIGHTER_STYLE_ROWS, STYLES as FIGHTER_STYLES
from core.rules.states import is_conscious
from core.rules.condition_removal import ConditionRemoval
from core.rules.types import (
    AuraSpec, ChoiceSpec, Cost, FeatureSpec, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, TargetEffect, UseChoice,
    UseText, Uses,
)
from core.rules.weapons import MASTERY_OPTIONS, mastery_choice

ED, CK = "2024", "paladin"
POOL = f"{CK}.channel_divinity"
LAY_ON_HANDS = f"{CK}.lay_on_hands"
PS = f"{CK}.paladins_smite"
STEED = f"{CK}.faithful_steed"
SMITE, SMITE_FREE = f"{CK}.divine_smite", f"{CK}.divine_smite_free"
SMITE_FIEND, SMITE_FIEND_FREE = f"{CK}.divine_smite_fiend", f"{CK}.divine_smite_fiend_free"
SMITE_GROUP = f"{CK}.divine_smite_cast"
BLESSED_CANTRIPS = "blessed_warrior_cantrip"
STYLES = (*FIGHTER_STYLES, "blessed_warrior")
_ROWS = "core/rules/proficiencies.py (class_proficiencies, as_multiclass), api/routers/classes.py create_class_for_character e add_class"


def _both(it: str, en: str) -> dict[str, str]:
    return {"it": it, "en": en}


def _melee_or_unarmed(ctx: RuleContext) -> bool:
    """Un attacco con un'arma da mischia (non lanciata né a distanza) o un Colpo Senz'armi; mai un incantesimo."""
    return ctx.spell is None and ctx.attack_mode in ("melee", "offhand")


# ---------------------------------------------------------------------------
# Imposizione delle Mani (azione bonus) e Tocco Ristoratore
# ---------------------------------------------------------------------------

_LOH_MODES = {
    "self": _both("Cura PF a te stesso", "Heal yourself"),
    "other": _both("Cura PF a un altro", "Heal another creature"),
    "cure": _both("Togli condizioni (5 punti ciascuna)", "Remove conditions (5 points each)"),
}
# Avvelenato dal 1° livello; le altre sei con il Tocco Ristoratore (14°)
_CURABLE = {
    "poisoned": ("Avvelenato", "Poisoned"), "blinded": ("Accecato", "Blinded"), "charmed": ("Affascinato", "Charmed"),
    "deafened": ("Assordato", "Deafened"), "frightened": ("Spaventato", "Frightened"), "paralyzed": ("Paralizzato", "Paralyzed"),
    "stunned": ("Stordito", "Stunned"),
}


def _curable(ctx: RuleContext) -> list[str]:
    return [c for i, c in enumerate(_CURABLE) if i == 0 or ctx.class_level >= 14]


def _loh_notes(_ctx: RuleContext, params: dict) -> list[str]:
    """Esiti per chi usa il privilegio: i PF di un altro fuori serata li riporta il giocatore al GM."""
    if params.get("mode") == "other" and params.get("target_character_id") is None:
        return ["lay_on_hands_other_2024"]
    return []  # le condizioni sono nel meccanismo comune (``removal``)


_LOH_REMOVAL = ConditionRemoval(tuple(_CURABLE), count=None, allowed=lambda c: tuple(_curable(c)), modes=("cure",), cost_each=5)

LAY_ON_HANDS_USE = OnUse(
    slot="bonus", choose_amount=True, heal=lambda _c, _r: 1, heal_when=lambda _c, p: p.get("mode") == "self",
    heal_ally_when=lambda _c, p: p.get("mode") == "other", ally_modes=("other",), notes=_loh_notes,
    removal=_LOH_REMOVAL,
    choices=(UseChoice("mode", _both("Su chi", "On whom"), lambda _c: list(_LOH_MODES), lambda k: _LOH_MODES[k]),))


# ---------------------------------------------------------------------------
# Stile di Combattimento: i dieci talenti del Guerriero (nuove righe del Paladino) e Guerriero Benedetto
# ---------------------------------------------------------------------------

def _paladin_style(spec: FeatureSpec) -> FeatureSpec:
    """Lo stesso talento, riga del Paladino: chiave, classe, livello 2 e fonte dei modificatori (le etichette citano la riga)."""
    return replace(spec, key=spec.key.replace("fighter.", f"{CK}.", 1), class_key=CK, level=2,
                   modifiers=tuple(replace(m, source=m.source.replace("fighter.", f"{CK}.", 1)) for m in spec.modifiers))


STYLE_ROWS = tuple(_paladin_style(s) for s in FIGHTER_STYLE_ROWS)
BLESSED_WARRIOR = feature(
    "style_blessed_warrior", CK, ED, 2, "Guerriero Benedetto / Blessed Warrior (Stile di Combattimento, Paladino 2, pag. 110)",
    ("Guerriero Benedetto", "Blessed Warrior"),
    ("Due trucchetti da chierico, fuori dal limite, con Carisma come caratteristica; ogni livello da paladino puoi cambiarne uno.",
     "Two cleric cantrips, outside the limit, with Charisma as the ability; at each paladin level you can swap one."),
    option_group=FIGHTING_STYLE_GROUP, option_key="blessed_warrior",
    choices=(ChoiceSpec(group=BLESSED_CANTRIPS, levels={2: 2}, options=lambda _c: [], spell_pick="extra", spell_level=0, spell_list="cleric"),))


# ---------------------------------------------------------------------------
# Punizione del Paladino: Punizione Divina con slot o lancio gratuito, azione bonus dopo un colpo
# ---------------------------------------------------------------------------

def _smite_dice(_ctx: RuleContext, inputs: dict) -> str:
    """2d8 con uno slot di 1° livello, un d8 in più per ogni livello oltre il primo (il manuale non pone un tetto)."""
    return f"{1 + int(inputs.get('slot_level') or 1)}d8"


def _slot_smite_ok(ctx: RuleContext) -> bool:
    """Con uno slot: un solo incantesimo con slot per turno."""
    return _melee_or_unarmed(ctx) and not (ctx.char.turn_state or {}).get("spell_slot_cast")


def _mark_smite(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    """La Punizione Divina è stata lanciata in questo turno: Punizione Ispiratrice (Gloria) la richiede."""
    ctx.char.turn_state = {**(ctx.char.turn_state or {}), "smite_cast": True}


def _mark_slot_spell(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    ctx.char.turn_state = {**(ctx.char.turn_state or {}), "spell_slot_cast": True, "smite_cast": True}


def _free_left(ctx: RuleContext) -> bool:
    return any(a.feature_key == PS and (a.uses or 0) >= 1 for a in ctx.char.abilities)


def _fiend_slot_ok(ctx: RuleContext) -> bool:
    from core.rules.roll_options import slot_choices  # import locale: roll_options usa il catalogo
    return _slot_smite_ok(ctx) and (SMITE in ctx.confirmed or bool(slot_choices(ctx.char, 1)))


def smite_cast(ctx: RuleContext) -> bool:
    """La Punizione Divina (con slot o gratuita) è stata scelta in questo colpo: la leggono i giuramenti (parte B)."""
    return SMITE in ctx.confirmed or SMITE_FREE in ctx.confirmed


_RADIANT = _say("I dadi in più sono danni radiosi.", "The extra dice are radiant damage.")
_SMITE_LABEL = ("Punizione Divina: azione bonus, 2d8 radiosi in più (+1d8 per livello dello slot oltre il 1°)",
                "Divine Smite: bonus action, extra 2d8 radiant (+1d8 per slot level above 1st)")
DIVINE_SMITE = RollOptionSpec(
    key=SMITE, phase="after_hit", rolls=("attack",), requires_input="slot", cost=Cost(spell_slot_min=1), slot="bonus", group=SMITE_GROUP,
    extra_damage_type="radiant", extra_dice=_smite_dice, available=_slot_smite_ok, on_confirm=_mark_slot_spell, effect=_RADIANT,
    label=_both(*_SMITE_LABEL))
DIVINE_SMITE_FREE = RollOptionSpec(
    key=SMITE_FREE, phase="after_hit", rolls=("attack",), cost=Cost(feature_key=PS), slot="bonus", group=SMITE_GROUP,
    extra_damage_type="radiant", extra_dice=lambda _c, _i: "2d8", available=_melee_or_unarmed, effect=_RADIANT, on_confirm=_mark_smite,
    label=_both("Punizione del Paladino: lancio gratuito, azione bonus, 2d8 radiosi in più (un uso, riposo lungo)",
                "Paladin's Smite: free cast, bonus action, extra 2d8 radiant (one use, long rest)"))
_FIEND_LABEL = _both("Punizione Divina: il bersaglio è un immondo o un non morto? +1d8 radioso",
                     "Divine Smite: is the target a fiend or an undead? +1d8 radiant")
DIVINE_SMITE_FIEND = RollOptionSpec(
    key=SMITE_FIEND, phase="after_hit", rolls=("attack",), needs=SMITE, extra_damage_type="radiant", extra_dice=lambda _c, _i: "1d8", available=_fiend_slot_ok,
    label=_FIEND_LABEL)
DIVINE_SMITE_FIEND_FREE = RollOptionSpec(
    key=SMITE_FIEND_FREE, phase="after_hit", rolls=("attack",), needs=SMITE_FREE, extra_damage_type="radiant", extra_dice=lambda _c, _i: "1d8",
    available=lambda c: _melee_or_unarmed(c) and (SMITE_FREE in c.confirmed or _free_left(c)), label=_FIEND_LABEL)

RADIANT_STRIKES = RollOptionSpec(
    key=f"{CK}.radiant_strikes", phase="before", rolls=("attack",), automatic=True, extra_damage_type="radiant", extra_dice=lambda _c, _i: "1d8",
    available=_melee_or_unarmed, label=_both("Assalti Radianti: 1d8 radioso in più", "Radiant Strikes: extra 1d8 radiant"),
    effect=_say("Assalti Radianti: 1d8 danni radiosi in più, già nel totale.", "Radiant Strikes: an extra 1d8 radiant damage, already in the total."))


# ---------------------------------------------------------------------------
# Incanalare Divinità: Percezione del Divino e Abiurare i Nemici
# ---------------------------------------------------------------------------

def _abjure_effect(ctx: RuleContext, _params: dict) -> TargetEffect:
    return TargetEffect(condition="frightened", save_ability="wisdom", save_dc=_spell_dc(ctx), rounds=10, note="abjure_foes")


def _abjure_state(ctx: RuleContext, _params: dict) -> StateSpec:
    return StateSpec("abjure_foes", rounds=10, ends_on=("manual",), data={"dc": _spell_dc(ctx), "save": "wisdom", "others": [f"{CK}.abjure_foes"]})


def _abjure_message(ctx: RuleContext, _params: dict) -> dict[str, str]:
    n = max(1, _cha_mod(ctx))
    return _both(f"Fino a {'1 creatura' if n == 1 else f'{n} creature'} che vedi entro 18 m: TS Saggezza CD {_spell_dc(ctx)}.",
                 f"Up to {n} creature{'' if n == 1 else 's'} you can see within 60 ft: Wisdom save DC {_spell_dc(ctx)}.")


# ---------------------------------------------------------------------------
# Destriero Fedele
# ---------------------------------------------------------------------------

STEED_SPELL_LEVEL = 2  # il lancio gratuito è al livello base dell'incantesimo


def make_steed(char: Any, name: str, level: int = STEED_SPELL_LEVEL) -> None:
    """Trova Destriero: crea il destriero come compagno con le statistiche del manuale (CA 10 + livello dell'incantesimo,
    PF 5 + 10 per livello, 18 m; il volo 27 m c'è solo dal 4° livello). Un nuovo lancio sostituisce il precedente."""
    from core.db.models import Companion  # import locale: i modelli non servono al resto del catalogo
    for old in [c for c in char.companions if c.feature_key == STEED]:
        char.companions.remove(old)
    hp = 5 + 10 * level
    char.companions.append(Companion(
        character_id=char.id, kind="mount", name=name.strip() or "Destriero",
        statblock={"type": "celestial, fey o fiend", "size": "Large", "speed_ft": 60, **({"fly_speed_ft": 90} if level >= 4 else {})},
        max_hp=hp, current_hp=hp, armor_class=10 + level, feature_key=STEED,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds")))


def _steed_cast(ctx: RuleContext, params: dict) -> None:
    """Il lancio gratuito (azione) è al livello base dell'incantesimo."""
    make_steed(ctx.char, str(params.get("name") or ""))


STEED_USE = OnUse(
    slot="action", effect=_steed_cast, texts=(UseText("name", _both("Nome del destriero", "Steed name"), max_len=80, optional=True),),
    message=lambda _c, _p: _both("Lanci Trova Destriero senza slot: il destriero è fra i compagni (CA 12, 25 PF, 18 m).",
                                 "You cast Find Steed with no slot: the steed is among your companions (AC 12, 25 HP, 60 ft)."))


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

BASE_ROWS = (
    feature("core_traits", CK, ED, 1, "Tratti base / Core Paladin Traits (Paladino 1, pag. 109)", ("Tratti Base del Paladino", "Core Paladin Traits"),
            ("d10 come dado vita, TS Saggezza e Carisma, 2 abilità, armi semplici e da guerra, tutte le armature e gli scudi.",
             "d10 hit die, Wisdom and Charisma saves, 2 skills, simple and martial weapons, all armor and shields."),
            no_row=True, covered_by=f"{_ROWS}, total_base_hp; l'equipaggiamento di partenza è in lavori-successivi (2024-paladin)"),
    feature("lay_on_hands", CK, ED, 1, "Imposizione delle Mani / Lay On Hands (Paladino 1, pag. 109)", ("Imposizione delle Mani", "Lay On Hands"),
            ("Azione bonus: riserva di 5 PF per livello; tocchi una creatura e spendi punti per curarla, o 5 per togliere Avvelenato (e dal 14° altre sei condizioni). Riposo lungo.",
             "Bonus action: a pool of 5 HP per level; touch a creature and spend points to heal it, or 5 to remove Poisoned (and six more conditions from 14th). Long rest."),
            "bonus_action", uses=Uses(per_level=5), restoration="long_rest", on_use=LAY_ON_HANDS_USE),
    feature("spellcasting", CK, ED, 1, "Incantesimi / Spellcasting (Paladino 1, pag. 109)", ("Incantesimi", "Spellcasting"),
            ("Carisma; slot da mezzo incantatore dal 1° livello, preparati da 2 a 15 da tabella, nessun trucchetto; simbolo sacro come focus.",
             "Charisma; half-caster slots from 1st level, prepared spells from 2 to 15 by table, no cantrips; a holy symbol as focus."),
            no_row=True, covered_by="core/rules/spellcasting.py (prepared_limit, slots_for) e core/data/spell_slots.py (HALF_CASTER_SLOTS_2024, "
                                    "multiclasse per eccesso); test_prepared_spells_follow_the_2024_table_and_there_are_no_cantrips"),
    feature("weapon_mastery", CK, ED, 1, "Maestria nelle Armi / Weapon Mastery (Paladino 1, pag. 110)", ("Maestria nelle Armi", "Weapon Mastery"),
            ("Usi le proprietà di maestria di 2 tipi di arma con cui sei competente; dopo un riposo lungo ne cambi uno.",
             "You use the mastery properties of 2 kinds of weapon you are proficient with; change one after a long rest."),
            choices=(mastery_choice({1: 2}),), roll_options=MASTERY_OPTIONS),
    feature("fighting_style", CK, ED, 2, "Stile di Combattimento / Fighting Style (Paladino 2, pag. 110)",
            ("Stile di Combattimento", "Fighting Style"),
            ("Scegli un talento Stile di Combattimento, o Guerriero Benedetto.",
             "You choose a Fighting Style feat, or Blessed Warrior."),
            no_row=True, choices=(ChoiceSpec(group=FIGHTING_STYLE_GROUP, levels={2: 1}, options=style_options(STYLES)),),
            covered_by="ChoiceSpec fighting_style di questa riga e le righe dei dieci stili e di Guerriero Benedetto; "
                       "test_the_fighting_style_is_chosen_at_level_2_among_ten_styles_and_blessed_warrior"),
    *STYLE_ROWS,
    BLESSED_WARRIOR,
    feature("paladins_smite", CK, ED, 2, "Punizione del Paladino / Paladin's Smite (Paladino 2, pag. 110)", ("Punizione del Paladino", "Paladin's Smite"),
            ("Punizione Divina sempre preparata e un lancio gratuito per riposo lungo. Dopo un colpo in mischia o senz'armi: azione bonus, 2d8 radiosi, +1d8 con uno slot più alto.",
             "Divine Smite always prepared and one free cast per long rest. After a melee or unarmed hit: bonus action, 2d8 radiant, +1d8 with a higher slot."),
            uses=Uses(table={2: 1}), restoration="long_rest", granted_spells=("divine-smite",), passive=True,
            roll_options=(DIVINE_SMITE, DIVINE_SMITE_FREE, DIVINE_SMITE_FIEND, DIVINE_SMITE_FIEND_FREE)),
    feature("divine_sense", CK, ED, 3, "Percezione del Divino / Divine Sense (Incanalare Divinità, Paladino 3, pag. 111)",
            ("Percezione del Divino", "Divine Sense"),
            ("Azione bonus, un uso di Incanalare Divinità: per 10 minuti, o finché sei Incapacitato, conosci posizione e tipo di celestiali, immondi e non morti entro 18 m.",
             "Bonus action, one Channel Divinity use: for 10 minutes, or until Incapacitated, you know the location and kind of celestials, fiends and undead within 60 ft."),
            "bonus_action", on_use=OnUse(slot="bonus", spends=POOL, state=StateSpec(
                "divine_sense", rounds=100, ends_on=("incapacitated", "manual"), data={"range_m": 18}))),
    feature("channel_divinity", CK, ED, 3, "Incanalare Divinità / Channel Divinity (Paladino 3, pag. 110)", ("Incanalare Divinità", "Channel Divinity"),
            ("Usi: 2 al 3°, 3 all'11°. Un riposo breve ne rende 1, uno lungo tutti. Ogni effetto, anche di giuramento, ne spende uno; la CD è quella degli incantesimi.",
             "Uses: 2 at 3rd, 3 at 11th. A short rest returns 1, a long rest all. Each effect, oath ones too, spends one; the DC is your spell save DC."),
            "action", uses=Uses(table={3: 2, 11: 3}), restoration="long_rest", short_rest_recovers=1, shared_pool="channel_divinity"),
    feature("paladin_subclass", CK, ED, 3, "Sottoclasse del Paladino / Paladin Subclass (Paladino 3, pag. 111)",
            ("Sottoclasse del Paladino", "Paladin Subclass"),
            ("Al 3° livello si sceglie il Giuramento di Devozione, della Gloria, degli Antichi o di Vendetta.",
             "At level 3 you choose the Oath of Devotion, Glory, the Ancients or Vengeance."),
            no_row=True, covered_by="core/rules/subclasses.py (match_subclass) e il campo sottoclasse della classe"),
    feature("ability_score_improvement", CK, ED, 4, "Aumento dei Punteggi di Caratteristica / Ability Score Improvement (Paladino 4, pag. 111)",
            ("Aumento dei Punteggi di Caratteristica", "Ability Score Improvement"),
            ("Ai livelli 4, 8, 12 e 16: il talento Aumento dei Punteggi o un altro talento di cui hai i requisiti.",
             "At levels 4, 8, 12 and 16: the Ability Score Improvement feat or another feat you qualify for."),
            no_row=True, covered_by="core/rules/level_choices.py (scelta asi); test_asi_at_4_8_12_16_and_the_19th_is_an_epic_boon"),
    feature("extra_attack", CK, ED, 5, "Attacco Extra / Extra Attack (Paladino 5, pag. 111)", ("Attacco Extra", "Extra Attack"),
            ("Due attacchi con l'azione Attacco; non si somma all'Attacco Extra di altre classi.",
             "Two attacks with the Attack action; does not stack with other classes' Extra Attack."), attacks_per_action=2),
    feature("faithful_steed", CK, ED, 5, "Destriero Fedele / Faithful Steed (Paladino 5, pag. 111)", ("Destriero Fedele", "Faithful Steed"),
            ("Trova Destriero sempre preparato; un lancio gratuito per riposo lungo: «Usa» lo lancia con l'azione e crea il destriero fra i compagni.",
             "Find Steed always prepared; one free cast per long rest: \"Use\" casts it with your action and adds the steed to your companions."),
            "action", uses=Uses(table={5: 1}), restoration="long_rest", granted_spells=("find-steed",), on_use=STEED_USE),
    feature("aura_of_protection", CK, ED, 6, "Aura di Protezione / Aura of Protection (Paladino 6, pag. 111)",
            ("Aura di Protezione", "Aura of Protection"),
            ("Tu e gli alleati entro 3 m (9 m dal 18°) sommate il tuo Carisma (minimo +1) ai TS, finché non sei Incapacitato. Il tuo bonus è già nei tuoi TS.",
             "You and allies within 10 ft (30 ft from 18th) add your Charisma (minimum +1) to saves while you are not Incapacitated. Your bonus is already in your saves."),
            modifiers=(Modifier("save", _cha_bonus, when=lambda c: c.roll in SAVE_ROLLS and is_conscious(c.char),
                                source=f"feature:{CK}.aura_of_protection"),),
            aura=AuraSpec("protection", _aura_range, _cha_bonus)),
    feature("abjure_foes", CK, ED, 9, "Abiurare i Nemici / Abjure Foes (Paladino 9, pag. 111)", ("Abiurare i Nemici", "Abjure Foes"),
            ("Azione Magia, un uso di Incanalare Divinità: fino a Carisma (minimo 1) creature entro 18 m fanno un TS Saggezza o sono Spaventate per 1 minuto o fino al danno.",
             "Magic action, one Channel Divinity use: up to Charisma (minimum 1) creatures within 60 ft make a Wisdom save or are Frightened for 1 minute or until damaged."),
            "action", on_use=OnUse(slot="action", spends=POOL, state=_abjure_state, target_effect=_abjure_effect, message=_abjure_message)),
    feature("aura_of_courage", CK, ED, 10, "Aura di Coraggio / Aura of Courage (Paladino 10, pag. 111)", ("Aura di Coraggio", "Aura of Courage"),
            ("Tu e gli alleati nell'Aura di Protezione non potete essere Spaventati, finché non sei Incapacitato.",
             "You and allies in your Aura of Protection cannot be Frightened while you are not Incapacitated."),
            condition_immunities=("frightened",), needs_conscious=True, passive=True, permanent_state=_permanent_note("aura_of_courage")),
    feature("radiant_strikes", CK, ED, 11, "Assalti Radianti / Radiant Strikes (Paladino 11, pag. 111)", ("Assalti Radianti", "Radiant Strikes"),
            ("Ogni colpo con un'arma da mischia o senz'armi infligge 1d8 radiosi in più, raddoppiati al critico.",
             "Every melee weapon or unarmed hit deals an extra 1d8 radiant damage, doubled on a critical."),
            roll_options=(RADIANT_STRIKES,), passive=True),
    feature("restoring_touch", CK, ED, 14, "Tocco Ristoratore / Restoring Touch (Paladino 14, pag. 111)", ("Tocco Ristoratore", "Restoring Touch"),
            ("Con Imposizione delle Mani togli anche Accecato, Affascinato, Assordato, Spaventato, Paralizzato, Stordito: 5 punti ciascuno.",
             "With Lay On Hands you also remove Blinded, Charmed, Deafened, Frightened, Paralyzed, Stunned: 5 points each."),
            no_row=True, covered_by=f"{LAY_ON_HANDS} (interruttori per condizione dal 14°); test_restoring_touch_adds_six_conditions_at_level_14"),
    feature("aura_expansion", CK, ED, 18, "Espansione dell'Aura / Aura Expansion (Paladino 18, pag. 111)", ("Espansione dell'Aura", "Aura Expansion"),
            ("Dal 18° livello l'Aura di Protezione ha raggio 9 m.", "From 18th level the Aura of Protection has a 30 ft radius."),
            no_row=True, covered_by=f"{CK}.aura_of_protection (_aura_range); test_the_aura_range_is_3_m_and_9_m_from_level_18"),
    feature("epic_boon", CK, ED, 19, "Dono Epico / Epic Boon (Paladino 19, pag. 111)", ("Dono Epico", "Epic Boon"),
            ("Al 19° livello un talento Dono Epico o un altro talento di cui hai i requisiti; consigliato Dono della Vista Veritiera.",
             "At 19th level an Epic Boon feat or another feat you qualify for; Boon of Truesight is recommended."),
            no_row=True, covered_by="core/rules/level_choices.py (scelta epic_boon); test_asi_at_4_8_12_16_and_the_19th_is_an_epic_boon"),
    feature("multiclassing", CK, ED, 1, "Multiclasse: Paladino / Multiclassing: Paladin (Regole di multiclasse, pag. 44)",
            ("Multiclasse: Paladino", "Multiclassing: Paladin"),
            ("Requisito Forza 13 e Carisma 13. Da multiclasse: d10, armi da guerra, armature leggere e medie, scudi; slot a metà livelli per eccesso.",
             "Requires Strength 13 and Charisma 13. As a multiclass: d10, martial weapons, light and medium armor, shields; half-level slots rounded up."),
            no_row=True, covered_by=f"{_ROWS} e webapp/src/data/multiclassPrereqs.ts (D2); test_multiclass_slots_count_half_the_paladin_levels_rounded_up"),
)

from core.rules.catalog.y2024.paladin_oaths import SUBCLASS_ROWS  # noqa: E402  (parte B, dopo le definizioni comuni)

FEATURES = BASE_ROWS + SUBCLASS_ROWS

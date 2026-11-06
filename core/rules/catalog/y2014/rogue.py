"""Ladro 2014 e i suoi archetipi: Furfante, Assassino e Mistificatore Arcano.

Valori dalla scheda ``docs/superpowers/rules/2014/classes/rogue.md``; i testi sono nostri, mai quelli del manuale.
L'Attacco Furtivo è una conferma al danno (dopo il colpo); Assassinare e Colpo Mortale sono conferme prima e dopo il tiro;
Azione Scaltra è un «Usa» con la scelta fra le azioni ammesse (Mani Veloci ne aggiunge tre). Gli incantesimi del Mistificatore
Arcano vivono in ``core/rules/spellcasting.py``; il secondo turno dei Riflessi da Furfante è una riga dell'incontro
(``api/services/thiefs_reflexes.py``).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from core.rules.catalog._common import feature, skill_label, state_on
from core.rules.catalog.y2014.bard import _expertise_options
from core.rules.catalog.y2014.fighter import _save_spell, _weapon_in_hand
from core.rules.states import STOLEN_SPELL, begin_state
from core.rules.types import (
    ChoiceSpec, Cost, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, TargetEffect, Uses, UseChoice, UseText,
    UseToggle,
)
from core.rules.weapons import has_property

ED, CK = "2014", "rogue"
EVASION_STATE = "evasion"
THIEF_SPELL, THIEF_SPELL_ROUNDS = f"{CK}.spell_thief", 4800  # 8 ore di round da 6 secondi
IDENTITY_COST, NAME_MAX = 25, 80
# azioni di Azione Scaltra; Mani Veloci (Furfante 3) aggiunge le ultime tre
CUNNING_BASE = ("dash", "disengage", "hide")
CUNNING_FAST_HANDS = ("sleight_of_hand", "thieves_tools", "use_object")
_CUNNING_LABELS = {
    "dash": ("Scatto", "Dash"), "disengage": ("Disimpegno", "Disengage"), "hide": ("Nascondersi", "Hide"),
    "sleight_of_hand": ("Rapidità di Mano (prova di Destrezza)", "Sleight of Hand (Dexterity check)"),
    "thieves_tools": ("Arnesi da scasso su una serratura o una trappola", "Thieves' tools on a lock or trap"),
    "use_object": ("Usare un Oggetto", "Use an Object"),
}


def _say(it: str, en: str):
    return lambda _ctx, _inputs: {"it": it, "en": en}


def _permanent_note(key: str) -> StateSpec:
    """Lo stato sempre attivo che porta il testo di un privilegio a GM e gruppo (R36)."""
    return StateSpec(key, ends_on=("manual",), data={"others": [f"{CK}.{key}"], "permanent": True})


def _dex_mod(ctx: RuleContext) -> int:
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    return effective_ability_mod(ctx.char, "dexterity")


def _knows_mage_hand(ctx: RuleContext) -> bool:
    return any(s.srd_index == "mage-hand" or (s.name or "").strip().lower() in ("mano magica", "mage hand")
               for s in ctx.char.spells or [])


# ---------------------------------------------------------------------------
# Maestria
# ---------------------------------------------------------------------------

EXPERTISE = ChoiceSpec(group="expertise", levels={1: 2, 6: 4}, options=_expertise_options, label=skill_label, grants="expert")


# ---------------------------------------------------------------------------
# Attacco Furtivo
# ---------------------------------------------------------------------------

def _finesse_or_ranged(ctx: RuleContext) -> bool:
    from core.game.item_bonuses import item_meta  # import locale: item_bonuses usa il catalogo
    return _weapon_in_hand(ctx) and (has_property(ctx.item, "finesse") or item_meta(ctx.item).get("weapon_type", "melee") == "ranged")


def _not_at_disadvantage(ctx: RuleContext) -> bool:
    """Con svantaggio al tiro per colpire un alleato accanto al bersaglio non basta: il modo lo dice l'attacco in sospeso."""
    pending = (ctx.turn or {}).get("pending_attack") or {}
    return (pending.get("result") or {}).get("mode") != "disadvantage"


def _sneak_dice(ctx: RuleContext, _inputs: dict) -> str:
    return f"{(ctx.class_level + 1) // 2}d6"


SNEAK_ATTACK = RollOptionSpec(
    key=f"{CK}.sneak_attack", phase="after_hit", rolls=("attack",), once_per_turn=True, extra_dice=_sneak_dice,
    available=lambda c: _finesse_or_ranged(c) and _not_at_disadvantage(c),
    label={"it": "Attacco Furtivo: hai vantaggio sul tiro, o un nemico del bersaglio (non incapacitato) è entro 1,5 m da esso e non hai svantaggio? Danni extra (una volta per turno)",
           "en": "Sneak Attack: do you have advantage on the roll, or is an enemy of the target (not incapacitated) within 5 ft of it and you have no disadvantage? Extra damage (once per turn)"})


# ---------------------------------------------------------------------------
# Azione Scaltra
# ---------------------------------------------------------------------------

def _cunning_options(ctx: RuleContext) -> list[str]:
    fast_hands = ctx.class_row.subclass_key == "thief" and ctx.class_level >= 3
    return [*CUNNING_BASE, *(CUNNING_FAST_HANDS if fast_hands else ())]


def _cunning_label(key: str) -> dict:
    it, en = _CUNNING_LABELS[key]
    return {"it": it, "en": en}


CUNNING_ACTION_USE = OnUse(
    slot="bonus", notes=lambda _c, params: [f"cunning_{params['action']}"],
    choices=(UseChoice("action", {"it": "Azione bonus", "en": "Bonus action"}, _cunning_options, _cunning_label),))


# ---------------------------------------------------------------------------
# Schivata Prodigiosa, Elusione
# ---------------------------------------------------------------------------

UNCANNY_DODGE = RollOptionSpec(
    key=f"{CK}.uncanny_dodge", phase="damage_in", rolls=("damage_taken",), slot="reaction", multiplier=0.5, offered_on_damage=False,
    label={"it": "Schivata Prodigiosa: un attaccante che vedi ti ha colpito? Reazione, dimezza i danni dell'attacco",
           "en": "Uncanny Dodge: did an attacker you can see hit you? Reaction, halves the damage of the attack"})


def _evasion_started(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    begin_state(ctx.char, StateSpec(EVASION_STATE, rounds=1, ends_on=("new_turn", "manual")), f"{CK}.evasion", "Elusione")


EVASION_SAVE = RollOptionSpec(
    key=f"{CK}.evasion", phase="before", rolls=("save",), available=lambda c: c.ability == "dexterity", on_confirm=_evasion_started,
    label={"it": "Elusione: l'effetto dimezza i danni con un TS Destrezza?", "en": "Evasion: does the effect halve damage on a Dexterity save?"},
    effect=_say("Elusione: se superi il TS non subisci danni, se lo fallisci subisci la metà. Applica l'esito al danno.",
                "Evasion: if you pass the save you take no damage, on a failure you take half. Apply the outcome to the damage."))
EVASION_SUCCESS = RollOptionSpec(
    key=f"{CK}.evasion_success", phase="damage_in", rolls=("damage_taken",), multiplier=0, group="evasion",
    cost=Cost(state_key=EVASION_STATE), available=lambda c: state_on(c, EVASION_STATE),
    label={"it": "Elusione: hai superato il TS, nessun danno", "en": "Evasion: you passed the save, no damage"})
EVASION_FAILED = RollOptionSpec(
    key=f"{CK}.evasion_failed", phase="damage_in", rolls=("damage_taken",), multiplier=0.5, group="evasion",
    cost=Cost(state_key=EVASION_STATE), available=lambda c: state_on(c, EVASION_STATE),
    label={"it": "Elusione: hai fallito il TS, metà del danno", "en": "Evasion: you failed the save, half damage"})


# ---------------------------------------------------------------------------
# Dote Affidabile, Mente Sfuggente, Percezione Cieca
# ---------------------------------------------------------------------------

def _proficient_skill_check(ctx: RuleContext) -> bool:
    """Una prova con una competenza (anche con la maestria): la mezza competenza e la prova pura non contano."""
    level = (ctx.char.skills or {}).get(ctx.skill)
    return ctx.roll == "skill" and (level is True or level == 1 or level == "expert")


def _lacks_wisdom_save_proficiency(ctx: RuleContext) -> bool:
    return ctx.roll in ("save", "concentration") and ctx.ability == "wisdom" and not (ctx.char.saving_throws or {}).get("wisdom")


def _can_hear(ctx: RuleContext) -> bool:
    return not (ctx.char.conditions or {}).get("deafened")


# ---------------------------------------------------------------------------
# Colpo di Fortuna
# ---------------------------------------------------------------------------

STROKE_OF_LUCK = RollOptionSpec(
    key=f"{CK}.stroke_of_luck", phase="after_roll", after="succeed", rolls=("attack", "skill"), cost=Cost(feature_key=f"{CK}.stroke_of_luck"),
    label={"it": "Colpo di Fortuna: l'attacco ha mancato un bersaglio nella gittata, o la prova è fallita? Diventa un colpo a segno, o il d20 vale 20",
           "en": "Stroke of Luck: did the attack miss a target in range, or did the check fail? It becomes a hit, or the d20 counts as 20"})


# ---------------------------------------------------------------------------
# Furfante
# ---------------------------------------------------------------------------

SUPREME_SNEAK = RollOptionSpec(
    key=f"{CK}.supreme_sneak_advantage", phase="before", rolls=("skill",), mode="advantage", available=lambda c: c.skill == "stealth",
    label={"it": "Furtività Suprema: ti sei mosso al massimo di metà della velocità in questo turno? Vantaggio a Furtività",
           "en": "Supreme Sneak: did you move at most half your speed this turn? Advantage on Stealth"})


# ---------------------------------------------------------------------------
# Assassino
# ---------------------------------------------------------------------------

ASSASSINATE_ADVANTAGE = RollOptionSpec(
    key=f"{CK}.assassinate_advantage", phase="before", rolls=("attack",), mode="advantage",
    label={"it": "Assassinare: il bersaglio non ha ancora fatto un turno in questo combattimento? Vantaggio al tiro per colpire",
           "en": "Assassinate: has the target not yet taken a turn in this combat? Advantage on the attack roll"})
ASSASSINATE_CRIT = RollOptionSpec(
    key=f"{CK}.assassinate_crit", phase="before", rolls=("attack",), force_crit=True,
    label={"it": "Assassinare: il bersaglio è sorpreso? Se colpisci, è un colpo critico",
           "en": "Assassinate: is the target surprised? If you hit, it is a critical hit"})
IMPOSTOR_ADVANTAGE = RollOptionSpec(
    key=f"{CK}.impostor_advantage", phase="before", rolls=("skill",), mode="advantage", available=lambda c: c.skill == "deception",
    label={"it": "Impostore: una creatura sospettosa dubita della tua imitazione (dopo 3 ore di studio)? Vantaggio a Inganno",
           "en": "Impostor: does a suspicious creature doubt your imitation (after 3 hours of study)? Advantage on Deception"})


def _death_strike_dc(ctx: RuleContext) -> int:
    return 8 + ctx.char.proficiency_bonus + _dex_mod(ctx)


def _death_strike_effect(ctx: RuleContext, _inputs: dict) -> dict:
    dc = _death_strike_dc(ctx)
    return {"it": f"Colpo Mortale: se colpisci, il bersaglio sorpreso fa un TS Costituzione CD {dc}. Se fallisce, conferma «TS fallito» dopo il colpo: i danni raddoppiano.",
            "en": f"Death Strike: if you hit, the surprised target makes a DC {dc} Constitution save. If it fails, confirm «save failed» after the hit: the damage is doubled."}


DEATH_STRIKE = RollOptionSpec(
    key=f"{CK}.death_strike", phase="before", rolls=("attack",), effect=_death_strike_effect,
    label={"it": "Colpo Mortale: il bersaglio è sorpreso? Se colpisci fa un TS Costituzione (CD 8 + Destrezza + competenza)",
           "en": "Death Strike: is the target surprised? If you hit it makes a Constitution save (DC 8 + Dexterity + proficiency)"})
DEATH_STRIKE_FAILED = RollOptionSpec(
    key=f"{CK}.death_strike_failed", phase="after_hit", rolls=("attack",), multiplier=2, needs=DEATH_STRIKE.key,
    label={"it": "Colpo Mortale: il bersaglio sorpreso ha fallito il TS Costituzione? I danni dell'attacco raddoppiano",
           "en": "Death Strike: did the surprised target fail its Constitution save? The damage of the attack is doubled"})


def _identity_title(params: dict) -> str:
    return f"Identità falsa: {params['identity'].strip()}"


def _identity_check(ctx: RuleContext, params: dict) -> tuple[int, str] | None:
    return (409, "identity_exists") if _identity_title(params) in (ctx.char.notes or {}) else None


def _identity_written(ctx: RuleContext, params: dict) -> None:
    notes = dict(ctx.char.notes or {})
    notes[_identity_title(params)] = {
        "body": f"Identità falsa creata con Maestro Infiltrato: 7 giorni di preparazione e {IDENTITY_COST} mo. / "
                f"False identity made with Infiltration Expertise: 7 days of preparation and {IDENTITY_COST} gp.",
        "created_at": datetime.now(timezone.utc).isoformat(), "tags": ["identity"]}
    ctx.char.notes = notes


INFILTRATION_USE = OnUse(
    gold_cost=IDENTITY_COST, check=_identity_check, effect=_identity_written,
    texts=(UseText("identity", {"it": "Nome dell'identità falsa", "en": "Name of the false identity"}, max_len=NAME_MAX),))


# ---------------------------------------------------------------------------
# Mistificatore Arcano
# ---------------------------------------------------------------------------

MAGICAL_AMBUSH_CAST = RollOptionSpec(
    key=f"{CK}.magical_ambush_cast", phase="before", rolls=("cast",), available=lambda c: c.spell is not None and _save_spell(c.spell),
    label={"it": "Imboscata Magica: sei nascosto dal bersaglio dell'incantesimo? Svantaggio ai suoi TS contro di esso, fino a fine turno",
           "en": "Magical Ambush: are you hidden from the spell's target? Disadvantage on its saves against it until the end of the turn"},
    effect=_say("Il bersaglio ha svantaggio a ogni TS contro questo incantesimo, fino alla fine del turno.",
                "The target has disadvantage on every saving throw against this spell until the end of the turn."),
    target_effect=lambda _c, _i: TargetEffect(condition="custom:magical_ambush", ends_at={"anchor": "source", "edge": "end", "count": 1}))

VERSATILE_TRICKSTER_ADVANTAGE = RollOptionSpec(
    key=f"{CK}.versatile_trickster_advantage", phase="before", rolls=("attack",), mode="advantage",
    available=lambda c: state_on(c, "versatile_trickster"),
    label={"it": "Ingannatore Versatile: il bersaglio è la creatura scelta, entro 1,5 m dalla mano spettrale? Vantaggio al tiro per colpire",
           "en": "Versatile Trickster: is the target the chosen creature, within 5 ft of the spectral hand? Advantage on the attack roll"})


def _max_stealable_level(ctx: RuleContext) -> int:
    return max((s.level for s in ctx.char.spell_slots or [] if s.total), default=0)


def _stolen_levels(ctx: RuleContext) -> list[str]:
    return [str(level) for level in range(1, _max_stealable_level(ctx) + 1)]


def _thief_check(ctx: RuleContext, params: dict) -> tuple[int, str] | None:
    """Con il furto riuscito servono il livello dell'incantesimo (entro quelli che il ladro può lanciare)."""
    return (422, "invalid_choice") if params.get("stolen") and params.get("spell_level") is None else None


def _thief_steal(ctx: RuleContext, params: dict) -> None:
    """Il TS del lanciatore è fallito: l'incantesimo diventa conosciuto per 8 ore, con i soli slot del ladro. Lo stato porta
    il segno dell'incantesimo, e quando finisce (durata, riposo lungo, a mano) la scheda lo toglie."""
    if not params.get("stolen"):
        return
    from core.db.models import Spell  # import locale: i modelli non servono al resto del catalogo
    tag = f"{STOLEN_SPELL}{uuid.uuid4().hex[:12]}"
    ctx.char.spells.append(Spell(
        character_id=ctx.char.id, name=params["spell"].strip(), level=int(params["spell_level"]), srd_index=tag,
        class_id=ctx.class_row.id, is_prepared=True, always_prepared=True))
    begin_state(ctx.char, StateSpec("spell_thief", rounds=THIEF_SPELL_ROUNDS, ends_on=("manual",),
                                    data={"stolen_spell": tag, "others": [THIEF_SPELL]}), THIEF_SPELL, "Ladro di Incantesimi")


SPELL_THIEF_USE = OnUse(
    slot="reaction", check=_thief_check, effect=_thief_steal,
    toggles=(UseToggle("stolen", {"it": "Il TS del lanciatore è fallito: ruba l'incantesimo", "en": "The caster's save failed: steal the spell"}),),
    choices=(UseChoice("spell_level", {"it": "Livello dell'incantesimo rubato", "en": "Level of the stolen spell"}, _stolen_levels,
                       lambda k: {"it": f"{k}° livello", "en": f"Level {k}"}, optional=True),),
    texts=(UseText("spell", {"it": "Nome dell'incantesimo rubato", "en": "Name of the stolen spell"}, max_len=NAME_MAX, optional=True,
                   required=lambda params: bool(params.get("stolen"))),))


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

def _thief(key: str, level: int, title: str, name: tuple[str, str], summary: tuple[str, str], action_type: str | None = None, **kw: Any):
    return feature(key, CK, ED, level, title, name, summary, action_type, subclass="thief", **kw)


def _assassin(key: str, level: int, title: str, name: tuple[str, str], summary: tuple[str, str], action_type: str | None = None, **kw: Any):
    return feature(key, CK, ED, level, title, name, summary, action_type, subclass="assassin", **kw)


def _trickster(key: str, level: int, title: str, name: tuple[str, str], summary: tuple[str, str], action_type: str | None = None, **kw: Any):
    return feature(key, CK, ED, level, title, name, summary, action_type, subclass="arcane_trickster", **kw)


FEATURES = (
    feature("hit_points", CK, ED, 1, "Punti Ferita / Hit Points (Ladro 1, pag. 77)", ("Punti Ferita", "Hit Points"),
            ("Dado vita d8; al 1° livello 8 + Costituzione, poi d8 (o 5) + Costituzione.",
             "Hit die d8; level 1 gives 8 + Constitution, then d8 (or 5) + Constitution."), no_row=True,
            covered_by="api/routers/classes.py create_class_for_character e total_base_hp; test_hit_points_use_the_d8_and_follow_constitution"),
    feature("proficiencies", CK, ED, 1, "Competenze / Proficiencies (Ladro 1, pag. 77)", ("Competenze", "Proficiencies"),
            ("Armature leggere, armi semplici, balestra a mano, spada lunga, stocco, spada corta, arnesi da scasso, TS Destrezza e Intelligenza, 4 abilità su 11.",
             "Light armor, simple weapons, hand crossbow, longsword, rapier, shortsword, thieves' tools, Dexterity and Intelligence saves, 4 skills out of 11."),
            no_row=True, covered_by="core/rules/proficiencies.py (class_proficiencies) e la scelta ClassSkillChoice; "
                                    "test_class_proficiencies_first_class_and_multiclass"),
    feature("equipment", CK, ED, 1, "Equipaggiamento / Equipment (Ladro 1, pag. 78)", ("Equipaggiamento", "Equipment"),
            ("Dotazione iniziale: stocco o spada corta, arco corto con frecce o spada corta, dotazione a scelta, armatura di cuoio, due pugnali, arnesi da scasso.",
             "Starting gear: a rapier or shortsword, a shortbow with arrows or a shortsword, a pack of your choice, leather armor, two daggers, thieves' tools."),
            no_row=True, covered_by="lavori-successivi"),
    feature("expertise", CK, ED, 1, "Maestria / Expertise (Ladro 1, pag. 78)", ("Maestria", "Expertise"),
            ("Al 1° e al 6° livello due abilità in cui sei competente (anche gli arnesi da scasso) hanno il bonus di competenza doppio.",
             "At 1st and 6th level two skills you are proficient in (or thieves' tools) get double your proficiency bonus."),
            choices=(EXPERTISE,)),
    feature("sneak_attack", CK, ED, 1, "Attacco Furtivo / Sneak Attack (Ladro 1, pag. 78)", ("Attacco Furtivo", "Sneak Attack"),
            ("Una volta per turno, danni extra con arma accurata o a distanza: 1d6, 2d6 al 3°, poi +1d6 ogni due livelli, 10d6 al 19°. Serve vantaggio o un nemico del bersaglio accanto.",
             "Once per turn, extra damage with a finesse or ranged weapon: 1d6, 2d6 at 3rd, then +1d6 every two levels, 10d6 at 19th. Needs advantage or an enemy of the target next to it."),
            roll_options=(SNEAK_ATTACK,), passive=True),
    feature("thieves_cant", CK, ED, 1, "Gergo Ladresco / Thieves' Cant (Ladro 1, pag. 78)", ("Gergo Ladresco", "Thieves' Cant"),
            ("Conosci il Gergo Ladresco, il codice segreto dei ladri.", "You know Thieves' Cant, the secret code of thieves."),
            no_row=True, covered_by="core/rules/proficiencies.py (languages della classe); test_thieves_cant_is_among_the_languages"),
    feature("cunning_action", CK, ED, 2, "Azione Scaltra / Cunning Action (Ladro 2, pag. 78)", ("Azione Scaltra", "Cunning Action"),
            ("Azione bonus in ogni tuo turno di combattimento per Scatto, Disimpegno o Nascondersi.",
             "A bonus action on each of your combat turns for Dash, Disengage or Hide."),
            "bonus_action", on_use=CUNNING_ACTION_USE),
    feature("roguish_archetype", CK, ED, 3, "Archetipo Ladresco / Roguish Archetype (Ladro 3, pag. 78)", ("Archetipo Ladresco", "Roguish Archetype"),
            ("Al 3° livello si sceglie Furfante, Assassino o Mistificatore Arcano: privilegi ai livelli 3, 9, 13 e 17.",
             "At 3rd level you choose Thief, Assassin or Arcane Trickster: features at levels 3, 9, 13 and 17."),
            no_row=True, covered_by="core/rules/subclasses.py (match_subclass) e il campo sottoclasse della classe"),
    feature("ability_score_improvement", CK, ED, 4,
            "Aumento dei Punteggi di Caratteristica / Ability Score Improvement (Ladro 4, pag. 78)",
            ("Aumento dei Punteggi di Caratteristica", "Ability Score Improvement"),
            ("Ai livelli 4, 8, 10, 12, 16 e 19: +2 a un punteggio o +1 a due, oppure un talento; massimo 20.",
             "At levels 4, 8, 10, 12, 16 and 19: +2 to one score or +1 to two, or a feat; maximum 20."), no_row=True,
            covered_by="core/rules/level_choices.py (scelta asi); test_asi_choices_are_pending_at_levels_4_8_10_12_16_and_19"),
    feature("uncanny_dodge", CK, ED, 5, "Schivata Prodigiosa / Uncanny Dodge (Ladro 5, pag. 78)", ("Schivata Prodigiosa", "Uncanny Dodge"),
            ("Reazione: un attaccante che vedi ti colpisce, dimezzi i danni di quell'attacco.",
             "Reaction: an attacker you can see hits you, you halve the damage of that attack."),
            "reaction", roll_options=(UNCANNY_DODGE,), passive=True),
    feature("evasion", CK, ED, 7, "Elusione / Evasion (Ladro 7, pag. 78)", ("Elusione", "Evasion"),
            ("Nei TS Destrezza per dimezzare i danni: nessun danno se superi, metà se fallisci.",
             "On Dexterity saves for half damage: no damage on a success, half on a failure."),
            roll_options=(EVASION_SAVE, EVASION_SUCCESS, EVASION_FAILED), passive=True),
    feature("reliable_talent", CK, ED, 11, "Dote Affidabile / Reliable Talent (Ladro 11, pag. 78)", ("Dote Affidabile", "Reliable Talent"),
            ("Nelle prove con un'abilità in cui sei competente, un d20 che dà 9 o meno conta come 10.",
             "On checks with a skill you are proficient in, a d20 roll of 9 or lower counts as 10."),
            modifiers=(Modifier("min_d20", 10, when=_proficient_skill_check, source=f"feature:{CK}.reliable_talent"),), passive=True),
    feature("blindsense", CK, ED, 14, "Percezione Cieca / Blindsense (Ladro 14, pag. 78)", ("Percezione Cieca", "Blindsense"),
            ("Se senti, conosci la posizione di ogni creatura nascosta o invisibile entro 3 m. Compare fra i sensi della scheda.",
             "If you can hear, you know the location of any hidden or invisible creature within 10 ft. It shows among the sheet's senses."),
            modifiers=(Modifier("sense:blindsense", 10, when=_can_hear, source=f"feature:{CK}.blindsense"),), passive=True),
    feature("slippery_mind", CK, ED, 15, "Mente Sfuggente / Slippery Mind (Ladro 15, pag. 78)", ("Mente Sfuggente", "Slippery Mind"),
            ("Competenza nei tiri salvezza su Saggezza.", "Proficiency in Wisdom saving throws."),
            modifiers=(Modifier("save", lambda c: c.char.proficiency_bonus, when=_lacks_wisdom_save_proficiency,
                                source=f"feature:{CK}.slippery_mind"),), passive=True),
    feature("elusive", CK, ED, 18, "Inafferrabile / Elusive (Ladro 18, pag. 78)", ("Inafferrabile", "Elusive"),
            ("Nessun tiro per colpire contro di te ha vantaggio, finché non sei incapacitato.",
             "No attack roll against you has advantage while you are not incapacitated."),
            passive=True, permanent_state=_permanent_note("elusive"), suspended_when_incapacitated=True),
    feature("stroke_of_luck", CK, ED, 20, "Colpo di Fortuna / Stroke of Luck (Ladro 20, pag. 79)", ("Colpo di Fortuna", "Stroke of Luck"),
            ("Un attacco che manca diventa un colpo a segno, o un d20 di una prova fallita vale 20. Un uso per riposo breve o lungo.",
             "A missed attack becomes a hit, or the d20 of a failed check counts as 20. One use per short or long rest."),
            uses=Uses(table={20: 1}), restoration="short_rest", roll_options=(STROKE_OF_LUCK,)),

    # Furfante
    _thief("fast_hands", 3, "Mani Veloci / Fast Hands (Furfante 3, pag. 79)", ("Mani Veloci", "Fast Hands"),
           ("Azione Scaltra vale anche per una prova di Rapidità di Mano, per usare arnesi da scasso su una serratura o una trappola, o per Usare un Oggetto.",
            "Cunning Action also covers a Sleight of Hand check, using thieves' tools on a lock or trap, or the Use an Object action."),
           "bonus_action", passive=True),
    _thief("second_story_work", 3, "Lavoro al Secondo Piano / Second-Story Work (Furfante 3, pag. 79)",
           ("Lavoro al Secondo Piano", "Second-Story Work"),
           ("Scalare non costa movimento extra; il salto in lungo con rincorsa aumenta di 30 cm per punto di Destrezza (la scheda mostra il bonus).",
            "Climbing costs no extra movement; a running long jump grows by 1 ft per Dexterity modifier point (the sheet shows the bonus)."),
           modifiers=(Modifier("jump_bonus", lambda c: max(0, _dex_mod(c)), when=lambda c: c.roll is None,
                               source=f"feature:{CK}.second_story_work"),), passive=True),
    _thief("supreme_sneak", 9, "Furtività Suprema / Supreme Sneak (Furfante 9, pag. 79)", ("Furtività Suprema", "Supreme Sneak"),
           ("Vantaggio alle prove di Furtività se ti muovi al massimo di metà della velocità nel turno.",
            "Advantage on Stealth checks if you move at most half your speed on the turn."),
           roll_options=(SUPREME_SNEAK,), passive=True),
    _thief("use_magic_device", 13, "Usare Oggetto Magico / Use Magic Device (Furfante 13, pag. 79)",
           ("Usare Oggetto Magico", "Use Magic Device"),
           ("Ignori ogni requisito di classe, razza e livello per usare oggetti magici: l'app non ne controlla nessuno.",
            "You ignore every class, race and level requirement for using magic items: the app checks none."),
           passive=True),
    _thief("thiefs_reflexes", 17, "Riflessi da Furfante / Thief's Reflexes (Furfante 17, pag. 79)",
           ("Riflessi da Furfante", "Thief's Reflexes"),
           ("Nel primo round di ogni combattimento hai due turni: all'iniziativa e all'iniziativa meno 10 (non se sei sorpreso). L'incontro aggiunge il secondo turno.",
            "In the first round of each combat you take two turns: at your initiative and at your initiative minus 10 (not if surprised). The encounter adds the second turn."),
           passive=True),

    # Assassino
    _assassin("bonus_proficiencies", 3, "Competenze Bonus / Bonus Proficiencies (Assassino 3, pag. 79)",
              ("Competenze Bonus", "Bonus Proficiencies"),
              ("Competenza nel kit da camuffamento e nel kit da avvelenatore, aggiunti alle competenze della scheda.",
               "Proficiency with the disguise kit and the poisoner's kit, added to the sheet's proficiencies."),
              proficiency_grants={"tools": ("disguise_kit", "poisoners_kit")}, passive=True),
    _assassin("assassinate", 3, "Assassinare / Assassinate (Assassino 3, pag. 79)", ("Assassinare", "Assassinate"),
              ("Vantaggio ai tiri per colpire contro chi non ha ancora fatto un turno nel combattimento; ogni colpo a segno su una creatura sorpresa è critico.",
               "Advantage on attack rolls against a creature that has not taken a turn yet in the combat; any hit on a surprised creature is a critical hit."),
              roll_options=(ASSASSINATE_ADVANTAGE, ASSASSINATE_CRIT), passive=True),
    _assassin("infiltration_expertise", 9, "Maestro Infiltrato / Infiltration Expertise (Assassino 9, pag. 79)",
              ("Maestro Infiltrato", "Infiltration Expertise"),
              ("Crei un'identità falsa con 7 giorni e 25 mo: «Usa» scala l'oro e ne scrive il nome nelle note. Non puoi copiare l'identità di un altro.",
               "You make a false identity with 7 days and 25 gp: «Use» spends the gold and writes its name in the notes. You cannot copy someone else's identity."),
              "special", on_use=INFILTRATION_USE),
    _assassin("impostor", 13, "Impostore / Impostor (Assassino 13, pag. 79)", ("Impostore", "Impostor"),
              ("Dopo 3 ore di studio imiti una persona in modo convincente; se una creatura dubita hai vantaggio alle prove di Inganno per non farti scoprire.",
               "After 3 hours of study you imitate a person convincingly; if a creature doubts you, you have advantage on Deception checks to avoid being found out."),
              roll_options=(IMPOSTOR_ADVANTAGE,), passive=True),
    _assassin("death_strike", 17, "Colpo Mortale / Death Strike (Assassino 17, pag. 79)", ("Colpo Mortale", "Death Strike"),
              ("Colpendo una creatura sorpresa, fa un TS Costituzione CD 8 + Destrezza + competenza: se fallisce i danni dell'attacco raddoppiano.",
               "Hitting a surprised creature, it makes a Constitution save DC 8 + Dexterity + proficiency: on a failure the attack's damage is doubled."),
              roll_options=(DEATH_STRIKE, DEATH_STRIKE_FAILED), passive=True, dc_ability="dexterity"),

    # Mistificatore Arcano
    _trickster("spellcasting", 3, "Incantesimi / Spellcasting (Mistificatore Arcano 3, pag. 80)", ("Incantesimi", "Spellcasting"),
               ("Terzo di incantatore con Intelligenza, lista del mago. Trucchetti 3 (4 al 10°); conosciuti da 3 a 13; quasi tutti di ammaliamento o illusione.",
                "Third-caster with Intelligence, wizard list. Cantrips 3 (4 at 10th); known spells 3 to 13; nearly all enchantment or illusion."),
               no_row=True, covered_by="core/rules/spellcasting.py (known_limits, slots_for, caster_stats, school_limit); "
                                       "test_arcane_trickster_slots_cantrips_and_known_follow_the_table"),
    _trickster("mage_hand_legerdemain", 3, "Gioco di Prestigio della Mano Magica / Mage Hand Legerdemain (Mistificatore Arcano 3, pag. 80)",
               ("Gioco di Prestigio della Mano Magica", "Mage Hand Legerdemain"),
               ("Con mano magica la rendi invisibile e le fai riporre o estrarre oggetti e usare arnesi da scasso. Azione bonus per controllarla; prova contrapposta Rapidità di Mano contro Percezione.",
                "With mage hand you make it invisible and have it stow or retrieve objects and use thieves' tools. A bonus action controls it; contested Sleight of Hand against Perception."),
               "bonus_action", on_use=OnUse(slot="bonus", available=_knows_mage_hand, notes=lambda _c, _p: ["mage_hand_control"])),
    _trickster("magical_ambush", 9, "Imboscata Magica / Magical Ambush (Mistificatore Arcano 9, pag. 80)",
               ("Imboscata Magica", "Magical Ambush"),
               ("Lanciando un incantesimo su una creatura da cui sei nascosto, ha svantaggio ai TS contro quell'incantesimo nel turno.",
                "When you cast a spell on a creature you are hidden from, it has disadvantage on saves against that spell this turn."),
               roll_options=(MAGICAL_AMBUSH_CAST,), passive=True),
    _trickster("versatile_trickster", 13, "Ingannatore Versatile / Versatile Trickster (Mistificatore Arcano 13, pag. 80)",
               ("Ingannatore Versatile", "Versatile Trickster"),
               ("Azione bonus: scegli una creatura entro 1,5 m dalla mano spettrale di mano magica: vantaggio ai tiri per colpire contro di essa fino a fine turno.",
                "Bonus action: choose a creature within 5 ft of your mage hand's spectral hand: advantage on attack rolls against it until the end of the turn."),
               "bonus_action", roll_options=(VERSATILE_TRICKSTER_ADVANTAGE,),
               on_use=OnUse(slot="bonus", available=_knows_mage_hand,
                            state=StateSpec("versatile_trickster", rounds=1, ends_on=("new_turn", "turn_end", "manual"),
                                            data={"others": [f"{CK}.versatile_trickster"]}))),
    _trickster("spell_thief", 17, "Ladro di Incantesimi / Spell Thief (Mistificatore Arcano 17, pag. 80)",
               ("Ladro di Incantesimi", "Spell Thief"),
               ("Reazione, una volta per riposo lungo: il lanciatore fa un TS contro la tua CD; se fallisce annulli l'effetto e ruba l'incantesimo per 8 ore.",
                "Reaction, once per long rest: the caster makes a save against your DC; on a failure you cancel the effect and steal the spell for 8 hours."),
               "reaction", uses=Uses(table={17: 1}), restoration="long_rest", on_use=SPELL_THIEF_USE, dc_ability="intelligence"),

    feature("multiclassing", CK, ED, 1, "Multiclasse: Ladro / Multiclassing: Rogue (Manuale del Giocatore, pag. 163)",
            ("Multiclasse: Ladro", "Multiclassing: Rogue"),
            ("Requisito Destrezza 13. Da multiclasse: armature leggere, arnesi da scasso, 1 abilità; il Mistificatore Arcano conta un terzo dei livelli per gli slot.",
             "Requires Dexterity 13. As a multiclass: light armor, thieves' tools, 1 skill; the Arcane Trickster counts a third of its levels for slots."),
            no_row=True, covered_by="core/rules/proficiencies.py (as_multiclass) e webapp/src/data/multiclassPrereqs.ts (D2); "
                                    "test_the_trickster_slots_add_a_third_of_the_rogue_levels_to_other_casters"),
)

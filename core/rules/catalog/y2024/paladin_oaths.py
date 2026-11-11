"""I quattro giuramenti del Paladino 2024: Devozione, Gloria, Antichi, Vendetta.

Valori dalla scheda ``docs/superpowers/rules/2024/classes/paladin.md``; i testi sono nostri, mai quelli del manuale.
Le opzioni di Incanalare Divinità spendono la riserva ``POOL`` della base; i giuramenti riusano dal 2014 i pezzi che il manuale
2024 non ha cambiato (Arma Consacrata, Giuramento di Inimicizia, Attacco di opportunità) e riscrivono gli altri.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from core.data.skills import SKILL_ABILITY_MAP
from core.rules.catalog._common import feature, state_on
from core.rules.catalog.y2014.paladin import (
    OPPORTUNITY_ATTACK, RELENTLESS_AVENGER, SENTINEL, SOUL_OF_VENGEANCE, VOW_ATTACK, _angel_effect, _aura_range, _champion_heal, _cha_bonus,
    _cha_mod, _metres, _permanent_note, _sacred_applies, _sacred_bonus, _spell_dc, _vow_state, _weapon_label, _wielded_weapons,
)
from core.rules.catalog.y2024.paladin import CK, ED, POOL, SMITE, SMITE_FREE, _fiend_slot_ok, _free_left, _melee_or_unarmed
from core.rules.states import begin_state, is_conscious
from core.game.item_bonuses import item_meta
from core.rules.types import (
    AuraSpec, Cost, FeatureSpec, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, TargetEffect, UseChoice, UseToggle, Uses,
)

# Due incantesimi per ogni soglia (3°, 5°, 9°, 13°, 17°): ``srd_index``, chiavi di ``GRANTED_SPELLS``.
OATH_SPELLS = {
    "devotion": (("protection-from-evil-and-good", "shield-of-faith"), ("aid", "zone-of-truth"), ("beacon-of-hope", "dispel-magic"),
                 ("freedom-of-movement", "guardian-of-faith"), ("commune", "flame-strike")),
    "glory": (("guiding-bolt", "heroism"), ("enhance-ability", "magic-weapon"), ("haste", "protection-from-energy"),
              ("compulsion", "freedom-of-movement"), ("legend-lore", "yolandes-regal-presence")),
    "ancients": (("ensnaring-strike", "speak-with-animals"), ("misty-step", "moonbeam"), ("plant-growth", "protection-from-energy"),
                 ("ice-storm", "stoneskin"), ("commune-with-nature", "tree-stride")),
    "vengeance": (("bane", "hunters-mark"), ("hold-person", "misty-step"), ("haste", "protection-from-energy"),
                  ("banishment", "dimension-door"), ("hold-monster", "scrying")),
}
OATH_LEVELS = (3, 5, 9, 13, 17)
OATH_TITLES = {
    "devotion": ("Incantesimi del Giuramento di Devozione / Oath of Devotion Spells (Giuramento di Devozione, Paladino 3, pag. 113)",
                 ("Incantesimi del Giuramento di Devozione", "Oath of Devotion Spells")),
    "glory": ("Incantesimi del Giuramento della Gloria / Oath of Glory Spells (Giuramento della Gloria, Paladino 3, pag. 115)",
              ("Incantesimi del Giuramento della Gloria", "Oath of Glory Spells")),
    "ancients": ("Incantesimi del Giuramento degli Antichi / Oath of the Ancients Spells (Giuramento degli Antichi, Paladino 3, pag. 115)",
                 ("Incantesimi del Giuramento degli Antichi", "Oath of the Ancients Spells")),
    "vengeance": ("Incantesimi del Giuramento di Vendetta / Oath of Vengeance Spells (Giuramento di Vendetta, Paladino 3, pag. 117)",
                  ("Incantesimi del Giuramento di Vendetta", "Oath of Vengeance Spells")),
}
SAVES = ("save", "death_save", "concentration")


def _both(it: str, en: str) -> dict[str, str]:
    return {"it": it, "en": en}


def _say(it: str, en: str):
    return lambda _ctx, _params=None: {"it": it, "en": en}


def _oath_spells(oath: str) -> list[FeatureSpec]:
    """Due incantesimi per ogni soglia. La riga del 3° livello è quella della scheda; le soglie successive sono la stessa voce a
    livello più alto e non portano una riga propria."""
    title, name = OATH_TITLES[oath]
    tiers = OATH_SPELLS[oath]
    out = [feature(f"{oath}_spells", CK, ED, OATH_LEVELS[0], title, name,
                   ("Incantesimi di giuramento sempre preparati, due per soglia (3°, 5°, 9°, 13°, 17°); non contano nel limite.",
                    "Oath spells are always prepared, two per tier (3rd, 5th, 9th, 13th, 17th); they do not count against the limit."),
                   subclass=oath, granted_spells=tiers[0])]
    for level, spells in zip(OATH_LEVELS[1:], tiers[1:]):
        out.append(feature(f"{oath}_spells_{level}", CK, ED, level, title, name,
                           (f"Incantesimi di giuramento del {level}° livello.", f"Oath spells gained at level {level}."),
                           subclass=oath, granted_spells=spells, no_row=True,
                           covered_by=f"{CK}.{oath}_spells (stessa voce della mappatura) e test_oath_spells_follow_the_level"))
    return out


# ---------------------------------------------------------------------------
# Ripristino con uno slot di 5° livello (Nube Sacra, Leggenda Vivente, Campione degli Antichi, Angelo Vendicatore)
# ---------------------------------------------------------------------------

def _restore_levels(ctx: RuleContext) -> list[str]:
    return [str(level) for level in sorted({s.level for s in ctx.char.spell_slots or [] if s.level >= 5 and s.available > 0})]


def _restore_check(_ctx: RuleContext, params: dict) -> tuple[int, str] | None:
    return (422, "invalid_choice") if params.get("restore") and params.get("slot_level") is None else None


def _restoring_use(state: Any, **kw: Any) -> OnUse:
    """Azione bonus che spende l'uso, oppure (``restore``) uno slot di 5° livello o superiore al posto dell'uso: il manuale
    dice che l'uso si recupera così, senza azione."""
    return OnUse(
        slot="bonus", state=state, spends_slot="slot_level", spends_slot_when=lambda _c, p: bool(p.get("restore")),
        cost_by=lambda _c, p: 0 if p.get("restore") else 1, check=_restore_check,
        toggles=(UseToggle("restore", _both("Ripristina spendendo uno slot di 5° livello o superiore (nessuna azione)",
                                            "Restore by spending a level 5 or higher slot (no action)")),),
        choices=(UseChoice("slot_level", _both("Slot da spendere per ripristinare", "Slot to spend to restore"), _restore_levels,
                           lambda level: _both(f"Slot di {level}° livello", f"Level {level} slot"), optional=True),), **kw)


# ---------------------------------------------------------------------------
# Devozione
# ---------------------------------------------------------------------------

def _melee_wielded(ctx: RuleContext) -> list[Any]:
    """Il manuale 2024 dice «un'arma da mischia»: il 2014 le accettava tutte."""
    return [i for i in _wielded_weapons(ctx) if item_meta(i).get("weapon_type", "melee") != "ranged"]


_DAMAGE_TYPES = {"normal": _both("Il tipo di danno normale dell'arma", "The weapon's normal damage type"),
                 "radiant": _both("Danno radioso", "Radiant damage")}


def _sacred_state(ctx: RuleContext, params: dict) -> StateSpec:
    return StateSpec("sacred_weapon", rounds=100, ends_on=("manual", "unconscious"),
                     data={"weapon_id": int(params["weapon"]), "bound_item": int(params["weapon"]), "attack_bonus": _cha_bonus(ctx),
                           "damage_type": params.get("damage_type") or "normal"})


def _sacred_radiant(ctx: RuleContext) -> bool:
    state = next((s for s in ctx.char.active_states or [] if s.get("key") == "sacred_weapon"), None)
    return _sacred_applies(ctx) and ((state or {}).get("data") or {}).get("damage_type") == "radiant"


SACRED_RADIANT = RollOptionSpec(
    key=f"{CK}.sacred_weapon_radiant", phase="before", rolls=("attack",), automatic=True, available=_sacred_radiant,
    label=_both("Arma Consacrata: il danno dell'arma è radioso", "Sacred Weapon: the weapon's damage is radiant"),
    effect=_say("Arma Consacrata: i danni di quest'arma sono radiosi (scelti all'attivazione).",
                "Sacred Weapon: this weapon's damage is radiant (chosen when activated)."))


SACRED_WEAPON_USE = OnUse(
    spends=POOL, available=lambda c: bool(_melee_wielded(c)), state=_sacred_state,
    choices=(UseChoice("weapon", _both("Arma", "Weapon"), lambda c: [str(i.id) for i in _melee_wielded(c)],
                       lambda k: _both(k, k), option_label_ctx=_weapon_label),
             UseChoice("damage_type", _both("Tipo di danno", "Damage type"), lambda _c: list(_DAMAGE_TYPES), lambda k: _DAMAGE_TYPES[k],
                       optional=True)))


def _protection_state(_ctx: RuleContext, _inputs: dict) -> StateSpec:
    return StateSpec("smite_of_protection", ends_on=("new_turn", "manual"), data={"others": [f"{CK}.smite_of_protection"]})


def _begin_protection(_session: Any, ctx: RuleContext, inputs: dict) -> None:
    begin_state(ctx.char, _protection_state(ctx, inputs), f"{CK}.smite_of_protection", "Punizione Protettiva")


_PROTECTION_LABEL = _both("Punizione Protettiva: tu e gli alleati nell'aura avete Copertura Parziale fino al tuo prossimo turno",
                          "Smite of Protection: you and allies in the aura have Half Cover until your next turn")
SMITE_PROTECTION = RollOptionSpec(
    key=f"{CK}.smite_of_protection", phase="after_hit", rolls=("attack",), needs=SMITE, available=_fiend_slot_ok,
    on_confirm=_begin_protection, label=_PROTECTION_LABEL,
    effect=_say("Copertura Parziale: +2 alla CA e ai TS di Destrezza fino al tuo prossimo turno; gli alleati nell'aura lo segnano loro.",
                "Half Cover: +2 to AC and Dexterity saves until your next turn; allies in the aura track it themselves."))
SMITE_PROTECTION_FREE = replace(
    SMITE_PROTECTION, key=f"{CK}.smite_of_protection_free", needs=SMITE_FREE,
    available=lambda c: _melee_or_unarmed(c) and (SMITE_FREE in c.confirmed or _free_left(c)))


def _cover(ctx: RuleContext) -> bool:
    return state_on(ctx, "smite_of_protection")


def _nimbus_state(ctx: RuleContext, _params: dict) -> StateSpec:
    return StateSpec("holy_nimbus", rounds=100, ends_on=("manual",),
                     data={"others": [f"{CK}.holy_nimbus"], "damage": _cha_mod(ctx) + ctx.char.proficiency_bonus, "radius_m": 9})


def _nimbus_message(ctx: RuleContext, _params: dict) -> dict[str, str]:
    damage = _cha_mod(ctx) + ctx.char.proficiency_bonus
    return _both(f"Un nemico che inizia il turno nell'aura subisce {damage} danni radiosi; vantaggio ai TS imposti da immondi e non morti.",
                 f"An enemy starting its turn in the aura takes {damage} radiant damage; advantage on saves imposed by fiends and undead.")


NIMBUS_SAVE = RollOptionSpec(
    key=f"{CK}.holy_nimbus_save", phase="before", rolls=("save",), mode="advantage", available=lambda c: state_on(c, "holy_nimbus"),
    label=_both("Nube Sacra: il TS è imposto da un immondo o da un non morto? Vantaggio",
                "Holy Nimbus: is the save imposed by a fiend or an undead? Advantage"))

DEVOTION = (
    *_oath_spells("devotion"),
    feature("sacred_weapon", CK, ED, 3, "Arma Consacrata / Sacred Weapon (Incanalare Divinità, Giuramento di Devozione, Paladino 3, pag. 113)",
            ("Arma Consacrata", "Sacred Weapon"),
            ("Con l'azione Attacca, un uso di Incanalare Divinità: per 10 minuti aggiungi il Carisma (minimo +1) ai tiri per colpire con l'arma impugnata, che fa luce.",
             "With the Attack action, one Channel Divinity use: for 10 minutes add your Charisma (minimum +1) to attack rolls with the wielded weapon, which sheds light."),
            "special", subclass="devotion", on_use=SACRED_WEAPON_USE, roll_options=(SACRED_RADIANT,),
            modifiers=(Modifier("attack", _sacred_bonus, when=_sacred_applies, source=f"feature:{CK}.sacred_weapon"),)),
    feature("aura_of_devotion", CK, ED, 7, "Aura di Devozione / Aura of Devotion (Giuramento di Devozione, Paladino 7, pag. 114)",
            ("Aura di Devozione", "Aura of Devotion"),
            ("Tu e gli alleati nella tua Aura di Protezione non potete essere Affascinati, finché non sei Incapacitato; un alleato già Affascinato non ne risente dentro l'aura.",
             "You and allies in your Aura of Protection cannot be Charmed while you are not Incapacitated; an already Charmed ally is unaffected inside the aura."),
            subclass="devotion", condition_immunities=("charmed",), needs_conscious=True, passive=True,
            permanent_state=_permanent_note("aura_of_devotion")),
    feature("smite_of_protection", CK, ED, 15, "Punizione Protettiva / Smite of Protection (Giuramento di Devozione, Paladino 15, pag. 114)",
            ("Punizione Protettiva", "Smite of Protection"),
            ("Quando lanci Punizione Divina, tu e gli alleati nell'aura avete Copertura Parziale (+2 a CA e TS Destrezza) fino al tuo prossimo turno.",
             "When you cast Divine Smite, you and allies in the aura have Half Cover (+2 AC and Dexterity saves) until your next turn."),
            subclass="devotion", passive=True, roll_options=(SMITE_PROTECTION, SMITE_PROTECTION_FREE),
            modifiers=(Modifier("ac", 2, when=_cover, source=f"feature:{CK}.smite_of_protection"),
                       Modifier("save", 2, when=lambda c: _cover(c) and c.roll in SAVES and c.ability == "dexterity",
                                source=f"feature:{CK}.smite_of_protection"))),
    feature("holy_nimbus", CK, ED, 20, "Nube Sacra / Holy Nimbus (Giuramento di Devozione, Paladino 20, pag. 114)",
            ("Nube Sacra", "Holy Nimbus"),
            ("Azione bonus, 10 minuti: l'aura dà vantaggio ai TS contro immondi e non morti e danni radiosi (Carisma + competenza) ai nemici che iniziano il turno dentro. Un uso, riposo lungo o slot di 5°.",
             "Bonus action, 10 minutes: aura with advantage on saves against fiends and undead, radiant damage (Cha + proficiency) to enemies starting their turn in it. One use, long rest or level 5 slot."),
            "bonus_action", subclass="devotion", uses=Uses(table={20: 1}), restoration="long_rest", roll_options=(NIMBUS_SAVE,),
            on_use=_restoring_use(_nimbus_state, message=_nimbus_message)),
)


# ---------------------------------------------------------------------------
# Gloria
# ---------------------------------------------------------------------------

def _smite_cast_this_turn(ctx: RuleContext) -> bool:
    return bool((ctx.char.turn_state or {}).get("smite_cast"))


def _inspiring_total(ctx: RuleContext, rolled: int) -> int:
    return rolled + ctx.class_level


def _inspiring_temp(ctx: RuleContext, rolled: int, params: dict) -> int:
    total = _inspiring_total(ctx, rolled)
    return {"all": total, "half": total // 2}.get(params.get("keep"), 0)


_KEEP = {"all": _both("Tutti a te", "All to you"), "half": _both("Metà a te, il resto a un solo altro", "Half to you, the rest to only one other creature"),
         "none": _both("Tutti a un solo altro", "All to only one other creature")}
def _inspiring_given(ctx: RuleContext, rolled: int, params: dict) -> int:
    """Agli altri va ciò che il paladino non tiene (D1: l'unico esito per loro)."""
    return _inspiring_total(ctx, rolled) - _inspiring_temp(ctx, rolled, params)


def _consume_smite(ctx: RuleContext, _params: dict) -> None:
    """Una volta per lancio di Punizione Divina: l'uso chiude la finestra, una nuova Punizione la riapre."""
    ctx.char.turn_state = {**(ctx.char.turn_state or {}), "smite_cast": False}


INSPIRING_SMITE_USE = OnUse(
    spends=POOL, rolls="2d8", available=_smite_cast_this_turn, gives_by=_inspiring_given, temp_hp_by=_inspiring_temp, temp_hp_ally=True,
    effect=_consume_smite,
    choices=(UseChoice("keep", _both("PF temporanei per te", "Temporary hit points for you"), lambda _c: list(_KEEP), lambda k: _KEEP[k]),))

PEERLESS_STATE = StateSpec("peerless_athlete", rounds=600, ends_on=("manual",), data={"others": [f"{CK}.peerless_athlete"]})
_PEERLESS_SKILLS = ("athletics", "acrobatics")


def _peerless_advantage(ctx: RuleContext) -> bool:
    return state_on(ctx, "peerless_athlete") and ctx.roll in ("skill", "ability") and ctx.skill in _PEERLESS_SKILLS


def _glorious_bonus(ctx: RuleContext, _params: dict) -> dict[str, str]:
    n = _cha_bonus(ctx)
    return _both(f"+{n} alla CA del bersaglio contro quell'attacco: se l'attacco fallisce puoi attaccare l'aggressore con un'arma, nella stessa reazione.",
                 f"+{n} to the target's AC against that attack: if it misses you can attack the attacker with a weapon as part of the reaction.")


GLORIOUS_STATE = "glorious_defense_strike"
# Il colpo di risposta è parte della stessa reazione: non pesa sul limite dell'azione Attacco e si dichiara una sola volta
GLORIOUS_STRIKE = RollOptionSpec(
    key=f"{CK}.glorious_defense_strike", phase="before", rolls=("attack",), outside_action=True, cost=Cost(state_key=GLORIOUS_STATE),
    available=lambda c: c.spell is None and state_on(c, GLORIOUS_STATE),
    label=_both("Difesa Gloriosa: attacco con arma sull'aggressore, nella stessa reazione",
                "Glorious Defense: weapon attack against the attacker, as part of the same reaction"))


def _glorious_state(_ctx: RuleContext, _params: dict) -> StateSpec:
    return StateSpec(GLORIOUS_STATE, rounds=1, ends_on=("new_turn", "manual"))


def _legend_state(_ctx: RuleContext, _params: dict) -> StateSpec:
    return StateSpec("living_legend", rounds=100, ends_on=("manual",), data={"others": [f"{CK}.living_legend"]})


def _legend_charisma(ctx: RuleContext) -> bool:
    return (state_on(ctx, "living_legend") and ctx.roll in ("skill", "ability")
            and (ctx.ability or SKILL_ABILITY_MAP.get(ctx.skill or "")) == "charisma")


LEGEND_SAVE = RollOptionSpec(
    key=f"{CK}.living_legend_save", phase="after_roll", after="reroll", rolls=("save",), slot="reaction", offered_on_damage=False,
    available=lambda c: state_on(c, "living_legend"),
    label=_both("Leggenda Vivente: ripeti il TS fallito con una reazione e tieni il nuovo risultato",
                "Living Legend: reroll the failed save with a reaction and keep the new result"))
LEGEND_HIT = RollOptionSpec(
    key=f"{CK}.living_legend_hit", phase="after_roll", after="succeed", rolls=("attack",), once_per_turn=True,
    available=lambda c: state_on(c, "living_legend") and c.spell is None and c.item is not None,
    label=_both("Leggenda Vivente: il tiro per colpire con arma mancato diventa un colpo (una volta per turno)",
                "Living Legend: a missed weapon attack roll becomes a hit (once per turn)"))

GLORY = (
    *_oath_spells("glory"),
    feature("inspiring_smite", CK, ED, 3, "Punizione Ispiratrice / Inspiring Smite (Incanalare Divinità, Giuramento della Gloria, Paladino 3, pag. 114)",
            ("Punizione Ispiratrice", "Inspiring Smite"),
            ("Subito dopo Punizione Divina, un uso di Incanalare Divinità: 2d8 + livello da paladino PF temporanei da dividere fra creature entro 9 m, te compreso (nell'app la quota altrui va a un solo PG).",
             "Right after Divine Smite, one Channel Divinity use: 2d8 + paladin level temporary hit points to divide among creatures within 30 ft, you included (in the app others' share goes to one PC)."),
            "special", subclass="glory", on_use=INSPIRING_SMITE_USE),
    feature("peerless_athlete", CK, ED, 3, "Atleta Impareggiabile / Peerless Athlete (Incanalare Divinità, Giuramento della Gloria, Paladino 3, pag. 115)",
            ("Atleta Impareggiabile", "Peerless Athlete"),
            ("Azione bonus, un uso di Incanalare Divinità: per 1 ora vantaggio a Atletica e Acrobazia e salti più lunghi di 3 m.",
             "Bonus action, one Channel Divinity use: for 1 hour advantage on Athletics and Acrobatics and jumps 10 ft longer."),
            "bonus_action", subclass="glory", on_use=OnUse(slot="bonus", spends=POOL, state=PEERLESS_STATE),
            modifiers=(Modifier("advantage", 1, when=_peerless_advantage, source=f"feature:{CK}.peerless_athlete"),
                       Modifier("jump_bonus", 10, when=lambda c: state_on(c, "peerless_athlete"), source=f"feature:{CK}.peerless_athlete"))),
    feature("aura_of_alacrity", CK, ED, 7, "Aura di Alacrità / Aura of Alacrity (Giuramento della Gloria, Paladino 7, pag. 115)",
            ("Aura di Alacrità", "Aura of Alacrity"),
            ("La tua Velocità aumenta di 3 m. Un alleato che entra nell'aura la prima volta nel turno, o vi inizia il turno, ha +3 m fino alla fine del suo turno successivo.",
             "Your Speed increases by 10 ft. An ally entering the aura for the first time on a turn, or starting its turn there, gets +10 ft until the end of its next turn."),
            subclass="glory", passive=True, permanent_state=_permanent_note("aura_of_alacrity"),
            modifiers=(Modifier("speed", 10, source=f"feature:{CK}.aura_of_alacrity"),)),
    feature("glorious_defense", CK, ED, 15, "Difesa Gloriosa / Glorious Defense (Giuramento della Gloria, Paladino 15, pag. 115)",
            ("Difesa Gloriosa", "Glorious Defense"),
            ("Reazione, quando tu o una creatura entro 3 m siete colpiti: bonus alla CA pari al Carisma (minimo +1); se l'attacco fallisce, un attacco con arma sull'aggressore. Usi pari al Carisma, riposo lungo.",
             "Reaction, when you or a creature within 10 ft is hit: AC bonus equal to Charisma (minimum +1); if the attack misses, a weapon attack against the attacker. Uses equal Charisma, long rest."),
            "reaction", subclass="glory", uses=Uses(ability="charisma", minimum=1), restoration="long_rest",
            roll_options=(GLORIOUS_STRIKE,), on_use=OnUse(slot="reaction", message=_glorious_bonus, state=_glorious_state)),
    feature("living_legend", CK, ED, 20, "Leggenda Vivente / Living Legend (Giuramento della Gloria, Paladino 20, pag. 115)",
            ("Leggenda Vivente", "Living Legend"),
            ("Azione bonus, 10 minuti: vantaggio alle prove di Carisma, un TS fallito ripetuto con reazione, una volta per turno un attacco con arma mancato diventa un colpo. Un uso, riposo lungo o slot di 5°.",
             "Bonus action, 10 minutes: advantage on Charisma checks, a failed save rerolled with a reaction, once per turn a missed weapon attack becomes a hit. One use, long rest or a level 5 slot."),
            "bonus_action", subclass="glory", uses=Uses(table={20: 1}), restoration="long_rest", roll_options=(LEGEND_SAVE, LEGEND_HIT),
            modifiers=(Modifier("advantage", 1, when=_legend_charisma, source=f"feature:{CK}.living_legend"),),
            on_use=_restoring_use(_legend_state)),
)


# ---------------------------------------------------------------------------
# Antichi
# ---------------------------------------------------------------------------

def _wrath_effect(ctx: RuleContext, _params: dict) -> TargetEffect:
    return TargetEffect(condition="restrained", save_ability="strength", save_dc=_spell_dc(ctx), rounds=10, repeat_save="end")


def _wrath_state(ctx: RuleContext, _params: dict) -> StateSpec:
    return StateSpec("natures_wrath", rounds=10, ends_on=("manual",),
                     data={"dc": _spell_dc(ctx), "save": "strength", "others": [f"{CK}.natures_wrath"]})


WARDED = ("necrotic", "psychic", "radiant")
SENTINEL_2024 = replace(
    SENTINEL, holds_heal=lambda c: 3 * c.class_level,
    label=_both("Sentinella Imperitura: se il danno ti porta a 0 PF senza ucciderti sul colpo, resti a 1 PF e recuperi 3 x livello da paladino (un uso, riposo lungo)",
                "Undying Sentinel: if the damage would drop you to 0 HP without killing you outright, you stay at 1 HP and regain 3 x paladin level (one use, long rest)"))


def _champion_state(ctx: RuleContext, _params: dict) -> StateSpec:
    return StateSpec("elder_champion", rounds=10, ends_on=("manual",),
                     data={"others": [f"{CK}.elder_champion"], "start_heal": 10, "dc": _spell_dc(ctx)})


ANCIENTS = (
    *_oath_spells("ancients"),
    feature("natures_wrath", CK, ED, 3, "Collera della Natura / Nature's Wrath (Incanalare Divinità, Giuramento degli Antichi, Paladino 3, pag. 115)",
            ("Collera della Natura", "Nature's Wrath"),
            ("Azione Magia, un uso di Incanalare Divinità: le creature che scegli entro 4,5 m fanno un TS Forza (CD incantesimi) o sono Trattenute per 1 minuto, con TS a fine turno.",
             "Magic action, one Channel Divinity use: creatures you choose within 15 ft make a Strength save (spell DC) or are Restrained for 1 minute, saving at the end of their turns."),
            "action", subclass="ancients", on_use=OnUse(slot="action", spends=POOL, state=_wrath_state, target_effect=_wrath_effect)),
    feature("aura_of_warding", CK, ED, 7, "Aura di Interdizione / Aura of Warding (Giuramento degli Antichi, Paladino 7, pag. 116)",
            ("Aura di Interdizione", "Aura of Warding"),
            ("Tu e gli alleati nella tua Aura di Protezione avete resistenza ai danni necrotici, psichici e radiosi. Il tuo è già nelle tue resistenze; gli alleati lo confermano al danno.",
             "You and allies in your Aura of Protection resist necrotic, psychic and radiant damage. Yours is already in your resistances; allies confirm it on the damage."),
            subclass="ancients", passive=True, aura=AuraSpec("warding", _aura_range),
            modifiers=tuple(Modifier(f"resistance:{t}", 1, when=lambda c: is_conscious(c.char), source=f"feature:{CK}.aura_of_warding")
                            for t in WARDED)),
    feature("undying_sentinel", CK, ED, 15, "Sentinella Imperitura / Undying Sentinel (Giuramento degli Antichi, Paladino 15, pag. 116)",
            ("Sentinella Imperitura", "Undying Sentinel"),
            ("A 0 PF, se non sei morto sul colpo, resti a 1 PF e recuperi 3 x livello da paladino. Un uso, riposo lungo. Non invecchi.",
             "When reduced to 0 HP and not killed outright, you drop to 1 HP and regain 3 x paladin level. One use, long rest. You do not age."),
            "special", subclass="ancients", uses=Uses(table={15: 1}), restoration="long_rest", roll_options=(SENTINEL_2024,)),
    feature("elder_champion", CK, ED, 20, "Campione degli Antichi / Elder Champion (Giuramento degli Antichi, Paladino 20, pag. 116)",
            ("Campione degli Antichi", "Elder Champion"),
            ("Azione bonus, 1 minuto: +10 PF a inizio turno, incantesimi da un'azione lanciati con azione bonus, nemici nell'aura con svantaggio ai TS contro i tuoi incantesimi. Un uso, riposo lungo o slot di 5°.",
             "Bonus action, 1 minute: regain 10 HP at turn start, one-action spells cast as a bonus action, enemies in the aura have disadvantage on saves against your spells. One use, long rest or a level 5 slot."),
            "bonus_action", subclass="ancients", uses=Uses(table={20: 1}), restoration="long_rest", turn_start_heal=_champion_heal,
            on_use=_restoring_use(_champion_state)),
)


# ---------------------------------------------------------------------------
# Vendetta
# ---------------------------------------------------------------------------

def _avenger_effect(ctx: RuleContext, _inputs: dict) -> dict[str, str]:
    from core.rules.modifiers import effective_speed  # import locale: modifiers usa il catalogo
    half = effective_speed(ctx.char, ctx.char.speed) // 2
    return _both(f"Velocità a 0 per la creatura colpita fino alla fine del turno; muoviti fino a metà della tua velocità ({_metres(half)} m) senza provocare attacchi di opportunità.",
                 f"The struck creature's Speed is 0 until the end of the turn; move up to half your speed ({half} ft) without provoking opportunity attacks.")


RELENTLESS_2024 = replace(RELENTLESS_AVENGER, effect=_avenger_effect,
                          label=_both("Vendicatore Implacabile: Velocità della creatura a 0 e muoviti di metà velocità dopo il colpo",
                                      "Relentless Avenger: the creature's Speed drops to 0 and you move half your speed after the hit"))
SOUL_2024 = replace(SOUL_OF_VENGEANCE, label=_both(
    "Anima di Vendetta: la creatura sotto Giuramento di Inimicizia ha colpito o mancato con un attacco? Reazione: attacco in mischia",
    "Soul of Vengeance: did the creature under your Vow of Enmity hit or miss with an attack? Reaction: melee attack"))


def _angel_effect_2024(ctx: RuleContext, params: dict) -> TargetEffect:
    """Il 2024 vale solo a inizio turno nell'aura: la nota del 2014 dice anche «entra nell'aura»."""
    return replace(_angel_effect(ctx, params), note="avenging_angel_2024")


def _angel_state(ctx: RuleContext, _params: dict) -> StateSpec:
    return StateSpec("avenging_angel", rounds=100, ends_on=("manual",),
                     data={"dc": _spell_dc(ctx), "save": "wisdom", "others": [f"{CK}.avenging_angel"], "radius_m": 9, "fly_ft": 60})


VENGEANCE = (
    *_oath_spells("vengeance"),
    feature("vow_of_enmity", CK, ED, 3, "Giuramento di Inimicizia / Vow of Enmity (Incanalare Divinità, Giuramento di Vendetta, Paladino 3, pag. 117)",
            ("Giuramento di Inimicizia", "Vow of Enmity"),
            ("Con l'azione Attacca, un uso di Incanalare Divinità: per 1 minuto vantaggio ai tiri per colpire contro una creatura entro 9 m; se scende a 0 PF il voto passa a un'altra.",
             "With the Attack action, one Channel Divinity use: for 1 minute advantage on attack rolls against a creature within 30 ft; if it drops to 0 HP the vow moves to another."),
            "special", subclass="vengeance", roll_options=(VOW_ATTACK,), on_use=OnUse(spends=POOL, state=_vow_state)),
    feature("relentless_avenger", CK, ED, 7, "Vendicatore Implacabile / Relentless Avenger (Giuramento di Vendetta, Paladino 7, pag. 117)",
            ("Vendicatore Implacabile", "Relentless Avenger"),
            ("Un Attacco di Opportunità a segno porta la Velocità della creatura a 0 fino a fine turno; poi ti muovi di metà Velocità nella stessa reazione, senza provocare.",
             "A hit with an Opportunity Attack sets the creature's Speed to 0 until the end of the turn; then you move half your Speed in the same reaction, without provoking."),
            subclass="vengeance", roll_options=(OPPORTUNITY_ATTACK, RELENTLESS_2024), passive=True),
    feature("soul_of_vengeance", CK, ED, 15, "Anima di Vendetta / Soul of Vengeance (Giuramento di Vendetta, Paladino 15, pag. 117)",
            ("Anima di Vendetta", "Soul of Vengeance"),
            ("Reazione: dopo che la creatura sotto il tuo Giuramento di Inimicizia colpisce o manca, un attacco in mischia contro di essa se è a portata.",
             "Reaction: after the creature under your Vow of Enmity hits or misses, a melee attack against it if it is within reach."),
            "reaction", subclass="vengeance", roll_options=(SOUL_2024,)),
    feature("avenging_angel", CK, ED, 20, "Angelo Vendicatore / Avenging Angel (Giuramento di Vendetta, Paladino 20, pag. 117)",
            ("Angelo Vendicatore", "Avenging Angel"),
            ("Azione bonus, 10 minuti: volo 18 m; i nemici che iniziano il turno nell'aura fanno un TS Saggezza o sono Spaventati, e gli attacchi contro di loro hanno vantaggio. Un uso, riposo lungo o slot di 5°.",
             "Bonus action, 10 minutes: fly 60 ft; enemies starting their turn in the aura make a Wisdom save or are Frightened, and attacks against them have advantage. One use, long rest or a level 5 slot."),
            "bonus_action", subclass="vengeance", uses=Uses(table={20: 1}), restoration="long_rest",
            modifiers=(Modifier("fly_speed_value", 60, when=lambda c: state_on(c, "avenging_angel"), source=f"feature:{CK}.avenging_angel"),),
            on_use=_restoring_use(_angel_state, target_effect=_angel_effect_2024)),
)

SUBCLASS_ROWS = DEVOTION + GLORY + ANCIENTS + VENGEANCE

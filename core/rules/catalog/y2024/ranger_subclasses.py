"""Le quattro sottoclassi del Ranger 2024: Signore delle Bestie, Viandante Fatato, Stalker delle Tenebre, Cacciatore.

Valori dalla scheda ``docs/superpowers/rules/2024/classes/ranger.md``; i testi sono nostri, mai quelli del manuale.
La bestia primordiale vive nella tabella dei compagni (``core/rules/companions.py``; ordini in ``api/routers/companions.py``);
i pezzi del Cacciatore che il 2014 non ha cambiato (Sterminatore di Colossi, Devastatore dell'Orda) sono quelli del 2014.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.data.damage_types import DAMAGE_TYPES
from core.data.skills import SKILL_ABILITY_MAP
from core.rules.catalog._common import feature, skill_label, state_on
from core.rules.catalog.y2014.ranger import (
    COLOSSUS_SLAYER, HORDE_BREAKER, SHARE_SPELLS_EXTEND, _permanent_note, _say, _weapon_attack,
)
from core.rules.catalog.y2014.rogue import _lacks_wisdom_save_proficiency
from core.rules.catalog.y2024.barbarian import _owl_range
from core.rules.catalog.y2024.druid import _free_slot_levels, _level_label
from core.rules.catalog.y2024.ranger import CK, ED, _mark_dice, _wis_mod, hunters_mark_active
from core.rules.companions import PRIMAL_COMPANION
from core.rules.states import begin_state, has_state
from core.rules.types import (
    ChoiceSpec, Cost, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, TargetEffect, UseChoice, UseToggle, Uses,
)


def _both(it: str, en: str) -> dict[str, str]:
    return {"it": it, "en": en}


def _spell_dc(ctx: RuleContext) -> int:
    return 8 + ctx.char.proficiency_bonus + _wis_mod(ctx)


def _sub(sub: str, key: str, level: int, title: str, name: tuple[str, str], summary: tuple[str, str], action_type: str | None = None, **kw: Any):
    return feature(key, CK, ED, level, title, name, summary, action_type, subclass=sub, **kw)


# ---------------------------------------------------------------------------
# Incantesimi sempre preparati: uno per soglia (3°, 5°, 9°, 13°, 17°)
# ---------------------------------------------------------------------------

TIER_LEVELS = (3, 5, 9, 13, 17)
SUBCLASS_SPELLS = {
    "fey_wanderer": ("charm-person", "misty-step", "summon-fey", "dimension-door", "mislead"),
    "gloom_stalker": ("disguise-self", "rope-trick", "fear", "greater-invisibility", "seeming"),
}


def _spell_rows(sub: str, title: str, name: tuple[str, str]) -> list:
    spells = SUBCLASS_SPELLS[sub]
    out = [_sub(sub, f"{sub}_spells", TIER_LEVELS[0], title, name,
                ("Un incantesimo sempre preparato per soglia (3°, 5°, 9°, 13°, 17°); non conta nel limite.",
                 "One always-prepared spell per tier (3rd, 5th, 9th, 13th, 17th); it does not count against the limit."),
                granted_spells=(spells[0],))]
    for level, spell in zip(TIER_LEVELS[1:], spells[1:]):
        out.append(_sub(sub, f"{sub}_spells_{level}", level, title, name,
                        (f"Incantesimo di sottoclasse del {level}° livello.", f"Subclass spell gained at level {level}."),
                        granted_spells=(spell,), no_row=True,
                        covered_by=f"{CK}.{sub}_spells (stessa voce della mappatura) e test_subclass_spells_follow_the_level"))
    return out


# ---------------------------------------------------------------------------
# Signore delle Bestie: la bestia primordiale
# ---------------------------------------------------------------------------

# tipo -> (taglia, dado vita, velocità, caratteristiche, dado di danno, tipi di danno ammessi, PF per livello)
BEASTS: dict[str, dict[str, Any]] = {
    "land": {"size": "Medium", "die": 8, "speed": {"walk_ft": 40, "climb_ft": 40}, "darkvision": 60, "dice": "1d8+2", "per_level": 5,
             "abilities": {"str": 14, "dex": 14, "con": 15, "int": 8, "wis": 14, "cha": 11}, "damage": ("bludgeoning", "piercing", "slashing")},
    "sky": {"size": "Small", "die": 6, "speed": {"walk_ft": 10, "fly_ft": 60}, "darkvision": 60, "dice": "1d4+3", "per_level": 4,
            "abilities": {"str": 6, "dex": 16, "con": 13, "int": 8, "wis": 14, "cha": 11}, "damage": ("slashing",)},
    "sea": {"size": "Medium", "die": 8, "speed": {"walk_ft": 5, "swim_ft": 60}, "darkvision": 90, "dice": "1d6+2", "per_level": 5,
            "abilities": {"str": 14, "dex": 14, "con": 15, "int": 8, "wis": 14, "cha": 11}, "damage": ("bludgeoning", "piercing")},
}
_KIND = {"land": _both("Bestia della Terra", "Beast of the Land"), "sky": _both("Bestia del Cielo", "Beast of the Sky"),
         "sea": _both("Bestia del Mare", "Beast of the Sea")}
_DAMAGE = {"bludgeoning": _both("Contundente", "Bludgeoning"), "piercing": _both("Perforante", "Piercing"),
           "slashing": _both("Tagliente", "Slashing")}
_PAYMENTS = {"use": _both("L'uso del riposo lungo", "The long rest use"), "slot": _both("Uno slot incantesimo", "A spell slot")}


def _beast_hp(kind: str, level: int) -> int:
    return BEASTS[kind]["per_level"] * (level + 1)


def _downed(ctx: RuleContext) -> Any:
    return next((c for c in ctx.char.companions if c.feature_key == PRIMAL_COMPANION and c.current_hp <= 0), None)


def _primal_check(ctx: RuleContext, params: dict) -> tuple[int, str] | None:
    if params.get("pay") == "slot":
        if params.get("slot_level") is None:
            return 422, "invalid_choice"
        if _downed(ctx) is not None:  # il ripristino non chiede la forma: torna com'era
            return None
    kind = params.get("kind")
    return None if kind in BEASTS and params.get("damage_type") in BEASTS[kind]["damage"] else (422, "invalid_choice")


def _primal_effect(ctx: RuleContext, params: dict) -> None:
    """Evoca la bestia (una sola alla volta: la precedente svanisce) o, con uno slot, rialza quella caduta con tutti i PF."""
    from core.db.models import Companion  # import locale: i modelli non servono al resto del catalogo
    if params.get("pay") == "slot" and (old := _downed(ctx)) is not None:
        old.current_hp = old.max_hp
        return
    for old in [c for c in ctx.char.companions if c.feature_key == PRIMAL_COMPANION]:
        ctx.char.companions.remove(old)
    kind, spec = str(params["kind"]), BEASTS[str(params["kind"])]
    hp = _beast_hp(kind, ctx.class_level)
    ctx.char.companions.append(Companion(
        character_id=ctx.char.id, kind="companion", name=str(params.get("name") or "").strip() or _KIND[kind]["it"],
        statblock={"size": spec["size"], "type": "beast", "primal_type": kind, "speed": spec["speed"], "abilities": spec["abilities"],
                   "hit_dice": f"{ctx.class_level}d{spec['die']}", "senses": {"darkvision_ft": spec["darkvision"]},
                   "actions": [{"name": "Colpo della Bestia", "attack_bonus": 0, "damage_dice": spec["dice"],
                                "damage_type": params["damage_type"]}]},
        max_hp=hp, current_hp=hp, armor_class=13, feature_key=PRIMAL_COMPANION,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds")))


PRIMAL_USE = OnUse(
    cost=1, cost_by=lambda _c, p: 1 if p.get("pay") == "use" else 0, slot_by=lambda _c, p: "action" if p.get("pay") == "slot" else None,
    spends_slot="slot_level", spends_slot_when=lambda _c, p: p.get("pay") == "slot", check=_primal_check, effect=_primal_effect,
    choices=(UseChoice("pay", _both("Costo", "Cost"), lambda _c: list(_PAYMENTS), lambda k: _PAYMENTS[k]),
             UseChoice("kind", _both("Bestia", "Beast"), lambda _c: list(BEASTS), lambda k: _KIND[k], optional=True),
             UseChoice("damage_type", _both("Tipo di danno", "Damage type"), lambda _c: list(_DAMAGE), lambda k: _DAMAGE[k], optional=True),
             UseChoice("slot_level", _both("Livello dello slot", "Slot level"), _free_slot_levels, _level_label, optional=True)),
    message=lambda _c, p: _both("La bestia è fra i compagni: agisce solo se glielo ordini, altrimenti Schiva.",
                                "The beast is among your companions: it acts only if you command it, otherwise it Dodges."))


def _beast_attack(ctx: RuleContext) -> bool:
    return ctx.attack_mode == "beast"


def _has_beast(kind: str):
    return lambda ctx: _beast_attack(ctx) and any(
        c.feature_key == PRIMAL_COMPANION and c.current_hp > 0 and (c.statblock or {}).get("primal_type") == kind for c in ctx.char.companions)


BEAST_CHARGE = RollOptionSpec(
    key=f"{CK}.beast_charge", phase="before", rolls=("attack",), extra_dice=lambda _c, _i: "1d6", available=_has_beast("land"),
    label=_both("Bestia della Terra: ha corso in linea retta per 6 m verso il bersaglio? +1d6 dello stesso tipo, Prono se Grande o più piccolo",
                "Beast of the Land: did it move 20 ft straight toward the target? +1d6 of the same type, Prone if Large or smaller"),
    effect=_say("Se il bersaglio è Grande o più piccolo, è Prono.", "If the target is Large or smaller, it is Prone."))

BEAST_GRAPPLE = RollOptionSpec(
    key=f"{CK}.beast_grapple", phase="before", rolls=("attack",), available=_has_beast("sea"),
    label=_both("Bestia del Mare: il bersaglio è Afferrato (CD per sfuggire pari alla tua CD degli incantesimi)",
                "Beast of the Sea: the target is Grappled (escape DC equal to your spell save DC)"),
    effect=lambda c, _i: _both(f"Il bersaglio è Afferrato: per sfuggire serve CD {_spell_dc(c)}.",
                               f"The target is Grappled: escaping takes DC {_spell_dc(c)}."))

BEAST_FORCE = RollOptionSpec(
    key=f"{CK}.beast_force", phase="before", rolls=("attack",), available=_beast_attack,
    label=_both("Addestramento Eccezionale: i colpi infliggono danni da forza invece del loro tipo",
                "Exceptional Training: the strikes deal force damage instead of their usual type"),
    effect=_say("Il Colpo della Bestia infligge danni da forza.", "The Beast's Strike deals force damage."))

BESTIAL_FURY_DAMAGE = RollOptionSpec(
    key=f"{CK}.bestial_fury_damage", phase="before", rolls=("attack",), once_per_turn=True, extra_dice=_mark_dice,
    pay_if_success=True,  # «la prima volta che colpisce»: su un mancato l'uso torna
    available=lambda c: _beast_attack(c) and hunters_mark_active(c),
    label=_both("Furia Bestiale: il bersaglio è la creatura marcata da Hunter's Mark? Danni da forza in più (una volta per turno)",
                "Bestial Fury: is the target the creature Hunter's Mark marks? Extra force damage (once per turn)"),
    effect=_say("Hunter's Mark: danni da forza in più, già nel totale.", "Hunter's Mark: extra force damage, already in the total."))


# ---------------------------------------------------------------------------
# Lanci gratuiti (Rinforzi Fatati, Vagabondo Nebbioso): lo stesso schema di Nemico Prescelto (R43)
# ---------------------------------------------------------------------------

def _free_use(state_key: str, spell: str, slot: str, toggle: bool = False) -> OnUse:
    turn_flag = {"action": "action_used", "bonus": "bonus_used"}[slot]

    def check(ctx: RuleContext, _params: dict) -> tuple[int, str] | None:
        if (ctx.char.turn_state or {}).get(turn_flag):
            return 409, "turn_slot_used"
        return (409, "feature_unavailable") if has_state(ctx.char, state_key) else None

    def effect(ctx: RuleContext, params: dict) -> None:
        data = {"free_cast": spell, "free_cast_slot": slot, "spell": spell, **({"no_concentration": True} if params.get("no_concentration") else {})}
        begin_state(ctx.char, StateSpec(state_key, ends_on=("manual", "rest_short", "rest_long"), data=data), f"{CK}.{state_key}", None)

    return OnUse(
        check=check, effect=effect,
        toggles=(UseToggle("no_concentration", _both("Rinuncia alla Concentrazione (dura 1 minuto)", "Give up Concentration (lasts 1 minute)")),) if toggle else (),
        message=lambda _c, _p: _both("Lancia l'incantesimo dalla pagina degli incantesimi, senza slot.", "Cast the spell from the spells page with no slot."))


# ---------------------------------------------------------------------------
# Viandante Fatato
# ---------------------------------------------------------------------------

def _strikes_dice(ctx: RuleContext, _inputs: dict) -> str:
    return "1d6" if ctx.class_level >= 11 else "1d4"


DREADFUL_STRIKES = RollOptionSpec(
    key=f"{CK}.dreadful_strikes", phase="after_hit", rolls=("attack",), once_per_turn=True, extra_dice=_strikes_dice, available=_weapon_attack,
    label=_both("Colpi Terribili: +1d4 danni psichici (1d6 dal 11°), una volta per turno", "Dreadful Strikes: +1d4 psychic damage (1d6 from 11th), once per turn"))

_CHARISMA_SKILLS = ("deception", "performance", "persuasion")


def _glamour_bonus(ctx: RuleContext) -> int:
    return max(1, _wis_mod(ctx))


GLAMOUR = Modifier("skill", _glamour_bonus,
                   when=lambda c: (c.roll == "skill" and SKILL_ABILITY_MAP.get(c.skill) == "charisma") or (c.roll == "ability" and c.ability == "charisma"),
                   source=f"feature:{CK}.otherworldly_glamour")

TWIST_SAVE = RollOptionSpec(
    key=f"{CK}.beguiling_twist_advantage", phase="before", rolls=("save",), mode="advantage",
    label=_both("Svolta Ammaliante: il tiro salvezza è contro l'essere Affascinato o Spaventato? Vantaggio",
                "Beguiling Twist: is the saving throw against being Charmed or Frightened? Advantage"))
_TWIST = {"charmed": _both("Affascinato", "Charmed"), "frightened": _both("Spaventato", "Frightened")}


def _twist_effect(ctx: RuleContext, params: dict) -> TargetEffect:
    return TargetEffect(condition=str(params["condition"]), save_ability="wisdom", save_dc=_spell_dc(ctx), rounds=10, repeat_save="end")


TWIST_USE = OnUse(
    slot="reaction", target_effect=_twist_effect,
    choices=(UseChoice("condition", _both("Condizione", "Condition"), lambda _c: list(_TWIST), lambda k: _TWIST[k]),))


# ---------------------------------------------------------------------------
# Stalker delle Tenebre
# ---------------------------------------------------------------------------

DREAD_KEY = f"{CK}.dreadful_strike"


def _dread_dice(ctx: RuleContext, _inputs: dict) -> str:
    return "2d8" if ctx.class_level >= 11 else "2d6"


DREADFUL_STRIKE = RollOptionSpec(
    key=DREAD_KEY, phase="after_hit", rolls=("attack",), once_per_turn=True, cost=Cost(feature_key=f"{CK}.dread_ambusher"),
    extra_dice=_dread_dice, available=_weapon_attack,
    label=_both("Colpo Terribile: +2d6 danni psichici (2d8 dal 11°), una volta per turno, spende un uso",
                "Dreadful Strike: +2d6 psychic damage (2d8 from 11th), once per turn, spends a use"))


def _ambush_started(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    begin_state(ctx.char, StateSpec("dread_ambusher_speed", ends_on=("new_turn", "turn_end_counted", "rest_short", "rest_long", "manual"),
                                    data={"skip_new_turns": 1}), f"{CK}.dread_ambusher", "Imboscatore Terribile")


AMBUSH_SPEED = RollOptionSpec(
    key=f"{CK}.dread_ambusher_speed", phase="before", rolls=("initiative",), on_confirm=_ambush_started,
    label=_both("Imboscatore Terribile: è l'inizio del combattimento? Velocità +3 m nel tuo primo turno",
                "Dread Ambusher: is this the start of combat? Speed +10 ft on your first turn"),
    effect=_say("Velocità +3 m fino alla fine del tuo primo turno.", "Speed +10 ft until the end of your first turn."))


def _dread_used(ctx: RuleContext) -> bool:
    return DREAD_KEY in ((ctx.turn or {}).get("once_per_turn") or [])


def _dread_offered(ctx: RuleContext) -> bool:
    """Paura di Massa è un effetto dell'uso di Colpo Terribile: si offre sul colpo che lo usa, non su uno successivo."""
    from core.rules.roll_options import _affordable  # import locale: roll_options usa il catalogo
    return DREAD_KEY in ctx.confirmed or _affordable(ctx.char, DREADFUL_STRIKE, ctx)


SUDDEN_STRIKE = RollOptionSpec(
    key=f"{CK}.sudden_strike", phase="before", rolls=("attack",), once_per_turn=True, group="stalkers_flurry", outside_action=True,
    available=lambda c: _weapon_attack(c) and _dread_used(c),
    label=_both("Colpo Improvviso: un attacco in più con la stessa arma contro un'altra creatura entro 1,5 m dal bersaglio, nella gittata",
                "Sudden Strike: an extra attack with the same weapon against another creature within 5 ft of the target, in range"))

MASS_FEAR = RollOptionSpec(
    key=f"{CK}.mass_fear", phase="after_hit", rolls=("attack",), once_per_turn=True, group="stalkers_flurry", needs=DREAD_KEY,
    available=lambda c: _weapon_attack(c) and _dread_offered(c),
    target_effect=lambda c, _i: TargetEffect(condition="frightened", save_ability="wisdom", save_dc=_spell_dc(c),
                                             ends_at={"anchor": "source", "edge": "start", "count": 1}),
    label=_both("Paura di Massa: il bersaglio e le creature entro 3 m fanno un TS Saggezza o sono Spaventati fino al tuo prossimo turno",
                "Mass Fear: the target and creatures within 10 ft make a Wisdom save or are Frightened until your next turn"),
    effect=lambda c, _i: _both(f"TS Saggezza CD {_spell_dc(c)}: chi fallisce è Spaventato fino all'inizio del tuo prossimo turno.",
                               f"Wisdom save DC {_spell_dc(c)}: those who fail are Frightened until the start of your next turn."))


# ---------------------------------------------------------------------------
# Cacciatore
# ---------------------------------------------------------------------------

MAD_ID = f"{CK}.multiattack_defense"


def _mad_started(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    begin_state(ctx.char, StateSpec("multiattack_defense", rounds=1, ends_on=("new_turn", "turn_end", "manual"),
                                    data={"others": [MAD_ID]}), MAD_ID, "Difesa dal Multiattacco")


MULTIATTACK_DEFENSE = RollOptionSpec(
    key=MAD_ID, phase="damage_in", rolls=("damage_taken",), on_confirm=_mad_started,
    label=_both("Difesa dal Multiattacco: ti ha colpito una creatura? Svantaggio ai suoi altri attacchi contro di te in questo turno",
                "Multiattack Defense: did a creature hit you? Disadvantage on its other attacks against you this turn"),
    effect=_say("Gli altri attacchi di quella creatura contro di te in questo turno hanno Svantaggio.",
                "That creature's other attacks against you this turn have Disadvantage."))

SUPERIOR_PREY = RollOptionSpec(
    key=f"{CK}.superior_hunters_prey", phase="after_hit", rolls=("attack",), once_per_turn=True, extra_dice=_mark_dice,
    separate_damage=True, crit_doubles=False,  # il dado è di una seconda creatura: fuori dal totale e senza raddoppio al critico
    available=lambda c: _weapon_attack(c) and hunters_mark_active(c),
    label=_both("Preda del Cacciatore Superiore: una seconda creatura entro 9 m dalla marcata subisce i danni di Hunter's Mark (una volta per turno)",
                "Superior Hunter's Prey: a second creature within 30 ft of the marked one takes Hunter's Mark's damage (once per turn)"))


def _defended_type(ctx: RuleContext) -> str | None:
    state = next((s for s in ctx.char.active_states or [] if s.get("key") == "superior_hunters_defense"), None)
    return (state.get("data") or {}).get("damage_type") if state else None


def _shd_started(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    begin_state(ctx.char, StateSpec("superior_hunters_defense", rounds=1, ends_on=("new_turn", "turn_end", "manual"),
                                    data={"others": [f"{CK}.superior_hunters_defense"], "damage_type": ctx.damage_type}),
                f"{CK}.superior_hunters_defense",
                "Difesa del Cacciatore Superiore")


SUPERIOR_DEFENSE = RollOptionSpec(
    key=f"{CK}.superior_hunters_defense", phase="damage_in", rolls=("damage_taken",), slot="reaction", grants_resistance=True, on_confirm=_shd_started,
    label=_both("Difesa del Cacciatore Superiore: subisci danni? Reazione, resistenza a quel tipo fino a fine turno (danni dimezzati)",
                "Superior Hunter's Defense: taking damage? Reaction, resistance to that type until end of turn (damage halved)"))


def _prey(key: str, title: str, name: tuple[str, str], summary: tuple[str, str], **kw: Any):
    return _sub("hunter", key, 3, title, name, summary, option_group="hunters_prey", option_key=key, passive=True, **kw)


def _tactic(key: str, title: str, name: tuple[str, str], summary: tuple[str, str], **kw: Any):
    return _sub("hunter", key, 7, title, name, summary, option_group="defensive_tactics", option_key=key, passive=True, **kw)


def _choice_row(key: str, level: int, title: str, name: tuple[str, str], summary: tuple[str, str], options: tuple[str, ...]):
    return _sub("hunter", key, level, title, name, summary, no_row=True,
                choices=(ChoiceSpec(group=key, levels={level: 1}, options=lambda _c: list(options), replaceable=True),),
                covered_by=f"ChoiceSpec {key} di questa riga e le righe delle opzioni; test_hunters_prey_is_chosen_at_level_3_and_only_the_chosen_one_works")


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

# Mente di Ferro a chi ha già il TS su Saggezza: la competenza va su Intelligenza o Carisma
_IRON_MIND_SAVES = {k: {"name": _both(it, en), "summary": _both("", "")}
                    for k, it, en in (("intelligence", "Intelligenza", "Intelligence"), ("charisma", "Carisma", "Charisma"))}

BM, FW, GS, HU = "beast_master", "fey_wanderer", "gloom_stalker", "hunter"
SUBCLASS_ROWS = (
    # Signore delle Bestie
    _sub(BM, "primal_companion", 3, "Compagno Primordiale / Primal Companion (Signore delle Bestie 3, pag. 122)",
         ("Compagno Primordiale", "Primal Companion"),
         ("Evochi una bestia primordiale (Terra, Cielo o Mare), una per volta; un uso a riposo lungo, o uno slot per rialzarla. "
          "Da sola Schiva: il Colpo lo ordini con l'azione bonus o cedendo un attacco.",
          "You summon a primal beast (Land, Sky or Sea), one at a time; one use per long rest, or a slot to raise it. "
          "Alone it Dodges: you order its Beast's Strike with a bonus action or by giving up an attack."),
         None, uses=Uses(table={3: 1}), restoration="long_rest", on_use=PRIMAL_USE),
    _sub(BM, "beast_of_the_land", 3, "Bestia della Terra / Beast of the Land (Signore delle Bestie 3, pag. 123)",
         ("Bestia della Terra", "Beast of the Land"),
         ("Media; CA 13 + Saggezza, PF 5 + 5 per livello, 12 m e scalare 12 m. Colpo della Bestia 1d8 + 2 + Saggezza; dopo una corsa di 6 m +1d6 e Prono.",
          "Medium; AC 13 + Wisdom, HP 5 + 5 per level, 40 ft and climb 40 ft. Beast's Strike 1d8 + 2 + Wisdom; after a 20 ft run +1d6 and Prone."),
         roll_options=(BEAST_CHARGE,), passive=True),
    _sub(BM, "beast_of_the_sky", 3, "Bestia del Cielo / Beast of the Sky (Signore delle Bestie 3, pag. 124)",
         ("Bestia del Cielo", "Beast of the Sky"),
         ("Piccola; CA 13 + Saggezza, PF 4 + 4 per livello, volare 18 m, Volo Radente. Colpo della Bestia 1d4 + 3 + Saggezza tagliente.",
          "Small; AC 13 + Wisdom, HP 4 + 4 per level, fly 60 ft, Flyby. Beast's Strike 1d4 + 3 + Wisdom slashing."), passive=True),
    _sub(BM, "beast_of_the_sea", 3, "Bestia del Mare / Beast of the Sea (Signore delle Bestie 3, pag. 124)",
         ("Bestia del Mare", "Beast of the Sea"),
         ("Media; CA 13 + Saggezza, PF 5 + 5 per livello, nuotare 18 m, Anfibio. Colpo della Bestia 1d6 + 2 + Saggezza che Afferra (CD degli incantesimi).",
          "Medium; AC 13 + Wisdom, HP 5 + 5 per level, swim 60 ft, Amphibious. Beast's Strike 1d6 + 2 + Wisdom that Grapples (spell save DC)."),
         roll_options=(BEAST_GRAPPLE,), passive=True),
    _sub(BM, "exceptional_training", 7, "Addestramento Eccezionale / Exceptional Training (Signore delle Bestie 7, pag. 123)",
         ("Addestramento Eccezionale", "Exceptional Training"),
         ("Con l'azione bonus la bestia può anche Scattare, Disimpegnarsi, Schivare o Aiutare, e compie un Colpo della Bestia; i colpi possono fare danni da forza.",
          "With a bonus action the beast can also Dash, Disengage, Dodge or Help, and makes a Beast's Strike; its strikes can deal force damage."),
         roll_options=(BEAST_FORCE,), passive=True),
    _sub(BM, "bestial_fury", 11, "Furia Bestiale / Bestial Fury (Signore delle Bestie 11, pag. 123)", ("Furia Bestiale", "Bestial Fury"),
         ("Il Colpo della Bestia due volte per ordine; la prima volta per turno che colpisce una creatura marcata da Hunter's Mark, danni da forza in più.",
          "Beast's Strike twice per command; the first time each turn it hits a creature marked by Hunter's Mark, extra force damage."),
         roll_options=(BESTIAL_FURY_DAMAGE,), passive=True),
    _sub(BM, "share_spells", 15, "Condividere Incantesimi / Share Spells (Signore delle Bestie 15, pag. 123)",
         ("Condividere Incantesimi", "Share Spells"),
         ("Lanciando un incantesimo che ha come bersaglio solo te, con la bestia entro 9 m, l'effetto vale anche per lei.",
          "When you cast a spell that targets only you, with the beast within 30 ft, it affects the beast too."),
         roll_options=(SHARE_SPELLS_EXTEND,), passive=True),

    # Viandante Fatato
    _sub(FW, "dreadful_strikes", 3, "Colpi Terribili / Dreadful Strikes (Viandante Fatato 3, pag. 124)", ("Colpi Terribili", "Dreadful Strikes"),
         ("Una volta per turno, colpendo con un'arma, +1d4 danni psichici (1d6 dall'11°).",
          "Once per turn, hitting with a weapon, +1d4 psychic damage (1d6 from 11th)."), roll_options=(DREADFUL_STRIKES,), passive=True),
    *_spell_rows(FW, "Incantesimi del Viandante Fatato / Fey Wanderer Spells (Viandante Fatato 3, pag. 124)",
                 ("Incantesimi del Viandante Fatato", "Fey Wanderer Spells")),
    _sub(FW, "feywild_gifts", 3, "Doni del Feywild / Feywild Gifts (Viandante Fatato 3, pag. 124)", ("Doni del Feywild", "Feywild Gifts"),
         ("Un dono estetico del Feywild, a scelta o a sorte: solo un tratto della scheda.", "An aesthetic Feywild gift, chosen or rolled: a sheet trait only."),
         passive=True),
    _sub(FW, "otherworldly_glamour", 3, "Fascino dell'Altro Mondo / Otherworldly Glamour (Viandante Fatato 3, pag. 124)",
         ("Fascino dell'Altro Mondo", "Otherworldly Glamour"),
         ("Alle prove di Carisma si somma la Saggezza (minimo +1); competenza in Inganno, Intrattenere o Persuasione, a scelta.",
          "Add your Wisdom (minimum +1) to Charisma checks; proficiency in Deception, Performance or Persuasion, your choice."),
         modifiers=(GLAMOUR,), passive=True,
         choices=(ChoiceSpec(group="otherworldly_glamour", levels={3: 1}, options=lambda _c: list(_CHARISMA_SKILLS), label=skill_label, grants="proficient"),)),
    _sub(FW, "beguiling_twist", 7, "Svolta Ammaliante / Beguiling Twist (Viandante Fatato 7, pag. 125)", ("Svolta Ammaliante", "Beguiling Twist"),
         ("Vantaggio ai TS contro Affascinato e Spaventato. Reazione: un'altra creatura entro 36 m fa un TS Saggezza o è Affascinata o Spaventata (1 minuto).",
          "Advantage on saves against Charmed and Frightened. Reaction: another creature within 120 ft makes a Wisdom save or is Charmed or Frightened (1 minute)."),
         "reaction", roll_options=(TWIST_SAVE,), on_use=TWIST_USE),
    _sub(FW, "fey_reinforcements", 11, "Rinforzi Fatati / Fey Reinforcements (Viandante Fatato 11, pag. 125)", ("Rinforzi Fatati", "Fey Reinforcements"),
         ("Summon Fey gratis una volta per riposo lungo, senza materiali; puoi rinunciare alla Concentrazione (dura 1 minuto).",
          "Summon Fey free once per long rest, no materials; you can give up Concentration (it lasts 1 minute)."),
         "action", uses=Uses(table={11: 1}), restoration="long_rest", on_use=_free_use("fey_reinforcements_free", "summon-fey", "action", toggle=True)),
    _sub(FW, "misty_wanderer", 15, "Vagabondo Nebbioso / Misty Wanderer (Viandante Fatato 15, pag. 125)", ("Vagabondo Nebbioso", "Misty Wanderer"),
         ("Misty Step gratis (azione bonus), usi pari a Saggezza (minimo 1), riposo lungo; porti con te una creatura consenziente entro 1,5 m.",
          "Misty Step free (bonus action), uses equal to Wisdom (minimum 1), long rest; bring a willing creature within 5 ft."),
         "bonus_action", uses=Uses(ability="wisdom", minimum=1), restoration="long_rest", on_use=_free_use("misty_wanderer_free", "misty-step", "bonus")),

    # Stalker delle Tenebre
    _sub(GS, "dread_ambusher", 3, "Imboscatore Terribile / Dread Ambusher (Stalker delle Tenebre 3, pag. 125)", ("Imboscatore Terribile", "Dread Ambusher"),
         ("Iniziativa + Saggezza; Velocità +3 m nel primo turno del combattimento. Colpo Terribile: +2d6 psichici (2d8 dall'11°) una volta per turno, usi pari a Saggezza (minimo 1), riposo lungo.",
          "Initiative + Wisdom; Speed +10 ft on the first turn of combat. Dreadful Strike: +2d6 psychic (2d8 from 11th) once per turn, uses equal to Wisdom (minimum 1), long rest."),
         uses=Uses(ability="wisdom", minimum=1), restoration="long_rest", roll_options=(DREADFUL_STRIKE, AMBUSH_SPEED), passive=True,
         modifiers=(Modifier("initiative", _wis_mod, source=f"feature:{CK}.dread_ambusher"),
                    Modifier("speed", 10, when=lambda c: state_on(c, "dread_ambusher_speed"), source=f"feature:{CK}.dread_ambusher"))),
    *_spell_rows(GS, "Incantesimi dello Stalker delle Tenebre / Gloom Stalker Spells (Stalker delle Tenebre 3, pag. 126)",
                 ("Incantesimi dello Stalker delle Tenebre", "Gloom Stalker Spells")),
    _sub(GS, "umbral_sight", 3, "Vista Ombrale / Umbral Sight (Stalker delle Tenebre 3, pag. 126)", ("Vista Ombrale", "Umbral Sight"),
         ("Scurovisione 18 m (o +18 m se l'hai già); nell'oscurità totale sei invisibile a chi si affida alla Scurovisione (lo applica il DM).",
          "Darkvision 60 ft (or +60 ft if you have it); in total darkness you are invisible to creatures relying on Darkvision (the GM applies it)."),
         modifiers=(Modifier("sense:darkvision", _owl_range, source=f"feature:{CK}.umbral_sight"),), passive=True),
    _sub(GS, "iron_mind", 7, "Mente di Ferro / Iron Mind (Stalker delle Tenebre 7, pag. 126)", ("Mente di Ferro", "Iron Mind"),
         ("Competenza nei tiri salvezza su Saggezza.", "Proficiency in Wisdom saving throws."),
         modifiers=(Modifier("save", lambda c: c.char.proficiency_bonus, when=_lacks_wisdom_save_proficiency, source=f"feature:{CK}.iron_mind"),),
         passive=True,
         choices=(ChoiceSpec(group="iron_mind", levels={7: 1}, options=lambda _c: list(_IRON_MIND_SAVES), label=lambda k: _IRON_MIND_SAVES[k],
                             grants="save", applies=lambda c: bool((c.char.saving_throws or {}).get("wisdom"))),)),
    _sub(GS, "stalkers_flurry", 11, "Raffica dello Stalker / Stalker's Flurry (Stalker delle Tenebre 11, pag. 126)", ("Raffica dello Stalker", "Stalker's Flurry"),
         ("Colpo Terribile a 2d8. Usandolo, una volta per turno scegli Colpo Improvviso o Paura di Massa.",
          "Dreadful Strike becomes 2d8. When you use it, once per turn you choose Sudden Strike or Mass Fear."), passive=True),
    _sub(GS, "sudden_strike", 11, "Colpo Improvviso / Sudden Strike (Stalker delle Tenebre 11, pag. 126)", ("Colpo Improvviso", "Sudden Strike"),
         ("Dopo il Colpo Terribile, un attacco in più con la stessa arma contro un'altra creatura entro 1,5 m dal bersaglio.",
          "After Dreadful Strike, an extra attack with the same weapon against another creature within 5 ft of the target."),
         roll_options=(SUDDEN_STRIKE,), passive=True),
    _sub(GS, "mass_fear", 11, "Paura di Massa / Mass Fear (Stalker delle Tenebre 11, pag. 126)", ("Paura di Massa", "Mass Fear"),
         ("Dopo il Colpo Terribile: TS Saggezza (CD incantesimi) del bersaglio e delle creature entro 3 m; chi fallisce è Spaventato fino al tuo prossimo turno.",
          "After Dreadful Strike: Wisdom save (spell save DC) for the target and creatures within 10 ft; those who fail are Frightened until your next turn."),
         roll_options=(MASS_FEAR,), passive=True),
    _sub(GS, "shadowy_dodge", 15, "Schivata d'Ombra / Shadowy Dodge (Stalker delle Tenebre 15, pag. 126)", ("Schivata d'Ombra", "Shadowy Dodge"),
         ("Reazione quando sei attaccato senza svantaggio: l'attacco ha Svantaggio e ti teletrasporti fino a 9 m.",
          "Reaction when attacked without disadvantage: the attack has Disadvantage and you teleport up to 30 ft."),
         "reaction", on_use=OnUse(slot="reaction", message=lambda _c, _p: _both("L'attacco ha Svantaggio; ti teletrasporti fino a 9 m.",
                                                                                "The attack has Disadvantage; you teleport up to 30 ft."))),

    # Cacciatore
    _sub(HU, "hunters_lore", 3, "Sapere del Cacciatore / Hunter's Lore (Cacciatore 3, pag. 127)", ("Sapere del Cacciatore", "Hunter's Lore"),
         ("Il DM ti dice immunità, resistenze e vulnerabilità della creatura marcata.", "The GM tells you the marked creature's immunities, resistances and vulnerabilities."),
         passive=True),
    _choice_row("hunters_prey", 3, "Preda del Cacciatore / Hunter's Prey (Cacciatore 3, pag. 127)", ("Preda del Cacciatore", "Hunter's Prey"),
                ("Al 3° livello scegli Sterminatore di Colossi o Devastatore dell'Orda; dopo un riposo puoi cambiare.",
                 "At 3rd level you choose Colossus Slayer or Horde Breaker; you can change it after a rest."),
                ("colossus_slayer", "horde_breaker")),
    _prey("colossus_slayer", "Sterminatore di Colossi / Colossus Slayer (Cacciatore 3, pag. 127)", ("Sterminatore di Colossi", "Colossus Slayer"),
          ("Una volta per turno, colpendo con un'arma una creatura che ha perso PF, +1d8 danni.",
           "Once per turn, hitting a creature that is missing hit points with a weapon, +1d8 damage."), roll_options=(COLOSSUS_SLAYER,)),
    _prey("horde_breaker", "Devastatore dell'Orda / Horde Breaker (Cacciatore 3, pag. 127)", ("Devastatore dell'Orda", "Horde Breaker"),
          ("Una volta per turno, un attacco in più con la stessa arma contro un'altra creatura entro 1,5 m dal bersaglio, non ancora attaccata.",
           "Once per turn, an extra attack with the same weapon against another creature within 5 ft of the target, not yet attacked."),
          roll_options=(HORDE_BREAKER,)),
    _choice_row("defensive_tactics", 7, "Tattiche Difensive / Defensive Tactics (Cacciatore 7, pag. 127)", ("Tattiche Difensive", "Defensive Tactics"),
                ("Al 7° livello scegli Fuggire dall'Orda o Difesa dal Multiattacco; dopo un riposo puoi cambiare.",
                 "At 7th level you choose Escape the Horde or Multiattack Defense; you can change it after a rest."),
                ("escape_the_horde", "multiattack_defense")),
    _tactic("escape_the_horde", "Fuggire dall'Orda / Escape the Horde (Cacciatore 7, pag. 127)", ("Fuggire dall'Orda", "Escape the Horde"),
            ("Gli attacchi di opportunità contro di te hanno Svantaggio.", "Opportunity attacks against you have Disadvantage."),
            permanent_state=_permanent_note("escape_the_horde")),
    _tactic("multiattack_defense", "Difesa dal Multiattacco / Multiattack Defense (Cacciatore 7, pag. 127)", ("Difesa dal Multiattacco", "Multiattack Defense"),
            ("Dopo che una creatura ti colpisce, i suoi altri attacchi contro di te in questo turno hanno Svantaggio.",
             "After a creature hits you, its other attacks against you this turn have Disadvantage."), roll_options=(MULTIATTACK_DEFENSE,)),
    _sub(HU, "superior_hunters_prey", 11, "Preda del Cacciatore Superiore / Superior Hunter's Prey (Cacciatore 11, pag. 127)",
         ("Preda del Cacciatore Superiore", "Superior Hunter's Prey"),
         ("Una volta per turno, i danni di Hunter's Mark colpiscono anche una seconda creatura entro 9 m dalla marcata.",
          "Once per turn, Hunter's Mark's damage also hits a second creature within 30 ft of the marked one."),
         roll_options=(SUPERIOR_PREY,), passive=True),
    _sub(HU, "superior_hunters_defense", 15, "Difesa del Cacciatore Superiore / Superior Hunter's Defense (Cacciatore 15, pag. 127)",
         ("Difesa del Cacciatore Superiore", "Superior Hunter's Defense"),
         ("Reazione quando subisci danni: resistenza a quel tipo fino alla fine del turno, anche per il danno che l'ha innescata.",
          "Reaction when you take damage: resistance to that type until the end of the turn, including the triggering damage."),
         "reaction", roll_options=(SUPERIOR_DEFENSE,), passive=True,
         modifiers=tuple(Modifier(f"resistance:{t}", 1, when=lambda c, t=t: _defended_type(c) == t, source=f"feature:{CK}.superior_hunters_defense")
                         for t in DAMAGE_TYPES)),
)

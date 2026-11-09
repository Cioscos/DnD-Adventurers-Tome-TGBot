"""Guerriero 2014 e i suoi archetipi: Campione, Maestro di Battaglia e Cavaliere Mistico.

Valori dalla scheda ``docs/superpowers/rules/2014/classes/fighter.md``; i testi sono nostri, mai quelli del manuale.
Gli stili di combattimento sono opzioni di una scelta (``fighting_style``) e agiscono con ``Modifier`` sui tiri; le manovre
del Maestro di Battaglia sono opzioni di una scelta (``maneuvers``) e conferme al tiro che spendono un dado di superiorità.
"""
from __future__ import annotations

from typing import Any

from core.data.damage_types import LABELS_IT, canonical_damage_type
from core.game.item_bonuses import item_meta
from core.rules.catalog._common import feature, save_spell as _save_spell, state_on, style_options
from core.rules.states import begin_state, has_state
from core.rules.types import (
    ChoiceSpec, Cost, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, TargetEffect, Uses, UseToggle,
)

ED, CK = "2014", "fighter"
SW, AS, IND, SD = f"{CK}.second_wind", f"{CK}.action_surge", f"{CK}.indomitable", f"{CK}.superiority_dice"
STYLES = ("archery", "defense", "dueling", "great_weapon", "two_weapon", "protection")
MANEUVER_GROUP = "maneuvers"
ONE_MANEUVER = f"{CK}.maneuver"  # una sola manovra per attacco


# ---------------------------------------------------------------------------
# Predicati comuni
# ---------------------------------------------------------------------------

def _weapon_attack(ctx: RuleContext) -> bool:
    """Un attacco con arma (anche il colpo senz'armi, che è un attacco con arma da mischia): non un incantesimo né
    l'attacco di un compagno."""
    return ctx.roll == "attack" and ctx.spell is None and (ctx.item is not None or ctx.attack_mode == "melee")


def _weapon_in_hand(ctx: RuleContext) -> bool:
    return ctx.spell is None and ctx.item is not None


def _props(item: Any) -> str:
    return " ".join(str(p).lower() for p in item_meta(item).get("properties") or [])


def _two_hands(ctx: RuleContext) -> bool:
    """L'arma è impugnata con due mani: a due mani per sua natura, o versatile impugnata così."""
    props = _props(ctx.item)
    return "two_handed" in props.replace("-", "_").replace(" ", "_") or "due mani" in props or (
        "versatile" in props and ctx.grip == "two")


def _wears_armor(ctx: RuleContext) -> bool:
    return any(i.is_equipped and i.item_type == "armor" for i in ctx.char.items or [])


def _wields_shield(ctx: RuleContext) -> bool:
    return any(i.is_equipped and i.item_type == "shield" for i in ctx.char.items or [])


def _is_ranged_weapon(ctx: RuleContext) -> bool:
    return _weapon_in_hand(ctx) and item_meta(ctx.item).get("weapon_type", "melee") == "ranged"


def _alone_in_hand(ctx: RuleContext) -> bool:
    """Nessun'altra arma impugnata; lo scudo non conta (il manuale non lo esclude)."""
    return not any(i.is_equipped and i.item_type == "weapon" and i.id != ctx.item.id for i in ctx.char.items or [])


def _dueling(ctx: RuleContext) -> bool:
    return (ctx.roll == "damage" and _weapon_in_hand(ctx) and ctx.attack_mode == "melee" and not ctx.offhand
            and not _two_hands(ctx) and _alone_in_hand(ctx))


def _great_weapon(ctx: RuleContext) -> bool:
    return ctx.roll == "damage" and _weapon_in_hand(ctx) and ctx.attack_mode == "melee" and _two_hands(ctx)


def _off_hand_modifier(ctx: RuleContext) -> int:
    from core.game.stats import roll_ability_mod  # import locale: stats usa il catalogo
    return max(0, roll_ability_mod(ctx.char, ctx.ability)) if ctx.ability else 0


# ---------------------------------------------------------------------------
# Stile di Combattimento
# ---------------------------------------------------------------------------

def _protection_effect(_ctx: RuleContext, _params: dict) -> TargetEffect:
    """Svantaggio al tiro per colpire dell'attaccante: lo vede il GM sul combattente scelto, per il suo turno (D1)."""
    return TargetEffect(condition="custom:protection", rounds=1)


def _style(key: str, title: str, name: tuple[str, str], summary: tuple[str, str], action_type: str | None = None, **kw: Any):
    return feature(f"style_{key}", CK, ED, 1, title, name, summary, action_type, option_group="fighting_style",
                   option_key=key, **kw)


STYLE_ROWS = (
    _style("archery", "Tiro / Archery (Stile di Combattimento, Guerriero 1, pag. 72)", ("Tiro", "Archery"),
           ("+2 ai tiri per colpire con armi a distanza (non con quelle da lancio da mischia).",
            "+2 to attack rolls with ranged weapons (not with melee weapons you throw)."),
           modifiers=(Modifier("attack", 2, when=lambda c: c.roll == "attack" and _is_ranged_weapon(c),
                               source=f"feature:{CK}.style_archery"),)),
    _style("defense", "Difesa / Defense (Stile di Combattimento, Guerriero 1, pag. 72)", ("Difesa", "Defense"),
           ("+1 alla CA finché indossi un'armatura (lo scudo da solo non basta).",
            "+1 to AC while you wear armor (a shield alone does not count)."),
           modifiers=(Modifier("ac", 1, when=lambda c: c.roll == "ac" and _wears_armor(c),
                               source=f"feature:{CK}.style_defense"),)),
    _style("dueling", "Duellare / Dueling (Stile di Combattimento, Guerriero 1, pag. 72)", ("Duellare", "Dueling"),
           ("+2 al danno con un'arma da mischia impugnata a una mano, se non impugni altre armi (lo scudo va bene).",
            "+2 damage with a melee weapon held in one hand when you hold no other weapon (a shield is fine)."),
           modifiers=(Modifier("damage", 2, when=_dueling, source=f"feature:{CK}.style_dueling"),)),
    _style("great_weapon",
           "Combattere con Armi Possenti / Great Weapon Fighting (Stile di Combattimento, Guerriero 1, pag. 72)",
           ("Combattere con Armi Possenti", "Great Weapon Fighting"),
           ("Con un'arma da mischia a due mani, i dadi dell'arma che mostrano 1 o 2 si ritirano una volta e vale il nuovo risultato.",
            "With a melee weapon held in two hands, weapon dice showing 1 or 2 are rerolled once and the new result stands."),
           modifiers=(Modifier("damage_reroll", 2, when=_great_weapon, source=f"feature:{CK}.style_great_weapon"),)),
    _style("two_weapon", "Combattere con Due Armi / Two-Weapon Fighting (Stile di Combattimento, Guerriero 1, pag. 72)",
           ("Combattere con Due Armi", "Two-Weapon Fighting"),
           ("Il danno dell'attacco con la seconda arma include il modificatore di caratteristica.",
            "The damage of the attack with the second weapon includes the ability modifier."),
           modifiers=(Modifier("damage", _off_hand_modifier,
                               when=lambda c: c.roll == "damage" and c.offhand and _weapon_in_hand(c),
                               source=f"feature:{CK}.style_two_weapon"),)),
    _style("protection", "Protezione / Protection (Stile di Combattimento, Guerriero 1, pag. 72)", ("Protezione", "Protection"),
           ("Reazione, con uno scudo: una creatura che vedi attacca un altro bersaglio entro 1,5 m da te e ha svantaggio al tiro.",
            "Reaction, with a shield: a creature you see attacks a target other than you within 5 ft of you and has disadvantage."),
           "reaction", on_use=OnUse(slot="reaction", available=_wields_shield, target_effect=_protection_effect)),
)


def _style_choice(levels: dict[int, int]) -> ChoiceSpec:
    return ChoiceSpec(group="fighting_style", levels=levels, options=style_options(STYLES))


# ---------------------------------------------------------------------------
# Recuperare Energie, Azione Impetuosa, Indomito
# ---------------------------------------------------------------------------

def _arcane_charge_toggle(ctx: RuleContext) -> bool:
    return ctx.class_row.subclass_key == "eldritch_knight" and ctx.class_level >= 15


def _arcane_charge_notes(ctx: RuleContext, params: dict) -> list[str]:
    return ["arcane_charge"] if params.get("arcane_charge") and _arcane_charge_toggle(ctx) else []


INDOMITABLE_REROLL = RollOptionSpec(
    key=IND, phase="after_roll", after="reroll", rolls=("save",), cost=Cost(feature_key=IND),
    label={"it": "Indomito: ripeti il tiro salvezza fallito (vale il nuovo risultato)",
           "en": "Indomitable: reroll the failed saving throw (the new result stands)"})


# ---------------------------------------------------------------------------
# Campione
# ---------------------------------------------------------------------------

def _athlete_bonus(ctx: RuleContext) -> int:
    """Metà competenza per eccesso, al netto di ciò che Factotum ha già messo sul totale (vale il maggiore dei due)."""
    from core.game.skills import jack_of_all_trades_part  # import locale: skills usa stats, che usa il catalogo
    return max(0, (ctx.char.proficiency_bonus + 1) // 2 - jack_of_all_trades_part(ctx.char))


def _athlete_applies(ctx: RuleContext) -> bool:
    if ctx.ability not in ("strength", "dexterity", "constitution"):
        return False
    if ctx.roll == "initiative":
        return True
    return ctx.roll in ("skill", "ability") and not (ctx.skill and (ctx.char.skills or {}).get(ctx.skill))


def _survivor_heal(ctx: RuleContext) -> int:
    """5 + Costituzione a inizio turno, fino a metà dei PF massimi e mai a 0 PF."""
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    from core.rules.modifiers import effective_hp_max  # import locale: modifiers usa il catalogo
    hp = ctx.char.current_hit_points
    if hp <= 0 or hp * 2 > effective_hp_max(ctx.char):
        return 0
    return max(0, 5 + effective_ability_mod(ctx.char, "constitution"))


# ---------------------------------------------------------------------------
# Maestro di Battaglia
# ---------------------------------------------------------------------------

def _die_sides(level: int) -> int:
    return 12 if level >= 18 else 10 if level >= 10 else 8


def _die(ctx: RuleContext) -> str:
    return f"1d{_die_sides(ctx.class_level)}"


def _die_dice(ctx: RuleContext, _inputs: dict) -> str:
    return _die(ctx)


def _dc(ctx: RuleContext) -> int:
    """CD delle manovre: 8 + competenza + Forza o Destrezza, a scelta del guerriero (qui la migliore)."""
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    best = max(effective_ability_mod(ctx.char, a) for a in ("strength", "dexterity"))
    return 8 + ctx.char.proficiency_bonus + best


# (chiave, nome it, nome en)
MANEUVERS = (
    ("goading", "Attacco Adescante", "Goading Attack"), ("lunging", "Attacco con Affondo", "Lunging Attack"),
    ("feinting", "Attacco con Finta", "Feinting Attack"), ("maneuvering", "Attacco con Manovra", "Maneuvering Attack"),
    ("sweeping", "Attacco con Spazzata", "Sweeping Attack"), ("pushing", "Attacco con Spinta", "Pushing Attack"),
    ("disarming", "Attacco Disarmante", "Disarming Attack"), ("menacing", "Attacco Minaccioso", "Menacing Attack"),
    ("precision", "Attacco Preciso", "Precision Attack"), ("trip", "Attacco Sbilanciante", "Trip Attack"),
    ("commanders_strike", "Colpo del Comandante", "Commander's Strike"),
    ("distracting", "Colpo Distraente", "Distracting Strike"), ("rally", "Incoraggiamento", "Rally"),
    ("parry", "Parata", "Parry"), ("riposte", "Replica", "Riposte"), ("evasive_footwork", "Scarto Elusivo", "Evasive Footwork"),
)
FEINT_STRIKE_KEY = f"{CK}.maneuver_feinting_strike"  # la conferma all'attacco della Finta, non una riga del catalogo
MANEUVER_KEYS = frozenset({*(f"{CK}.maneuver_{k}" for k, _it, _en in MANEUVERS), FEINT_STRIKE_KEY})


def _key(maneuver: str) -> str:
    return f"{CK}.maneuver_{maneuver}"


def _other_maneuver_used(ctx: RuleContext) -> bool:
    """Una manovra è già stata confermata per questo attacco (nelle fasi precedenti): al massimo una per attacco."""
    return bool(set(ctx.confirmed) & MANEUVER_KEYS)


def _after(ctx: RuleContext) -> bool:
    return _weapon_in_hand(ctx) and not _other_maneuver_used(ctx)


def _melee_after(ctx: RuleContext) -> bool:
    return _after(ctx) and ctx.attack_mode in ("melee", "offhand")


def _say(it: str, en: str):
    return lambda _ctx, _inputs: {"it": it, "en": en}


def _dc_say(it: str, en: str):
    """Esito con la CD delle manovre (il TS lo tira il bersaglio, lo segna il GM: D1)."""
    return lambda ctx, _inputs: {"it": it.format(dc=_dc(ctx)), "en": en.format(dc=_dc(ctx))}


def _till_my_next_turn() -> dict:
    return {"anchor": "source", "edge": "end", "count": 1}


def _rider(maneuver: str, label: tuple[str, str], *, melee: bool = False, **kw: Any) -> RollOptionSpec:
    """Una manovra che dopo un colpo con arma aggiunge il dado di superiorità al danno."""
    return RollOptionSpec(
        key=_key(maneuver), phase="after_hit", rolls=("attack",), group=ONE_MANEUVER, extra_dice=_die_dice,
        cost=Cost(feature_key=SD), available=_melee_after if melee else _after, label={"it": label[0], "en": label[1]}, **kw)


def _start_note(maneuver: str, name: str):
    """Un effetto senza condizione sul bersaglio o su un alleato: lo stato con `others` lo mostra a GM e gruppo (R36)."""
    key = _key(maneuver)

    def confirmed(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
        begin_state(ctx.char, StateSpec(f"maneuver_{maneuver}", rounds=1, ends_on=("new_turn", "manual"),
                                        data={"others": [key]}), key, name)
    return confirmed


GOADING = _rider(
    "goading", ("Attacco Adescante: +dado al danno, il bersaglio fa un TS Saggezza o ha svantaggio contro altri",
                "Goading Attack: +die to damage, the target makes a Wisdom save or has disadvantage against others"),
    effect=_dc_say("Il bersaglio fa un TS Saggezza CD {dc}: se fallisce ha svantaggio agli attacchi contro chiunque non sia te, fino alla fine del tuo prossimo turno.",
                   "The target makes a DC {dc} Wisdom save: on a failure it has disadvantage on attacks against anyone but you, until the end of your next turn."),
    target_effect=lambda ctx, _i: TargetEffect(condition="custom:goaded", save_ability="wisdom", save_dc=_dc(ctx),
                                               ends_at=_till_my_next_turn()))
LUNGING = RollOptionSpec(
    key=_key("lunging"), phase="before", rolls=("attack",), group=ONE_MANEUVER, extra_dice=_die_dice,
    cost=Cost(feature_key=SD), available=lambda c: _weapon_in_hand(c) and c.attack_mode in ("melee", "offhand"),
    label={"it": "Attacco con Affondo: portata +1,5 m per questo attacco, se colpisce +dado al danno",
           "en": "Lunging Attack: +5 ft reach for this attack, +die to damage if it hits"},
    effect=_say("Portata aumentata di 1,5 m per questo attacco.", "Reach increased by 5 ft for this attack."))
FEINT_STRIKE = RollOptionSpec(
    key=FEINT_STRIKE_KEY, phase="before", rolls=("attack",), group=ONE_MANEUVER, mode="advantage",
    extra_dice=_die_dice, cost=Cost(state_key="feinting_attack"),
    available=lambda c: _weapon_in_hand(c) and state_on(c, "feinting_attack"),
    label={"it": "Finta: l'attacco è contro la creatura che hai fintato (vantaggio, +dado al danno se colpisce)?",
           "en": "Feint: is the attack against the creature you feinted (advantage, +die to damage on a hit)?"})
MANEUVERING = _rider(
    "maneuvering", ("Attacco con Manovra: +dado al danno, un alleato si muove senza provocare",
                    "Maneuvering Attack: +die to damage, an ally moves without provoking"),
    effect=_say("Un alleato che ti vede o ti sente usa la reazione per muoversi fino a metà velocità, senza provocare attacchi di opportunità dal bersaglio.",
                "An ally who sees or hears you uses their reaction to move up to half speed, without provoking opportunity attacks from the target."),
    on_confirm=_start_note("maneuvering", "Attacco con Manovra"))
SWEEPING = _rider(
    "sweeping", ("Attacco con Spazzata: il dado va a una seconda creatura entro 1,5 m dal bersaglio, se il tiro la colpirebbe",
                 "Sweeping Attack: the die hits a second creature within 5 ft of the target, if the roll would hit it"),
    melee=True, crit_doubles=False, separate_damage=True,
    effect=lambda ctx, _i: _sweeping_effect(ctx))
PUSHING = _rider(
    "pushing", ("Attacco con Spinta: +dado al danno, TS Forza o il bersaglio (Grande o più piccolo) è spinto di 4,5 m",
                "Pushing Attack: +die to damage, Strength save or the target (Large or smaller) is pushed 15 ft"),
    effect=_dc_say("Se il bersaglio è Grande o più piccolo fa un TS Forza CD {dc}: se fallisce è spinto fino a 4,5 m lontano da te.",
                   "If the target is Large or smaller it makes a DC {dc} Strength save: on a failure it is pushed up to 15 ft away from you."))
DISARMING = _rider(
    "disarming", ("Attacco Disarmante: +dado al danno, TS Forza o il bersaglio lascia cadere un oggetto",
                  "Disarming Attack: +die to damage, Strength save or the target drops an item"),
    effect=_dc_say("Il bersaglio fa un TS Forza CD {dc}: se fallisce lascia cadere un oggetto impugnato a tua scelta.",
                   "The target makes a DC {dc} Strength save: on a failure it drops one held item of your choice."))
MENACING = _rider(
    "menacing", ("Attacco Minaccioso: +dado al danno, TS Saggezza o il bersaglio è spaventato",
                 "Menacing Attack: +die to damage, Wisdom save or the target is frightened"),
    effect=_dc_say("Il bersaglio fa un TS Saggezza CD {dc}: se fallisce è spaventato da te fino alla fine del tuo prossimo turno.",
                   "The target makes a DC {dc} Wisdom save: on a failure it is frightened of you until the end of your next turn."),
    target_effect=lambda ctx, _i: TargetEffect(condition="frightened", save_ability="wisdom", save_dc=_dc(ctx),
                                               ends_at=_till_my_next_turn()))
TRIP = _rider(
    "trip", ("Attacco Sbilanciante: +dado al danno, TS Forza o il bersaglio (Grande o più piccolo) cade prono",
             "Trip Attack: +die to damage, Strength save or the target (Large or smaller) falls prone"),
    effect=_dc_say("Se il bersaglio è Grande o più piccolo fa un TS Forza CD {dc}: se fallisce cade prono.",
                   "If the target is Large or smaller it makes a DC {dc} Strength save: on a failure it falls prone."),
    target_effect=lambda ctx, _i: TargetEffect(condition="prone", save_ability="strength", save_dc=_dc(ctx)))
DISTRACTING = _rider(
    "distracting", ("Colpo Distraente: +dado al danno, il prossimo attacco di un altro contro il bersaglio ha vantaggio",
                    "Distracting Strike: +die to damage, the next attack by someone else against the target has advantage"),
    effect=_say("Il prossimo tiro per colpire contro il bersaglio da parte di un altro attaccante ha vantaggio, se fatto prima dell'inizio del tuo prossimo turno.",
                "The next attack roll against the target by an attacker other than you has advantage, if made before the start of your next turn."),
    on_confirm=_start_note("distracting", "Colpo Distraente"))
PRECISION = RollOptionSpec(
    key=_key("precision"), phase="after_roll", after="add", rolls=("attack",), group=ONE_MANEUVER, extra_dice=_die_dice,
    cost=Cost(feature_key=SD), available=lambda c: _weapon_in_hand(c) and not _other_maneuver_used(c),
    label={"it": "Attacco Preciso: somma il dado di superiorità al tiro per colpire",
           "en": "Precision Attack: add the superiority die to the attack roll"})
RIPOSTE = RollOptionSpec(
    key=_key("riposte"), phase="before", rolls=("attack",), group=ONE_MANEUVER, slot="reaction", extra_dice=_die_dice,
    cost=Cost(feature_key=SD), available=lambda c: _weapon_in_hand(c) and c.attack_mode in ("melee", "offhand"),
    label={"it": "Replica: una creatura ti ha mancato con un attacco in mischia? Reazione, +dado al danno se colpisci",
           "en": "Riposte: did a creature miss you with a melee attack? Reaction, +die to damage if you hit"})
PARRY = RollOptionSpec(
    key=_key("parry"), phase="damage_in", rolls=("damage_taken",), slot="reaction", extra_dice=_die_dice,
    cost=Cost(feature_key=SD), bonus=lambda c, _i: _dex_mod(c),
    label={"it": "Parata: il danno viene da un attacco in mischia di un'altra creatura? Reazione, riduce il danno di dado + Destrezza",
           "en": "Parry: is the damage from another creature's melee attack? Reaction, reduces the damage by die + Dexterity"})


def _dex_mod(ctx: RuleContext) -> int:
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    return effective_ability_mod(ctx.char, "dexterity")


def _sweeping_effect(ctx: RuleContext) -> dict[str, str]:
    slug = canonical_damage_type(item_meta(ctx.item).get("damage_type")) if ctx.item is not None else None
    kind = {"it": f" ({LABELS_IT[slug]})", "en": f" ({slug})"} if slug else {"it": "", "en": ""}
    return {"it": "Una seconda creatura entro 1,5 m dal bersaglio e alla tua portata subisce il dado, dello stesso tipo dell'arma"
                  f"{kind['it']}, se il totale del tuo tiro per colpire basta a colpirla.",
            "en": "A second creature within 5 ft of the target and within your reach takes the die, of the weapon's damage type"
                  f"{kind['en']}, if your attack roll total would hit it."}


def _evasive_state(_ctx: RuleContext, params: dict) -> StateSpec:
    """Il bonus alla CA è il dado tirato all'uso; finisce quando smetti di muoverti (a mano) o col turno."""
    return StateSpec("evasive_footwork", rounds=1, ends_on=("manual", "new_turn"), data={"ac": int(params.get("rolled") or 0)})


def _evasive_bonus(ctx: RuleContext) -> int:
    state = next((s for s in ctx.char.active_states or [] if s.get("key") == "evasive_footwork"), None)
    return int(((state or {}).get("data") or {}).get("ac") or 0)


def _cha_mod(ctx: RuleContext) -> int:
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    return effective_ability_mod(ctx.char, "charisma")


def _maneuver(maneuver: str, summary: tuple[str, str], action_type: str | None = None, **kw: Any):
    name = next((it, en) for k, it, en in MANEUVERS if k == maneuver)
    return feature(f"maneuver_{maneuver}", CK, ED, 3, f"{name[0]} / {name[1]} (Manovra, Maestro di Battaglia 3, pag. 74)",
                   name, summary, action_type, subclass="battle_master", option_group=MANEUVER_GROUP, option_key=maneuver, **kw)


def _maneuver_rows() -> list:
    return [
        _maneuver("goading", ("Dopo un colpo con arma, +dado al danno; il bersaglio fa un TS Saggezza o ha svantaggio contro chi non sei tu.",
                                  "After a weapon hit, +die to damage; the target makes a Wisdom save or has disadvantage against anyone but you."),
                  roll_options=(GOADING,)),
        _maneuver("lunging", ("In mischia, nel tuo turno: portata +1,5 m per l'attacco e, se colpisce, +dado al danno.",
                                  "In melee on your turn: +5 ft reach for the attack and, if it hits, +die to damage."),
                  roll_options=(LUNGING,)),
        _maneuver("feinting", ("Azione bonus e un dado: vantaggio al prossimo attacco contro una creatura entro 1,5 m, +dado al danno se colpisce.",
                                   "Bonus action and a die: advantage on your next attack against a creature within 5 ft, +die to damage on a hit."),
                  "bonus_action", roll_options=(FEINT_STRIKE,),
                  on_use=OnUse(slot="bonus", spends=SD, state=StateSpec(
                      "feinting_attack", rounds=1, ends_on=("new_turn", "manual")))),
        _maneuver("maneuvering", ("Dopo un colpo con arma, +dado al danno; un alleato usa la reazione per muoversi di metà velocità senza provocare.",
                                      "After a weapon hit, +die to damage; an ally uses their reaction to move half speed without provoking."),
                  roll_options=(MANEUVERING,)),
        _maneuver("sweeping", ("Dopo un colpo in mischia, il dado danneggia una seconda creatura vicina se il tiro per colpire la colpirebbe.",
                                   "After a melee hit, the die damages a second nearby creature if the attack roll would hit it."),
                  roll_options=(SWEEPING,)),
        _maneuver("pushing", ("Dopo un colpo con arma, +dado al danno; TS Forza o il bersaglio Grande o più piccolo è spinto fino a 4,5 m.",
                                  "After a weapon hit, +die to damage; Strength save or a Large or smaller target is pushed up to 15 ft."),
                  roll_options=(PUSHING,)),
        _maneuver("disarming", ("Dopo un colpo con arma, +dado al danno; TS Forza o il bersaglio lascia cadere un oggetto.",
                                    "After a weapon hit, +die to damage; Strength save or the target drops an item."),
                  roll_options=(DISARMING,)),
        _maneuver("menacing", ("Dopo un colpo con arma, +dado al danno; TS Saggezza o il bersaglio è spaventato fino alla fine del tuo prossimo turno.",
                                   "After a weapon hit, +die to damage; Wisdom save or the target is frightened until the end of your next turn."),
                  roll_options=(MENACING,)),
        _maneuver("precision", ("Su un tiro per colpire con arma, somma il dado di superiorità al totale, anche dopo averlo visto.",
                                    "On a weapon attack roll, add the superiority die to the total, even after seeing it."),
                  roll_options=(PRECISION,)),
        _maneuver("trip", ("Dopo un colpo con arma, +dado al danno; TS Forza o il bersaglio Grande o più piccolo cade prono.",
                               "After a weapon hit, +die to damage; Strength save or a Large or smaller target falls prone."),
                  roll_options=(TRIP,)),
        _maneuver("commanders_strike", ("Rinunci a un attacco dell'azione Attacco; azione bonus e un dado: un alleato attacca in reazione con +dado al danno.",
                                            "Give up one attack of the Attack action; bonus action and a die: an ally attacks as a reaction with +die to damage."),
                  "bonus_action",
                  on_use=OnUse(slot="bonus", spends=SD, forgoes_attack=True, rolls=_die, gives=lambda _c, rolled: rolled)),
        _maneuver("distracting", ("Dopo un colpo con arma, +dado al danno; il prossimo attacco di un altro contro il bersaglio ha vantaggio.",
                                      "After a weapon hit, +die to damage; the next attack by someone else against the target has advantage."),
                  roll_options=(DISTRACTING,)),
        _maneuver("rally", ("Azione bonus e un dado: un alleato che vedi o senti riceve PF temporanei pari al dado + Carisma.",
                                "Bonus action and a die: an ally you see or hear gains temporary hit points equal to the die + Charisma."),
                  "bonus_action",
                  on_use=OnUse(slot="bonus", spends=SD, rolls=_die, gives=lambda c, rolled: rolled + _cha_mod(c), temp_hp_ally=True)),
        _maneuver("parry", ("Reazione: un attacco in mischia ti ferisce, il danno scende del dado + Destrezza.",
                                "Reaction: a melee attack hurts you, the damage drops by the die + Dexterity."),
                  "reaction", roll_options=(PARRY,)),
        _maneuver("riposte", ("Reazione: una creatura ti manca in mischia, la attacchi con un'arma da mischia e se colpisci +dado al danno.",
                                  "Reaction: a creature misses you in melee, you attack it with a melee weapon and add the die to damage on a hit."),
                  "reaction", roll_options=(RIPOSTE,)),
        _maneuver("evasive_footwork", ("Mentre ti muovi, un dado si somma alla CA finché non smetti di muoverti.",
                                           "While you move, a die adds to your AC until you stop moving."),
                  "special", modifiers=(Modifier("ac", _evasive_bonus,
                                                 when=lambda c: c.roll == "ac" and has_state(c.char, "evasive_footwork"),
                                                 source=f"feature:{_key('evasive_footwork')}"),),
                  on_use=OnUse(spends=SD, rolls=_die, state=_evasive_state)),
    ]


def _relentless_available(ctx: RuleContext) -> bool:
    row = next((a for a in ctx.char.abilities if a.feature_key == SD), None)
    return row is not None and row.max_uses is not None and (row.uses or 0) == 0


def _relentless_confirmed(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    row = next((a for a in ctx.char.abilities if a.feature_key == SD), None)
    if row is not None and row.max_uses is not None:
        row.uses = min(row.max_uses, (row.uses or 0) + 1)


RELENTLESS = RollOptionSpec(
    key=f"{CK}.relentless", phase="before", rolls=("initiative",), available=_relentless_available,
    on_confirm=_relentless_confirmed,
    label={"it": "Implacabile: recupera un dado di superiorità (non ne hai)", "en": "Relentless: regain a superiority die (you have none)"})


# ---------------------------------------------------------------------------
# Cavaliere Mistico
# ---------------------------------------------------------------------------

def _after_action_spell(ctx: RuleContext, *, cantrip_only: bool) -> bool:
    """Un incantesimo da guerriero lanciato con l'azione in questo turno (segnato dal lancio) e l'attacco non è un incantesimo."""
    turn = ctx.turn or {}
    if ctx.spell is not None or turn.get("action_spell_class") != ctx.class_row.id:
        return False
    return turn.get("action_spell_level") == 0 if cantrip_only else turn.get("action_spell_level") is not None


WAR_MAGIC = RollOptionSpec(
    key=f"{CK}.war_magic", phase="before", rolls=("attack",), slot="bonus", available=lambda c: _after_action_spell(c, cantrip_only=True),
    label={"it": "Magia da Guerra: attacco con arma come azione bonus dopo un trucchetto",
           "en": "War Magic: weapon attack as a bonus action after a cantrip"})
IMPROVED_WAR_MAGIC = RollOptionSpec(
    key=f"{CK}.improved_war_magic", phase="before", rolls=("attack",), slot="bonus",
    available=lambda c: _after_action_spell(c, cantrip_only=False),
    label={"it": "Magia da Guerra Migliorata: attacco con arma come azione bonus dopo un incantesimo",
           "en": "Improved War Magic: weapon attack as a bonus action after a spell"})


def _strike_confirmed(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    # Vale fino alla fine del turno che segue il colpo: salta il «nuovo turno» che lo apre e finisce alla fine di quello.
    begin_state(ctx.char, StateSpec("eldritch_strike", ends_on=("new_turn", "turn_end_counted", "rest_short", "rest_long", "manual"),
                                    data={"skip_new_turns": 1}), f"{CK}.eldritch_strike", "Colpo Mistico")


ELDRITCH_STRIKE = RollOptionSpec(
    key=f"{CK}.eldritch_strike", phase="after_hit", rolls=("attack",), available=_weapon_in_hand, on_confirm=_strike_confirmed,
    label={"it": "Colpo Mistico: il bersaglio ha svantaggio al suo prossimo TS contro un tuo incantesimo",
           "en": "Eldritch Strike: the target has disadvantage on its next save against a spell of yours"},
    effect=_say("Il bersaglio ha svantaggio al prossimo TS contro un tuo incantesimo, fino alla fine del tuo prossimo turno.",
                "The target has disadvantage on its next save against a spell of yours, until the end of your next turn."),
    target_effect=lambda _c, _i: TargetEffect(condition="custom:eldritch_strike", ends_at=_till_my_next_turn()))
ELDRITCH_STRIKE_CAST = RollOptionSpec(
    key=f"{CK}.eldritch_strike_cast", phase="before", rolls=("cast",), cost=Cost(state_key="eldritch_strike"),
    available=lambda c: c.spell is not None and state_on(c, "eldritch_strike") and _save_spell(c.spell),
    label={"it": "Colpo Mistico: il bersaglio dell'incantesimo è la creatura che hai colpito?",
           "en": "Eldritch Strike: is the spell's target the creature you hit?"},
    effect=_say("Il bersaglio ha svantaggio al TS contro questo incantesimo.", "The target has disadvantage on its save against this spell."))


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

FEATURES = (
    feature("hit_points", CK, ED, 1, "Punti Ferita / Hit Points (Guerriero 1, pag. 71)", ("Punti Ferita", "Hit Points"),
            ("Dado vita d10; al 1° livello 10 + Costituzione, poi d10 (o 6) + Costituzione.",
             "Hit die d10; level 1 gives 10 + Constitution, then d10 (or 6) + Constitution."), no_row=True,
            covered_by="api/routers/classes.py create_class_for_character e total_base_hp; test_hit_points_use_the_d10_and_follow_constitution"),
    feature("proficiencies", CK, ED, 1, "Competenze / Proficiencies (Guerriero 1, pag. 71)", ("Competenze", "Proficiencies"),
            ("Tutte le armature e gli scudi, armi semplici e da guerra, TS Forza e Costituzione, 2 abilità.",
             "All armor and shields, simple and martial weapons, Strength and Constitution saves, 2 skills."),
            no_row=True, covered_by="core/rules/proficiencies.py (class_proficiencies) e la scelta ClassSkillChoice; "
                                    "test_class_proficiencies_first_class_and_multiclass"),
    feature("equipment", CK, ED, 1, "Equipaggiamento / Equipment (Guerriero 1, pag. 71)", ("Equipaggiamento", "Equipment"),
            ("Dotazione iniziale: cotta di maglia o cuoio con arco lungo, arma da guerra e scudo o due armi, balestra o due asce, pacco.",
             "Starting gear: chain mail or leather with a longbow, a martial weapon and shield or two weapons, a crossbow or two handaxes, a pack."),
            no_row=True, covered_by="lavori-successivi"),
    feature("fighting_style", CK, ED, 1, "Stile di Combattimento / Fighting Style (Guerriero 1, pag. 72)",
            ("Stile di Combattimento", "Fighting Style"),
            ("Al 1° livello scegli uno stile: Tiro, Difesa, Duellare, Armi Possenti, Due Armi o Protezione. Mai due volte lo stesso.",
             "At 1st level you choose a style: Archery, Defense, Dueling, Great Weapon, Two-Weapon or Protection. Never the same one twice."),
            no_row=True, choices=(_style_choice({1: 1}),),
            covered_by="ChoiceSpec fighting_style di questa riga e le righe dei sei stili; test_the_style_is_a_choice_made_at_level_1"),
    *STYLE_ROWS,
    feature("second_wind", CK, ED, 1, "Recuperare Energie / Second Wind (Guerriero 1, pag. 72)",
            ("Recuperare Energie", "Second Wind"),
            ("Azione bonus: recuperi 1d10 + il tuo livello da guerriero in PF. Un uso, torna con un riposo breve o lungo.",
             "Bonus action: you regain 1d10 + your fighter level in hit points. One use, back after a short or long rest."),
            "bonus_action", uses=Uses(table={1: 1}), restoration="short_rest",
            on_use=OnUse(slot="bonus", rolls="1d10", heal=lambda ctx, rolled: rolled + ctx.class_level)),
    feature("action_surge", CK, ED, 2, "Azione Impetuosa / Action Surge (Guerriero 2, pag. 72)",
            ("Azione Impetuosa", "Action Surge"),
            ("Nel tuo turno compi un'azione in più (non bonus). Un uso, due dal 17° ma uno solo per turno; torna con un riposo breve o lungo.",
             "On your turn you take one extra action (not a bonus action). One use, two from 17th but one per turn; back after a short or long rest."),
            "special", uses=Uses(table={2: 1, 17: 2}), restoration="short_rest",
            on_use=OnUse(grants_action=True, once_per_turn=True, notes=_arcane_charge_notes, toggles=(UseToggle(
                "arcane_charge", {"it": "Carica Arcana: ti teletrasporti fino a 9 m", "en": "Arcane Charge: teleport up to 30 ft"},
                available=_arcane_charge_toggle),))),
    feature("martial_archetype", CK, ED, 3, "Archetipo Marziale / Martial Archetype (Guerriero 3, pag. 72)",
            ("Archetipo Marziale", "Martial Archetype"),
            ("Al 3° livello si sceglie Campione, Maestro di Battaglia o Cavaliere Mistico.",
             "At 3rd level you choose Champion, Battle Master or Eldritch Knight."),
            no_row=True, covered_by="core/rules/subclasses.py (match_subclass) e il campo sottoclasse della classe"),
    feature("ability_score_improvement", CK, ED, 4,
            "Aumento dei Punteggi di Caratteristica / Ability Score Improvement (Guerriero 4, pag. 72)",
            ("Aumento dei Punteggi di Caratteristica", "Ability Score Improvement"),
            ("Ai livelli 4, 6, 8, 12, 14, 16 e 19: +2 a un punteggio o +1 a due, oppure un talento; massimo 20.",
             "At levels 4, 6, 8, 12, 14, 16 and 19: +2 to one score or +1 to two, or a feat; maximum 20."), no_row=True,
            covered_by="core/rules/level_choices.py (scelta asi); test_asi_choice_is_pending_at_each_asi_level"),
    feature("extra_attack", CK, ED, 5, "Attacco Extra / Extra Attack (Guerriero 5, pag. 72)", ("Attacco Extra", "Extra Attack"),
            ("Con l'azione Attacco attacchi due volte; tre dall'11°, quattro dal 20°. Non si somma all'Attacco Extra di altre classi.",
             "You attack twice with the Attack action; three times from 11th, four from 20th. Does not stack with other classes' Extra Attack."),
            attacks_per_action=2),
    feature("extra_attack_11", CK, ED, 11, "Attacco Extra / Extra Attack (Guerriero 5, pag. 72)",
            ("Attacco Extra (2)", "Extra Attack (2)"),
            ("Tre attacchi con l'azione Attacco.", "Three attacks with the Attack action."),
            attacks_per_action=3, no_row=True, covered_by=f"{CK}.extra_attack (stessa voce della mappatura); test_extra_attacks_follow_the_level"),
    feature("extra_attack_20", CK, ED, 20, "Attacco Extra / Extra Attack (Guerriero 5, pag. 72)",
            ("Attacco Extra (3)", "Extra Attack (3)"),
            ("Quattro attacchi con l'azione Attacco.", "Four attacks with the Attack action."),
            attacks_per_action=4, no_row=True, covered_by=f"{CK}.extra_attack (stessa voce della mappatura); test_extra_attacks_follow_the_level"),
    feature("indomitable", CK, ED, 9, "Indomito / Indomitable (Guerriero 9, pag. 72)", ("Indomito", "Indomitable"),
            ("Dopo un TS fallito lo ripeti e vale il nuovo risultato. Un uso, due dal 13°, tre dal 17°; tornano con un riposo lungo.",
             "After a failed save you reroll it and the new result stands. One use, two from 13th, three from 17th; back after a long rest."),
            "special", uses=Uses(table={9: 1, 13: 2, 17: 3}), restoration="long_rest", roll_options=(INDOMITABLE_REROLL,)),

    # Campione
    feature("improved_critical", CK, ED, 3, "Critico Migliorato / Improved Critical (Campione 3, pag. 72)",
            ("Critico Migliorato", "Improved Critical"),
            ("Gli attacchi con arma mettono a segno un critico con 19 o 20 al d20, fino al 15° livello.",
             "Weapon attacks score a critical hit on a 19 or 20 on the d20, until 15th level."),
            subclass="champion", modifiers=(Modifier("crit_min", 19, when=_weapon_attack, source=f"feature:{CK}.improved_critical"),)),
    feature("remarkable_athlete", CK, ED, 7, "Atleta Straordinario / Remarkable Athlete (Campione 7, pag. 72)",
            ("Atleta Straordinario", "Remarkable Athlete"),
            ("Metà competenza (per eccesso) alle prove di Forza, Destrezza e Costituzione senza competenza, iniziativa compresa; salto in lungo +30 cm per punto di Forza.",
             "Half proficiency (rounded up) on Strength, Dexterity and Constitution checks you are not proficient in, initiative included; long jump +1 ft per Strength point."),
            subclass="champion", modifiers=(
                Modifier("skill", _athlete_bonus, when=_athlete_applies, source=f"feature:{CK}.remarkable_athlete"),
                Modifier("initiative", _athlete_bonus, when=_athlete_applies, source=f"feature:{CK}.remarkable_athlete"),)),
    feature("additional_fighting_style", CK, ED, 10, "Stile di Combattimento Aggiuntivo / Additional Fighting Style (Campione 10, pag. 72)",
            ("Stile di Combattimento Aggiuntivo", "Additional Fighting Style"),
            ("Al 10° livello scegli un secondo stile di combattimento, diverso dal primo.",
             "At 10th level you choose a second fighting style, different from the first."),
            subclass="champion", no_row=True, choices=(_style_choice({10: 2}),),
            covered_by="ChoiceSpec fighting_style di questa riga e le righe dei sei stili; test_the_champion_chooses_a_second_style_at_level_10"),
    feature("superior_critical", CK, ED, 15, "Critico Superiore / Superior Critical (Campione 15, pag. 72)",
            ("Critico Superiore", "Superior Critical"),
            ("Gli attacchi con arma mettono a segno un critico con 18, 19 o 20 al d20.",
             "Weapon attacks score a critical hit on an 18, 19 or 20 on the d20."),
            subclass="champion", modifiers=(Modifier("crit_min", 18, when=_weapon_attack, source=f"feature:{CK}.superior_critical"),)),
    feature("survivor", CK, ED, 18, "Sopravvissuto / Survivor (Campione 18, pag. 73)", ("Sopravvissuto", "Survivor"),
            ("All'inizio di ogni tuo turno recuperi 5 + Costituzione PF, se ne hai almeno uno e non più di metà del massimo.",
             "At the start of each of your turns you regain 5 + Constitution hit points, if you have at least 1 and no more than half your maximum."),
            subclass="champion", turn_start_heal=_survivor_heal),

    # Maestro di Battaglia
    feature("superiority_dice", CK, ED, 3, "Superiorità in Combattimento / Combat Superiority (Maestro di Battaglia 3, pag. 73)",
            ("Dadi di Superiorità", "Superiority Dice"),
            ("Dadi per le manovre: 4 (5 al 7°, 6 al 15°), d8 (d10 al 10°, d12 al 18°). Tre manovre, più due ai livelli 7, 10 e 15. CD 8 + competenza + Forza o Destrezza.",
             "Dice for maneuvers: 4 (5 at 7th, 6 at 15th), d8 (d10 at 10th, d12 at 18th). Three maneuvers, plus two at 7th, 10th and 15th. DC 8 + proficiency + Strength or Dexterity."),
            subclass="battle_master", uses=Uses(table={3: 4, 7: 5, 15: 6}), restoration="short_rest",
            choices=(ChoiceSpec(group=MANEUVER_GROUP, levels={3: 3, 7: 5, 10: 7, 15: 9}, replaceable=True,
                                options=lambda _ctx: [k for k, _it, _en in MANEUVERS]),)),
    feature("student_of_war", CK, ED, 3, "Studioso di Guerra / Student of War (Maestro di Battaglia 3, pag. 73)",
            ("Studioso di Guerra", "Student of War"),
            ("Competenza in un tipo di strumenti da artigiano a tua scelta.", "Proficiency with one type of artisan's tools of your choice."),
            subclass="battle_master", no_row=True, covered_by="lavori-successivi"),
    feature("know_your_enemy", CK, ED, 7, "Conosci il Tuo Nemico / Know Your Enemy (Maestro di Battaglia 7, pag. 73)",
            ("Conosci il Tuo Nemico", "Know Your Enemy"),
            ("Dopo 1 minuto fuori dal combattimento a osservare una creatura, il GM ti dice se è pari, superiore o inferiore a te in due tratti.",
             "After 1 minute out of combat studying a creature, the GM tells you whether it is equal, superior or inferior to you in two traits."),
            subclass="battle_master", passive=True),
    feature("improved_combat_superiority", CK, ED, 10,
            "Superiorità in Combattimento Migliorata / Improved Combat Superiority (Maestro di Battaglia 10, pag. 74)",
            ("Superiorità in Combattimento Migliorata", "Improved Combat Superiority"),
            ("I dadi di superiorità diventano d10 al 10° livello e d12 al 18°; le manovre tirano il dado del tuo livello.",
             "Superiority dice become d10 at 10th level and d12 at 18th; maneuvers roll the die of your level."),
            subclass="battle_master", passive=True),
    feature("relentless", CK, ED, 15, "Implacabile / Relentless (Maestro di Battaglia 15, pag. 74)",
            ("Implacabile", "Relentless"),
            ("Tirando l'iniziativa senza dadi di superiorità, ne recuperi uno.",
             "When you roll initiative with no superiority dice left, you regain one."),
            subclass="battle_master", roll_options=(RELENTLESS,)),
    *_maneuver_rows(),

    # Cavaliere Mistico
    feature("eldritch_knight_spellcasting", CK, ED, 3, "Incantesimi / Eldritch Knight Spellcasting (Cavaliere Mistico 3, pag. 75)",
            ("Incantesimi", "Spellcasting"),
            ("Terzo di incantatore con Intelligenza, lista del mago. Trucchetti 2 (3 al 10°); conosciuti da 3 a 13; quasi tutti di abiurazione o invocazione.",
             "Third-caster with Intelligence, wizard list. Cantrips 2 (3 at 10th); known spells 3 to 13; nearly all abjuration or evocation."),
            subclass="eldritch_knight", no_row=True,
            covered_by="core/rules/spellcasting.py (known_limits, slots_for, caster_stats, school_limits); "
                       "test_eldritch_knight_spell_slots_cantrips_and_known_follow_the_table"),
    feature("weapon_bond", CK, ED, 3, "Arma Vincolata / Weapon Bond (Cavaliere Mistico 3, pag. 75)",
            ("Arma Vincolata", "Weapon Bond"),
            ("Rituale di 1 ora vincola fino a due armi: nessun disarmo, e le evochi in mano con un'azione bonus (una per volta).",
             "A 1-hour ritual bonds up to two weapons: they cannot be disarmed, and you summon one at a time to your hand as a bonus action."),
            "bonus_action", subclass="eldritch_knight", on_use=OnUse(panel="weapon_bond")),
    feature("war_magic", CK, ED, 7, "Magia da Guerra / War Magic (Cavaliere Mistico 7, pag. 75)",
            ("Magia da Guerra", "War Magic"),
            ("Dopo aver lanciato un trucchetto con l'azione, un attacco con arma come azione bonus. Fino al 18° livello.",
             "After casting a cantrip with your action, one weapon attack as a bonus action. Until 18th level."),
            subclass="eldritch_knight", roll_options=(WAR_MAGIC,)),
    feature("eldritch_strike", CK, ED, 10, "Colpo Mistico / Eldritch Strike (Cavaliere Mistico 10, pag. 75)",
            ("Colpo Mistico", "Eldritch Strike"),
            ("La creatura che colpisci con un'arma ha svantaggio al prossimo TS contro un tuo incantesimo, fino alla fine del tuo turno seguente.",
             "A creature you hit with a weapon has disadvantage on its next saving throw against a spell of yours, until the end of your next turn."),
            subclass="eldritch_knight", roll_options=(ELDRITCH_STRIKE, ELDRITCH_STRIKE_CAST)),
    feature("arcane_charge", CK, ED, 15, "Carica Arcana / Arcane Charge (Cavaliere Mistico 15, pag. 75)",
            ("Carica Arcana", "Arcane Charge"),
            ("Quando usi Azione Impetuosa ti teletrasporti fino a 9 m in uno spazio libero che vedi, prima o dopo l'azione in più.",
             "When you use Action Surge you teleport up to 30 ft to an unoccupied space you can see, before or after the extra action."),
            subclass="eldritch_knight", passive=True),
    feature("improved_war_magic", CK, ED, 18, "Magia da Guerra Migliorata / Improved War Magic (Cavaliere Mistico 18, pag. 75)",
            ("Magia da Guerra Migliorata", "Improved War Magic"),
            ("Dopo aver lanciato un qualsiasi incantesimo con l'azione, un attacco con arma come azione bonus.",
             "After casting any spell with your action, one weapon attack as a bonus action."),
            subclass="eldritch_knight", roll_options=(IMPROVED_WAR_MAGIC,)),

    feature("multiclassing", CK, ED, 1, "Multiclasse: Guerriero / Multiclassing: Fighter (Regole opzionali, pag. 163)",
            ("Multiclasse: Guerriero", "Multiclassing: Fighter"),
            ("Requisito Forza 13 o Destrezza 13. Da multiclasse: armature leggere e medie, scudi, armi semplici e da guerra.",
             "Requires Strength 13 or Dexterity 13. As a multiclass: light and medium armor, shields, simple and martial weapons."),
            no_row=True, covered_by="core/rules/proficiencies.py (as_multiclass) e webapp/src/data/multiclassPrereqs.ts (D2)"),
)

"""Marchi e punizioni (Sortilegio, Marchio del Cacciatore, le punizioni, Colpo Intrappolante, Raffica di Spine, Freccia Folgorante,
Colpo Accurato): lo stato ``spell:<chiave>`` sta sul lanciatore e dà opzioni ai suoi attacchi con arma.

- Marchi: a ogni attacco l'app chiede se il bersaglio è quello marchiato e aggiunge il danno extra (come il Ranger 2024).
- Punizioni: opzione dopo il colpo. Quelle il cui effetto dura (condizione «finché dura l'incantesimo») restano attive e si segnano
  come scaricate; le altre chiudono l'incantesimo al colpo (``Cost(state_key)`` -> ``_end_spent_spells``).
- Le condizioni vanno sul combattente dell'incontro con ``TargetEffect`` (legate alla concentrazione se l'incantesimo la richiede).
Il tipo di danno extra sta in ``RollOptionSpec.extra_damage_type``: arriva nel blocco dell'esito (``extra_types``).
"""
from __future__ import annotations

import random
from dataclasses import replace
from typing import Callable

from core.rules.spell_effects import SpellChoice, SpellEffect, SpellTarget, SpellVariant
from core.rules.types import Cost, RollOptionSpec, RuleContext, TargetEffect

HOUR, MIN1 = 600, 10  # round (6 secondi)


def _mark_rounds(four_hours_at_2: bool) -> Callable[[int], int]:
    """Durata del marchio: 1 ora; con uno slot di 3°-4° 8 ore, di 5° o più 24 ore (Sortilegio 2024: 4 ore con il 2°)."""
    return lambda slot: HOUR * (24 if slot >= 5 else 8 if slot >= 3 else 4 if slot == 2 and four_hours_at_2 else 1)


RANGER_MARK = "ranger.hunters_mark_damage"  # Marchio del Cacciatore del Ranger 2024: ha già la sua opzione


def txt(it: str, en: str) -> dict[str, str]:
    return {"it": it, "en": en}


def both(variant: SpellVariant) -> dict[str, SpellVariant]:
    return {"2014": variant, "2024": variant}


def _data(ctx: RuleContext) -> dict:
    return ctx.spell_data or {}


def _slot(ctx: RuleContext) -> int:
    return int(_data(ctx).get("slot_level") or 1)


def _dc(ctx: RuleContext) -> int:
    return int(_data(ctx).get("save_dc") or 8 + ctx.char.proficiency_bonus)


def _dice(count: int, sides: int, base_slot: int, per: int = 1, cap: int | None = None) -> Callable[[RuleContext, dict], str]:
    """``count`` dadi al livello base, ``per`` in più per ogni livello di slot oltre."""
    return lambda ctx, _i: f"{min(count + per * max(_slot(ctx) - base_slot, 0), cap or 99)}d{sides}"


def _fmt(ctx: RuleContext, text: dict[str, str]) -> dict[str, str]:
    return {lang: s.format(dc=_dc(ctx), slot=_slot(ctx)) for lang, s in text.items()}


# --- Marchi ---------------------------------------------------------------------------------------------------------------------

def _own_attack(ctx: RuleContext) -> bool:
    """Il marchio è di chi lo lancia: non vale sull'attacco della bestia o di un altro compagno."""
    return ctx.attack_mode not in ("beast", "companion")


def _weapon_attack(ctx: RuleContext) -> bool:
    """Solo l'attacco con arma: il Marchio del Cacciatore 2014 e Colpo Accurato 2024 non valgono con un incantesimo."""
    return _own_attack(ctx) and ctx.spell is None


def _no_ranger_mark(ctx: RuleContext) -> bool:
    """Il Ranger 2024 ha già l'opzione del suo privilegio: non si conta due volte."""
    from core.rules.catalog import active_features  # import locale: il catalogo delle classi usa questi tipi
    return not any(o.key == RANGER_MARK for spec, _row in active_features(ctx.char) for o in spec.roll_options)


def _mark(key: str, label: dict[str, str], effect: dict[str, str], available: Callable[[RuleContext], bool] = _own_attack,
          kind: str | None = None) -> RollOptionSpec:
    return RollOptionSpec(
        key=f"spell:{key}:damage", phase="before", rolls=("attack",), extra_dice=lambda _c, _i: "1d6", extra_damage_type=kind, available=available,
        label=label, effect=lambda _c, _i: effect)


_HEX_OPTION = _mark(
    "hex", txt("Sortilegio: il bersaglio è la creatura maledetta? +1d6 danni necrotici",
               "Hex: is the target the cursed creature? Extra 1d6 necrotic damage"),
    txt("Sortilegio: danni necrotici in più, già nel totale.", "Hex: extra necrotic damage, already in the total."), kind="necrotic")
_HEX = SpellVariant(
    options=(_HEX_OPTION,),
    choices=(SpellChoice("ability", txt("Caratteristica", "Ability"),
                         lambda _ed: ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]),),
    concentration=True, rounds=HOUR, rounds_by_slot=_mark_rounds(False),
    text=txt("Il bersaglio ha svantaggio alle prove della caratteristica scelta: lo applica il GM. A 0 PF sposti il sortilegio con un'azione bonus.",
             "The target has disadvantage on checks with the chosen ability: the GM applies it. At 0 HP you move the curse with a bonus action."))

_MARK_2014 = SpellVariant(
    options=(_mark("hunters_mark", txt("Marchio del Cacciatore: il bersaglio è la creatura marcata? +1d6 danni", "Hunter's Mark: is the target the marked creature? Extra 1d6 damage"),
                   txt("Marchio del Cacciatore: danni in più, già nel totale.", "Hunter's Mark: extra damage, already in the total."), 
                   lambda c: _weapon_attack(c) and _no_ranger_mark(c)),),
    concentration=True, rounds=HOUR, rounds_by_slot=_mark_rounds(False),
    text=txt("Vantaggio alle prove di Saggezza (Percezione e Sopravvivenza) per trovare la creatura marcata. A 0 PF sposti il marchio con un'azione bonus.",
             "Advantage on Wisdom (Perception and Survival) checks to find the marked creature. At 0 HP you move the mark with a bonus action."))
_MARK_2024 = SpellVariant(
    options=(_mark("hunters_mark", txt("Marchio del Cacciatore: il bersaglio è la creatura marcata? +1d6 danni da forza", "Hunter's Mark: is the target the marked creature? Extra 1d6 force damage"),
                   txt("Marchio del Cacciatore: danni da forza in più, già nel totale.", "Hunter's Mark: extra force damage, already in the total."),
                   lambda c: _own_attack(c) and _no_ranger_mark(c), kind="force"),),
    concentration=True, rounds=HOUR, rounds_by_slot=_mark_rounds(False), text=_MARK_2014.text)


# --- Punizioni ------------------------------------------------------------------------------------------------------------------

def _ranged(ctx: RuleContext) -> bool:
    from core.game.item_bonuses import item_meta  # import locale, come negli altri privilegi
    return ctx.attack_mode == "thrown" or (ctx.item is not None and item_meta(ctx.item).get("weapon_type", "melee") == "ranged")


def _hit_ok(ctx: RuleContext, *, ranged: bool, anywhere: bool = False) -> bool:
    """Non ancora scaricata, attacco del lanciatore e del tipo giusto (a distanza o no; ``anywhere``: qualunque attacco con arma)."""
    return not _data(ctx).get("discharged") and _own_attack(ctx) and (anywhere or _ranged(ctx) == ranged)


def _discharge(key: str) -> Callable:
    """La punizione ha colpito ma l'incantesimo dura ancora (condizione fino alla fine): non scatta una seconda volta."""
    def run(_session, ctx: RuleContext, _inputs: dict) -> None:
        ctx.char.active_states = [
            {**s, "data": {**(s.get("data") or {}), "discharged": True}} if s.get("key") == f"spell:{key}" else s
            for s in ctx.char.active_states or []]
    return run


def _target(condition: str | None, ability: str, *, repeat: str | None = None, ends_at: dict | None = None, concentration: bool = False):
    return lambda ctx, _i: TargetEffect(condition=condition, save_ability=ability, save_dc=_dc(ctx), repeat_save=repeat, ends_at=ends_at,
                                        ends_with_concentration=concentration)


def _smite(key: str, it_name: str, en_name: str, kind: str | None, label: dict[str, str], *, dice=None, lingers: bool = False, ranged: bool = False, anywhere: bool = False,
           separate: bool = False, doubles: bool = True, effect: dict[str, str], target=None) -> RollOptionSpec:
    """``anywhere``: qualunque attacco con arma (Marchiante, Esiliante, Colpo Intrappolante), non solo mischia.
    L'etichetta comincia con il nome dell'incantesimo (``it_name``/``en_name``); ``kind``: tipo di danno dei dadi."""
    label = {"it": f"{it_name}: {label['it'].partition(': ')[2]}", "en": f"{en_name}: {label['en'].partition(': ')[2]}"}
    return RollOptionSpec(
        key=f"spell:{key}:hit", phase="after_hit", rolls=("attack",), label=label, extra_dice=dice, extra_damage_type=kind, separate_damage=separate,
        crit_doubles=doubles, available=lambda c: _hit_ok(c, ranged=ranged, anywhere=anywhere),
        cost=None if lingers else Cost(state_key=f"spell:{key}"), on_confirm=_discharge(key) if lingers else None,
        effect=lambda c, _i: _fmt(c, effect), target_effect=target)


def _variant(option: RollOptionSpec, *, concentration: bool, rounds: int = MIN1, text=None, more: tuple[RollOptionSpec, ...] = ()) -> SpellVariant:
    return SpellVariant(options=(option, *more), concentration=concentration, rounds=rounds, needs_dc=True, text=text)


SMITE_GROUP = "paladin.divine_smite_cast"  # lo stesso gruppo della Punizione Divina 2024: una sola punizione per colpo


def _cast_on_hit(variant: SpellVariant, base_slot: int) -> SpellVariant:
    """2024: la punizione è un'azione bonus «subito dopo aver colpito» (mischia o senz'armi): si offre dopo il colpo a segno, con lo slot
    scelto lì (e i dadi che ne seguono), come la Punizione Divina. Non serve lanciarla prima, e un mancato non spreca lo slot.
    Se l'hai già lanciata prima (stato sul lanciatore) vale l'opzione dello stato: non si conta due volte."""
    opt = variant.options[0]
    state = opt.key.removesuffix(":hit")

    def at(ctx: RuleContext, inputs: dict) -> RuleContext:
        return replace(ctx, spell_data={**_data(ctx), "slot_level": int(inputs.get("slot_level") or base_slot)})

    def available(ctx: RuleContext) -> bool:
        return (ctx.spell is None and ctx.attack_mode in ("melee", "offhand") and not (ctx.char.turn_state or {}).get("spell_slot_cast")
                and not any(s.get("key") == state for s in ctx.char.active_states or []))

    def cast(_session, ctx: RuleContext, _inputs: dict) -> None:
        ctx.char.turn_state = {**(ctx.char.turn_state or {}), "spell_slot_cast": True, "leveled_cast": True, "bonus_spell_cast": True}

    return replace(variant, on_hit=(replace(
        opt, requires_input="slot", cost=Cost(spell_slot_min=base_slot), slot="bonus", group=SMITE_GROUP, available=available, on_confirm=cast,
        extra_dice=(lambda c, i: opt.extra_dice(at(c, i), i)) if opt.extra_dice else None, effect=lambda c, i: opt.effect(at(c, i), i),
        starts_concentration=variant.rounds if variant.concentration else None),))


BLIND_AT = {"anchor": "owner", "edge": "end", "count": MIN1}  # 1 minuto sui turni del bersaglio (senza concentrazione)

# Colpo Accecante
_BLINDING_LABEL = txt("Punizione: +3d8 radiosi e il bersaglio è accecato (TS Costituzione)", "Smite: extra 3d8 radiant and the target is blinded (Constitution save)")
_BLINDING_2014 = _variant(_smite(
    "blinding_smite", "Punizione Accecante", "Blinding Smite", "radiant", _BLINDING_LABEL, dice=lambda *_: "3d8", lingers=True,
    effect=txt("Colpo Accecante: +3d8 radiosi; TS Costituzione CD {dc} o accecato finché dura, ripetendo il TS a fine di ogni suo turno (se lo supera l'effetto cade solo su di lui: l'incantesimo resta finché non lo chiudi tu).",
               "Blinding Smite: extra 3d8 radiant; Constitution save DC {dc} or blinded while it lasts, repeating the save at the end of each of its turns (if it passes, only its effect ends: the spell stays until you end it)."),
    target=_target("blinded", "constitution", repeat="end", concentration=True)), concentration=True)
_BLINDING_2024 = _variant(_smite(
    "blinding_smite", "Colpo Accecante", "Blinding Smite", "radiant", txt("Punizione: +3d8 radiosi (+1d8 per slot oltre il 3°), il bersaglio è accecato (TS Costituzione)", "Smite: extra 3d8 radiant (+1d8 per slot above 3rd), the target is blinded (Constitution save)"),
    dice=_dice(3, 8, 3), lingers=True,
    effect=txt("Colpo Accecante: radiosi in più; TS Costituzione CD {dc} o accecato, ripetendo il TS a fine di ogni suo turno (se lo supera l'effetto cade solo su di lui: l'incantesimo resta finché non lo chiudi tu).",
               "Blinding Smite: extra radiant; Constitution save DC {dc} or blinded, repeating the save at the end of each of its turns (if it passes, only its effect ends: the spell stays until you end it)."),
    target=_target("blinded", "constitution", repeat="end", ends_at=BLIND_AT)), concentration=False)

# Punizione Marchiante (2014)
_BRANDING = _variant(_smite(
    "branding_smite", "Punizione Marchiante", "Branding Smite", "radiant", txt("Punizione: +2d6 radiosi (+1d6 per slot oltre il 2°)", "Smite: extra 2d6 radiant (+1d6 per slot above 2nd)"),
    dice=_dice(2, 6, 2), lingers=True, anywhere=True,
    effect=txt("Punizione Marchiante: radiosi in più; il bersaglio diventa visibile, emette luce fioca (1,5 m) e non può diventare invisibile finché dura.",
               "Branding Smite: extra radiant; the target becomes visible, sheds dim light (5 ft) and can't turn invisible while it lasts.")),
    concentration=True)

# Punizione Incandescente / Infuocata
_SEARING_TEXT_2014 = txt("Punizione Incandescente: +fuoco; a inizio di ogni suo turno il bersaglio fa un TS Costituzione CD {dc}: se fallisce subisce 1d6 fuoco, se supera l'incantesimo termina.",
                         "Searing Smite: extra fire; at the start of each of its turns the target makes a Constitution save DC {dc}: on a failure it takes 1d6 fire, on a success the spell ends.")
_SEARING_2014 = _variant(_smite(
    "searing_smite", "Punizione Incandescente", "Searing Smite", "fire", txt("Punizione: +1d6 fuoco (+1d6 per slot oltre il 1°)", "Smite: extra 1d6 fire (+1d6 per slot above 1st)"),
    dice=_dice(1, 6, 1), lingers=True, effect=_SEARING_TEXT_2014), concentration=True)
_SEARING_2024 = _variant(_smite(
    "searing_smite", "Punizione Infuocata", "Searing Smite", "fire", txt("Punizione: +1d6 fuoco (+1d6 per slot oltre il 1°)", "Smite: extra 1d6 fire (+1d6 per slot above 1st)"),
    dice=_dice(1, 6, 1), lingers=True,
    effect=txt("Punizione Infuocata: fuoco in più; a inizio di ogni suo turno il bersaglio subisce {slot}d6 fuoco e fa un TS Costituzione CD {dc}: se supera l'incantesimo termina.",
               "Searing Smite: extra fire; at the start of each of its turns the target takes {slot}d6 fire and makes a Constitution save DC {dc}: on a success the spell ends.")),
    concentration=False)

# Punizione Splendente (2024)
_SHINING = _variant(_smite(
    "shining_smite", "Punizione Splendente", "Shining Smite", "radiant", txt("Punizione: +2d6 radiosi (+1d6 per slot oltre il 2°)", "Smite: extra 2d6 radiant (+1d6 per slot above 2nd)"),
    dice=_dice(2, 6, 2), lingers=True,
    effect=txt("Punizione Splendente: radiosi in più; finché dura il bersaglio emette luce intensa (1,5 m), chi lo attacca ha vantaggio e non beneficia di Invisibile.",
               "Shining Smite: extra radiant; while it lasts the target sheds bright light (5 ft), attackers have advantage and it gets no benefit from Invisible.")),
    concentration=True)

# Punizione Collerica
_WRATHFUL_2014 = _variant(_smite(
    "wrathful_smite", "Punizione Collerica", "Wrathful Smite", "psychic", txt("Punizione: +1d6 psichici, il bersaglio è spaventato (TS Saggezza)", "Smite: extra 1d6 psychic, the target is frightened (Wisdom save)"),
    dice=lambda *_: "1d6", lingers=True,
    effect=txt("Punizione Collerica: +1d6 psichici; TS Saggezza CD {dc} o spaventato finché dura. Con un'azione può fare una prova di Saggezza contro la CD per terminare l'effetto.",
               "Wrathful Smite: extra 1d6 psychic; Wisdom save DC {dc} or frightened while it lasts. As an action it can make a Wisdom check against the DC to end the effect."),
    target=_target("frightened", "wisdom", concentration=True)), concentration=True)
_WRATHFUL_2024 = _variant(_smite(
    "wrathful_smite", "Punizione Collerica", "Wrathful Smite", "necrotic", txt("Punizione: +1d6 necrotici (+1d6 per slot oltre il 1°), il bersaglio è spaventato (TS Saggezza)", "Smite: extra 1d6 necrotic (+1d6 per slot above 1st), the target is frightened (Wisdom save)"),
    dice=_dice(1, 6, 1), lingers=True,
    effect=txt("Punizione Collerica: necrotici in più; TS Saggezza CD {dc} o spaventato, ripetendo il TS a fine di ogni suo turno (se lo supera l'effetto cade solo su di lui: l'incantesimo resta finché non lo chiudi tu).",
               "Wrathful Smite: extra necrotic; Wisdom save DC {dc} or frightened, repeating the save at the end of each of its turns (if it passes, only its effect ends: the spell stays until you end it)."),
    target=_target("frightened", "wisdom", repeat="end", concentration=True)), concentration=True)

# Punizione Tonante
_THUNDER_2014 = _variant(_smite(
    "thunderous_smite", "Punizione Tonante", "Thunderous Smite", "thunder", txt("Punizione: +2d6 tuono, il bersaglio è spinto e prono (TS Forza)", "Smite: extra 2d6 thunder, the target is pushed and prone (Strength save)"),
    dice=lambda *_: "2d6",
    effect=txt("Punizione Tonante: +2d6 tuono (si sente a 90 m); TS Forza CD {dc} o spinto di 3 m e prono.",
               "Thunderous Smite: extra 2d6 thunder (audible at 300 ft); Strength save DC {dc} or pushed 10 ft and knocked prone."),
    target=_target("prone", "strength")), concentration=True)
_THUNDER_2024 = _variant(_smite(
    "thunderous_smite", "Punizione Tonante", "Thunderous Smite", "thunder", txt("Punizione: +2d6 tuono (+1d6 per slot oltre il 1°), il bersaglio è spinto e prono (TS Forza)", "Smite: extra 2d6 thunder (+1d6 per slot above 1st), the target is pushed and prone (Strength save)"),
    dice=_dice(2, 6, 1),
    effect=txt("Punizione Tonante: tuono in più (si sente a 90 m); se è una creatura, TS Forza CD {dc} o spinta di 3 m e prona.",
               "Thunderous Smite: extra thunder (audible at 300 ft); if it is a creature, Strength save DC {dc} or pushed 10 ft and prone."),
    target=_target("prone", "strength")), concentration=False, rounds=1)

# Punizione Demoralizzante / Sconvolgente
_STAGGER_2014 = _variant(_smite(
    "staggering_smite", "Punizione Demoralizzante", "Staggering Smite", "psychic", txt("Punizione: +4d6 psichici, il bersaglio è frastornato (TS Saggezza)", "Smite: extra 4d6 psychic, the target is staggered (Wisdom save)"),
    dice=lambda *_: "4d6",
    effect=txt("Punizione Demoralizzante: +4d6 psichici; TS Saggezza CD {dc}: se fallisce svantaggio ai tiri per colpire e alle prove e niente reazioni fino alla fine del suo turno successivo (lo applica il GM).",
               "Staggering Smite: extra 4d6 psychic; Wisdom save DC {dc}: on a failure it has disadvantage on attack rolls and ability checks and can't take reactions until the end of its next turn (the GM applies it).")),
    concentration=True)
_STAGGER_2024 = _variant(_smite(
    "staggering_smite", "Punizione Sconvolgente", "Staggering Smite", "psychic", txt("Punizione: +4d6 psichici (+1d6 per slot oltre il 4°), il bersaglio è stordito (TS Saggezza)", "Smite: extra 4d6 psychic (+1d6 per slot above 4th), the target is stunned (Wisdom save)"),
    dice=_dice(4, 6, 4),
    effect=txt("Punizione Sconvolgente: psichici in più; TS Saggezza CD {dc} o stordito fino alla fine del tuo turno successivo.",
               "Staggering Smite: extra psychic; Wisdom save DC {dc} or stunned until the end of your next turn."),
    target=_target("stunned", "wisdom", ends_at={"anchor": "source", "edge": "end", "count": 1})), concentration=False, rounds=1)

# Punizione Esiliante / Colpo dell'Esilio
_BANISH_2014 = _variant(_smite(
    "banishing_smite", "Punizione Esiliante", "Banishing Smite", "force", txt("Punizione: +5d10 forza, esilio sotto i 50 PF", "Smite: extra 5d10 force, banishment at 50 HP or fewer"),
    dice=lambda *_: "5d10", lingers=True, anywhere=True,
    effect=txt("Punizione Esiliante: +5d10 da forza; se il bersaglio ha 50 PF o meno è esiliato fino alla fine dell'incantesimo (lo applica il GM).",
               "Banishing Smite: extra 5d10 force; if the target has 50 HP or fewer it is banished until the spell ends (the GM applies it).")),
    concentration=True)
_BANISH_2024 = _variant(_smite(
    "banishing_smite", "Colpo dell'Esilio", "Banishing Smite", "force", txt("Punizione: +5d10 forza, esilio sotto i 50 PF", "Smite: extra 5d10 force, banishment at 50 HP or fewer"),
    dice=lambda *_: "5d10", lingers=True, anywhere=True,
    effect=txt("Colpo dell'Esilio: +5d10 da forza; se il bersaglio ha 50 PF o meno, TS Carisma CD {dc} o è trasportato in un semipiano innocuo, incapacitato, per la durata (lo applica il GM).",
               "Banishing Smite: extra 5d10 force; if the target has 50 HP or fewer, Charisma save DC {dc} or it is sent to a harmless demiplane, incapacitated, for the duration (the GM applies it).")),
    concentration=True)

# Colpo Intrappolante
_ENSNARE_TEXT = txt("Colpo Intrappolante: TS Forza CD {dc} (vantaggio se Grande o più) o trattenuto da rampicanti; a inizio di ogni suo turno subisce {slot}d6 perforanti. Con un'azione si libera con una prova di Forza contro la CD.",
                    "Ensnaring Strike: Strength save DC {dc} (advantage if Large or larger) or restrained by vines; at the start of each of its turns it takes {slot}d6 piercing. As an action it frees itself with a Strength check against the DC.")
_ENSNARE = _variant(_smite(
    "ensnaring_strike", "Colpo Intrappolante", "Ensnaring Strike", None, txt("Punizione: il bersaglio è trattenuto (TS Forza)", "Strike: the target is restrained (Strength save)"),
    lingers=True, anywhere=True, effect=_ENSNARE_TEXT, target=_target("restrained", "strength", concentration=True)), concentration=True)

# Raffica di Spine / Grandine di Spine (danni ad area a parte)
_HAIL_TEXT = txt("Raffica di Spine: il bersaglio e le creature entro 1,5 m fanno un TS Destrezza CD {dc}: perforanti, la metà se superato (danni a parte, non nel totale).",
                 "Hail of Thorns: the target and creatures within 5 ft make a Dexterity save DC {dc}: piercing, half on a success (separate damage, not in the total).")
_HAIL = lambda conc: _variant(_smite(  # noqa: E731
    "hail_of_thorns", "Raffica di Spine" if conc else "Grandine di Spine", "Hail of Thorns", "piercing", txt("Punizione a distanza: 1d10 perforanti ad area (+1d10 per slot oltre il 1°)", "Ranged strike: 1d10 piercing in an area (+1d10 per slot above 1st)"),
    dice=_dice(1, 10, 1, cap=6 if conc else None), ranged=True, separate=True, doubles=False, effect=_HAIL_TEXT), concentration=conc, rounds=MIN1 if conc else 1)

# Freccia Folgorante / Fulminea (4d8 al posto dei danni dell'arma, area a parte)
def _lightning_miss(conc: bool) -> RollOptionSpec:
    """Mancato: il bersaglio subisce comunque la metà dei 4d8 (+1d8 per slot oltre il 3°); la tira il server e chiude l'incantesimo."""
    def half(ctx: RuleContext) -> int:
        return sum(random.randint(1, 8) for _ in range(4 + max(_slot(ctx) - 3, 0))) // 2
    return RollOptionSpec(
        key="spell:lightning_arrow:miss", phase="after_roll", after="miss", rolls=("attack",), miss_damage=half,
        cost=Cost(state_key="spell:lightning_arrow"), available=lambda c: _hit_ok(c, ranged=True),
        label=txt(("Freccia Folgorante" if conc else "Freccia Fulminea") + ": hai mancato? Il bersaglio subisce la metà dei danni da fulmine",
                  "Lightning Arrow: did you miss? The target takes half the lightning damage"),
        effect=lambda _c, _i: txt("Freccia Folgorante: mancato, metà dei danni da fulmine già nel totale; l'area (TS Destrezza) resta da applicare.",
                                  "Lightning Arrow: a miss, half the lightning damage already in the total; the area (Dexterity save) is still to apply."))


_LIGHTNING = lambda conc: _variant(_smite(  # noqa: E731
    "lightning_arrow", "Freccia Folgorante" if conc else "Freccia Fulminea", "Lightning Arrow", "lightning", txt("Attacco a distanza: 4d8 fulmine al posto dei danni dell'arma (+1d8 per slot oltre il 3°)", "Ranged attack: 4d8 lightning instead of the weapon damage (+1d8 per slot above 3rd)"),
    dice=_dice(4, 8, 3), ranged=True, separate=True,
    effect=txt("Freccia Folgorante: i danni da fulmine sostituiscono quelli dell'arma (togli i danni normali dal totale). Le creature entro 3 m dal bersaglio fanno un TS Destrezza CD {dc}: 2d8 fulmine (+1d8 per slot oltre il 3°), la metà se superato.",
               "Lightning Arrow: the lightning damage replaces the weapon's (remove the normal damage from the total). Creatures within 10 ft of the target make a Dexterity save DC {dc}: 2d8 lightning (+1d8 per slot above 3rd), half on a success.")),
    concentration=conc, rounds=MIN1 if conc else 1, more=(_lightning_miss(conc),))


# Colpo Accurato
_TRUE_2014 = SpellVariant(
    options=(RollOptionSpec(
        key="spell:true_strike:advantage", phase="before", rolls=("attack",), mode="advantage", cost=Cost(state_key="spell:true_strike"),
        label=txt("Colpo Accurato: il bersaglio è la creatura scelta? Vantaggio al tiro per colpire", "True Strike: is the target the chosen creature? Advantage on the attack roll")),),
    concentration=True, rounds=2)  # lanciato nel turno prima: sopravvive al «Nuovo turno» che lo apre


def _true_strike_dice(ctx: RuleContext, _inputs: dict) -> str:
    level = ctx.char.total_level
    return f"{1 + (level >= 11) + (level >= 17) if level >= 5 else 0}d6"


_TRUE_2024 = SpellVariant(
    options=(RollOptionSpec(
        key="spell:true_strike:damage", phase="before", rolls=("attack",), extra_dice=_true_strike_dice, extra_damage_type="radiant",
        available=_weapon_attack, cost=Cost(state_key="spell:true_strike"),
        label=txt("Colpo Accurato: danni radiosi extra (1d6 dal 5° livello, 2d6 all'11°, 3d6 al 17°)", "True Strike: extra radiant damage (1d6 from level 5, 2d6 at 11, 3d6 at 17)"),
        effect=lambda _c, _i: txt("Colpo Accurato: il colpo usa la caratteristica da incantatore per colpire e per il danno (applicalo a mano); radiosi in più già nel totale.",
                                  "True Strike: the attack uses your spellcasting ability for the attack and damage (apply it by hand); extra radiant already in the total.")),),
    rounds=1)


def _spell(key: str, srd: str, names: tuple[str, ...], variants: dict[str, SpellVariant]) -> SpellEffect:
    return SpellEffect(key, (srd,), names, SpellTarget("self"), variants)


SPELLS: tuple[SpellEffect, ...] = (
    _spell("hex", "hex", ("Sortilegio", "Malocchio", "Hex"), {"2014": _HEX, "2024": replace(_HEX, rounds_by_slot=_mark_rounds(True))}),
    _spell("hunters_mark", "hunters-mark", ("Marchio del Cacciatore", "Hunter's Mark"), {"2014": _MARK_2014, "2024": _MARK_2024}),
    _spell("blinding_smite", "blinding-smite", ("Punizione Accecante", "Colpo Accecante", "Blinding Smite"), {"2014": _BLINDING_2014, "2024": _cast_on_hit(_BLINDING_2024, 3)}),
    _spell("branding_smite", "branding-smite", ("Punizione Marchiante", "Branding Smite"), {"2014": _BRANDING}),
    _spell("searing_smite", "searing-smite", ("Punizione Incandescente", "Punizione Infuocata", "Searing Smite"), {"2014": _SEARING_2014, "2024": _cast_on_hit(_SEARING_2024, 1)}),
    _spell("shining_smite", "shining-smite", ("Punizione Splendente", "Shining Smite"), {"2024": _cast_on_hit(_SHINING, 2)}),
    _spell("wrathful_smite", "wrathful-smite", ("Punizione Collerica", "Wrathful Smite"), {"2014": _WRATHFUL_2014, "2024": _cast_on_hit(_WRATHFUL_2024, 1)}),
    _spell("thunderous_smite", "thunderous-smite", ("Punizione Tonante", "Thunderous Smite"), {"2014": _THUNDER_2014, "2024": _cast_on_hit(_THUNDER_2024, 1)}),
    _spell("staggering_smite", "staggering-smite", ("Punizione Demoralizzante", "Punizione Sconvolgente", "Staggering Smite"), {"2014": _STAGGER_2014, "2024": _cast_on_hit(_STAGGER_2024, 4)}),
    _spell("banishing_smite", "banishing-smite", ("Punizione Esiliante", "Colpo dell'Esilio", "Banishing Smite"), {"2014": _BANISH_2014, "2024": _cast_on_hit(_BANISH_2024, 5)}),
    _spell("ensnaring_strike", "ensnaring-strike", ("Colpo Intrappolante", "Ensnaring Strike"), both(_ENSNARE)),
    _spell("hail_of_thorns", "hail-of-thorns", ("Raffica di Spine", "Grandine di Spine", "Hail of Thorns"), {"2014": _HAIL(True), "2024": _HAIL(False)}),
    _spell("lightning_arrow", "lightning-arrow", ("Freccia Folgorante", "Freccia Fulminea", "Lightning Arrow"), {"2014": _LIGHTNING(True), "2024": _LIGHTNING(False)}),
    _spell("true_strike", "true-strike", ("Colpo Accurato", "True Strike"), {"2014": _TRUE_2014, "2024": _TRUE_2024}),
)

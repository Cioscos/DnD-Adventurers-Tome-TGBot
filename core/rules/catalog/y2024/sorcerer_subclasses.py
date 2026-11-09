"""Sottoclassi dello Stregone 2024 (parte B): Stregoneria Aberrante, Meccanica, Draconica e Magia Selvaggia.

Valori dalla scheda ``docs/superpowers/rules/2024/classes/sorcerer.md``; i testi sono nostri, mai quelli del manuale.
Non importa ``sorcerer.py`` (che importa questo modulo in fondo): usa solo le definizioni del 2014 (``SP``, ``_cha``).
Gli incantesimi sempre preparati sono ``granted_spells`` (tiers 3/5/7/9, come i domini del Chierico). Stregoneria Psionica è il
lancio coi punti (``KiSpell`` sulla riserva dei punti stregoneria). Gli impulsi di Magia Selvaggia: ``sorcerer_wild_magic.py`` e
``api/services/wild_magic.py``. Il «ripristino» dei privilegi a un uso (Ali di Drago...) è il solito interruttore ``restore``.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from core.data.damage_types import canonical_damage_type
from core.rules.catalog._common import feature, state_on
from core.rules.catalog.y2014.sorcerer import BEND_LUCK_USE, SP, TIDES, _cha, _regeneration
from core.rules.states import get_states
from core.rules.types import (
    ChoiceSpec, Cost, KiSpell, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, UnarmoredAc, UseChoice, Uses, UseToggle,
)

ED, CK = "2024", "sorcerer"
P = f"{CK}."
D20_TESTS = ("attack", "skill", "ability", "save", "death_save", "initiative")  # D20 Test: prove, tiri per colpire, TS
NO_CONCENTRATION_KEY = f"{P}dragon_companion_no_concentration"  # lo legge il router degli incantesimi


def _both(it: str, en: str) -> dict[str, str]:
    return {"it": it, "en": en}


def _sub(label: str, subclass: str):
    """Fabbrica delle righe di una sottoclasse: il titolo è quello della scheda."""
    def make(key: str, level: int, it: str, en: str, page: int, summary: tuple[str, str], action_type: str | None = None, **kw: Any):
        return feature(key, CK, ED, level, f"{it} / {en} ({label} {level}, pag. {page})", (it, en), summary, action_type, subclass=subclass, **kw)
    return make


def _data(ctx: RuleContext, key: str) -> dict | None:
    """I dati dello stato ``key`` se è attivo, altrimenti ``None``."""
    return next((s.get("data") or {} for s in get_states(ctx.char) if s["key"] == key), None)


def _spells(sub: str, label: str, key: str, it: str, en: str, page: int, tiers: tuple[tuple[str, ...], ...]) -> list:
    """Incantesimi sempre preparati ai livelli 3, 5, 7 e 9: la riga del 3° è quella della scheda, le altre soglie la ripetono."""
    make = _sub(label, sub)
    title = f"{it} / {en} ({label} 3, pag. {page})"
    out = [make(key, 3, it, en, page, ("Incantesimi sempre preparati ai livelli 3, 5, 7 e 9; non contano nel limite dei preparati.",
                                      "Spells always prepared at levels 3, 5, 7 and 9; they do not count against your prepared limit."),
                granted_spells=tiers[0])]
    for lv, spells in zip((5, 7, 9), tiers[1:]):
        out.append(feature(f"{key}_{lv}", CK, ED, lv, title, (it, en), (f"Incantesimi sempre preparati del {lv}° livello.", f"Always-prepared spells gained at level {lv}."),
                           subclass=sub, granted_spells=spells, no_row=True,
                           covered_by=f"{P}{key} (stessa voce della mappatura) e test_subclass_spells_are_always_prepared_from_their_level"))
    return out


def _uses_of(ctx: RuleContext, key: str) -> int:
    row = next((a for a in ctx.char.abilities if a.feature_key == key), None)
    return (row.uses or 0) if row is not None else 0


def _restorable(key: str, points: int, **kw: Any) -> OnUse:
    """Un uso per riposo lungo, ripristinabile con ``points`` punti stregoneria (nessuna azione): senza usi l'interruttore
    ``restore`` spende i punti al posto dell'uso; l'azione dell'uso si paga lo stesso."""
    return OnUse(
        alt_spends=SP, cost_by=lambda _c, p: points if p.get("restore") else 1,
        check=lambda c, p: (409, "uses_left") if p.get("restore") and _uses_of(c, key) > 0 else None,
        toggles=(UseToggle("restore", _both(f"Senza usi: ripristina spendendo {points} punti stregoneria",
                                            f"No uses left: restore it for {points} sorcery points")),), **kw)


# ---------------------------------------------------------------------------
# Stregoneria Aberrante
# ---------------------------------------------------------------------------

ABERRANT = "Stregoneria Aberrante"
PSIONIC_SPELLS = (("arms-of-hadar", "calm-emotions", "detect-thoughts", "dissonant-whispers", "mind-sliver"), ("hunger-of-hadar", "sending"),
                  ("evards-black-tentacles", "summon-aberration"), ("rarys-telepathic-bond", "telekinesis"))
PSIONIC_LEVELS = {"arms-of-hadar": 1, "dissonant-whispers": 1, "calm-emotions": 2, "detect-thoughts": 2, "hunger-of-hadar": 3, "sending": 3,
                  "evards-black-tentacles": 4, "summon-aberration": 4, "rarys-telepathic-bond": 5, "telekinesis": 5}
PSYCHIC_SAVE = RollOptionSpec(
    key=f"{P}psychic_defenses", phase="before", rolls=("save",), mode="advantage",
    label=_both("Difese Psichiche: il TS è per evitare o terminare Affascinato o Spaventato? Vantaggio",
                "Psychic Defenses: is the save to avoid or end Charmed or Frightened? Advantage"))
BENEFITS = {"swim": ("Adattamento Acquatico", "Aquatic Adaptation"), "fly": ("Volo Luminescente", "Glistening Flight"),
            "see_invisible": ("Vedere l'Invisibile", "See the Invisible"), "worm": ("Movimento Vermiforme", "Wormlike Movement")}


def _benefits(ctx: RuleContext, params: dict) -> list[str]:
    return [k for k in BENEFITS if params.get(k)]


def _has_benefit(key: str):
    return lambda ctx: key in ((_data(ctx, "revelation_in_flesh") or {}).get("benefits") or [])


REVELATION_USE = OnUse(
    slot="bonus", spends=SP, cost_by=lambda c, p: max(1, len(_benefits(c, p))),
    check=lambda c, p: None if _benefits(c, p) else (422, "no_benefit"),
    state=lambda c, p: StateSpec("revelation_in_flesh", rounds=100, ends_on=("manual",), data={"benefits": _benefits(c, p)}),
    toggles=tuple(UseToggle(k, _both(f"{it} (1 punto)", f"{en} (1 point)")) for k, (it, en) in BENEFITS.items()))
TELEPATHIC_USE = OnUse(
    slot="bonus", state=lambda c, _p: StateSpec("telepathic_speech", rounds=c.class_level * 10, ends_on=("manual",)),
    message=lambda c, _p: _both(f"Legame telepatico con una creatura visibile entro 9 m per {c.class_level} minuti; distanza: {max(1, _cha(c))} miglia.",
                                f"Telepathic link with a creature you see within 30 ft for {c.class_level} minutes; range: {max(1, _cha(c))} miles."))
IMPLOSION_USE = _restorable(f"{P}warping_implosion", 5, slot="action", rolls="3d10")
aberrant = _sub(ABERRANT, "aberrant")

# ---------------------------------------------------------------------------
# Stregoneria Meccanica
# ---------------------------------------------------------------------------

CLOCKWORK = "Stregoneria Meccanica"
CLOCK_SPELLS = (("aid", "alarm", "lesser-restoration", "protection-from-evil-and-good"), ("dispel-magic", "protection-from-energy"),
                ("freedom-of-movement", "summon-construct"), ("greater-restoration", "wall-of-force"))
MANIFESTATIONS = {"gears": ("Ingranaggi spettrali dietro di te", "Spectral gears behind you"), "hands": ("Lancette negli occhi", "Clock hands in your eyes"),
                  "brass": ("Pelle dal riflesso ottonato", "Brassy skin"), "equations": ("Equazioni sul corpo", "Equations on your body"),
                  "focus": ("Il focus diventa un meccanismo", "Your focus becomes a mechanism"), "ticking": ("Un ticchettio udibile", "An audible ticking")}


def _manifestation_label(key: str) -> dict:
    it, en = MANIFESTATIONS[key]
    return {"name": _both(it, en), "summary": _both("Solo estetica, mentre lanci incantesimi da stregone.", "Cosmetic only, while you cast sorcerer spells.")}


def _bastion_left(ctx: RuleContext) -> int:
    return int((_data(ctx, "bastion_of_law") or {}).get("dice") or 0)


def _spend_bastion(n: int):
    def run(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
        left = _bastion_left(ctx) - n
        states = [s for s in get_states(ctx.char) if s["key"] != "bastion_of_law"]
        if left > 0:
            old = next(s for s in get_states(ctx.char) if s["key"] == "bastion_of_law")
            states.append({**old, "data": {**(old.get("data") or {}), "dice": left}})
        ctx.char.active_states = states
    return run


BASTION_USE = OnUse(
    slot="action", spends=SP, cost_by=lambda _c, p: int(p.get("points") or 1),
    state=lambda _c, p: StateSpec("bastion_of_law", ends_on=("rest_long", "manual"), data={"dice": int(p.get("points") or 1)}),
    choices=(UseChoice("points", _both("Punti stregoneria (un d8 ciascuno)", "Sorcery points (one d8 each)"), lambda _c: [str(n) for n in range(1, 6)],
                       lambda k: _both(f"{k} punti, {k}d8", f"{k} points, {k}d8")),))
BASTION_DAMAGE = tuple(RollOptionSpec(
    key=f"{P}bastion_of_law_{n}", phase="damage_in", rolls=("damage_taken",), group=f"{P}bastion_of_law", extra_dice=lambda _c, _i, n=n: f"{n}d8",
    available=lambda c, n=n: _bastion_left(c) >= n, on_confirm=_spend_bastion(n),
    label=_both(f"Bastione della Legge: spendi {n}d8 per ridurre il danno", f"Bastion of Law: spend {n}d8 to reduce the damage")) for n in range(1, 6))
TRANCE_USE = _restorable(f"{P}trance_of_order", 5, slot="bonus", state=StateSpec("trance_of_order", rounds=10, ends_on=("manual",)))
CAVALCADE_USE = _restorable(
    f"{P}clockwork_cavalcade", 7, slot="action",
    message=lambda _c, _p: _both("Cubo di 9 m: cura fino a 100 PF divisi, ripara gli oggetti, termina incantesimi di livello 6 o inferiore.",
                                 "30 ft cube: heal up to 100 hit points split, repair objects, end spells of level 6 or lower."))
clockwork = _sub(CLOCKWORK, "clockwork")

# ---------------------------------------------------------------------------
# Stregoneria Draconica
# ---------------------------------------------------------------------------

DRACONIC = "Stregoneria Draconica"
DRACONIC_SPELLS = (("alter-self", "chromatic-orb", "command", "dragons-breath"), ("fear", "fly"), ("arcane-eye", "charm-monster"),
                   ("legend-lore", "summon-dragon"))
AFFINITY_GROUP = "elemental_affinity"
AFFINITY_TYPES = {"acid": ("acido", "acid"), "cold": ("freddo", "cold"), "fire": ("fuoco", "fire"), "lightning": ("fulmine", "lightning"),
                  "poison": ("veleno", "poison")}


def _affinity_type(ctx: RuleContext) -> str | None:
    return ((getattr(ctx.class_row, "options", None) or {}).get(AFFINITY_GROUP) or [None])[0]


def _affinity_label(key: str) -> dict:
    it, en = AFFINITY_TYPES[key]
    return {"name": _both(it.capitalize(), en.capitalize()), "summary": _both(f"Resistenza al danno da {it} e + Carisma ai suoi incantesimi.",
                                                                              f"Resistance to {en} damage and + Charisma on its spells.")}


AFFINITY_BONUS = RollOptionSpec(
    key=f"{P}elemental_affinity", phase="before", rolls=("spell_damage",), bonus=lambda c, _i: _cha(c),
    available=lambda c: c.spell is not None and _affinity_type(c) is not None and canonical_damage_type(c.spell.damage_type) == _affinity_type(c),
    label=_both("Affinità Elementale: aggiungi il Carisma a un tiro dei danni del tipo scelto", "Elemental Affinity: add your Charisma modifier to one damage roll of your chosen type"))
RESTORE_OWN_ROLL = RollOptionSpec(
    key=f"{P}restore_balance_own_roll", phase="before", rolls=D20_TESTS, cancels=("*",), slot="reaction", cost=Cost(feature_key=f"{P}restore_balance"),
    label=_both("Ripristinare l'Equilibrio: tira questo d20 senza vantaggio né svantaggio (reazione)",
                "Restore Balance: roll this d20 without advantage or disadvantage (reaction)"))
NO_CONCENTRATION = RollOptionSpec(
    key=NO_CONCENTRATION_KEY, phase="before", rolls=("cast",),
    available=lambda c: c.spell is not None and c.spell.srd_index == "summon-dragon",
    label=_both("Compagno Draconico: senza concentrazione, per 1 minuto", "Dragon Companion: no concentration, for 1 minute"),
    effect=lambda _c, _i: _both("L'incantesimo non richiede concentrazione e dura 1 minuto; senza componente materiale.",
                                "The spell needs no concentration and lasts 1 minute; no material component."))
WINGS_USE = _restorable(f"{P}dragon_wings", 3, slot="bonus", state=StateSpec("dragon_wings", rounds=600, ends_on=("manual",)))
draconic = _sub(DRACONIC, "draconic")

# ---------------------------------------------------------------------------
# Magia Selvaggia
# ---------------------------------------------------------------------------

WILD = "Magia Selvaggia"
TIDES_ADVANTAGE = RollOptionSpec(
    key=f"{P}tides_of_chaos_advantage", phase="before", rolls=D20_TESTS, mode="advantage", cost=Cost(feature_key=TIDES),
    label=_both("Maree del Caos: tira questo d20 con vantaggio", "Tides of Chaos: make this D20 Test with advantage"))
wild = _sub(WILD, "wild_magic")
SURGE_MODIFIERS = (
    Modifier("ac", 2, when=lambda c: state_on(c, "wild_shield"), source=f"feature:{P}wild_magic_surge"),
    Modifier("resistance:all", 1, when=lambda c: state_on(c, "wild_resistance"), source=f"feature:{P}wild_magic_surge"),
    Modifier("vulnerability:all", 1, when=lambda c: state_on(c, "wild_vulnerable_all"), source=f"feature:{P}wild_magic_surge"),
    Modifier("vulnerability:piercing", 1, when=lambda c: state_on(c, "wild_vulnerable_piercing"), source=f"feature:{P}wild_magic_surge"))

# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

SUBCLASS_ROWS: tuple = (
    # Stregoneria Aberrante
    *_spells("aberrant", ABERRANT, "psionic_spells", "Incantesimi Psionici", "Psionic Spells", 145, PSIONIC_SPELLS),
    aberrant("telepathic_speech", 3, "Parlata Telepatica", "Telepathic Speech", 145,
             ("Azione bonus: legame telepatico con una creatura visibile entro 9 m per tanti minuti quanti i livelli; distanza in miglia pari a Carisma.",
              "Bonus action: telepathic link with a creature you see within 30 ft for minutes equal to your level; range in miles equals Charisma."),
             "bonus_action", on_use=TELEPATHIC_USE),
    aberrant("psionic_sorcery", 6, "Stregoneria Psionica", "Psionic Sorcery", 146,
             ("Lanci un incantesimo psionico di 1° livello o più spendendo punti stregoneria pari al suo livello al posto dello slot, senza componenti.",
              "Cast a level 1+ psionic spell by spending sorcery points equal to its level instead of a slot, with no components."),
             passive=True, ki_spells=tuple(KiSpell(k, v, pool=SP) for k, v in PSIONIC_LEVELS.items())),
    aberrant("psychic_defenses", 6, "Difese Psichiche", "Psychic Defenses", 146,
             ("Resistenza ai danni psichici; vantaggio ai TS per evitare o terminare Affascinato e Spaventato.",
              "Resistance to psychic damage; advantage on saves to avoid or end Charmed and Frightened."),
             roll_options=(PSYCHIC_SAVE,), modifiers=(Modifier("resistance:psychic", 1, source=f"feature:{P}psychic_defenses"),)),
    aberrant("revelation_in_flesh", 14, "Rivelazione nella Carne", "Revelation in Flesh", 146,
             ("Azione bonus, 10 minuti: per ogni punto stregoneria speso (minimo 1) un beneficio fra nuoto, volo, vedere l'invisibile, movimento vermiforme.",
              "Bonus action, 10 minutes: for each sorcery point spent (minimum 1) one benefit among swim, flight, see invisible, wormlike movement."),
             "bonus_action", on_use=REVELATION_USE),
    aberrant("aquatic_adaptation", 14, *BENEFITS["swim"], 146,
             ("Beneficio di Rivelazione nella Carne: velocità di nuoto doppia della Velocità e respiro sott'acqua.",
              "Revelation in Flesh benefit: swim speed double your Speed and breathing underwater."),
             modifiers=(Modifier("swim_speed", 1, when=_has_benefit("swim"), source=f"feature:{P}aquatic_adaptation"),), passive=True),
    aberrant("glistening_flight", 14, *BENEFITS["fly"], 146,
             ("Beneficio di Rivelazione nella Carne: velocità di volo pari alla Velocità, puoi librarti.",
              "Revelation in Flesh benefit: flying speed equal to your Speed, and you can hover."),
             modifiers=(Modifier("fly_speed", 1, when=_has_benefit("fly"), source=f"feature:{P}glistening_flight"),), passive=True),
    aberrant("see_the_invisible", 14, *BENEFITS["see_invisible"], 146,
             ("Beneficio di Rivelazione nella Carne: vedi le creature invisibili entro 18 m che non sono dietro copertura totale.",
              "Revelation in Flesh benefit: you see invisible creatures within 60 ft that are not behind total cover."),
             modifiers=(Modifier("sense:see_invisible", 60, when=_has_benefit("see_invisible"), source=f"feature:{P}see_the_invisible"),), passive=True),
    aberrant("wormlike_movement", 14, *BENEFITS["worm"], 146,
             ("Beneficio di Rivelazione nella Carne: attraversi spazi di 2,5 cm e spendi 1,5 m per sfuggire a trattenimenti non magici o Afferrato.",
              "Revelation in Flesh benefit: you pass through 1-inch spaces and spend 5 ft to escape nonmagical restraints or Grappled."),
             passive=True),
    aberrant("warping_implosion", 18, "Implosione Distorcente", "Warping Implosion", 146,
             ("Azione Magia: teletrasporto entro 36 m; creature entro 9 m dallo spazio lasciato, TS Forza o 3d10 forza e trascinamento (metà se riesce). Un uso.",
              "Magic action: teleport up to 120 ft; creatures within 30 ft of where you were make a Strength save or take 3d10 force and are pulled (half on a success). One use."),
             "action", uses=Uses(table={18: 1}), restoration="long_rest", on_use=IMPLOSION_USE, dc_ability="charisma"),

    # Stregoneria Meccanica
    *_spells("clockwork", CLOCKWORK, "clockwork_spells", "Incantesimi Meccanici", "Clockwork Spells", 146, CLOCK_SPELLS),
    clockwork("restore_balance", 3, "Ripristinare l'Equilibrio", "Restore Balance", 146,
              ("Reazione: una creatura entro 18 m che tira un d20 con vantaggio o svantaggio lo tira senza. Usi pari a Carisma (minimo 1).",
               "Reaction: a creature within 60 ft rolling a d20 with advantage or disadvantage rolls without. Uses equal to Charisma (minimum 1)."),
              "reaction", uses=Uses(ability="charisma", minimum=1), restoration="long_rest", roll_options=(RESTORE_OWN_ROLL,),
              on_use=OnUse(slot="reaction", message=_both("Il GM tira senza vantaggio né svantaggio il d20 della creatura entro 18 m.",
                                                          "The GM rolls that creature's d20 (within 60 ft) without advantage or disadvantage."))),
    clockwork("bastion_of_law", 6, "Bastione della Legge", "Bastion of Law", 147,
              ("Azione Magia, 1-5 punti: tanti d8 su di te o su una creatura entro 9 m; chi subisce danni ne spende e ne riduce il danno. Fino al riposo lungo.",
               "Magic action, 1-5 points: that many d8 on you or a creature within 30 ft; when it takes damage it spends some to reduce it. Until a long rest."),
              "action", on_use=BASTION_USE, roll_options=BASTION_DAMAGE),
    clockwork("trance_of_order", 14, "Trance dell'Ordine", "Trance of Order", 147,
              ("Azione bonus, 1 minuto: i tiri per colpire contro di te non hanno vantaggio e un d20 di 9 o meno nelle Prove vale 10. Un uso.",
               "Bonus action, 1 minute: attack rolls against you lack advantage and a d20 of 9 or lower on checks counts as 10. One use."),
              "bonus_action", uses=Uses(table={14: 1}), restoration="long_rest", on_use=TRANCE_USE,
              modifiers=(Modifier("min_d20", 10, when=lambda c: state_on(c, "trance_of_order") and c.roll in D20_TESTS,
                                  source=f"feature:{P}trance_of_order"),)),
    clockwork("clockwork_cavalcade", 18, "Cavalcata Meccanica", "Clockwork Cavalcade", 147,
              ("Azione Magia: Cubo di 9 m, cura fino a 100 PF divisi, ripara oggetti, termina incantesimi di livello 6 o inferiore. Un uso.",
               "Magic action: 30 ft cube, heal up to 100 hit points split, repair objects, end spells of level 6 or lower. One use."),
              "action", uses=Uses(table={18: 1}), restoration="long_rest", on_use=CAVALCADE_USE),

    # Stregoneria Draconica
    draconic("draconic_resilience", 3, "Resilienza Draconica", "Draconic Resilience", 148,
             ("PF massimi +3 al 3° e +1 per ogni livello da stregone dopo; senza armatura la CA è 10 + Destrezza + Carisma.",
              "Hit point maximum +3 at 3rd and +1 per sorcerer level after; unarmored AC is 10 + Dexterity + Charisma."),
             modifiers=(Modifier("hp_max", lambda c: c.class_level, source=f"feature:{P}draconic_resilience"),),
             unarmored=UnarmoredAc(("dexterity", "charisma")), passive=True),
    *_spells("draconic", DRACONIC, "draconic_spells", "Incantesimi Draconici", "Draconic Spells", 148, DRACONIC_SPELLS),
    draconic("elemental_affinity", 6, "Affinità Elementale", "Elemental Affinity", 148,
             ("Scegli acido, freddo, fuoco, fulmine o veleno: resistenza a quel tipo e + Carisma a un tiro dei danni dei tuoi incantesimi di quel tipo.",
              "Choose acid, cold, fire, lightning or poison: resistance to it and + Charisma to one damage roll of your spells of that type."),
             roll_options=(AFFINITY_BONUS,), passive=True,
             choices=(ChoiceSpec(group=AFFINITY_GROUP, levels={6: 1}, options=lambda _c: list(AFFINITY_TYPES), label=_affinity_label, listed=True),),
             modifiers=tuple(Modifier(f"resistance:{t}", 1, when=lambda c, t=t: _affinity_type(c) == t, source=f"feature:{P}elemental_affinity")
                             for t in AFFINITY_TYPES)),
    draconic("dragon_wings", 14, "Ali di Drago", "Dragon Wings", 148,
             ("Azione bonus: ali per 1 ora o finché le congedi (nessuna azione); velocità di volo 18 m. Un uso.",
              "Bonus action: wings for 1 hour or until you dismiss them (no action); flying speed 60 ft. One use."),
             "bonus_action", uses=Uses(table={14: 1}), restoration="long_rest", on_use=WINGS_USE,
             modifiers=(Modifier("fly_speed_value", 60, when=lambda c: state_on(c, "dragon_wings"), source=f"feature:{P}dragon_wings"),)),
    draconic("dragon_companion", 18, "Compagno Draconico", "Dragon Companion", 149,
             ("Evocare drago senza componente materiale e una volta per riposo lungo senza slot; puoi evitare la concentrazione (1 minuto).",
              "Summon Dragon with no material component, once per long rest without a slot; you may skip concentration (1 minute)."),
             uses=Uses(table={18: 1}), restoration="long_rest", free_spell="summon-dragon", roll_options=(NO_CONCENTRATION,), passive=True),

    # Magia Selvaggia
    wild("wild_magic_surge", 3, "Impulso di Magia Selvaggia", "Wild Magic Surge", 149,
         ("Dopo un incantesimo da stregone con uno slot, d20 una volta per turno: con 20 tiri 1d100 sulla tabella e l'app applica gli effetti.",
          "After a sorcerer spell cast with a slot, a d20 once per turn: on a 20 you roll the 1d100 table and the app applies the effects."),
         "special", on_use=OnUse(panel="wild_magic"), turn_start_heal=_regeneration, dc_ability="charisma", modifiers=SURGE_MODIFIERS),
    wild("tides_of_chaos", 3, "Maree del Caos", "Tides of Chaos", 149,
         ("Vantaggio a una Prova con d20. Torna dopo un incantesimo da stregone con uno slot (con un impulso) o un riposo lungo.",
          "Advantage on a d20 check. It returns after a sorcerer spell cast with a slot (with a surge) or a long rest."),
         uses=Uses(table={3: 1}), restoration="long_rest", roll_options=(TIDES_ADVANTAGE,)),
    wild("bend_luck", 6, "Piegare la Fortuna", "Bend Luck", 149,
         ("Reazione, 1 punto: dopo il d20 di una Prova di un'altra creatura che vedi, tira 1d4 e applicalo come bonus o penalità.",
          "Reaction, 1 point: after another creature you can see rolls a d20 check, roll 1d4 and apply it as a bonus or penalty."),
         "reaction", on_use=replace(BEND_LUCK_USE, cost=1)),
    wild("controlled_chaos", 14, "Caos Controllato", "Controlled Chaos", 149,
         ("Sulla tabella degli impulsi tiri due volte e scegli il risultato.", "On the surge table you roll twice and choose the result."),
         passive=True),
    wild("tamed_surge", 18, "Impulso Domato", "Tamed Surge", 150,
         ("Dopo un incantesimo da stregone con uno slot scegli un effetto della tabella, tranne 97-00, invece di tirare. Un uso.",
          "After a sorcerer spell cast with a slot, choose a table effect, except 97-00, instead of rolling. One use."),
         uses=Uses(table={18: 1}), restoration="long_rest", on_use=OnUse(panel="wild_magic")),

)

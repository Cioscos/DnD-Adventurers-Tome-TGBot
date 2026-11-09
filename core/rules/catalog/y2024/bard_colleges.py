"""I quattro Collegi del Bardo 2024: Danza, Incanto, Sapienza, Valore.

Valori dalla scheda ``docs/superpowers/rules/2024/classes/bard.md``; i testi sono nostri, mai quelli del manuale.
"""
from __future__ import annotations

import re
from typing import Any

from core.rules.catalog._common import INCAPACITATING, feature, skill_label, state_on, unarmored_unshielded
from core.rules.catalog.y2014.bard import ALL_SKILLS, BI, _no_options, inspiration_die
from core.rules.schools import normalize_school
from core.rules.states import begin_state
from core.rules.types import ChoiceSpec, Cost, OnUse, RollOptionSpec, RuleContext, StateSpec, TargetEffect, UnarmoredAc, Uses, UseChoice, UseToggle

ED, CK = "2024", "bard"
_LONG_CASTING = re.compile(r"minut|minute|\bor[ae]\b|hour", re.IGNORECASE)  # un lancio di minuti o ore non è un'azione
AGILE_KEY = "agile_strikes"  # turn_state: Colpi Senz'Armi guadagnati spendendo Ispirazione Bardica in questo turno
EVASION_STATE = "evasion"


def _both(it: str, en: str):
    return lambda _ctx, _params=None: {"it": it, "en": en}


def _incapacitated(char: Any) -> bool:
    return any((char.conditions or {}).get(c) for c in INCAPACITATING)


def _die(ctx: RuleContext, _inputs: dict | None = None) -> str:
    return f"1d{inspiration_die(ctx.class_level)}"


def _m(ft: int) -> str:
    return f"{ft * 3 / 10:g}".replace(".", ",") + " m"


# ---------------------------------------------------------------------------
# Collegio della Danza
# ---------------------------------------------------------------------------

def note_inspiration_spent(ctx: RuleContext) -> None:
    """Un uso di Ispirazione Bardica speso in un'azione, azione bonus o reazione: Colpi Agili ne ricava un Colpo Senz'Armi."""
    if getattr(ctx.class_row, "subclass_key", None) == "dance" and ctx.class_level >= 3:
        turn = dict(ctx.char.turn_state or {})
        turn[AGILE_KEY] = turn.get(AGILE_KEY, 0) + 1
        ctx.char.turn_state = turn


def _agile_confirmed(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    turn = dict(ctx.char.turn_state or {})
    turn[AGILE_KEY] = max(0, turn.get(AGILE_KEY, 0) - 1)
    ctx.char.turn_state = turn


def _bare_unarmed(ctx: RuleContext) -> bool:
    """Un Colpo Senz'Armi (né arma né incantesimo) di chi non porta armatura né Scudo."""
    return ctx.item is None and ctx.spell is None and unarmored_unshielded(ctx.char)


DANCING = RollOptionSpec(
    key=f"{CK}.dazzling_footwork_dance", phase="before", rolls=("skill",), mode="advantage",
    available=lambda c: c.skill == "performance" and unarmored_unshielded(c.char),
    label={"it": "Virtuoso della Danza: la prova implica ballare? Vantaggio a Intrattenere",
           "en": "Dance Virtuoso: does the check involve dancing? Advantage on Performance"})

BARDIC_DAMAGE = RollOptionSpec(
    key=f"{CK}.bardic_damage", phase="before", rolls=("attack",), available=_bare_unarmed, unarmed_dice=_die,
    label={"it": "Danno Bardico: danno contundente pari al dado di Ispirazione più Destrezza, senza consumare il dado",
           "en": "Bardic Damage: bludgeoning damage equal to the Inspiration die plus Dexterity, without using the die"})

AGILE_STRIKES = RollOptionSpec(
    key=f"{CK}.agile_strikes", phase="before", rolls=("attack",), outside_action=True, on_confirm=_agile_confirmed,
    available=lambda c: _bare_unarmed(c) and (c.turn or {}).get(AGILE_KEY, 0) > 0,
    label={"it": "Colpi Agili: Colpo Senz'Armi gratuito, parte dell'azione in cui hai speso Ispirazione",
           "en": "Agile Strikes: a free Unarmed Strike, part of the action where you spent Inspiration"})


def _movement_message(ctx: RuleContext, _params: dict) -> dict[str, str]:
    from core.rules.modifiers import effective_speed  # import locale: modifiers usa il catalogo
    half = effective_speed(ctx.char, ctx.char.speed) // 2
    return {"it": f"Ti muovi fino a {_m(half)} (metà Velocità) senza provocare Attacchi di Opportunità; un alleato entro 9 m "
                  "può muoversi di metà della sua Velocità con la sua reazione.",
            "en": f"You move up to {half} ft (half your Speed) without provoking Opportunity Attacks; an ally within 30 ft "
                  "can move half its Speed using its reaction."}


TANDEM = RollOptionSpec(
    key=f"{CK}.tandem_footwork", phase="before", rolls=("initiative",), cost=Cost(feature_key=BI), extra_dice=_die,
    available=lambda c: not _incapacitated(c.char),
    label={"it": "Passo a Due: spendi Ispirazione Bardica e somma il dado all'Iniziativa tua e degli alleati entro 9 m",
           "en": "Tandem Footwork: spend Bardic Inspiration and add the die to your Initiative and your allies' within 30 ft"},
    effect=_both("Tu e ogni alleato entro 9 m che ti vede o sente ottenete lo stesso bonus all'Iniziativa: il risultato del dado è nel tiro.",
                 "You and every ally within 30 ft who can see or hear you get the same Initiative bonus: the die result is in the roll."))


def _evasion_started(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    begin_state(ctx.char, StateSpec(EVASION_STATE, rounds=1, ends_on=("new_turn", "manual")), f"{CK}.leading_evasion", "Evasione Guida")


def _evasion_ready(ctx: RuleContext) -> bool:
    return any(s.get("key") == EVASION_STATE for s in ctx.char.active_states or []) and not _incapacitated(ctx.char)


EVASION_SAVE = RollOptionSpec(
    key=f"{CK}.leading_evasion", phase="before", rolls=("save",),
    available=lambda c: c.ability == "dexterity" and not _incapacitated(c.char), on_confirm=_evasion_started,
    label={"it": "Evasione Guida: l'effetto dimezza i danni con un TS Destrezza?",
           "en": "Leading Evasion: does the effect halve damage on a Dexterity save?"},
    effect=_both("Evasione Guida: se superi il TS non subisci danni, se lo fallisci subisci la metà; le creature entro 1,5 m "
                 "che fanno lo stesso tiro ottengono lo stesso beneficio. Applica l'esito al danno.",
                 "Leading Evasion: if you pass the save you take no damage, on a failure you take half; creatures within 5 ft "
                 "making the same save get the same benefit. Apply the outcome to the damage."))
EVASION_SUCCESS = RollOptionSpec(
    key=f"{CK}.leading_evasion_success", phase="damage_in", rolls=("damage_taken",), multiplier=0, group="evasion",
    cost=Cost(state_key=EVASION_STATE), available=_evasion_ready,
    label={"it": "Evasione Guida: hai superato il TS, nessun danno", "en": "Leading Evasion: you passed the save, no damage"})
EVASION_FAILED = RollOptionSpec(
    key=f"{CK}.leading_evasion_failed", phase="damage_in", rolls=("damage_taken",), multiplier=0.5, group="evasion",
    cost=Cost(state_key=EVASION_STATE), available=_evasion_ready,
    label={"it": "Evasione Guida: hai fallito il TS, metà del danno", "en": "Leading Evasion: you failed the save, half damage"})


def _dance(key: str, level: int, title: str, name: tuple[str, str], summary: tuple[str, str], action_type: str | None = None, **kw: Any):
    return feature(key, CK, ED, level, title, name, summary, action_type, subclass="dance", **kw)


DANCE = (
    _dance("dazzling_footwork", 3, "Passo Abbagliante / Dazzling Footwork (Collegio della Danza 3, pag. 64)",
           ("Passo Abbagliante", "Dazzling Footwork"),
           ("Senza armatura né Scudo: vantaggio a Intrattenere ballando, CA 10 + Des + Car, Colpi Senz'Armi con Des e danno bardico.",
            "Without armor or a Shield: advantage on Performance when dancing, AC 10 + Dex + Cha, Unarmed Strikes with Dex and bardic damage."),
           unarmored=UnarmoredAc(("dexterity", "charisma"), no_shield=True), dex_unarmed=True,
           roll_options=(DANCING, BARDIC_DAMAGE, AGILE_STRIKES), passive=True),
    _dance("inspiring_movement", 6, "Movimento Ispiratore / Inspiring Movement (Collegio della Danza 6, pag. 64)",
           ("Movimento Ispiratore", "Inspiring Movement"),
           ("Reazione, un uso di Ispirazione: un nemico finisce il turno entro 1,5 m, ti muovi di metà Velocità e un alleato entro 9 m anche.",
            "Reaction, one Inspiration use: an enemy ends its turn within 5 ft, you move half your Speed and an ally within 30 ft does too."),
           "reaction", on_use=OnUse(slot="reaction", spends=BI, message=_movement_message, effect=lambda c, p: note_inspiration_spent(c))),
    _dance("tandem_footwork", 6, "Passo a Due / Tandem Footwork (Collegio della Danza 6, pag. 64)",
           ("Passo a Due", "Tandem Footwork"),
           ("All'Iniziativa, se non sei Incapacitato, spendi un uso di Ispirazione: il dado si somma all'Iniziativa tua e degli alleati entro 9 m.",
            "On Initiative, if not Incapacitated, spend an Inspiration use: the die adds to your Initiative and your allies' within 30 ft."),
           roll_options=(TANDEM,), passive=True),
    _dance("leading_evasion", 14, "Evasione Guida / Leading Evasion (Collegio della Danza 14, pag. 65)",
           ("Evasione Guida", "Leading Evasion"),
           ("TS Destrezza per dimezzare: successo nessun danno, fallimento metà; vale anche per le creature entro 1,5 m. Non se Incapacitato.",
            "Dexterity save to halve: success no damage, failure half; also for creatures within 5 ft. Not while Incapacitated."),
           roll_options=(EVASION_SAVE, EVASION_SUCCESS, EVASION_FAILED), passive=True),
)

# ---------------------------------------------------------------------------
# Collegio dell'Incanto
# ---------------------------------------------------------------------------

BEGUILING = f"{CK}.beguiling_magic"
MAJESTY = f"{CK}.mantle_of_majesty"


def _spell_dc(ctx: RuleContext) -> int:
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    from core.rules.spellcasting import caster_stats  # import locale: spellcasting usa il catalogo
    mine = next((s.save_dc for s in caster_stats(ctx.char) if ctx.class_row is not None and s.class_id == ctx.class_row.id), None)
    return mine if mine is not None else 8 + ctx.char.proficiency_bonus + effective_ability_mod(ctx.char, "charisma")


def _own_row(ctx: RuleContext, key: str) -> Any:
    return next((a for a in ctx.char.abilities if a.feature_key == key and a.source_class_id == getattr(ctx.class_row, "id", None)), None)


def _charm_or_illusion(ctx: RuleContext) -> bool:
    """Un incantesimo di Ammaliamento o Illusione lanciato con uno slot (né un trucchetto, né un lancio gratuito o rituale)."""
    return ctx.spell is not None and ctx.spell.level >= 1 and not ctx.slotless and normalize_school(ctx.spell.school) in ("enchantment", "illusion")


def _beguiled(slug: str, it: str, en: str) -> RollOptionSpec:
    def effect(ctx: RuleContext, _inputs: dict) -> dict[str, str]:
        dc = _spell_dc(ctx)
        return {"it": f"Magia Ammaliante, CD {dc}: una creatura entro 18 m che vedi fa un TS Saggezza; se fallisce è {it} per 1 minuto "
                      "e ripete il TS alla fine di ogni suo turno.",
                "en": f"Beguiling Magic, DC {dc}: a creature within 60 ft that you can see makes a Wisdom save; on a failure it is "
                      f"{en} for 1 minute and repeats the save at the end of each of its turns."}
    return RollOptionSpec(
        key=f"{BEGUILING}_{slug}", phase="before", rolls=("cast",), cost=Cost(feature_key=BEGUILING), group="beguiling",
        available=_charm_or_illusion, effect=effect,
        label={"it": f"Magia Ammaliante: la creatura è {it.lower()} se fallisce il TS Saggezza",
               "en": f"Beguiling Magic: the creature is {en} on a failed Wisdom save"},
        target_effect=lambda ctx, _i: TargetEffect(condition=slug, save_ability="wisdom", save_dc=_spell_dc(ctx), rounds=10, repeat_save="end"))


def _beguiling_restorable(ctx: RuleContext) -> bool:
    row = _own_row(ctx, BEGUILING)
    return row is not None and row.max_uses is not None and (row.uses or 0) < row.max_uses


def _beguiling_restore(ctx: RuleContext, _params: dict) -> None:
    row = _own_row(ctx, BEGUILING)
    if row is not None and row.max_uses is not None:
        row.uses = min(row.max_uses, (row.uses or 0) + 1)


def _mantle_targets(ctx: RuleContext) -> int:
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    return max(1, effective_ability_mod(ctx.char, "charisma"))


def _mantle_message(ctx: RuleContext, _params: dict) -> dict[str, str]:
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    n = max(1, effective_ability_mod(ctx.char, "charisma"))
    word_it, word_en = ("creatura", "creature") if n == 1 else ("creature", "creatures")
    return {"it": f"Fino a {n} {word_it} entro 18 m ottengono PF temporanei pari al doppio del dado e possono usare la reazione per "
                  "muoversi fino alla loro Velocità, senza Attacchi di Opportunità.",
            "en": f"Up to {n} {word_en} within 60 ft get temporary hit points equal to twice the die and can use their reaction "
                  "to move up to their Speed, without Opportunity Attacks."}


def _majesty_levels(ctx: RuleContext) -> list[str]:
    return [str(level) for level in sorted({s.level for s in ctx.char.spell_slots or [] if s.level >= 3 and s.available > 0})]


def _majesty_state(ctx: RuleContext, _params: dict) -> StateSpec:
    return StateSpec("mantle_of_majesty", rounds=10, ends_on=("concentration_end", "manual"),
                     data={"free_cast": "command", "free_cast_slot": "bonus", "free_cast_keep": True, "dc": _spell_dc(ctx),
                           "save": "wisdom", "others": [MAJESTY]})


def _majesty_message(ctx: RuleContext, _params: dict) -> dict[str, str]:
    dc = _spell_dc(ctx)
    return {"it": f"Lanci Comando senza slot (CD {dc}) e assumi un aspetto sovrannaturale per 1 minuto. Finché dura puoi lanciare "
                  "Comando come azione bonus senza slot; una creatura da te Affascinata fallisce il TS contro questo Comando.",
            "en": f"You cast Command without a slot (DC {dc}) and take on an otherworldly appearance for 1 minute. While it lasts "
                  "you can cast Command as a bonus action without a slot; a creature charmed by you fails its save against this Command."}


def _majesty_check(_ctx: RuleContext, params: dict) -> tuple[int, str] | None:
    return (422, "invalid_choice") if params.get("restore") and params.get("slot_level") is None else None


MAJESTY_USE = OnUse(
    slot="bonus", concentration=True, state=_majesty_state, message=_majesty_message, spends_slot="slot_level",
    spends_slot_when=lambda _c, p: bool(p.get("restore")), cost_by=lambda _c, p: 0 if p.get("restore") else 1, check=_majesty_check,
    toggles=(UseToggle("restore", {"it": "Ripristina spendendo uno slot di 3° livello o superiore (nessuna azione)",
                                   "en": "Restore by spending a level 3 or higher slot (no action)"}),),
    choices=(UseChoice("slot_level", {"it": "Slot da spendere per ripristinare", "en": "Slot to spend to restore"}, _majesty_levels,
                       lambda level: {"it": f"Slot di {level}° livello", "en": f"Level {level} slot"}, optional=True),))


def _unbreakable_state(ctx: RuleContext, _params: dict) -> StateSpec:
    return StateSpec("unbreakable_majesty", rounds=10, ends_on=("incapacitated", "manual"),
                     data={"dc": _spell_dc(ctx), "save": "charisma", "others": [f"{CK}.unbreakable_majesty"]})


UNBREAKABLE_MISS = RollOptionSpec(
    key=f"{CK}.unbreakable_majesty_miss", phase="damage_in", rolls=("damage_taken",), multiplier=0,
    available=lambda c: state_on(c, "unbreakable_majesty") and not _incapacitated(c.char),
    label={"it": "Maestà Infrangibile: è il primo colpo di questa creatura nel turno e ha fallito il TS Carisma? L'attacco manca",
           "en": "Unbreakable Majesty: is this the creature's first hit this turn and did it fail the Charisma save? The attack misses"},
    effect=lambda ctx, _i: {"it": f"Maestà Infrangibile (CD {_spell_dc(ctx)}): la creatura ha fallito il TS Carisma e l'attacco manca.",
                            "en": f"Unbreakable Majesty (DC {_spell_dc(ctx)}): the creature failed the Charisma save and the attack misses."})


def _glamour(key: str, level: int, title: str, name: tuple[str, str], summary: tuple[str, str], action_type: str | None = None, **kw: Any):
    return feature(key, CK, ED, level, title, name, summary, action_type, subclass="glamour", **kw)


GLAMOUR = (
    _glamour("beguiling_magic", 3, "Magia Ammaliante / Beguiling Magic (Collegio dell'Incanto 3, pag. 65)",
             ("Magia Ammaliante", "Beguiling Magic"),
             ("Charme su Persone e Immagine Speculare sempre preparati. Dopo Ammaliamento o Illusione con uno slot: TS Saggezza, Affascinato o Spaventato.",
              "Charm Person and Mirror Image always prepared. After an Enchantment or Illusion with a slot: Wisdom save, Charmed or Frightened."),
             uses=Uses(table={3: 1}), restoration="long_rest", granted_spells=("charm-person", "mirror-image"),
             roll_options=(_beguiled("charmed", "Affascinata", "Charmed"), _beguiled("frightened", "Spaventata", "Frightened")),
             on_use=OnUse(spends=BI, available=_beguiling_restorable, effect=_beguiling_restore)),
    _glamour("mantle_of_inspiration", 3, "Mantello di Ispirazione / Mantle of Inspiration (Collegio dell'Incanto 3, pag. 65)",
             ("Mantello di Ispirazione", "Mantle of Inspiration"),
             ("Azione bonus, un uso di Ispirazione: tiri il dado e fino a Car creature entro 18 m ottengono il doppio come PF temporanei.",
              "Bonus action, one Inspiration use: roll the die and up to Cha creatures within 60 ft get twice the result as temporary HP."),
             "bonus_action", on_use=OnUse(slot="bonus", spends=BI, rolls=_die, gives=lambda _c, rolled: 2 * rolled, message=_mantle_message,
                                          temp_hp_ally=True, ally_count=_mantle_targets)),
    _glamour("mantle_of_majesty", 6, "Mantello di Maestà / Mantle of Majesty (Collegio dell'Incanto 6, pag. 65)",
             ("Mantello di Maestà", "Mantle of Majesty"),
             ("Comando sempre preparato. Azione bonus: lo lanci senza slot per 1 minuto e per la durata puoi rilanciarlo come azione bonus senza slot.",
              "Command always prepared. Bonus action: cast it without a slot for 1 minute and recast it as a bonus action without a slot."),
             "bonus_action", uses=Uses(table={6: 1}), restoration="long_rest", granted_spells=("command",), on_use=MAJESTY_USE),
    _glamour("unbreakable_majesty", 14, "Maestà Infrangibile / Unbreakable Majesty (Collegio dell'Incanto 14, pag. 66)",
             ("Maestà Infrangibile", "Unbreakable Majesty"),
             ("Azione bonus, 1 minuto: il primo colpo di una creatura in un turno chiede un TS Carisma contro la tua CD, altrimenti manca.",
              "Bonus action, 1 minute: a creature's first hit in a turn asks for a Charisma save against your DC, otherwise it misses."),
             "bonus_action", uses=Uses(table={14: 1}), restoration="short_rest", roll_options=(UNBREAKABLE_MISS,),
             on_use=OnUse(slot="bonus", state=_unbreakable_state)),
)

# ---------------------------------------------------------------------------
# Collegio della Sapienza
# ---------------------------------------------------------------------------

def _skill_proficient(ctx: RuleContext, skill: str) -> bool:
    return bool((ctx.char.skills or {}).get(skill))


def _untrained_skills(ctx: RuleContext) -> list[str]:
    return [s for s in ALL_SKILLS if not _skill_proficient(ctx, s)]


def _proficient_skills(ctx: RuleContext) -> list[str]:
    """Abilità già competenti: un Bardo salvato prima del catalogo le dichiara «già sulla scheda» (R39)."""
    return [s for s in ALL_SKILLS if _skill_proficient(ctx, s)]


PEERLESS_SKILL = RollOptionSpec(
    key=f"{CK}.peerless_skill", phase="after_roll", after="add", rolls=("skill", "ability", "attack", "initiative"),
    cost=Cost(feature_key=BI), pay_if_success=True, extra_dice=_die,
    label={"it": "Abilità Impareggiabile: spendi Ispirazione Bardica e somma il dado al d20 (l'uso torna se il tiro fallisce comunque)",
           "en": "Peerless Skill: spend Bardic Inspiration and add the die to the d20 (the use comes back if the roll still fails)"})


def _lore(key: str, level: int, title: str, name: tuple[str, str], summary: tuple[str, str], action_type: str | None = None, **kw: Any):
    return feature(key, CK, ED, level, title, name, summary, action_type, subclass="lore", **kw)


LORE = (
    # Prima di Maestria (R39): le tre abilità di Sapienza sono quelle che la rendono scegliibile a chi nasce al 9°
    _lore("lore_bonus_proficiencies", 3, "Competenze Bonus / Bonus Proficiencies (Collegio della Sapienza 3, pag. 66)",
          ("Competenze Bonus", "Bonus Proficiencies"),
          ("Tre abilità a tua scelta, non ancora competenti, diventano competenti.",
           "Three skills of your choice that you are not proficient in become proficient."),
          choices=(ChoiceSpec(group="lore_skills", levels={3: 3}, options=_untrained_skills, label=skill_label,
                              grants="proficient", owned=_proficient_skills),)),
    _lore("cutting_words", 3, "Parole Taglienti / Cutting Words (Collegio della Sapienza 3, pag. 66)",
          ("Parole Taglienti", "Cutting Words"),
          ("Reazione: spendi un uso di Ispirazione Bardica e tiri il dado da sottrarre al tiro di una creatura entro 18 m.",
           "Reaction: spend a Bardic Inspiration use and roll the die to subtract from a creature's roll within 60 ft."),
          "reaction", on_use=OnUse(slot="reaction", rolls=_die, spends=BI, message=_both(
              "Sottrai il dado al tiro di danno, alla prova o al tiro per colpire di una creatura entro 18 m che vedi: "
              "il danno cala, un successo può diventare un fallimento.",
              "Subtract the die from the damage roll, ability check or attack roll of a creature within 60 ft that you can see: "
              "the damage drops, a success can become a failure."))),
    _lore("magical_discoveries", 6, "Scoperte Magiche / Magical Discoveries (Collegio della Sapienza 6, pag. 66)",
          ("Scoperte Magiche", "Magical Discoveries"),
          ("Due incantesimi dalle liste di Chierico, Druido o Mago (trucchetti o con slot), sempre preparati, sostituibili a ogni livello.",
           "Two spells from the Cleric, Druid or Wizard lists (cantrips or with slots), always prepared, replaceable at each level."),
          choices=(ChoiceSpec(group="magical_discoveries", levels={6: 2}, options=_no_options, spell_pick="extra",
                              always_prepared=True),), passive=True),
    _lore("peerless_skill", 14, "Abilità Impareggiabile / Peerless Skill (Collegio della Sapienza 14, pag. 67)",
          ("Abilità Impareggiabile", "Peerless Skill"),
          ("Dopo una prova o un tiro per colpire fallito spendi un uso di Ispirazione e sommi il dado; se fallisce comunque l'uso torna.",
           "After a failed check or attack roll spend an Inspiration use and add the die; if it still fails the use comes back."),
          roll_options=(PEERLESS_SKILL,), passive=True),
)


# ---------------------------------------------------------------------------
# Collegio del Valore
# ---------------------------------------------------------------------------

def _attacks_left(ctx: RuleContext) -> int:
    """Attacchi dell'azione Attacco che restano nel turno: il massimo fra le classi per azione, mai la somma."""
    from core.game.actions import attacks_per_action  # import locale, come sopra
    from core.rules.catalog import active_features  # import locale: questo modulo è caricato dal catalogo
    turn = ctx.turn or {}
    per_action = max(attacks_per_action(ctx.char.classes), *(spec.attacks_per_action for spec, _ in active_features(ctx.char)), 1)
    return per_action * (1 + turn.get("extra_actions", 0)) - turn.get("action_attacks", 0)


def _action_cantrip(ctx: RuleContext) -> bool:
    """Un trucchetto con tempo di lancio di un'azione, mentre dell'azione Attacco restano attacchi."""
    spell = ctx.spell
    if spell is None or spell.level != 0 or _attacks_left(ctx) < 1:
        return False
    from core.rules.spellcasting import casting_kind  # import locale
    return casting_kind(spell) == "action" and not _LONG_CASTING.search(spell.casting_time or "")


def _cantrip_for_an_attack(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    turn = dict(ctx.char.turn_state or {})
    turn["action_attacks"] = turn.get("action_attacks", 0) + 1
    ctx.char.turn_state = turn


CANTRIP_FOR_ATTACK = RollOptionSpec(
    key=f"{CK}.extra_attack_cantrip", phase="before", rolls=("cast",), available=_action_cantrip, on_confirm=_cantrip_for_an_attack,
    label={"it": "Attacco Extra: il trucchetto prende il posto di uno degli attacchi dell'azione Attacco",
           "en": "Extra Attack: the cantrip takes the place of one of the Attack action's attacks"})


def _after_action_spell(ctx: RuleContext) -> bool:
    """Un incantesimo con tempo di lancio di un'azione (di qualsiasi classe) lanciato in questo turno, e l'attacco non è un incantesimo."""
    return ctx.spell is None and (ctx.turn or {}).get("action_spell_level") is not None


BATTLE_MAGIC = RollOptionSpec(
    key=f"{CK}.battle_magic", phase="before", rolls=("attack",), slot="bonus", available=_after_action_spell,
    label={"it": "Magia da Battaglia: attacco con arma come azione bonus dopo un incantesimo da un'azione",
           "en": "Battle Magic: weapon attack as a bonus action after a one-action spell"})


def _valor(key: str, level: int, title: str, name: tuple[str, str], summary: tuple[str, str], action_type: str | None = None, **kw: Any):
    return feature(key, CK, ED, level, title, name, summary, action_type, subclass="valor", **kw)


VALOR = (
    _valor("combat_inspiration", 3, "Ispirazione in Combattimento / Combat Inspiration (Collegio del Valore 3, pag. 67)",
           ("Ispirazione in Combattimento", "Combat Inspiration"),
           ("Chi ha il tuo dado può sommarlo al danno di un colpo a segno o, in reazione, alla CA contro un attacco.",
            "A creature holding your die can add it to the damage of a hit or, as a reaction, to its AC against an attack."),
           passive=True),
    _valor("martial_training", 3, "Addestramento Marziale / Martial Training (Collegio del Valore 3, pag. 67)",
           ("Addestramento Marziale", "Martial Training"),
           ("Competenza con le armi da guerra, armature medie e Scudi; un'arma semplice o da guerra come focus.",
            "Proficiency with martial weapons, medium armor and Shields; a simple or martial weapon as a focus."),
           proficiency_grants={"armor": ("medium", "shields"), "weapons": ("martial",)}),
    _valor("extra_attack", 6, "Attacco Extra / Extra Attack (Collegio del Valore 6, pag. 67)",
           ("Attacco Extra", "Extra Attack"),
           ("Due attacchi con l'azione Attacco; un trucchetto da un'azione può sostituirne uno. Non si somma ad altri Attacco Extra.",
            "Two attacks with the Attack action; a one-action cantrip can replace one. Does not stack with other Extra Attack."),
           attacks_per_action=2, roll_options=(CANTRIP_FOR_ATTACK,)),
    _valor("battle_magic", 14, "Magia da Battaglia / Battle Magic (Collegio del Valore 14, pag. 67)",
           ("Magia da Battaglia", "Battle Magic"),
           ("Dopo un incantesimo con tempo di lancio di un'azione, un attacco con arma come azione bonus.",
            "After casting a spell with a casting time of one action, make one weapon attack as a bonus action."),
           roll_options=(BATTLE_MAGIC,)),
)

FEATURES = LORE + DANCE + GLAMOUR + VALOR

"""Warlock 2024, parte A (base della classe). Le sottoclassi (Fatato, Celestiale, Immondo, Grande Antico) sono la parte B, in
``warlock_subclasses.py``: le loro righe vanno in ``SUBCLASS_ROWS`` con ``subclass=`` (archfey, celestial, fiend, great_old_one).

Valori dalla scheda ``docs/superpowers/rules/2024/classes/warlock.md``; i testi sono nostri, mai quelli del manuale. Le suppliche
(e i Patti, che nel 2024 sono suppliche) stanno in ``warlock_invocations``. Per la parte B: ``dc(ctx)`` è la CD degli incantesimi,
``pact_slots(char)`` gli slot di Patto, ``is_pact_weapon`` e ``is_cantrip`` stanno in ``warlock_invocations``.
"""
from __future__ import annotations

from typing import Any

from core.rules.catalog._common import feature
from core.rules.catalog.y2014.warlock_invocations import _mod, _say
from core.rules.catalog.y2024 import warlock_invocations as inv
from core.rules.types import ChoiceSpec, OnUse, RollOptionSpec, RuleContext, Uses

ED, CK = "2024", "warlock"
ARCANUM = (("6", 11, 6), ("7", 13, 7), ("8", 15, 8), ("9", 17, 9))  # chiave, livello da warlock, livello dell'incantesimo
CONTACT = f"{CK}.contact_patron"
_ROWS = "core/rules/proficiencies.py (class_proficiencies, as_multiclass), api/routers/classes.py create_class_for_character e add_class"


def dc(ctx: RuleContext) -> int:
    """CD degli incantesimi del warlock: 8 + competenza + Carisma."""
    return 8 + ctx.char.proficiency_bonus + _mod(ctx, "charisma")


def pact_slots(char: Any) -> list[Any]:
    return [s for s in char.spell_slots or [] if s.is_pact]


# ---------------------------------------------------------------------------
# Astuzia Magica e Maestro dell'Occulto
# ---------------------------------------------------------------------------

def _cunning(ctx: RuleContext, _params: dict) -> None:
    """Rito di un minuto: torna metà dei massimi slot di Patto (per eccesso), tutti dal 20° livello; mai più degli slot spesi."""
    slots = pact_slots(ctx.char)
    total = sum(s.total for s in slots)
    budget = total if ctx.class_level >= 20 else -(-total // 2)
    for slot in slots:
        back = min(slot.used, budget)
        slot.used -= back
        budget -= back
    from core.rules.catalog.y2024.warlock_subclasses import resilience_hp  # import locale: il modulo dei patroni importa questo in fondo
    if (points := resilience_hp(ctx)) is not None:  # Resilienza Celestiale: PF temporanei a ogni uso di Astuzia Magica
        ctx.char.temp_hp = max(ctx.char.temp_hp or 0, points)


def _cunning_message(ctx: RuleContext, _params: dict) -> dict[str, str] | None:
    from core.rules.catalog.y2024.warlock_subclasses import resilience_ally_text  # import locale, come sopra
    return resilience_ally_text(ctx)


CUNNING_USE = OnUse(effect=_cunning, message=_cunning_message, available=lambda c: any(s.used > 0 for s in pact_slots(c.char)))


# ---------------------------------------------------------------------------
# Contattare il Patrono, Arcanum Mistico
# ---------------------------------------------------------------------------

CONTACT_SAVE = RollOptionSpec(
    key=f"{CK}.contact_patron_save", phase="before", rolls=("cast",),
    available=lambda c: c.spell is not None and (c.spell.srd_index or "") == "contact-other-plane" and c.slotless,
    label={"it": "Contattare il Patrono: il tuo TS dell'incantesimo riesce automaticamente",
           "en": "Contact Patron: your saving throw for the spell succeeds automatically"},
    effect=_say("Il lancio gratuito fa riuscire da solo il tuo TS dell'incantesimo: niente tiro.",
                "The free cast makes your own saving throw for the spell succeed on its own: no roll."))


def _no_options(_ctx: RuleContext) -> list[str]:
    return []


def _arcanum(grade: str, level: int, spell_level: int):
    return feature(
        f"mystic_arcanum_{grade}", CK, ED, level, "Arcanum Mistico / Mystic Arcanum (Warlock 11, pag. 155)",
        (f"Arcanum Mistico ({spell_level}° livello)", f"Mystic Arcanum (level {spell_level})"),
        (f"Un incantesimo da warlock di {spell_level}° livello scelto da te: lo lanci una volta per riposo lungo senza slot, dalla pagina degli incantesimi.",
         f"A warlock spell of level {spell_level} of your choice: you cast it once per long rest with no slot, from the spells page."),
        uses=Uses(table={level: 1}), restoration="long_rest", arcanum_group=f"arcanum_{grade}", passive=True,
        choices=(ChoiceSpec(group=f"arcanum_{grade}", levels={level: 1}, options=_no_options, spell_pick="extra", spell_level=spell_level,
                            spell_exact=True),))


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

BASE_ROWS = (
    feature("core_traits", CK, ED, 1, "Tratti base del Warlock / Core Warlock Traits (Warlock 1, pag. 153)", ("Tratti Base", "Core Warlock Traits"),
            ("Dado vita d8, TS Saggezza e Carisma, 2 abilità su 7, armi semplici, armatura leggera. Multiclasse: dado vita e armatura leggera.",
             "Hit die d8, Wisdom and Charisma saves, 2 skills out of 7, simple weapons, light armor. Multiclass: the hit die and light armor."),
            no_row=True, covered_by=f"{_ROWS}; test_hit_points_use_the_d8, test_class_and_multiclass_proficiencies; equipaggiamento di partenza: lavori-successivi"),
    feature("eldritch_invocations", CK, ED, 1, "Suppliche Occulte / Eldritch Invocations (Warlock 1, pag. 153)",
            ("Suppliche Occulte", "Eldritch Invocations"),
            ("Una supplica al 1° livello, fino a dieci al 18°: ne sostituisci una a ogni livello, ma non una che serve a un'altra. Alcune sono Ripetibili.",
             "One invocation at 1st level, up to ten at 18th: you replace one at each level, but not one another needs. Some are Repeatable."),
            no_row=True, choices=(inv.INVOCATION_CHOICE,),
            covered_by="ChoiceSpec invocations di questa riga e le righe delle suppliche; test_invocations_known_follow_the_level"),
    feature("pact_magic", CK, ED, 1, "Magia del Patto / Pact Magic (Warlock 1, pag. 153)", ("Magia del Patto", "Pact Magic"),
            ("Carisma; CD 8 + competenza + Carisma. Pochi slot tutti dello stesso livello, tornano con un riposo breve o lungo; trucchetti 2/3/4, preparati 2-15.",
             "Charisma; DC 8 + proficiency + Charisma. A few slots all of one level, back on a short or long rest; cantrips 2/3/4, prepared spells 2-15."),
            no_row=True, covered_by="core/data/spell_slots.py (compute_pact_slots, pool is_pact), core/rules/spellcasting.py (known_limits) e "
                                    "api/routers/spells.py _consume_cast (slot_id sceglie il pool); test_pact_slots_cantrips_and_prepared_follow_the_table"),
    feature("magical_cunning", CK, ED, 2, "Astuzia Magica / Magical Cunning (Warlock 2, pag. 154)", ("Astuzia Magica", "Magical Cunning"),
            ("Rito di 1 minuto: recuperi gli slot di Patto spesi, fino a metà del massimo (per eccesso). Un uso, riposo lungo. Al 20° recuperi tutti gli slot.",
             "A 1-minute rite: you regain spent Pact slots, up to half your maximum (rounded up). One use, long rest. At 20th you regain all of them."),
            "special", uses=Uses(table={2: 1}), restoration="long_rest", on_use=CUNNING_USE),
    feature("warlock_subclass", CK, ED, 3, "Sottoclasse del Warlock / Warlock Subclass (Warlock 3, pag. 154)",
            ("Sottoclasse del Warlock", "Warlock Subclass"),
            ("Al 3° livello si sceglie il Patrono Fatato, Celestiale, Immondo o Grande Antico: privilegi ai livelli 3, 6, 10 e 14.",
             "At level 3 you choose the Archfey, Celestial, Fiend or Great Old One Patron: features at levels 3, 6, 10 and 14."),
            no_row=True, covered_by="core/rules/subclasses.py (match_subclass) e il campo sottoclasse della classe"),
    feature("ability_score_improvement", CK, ED, 4, "Aumento dei Punteggi di Caratteristica / Ability Score Improvement (Warlock 4, pag. 155)",
            ("Aumento dei Punteggi di Caratteristica", "Ability Score Improvement"),
            ("Ai livelli 4, 8, 12 e 16: il talento Aumento dei Punteggi o un altro talento di cui hai i requisiti.",
             "At levels 4, 8, 12 and 16: the Ability Score Improvement feat or another feat you qualify for."),
            no_row=True, covered_by="core/rules/level_choices.py (scelta asi); test_asi_at_4_8_12_16_and_the_19th_is_an_epic_boon"),
    feature("contact_patron", CK, ED, 9, "Contattare il Patrono / Contact Patron (Warlock 9, pag. 155)", ("Contattare il Patrono", "Contact Patron"),
            ("Contattare altro piano è sempre preparato, fuori dal limite. Lo lanci una volta senza slot, e il tuo TS dell'incantesimo riesce da solo. Riposo lungo.",
             "Contact Other Plane is always prepared, outside the limit. You cast it once with no slot, and your saving throw for it succeeds on its own. Long rest."),
            uses=Uses(table={9: 1}), restoration="long_rest", granted_spells=("contact-other-plane",), free_spell="contact-other-plane",
            roll_options=(CONTACT_SAVE,), passive=True),
    *(_arcanum(grade, level, spell_level) for grade, level, spell_level in ARCANUM),
    feature("epic_boon", CK, ED, 19, "Dono Epico / Epic Boon (Warlock 19, pag. 155)", ("Dono Epico", "Epic Boon"),
            ("Al 19° livello un talento Dono Epico o un altro talento di cui hai i requisiti; consigliato Dono del Fato.",
             "At 19th level an Epic Boon feat or another feat you qualify for; Boon of Fate is recommended."),
            no_row=True, covered_by="core/rules/level_choices.py (scelta epic_boon); test_asi_at_4_8_12_16_and_the_19th_is_an_epic_boon"),
    feature("eldritch_master", CK, ED, 20, "Maestro dell'Occulto / Eldritch Master (Warlock 20, pag. 155)", ("Maestro dell'Occulto", "Eldritch Master"),
            ("Con Astuzia Magica recuperi tutti gli slot di Patto spesi invece di metà. Segue gli usi di Astuzia Magica.",
             "With Magical Cunning you regain all spent Pact slots instead of half. It follows the uses of Magical Cunning."), passive=True),
    *inv.INVOCATION_ROWS,
    feature("multiclassing", CK, ED, 1, "Multiclasse: Warlock / Multiclassing: Warlock (Manuale 2024, pag. 44)",
            ("Multiclasse: Warlock", "Multiclassing: Warlock"),
            ("Requisito Carisma 13. Da multiclasse: dado vita d8 e armatura leggera. Gli slot di Patto restano un pool a parte e valgono per gli incantesimi delle altre classi.",
             "Requires Charisma 13. As a multiclass: the d8 hit die and light armor. Pact slots stay a separate pool and work for other classes' spells."),
            no_row=True, covered_by=f"{_ROWS}, webapp/src/data/multiclassPrereqs.ts (D2) e api/routers/spells.py (_pick_slot, slot_id); "
                                    "test_multiclass_with_a_sorcerer_keeps_the_pact_pool_apart_and_points_count_only_sorcerer_levels"),
)

from core.rules.catalog.y2024.warlock_subclasses import SUBCLASS_ROWS  # noqa: E402  (parte B, dopo le definizioni comuni)

FEATURES = BASE_ROWS + SUBCLASS_ROWS

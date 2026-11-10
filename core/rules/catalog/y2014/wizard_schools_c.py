"""Scuola di Illusione e Scuola di Invocazione (evocation) del Mago 2014. Valori dalla scheda del Mago."""
from __future__ import annotations

from core.rules.catalog._common import feature, save_spell
from core.rules.catalog.y2014.wizard_common import CK, ED, mod, savant
from core.rules.schools import WINDOW_ILLUSION, WINDOW_ILLUSION_TURN, normalize_school
from core.rules.states import has_state
from core.rules.types import ChoiceSpec, Cost, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, Uses, UseText

OVERCHANNEL = f"{CK}.overchannel"
OVERCHANNEL_STATE = "overchannel"


def _no_options(_ctx: RuleContext) -> list[str]:
    return []


def _object_text() -> tuple[UseText, ...]:
    return (UseText("object", {"it": "Oggetto reso reale", "en": "Object made real"}, max_len=60),)


# ---------------------------------------------------------------------------
# Scuola di Illusione
# ---------------------------------------------------------------------------

ILLUSION = (
    savant("illusion"),
    feature("improved_minor_illusion", CK, ED, 2, "Illusione Minore Migliorata / Improved Minor Illusion (Illusione 2, pag. 86)",
            ("Illusione Minore Migliorata", "Improved Minor Illusion"),
            ("Impari illusione minore (o un altro trucchetto da mago se la conosci già), fuori dal limite dei trucchetti. Un lancio crea suono e immagine insieme.",
             "You learn minor illusion (or another wizard cantrip if you know it already), outside the cantrip limit. One casting makes sound and image together."),
            subclass="illusion", passive=True,
            choices=(ChoiceSpec(group="improved_minor_illusion", levels={2: 1}, options=_no_options, spell_pick="extra", spell_level=0,
                                spell_list="wizard"),)),
    feature("malleable_illusions", CK, ED, 6, "Illusioni Duttili / Malleable Illusions (Illusione 6, pag. 86)",
            ("Illusioni Duttili", "Malleable Illusions"),
            ("Azione: finché un'illusione da 1 minuto o più è attiva e la vedi, ne cambi la natura entro i limiti dell'incantesimo.",
             "Action: while an illusion of 1 minute or longer is active and you can see it, you change its nature within the spell's limits."),
            "action", subclass="illusion",
            on_use=OnUse(cost=0, slot="action", available=lambda c: has_state(c.char, WINDOW_ILLUSION))),
    feature("illusory_self", CK, ED, 10, "Sosia Illusorio / Illusory Self (Illusione 10, pag. 87)",
            ("Sosia Illusorio", "Illusory Self"),
            ("Reazione: un attacco contro di te manca automaticamente e il duplicato svanisce. Un uso, riposo breve o lungo.",
             "Reaction: an attack against you automatically misses and the duplicate vanishes. One use, short or long rest."),
            "reaction", subclass="illusion", uses=Uses(table={10: 1}), restoration="short_rest", on_use=OnUse(slot="reaction")),
    feature("illusory_reality", CK, ED, 14, "Realtà Illusoria / Illusory Reality (Illusione 14, pag. 87)",
            ("Realtà Illusoria", "Illusory Reality"),
            ("Azione bonus, nel turno in cui lanci un'illusione di 1° livello o più: un oggetto inanimato non magico dell'illusione diventa reale per 1 minuto. Non può ferire.",
             "Bonus action, on the turn you cast an illusion of 1st level or higher: a nonmagical inanimate object of the illusion becomes real for 1 minute. It cannot harm."),
            "bonus_action", subclass="illusion",
            on_use=OnUse(cost=0, slot="bonus", available=lambda c: has_state(c.char, WINDOW_ILLUSION_TURN), ends_state=WINDOW_ILLUSION_TURN,
                         texts=_object_text(),
                         state=lambda _c, p: StateSpec("illusory_reality", rounds=10, ends_on=("manual",), data={"object": str(p["object"]).strip()}))),
)

# ---------------------------------------------------------------------------
# Scuola di Invocazione
# ---------------------------------------------------------------------------


def _evocation_save(ctx: RuleContext) -> bool:
    return ctx.spell is not None and normalize_school(ctx.spell.school) == "evocation" and save_spell(ctx.spell)


def _sculpt_effect(ctx: RuleContext, _inputs: dict) -> dict[str, str]:
    n = 1 + (ctx.casting_level or ctx.spell.level)
    return {"it": f"Scegli fino a {n} creature che vedi: superano da sole il TS e non subiscono danni.",
            "en": f"Choose up to {n} creatures you can see: they automatically pass the save and take no damage."}


SCULPT_SPELLS = RollOptionSpec(
    key=f"{CK}.sculpt_spells", phase="before", rolls=("cast",), available=_evocation_save, effect=_sculpt_effect,
    label={"it": "Plasmare Incantesimi: proteggi alcune creature visibili dall'incantesimo",
           "en": "Sculpt Spells: shield some visible creatures from the spell"})


EMPOWERED_USED = "empowered_used"  # turn_state: l'incantesimo il cui tiro di danno ha già avuto il bonus (un tiro per lancio)


def _empowered(ctx: RuleContext) -> bool:
    spell = ctx.spell
    return (ctx.roll == "damage" and spell is not None and normalize_school(spell.school) == "evocation"
            and (ctx.char.turn_state or {}).get(EMPOWERED_USED) != spell.id
            and (spell.class_id == ctx.class_row.id or (spell.class_id is None and len(ctx.char.classes) == 1)))


def _overchannel_state(char) -> dict | None:
    return next((s for s in char.active_states or [] if s.get("key") == OVERCHANNEL_STATE), None)


def _count_overchannel(_session, ctx: RuleContext, _inputs: dict) -> None:
    """Un uso in più fra due riposi lunghi: lo stato porta il conto, il riposo lungo lo chiude."""
    from core.rules.states import begin_state  # import locale
    state = _overchannel_state(ctx.char)
    uses = int(((state or {}).get("data") or {}).get("uses") or 0) + 1
    begin_state(ctx.char, StateSpec(OVERCHANNEL_STATE, ends_on=("rest_long",), data={"uses": uses, "locked": True}), OVERCHANNEL, "Saturazione Magica")


def _overchannel_hurt(ctx: RuleContext, _inputs: dict) -> str | None:
    """Dal secondo uso: 2d12 per livello dell'incantesimo, e 1d12 per livello in più a ogni uso successivo."""
    uses = int(((_overchannel_state(ctx.char) or {}).get("data") or {}).get("uses") or 0)
    return f"{uses * (ctx.casting_level or ctx.spell.level)}d12" if uses >= 2 else None


OVERCHANNEL_OPTION = RollOptionSpec(
    key=OVERCHANNEL, phase="before", rolls=("spell_damage",), maximize=True, on_confirm=_count_overchannel, self_damage=_overchannel_hurt,
    available=lambda c: c.spell is not None and 1 <= (c.casting_level or c.spell.level) <= 5 and bool(c.spell.damage_dice),
    label={"it": "Saturazione Magica: i dadi di danno valgono il massimo (dal secondo uso subisci danni necrotici)",
           "en": "Overchannel: damage dice are maximized (from the second use you take necrotic damage)"})

EVOCATION = (
    savant("evocation"),
    feature("sculpt_spells", CK, ED, 2, "Plasmare Incantesimi / Sculpt Spells (Invocazione 2, pag. 87)",
            ("Plasmare Incantesimi", "Sculpt Spells"),
            ("Lanciando un'invocazione con TS scegli 1 + livello dell'incantesimo creature visibili: superano il TS e non subiscono danni.",
             "When you cast an evocation with a save you pick 1 + the spell's level visible creatures: they pass the save and take no damage."),
            subclass="evocation", roll_options=(SCULPT_SPELLS,)),
    feature("potent_cantrip", CK, ED, 6, "Trucchetto Potente / Potent Cantrip (Invocazione 6, pag. 87)",
            ("Trucchetto Potente", "Potent Cantrip"),
            ("Chi supera il TS contro un tuo trucchetto di danno ne subisce comunque metà, senza altri effetti.",
             "A creature that saves against your damaging cantrip still takes half the damage, with no other effect."),
            subclass="evocation", passive=True, save_half_cantrips=True),
    feature("empowered_evocation", CK, ED, 10, "Invocazione Potente / Empowered Evocation (Invocazione 10, pag. 87)",
            ("Invocazione Potente", "Empowered Evocation"),
            ("Aggiungi il modificatore di Intelligenza a un tiro di danno di ogni tuo incantesimo da mago di invocazione.",
             "Add your Intelligence modifier to one damage roll of every wizard evocation spell you cast."),
            subclass="evocation", modifiers=(Modifier("damage", lambda c: mod(c, "intelligence"), when=_empowered,
                                                       source=f"feature:{CK}.empowered_evocation"),)),
    feature("overchannel", CK, ED, 14, "Saturazione Magica / Overchannel (Invocazione 14, pag. 87)",
            ("Saturazione Magica", "Overchannel"),
            ("Un incantesimo da mago di 1°-5° livello infligge il massimo dei danni. Dal secondo uso fra riposi lunghi subisci 2d12 necrotici per livello (+1d12 a ogni uso).",
             "A wizard spell of 1st-5th level deals maximum damage. From the second use between long rests you take 2d12 necrotic per level (+1d12 each use)."),
            subclass="evocation", roll_options=(OVERCHANNEL_OPTION,)),
)

FEATURES = (*ILLUSION, *EVOCATION)

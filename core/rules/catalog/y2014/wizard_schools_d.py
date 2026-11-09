"""Scuola di Necromanzia e Scuola di Trasmutazione del Mago 2014. Valori dalla scheda del Mago."""
from __future__ import annotations

import uuid

from core.rules.catalog._common import feature
from core.rules.condition_removal import ConditionRemoval
from core.rules.catalog.y2014.wizard_common import CK, ED, dc, savant
from core.rules.schools import WINDOW_TRANSMUTATION
from core.rules.states import STOLEN_SPELL, begin_state, has_state
from core.rules.types import Modifier, OnUse, RuleContext, StateSpec, TargetEffect, UseChoice, Uses

STONE_STATE, LOCK_STATE = "transmuters_stone", "master_transmuter_lock"
ELEMENTS = ("acid", "cold", "lightning", "fire", "thunder")
_ELEMENT_LABELS = {"acid": ("acido", "acid"), "cold": ("freddo", "cold"), "lightning": ("fulmine", "lightning"),
                   "fire": ("fuoco", "fire"), "thunder": ("tuono", "thunder")}


def _choice(key: str, label: tuple[str, str], options: dict[str, tuple[str, str]], optional: bool = False) -> UseChoice:
    return UseChoice(key, {"it": label[0], "en": label[1]}, lambda _c: list(options),
                     lambda k: {"it": options[k][0], "en": options[k][1]}, optional=optional)


# ---------------------------------------------------------------------------
# Scuola di Necromanzia
# ---------------------------------------------------------------------------

_SCHOOL_CHOICE = {"necromancy": ("Di necromanzia (triplo del livello)", "Necromancy (three times the level)"),
                  "other": ("Di un'altra scuola (doppio del livello)", "Another school (twice the level)")}
_CREATURE_CHOICE = {"living": ("Una creatura viva", "A living creature"),
                    "construct_or_undead": ("Un costrutto o un non morto (nessun beneficio)", "A construct or undead (no benefit)")}

HARVEST_USE = OnUse(
    cost=0, once_per_turn=True,
    choices=(UseChoice("level", {"it": "Livello dell'incantesimo", "en": "Spell level"}, lambda _c: [str(n) for n in range(1, 10)],
                       lambda k: {"it": f"{k}° livello", "en": f"Level {k}"}),
             _choice("school", ("Scuola", "School"), _SCHOOL_CHOICE),
             _choice("creature", ("Creatura uccisa", "Creature killed"), _CREATURE_CHOICE)),
    check=lambda _c, p: (409, "no_benefit") if p.get("creature") == "construct_or_undead" else None,
    heal_by=lambda _c, p: int(p["level"]) * (3 if p["school"] == "necromancy" else 2))

_INTELLIGENCE = {"lt8": ("Intelligenza inferiore a 8", "Intelligence below 8"),
                 "8_11": ("Intelligenza da 8 a 11", "Intelligence 8 to 11"),
                 "12plus": ("Intelligenza 12 o più", "Intelligence 12 or higher")}
_COMMAND_NOTE = {"lt8": "command_undead_low", "8_11": "command_undead_mid", "12plus": "command_undead_high"}

COMMAND_USE = OnUse(
    cost=0, slot="action", choices=(_choice("intelligence", ("Intelligenza del non morto", "Undead's Intelligence"), _INTELLIGENCE),),
    state=lambda _c, p: StateSpec("command_undead", ends_on=("manual",), data={"intelligence": p["intelligence"]}),
    target_effect=lambda ctx, p: TargetEffect(
        condition="custom:commanded_undead", save_ability="charisma", save_dc=dc(ctx), immune_on_success=True,
        note=_COMMAND_NOTE[p["intelligence"]]))

NECROMANCY = (
    savant("necromancy"),
    feature("grim_harvest", CK, ED, 2, "Raccolto Macabro / Grim Harvest (Necromanzia 2, pag. 87)", ("Raccolto Macabro", "Grim Harvest"),
            ("Uccidendo con un incantesimo di 1° livello o più, una volta per turno, recuperi PF pari al doppio del suo livello, al triplo se è di necromanzia. Non con costrutti e non morti.",
             "When you kill with a spell of 1st level or higher, once per turn, you regain twice its level in hit points, three times if it is necromancy. Not for constructs or undead."),
            subclass="necromancy", on_use=HARVEST_USE),
    feature("undead_thralls", CK, ED, 6, "Servitori Non Morti / Undead Thralls (Necromanzia 6, pag. 88)", ("Servitori Non Morti", "Undead Thralls"),
            ("Animare morti entra nel libro. I non morti creati con la necromanzia hanno PF massimi + livello da mago e la tua competenza ai danni con le armi.",
             "Animate dead joins the book. Undead made with necromancy have maximum hit points + your wizard level and your proficiency bonus on weapon damage."),
            subclass="necromancy", passive=True, book_spells=("animate-dead",)),
    feature("inured_to_undeath", CK, ED, 10, "Impervio alla Non Morte / Inured to Undeath (Necromanzia 10, pag. 88)",
            ("Impervio alla Non Morte", "Inured to Undeath"),
            ("Resistenza ai danni necrotici; i tuoi PF massimi non possono essere ridotti.",
             "Resistance to necrotic damage; your hit point maximum cannot be reduced."),
            subclass="necromancy", hp_max_locked=True,
            modifiers=(Modifier("resistance:necrotic", 1, source=f"feature:{CK}.inured_to_undeath"),)),
    feature("command_undead", CK, ED, 14, "Comandare Non Morti / Command Undead (Necromanzia 14, pag. 88)",
            ("Comandare Non Morti", "Command Undead"),
            ("Azione: un non morto visibile entro 18 m fa un TS Carisma; se fallisce ti obbedisce finché non usi di nuovo il privilegio. Chi supera il TS è immune.",
             "Action: a visible undead within 60 ft makes a Charisma save; on a failure it obeys you until you use this again. A creature that saves is immune."),
            "action", subclass="necromancy", on_use=COMMAND_USE),
)

# ---------------------------------------------------------------------------
# Scuola di Trasmutazione
# ---------------------------------------------------------------------------

_BENEFITS = {"darkvision": ("Scurovisione 18 m", "Darkvision 60 ft"), "speed": ("+3 m di velocità", "+10 ft speed"),
             "constitution_save": ("Competenza nei TS Costituzione", "Constitution save proficiency"),
             "resistance": ("Resistenza a un tipo di danno", "Resistance to a damage type")}


def _stone_data(ctx: RuleContext) -> dict:
    return next((s.get("data") or {} for s in ctx.char.active_states or [] if s.get("key") == STONE_STATE), {})


def _stone(benefit: str, damage_type: str | None = None):
    def active(ctx: RuleContext) -> bool:
        data = _stone_data(ctx)
        return data.get("benefit") == benefit and (damage_type is None or data.get("damage_type") == damage_type)
    return active


def _not_overloaded(ctx: RuleContext) -> bool:
    """La pietra dà +3 m solo a chi non è ingombrato: oltre la capacità di carico non vale."""
    return not (ctx.char.carry_capacity and (ctx.char.encumbrance or 0) > ctx.char.carry_capacity)


def _stone_check(_ctx: RuleContext, params: dict) -> tuple[int, str] | None:
    if params.get("benefit") == "resistance" and params.get("damage_type") not in ELEMENTS:
        return 422, "invalid_choice"  # la resistenza vuole uno dei cinque tipi
    return None


def _stone_state(_ctx: RuleContext, params: dict) -> StateSpec:
    data = {"benefit": params["benefit"], **({"damage_type": params["damage_type"]} if params["benefit"] == "resistance" else {})}
    return StateSpec(STONE_STATE, ends_on=("manual",), data=data)


_STONE_CHOICES = (_choice("benefit", ("Beneficio", "Benefit"), _BENEFITS),
                  _choice("damage_type", ("Tipo di danno", "Damage type"), _ELEMENT_LABELS, optional=True))

STONE_USE = OnUse(cost=0, available=lambda c: not has_state(c.char, LOCK_STATE), choices=_STONE_CHOICES, check=_stone_check, state=_stone_state)
STONE_CHANGE_USE = OnUse(
    cost=0, available=lambda c: has_state(c.char, STONE_STATE) and has_state(c.char, WINDOW_TRANSMUTATION),
    ends_state=WINDOW_TRANSMUTATION, choices=_STONE_CHOICES, check=_stone_check, state=_stone_state)

STONE_MODIFIERS = (
    Modifier("sense:darkvision", 60, when=_stone("darkvision"), source=f"feature:{CK}.transmuters_stone"),
    Modifier("speed", 10, when=lambda c: _stone("speed")(c) and _not_overloaded(c), source=f"feature:{CK}.transmuters_stone"),
    Modifier("save", lambda c: c.char.proficiency_bonus,
             when=lambda c: c.roll in ("save", "concentration") and c.ability == "constitution" and _stone("constitution_save")(c)
             and not (c.char.saving_throws or {}).get("constitution"), source=f"feature:{CK}.transmuters_stone"),
    *(Modifier(f"resistance:{t}", 1, when=_stone("resistance", t), source=f"feature:{CK}.transmuters_stone") for t in ELEMENTS),
)


def _alchemy_state(_ctx: RuleContext, _params: dict) -> StateSpec:
    return StateSpec("minor_alchemy", rounds=600, ends_on=("concentration_end", "manual"))


def _after_stone(extra: OnUse | None = None):
    """Le opzioni di Maestro Trasmutatore consumano la pietra e la fanno ricomparire solo dopo un riposo lungo."""
    return dict(cost=0, slot="action", available=lambda c: has_state(c.char, STONE_STATE), ends_state=STONE_STATE,
                state=StateSpec(LOCK_STATE, ends_on=("rest_long",), data={"internal": True}))


def _restore_to_full(ctx: RuleContext, params: dict) -> int:
    from core.rules.modifiers import effective_hp_max  # import locale: modifiers usa il catalogo
    return max(0, effective_hp_max(ctx.char) - ctx.char.current_hit_points) if params.get("mode") == "self" else 0


_PANACEA_TARGET = {"self": ("Su di te", "On yourself"), "other": ("Su un'altra creatura", "On another creature")}

PANACEA_USE = OnUse(
    **_after_stone(), choices=(_choice("mode", ("Creatura toccata", "Creature touched"), _PANACEA_TARGET),), ally_modes=("other",),
    # veleno come condizione; maledizioni e malattie sono note. Su sé o su un PG della serata, nel foglio comune
    removal=ConditionRemoval(("poisoned",), ("curse", "disease"), count=None, bound=True),
    heal_by=_restore_to_full,
    message=lambda _c, p: {"it": "Una creatura toccata con la pietra torna a tutti i suoi PF e perde maledizioni, malattie e veleni."
                           if p["mode"] == "other" else "Recuperi tutti i tuoi PF e perdi veleno; maledizioni e malattie le toglie il tavolo.",
                           "en": "A creature touched with the stone regains all its hit points and loses curses, diseases and poisons."
                           if p["mode"] == "other" else "You regain all your hit points and lose poison; the table removes curses and diseases."})

YOUTH_USE = OnUse(
    **_after_stone(), rolls="3d10",
    message=lambda _c, _p: {"it": "Una creatura consenziente toccata ringiovanisce degli anni tirati (non sotto i 13 anni apparenti, nessuna vita in più).",
                            "en": "A willing creature touched grows younger by the years rolled (not below 13 apparent years, no longer life)."})


def _raise_dead_spell(ctx: RuleContext, _params: dict) -> None:
    """Rianimare morti per un lancio solo, senza slot e senza stare nel libro: l'incantesimo sta sulla scheda finché lo stato che lo
    autorizza dura, e il lancio lo chiude."""
    from core.db.models import Spell  # import locale: i modelli non servono al resto del catalogo
    tag = f"{STOLEN_SPELL}{uuid.uuid4().hex[:12]}"
    ctx.char.spells.append(Spell(
        character_id=ctx.char.id, name="Rianimare morti", level=5, srd_index=tag, class_id=ctx.class_row.id, school="necromancy",
        casting_time="1 ora", range_area="Contatto", duration="Istantanea", components="V, S, M", is_prepared=True, always_prepared=True))
    begin_state(ctx.char, StateSpec("restore_life", ends_on=("manual", "rest_long"), data={"stolen_spell": tag, "free_cast": tag}),
                f"{CK}.restore_life", "Ripristinare Vita")


LIFE_USE = OnUse(**_after_stone(), effect=_raise_dead_spell)
MAJOR_USE = OnUse(**_after_stone(), message=lambda _c, _p: {
    "it": "L'oggetto non magico si converte dopo 10 minuti di lavoro; il risultato lo decide il tavolo.",
    "en": "The nonmagical object converts after 10 minutes of work; the table decides the result."})

TRANSMUTATION = (
    savant("transmutation"),
    feature("minor_alchemy", CK, ED, 2, "Alchimia Minore / Minor Alchemy (Trasmutazione 2, pag. 88)", ("Alchimia Minore", "Minor Alchemy"),
            ("Procedura di 10 minuti per cubo di 30 cm: cambi un oggetto non magico fra legno, pietra, ferro, rame e argento. Dura 1 ora o finché ti concentri.",
             "A 10-minute procedure per 1-ft cube: change a nonmagical object among wood, stone, iron, copper and silver. Lasts 1 hour or while you concentrate."),
            subclass="transmutation", on_use=OnUse(cost=0, concentration=True, state=_alchemy_state)),
    feature("transmuters_stone", CK, ED, 6, "Pietra del Trasmutatore / Transmuter's Stone (Trasmutazione 6, pag. 88)",
            ("Pietra del Trasmutatore", "Transmuter's Stone"),
            ("In 8 ore crei una pietra con un beneficio: scurovisione 18 m, +3 m di velocità, TS Costituzione o resistenza a un tipo di danno. Una nuova pietra annulla la precedente.",
             "In 8 hours you make a stone with one benefit: darkvision 60 ft, +10 ft speed, Constitution saves, or resistance to a damage type. A new stone replaces the old one."),
            subclass="transmutation", on_use=STONE_USE, modifiers=STONE_MODIFIERS),
    feature("transmuters_stone_change", CK, ED, 6, "Pietra del Trasmutatore / Transmuter's Stone (Trasmutazione 6, pag. 88)",
            ("Pietra: cambia beneficio", "Stone: change benefit"),
            ("Dopo aver lanciato una trasmutazione di 1° livello o più puoi cambiare il beneficio della pietra, una volta per lancio.",
             "After casting a transmutation of 1st level or higher you can change the stone's benefit, once per cast."),
            subclass="transmutation", on_use=STONE_CHANGE_USE),
    feature("shapechanger", CK, ED, 10, "Mutaforma / Shapechanger (Trasmutazione 10, pag. 88)", ("Mutaforma", "Shapechanger"),
            ("Metamorfosi entra nel libro. La lanci su di te senza slot, solo in una bestia di GS 1 o meno. Un uso, riposo breve o lungo; con uno slot la lanci come sempre.",
             "Polymorph joins the book. Cast it on yourself with no slot, only into a beast of CR 1 or lower. One use, short or long rest; with a slot it casts as usual."),
            subclass="transmutation", uses=Uses(table={10: 1}), restoration="short_rest", book_spells=("polymorph",), free_spell="polymorph"),
    feature("master_transmuter", CK, ED, 14, "Maestro Trasmutatore / Master Transmuter (Trasmutazione 14, pag. 88)",
            ("Maestro Trasmutatore", "Master Transmuter"),
            ("Azione: consumi la pietra per uno di quattro effetti. Non puoi crearne un'altra fino al riposo lungo.",
             "Action: consume the stone for one of four effects. You cannot make another until a long rest."),
            subclass="transmutation", no_row=True,
            covered_by="le quattro righe di opzione di questo livello (OnUse con ends_state sulla pietra e stato master_transmuter_lock)"),
    feature("panacea", CK, ED, 14, "Panacea / Panacea (Trasmutazione 14, pag. 88)", ("Panacea", "Panacea"),
            ("Consumi la pietra: una creatura toccata perde maledizioni, malattie e veleni e torna a tutti i PF.",
             "Consume the stone: a creature touched loses curses, diseases and poisons and regains all hit points."),
            "action", subclass="transmutation", on_use=PANACEA_USE),
    feature("restore_youth", CK, ED, 14, "Ripristinare Giovinezza / Restore Youth (Trasmutazione 14, pag. 88)",
            ("Ripristinare Giovinezza", "Restore Youth"),
            ("Consumi la pietra: una creatura consenziente toccata ringiovanisce di 3d10 anni, non sotto i 13.",
             "Consume the stone: a willing creature touched grows 3d10 years younger, not below 13."),
            "action", subclass="transmutation", on_use=YOUTH_USE),
    feature("restore_life", CK, ED, 14, "Ripristinare Vita / Restore Life (Trasmutazione 14, pag. 88)",
            ("Ripristinare Vita", "Restore Life"),
            ("Consumi la pietra e lanci rianimare morti una volta, senza slot e senza averlo nel libro.",
             "Consume the stone and cast raise dead once, with no slot and without having it in the book."),
            "action", subclass="transmutation", on_use=LIFE_USE),
    feature("major_transformation", CK, ED, 14, "Trasformazione Maggiore / Major Transformation (Trasmutazione 14, pag. 88)",
            ("Trasformazione Maggiore", "Major Transformation"),
            ("Consumi la pietra: dopo 10 minuti converti un oggetto non magico in un altro di dimensioni e valore uguali o minori.",
             "Consume the stone: after 10 minutes you convert a nonmagical object into another of equal or lesser size and value."),
            "action", subclass="transmutation", on_use=MAJOR_USE),
)

FEATURES = (*NECROMANCY, *TRANSMUTATION)

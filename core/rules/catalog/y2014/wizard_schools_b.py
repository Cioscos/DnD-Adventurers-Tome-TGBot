"""Scuola di Divinazione e Scuola di Evocazione (conjuration) del Mago 2014. Valori dalla scheda del Mago."""
from __future__ import annotations

from core.rules.catalog._common import feature
from core.rules.catalog.y2014.wizard_common import CK, ED, savant
from core.rules.schools import normalize_school
from core.rules.types import Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, UseChoice, Uses, UseText

# ---------------------------------------------------------------------------
# Scuola di Divinazione
# ---------------------------------------------------------------------------

PORTENT = RollOptionSpec(
    key=f"{CK}.portent", phase="before", rolls=("attack", "skill", "save", "initiative"), once_per_turn=True, replace_die=True,
    label={"it": "Portento: sostituisci il d20 con uno dei dadi di preveggenza",
           "en": "Portent: replace the d20 with one of your foretelling dice"})


def _casting_level(ctx: RuleContext) -> int:
    return ctx.casting_level or (ctx.spell.level if ctx.spell is not None else 0)


def _recoverable(ctx: RuleContext) -> list[int]:
    """Divinazione Esperta: gli slot spesi di livello inferiore all'incantesimo e al massimo di 5°."""
    from core.rules.roll_options import spent_levels  # import locale: roll_options usa il catalogo
    if ctx.spell is None or normalize_school(ctx.spell.school) != "divination" or _casting_level(ctx) < 2:
        return []
    return [level for level in spent_levels(ctx.char) if level < _casting_level(ctx) and level <= 5]


EXPERT_DIVINATION = RollOptionSpec(
    key=f"{CK}.expert_divination", phase="before", rolls=("cast",), requires_input="recover", recover_levels=_recoverable,
    available=lambda c: bool(_recoverable(c)),
    label={"it": "Divinazione Esperta: recupera uno slot speso di livello inferiore (al massimo 5°)",
           "en": "Expert Divination: regain a spent slot of a lower level (5th at most)"})

THIRD_EYE_OPTIONS = {
    "greater_comprehension": ("Comprensione Superiore", "Greater Comprehension"), "darkvision": ("Scurovisione", "Darkvision"),
    "see_invisibility": ("Vedere Invisibilità", "See Invisibility"), "ethereal_sight": ("Vista Eterea", "Ethereal Sight")}


def _third_eye(option: str):
    return lambda ctx: any(s.get("key") == "third_eye" and (s.get("data") or {}).get("option") == option for s in ctx.char.active_states or [])


THIRD_EYE_USE = OnUse(
    slot="action",
    state=lambda _c, p: StateSpec("third_eye", ends_on=("rest_short", "rest_long", "incapacitated", "manual"), data={"option": p["option"]}),
    choices=(UseChoice("option", {"it": "Beneficio", "en": "Benefit"}, lambda _c: list(THIRD_EYE_OPTIONS),
                       lambda k: {"it": THIRD_EYE_OPTIONS[k][0], "en": THIRD_EYE_OPTIONS[k][1]}),))
THIRD_EYE_SENSES = (
    Modifier("sense:darkvision", 60, when=_third_eye("darkvision"), source=f"feature:{CK}.third_eye"),
    Modifier("sense:see_invisible", 10, when=_third_eye("see_invisibility"), source=f"feature:{CK}.third_eye"),
    Modifier("sense:ethereal_sight", 60, when=_third_eye("ethereal_sight"), source=f"feature:{CK}.third_eye"))


def _option_row(key: str, title: str, name: tuple[str, str], summary: tuple[str, str]):
    return feature(key, CK, ED, 10, title, name, summary, subclass="divination", no_row=True,
                   covered_by="UseChoice option di Terzo Occhio (OnUse) e i Modifier di senso della stessa riga")


DIVINATION = (
    savant("divination"),
    feature("portent", CK, ED, 2, "Portento / Portent (Divinazione 2, pag. 86)", ("Portento", "Portent"),
            ("Alla fine di un riposo lungo tiri 2d20 (3 dal 14°) e li registri: ognuno può sostituire un tiro per colpire, TS o prova, una volta per turno.",
             "At the end of a long rest you roll 2d20 (3 from 14th) and record them: each can replace an attack roll, save or check, once per turn."),
            subclass="divination", roll_options=(PORTENT,), long_rest_dice=(f"{CK}.portent", lambda c: 3 if c.class_level >= 14 else 2)),
    feature("expert_divination", CK, ED, 6, "Divinazione Esperta / Expert Divination (Divinazione 6, pag. 86)",
            ("Divinazione Esperta", "Expert Divination"),
            ("Lanciando una divinazione di 2° livello o più recuperi uno slot speso di livello inferiore, al massimo di 5°.",
             "When you cast a divination of 2nd level or higher you regain a spent slot of a lower level, 5th at most."),
            subclass="divination", roll_options=(EXPERT_DIVINATION,)),
    feature("third_eye", CK, ED, 10, "Terzo Occhio / The Third Eye (Divinazione 10, pag. 86)", ("Terzo Occhio", "The Third Eye"),
            ("Azione: scegli un beneficio fino a incapacitazione o riposo: leggere ogni linguaggio, scurovisione 18 m, vedere invisibilità 3 m, Piano Etereo 18 m. Un uso, riposo breve.",
             "Action: pick a benefit until incapacitated or a rest: read any language, darkvision 60 ft, see invisibility 10 ft, Ethereal Plane 60 ft. One use, short rest."),
            "action", subclass="divination", uses=Uses(table={10: 1}), restoration="short_rest", on_use=THIRD_EYE_USE,
            modifiers=THIRD_EYE_SENSES),
    _option_row("greater_comprehension", "Comprensione Superiore / Greater Comprehension (Divinazione 10, pag. 86)",
                ("Comprensione Superiore", "Greater Comprehension"),
                ("Opzione di Terzo Occhio: leggi qualsiasi linguaggio.", "Third Eye option: you read any language.")),
    _option_row("darkvision", "Scurovisione / Darkvision (Divinazione 10, pag. 86)", ("Scurovisione", "Darkvision"),
                ("Opzione di Terzo Occhio: scurovisione entro 18 m.", "Third Eye option: darkvision out to 60 ft.")),
    _option_row("see_invisibility", "Vedere Invisibilità / See Invisibility (Divinazione 10, pag. 86)", ("Vedere Invisibilità", "See Invisibility"),
                ("Opzione di Terzo Occhio: vedi creature e oggetti invisibili entro 3 m.",
                 "Third Eye option: you see invisible creatures and objects within 10 ft.")),
    _option_row("ethereal_sight", "Vista Eterea / Ethereal Sight (Divinazione 10, pag. 86)", ("Vista Eterea", "Ethereal Sight"),
                ("Opzione di Terzo Occhio: vedi sul Piano Etereo entro 18 m.", "Third Eye option: you see into the Ethereal Plane out to 60 ft.")),
    feature("greater_portent", CK, ED, 14, "Portento Superiore / Greater Portent (Divinazione 14, pag. 86)",
            ("Portento Superiore", "Greater Portent"),
            ("Portento registra tre d20 invece di due.", "Portent records three d20s instead of two."),
            subclass="divination", passive=True),
)

# ---------------------------------------------------------------------------
# Scuola di Evocazione (conjuration)
# ---------------------------------------------------------------------------

MINOR_USE = OnUse(
    cost=0, slot="action",
    texts=(UseText("object", {"it": "Oggetto creato", "en": "Object created"}, max_len=60),),
    state=lambda _c, p: StateSpec("minor_conjuration", rounds=600, ends_on=("manual",), data={"object": str(p["object"]).strip()}))

CONJURATION = (
    savant("conjuration"),
    feature("minor_conjuration", CK, ED, 2, "Evocazione Minore / Minor Conjuration (Evocazione 2, pag. 86)",
            ("Evocazione Minore", "Minor Conjuration"),
            ("Azione: crei un oggetto non magico (max 90 cm, 5 kg) entro 3 m. Dura 1 ora, finché non lo ricrei o non subisci danni; emette luce fioca.",
             "Action: you create a nonmagical object (max 3 ft, 10 lb) within 10 ft. It lasts 1 hour, until you use this again or take damage; it sheds dim light."),
            "action", subclass="conjuration", on_use=MINOR_USE),
    feature("benign_transposition", CK, ED, 6, "Trasposizione Benevola / Benign Transposition (Evocazione 6, pag. 86)",
            ("Trasposizione Benevola", "Benign Transposition"),
            ("Azione: ti teletrasporti fino a 9 m o scambi posto con una creatura consenziente. Un uso: riposo lungo, o lanciando un'evocazione di 1° livello o più.",
             "Action: teleport up to 30 ft or swap places with a willing creature. One use: long rest, or casting a conjuration of 1st level or higher."),
            "action", subclass="conjuration", uses=Uses(table={6: 1}), restoration="long_rest", on_use=OnUse(slot="action")),
    feature("focused_conjuration", CK, ED, 10, "Evocazione Focalizzata / Focused Conjuration (Evocazione 10, pag. 86)",
            ("Evocazione Focalizzata", "Focused Conjuration"),
            ("Il danno non interrompe la tua concentrazione su un incantesimo di evocazione: niente TS Costituzione.",
             "Damage cannot break your concentration on a conjuration spell: no Constitution save."),
            subclass="conjuration", passive=True, concentration_safe_schools=("conjuration",)),
    feature("durable_summons", CK, ED, 14, "Evocazioni Perduranti / Durable Summons (Evocazione 14, pag. 86)",
            ("Evocazioni Perduranti", "Durable Summons"),
            ("Le creature evocate o create con un incantesimo di evocazione hanno 30 PF temporanei.",
             "Creatures you summon or create with a conjuration spell have 30 temporary hit points."),
            subclass="conjuration", passive=True),
)

FEATURES = (*DIVINATION, *CONJURATION)

"""Suppliche Occulte del Warlock 2014: le 33 opzioni della scelta ``invocations``.

Valori dalla scheda ``docs/superpowers/rules/2014/classes/warlock.md``; i testi sono nostri, mai quelli del manuale.
Ogni supplica è una riga con ``option_group="invocations"``; i prerequisiti (livello da warlock, Dono del Patto,
trucchetto deflagrazione occulta) filtrano l'elenco della scelta in ``available_invocations``.
Gli incantesimi a volontà sono ``granted_spells`` + ``at_will_spells``; quelli «una volta per riposo lungo con uno slot di
Patto» sono ``pact_spell`` (il lancio spende l'uso, vedi ``core.rules.pact_casts``).
"""
from __future__ import annotations

from typing import Any

from core.rules.catalog._common import feature, state_on
from core.rules.states import begin_state
from core.rules.types import (
    ChoiceSpec, FeatureSpec, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, TargetEffect, UseChoice, Uses,
)

ED, CK = "2014", "warlock"
INVOCATIONS = "invocations"
BOON_GROUP = "pact_boon"
BLAST = "eldritch-blast"
BLAST_NAMES = ("deflagrazione occulta", "eldritch blast")
PACT_WEAPON = "pact_weapon"  # item_metadata: l'arma creata dal Patto della Lama
INVISIBLE_UNTIL_ACT = "one_with_shadows"


def is_blast(spell: Any) -> bool:
    """Deflagrazione occulta: dallo `srd_index` o, per un incantesimo scritto a mano, dal nome."""
    return spell is not None and ((getattr(spell, "srd_index", None) or "") == BLAST
                                  or (getattr(spell, "name", None) or "").strip().lower() in BLAST_NAMES)


def _mod(ctx: RuleContext, ability: str) -> int:
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    return effective_ability_mod(ctx.char, ability)


def _say(it: str, en: str):
    return lambda _ctx, _inputs: {"it": it, "en": en}


def _is_pact_weapon(ctx: RuleContext) -> bool:
    from core.game.item_bonuses import item_meta  # import locale
    return ctx.item is not None and bool(item_meta(ctx.item).get(PACT_WEAPON))


# ---------------------------------------------------------------------------
# Effetti delle suppliche
# ---------------------------------------------------------------------------

def _beams(ctx: RuleContext) -> int:
    from core.game.stats import cantrip_dice_multiplier  # import locale
    return cantrip_dice_multiplier(ctx.char.total_level)


AGONIZING = Modifier("damage", lambda c: _mod(c, "charisma") * _beams(c), when=lambda c: is_blast(c.spell),
                     source=f"feature:{CK}.agonizing_blast")

REPELLING = RollOptionSpec(
    key=f"{CK}.repelling_blast", phase="after_hit", rolls=("attack",), available=lambda c: is_blast(c.spell),
    label={"it": "Deflagrazione Respingente: spingi il bersaglio fino a 3 m in linea retta lontano da te",
           "en": "Repelling Blast: push the target up to 10 ft straight away from you"},
    effect=_say("Il bersaglio è spinto fino a 3 m in linea retta lontano da te.", "The target is pushed up to 10 ft straight away from you."),
    target_effect=lambda _c, _i: TargetEffect(note="repelling_blast"))

LIFEDRINKER = RollOptionSpec(
    key=f"{CK}.lifedrinker", phase="after_hit", rolls=("attack",), available=_is_pact_weapon,
    bonus=lambda c, _i: max(1, _mod(c, "charisma")),
    label={"it": "Succhiavita: danni necrotici extra pari al Carisma (minimo 1) con l'arma del patto",
           "en": "Lifedrinker: extra necrotic damage equal to your Charisma modifier (minimum 1) with the pact weapon"},
    effect=lambda c, _i: {"it": f"Danni necrotici extra: {max(1, _mod(c, 'charisma'))}.",
                          "en": f"Extra necrotic damage: {max(1, _mod(c, 'charisma'))}."})


def _mage_armor_cast(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    """Armatura magica dura 8 ore: lo stato porta la CA 13 + Destrezza finché non indossi un'armatura o riposi a lungo."""
    begin_state(ctx.char, StateSpec("mage_armor", rounds=4800, ends_on=("rest_long", "manual")), f"{CK}.armor_of_shadows",
                "Armatura magica")


MAGE_ARMOR_CAST = RollOptionSpec(
    key=f"{CK}.armor_of_shadows_cast", phase="before", rolls=("cast",), automatic=True,
    available=lambda c: c.spell is not None and (c.spell.srd_index or "") == "mage-armor", on_confirm=_mage_armor_cast,
    label={"it": "Armatura delle Ombre: la CA diventa 13 + Destrezza per 8 ore", "en": "Armor of Shadows: your AC becomes 13 + Dexterity for 8 hours"})


def _mage_armor_bonus(ctx: RuleContext) -> int:
    from core.game.stats import computed_base_ac  # import locale
    return max(0, 13 + _mod(ctx, "dexterity") - computed_base_ac(ctx.char))


def _no_armor(ctx: RuleContext) -> bool:
    return not any(i.is_equipped and i.item_type == "armor" for i in ctx.char.items or [])


MAGE_ARMOR_AC = Modifier("ac", _mage_armor_bonus, when=lambda c: state_on(c, "mage_armor") and _no_armor(c) and not state_on(c, "spell:mage_armor"),  # il catalogo degli incantesimi lo conta già
                         source=f"feature:{CK}.armor_of_shadows")

CHAINS_CAST = RollOptionSpec(
    key=f"{CK}.chains_of_carceri_cast", phase="before", rolls=("cast",),
    available=lambda c: c.spell is not None and (c.spell.srd_index or "") == "hold-monster",
    label={"it": "Catene di Carceri: il bersaglio è un celestiale, un immondo o un elementale che non hai già preso di mira dall'ultimo riposo lungo?",
           "en": "Chains of Carceri: is the target a celestial, fiend or elemental you have not targeted since your last long rest?"},
    effect=_say("Solo contro celestiali, immondi ed elementali; la stessa creatura non può esserne di nuovo bersaglio finché non completi un riposo lungo.",
                "Only against celestials, fiends and elementals; the same creature cannot be targeted again until you finish a long rest."))

VIGOR_USE = OnUse(slot="action", rolls="1d4", temp_hp=lambda _c, rolled: rolled + 4)


def _shadows_state(_ctx: RuleContext, _params: dict) -> StateSpec:
    return StateSpec(INVISIBLE_UNTIL_ACT, condition="invisible", ends_on=("attack", "cast", "rest_short", "rest_long", "manual"),
                     data={"others": [f"{CK}.one_with_shadows"]})


SHADOWS_USE = OnUse(
    slot="action", state=_shadows_state,
    choices=(UseChoice("light", {"it": "Dove sei", "en": "Where you are"}, lambda _c: ["dim", "dark"],
                       lambda k: {"it": "In penombra", "en": "In dim light"} if k == "dim" else {"it": "Al buio", "en": "In darkness"}),))


def _gaze_state(key: str, condition: str):
    return StateSpec(key, condition=condition, ends_on=("new_turn", "turn_end_counted", "rest_short", "rest_long", "manual"),
                     data={"skip_new_turns": 1, "others": [f"{CK}.gaze_of_two_minds"]})


def _gaze_deaf(_session: Any, ctx: RuleContext, _params: dict) -> None:
    begin_state(ctx.char, _gaze_state("gaze_of_two_minds_deaf", "deafened"), f"{CK}.gaze_of_two_minds", "Sguardo delle Due Menti")


def _gaze_effect(ctx: RuleContext, params: dict) -> None:
    _gaze_deaf(None, ctx, params)


GAZE_USE = OnUse(slot="action", state=lambda _c, _p: _gaze_state("gaze_of_two_minds", "blinded"), effect=_gaze_effect)


# ---------------------------------------------------------------------------
# Elenco
# ---------------------------------------------------------------------------

def _inv(key: str, it: str, en: str, suffix: str, level: int, summary: tuple[str, str], *, boon: str | None = None,
         blast: bool = False, action_type: str | None = None, **kw: Any) -> tuple[FeatureSpec, tuple[str, int, str | None, bool]]:
    """La riga della supplica e i suoi prerequisiti ``(chiave, livello, Dono del Patto, richiede il trucchetto)``."""
    spec = feature(key, CK, ED, 2, f"{it} / {en} ({suffix})", (it, en), summary, action_type,
                   option_group=INVOCATIONS, option_key=key, **kw)
    return spec, (key, level, boon, blast)


def _spell_summary(spell_it: str, spell_en: str, mode: str, **_: Any) -> tuple[str, str]:
    return {
        "will": (f"Lanci {spell_it} a volontà, senza slot né componenti materiali.",
                 f"You cast {spell_en} at will, with no slot and no material components."),
        "will_self": (f"Lanci {spell_it} su te stesso a volontà, senza slot né componenti materiali.",
                      f"You cast {spell_en} on yourself at will, with no slot and no material components."),
        "slot": (f"Lanci {spell_it} una volta con uno slot di Patto; l'uso torna con un riposo lungo.",
                 f"You cast {spell_en} once using a Pact slot; the use returns on a long rest."),
    }[mode]


def _will(key: str, it: str, en: str, suffix: str, level: int, spell: str, spell_it: str, spell_en: str, *, self_only: bool = False,
          **kw: Any):
    return _inv(key, it, en, suffix, level, _spell_summary(spell_it, spell_en, "will_self" if self_only else "will"),
                granted_spells=(spell,), at_will_spells=(spell,), **kw)


def _once(key: str, it: str, en: str, suffix: str, level: int, spell: str, spell_it: str, spell_en: str):
    return _inv(key, it, en, suffix, level, _spell_summary(spell_it, spell_en, "slot"), granted_spells=(spell,), pact_spell=spell,
                uses=Uses(table={2: 1}), restoration="long_rest")


_ROWS = (
    _will("armor_of_shadows", "Armatura delle Ombre", "Armor of Shadows", "Suppliche Occulte, pag. 118", 2, "mage-armor",
          "armatura magica", "mage armor", self_only=True, roll_options=(MAGE_ARMOR_CAST,), modifiers=(MAGE_ARMOR_AC,)),
    _will("otherworldly_leap", "Balzo Ultraterreno", "Otherworldly Leap", "Suppliche Occulte, livello 9, pag. 118", 9, "jump",
          "saltare", "jump", self_only=True),
    _will("chains_of_carceri", "Catene di Carceri", "Chains of Carceri", "Suppliche Occulte, livello 15, Patto della Catena, pag. 118", 15,
          "hold-monster", "bloccare mostri", "hold monster", roll_options=(CHAINS_CAST,), boon="chain"),
    _inv("agonizing_blast", "Deflagrazione Agonizzante", "Agonizing Blast", "Suppliche Occulte, trucchetto deflagrazione occulta, pag. 118", 2,
         ("Con deflagrazione occulta aggiungi il Carisma ai danni di ogni raggio che colpisce.",
          "With eldritch blast you add your Charisma modifier to the damage of each beam that hits."),
         blast=True, modifiers=(AGONIZING,)),
    _inv("repelling_blast", "Deflagrazione Respingente", "Repelling Blast", "Suppliche Occulte, trucchetto deflagrazione occulta, pag. 118", 2,
         ("Quando colpisci con deflagrazione occulta puoi spingere la creatura fino a 3 m in linea retta lontano da te.",
          "When you hit with eldritch blast you can push the creature up to 10 ft straight away from you."),
         blast=True, roll_options=(REPELLING,)),
    _once("mire_the_mind", "Fardello Mentale", "Mire the Mind", "Suppliche Occulte, livello 5, pag. 118", 5, "slow", "lentezza", "slow"),
    _inv("beguiling_influence", "Influenza Seducente", "Beguiling Influence", "Suppliche Occulte, pag. 118", 2,
         ("Hai competenza in Inganno e Persuasione.", "You have proficiency in Deception and Persuasion."),
         proficiency_grants={"skills": ("deception", "persuasion")}),
    _once("thief_of_five_fates", "Ladro dei Cinque Fati", "Thief of Five Fates", "Suppliche Occulte, pag. 118", 2, "bane", "anatema", "bane"),
    _inv("thirsting_blade", "Lama Assetata", "Thirsting Blade", "Suppliche Occulte, livello 5, Patto della Lama, pag. 118", 5,
         ("Con l'azione di Attacco attacchi due volte con l'arma del patto. Non si somma ad Attacco Extra.",
          "With the Attack action you attack twice with the pact weapon. It does not stack with Extra Attack."),
         boon="blade", attacks_with_pact_weapon=2),
    _inv("eldritch_spear", "Lancia Occulta", "Eldritch Spear", "Suppliche Occulte, trucchetto deflagrazione occulta, pag. 118", 2,
         ("La gittata di deflagrazione occulta diventa 90 m.", "The range of eldritch blast becomes 300 ft."),
         blast=True, spell_range=((BLAST, *BLAST_NAMES), "90 m")),
    _inv("book_of_ancient_secrets", "Libro degli Antichi Segreti", "Book of Ancient Secrets", "Suppliche Occulte, Patto del Tomo, pag. 118", 2,
         ("Trascrivi nel Libro delle Ombre due rituali di 1° livello di qualsiasi lista: fuori dai conosciuti. Impugnando il libro lanci come rituale anche i tuoi rituali da warlock.",
          "Inscribe two 1st-level rituals from any list in your Book of Shadows, outside your known spells. While holding it you also cast your warlock rituals as rituals."),
         boon="tome", ritual_casting=True,
         choices=(ChoiceSpec(group="book_rituals", levels={2: 2}, options=lambda _c: [], spell_pick="extra", spell_level=1, spell_exact=True,
                             spell_ritual=True),)),
    _will("beast_speech", "Lingue delle Bestie", "Beast Speech", "Suppliche Occulte, pag. 119", 2, "speak-with-animals",
          "parlare con gli animali", "speak with animals"),
    _will("master_of_myriad_forms", "Maestro di Mille Forme", "Master of Myriad Forms", "Suppliche Occulte, livello 15, pag. 119", 15,
          "alter-self", "alterare se stessi", "alter self"),
    _will("mask_of_many_faces", "Maschera dei Molti Volti", "Mask of Many Faces", "Suppliche Occulte, pag. 119", 2, "disguise-self",
          "camuffare se stesso", "disguise self", self_only=True),
    _inv("eyes_of_the_rune_keeper", "Occhi del Custode delle Rune", "Eyes of the Rune Keeper", "Suppliche Occulte, pag. 119", 2,
         ("Puoi leggere ogni forma di scrittura.", "You can read all writing."), passive=True),
    _once("dreadful_word", "Parola Temibile", "Dreadful Word", "Suppliche Occulte, livello 7, pag. 119", 7, "confusion", "confusione", "confusion"),
    _will("ascendant_step", "Passo Ascendente", "Ascendant Step", "Suppliche Occulte, livello 9, pag. 119", 9, "levitate",
          "levitazione", "levitate", self_only=True),
    _once("sign_of_ill_omen", "Presagio di Sventura", "Sign of Ill Omen", "Suppliche Occulte, livello 5, pag. 119", 5, "bestow-curse",
          "scagliare maledizione", "bestow curse"),
    _once("sculptor_of_flesh", "Scultore della Carne", "Sculptor of Flesh", "Suppliche Occulte, livello 7, pag. 119", 7, "polymorph",
          "metamorfosi", "polymorph"),
    _once("minions_of_chaos", "Servitori del Caos", "Minions of Chaos", "Suppliche Occulte, livello 9, pag. 119", 9, "conjure-elemental",
          "evocare elementale", "conjure elemental"),
    _inv("gaze_of_two_minds", "Sguardo delle Due Menti", "Gaze of Two Minds", "Suppliche Occulte, pag. 119", 2,
         ("Azione: percepisci con i sensi di un umanoide consenziente toccato fino alla fine del tuo prossimo turno; sei cieco e sordo verso ciò che ti circonda. Rinnovabile con un'azione.",
          "Action: you perceive through a touched willing humanoid's senses until the end of your next turn; you are blind and deaf to your surroundings. Renewable with an action."),
         action_type="action", on_use=GAZE_USE),
    _inv("lifedrinker", "Succhiavita", "Lifedrinker", "Suppliche Occulte, livello 12, Patto della Lama, pag. 119", 12,
         ("Quando colpisci con l'arma del patto infliggi danni necrotici extra pari al Carisma (minimo 1).",
          "When you hit with the pact weapon you deal extra necrotic damage equal to your Charisma modifier (minimum 1)."),
         boon="blade", roll_options=(LIFEDRINKER,)),
    _will("whispers_of_the_grave", "Sussurri dalla Tomba", "Whispers of the Grave", "Suppliche Occulte, livello 9, pag. 119", 9,
          "speak-with-dead", "parlare con i morti", "speak with dead"),
    _once("bewitching_whispers", "Sussurri Stregati", "Bewitching Whispers", "Suppliche Occulte, livello 7, pag. 119", 7, "compulsion",
          "compulsione", "compulsion"),
    _inv("one_with_shadows", "Tutt'Uno con le Ombre", "One with Shadows", "Suppliche Occulte, livello 5, pag. 119", 5,
         ("Azione, in penombra o al buio: sei invisibile finché resti fermo e non compi azioni o reazioni. Dichiari tu la luce.",
          "Action, in dim light or darkness: you are invisible while you stay still and take no actions or reactions. You declare the light."),
         action_type="action", on_use=SHADOWS_USE),
    _inv("fiendish_vigor", "Vigore Immondo", "Fiendish Vigor", "Suppliche Occulte, pag. 119", 2,
         ("Azione: lanci vita falsata su di te come incantesimo di 1° livello, senza slot: ottieni 1d4 + 4 PF temporanei, se più di quelli che hai.",
          "Action: you cast false life on yourself as a 1st-level spell, with no slot: you gain 1d4 + 4 temporary hit points if higher than yours."),
         action_type="action", on_use=VIGOR_USE),
    _will("visions_of_distant_realms", "Visione dei Reami Lontani", "Visions of Distant Realms",
          "Suppliche Occulte, livello 15, pag. 119", 15, "arcane-eye", "occhio arcano", "arcane eye"),
    _will("misty_visions", "Visioni Velate", "Misty Visions", "Suppliche Occulte, pag. 119", 2, "silent-image",
          "immagine silenziosa", "silent image", self_only=False),
    _inv("devils_sight", "Vista del Diavolo", "Devil's Sight", "Suppliche Occulte, pag. 119", 2,
         ("Vedi normalmente nell'oscurità, magica e non, fino a 36 m.", "You see normally in darkness, both magical and nonmagical, up to 120 ft."),
         modifiers=(Modifier("sense:devils_sight", 120, source=f"feature:{CK}.devils_sight"),), passive=True),
    _will("eldritch_sight", "Vista dell'Occulto", "Eldritch Sight", "Suppliche Occulte, pag. 119", 2, "detect-magic",
          "individuazione del magico", "detect magic"),
    _inv("witch_sight", "Vista Stregata", "Witch Sight", "Suppliche Occulte, livello 15, pag. 119", 15,
         ("Vedi la vera forma di mutaforma e creature celate da illusione o trasmutazione entro 9 m in linea di vista.",
          "You see the true form of shapechangers and creatures concealed by illusion or transmutation within 30 ft in line of sight."),
         passive=True),
    _inv("voice_of_the_chain_master", "Voce del Signore delle Catene", "Voice of the Chain Master",
         "Suppliche Occulte, Patto della Catena, pag. 119", 2,
         ("Comunichi telepaticamente con il famiglio e percepisci con i suoi sensi sullo stesso piano; puoi parlare tramite lui.",
          "You communicate telepathically with your familiar and perceive through its senses on the same plane; you can speak through it."),
         boon="chain", passive=True),
)

INVOCATION_ROWS: tuple[FeatureSpec, ...] = tuple(spec for spec, _req in _ROWS)
PREREQUISITES = {key: (level, boon, blast) for _spec, (key, level, boon, blast) in _ROWS}

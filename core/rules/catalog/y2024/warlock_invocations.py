"""Suppliche Occulte del Warlock 2024 (Task 41, parte A): le opzioni del gruppo ``invocations``.

Valori da ``docs/superpowers/rules/2024/classes/warlock.md``; i testi sono nostri, mai quelli del manuale. Il 2024 mette i Patti fra le
suppliche (Lama, Catena, Tomo) e alcune suppliche ne richiedono un'altra: ``REQUIRES``. Le suppliche Ripetibili (Deflagrazione Agonizzante,
Lancia Occulta, Deflagrazione Respingente) hanno una riga per ogni trucchetto idoneo, con chiave ``<supplica>__<trucchetto>``: la
scelta del giocatore è la riga. Nota per la parte B: ``PACT_WEAPON`` (metadato dell'arma del patto) e ``is_pact_weapon(ctx)``.
"""
from __future__ import annotations

import json
import random
from typing import Any

from core.rules.catalog._common import feature, state_on
from core.rules.catalog.y2014.paladin import _drops_to_zero
from core.rules.catalog.y2014.warlock import PACT_WEAPONS, _create_pact_weapon, _is_pact, _weapon_label
from core.rules.catalog.y2014.warlock_invocations import (
    MAGE_ARMOR_AC, MAGE_ARMOR_CAST, PACT_WEAPON, _beams, _is_pact_weapon, _mod, _say,
)
from core.rules.types import (
    ChoiceSpec, Cost, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, TargetEffect, UseChoice, Uses,
)

ED, CK = "2024", "warlock"
INVOCATIONS = "invocations"
is_pact_weapon = _is_pact_weapon
# trucchetti da warlock che infliggono danno: srd_index -> (nome it, nome en, ha un tiro per colpire, gittata di almeno 3 m)
CANTRIPS: dict[str, tuple[str, str, bool, bool]] = {
    "eldritch-blast": ("Deflagrazione Occulta", "Eldritch Blast", True, True), "chill-touch": ("Tocco Gelido", "Chill Touch", True, True),
    "poison-spray": ("Spruzzo Velenoso", "Poison Spray", False, True), "thunderclap": ("Fragore di Tuono", "Thunderclap", False, False),
    "toll-the-dead": ("Rintocco dei Morti", "Toll the Dead", False, True), "mind-sliver": ("Scheggia Mentale", "Mind Sliver", False, True),
    "create-bonfire": ("Creare Falò", "Create Bonfire", False, True),
}
# supplica -> supplica che deve essere già scelta
REQUIRES = {"devouring_blade": "thirsting_blade", "eldritch_smite": "pact_of_the_blade", "thirsting_blade": "pact_of_the_blade",
            "lifedrinker": "pact_of_the_blade", "gift_of_the_protectors": "pact_of_the_tome",
            "investment_of_the_chain_master": "pact_of_the_chain"}
DAMAGE_TYPES = ("necrotic", "psychic", "radiant")
_TYPE_LABELS = {"necrotic": ("necrotici", "necrotic"), "psychic": ("psichici", "psychic"), "radiant": ("radiosi", "radiant")}


def _names(index: str) -> set[str]:
    it, en, *_ = CANTRIPS[index]
    return {index, it.lower(), en.lower()}


def is_cantrip(spell: Any, index: str) -> bool:
    """L'incantesimo è questo trucchetto: dallo `srd_index` o, se scritto a mano, dal nome."""
    return spell is not None and ((getattr(spell, "srd_index", None) or "").lower() == index
                                  or (getattr(spell, "name", None) or "").strip().lower() in _names(index))


def knows_cantrip(char: Any, index: str) -> bool:
    return any(is_cantrip(s, index) and s.level == 0 for s in char.spells or [])


def _slug(index: str) -> str:
    return index.replace("-", "_")


def _chosen(ctx: RuleContext) -> list[str]:
    return list((getattr(ctx.class_row, "options", None) or {}).get(INVOCATIONS, []))


# ---------------------------------------------------------------------------
# Effetti
# ---------------------------------------------------------------------------

def _agonizing(index: str, key: str) -> Modifier:
    return Modifier("damage", lambda c: _mod(c, "charisma") * _beams(c), when=lambda c: is_cantrip(c.spell, index),
                    source=f"feature:{CK}.{key}")


def _repelling(index: str, key: str) -> RollOptionSpec:
    return RollOptionSpec(
        key=f"{CK}.{key}", phase="after_hit", rolls=("attack",), available=lambda c: is_cantrip(c.spell, index),
        label={"it": "Deflagrazione Respingente: spingi il bersaglio (Grande o più piccolo) fino a 3 m in linea retta lontano da te",
               "en": "Repelling Blast: push the target (Large or smaller) up to 10 ft straight away from you"},
        effect=_say("Il bersaglio, se Grande o più piccolo, è spinto fino a 3 m in linea retta lontano da te.",
                    "The target, if Large or smaller, is pushed up to 10 ft straight away from you."),
        target_effect=lambda _c, _i: TargetEffect(note="repelling_blast"))


def _smite_dice(_ctx: RuleContext, inputs: dict) -> str:
    """1d8 più 1d8 per livello dello slot di Patto speso."""
    return f"{1 + int(inputs.get('slot_level') or 1)}d8"


SMITE = RollOptionSpec(
    key=f"{CK}.eldritch_smite", phase="after_hit", rolls=("attack",), requires_input="slot", cost=Cost(spell_slot_min=1, pact_only=True),
    once_per_turn=True, extra_dice=_smite_dice, available=_is_pact_weapon, target_effect=lambda _c, _i: TargetEffect(condition="prone"),
    label={"it": "Fendente Occulto: spendi uno slot di Patto, 1d8 + 1d8 per livello dello slot di danni da forza (una volta per turno)",
           "en": "Eldritch Smite: spend a Pact slot, 1d8 + 1d8 per slot level of force damage (once per turn)"},
    effect=_say("I dadi in più sono danni da forza. Se il bersaglio è Enorme o più piccolo puoi renderlo Prono.",
                "The extra dice are force damage. If the target is Huge or smaller you can knock it Prone."))


def _hit_die_row(ctx: RuleContext) -> Any:
    """La classe da cui spendere un Dado Vita: la propria se ne ha, altrimenti un'altra."""
    rows = [ctx.class_row, *(ctx.char.classes or [])]
    return next((r for r in rows if r is not None and (r.hit_dice_used or 0) < r.level), None)


def _drink_hit_die(ctx: RuleContext, given: dict) -> int:
    """Spende un Dado Vita e dà la cura: il tiro più Costituzione, minimo 1 (2024). Il tiro resta in ``given`` per l'esito."""
    row = _hit_die_row(ctx)
    given["rolled"] = random.randint(1, row.hit_die or 8)
    row.hit_dice_used = (row.hit_dice_used or 0) + 1
    given["healed"] = max(1, given["rolled"] + _mod(ctx, "constitution"))
    return given["healed"]


def _lifedrinker(damage_type: str, hit_die: bool = False) -> RollOptionSpec:
    it, en = _TYPE_LABELS[damage_type]
    plain = {"it": f"1d6 danni {it} in più. Puoi spendere un Dado Vita con l'altra opzione di Succhiavita.",
             "en": f"Extra 1d6 {en} damage. You can spend a Hit Die with the other Lifedrinker option."}
    return RollOptionSpec(
        key=f"{CK}.lifedrinker_{damage_type}" + ("_hd" if hit_die else ""), phase="after_hit", rolls=("attack",), group=f"{CK}.lifedrinker",
        once_per_turn=True, extra_dice=lambda _c, _i: "1d6",
        available=(lambda c: _is_pact_weapon(c) and _hit_die_row(c) is not None) if hit_die else _is_pact_weapon,
        self_heal=_drink_hit_die if hit_die else None,
        label={"it": f"Succhiavita: 1d6 danni {it} in più con l'arma del patto" + (", e spendi un Dado Vita per curarti" if hit_die else "") + " (una volta per turno)",
               "en": f"Lifedrinker: extra 1d6 {en} damage with the pact weapon" + (", and spend a Hit Die to heal" if hit_die else "") + " (once per turn)"},
        effect=(lambda _c, g: {"it": f"1d6 danni {it} in più. Dado Vita speso: tiro {g.get('rolled')} + Costituzione = {g.get('healed')} PF recuperati.",
                               "en": f"Extra 1d6 {en} damage. Hit Die spent: roll {g.get('rolled')} + Constitution = {g.get('healed')} hit points regained."})
        if hit_die else (lambda _c, _i: plain))


BOUND = "pact_bound"  # item_metadata: un'arma magica già posseduta, legata (non evocata)
ORIGINAL_TYPE = "pact_original_damage_type"


def _bindable(ctx: RuleContext) -> list[str]:
    """Armi da mischia magiche dell'inventario: si legano invece di evocarne una (``bind:<id>``)."""
    from core.game.item_bonuses import item_meta  # import locale
    out = []
    for item in ctx.char.items:
        meta = item_meta(item)
        magic = int(meta.get("magic_bonus") or 0) > 0 or bool(meta.get("requires_attunement") or meta.get("magical"))
        if item.item_type == "weapon" and magic and meta.get("weapon_type", "melee") == "melee":
            out.append(f"bind:{item.id}")
    return out


def _release_bound(char: Any) -> None:
    """Il legame con un'arma vera termina: torna com'era, non si cancella (l'arma evocata la toglie ``_create_pact_weapon``)."""
    from core.game.item_bonuses import item_meta  # import locale
    for item in char.items:
        meta = dict(item_meta(item))
        if meta.get(BOUND):
            original = meta.pop(ORIGINAL_TYPE, None)
            meta.pop(PACT_WEAPON, None)
            meta.pop(BOUND, None)
            if original is None:
                meta.pop("damage_type", None)
            else:
                meta["damage_type"] = original
            item.item_metadata = json.dumps(meta)


def _blade_use() -> OnUse:
    def create(ctx: RuleContext, params: dict) -> None:
        from core.db.models import EquipmentSlot  # import locale: i modelli non si importano dal catalogo
        from core.game.item_bonuses import item_meta
        _release_bound(ctx.char)
        chosen = params.get("damage_type")
        if params["weapon"].startswith("bind:"):
            item = next(i for i in ctx.char.items if f"bind:{i.id}" == params["weapon"])
            for other in ctx.char.items:
                if other.is_equipped and other.equipment_slot == EquipmentSlot.MAIN_HAND:
                    other.is_equipped, other.equipment_slot = False, None
            item.is_equipped, item.equipment_slot = True, EquipmentSlot.MAIN_HAND
            meta = item_meta(item)
            item.item_metadata = json.dumps({**meta, PACT_WEAPON: True, BOUND: True, ORIGINAL_TYPE: meta.get("damage_type")})
        else:
            _create_pact_weapon(ctx, params)
        if chosen in DAMAGE_TYPES:  # la scelta è il tipo di danno dell'arma; senza, resta il suo
            for item in ctx.char.items:
                if _is_pact(item):
                    item.item_metadata = json.dumps({**json.loads(item.item_metadata), "damage_type": chosen})

    def label_ctx(ctx: RuleContext, key: str) -> dict[str, str]:
        if not key.startswith("bind:"):
            return _weapon_label(key)
        name = next((i.name for i in ctx.char.items if f"bind:{i.id}" == key), key)
        return {"it": f"Lega: {name}", "en": f"Bind: {name}"}

    return OnUse(
        slot="bonus", effect=create,
        choices=(UseChoice("weapon", {"it": "Forma dell'arma o arma magica da legare", "en": "Weapon form or magic weapon to bind"},
                           lambda c: [*PACT_WEAPONS, *_bindable(c)], lambda k: _weapon_label(k), option_label_ctx=label_ctx),
                 UseChoice("damage_type", {"it": "Tipo di danno", "en": "Damage type"}, lambda _c: ["normal", *DAMAGE_TYPES],
                           lambda k: {"it": "Quello dell'arma", "en": "The weapon's own"} if k == "normal"
                           else {"it": _TYPE_LABELS[k][0].title(), "en": _TYPE_LABELS[k][1].title()}, optional=True)))


def _gaze_state(_ctx: RuleContext, _params: dict) -> StateSpec:
    return StateSpec("gaze_of_two_minds", ends_on=("new_turn", "turn_end_counted", "rest_short", "rest_long", "manual"),
                     data={"skip_new_turns": 1, "others": [f"{CK}.gaze_of_two_minds"]})


GAZE_USE = OnUse(slot="bonus", state=_gaze_state)
# I PF temporanei sono il massimo del dado (1d4 + 4): niente tiro
VIGOR_USE = OnUse(slot="action", temp_hp=lambda _c, _rolled: 8)
CHAIN_USE = OnUse(forgoes_attack=True)  # rinunci a un attacco: il famiglio attacca con la sua reazione


def _gift_available(ctx: RuleContext) -> bool:
    """Come Sentinella, ma niente offerta se il danno uccide sul colpo (residuo >= PF massimi): non potrebbe funzionare."""
    if not _drops_to_zero(ctx):
        return False
    char = ctx.char
    return ctx.damage is None or ctx.damage - char.current_hit_points - (char.temp_hp or 0) < char.hit_points


GIFT_KEY = f"{CK}.gift_of_the_protectors"
GIFT_GROUP = "gift_of_the_protectors"  # una sola offerta per danno: la propria o quella di un compagno
GIFT = RollOptionSpec(
    key=GIFT_KEY, phase="damage_in", rolls=("damage_taken",), holds_at_one=True, cost=Cost(feature_key=GIFT_KEY), available=_gift_available,
    group=GIFT_GROUP,
    label={"it": "Dono dei Protettori: se il danno ti porta a 0 PF senza ucciderti sul colpo, resti a 1 PF (un uso, riposo lungo)",
           "en": "Gift of the Protectors: if the damage would drop you to 0 HP without killing you outright, you stay at 1 HP (one use, long rest)"})
# Il nome sul libro lo sa il tavolo (R42): l'offerta vale per ogni partecipante della serata e paga l'uso del warlock
GIFT_ALLY = RollOptionSpec(
    key=GIFT_KEY, phase="damage_in", rolls=("damage_taken",), holds_at_one=True, cost=Cost(feature_key=GIFT_KEY), available=_gift_available,
    group=GIFT_GROUP, for_ally=True,
    label={"it": "Dono dei Protettori di {donor}: il tuo nome è scritto nel suo libro? Se il danno ti porta a 0 PF senza ucciderti sul colpo, resti a 1 PF (spende l'uso di {donor})",
           "en": "{donor}'s Gift of the Protectors: is your name written in their book? If the damage would drop you to 0 HP without killing you outright, you stay at 1 HP (spends {donor}'s use)"})


# Su un alleato della serata il Dono scatta dal suo danno (``GIFT_ALLY``): «Usa» resta per le creature non PG, esito testuale
GIFT_USE = OnUse(notes=lambda _c, _p: ["gift_of_the_protectors_other"])


def _shadows_state() -> RollOptionSpec:
    return RollOptionSpec(
        key=f"{CK}.one_with_shadows_light", phase="before", rolls=("cast",),
        available=lambda c: c.spell is not None and (c.spell.srd_index or "") == "invisibility",
        label={"it": "Tutt'Uno con le Ombre: sei in luce fioca o nell'oscurità?", "en": "One with Shadows: are you in dim light or darkness?"},
        effect=_say("Solo in luce fioca o nell'oscurità: la luce la dichiari tu.", "Only in dim light or darkness: you declare the light."))


# ---------------------------------------------------------------------------
# Elenco
# ---------------------------------------------------------------------------

def _inv(key: str, it: str, en: str, suffix: str, level: int, summary: tuple[str, str], *, name: tuple[str, str] | None = None,
         action_type: str | None = None, **kw: Any):
    return feature(key, CK, ED, 1, f"{it} / {en} ({suffix})", name or (it, en), summary, action_type,
                   option_group=INVOCATIONS, option_key=key, **kw), level


def _will(key: str, it: str, en: str, suffix: str, level: int, spell: str, spell_it: str, spell_en: str, self_only: bool = False, **kw: Any):
    on_self = " su te stesso" if self_only else ""
    on_self_en = " on yourself" if self_only else ""
    return _inv(key, it, en, suffix, level,
                (f"Lanci {spell_it}{on_self} a volontà, senza slot. Per l'azione di lancio usa la pagina degli incantesimi.",
                 f"You cast {spell_en}{on_self_en} at will, with no slot. Use the spells page for the casting action."),
                granted_spells=(spell,), at_will_spells=(spell,), **kw)


def _per_cantrip(family: str, it: str, en: str, suffix: str, summary: tuple[str, str], pick, build) -> list:
    rows = []
    for index in pick:
        c_it, c_en = CANTRIPS[index][:2]
        key = f"{family}__{_slug(index)}"
        rows.append(_inv(key, it, en, suffix, 2, summary, name=(f"{it}: {c_it}", f"{en}: {c_en}"), **build(index, key)))
    return rows


_P = "Suppliche Occulte"
_DAMAGE = "trucchetto Warlock che infligge danno"
_ROWS: list = [
    *_per_cantrip(
        "agonizing_blast", "Deflagrazione Agonizzante", "Agonizing Blast", f"{_P}, livello 2+, {_DAMAGE}, pag. 155",
        ("Ripetibile: per il trucchetto scelto aggiungi il modificatore di Carisma ai danni di ogni tiro, con un trucchetto diverso a ogni scelta.",
         "Repeatable: for the chosen cantrip you add your Charisma modifier to every damage roll, with a different cantrip each pick."),
        CANTRIPS, lambda index, key: {"modifiers": (_agonizing(index, key),)}),
    _will("armor_of_shadows", "Armatura delle Ombre", "Armor of Shadows", f"{_P}, pag. 155", 1, "mage-armor", "armatura magica", "mage armor",
          True, roll_options=(MAGE_ARMOR_CAST,), modifiers=(MAGE_ARMOR_AC,)),
    _will("ascendant_step", "Passo Ascendente", "Ascendant Step", f"{_P}, livello 5+, pag. 155", 5, "levitate", "levitazione", "levitate", True),
    _inv("devils_sight", "Vista del Diavolo", "Devil's Sight", f"{_P}, livello 2+, pag. 155", 2,
         ("Vedi normalmente in luce fioca e nell'oscurità, anche magica, fino a 36 m.",
          "You see normally in dim light and darkness, magical or not, up to 120 ft."),
         modifiers=(Modifier("sense:devils_sight", 120, source=f"feature:{CK}.devils_sight"),), passive=True),
    _inv("devouring_blade", "Lama Divoratrice", "Devouring Blade", f"{_P}, livello 12+, Lama Assetata, pag. 155", 12,
         ("Con l'azione di Attacco attacchi tre volte con l'arma del patto. Non si somma ad Attacco Extra.",
          "With the Attack action you attack three times with the pact weapon. It does not stack with Extra Attack."),
         attacks_with_pact_weapon=3),
    _inv("eldritch_mind", "Mente Occulta", "Eldritch Mind", f"{_P}, pag. 155", 1,
         ("Hai vantaggio ai TS su Costituzione per mantenere la Concentrazione.",
          "You have advantage on Constitution saves to maintain Concentration."),
         modifiers=(Modifier("advantage", 1, when=lambda c: c.roll == "concentration", source=f"feature:{CK}.eldritch_mind"),), passive=True),
    _inv("eldritch_smite", "Fendente Occulto", "Eldritch Smite", f"{_P}, livello 5+, Patto della Lama, pag. 155", 5,
         ("Dopo un colpo con l'arma del patto spendi uno slot di Patto: 1d8 + 1d8 per livello dello slot di danni da forza e, se Enorme o meno, Prono. Una volta per turno.",
          "After a hit with the pact weapon you spend a Pact slot: 1d8 + 1d8 per slot level of force damage and, if Huge or smaller, Prone. Once per turn."),
         roll_options=(SMITE,), passive=True),
    *_per_cantrip(
        "eldritch_spear", "Lancia Occulta", "Eldritch Spear", f"{_P}, livello 2+, {_DAMAGE}, pag. 155",
        ("Ripetibile: la gittata del trucchetto scelto (almeno 3 m) aumenta di 9 m per livello da warlock, con un trucchetto diverso a ogni scelta.",
         "Repeatable: the range of the chosen cantrip (at least 10 ft) grows by 30 ft per warlock level, with a different cantrip each pick."),
        [i for i, c in CANTRIPS.items() if c[3]], lambda index, key: {"spell_range_per_level": (tuple(_names(index)), 9), "passive": True}),
    _inv("fiendish_vigor", "Vigore Immondo", "Fiendish Vigor", f"{_P}, livello 2+, pag. 155", 2,
         ("Azione: lanci vita falsata su di te senza slot, a volontà; ottieni il massimo dei PF temporanei (8) invece di tirare, se più di quelli che hai.",
          "Action: you cast false life on yourself with no slot, at will; you gain the maximum temporary hit points (8) instead of rolling, if higher than yours."),
         action_type="action", on_use=VIGOR_USE),
    _inv("gaze_of_two_minds", "Sguardo delle Due Menti", "Gaze of Two Minds", f"{_P}, livello 5+, pag. 156", 5,
         ("Azione bonus: tocchi una creatura consenziente e percepisci con i suoi sensi fino alla fine del tuo turno successivo; si rinnova con un'azione bonus.",
          "Bonus action: link up with a willing creature you touch and share what it senses, until your next turn ends; renew it with a bonus action."),
         action_type="bonus_action", on_use=GAZE_USE),
    _inv("gift_of_the_depths", "Dono delle Profondità", "Gift of the Depths", f"{_P}, livello 5+, pag. 156", 5,
         ("Respiri sott'acqua e hai velocità di nuotare pari alla velocità. Lanci respirare sott'acqua una volta senza slot; l'uso torna con un riposo lungo.",
          "You breathe underwater and have a swim speed equal to your speed. You cast water breathing once with no slot; the use returns on a long rest."),
         granted_spells=("water-breathing",), free_spell="water-breathing", uses=Uses(table={1: 1}), restoration="long_rest",
         modifiers=(Modifier("swim_speed", 1, source=f"feature:{CK}.gift_of_the_depths"),)),
    _inv("gift_of_the_protectors", "Dono dei Protettori", "Gift of the Protectors", f"{_P}, livello 9+, Patto del Tomo, pag. 156", 9,
         ("Chi scende a 0 PF senza morire sul colpo resta a 1 PF, una volta fino al riposo lungo (nomi: Carisma, min. 1). Scatta da solo col danno, su di te o su un alleato della serata (usa il tuo uso).",
          "Whoever drops to 0 HP without dying outright stays at 1, once until a long rest (names: Charisma, min. 1). Triggers by itself on the damage, on you or on a table ally (spends your use)."),
         uses=Uses(table={9: 1}), restoration="long_rest", roll_options=(GIFT, GIFT_ALLY), on_use=GIFT_USE),
    _inv("investment_of_the_chain_master", "Investitura del Padrone delle Catene", "Investment of the Chain Master",
         f"{_P}, livello 5+, Patto della Catena, pag. 156", 5,
         ("Il famiglio evocato con Trova Famiglio vola o nuota a 12 m, attacca con la tua azione bonus, infligge danni necrotici o radiosi, usa la tua CD e resiste in reazione.",
          "The familiar from Find Familiar flies or swims at 40 ft, attacks on your bonus action, deals necrotic or radiant damage, uses your DC and resists as a reaction."),
         passive=True),
    _inv("lessons_of_the_first_ones", "Lezioni dei Primi", "Lessons of the First Ones", f"{_P}, livello 2+, pag. 156", 2,
         ("Ripetibile: ottieni un talento di Origine a tua scelta, diverso a ogni scelta.",
          "Repeatable: you gain an Origin feat of your choice, a different one each pick."), passive=True),
    _inv("lifedrinker", "Succhiavita", "Lifedrinker", f"{_P}, livello 9+, Patto della Lama, pag. 156", 9,
         ("Dopo un colpo con l'arma del patto: 1d6 danni necrotici, psichici o radiosi in più e, spendendo un Dado Vita, recuperi PF pari al tiro più COS. Una volta per turno.",
          "After a hit with the pact weapon: extra 1d6 necrotic, psychic or radiant damage and, spending a Hit Die, you regain hit points equal to the roll plus Con. Once per turn."),
         roll_options=(*(_lifedrinker(t) for t in DAMAGE_TYPES), *(_lifedrinker(t, True) for t in DAMAGE_TYPES)), passive=True),
    _will("mask_of_many_faces", "Maschera dei Molti Volti", "Mask of Many Faces", f"{_P}, livello 2+, pag. 156", 2, "disguise-self",
          "camuffare se stesso", "disguise self", True),
    _will("master_of_myriad_forms", "Maestro di Mille Forme", "Master of Myriad Forms", f"{_P}, livello 5+, pag. 156", 5, "alter-self",
          "alterare se stesso", "alter self", True),
    _will("misty_visions", "Visioni Velate", "Misty Visions", f"{_P}, livello 2+, pag. 156", 2, "silent-image", "immagine silenziosa", "silent image"),
    _will("one_with_shadows", "Tutt'Uno con le Ombre", "One with Shadows", f"{_P}, livello 5+, pag. 156", 5, "invisibility",
          "invisibilità", "invisibility", True, roll_options=(_shadows_state(),)),
    _will("otherworldly_leap", "Balzo Ultraterreno", "Otherworldly Leap", f"{_P}, livello 2+, pag. 156", 2, "jump", "saltare", "jump", True),
    _inv("pact_of_the_blade", "Patto della Lama", "Pact of the Blade", f"{_P}, pag. 156", 1,
         ("Azione bonus: evochi un'arma da mischia del patto (di cui sei competente, anche focus). Usi Carisma per attacco e danni; danno necrotico, psichico, radioso o normale.",
          "Bonus action: you conjure a pact melee weapon (you are proficient, also a focus). You use Charisma for attack and damage; necrotic, psychic, radiant or normal damage."),
         action_type="bonus_action", on_use=_blade_use()),
    _inv("pact_of_the_chain", "Patto della Catena", "Pact of the Chain", f"{_P}, pag. 157", 1,
         ("Trova Famiglio a volontà, senza slot, anche nelle forme speciali. Rinunci a un attacco e il famiglio attacca con la sua reazione.",
          "Find Familiar at will, with no slot, also in the special forms. Give up an attack and the familiar attacks with its reaction."),
         action_type="special", granted_spells=("find-familiar",), at_will_spells=("find-familiar",), on_use=CHAIN_USE),
    _inv("pact_of_the_tome", "Patto del Tomo", "Pact of the Tome", f"{_P}, pag. 157", 1,
         ("Il Libro delle Ombre: tre trucchetti e due incantesimi rituali di 1° livello da qualsiasi lista, preparati come da warlock, fuori dal limite.",
          "The Book of Shadows: three cantrips and two 1st-level ritual spells from any list, prepared as warlock spells, outside the limit."),
         passive=True,
         choices=(ChoiceSpec(group="tome_cantrips", levels={1: 3}, options=lambda _c: [], spell_pick="extra", spell_level=0),
                  ChoiceSpec(group="tome_rituals", levels={1: 2}, options=lambda _c: [], spell_pick="extra", spell_level=1, spell_exact=True,
                             spell_ritual=True))),
    *_per_cantrip(
        "repelling_blast", "Deflagrazione Respingente", "Repelling Blast",
        f"{_P}, livello 2+, {_DAMAGE} con un tiro per colpire, pag. 157",
        ("Ripetibile: dopo un colpo con il trucchetto scelto spingi il bersaglio (Grande o meno) fino a 3 m, con un trucchetto diverso a ogni scelta.",
         "Repeatable: after a hit with the chosen cantrip you push the target (Large or smaller) up to 10 ft, with a different cantrip each pick."),
        [i for i, c in CANTRIPS.items() if c[2]], lambda index, key: {"roll_options": (_repelling(index, key),), "passive": True}),
    _inv("thirsting_blade", "Lama Assetata", "Thirsting Blade", f"{_P}, livello 5+, Patto della Lama, pag. 157", 5,
         ("Con l'azione di Attacco attacchi due volte con l'arma del patto. Non si somma ad Attacco Extra.",
          "With the Attack action you attack twice with the pact weapon. It does not stack with Extra Attack."),
         attacks_with_pact_weapon=2),
    _will("visions_of_distant_realms", "Visione dei Reami Lontani", "Visions of Distant Realms", f"{_P}, livello 9+, pag. 157", 9, "arcane-eye",
          "occhio arcano", "arcane eye"),
    _will("whispers_of_the_grave", "Sussurri dalla Tomba", "Whispers of the Grave", f"{_P}, livello 7+, pag. 157", 7, "speak-with-dead",
          "parlare con i morti", "speak with dead"),
    _inv("witch_sight", "Vista Stregata", "Witch Sight", f"{_P}, livello 15+, pag. 157", 15,
         ("Vedi la Visione Veritiera fino a 9 m.", "You have truesight out to 30 ft."),
         modifiers=(Modifier("sense:truesight", 30, source=f"feature:{CK}.witch_sight"),), passive=True),
]

INVOCATION_ROWS = tuple(spec for spec, _level in _ROWS)
LEVELS = {spec.option_key: level for spec, level in _ROWS}


def prerequisites_met(ctx: RuleContext, key: str, owned: list[str]) -> bool:
    """Livello da warlock, supplica richiesta (già scelta, o scegliibile adesso: si prendono insieme) e, per le Ripetibili,
    il trucchetto di cui parla la riga."""
    if ctx.class_level < LEVELS[key]:
        return False
    if key in REQUIRES and REQUIRES[key] not in owned and not prerequisites_met(ctx, REQUIRES[key], owned):
        return False
    _family, _, slug = key.partition("__")
    return not slug or knows_cantrip(ctx.char, next(i for i in CANTRIPS if _slug(i) == slug))


def available_invocations(ctx: RuleContext) -> list[str]:
    owned = _chosen(ctx)
    return [key for key in LEVELS if prerequisites_met(ctx, key, owned)]


def picks_ok(ctx: RuleContext, picked: list[str]) -> bool:
    """Una scelta in blocco rispetta le richieste fra suppliche: ognuna ha la sua già scelta o scelta insieme."""
    owned = [*_chosen(ctx), *picked]
    return all(REQUIRES[k] in owned for k in picked if k in REQUIRES)


def protected_invocations(ctx: RuleContext) -> set[str]:
    """Suppliche che non si sostituiscono perché un'altra scelta le richiede."""
    return {REQUIRES[k] for k in _chosen(ctx) if k in REQUIRES}


INVOCATION_CHOICE = ChoiceSpec(
    group=INVOCATIONS, levels={1: 1, 2: 3, 5: 5, 7: 6, 9: 7, 12: 8, 15: 9, 18: 10}, replaceable=True, options=available_invocations,
    import_options=lambda _c: list(LEVELS), protected=protected_invocations,
    batch_ok=picks_ok)

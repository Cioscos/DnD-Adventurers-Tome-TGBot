"""Conferma al tiro: quali opzioni offrire per un tiro e cosa comportano. Il giudizio è del giocatore, il calcolo qui."""
from __future__ import annotations

import json
import random
import re
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from typing import Any

from core.db.models import CharacterHistory
from core.rules.catalog import active_features
from core.rules.edition import character_edition
from core.rules.spell_effects import SPELL_STATE_PREFIX
from core.rules.states import SPELL_SPENT, has_state, immune_conditions
from core.rules.uses import pool_key
from core.rules.types import BARDIC_DIE, TRICKSTER_BLESSING, TURN_FLAGS, WAR_GODS_BLESSING, Cost, RollOptionSpec, RuleContext
from core.rules.weapons import has_property, small_race

_DICE = re.compile(r"^(\d+)d(\d+)([+-]\d+)?$")


def _on(condition: str):
    """La condizione c'è e non è sospesa da uno stato (Ira Incontenibile)."""
    return lambda ctx: bool((ctx.char.conditions or {}).get(condition)) and condition not in immune_conditions(ctx.char)


def _spend_inspiration(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    ctx.char.heroic_inspiration = False
    settings = ctx.char.settings or {}
    if settings.get("inspiration_extra"):  # nessuna da cedere, adesso
        ctx.char.settings = {k: v for k, v in settings.items() if k != "inspiration_extra"}


def _bardic_state(ctx: RuleContext) -> dict | None:
    return next((s for s in ctx.char.active_states or [] if s.get("key") == BARDIC_DIE), None)


def _bardic_dice(ctx: RuleContext, _inputs: dict) -> str:
    return f"1d{((_bardic_state(ctx) or {}).get('data') or {}).get('die') or 6}"


def _ally_aura(kind: str, edition: str | None = None):
    """Un compagno della serata proietta questa aura (nell'edizione data: l'Interdizione cambia fra 2014 e 2024) e chi tira non
    ne ha una uguale per conto suo."""
    from core.rules.auras import has_own_aura, party_auras  # import locale: auras usa il catalogo
    return lambda ctx: (any(edition is None or a.get("edition") == edition for a in party_auras(ctx.char, kind))
                        and not has_own_aura(ctx.char, kind))


def _ally_aura_bonus(ctx: RuleContext, _inputs: dict) -> int:
    from core.rules.auras import party_auras  # import locale
    return max((a["bonus"] for a in party_auras(ctx.char, "protection")), default=0)


# Regole generali, e condizioni i cui effetti dipendono da ciò che l'app non vede (R25, R25 bis).
_CONDITION_OPTIONS = (
    RollOptionSpec(
        key="inspiration:advantage", phase="before", rolls=("attack", "skill", "save", "initiative", "death_save"),
        mode="advantage", on_confirm=_spend_inspiration,
        label={"it": "Spendi l'Ispirazione: tiro con vantaggio", "en": "Spend Inspiration: roll with advantage"},
        available=lambda ctx: ctx.edition == "2014" and bool(ctx.char.heroic_inspiration),
    ),
    RollOptionSpec(
        key="inspiration:reroll_damage", phase="after_damage", rolls=("spell_damage", "weapon_damage"), reroll_dice=lambda _ctx, _i: 1,
        on_confirm=_spend_inspiration,
        label={"it": "Spendi l'Ispirazione Eroica: ritira un dado di danno", "en": "Spend Heroic Inspiration: reroll a damage die"},
        available=lambda ctx: ctx.edition == "2024" and bool(ctx.char.heroic_inspiration),
    ),
    # Dado di Ispirazione Bardica ricevuto (R38): vale per ogni scheda, qualunque sia la sua edizione. Il dado si perde
    # comunque dopo l'uso: lo stato si chiude, e un rimborso dei gettoni lo rimette.
    RollOptionSpec(
        key="bardic_die:add", phase="after_roll", after="add", rolls=("skill", "attack", "save", "initiative", "death_save"),
        extra_dice=_bardic_dice, cost=Cost(state_key=BARDIC_DIE),
        label={"it": "Dado di Ispirazione Bardica: somma il dado al tiro", "en": "Bardic Inspiration die: add the die to the roll"},
        available=lambda ctx: _bardic_state(ctx) is not None,
    ),
    RollOptionSpec(
        key="bardic_die:damage", phase="after_hit", rolls=("attack",), crit_doubles=False,
        extra_dice=_bardic_dice, cost=Cost(state_key=BARDIC_DIE),
        label={"it": "Ispirazione in Combattimento: somma il dado al danno", "en": "Combat Inspiration: add the die to the damage"},
        available=lambda ctx: bool((((_bardic_state(ctx) or {}).get("data")) or {}).get("combat")),
    ),
    # Aure dei compagni di serata (Paladino 2014): il giocatore conferma di essere nella gittata (D1)
    RollOptionSpec(
        key="aura:protection", phase="before", rolls=("save", "death_save"), bonus=_ally_aura_bonus,
        label={"it": "Aura di Protezione di un compagno paladino: sei entro la sua gittata (3 m, 9 m dal 18°)? Somma il suo Carisma",
               "en": "Aura of Protection of a paladin ally: are you within its range (10 ft, 30 ft from 18th)? Add their Charisma"},
        available=_ally_aura("protection"),
    ),
    # Lo stesso bonus dopo aver visto il d20: serve al TS di concentrazione, anche quello automatico dopo il danno, per cui
    # il giocatore non può confermare prima (D1).
    RollOptionSpec(
        key="aura:protection_after", phase="after_roll", after="add", rolls=("save", "death_save"), bonus=_ally_aura_bonus,
        label={"it": "Aura di Protezione di un compagno paladino: sei entro la sua gittata? Somma il suo Carisma al tiro",
               "en": "Aura of Protection of a paladin ally: are you within its range? Add their Charisma to the roll"},
        # Il Carisma si somma una volta: se è già stata confermata prima del tiro non si ripropone.
        available=lambda ctx: _ally_aura("protection")(ctx) and "aura:protection" not in ctx.confirmed,
    ),
    RollOptionSpec(
        key="aura:warding", phase="damage_in", rolls=("damage_taken",), grants_resistance=True,
        label={"it": "Aura di Interdizione di un compagno paladino: sei entro la sua gittata e il danno viene da un incantesimo? Resistenza",
               "en": "Aura of Warding of a paladin ally: are you within its range and does the damage come from a spell? Resistance"},
        available=_ally_aura("warding", "2014"),
    ),
    RollOptionSpec(
        key="aura:warding_2024", phase="damage_in", rolls=("damage_taken",), grants_resistance=True,
        label={"it": "Aura di Interdizione di un compagno paladino: sei entro la sua gittata? Resistenza al danno necrotico, psichico o radioso",
               "en": "Aura of Warding of a paladin ally: are you within its range? Resistance to necrotic, psychic or radiant damage"},
        available=lambda ctx: _ally_aura("warding", "2024")(ctx) and ctx.damage_type in (None, "necrotic", "psychic", "radiant"),
    ),
    # Effetti dati da un chierico a chi li riceve: valgono per ogni scheda, come il dado di Ispirazione Bardica.
    RollOptionSpec(
        key="war_blessing:add", phase="after_roll", after="add", rolls=("attack",), bonus=lambda _c, _i: 10,
        cost=Cost(state_key=WAR_GODS_BLESSING),
        label={"it": "Benedizione del Dio della Guerra: somma 10 al tiro per colpire", "en": "War God's Blessing: add 10 to the attack roll"},
        available=lambda ctx: has_state(ctx.char, WAR_GODS_BLESSING),
    ),
    RollOptionSpec(
        key="trickster:advantage", phase="before", rolls=("skill",), mode="advantage",
        label={"it": "Benedizione dell'Ingannatore: vantaggio a Furtività", "en": "Blessing of the Trickster: advantage on Stealth"},
        available=lambda ctx: ctx.skill == "stealth" and has_state(ctx.char, TRICKSTER_BLESSING),
    ),
    RollOptionSpec(
        key="weapon:heavy_small", phase="before", rolls=("attack",), mode="disadvantage",
        label={"it": "Arma pesante: sei una creatura Piccola?", "en": "Heavy weapon: are you a Small creature?"},
        available=lambda ctx: (ctx.edition == "2014" and ctx.item is not None and has_property(ctx.item, "heavy")
                               and small_race(ctx.char) is None),
    ),
    RollOptionSpec(
        key="condition:frightened", phase="before", rolls=("attack", "skill", "initiative"), mode="disadvantage",
        label={"it": "Spaventato: vedi la fonte della paura?", "en": "Frightened: can you see the source of your fear?"},
        available=_on("frightened"),
    ),
    RollOptionSpec(
        key="condition:grappled", phase="before", rolls=("attack",), mode="disadvantage",
        label={"it": "Afferrato: il bersaglio non è chi ti afferra?", "en": "Grappled: is the target someone other than your grappler?"},
        available=lambda ctx: ctx.edition == "2024" and _on("grappled")(ctx),
    ),
    RollOptionSpec(
        key="condition:invisible", phase="before", rolls=("attack",), cancels=("condition:invisible",),
        label={"it": "Invisibile: un nemico ti vede?", "en": "Invisible: can an enemy see you?"},
        available=lambda ctx: ctx.edition == "2024" and _on("invisible")(ctx),
    ),
    RollOptionSpec(
        key="condition:blinded", phase="before", rolls=("skill",), auto_fail=True,
        label={"it": "Accecato: la prova richiede la vista?", "en": "Blinded: does this check require sight?"},
        available=_on("blinded"),
    ),
    RollOptionSpec(
        key="condition:deafened", phase="before", rolls=("skill",), auto_fail=True,
        label={"it": "Assordato: la prova richiede l'udito?", "en": "Deafened: does this check require hearing?"},
        available=_on("deafened"),
    ),
)


def _bastion_left(ctx: RuleContext) -> int:
    state = next((s for s in ctx.char.active_states or [] if s.get("key") == "bastion_of_law"), None)
    return int(((state or {}).get("data") or {}).get("dice") or 0)


def _spend_bastion(n: int):
    def run(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
        left = _bastion_left(ctx) - n
        states = [s for s in ctx.char.active_states or [] if s.get("key") != "bastion_of_law"]
        if left > 0:
            old = next(s for s in ctx.char.active_states if s.get("key") == "bastion_of_law")
            states.append({**old, "data": {**(old.get("data") or {}), "dice": left}})
        ctx.char.active_states = states
    return run


# Bastione della Legge (Stregone 2024): i d8 stanno sullo stato di chi è protetto, anche un altro personaggio della serata
_CONDITION_OPTIONS += tuple(RollOptionSpec(
    key=f"sorcerer.bastion_of_law_{n}", phase="damage_in", rolls=("damage_taken",), group="sorcerer.bastion_of_law",
    extra_dice=lambda _c, _i, n=n: f"{n}d8", available=lambda c, n=n: _bastion_left(c) >= n, on_confirm=_spend_bastion(n),
    label={"it": f"Bastione della Legge: spendi {n}d8 per ridurre il danno", "en": f"Bastion of Law: spend {n}d8 to reduce the damage"})
    for n in range(1, 6))


class OptionUnavailable(Exception):
    """Opzione non applicabile adesso: già usata, senza risorse, di un'altra fase o inesistente."""

    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


@dataclass(frozen=True)
class RollOption:
    spec: RollOptionSpec
    ctx: RuleContext  # con la classe che possiede il privilegio
    source: str  # nota del tiro: `condition:<slug>` o `feature:<chiave>`
    donor: Any = None  # la scheda che paga (opzione ``for_ally`` di un altro partecipante); None: paga chi tira


@dataclass
class AppliedOptions:
    keys: list[str] = field(default_factory=list)
    extra_dice: list[str] = field(default_factory=list)  # raddoppiano al critico
    fixed_dice: list[str] = field(default_factory=list)  # nel totale, senza raddoppio
    extra_dice_types: list[str | None] = field(default_factory=list)  # tipo di danno di ogni espressione di ``extra_dice``
    fixed_dice_types: list[str | None] = field(default_factory=list)  # ... e di ``fixed_dice``
    rolled_types: list[str | None] = field(default_factory=list)  # tipo di ogni dado tirato, nell'ordine di ``rolled_dice``
    separate_type: str | None = None  # tipo del danno a parte
    separate_dice: list[list] = field(default_factory=list)  # [espressione, raddoppia], fuori dal totale
    separate_rolls: list[int] = field(default_factory=list)
    separate_total: int = 0
    bonus: int = 0
    modes: list[str] = field(default_factory=list)
    multiplier: float = 1
    spent: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    auto_fail: bool = False
    force_crit: bool = False
    reroll: bool = False
    succeed: bool = False
    twenty: bool = False
    refundable: dict[str, list[str]] = field(default_factory=dict)  # chiave -> gettoni, per ``pay_if_success``
    replace_die: int | None = None
    miss_damage: int | None = None
    effects: list[dict[str, str]] = field(default_factory=list)  # {"it", "en"}: esiti da mostrare
    second_attack: bool = False
    targets: list[str] = field(default_factory=list)  # chiavi con un ``target_effect`` da applicare
    reroll_limit: int = 0  # ``after_damage``: dadi di danno ritirabili
    keep_rolled: bool = False
    cancels: list[str] = field(default_factory=list)  # fonti di vantaggio/svantaggio che l'opzione toglie
    maximize: bool = False  # i dadi di danno dell'incantesimo valgono il massimo
    maximize_types: frozenset[str] | None = None  # solo questi tipi di danno; None = tutti
    self_heal: int = 0  # PF che chi lancia una cura recupera
    damage_unscaled: int | None = None  # danno dell'arma prima del moltiplicatore, per rilanciare i dadi
    rolled_dice: list[tuple[int, int]] = field(default_factory=list)  # (lati, valore) dei dadi nel totale, ritirabili
    side_rolls: list[tuple[str, int]] = field(default_factory=list)  # dadi tirati da ``on_confirm`` fuori dal totale (d10 di Passo Rinfrescante): solo cronologia dadi
    holds_at_one: bool = False  # il danno che porta a 0 PF lascia il personaggio a 1 PF
    holds_vs_massive: bool = False  # ``holds_at_one`` vale anche se il danno uccide sul colpo (Interdizione alla Morte)
    held_heal: int = 0  # PF recuperati oltre a quel 1 PF (Sentinella Imperitura 2024)
    resistance: bool = False  # un'opzione dà resistenza al danno subito, che non si cumula con quella già presente
    self_damage: list[tuple[str, str]] = field(default_factory=list)  # (dadi, tipo) che chi usa le opzioni subisce
    ability_override: str | None = None  # la prova di abilità si fa con questa caratteristica (Conoscenza Primordiale)
    unarmed_dice: str | None = None  # il Colpo Senz'Armi infligge questi dadi più Destrezza (Danno Bardico)
    unarmed_damage_type: str | None = None  # il Colpo Senz'Armi infligge questo tipo di danno (Colpi Potenziati)
    finesse_unarmed: bool = False  # per colpire e per il danno vale la migliore fra Forza e Destrezza (Lame Psichiche)
    damage_type: str | None = None  # il danno dell'incantesimo cambia tipo (Incantesimo Trasmutato)
    gifts: list[dict] = field(default_factory=list)  # PF temporanei per un'altra creatura: {"target": id, "value": n}, consegnati dal router

    @property
    def mode(self) -> str | None:
        """Modo confermato; i due opposti si annullano in ``normal``."""
        if not self.modes:
            return None
        return self.modes[0] if len(set(self.modes)) == 1 else "normal"


def keep_target_effect(char: Any, key: str, effect: Any) -> None:
    """Tiene l'effetto deciso dal server fino a quando il giocatore sceglie il combattente (si consuma una volta)."""
    turn = _turn(char)
    turn["target_effects"] = {**turn.get("target_effects", {}), key: asdict(effect)}
    char.turn_state = turn


def _turn(char: Any) -> dict:
    return dict(char.turn_state or {})


def slot_choices(char: Any, minimum: int, pact_only: bool = False) -> dict[int, int]:
    """Livello -> slot liberi (patto compreso, o solo il patto) da ``minimum`` in su."""
    out: dict[int, int] = {}
    for slot in char.spell_slots:
        if slot.level >= minimum and slot.available > 0 and (slot.is_pact or not pact_only):
            out[slot.level] = out.get(slot.level, 0) + slot.available
    return dict(sorted(out.items()))


def _ability_row(char: Any, feature_key: str, amount: int) -> Any:
    """La riga con usi sufficienti; senza massimo il contatore è illimitato (come ``use_feature``)."""
    held = pool_key(char, feature_key)
    return next((a for a in char.abilities if a.feature_key == held
                 and (a.max_uses is None or (a.uses or 0) >= amount)), None)


def _slot_free(char: Any, slot: str) -> bool:
    turn = _turn(char)
    return not turn.get(TURN_FLAGS[slot]) or (slot == "action" and (turn.get("extra_actions") or 0) > 0)


def _once_key(spec: RollOptionSpec) -> str:
    return spec.group or spec.key


def saved_dice(char: Any, key: str) -> list[int]:
    """Valori del d20 salvati per l'opzione ``key`` (Portento), ognuno usabile una volta."""
    return list(((char.settings or {}).get("saved_dice") or {}).get(key) or [])


def _store_saved_dice(char: Any, key: str, values: list[int]) -> None:
    settings = dict(char.settings or {})
    settings["saved_dice"] = {**(settings.get("saved_dice") or {}), key: values}
    char.settings = settings  # nuovo dict: SQLAlchemy non vede le mutazioni in place


def set_saved_dice(char: Any, key: str, values: list[int]) -> None:
    """Sostituisce i dadi salvati di ``key`` (Portento: i d20 tirati alla fine di un riposo lungo)."""
    _store_saved_dice(char, key, values)


def cost_amount(cost: Cost, ctx: RuleContext) -> int:
    """Quanti usi costa l'opzione adesso: fisso, o calcolato dal lancio (``amount_by``)."""
    return cost.amount_by(ctx) if cost.amount_by else cost.amount


def _affordable(char: Any, spec: RollOptionSpec, ctx: RuleContext | None = None) -> bool:
    if spec.replace_die and not saved_dice(char, spec.key):
        return False
    if spec.once_per_turn and _once_key(spec) in _turn(char).get("once_per_turn", []):
        return False
    if spec.slot and not _slot_free(char, spec.slot):
        return False
    cost = spec.cost
    if cost and cost.feature_key and _ability_row(char, cost.feature_key, cost_amount(cost, ctx) if ctx else cost.amount) is None:
        return False
    if cost and cost.state_key and not any(s.get("key") == cost.state_key for s in char.active_states or []):
        return False
    return not (cost and cost.spell_slot_min is not None and not slot_choices(char, cost.spell_slot_min, cost.pact_only))


def _candidates(ctx: RuleContext) -> list[RollOption]:
    """Le opzioni dei privilegi attivi (e quelle generali) valide per ``ctx.roll`` e disponibili adesso, non ancora pagate."""
    found: dict[str, RollOption] = {s.key: RollOption(s, ctx, s.key) for s in _CONDITION_OPTIONS}
    for spec, row in active_features(ctx.char):
        feature_ctx = replace(ctx, class_row=row, class_level=row.level)
        for option in spec.roll_options:
            if not option.for_ally:  # le ``for_ally`` le offre ai compagni, non a chi le possiede
                found.setdefault(option.key, RollOption(option, feature_ctx, f"feature:{spec.key}"))
    from core.rules.spell_effects import spell_state_options  # import locale: il catalogo degli incantesimi usa i tipi delle regole
    for spec, data in spell_state_options(ctx.char):  # dadi e bonus degli incantesimi ricevuti
        found.setdefault(spec.key, RollOption(spec, replace(ctx, spell_data=data), f"spell:{data.get('spell_key')}"))
    for offer in getattr(ctx.char, "party_donors", None) or []:  # messi dal server (``attach_party``)
        donor, spec = offer["donor"], offer["spec"]
        key = f"ally:{donor.id}:{spec.key}"
        label = {lang: text.format(donor=donor.name) for lang, text in spec.label.items()}
        found[key] = RollOption(replace(spec, key=key, for_ally=False, label=label), ctx, f"feature:{spec.key}", donor)
    # Una prova di caratteristica pura è una prova: le opzioni «skill» valgono anche per lei
    kinds = (ctx.roll, "skill") if ctx.roll == "ability" else (ctx.roll,)
    return [o for o in found.values()
            if any(k in o.spec.rolls for k in kinds) and o.spec.available(o.ctx) and _affordable(o.donor or ctx.char, o.spec, o.ctx)]


def roll_options_for(ctx: RuleContext) -> list[RollOption]:
    """Opzioni da offrire per ``ctx.roll``: disponibili e ancora pagabili. Una chiave di due classi vale una volta.
    Le opzioni automatiche non si offrono: le applica il server (``automatic_options_for``)."""
    return [o for o in _candidates(ctx) if not o.spec.automatic]


def automatic_options_for(ctx: RuleContext) -> list[RollOption]:
    """Le opzioni che si applicano da sole a questo tiro (Punizione Divina Migliorata)."""
    return [o for o in _candidates(ctx) if o.spec.automatic]


def _specs_by_key(char: Any) -> dict[str, RollOptionSpec]:
    specs = {s.key: s for s in _CONDITION_OPTIONS}
    for feature, _row in active_features(char):
        specs.update({o.key: o for o in feature.roll_options})
    return specs


def uses_own_slot(char: Any, keys: list[str]) -> bool:
    """Una delle opzioni indicate ha uno slot di turno proprio (azione bonus, reazione): un attacco così non pesa sul
    limite dell'azione Attacco. Il server ricontrolla poi disponibilità e costo di ogni opzione."""
    specs = _specs_by_key(char)
    return any(specs[k].slot or specs[k].outside_action for k in keys if k in specs)


def throws_unarmed(char: Any, keys: list[str]) -> bool:
    """Una delle opzioni indicate è il lancio a distanza senz'armi (``ranged_unarmed``). Il server la ricontrolla poi."""
    specs = _specs_by_key(char)
    return any(specs[k].ranged_unarmed for k in keys if k in specs)


def _spend_state_token(char: Any, key: str) -> str:
    """Chiude lo stato ``key`` (o, se ha più ``data["charges"]``, ne scala una) e restituisce il gettone che
    ``refund_spent`` usa per rimetterlo com'era."""
    state = next(s for s in char.active_states or [] if s.get("key") == key)
    rest = [s for s in char.active_states if s.get("key") != key]
    charges = (state.get("data") or {}).get("charges")
    if type(charges) is int and charges > 1:
        rest.append({**state, "data": {**state["data"], "charges": charges - 1}})
    char.active_states = rest
    caster = (state.get("data") or {}).get("caster_id")
    if key.startswith(SPELL_STATE_PREFIX) and caster is not None and not any(s.get("key") == key for s in rest):
        settings = char.settings or {}  # l'incantesimo termina con l'ultimo uso: il flush chiude il lanciatore
        char.settings = {**settings, SPELL_SPENT: [*(settings.get(SPELL_SPENT) or []), {"caster_id": caster, "key": key}]}
    return f"state:{key}:{json.dumps(state)}"


def run_zero_damage_hooks(session: Any, char: Any, keys: list[str]) -> None:
    """Il danno subito è sceso a 0 con queste opzioni: le loro ``on_zero_damage`` scrivono ciò che ne segue."""
    for spec, row in active_features(char):
        for option in spec.roll_options:
            if option.key in keys and option.on_zero_damage:
                option.on_zero_damage(session, RuleContext(char=char, edition=character_edition(char), class_row=row,
                                                           class_level=row.level))


def _slot_level(char: Any, spec: RollOptionSpec, inputs: dict) -> int:
    level = inputs.get("slot_level")
    if type(level) is not int or level not in slot_choices(
            char, (spec.cost.spell_slot_min if spec.cost else None) or 0, bool(spec.cost and spec.cost.pact_only)):
        raise OptionUnavailable(spec.key)
    return level


def spent_levels(char: Any) -> dict[int, int]:
    """Livello -> slot normali spesi (il Patto non c'entra): quelli che un'opzione può far tornare."""
    out: dict[int, int] = {}
    for slot in char.spell_slots:
        if not slot.is_pact and slot.used > 0:
            out[slot.level] = out.get(slot.level, 0) + slot.used
    return dict(sorted(out.items()))


def _recover_level(option: RollOption, inputs: dict) -> int:
    level = inputs.get("slot_level")
    if type(level) is not int or level not in option.spec.recover_levels(option.ctx):
        raise OptionUnavailable(option.spec.key)
    return level


def _spend(session: Any, option: RollOption, inputs: dict) -> list[str]:
    """Paga l'opzione e ne applica l'effetto collaterale. Ricontrolla ogni risorsa: due opzioni possono contendersi
    l'ultima. I gettoni restituiti sono quelli che ``refund_spent`` sa rimborsare."""
    spec, char = option.spec, option.ctx.char
    if option.donor is not None:
        # Il costo è sulla scheda del donatore: qui solo un gettone. Lo spende il router, con un UPDATE condizionato, quando
        # l'effetto scatta davvero (``spend_donor_tokens``): niente da rimborsare, e due richieste insieme non spendono lo stesso uso.
        row = _ability_row(option.donor, spec.cost.feature_key, cost_amount(spec.cost, option.ctx))
        if row is None:
            raise OptionUnavailable(spec.key)
        return [f"donor:{option.donor.id}:{row.id}:{cost_amount(spec.cost, option.ctx)}"]
    if not _affordable(char, spec, option.ctx):
        raise OptionUnavailable(spec.key)
    spent: list[str] = []
    turn = _turn(char)
    if spec.once_per_turn:
        turn["once_per_turn"] = [*turn.get("once_per_turn", []), _once_key(spec)]
        spent.append(f"once:{_once_key(spec)}")
    if spec.slot:
        flag = TURN_FLAGS[spec.slot]
        if turn.get(flag):  # solo l'azione arriva qui già usata: consuma l'azione extra
            turn["extra_actions"] -= 1
            spent.append("turn:extra_action")
        else:
            turn[flag] = True
            spent.append(f"turn:{spec.slot}")
    char.turn_state = turn  # nuovo dict: SQLAlchemy non vede le mutazioni in place
    cost = spec.cost
    if cost and cost.feature_key:
        amount = cost_amount(cost, option.ctx)
        row = _ability_row(char, cost.feature_key, amount)
        if row.max_uses is not None:
            row.uses = (row.uses or 0) - amount
        spent.append(f"feature:{row.feature_key}:{amount}")
    if cost and cost.state_key:
        spent.append(_spend_state_token(char, cost.state_key))
    if spec.requires_input == "slot":
        level = _slot_level(char, spec, inputs)
        slot = next(s for s in char.spell_slots if s.level == level and s.available > 0 and (s.is_pact or not (cost and cost.pact_only)))
        slot.use_slot()
        spent.append(f"slot:{level}:pact" if slot.is_pact else f"slot:{level}")
    if spec.requires_input == "recover":
        level = _recover_level(option, inputs)
        slot = next(s for s in char.spell_slots if s.level == level and not s.is_pact and s.used > 0)
        slot.used -= 1
        spent.append(f"unslot:{level}")
    if spec.replace_die:
        values = saved_dice(char, spec.key)
        if inputs.get("die") not in values:
            raise OptionUnavailable(spec.key)
        values.remove(inputs["die"])
        _store_saved_dice(char, spec.key, values)
        spent.append(f"die:{spec.key}:{inputs['die']}")
    if spent:
        session.add(CharacterHistory(
            character_id=char.id, timestamp=datetime.utcnow().isoformat(timespec="seconds"),
            event_type="roll_option", description=f"{spec.label['it']} ({', '.join(t.split(':{')[0] for t in spent)})",
        ))
    if spec.on_confirm:
        extra = spec.on_confirm(session, option.ctx, inputs)
        if isinstance(extra, list):  # gettoni che l'effetto ha scritto sul turno (``turnkey:``), da rimborsare con gli altri
            spent.extend(extra)
    return spent


def _take_dice(expr: str, cost: int) -> str | None:
    """``expr`` con ``cost`` dadi in meno; ``None`` se non ne restano abbastanza."""
    match = _DICE.match(expr)
    if match is None or int(match[1]) < cost:
        return None
    return f"{int(match[1]) - cost}d{match[2]}{match[3] or ''}"


def apply_options(session: Any, ctx: RuleContext, keys: list[str], inputs: dict | None = None,
                  phase: str = "before") -> AppliedOptions:
    """Riconvalida e paga le opzioni scelte. ``OptionUnavailable`` lascia pagamenti a metà: il chiamante annulla."""
    inputs = inputs or {}
    automatic = [o for o in automatic_options_for(ctx) if o.spec.phase == phase]
    keys = list(dict.fromkeys([*(o.spec.key for o in automatic), *keys]))  # le automatiche per prime, una volta sola
    usable = {o.spec.key: o for o in [*roll_options_for(ctx), *automatic] if o.spec.phase == phase}
    turned = next((usable[k].spec.damage_type_to for k in keys if k in usable and usable[k].spec.damage_type_to), None)
    if turned and phase == "before":  # Incantesimo Trasmutato: le altre opzioni leggono il tipo nuovo (Affinità Elementale)
        fixed = {k: o for k, o in usable.items() if o.spec.damage_type_to or o.spec.automatic}
        usable = {**{o.spec.key: o for o in roll_options_for(replace(ctx, damage_type=turned)) if o.spec.phase == phase}, **fixed}
    confirmed = ctx.confirmed if phase != "before" else ()
    # Prima del tiro ``needs`` è soddisfatto anche da un'opzione «una volta per turno» già dichiarata in questo turno (Colpo
    # Brutale su un attacco successivo a quello dell'Attacco Irruento)
    declared = tuple(_turn(ctx.char).get("once_per_turn", ())) if phase == "before" else ()
    out = AppliedOptions()
    dice: dict[str, str] = {}
    groups: dict[str, int] = {}
    for key in keys:
        option = usable.get(key)
        if option is None or (option.spec.needs and option.spec.needs not in keys
                              and option.spec.needs not in confirmed and option.spec.needs not in declared):
            raise OptionUnavailable(key)
        spec, given = option.spec, inputs.get(key) or {}
        if spec.group:
            if groups.get(spec.group, 0) >= (spec.group_max(option.ctx) if spec.group_max else 1):
                raise OptionUnavailable(key)
            groups[spec.group] = groups.get(spec.group, 0) + 1
        if spec.requires_input == "slot":
            _slot_level(ctx.char, spec, given)  # i dadi dipendono dallo slot: va controllato prima di calcolarli
        if spec.requires_input == "recover":
            _recover_level(option, given)
        pre_dice = spec.extra_dice(option.ctx, given) if spec.extra_dice else None  # prima del pagamento: Implacabile lo cambia
        rolled_before = given.get("rolled")
        paid = _spend(session, option, given)
        if given.get("rolled") != rolled_before and isinstance(given.get("rolled"), int):
            out.side_rolls.append(("d10", given["rolled"]))  # shortcut: l'unico dado che ``on_confirm`` tira e scrive in ``rolled`` è il d10 di Passo Rinfrescante
        out.spent += paid
        out.keys.append(key)
        if spec.pay_if_success or spec.holds_at_one:
            out.refundable[key] = paid
        out.holds_at_one = out.holds_at_one or spec.holds_at_one
        out.holds_vs_massive = out.holds_vs_massive or spec.holds_vs_massive
        if spec.holds_heal:
            out.held_heal = max(out.held_heal, spec.holds_heal(option.ctx))
        out.resistance = out.resistance or spec.grants_resistance
        if spec.replace_die:
            out.replace_die = given["die"]
        out.reroll = out.reroll or spec.after == "reroll"
        out.succeed = out.succeed or spec.after == "succeed"
        out.twenty = out.twenty or spec.after == "twenty"
        out.second_attack = out.second_attack or spec.second_attack
        if spec.reroll_dice:
            out.reroll_limit += spec.reroll_dice(option.ctx, given)
            out.keep_rolled = out.keep_rolled or spec.keep_rolled
        if spec.miss_damage:  # «declared_only» (pulsante Mancato): arma l'opzione senza il danno di Graze
            out.miss_damage = max(out.miss_damage or 0, 0 if given.get("declared_only") else max(0, spec.miss_damage(option.ctx)))
        if spec.self_heal:  # prima di ``effect``: l'esito può citare il tiro che `self_heal` scrive in ``given``
            out.self_heal += max(0, spec.self_heal(option.ctx, given))
        if spec.effect:
            out.effects.append(spec.effect(option.ctx, given))
        if spec.temp_hp_gift and type(given.get("target_character_id")) is int:
            out.gifts.append({"target": given["target_character_id"], "value": max(0, spec.temp_hp_gift(option.ctx, given))})
        if spec.target_effect:
            keep_target_effect(ctx.char, key, spec.target_effect(option.ctx, given))
            out.targets.append(key)
        if pre_dice is not None:
            dice[key] = pre_dice
        if spec.bonus:
            out.bonus += spec.bonus(option.ctx, given)
        if spec.mode:
            out.modes.append(spec.mode)
        out.cancels += spec.cancels
        out.ability_override = spec.ability_override or out.ability_override
        if spec.unarmed_dice:
            out.unarmed_dice = spec.unarmed_dice(option.ctx, given)
        out.unarmed_damage_type = spec.unarmed_damage_type or out.unarmed_damage_type
        out.finesse_unarmed = out.finesse_unarmed or spec.finesse_unarmed
        out.damage_type = spec.damage_type_to or out.damage_type
        if spec.multiplier is not None:
            out.multiplier *= spec.multiplier
        out.auto_fail = out.auto_fail or spec.auto_fail
        if spec.maximize:
            types = frozenset(spec.maximize_types) if spec.maximize_types else None
            out.maximize_types = types if not out.maximize else (None if None in (types, out.maximize_types) else out.maximize_types | types)
            out.maximize = True
        if spec.self_damage and (expr := spec.self_damage(option.ctx, given)):
            out.self_damage.append((expr, spec.self_damage_type))
        out.force_crit = out.force_crit or spec.force_crit
        if option.source not in out.notes:
            out.notes.append(option.source)
    if out.miss_damage is not None:  # un mancato dichiarato arma anche le opzioni «on_miss» non scelte (Attacchi Studiati)
        for key, option in usable.items():
            if option.spec.on_miss and key not in keys and option.spec.on_confirm:
                option.spec.on_confirm(session, option.ctx, {})
    for key in keys:
        spec = usable[key].spec
        if spec.dice_cost:
            left = _take_dice(dice.get(spec.needs, ""), spec.dice_cost)
            if left is None:
                raise OptionUnavailable(key)
            dice[spec.needs] = left
    for key, expr in dice.items():
        if expr.startswith("0d") and "+" not in expr and "-" not in expr:
            continue
        spec = usable[key].spec
        if spec.separate_damage:
            out.separate_dice.append([expr, spec.crit_doubles])
            out.separate_type = spec.extra_damage_type or out.separate_type
        elif spec.crit_doubles:
            out.extra_dice.append(expr)
            out.extra_dice_types.append(spec.extra_damage_type)
        else:
            out.fixed_dice.append(expr)
            out.fixed_dice_types.append(spec.extra_damage_type)
    return out


def refund_spent(char: Any, spent: list[str]) -> None:
    """Restituisce ciò che ``_spend`` ha pagato, a partire dai suoi gettoni. I gettoni ``donor:`` toccano la riga di un'altra
    scheda e li rimborsa il server con un UPDATE atomico (``refund_donor_tokens``): qui sono ignorati."""
    turn = _turn(char)
    for token in spent:
        kind, _, rest = token.partition(":")
        if kind == "once":
            turn["once_per_turn"] = [k for k in turn.get("once_per_turn", []) if k != rest]
        elif kind == "turnkey":  # un segno scritto sul turno da ``on_confirm`` (Apoteosi Arcana)
            turn.pop(rest, None)
        elif kind == "turn" and rest == "extra_action":
            turn["extra_actions"] = turn.get("extra_actions", 0) + 1
        elif kind == "turn":
            turn[TURN_FLAGS[rest]] = False
        elif kind == "feature":
            feature_key, _, amount = rest.rpartition(":")
            row = next((a for a in char.abilities if a.feature_key == feature_key
                        and a.max_uses is not None and (a.uses or 0) < a.max_uses), None)
            if row is not None:
                row.uses = min(row.max_uses, (row.uses or 0) + int(amount))
        elif kind == "unslot":  # lo slot recuperato torna speso
            slot = next((s for s in char.spell_slots if s.level == int(rest) and not s.is_pact and s.used < s.total), None)
            if slot is not None:
                slot.used += 1
        elif kind == "slot":
            level, _, pact = rest.partition(":")
            slot = next((s for s in char.spell_slots
                         if s.level == int(level) and bool(s.is_pact) == bool(pact) and s.used > 0), None)
            if slot is not None:
                slot.used -= 1
        elif kind == "state":
            key, _, blob = rest.partition(":{")  # la chiave può avere i due punti (``spell:guidance``)
            state = json.loads("{" + blob)
            char.active_states = [*(s for s in char.active_states or [] if s.get("key") != key), state]
            if key.startswith(SPELL_STATE_PREFIX):  # l'incantesimo non è finito: il pagamento annullato toglie la fine in attesa
                pending = (char.settings or {}).get(SPELL_SPENT) or []
                mine = next((e for e in pending if e["key"] == key and e["caster_id"] == (state.get("data") or {}).get("caster_id")), None)
                if mine is not None:
                    char.settings = {**char.settings, SPELL_SPENT: [e for e in pending if e is not mine]}
            if state.get("condition"):  # lo stato rimesso rimette anche la condizione che imponeva
                char.conditions = {**(char.conditions or {}), state["condition"]: True}
        elif kind == "die":
            key, _, value = rest.rpartition(":")
            _store_saved_dice(char, key, [*saved_dice(char, key), int(value)])
    char.turn_state = turn


def roll_extra(dice: list[str], critical: bool = False) -> tuple[list[tuple[str, int]], int]:
    """Tira ``["2d6+3", ...]``: restituisce (tipo di dado, valore) e il bonus fisso. Il critico raddoppia i soli dadi."""
    rolled: list[tuple[str, int]] = []
    flat = 0
    for expr in dice:
        match = _DICE.match(expr)
        if match is None:
            raise ValueError(f"dadi non validi: {expr}")
        count, sides = int(match[1]) * (2 if critical else 1), int(match[2])
        rolled += [(f"d{sides}", random.randint(1, sides)) for _ in range(count)]
        flat += int(match[3] or 0)
    return rolled, flat


def doubled_dice(expr: str) -> str:
    """Il critico raddoppia i dadi, non il fisso."""
    match = _DICE.match(expr)
    return f"{int(match[1]) * 2}d{match[2]}{match[3] or ''}" if match else expr


def scale_damage(value: int, multiplier: float) -> int:
    """Moltiplicatore sul danno, per difetto."""
    return int(value * multiplier)

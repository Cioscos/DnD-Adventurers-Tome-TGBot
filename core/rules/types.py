"""Tipi condivisi delle regole di classe."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from core.rules.condition_removal import ConditionRemoval

Edition = Literal["2014", "2024"]


@dataclass(frozen=True)
class Uses:
    """Formula degli usi massimi: tabella (livello minimo -> usi) + mod caratteristica + competenza + per livello."""
    table: dict[int, int] | None = None
    ability: str | None = None
    minimum: int = 1
    per_level: int = 0
    proficiency: bool = False
    unlimited_from: int | None = None


@dataclass(frozen=True)
class ChoiceSpec:
    """Opzioni di classe da scegliere salendo di livello (Metamagia, Invocazioni, Stili...).

    ``levels``: livello di classe minimo -> totale delle opzioni conosciute a quel livello.
    ``options(ctx)``: chiavi scegliibili (``ctx.class_row.options[group]`` contiene già le scelte).
    ``label(key)``: ``{"name": ..., "summary": ...}`` delle opzioni che non sono privilegi del catalogo (armi, abilità).
    ``grants``: alla risoluzione le opzioni scelte sono abilità e diventano ``proficient`` (competenza) o ``expert``
    (maestria); un'abilità già ``expert`` non scende mai. ``save``: le opzioni sono caratteristiche e ne diventa competente il TS. ``language``: le opzioni sono lingue (``label`` ne dà il nome
    bilingue) e si aggiungono a ``Character.languages`` senza duplicati. ``spell_pick``: le scelte non sono opzioni di un elenco ma
    incantesimi di qualsiasi classe, aggiunti dalla pagina degli incantesimi (``known`` conta fra i conosciuti,
    ``extra`` no: Segreti Magici Aggiuntivi; ``book``: l'incantesimo entra gratis nel Libro del Mago); ``options`` non si usa.
    ``owned(ctx)``: abilità che il giocatore ha già sulla scheda e che, per un personaggio esistente prima del catalogo
    (scelta con ``retrofit``, R39), si possono dichiarare «già sulla scheda» invece di aggiungerne altre.
    ``spell_level``: con ``spell_pick``, il livello massimo dell'incantesimo scelto (0: un trucchetto). ``spell_list``: la
    classe del cui elenco si pesca (``druid``); il client restringe il catalogo, il server non ha gli elenchi.
    ``listed``: la pagina della classe mostra le opzioni scelte del gruppo anche se non si possono sostituire (Nemico Prescelto).
    """
    group: str
    levels: dict[int, int]
    options: Callable[["RuleContext"], list[str]]
    replaceable: bool = False
    # Con ``replaceable``: una sostituzione per riposo lungo (Maestria negli Incantesimi 2024: «al termine di un riposo lungo»)
    replace_per_long_rest: int = 0  # quanti cambi per riposo lungo (True = 1)
    label: Callable[[str], dict] | None = None
    grants: Literal["proficient", "expert", "language", "save"] | None = None
    spell_pick: Literal["known", "extra", "book"] | None = None
    owned: Callable[["RuleContext"], list[str]] | None = None
    spell_level: int | None = None
    spell_list: str | None = None
    listed: bool = False
    # Lingue (it, en) che la risoluzione della scelta aggiunge sempre, qualunque opzione sia scelta (l'Antenato Draconico dà il Draconico)
    adds_language: tuple[str, str] | None = None
    # Con ``spell_pick``: l'incantesimo deve essere esattamente di ``spell_level`` e non dipende dagli slot della classe
    # (Arcanum Mistico: livelli 6-9, oltre gli slot di Patto)
    spell_exact: bool = False
    # Con ``spell_pick``: l'incantesimo scelto deve avere il tag rituale (Libro degli Antichi Segreti)
    spell_ritual: bool = False
    # Chiavi che l'import da Beyond riconosce per nome: tutte, senza i prerequisiti che ``options`` verifica (le suppliche del
    # Warlock dipendono dal Dono del Patto, che l'import scrive nello stesso passaggio)
    import_options: "Callable[[RuleContext], list[str]] | None" = None
    # Gli incantesimi scelti (per nome) diventano sempre preparati e fuori dal limite (Incantesimi Personali)
    always_prepared: bool = False
    # La scelta esiste solo se ``applies(ctx)``: Mente di Ferro la chiede a chi ha già la competenza nei TS su Saggezza
    applies: "Callable[[RuleContext], bool] | None" = None
    # Opzioni scelte che non si sostituiscono perche un'altra scelta le richiede (Patto della Lama per Lama Assetata)
    protected: "Callable[[RuleContext], set[str]] | None" = None
    # La scelta in blocco e ammessa: ``f(ctx, scelte) -> bool`` (una supplica che ne richiede un'altra scelta insieme a lei)
    batch_ok: "Callable[[RuleContext, list[str]], bool] | None" = None
    # Con ``spell_pick``: l'incantesimo scelto deve essere di questa scuola (slug inglese): i Sapienti del Mago 2024
    spell_school: str | None = None

    def __post_init__(self) -> None:
        if self.grants not in (None, "proficient", "expert", "language", "save"):
            raise ValueError(f"grants sconosciuto: {self.grants}")
        if self.spell_pick not in (None, "known", "extra", "book"):
            raise ValueError(f"spell_pick sconosciuto: {self.spell_pick}")


@dataclass(frozen=True)
class UnarmoredAc:
    """CA senza armatura: ``base`` + modificatori di ``abilities``. ``no_shield``: lo scudo la annulla (Monaco)."""
    abilities: tuple[str, ...]
    base: int = 10
    no_shield: bool = False


_DICE = re.compile(r"(\d+)d(\d+)")


def parse_dice(text: str) -> tuple[int, int] | None:
    """``"2d6"`` -> ``(2, 6)``; ``None`` se non è esattamente ``NdM`` con N >= 1 e M >= 2."""
    m = _DICE.fullmatch(text)
    if m is None or int(m[1]) < 1 or int(m[2]) < 2:
        return None
    return int(m[1]), int(m[2])


ENDS_ON = frozenset({
    "rest_short", "rest_long", "unconscious", "incapacitated", "turn_end_inactive", "concentration_end", "manual",
    "new_turn", "attack", "cast", "turn_end_counted", "turn_end", "turn_end_unextended", "heavy_armor",
})

BARDIC_DIE = "bardic_die"  # stato sul ricevente del dado di Ispirazione Bardica (R38); `data`: die, combat
WAR_GODS_BLESSING = "war_gods_blessing"  # stato sul ricevente del +10 al tiro per colpire (Benedizione del Dio della Guerra)
TRICKSTER_BLESSING = "trickster_blessing"  # stato sul ricevente del vantaggio a Furtività (Benedizione dell'Ingannatore)


@dataclass(frozen=True)
class StateSpec:
    """Stato attivo avviato da un privilegio (Ira, Forma Selvatica...).

    ``ends_on`` (insieme chiuso ``ENDS_ON``): ``turn_end_inactive`` = a fine turno senza aver attaccato né subito
    danno dall'ultimo turno (Ira 2014); ``incapacitated`` = condizione che toglie le azioni o 0 PF; ``turn_end`` = alla fine del turno di chiunque in un incontro (fuori incontro vale ``new_turn``);
    ``new_turn`` = al
    prossimo «Nuovo turno» di chi lo porta (Canto di Riposo); ``turn_end_counted`` = alla fine del turno che comincia dopo
    quello in cui è nato, con ``data["skip_new_turns"]`` = 1 (Colpo Mistico): ``new_turn`` lo fa scalare invece di
    chiuderlo e fuori da un incontro lo chiude al «Nuovo turno» seguente; ``attack`` / ``cast`` = quando chi lo porta attacca o lancia
    un incantesimo (Manto di Ombre). ``condition``: condizione che lo stato imposta finché dura (Invisibile) e toglie
    quando finisce, a meno che ci fosse già per un'altra fonte. ``turn_end_unextended`` = alla fine di un turno di chi lo
    porta in cui non è stato prolungato (attacco, TS imposto o azione bonus: Ira 2024); lo stato nato in quel turno
    (``data["fresh"]``) vive fino alla fine del turno seguente. ``heavy_armor`` = quando chi lo porta indossa un'armatura pesante.
    ``rounds``: durata in round, ``None`` = senza scadenza. ``blocks_casting``: finché dura non si lanciano
    incantesimi (conferma al lancio). ``exhaustion_on_end``: livelli di spossatezza quando lo stato finisce, per
    qualunque via. ``immune_conditions``: condizioni che non si possono aggiungere finché dura; quelle già presenti
    sono sospese (restano sulla scheda ma non hanno effetto). ``end_slot``: slot di turno che costa terminarlo a mano
    (``bonus`` per l'Ira): se è già speso lo stato finisce lo stesso, così un tocco sbagliato si corregge; le fini
    automatiche (perdita dei sensi, durata, riposo) non costano nulla."""
    key: str
    rounds: int | None = None
    ends_on: tuple[str, ...] = ("manual",)
    data: dict = field(default_factory=dict)
    blocks_casting: bool = False
    exhaustion_on_end: int = 0
    immune_conditions: tuple[str, ...] = ()
    end_slot: str | None = None
    condition: str | None = None
    also_conditions: tuple[str, ...] = ()  # altre condizioni imposte insieme a ``condition`` (Morte Apparente: Incapacitato e Accecato)

    def __post_init__(self) -> None:
        unknown = set(self.ends_on) - ENDS_ON
        if unknown:
            raise ValueError(f"ends_on sconosciuto: {sorted(unknown)}")
        if self.end_slot is not None and self.end_slot not in TURN_FLAGS:
            raise ValueError(f"end_slot sconosciuto: {self.end_slot}")


@dataclass(frozen=True)
class TargetEffect:
    """Effetto di un privilegio su un altro combattente dell'incontro (D1: nessun modello di posizioni o bersagli).

    ``condition``: slug applicato (anche ``custom:*``). ``save_ability``/``save_dc``: TS del bersaglio; senza, l'effetto
    si applica subito. ``on_failure_only=False``: si applica comunque e il TS non lo toglie (resta solo il risultato).
    Durata: ``ends_at`` = ``{"anchor": "owner"|"source", "edge": "start"|"end", "count": n}`` (stesso formato di
    ``ExpirySpec``, ``source`` = chi usa il privilegio); altrimenti ``rounds`` round sul turno del bersaglio; senza
    nessuno dei due dura finché non viene tolta. ``damage_dice``: danno dell'effetto, mostrato nell'esito.
    ``extends``: se il bersaglio porta già la condizione da chi usa il privilegio, la durata si rinnova senza un nuovo TS
    (prolungamento). ``immune_on_success``: chi supera il TS non è più bersaglio di questo effetto fino al prossimo
    riposo lungo di chi lo usa (le «24 ore» delle schede)."""
    condition: str | None = None
    save_ability: str | None = None
    save_dc: int | None = None
    rounds: int | None = None
    ends_at: dict | None = None
    # Altre condizioni che arrivano insieme a ``condition`` con lo stesso TS, la stessa durata e la stessa fonte (Sguardo Ipnotico)
    also: tuple[str, ...] = ()
    on_failure_only: bool = True
    damage_dice: str | None = None
    extends: bool = False
    immune_on_success: bool = False
    # Con un TS: se fallito, la condizione ripete il TS a ``start`` o ``end`` del turno del bersaglio (Collera della Natura)
    repeat_save: str | None = None
    # Chiave di un testo che il foglio del bersaglio traduce (``character.target_effect.notes.<chiave>``): ciò che l'app non
    # applica da sola e il GM chiude a mano (fino al danno, svantaggio, velocità, vantaggio agli attacchi...)
    note: str | None = None
    # La condizione cade con la concentrazione di chi la applica (le punizioni: Punizione Collerica, Colpo Accecante...)
    ends_with_concentration: bool = False

    def __post_init__(self) -> None:
        if self.repeat_save not in (None, "start", "end"):
            raise ValueError(f"repeat_save sconosciuto: {self.repeat_save}")


@dataclass(frozen=True)
class KiSpell:
    """Incantesimo che un privilegio fa lanciare spendendo punti di una riserva invece di uno slot (Arti dell'Ombra, discipline
    dei Quattro Elementi). ``spell``: ``srd_index``, anche chiave di ``GRANTED_SPELLS``. ``cost``: punti del lancio base.
    ``upcast``: dal 5° livello di classe i punti in più alzano il livello dell'incantesimo di 1 ciascuno, entro il tetto
    per livello (``ki_spell_cap``). ``pool``: la riga ``Ability`` da cui si spende. ``self_only``: il lancio vale solo per
    chi lo fa, senza altre creature (Cavalcare il Vento, Proiezione Astrale)."""
    spell: str
    cost: int
    upcast: bool = False
    pool: str = "monk.ki"
    self_only: bool = False


@dataclass(frozen=True)
class UseToggle:
    """Scelta sì/no all'uso di un privilegio: ``params[key]`` vale ``True`` se il giocatore l'ha attivata."""
    key: str
    label: dict[str, str]
    available: "Callable[[RuleContext], bool]" = lambda _ctx: True


@dataclass(frozen=True)
class UseChoice:
    """Scelta fra più valori all'uso di un privilegio (Conoscenze Secolari: quale abilità): ``params[key]`` ne contiene uno.
    ``options(ctx)`` elenca le chiavi ammesse, ``option_label(key)`` dà il nome bilingue; ``option_label_ctx(ctx, key)`` lo
    sostituisce quando il nome sta sulla scheda (l'arma di Arma Consacrata). ``optional``: la scelta si può lasciare fuori
    (Tocco Purificatore: l'effetto può essere su un'altra creatura); se c'è, deve comunque essere ammessa."""
    key: str
    label: dict[str, str]
    options: "Callable[[RuleContext], list[str]]"
    option_label: "Callable[[str], dict[str, str]]"
    optional: bool = False
    option_label_ctx: "Callable[[RuleContext, str], dict[str, str]] | None" = None
    # La scelta esiste solo se ``applies(ctx)``: altrimenti non si elenca né si valida (l'animale dell'Ira vale per un solo Cammino)
    applies: "Callable[[RuleContext], bool] | None" = None


@dataclass(frozen=True)
class UseText:
    """Testo libero da scrivere all'uso di un privilegio (il nome di un'identità, di un incantesimo rubato): ``params[key]``
    è una stringa. Il server la ripulisce e rifiuta (422 ``invalid_text``) una vuota o più lunga di ``max_len``, prima di
    spendere qualcosa. ``optional``: si può lasciare fuori, ma se c'è deve essere valida. ``required(params)``: la rende
    obbligatoria solo quando vale (il furto riuscito di Ladro di Incantesimi)."""
    key: str
    label: dict[str, str]
    max_len: int = 80
    optional: bool = False
    required: "Callable[[dict], bool] | None" = None


@dataclass(frozen=True)
class OnUse:
    """Cosa fa il pulsante «Usa» di un privilegio oltre a spendere ``cost`` usi.

    ``slot``: slot di turno da spendere (``action``, ``bonus``, ``reaction``...). ``rolls``: dado tirato
    (``1d10``, validato alla definizione); ``heal(ctx, tirato) -> PF`` converte il tiro in cura. ``grants_action``: +1
    azione extra. Con ``amount`` = N (pool come Imposizione delle Mani) l'effetto per unità si ripete N volte: tiri, cura
    e azioni extra; lo stato e l'effetto sul bersaglio si avviano una volta sola.
    ``rolls`` può essere anche ``f(ctx) -> "NdM"`` quando il dado dipende dal livello (Parole Taglienti).
    ``spends``: chiave di un altro privilegio i cui usi si spendono (``cost``), invece degli usi di questo; senza usi
    sufficienti l'uso è rifiutato (409 ``no_uses``) prima di toccare il turno.
    ``ally_state``: con ``params["target_character_id"]`` lo stato non va a chi usa il privilegio ma a quell'altro
    personaggio della stessa serata (Ispirazione Bardica, R38); un bersaglio non valido è rifiutato (422
    ``invalid_target``) prima di spendere qualcosa. Senza bersaglio lo stato è di chi lo usa.
    ``concentration``: l'uso avvia una concentrazione che non è di un incantesimo (Invocare Duplicato), per la durata
    dello stato; gli stati con ``concentration_end`` finiscono con lei.
    ``ally_exclusive``: lo stato dato a un alleato è uno solo alla volta: un nuovo uso toglie quello del bersaglio precedente,
    il cui id il server tiene in ``settings["ally_exclusive"]``.
    ``panel``: l'uso passa da un pannello e da un endpoint propri (Preservare Vita): ``POST /features/{key}/use`` lo
    rifiuta (409 ``needs_panel``) e la scheda dice quale pannello aprire in ``use_panel``.
    ``maximize_if(ctx, params)``: i dadi tirati dall'uso valgono il massimo e l'uso spende anche un uso di ``maximize_cost``
    (Collera Distruttiva su Collera della Tempesta; senza ``maximize_cost`` i dadi valgono il massimo e nulla si spende,
    Guarigione Suprema); senza usi sufficienti l'uso è rifiutato prima di spendere (409 ``no_uses``).
    ``choices``: scelte da fare all'uso, validate prima di spendere qualcosa (422 ``invalid_choice``).
    ``once_per_turn``: l'uso vale una volta per turno anche con più usi disponibili (Azione Impetuosa dal 17°); il secondo è
    rifiutato (409 ``once_per_turn``) prima di spendere. ``forgoes_attack``: l'uso rinuncia a un attacco dell'azione Attacco
    (Colpo del Comandante) e senza attacchi ancora disponibili è rifiutato (409 ``no_attack_left``). ``notes(ctx, params) ->
    [chiave]``: esiti da mostrare, come chiavi che il client traduce (Carica Arcana). ``gives(ctx, tirato) -> n``: valore
    da dare a un altro (PF temporanei di Incoraggiamento): l'app lo mostra e non scrive nulla sulla scheda altrui.
    ``choose_amount``: il giocatore sceglie quanti usi spendere (selettore in «Turno», massimo gli usi rimasti);
    ``max_amount``: tetto per un uso solo.
    ``state``: uno ``StateSpec`` oppure ``f(ctx, params) -> StateSpec`` quando dipende dal livello o da una scelta fatta
    all'uso. ``ends_concentration``: l'uso interrompe la concentrazione. ``available(ctx)``: l'uso è possibile solo se
    vero (409 ``feature_unavailable``), per esempio solo con uno stato attivo. ``toggles``: scelte facoltative da
    fare all'uso (Frenesia), mostrate come interruttori e lette dal privilegio in ``params``."""
    cost: int = 1
    slot: str | None = None
    heal: Callable[["RuleContext", int], int] | None = None
    state: "StateSpec | Callable[[RuleContext, dict], StateSpec] | None" = None
    ends_concentration: bool = False
    available: "Callable[[RuleContext], bool] | None" = None
    toggles: "tuple[UseToggle, ...]" = ()
    grants_action: bool = False
    rolls: "str | Callable[[RuleContext], str] | None" = None
    target_effect: "Callable[[RuleContext, dict], TargetEffect] | None" = None
    choose_amount: bool = False
    max_amount: int | None = None
    spends: str | None = None
    ally_state: bool = False
    concentration: bool = False
    panel: str | None = None
    ally_exclusive: bool = False
    maximize_if: "Callable[[RuleContext, dict], bool] | None" = None
    maximize_cost: str | None = None
    choices: "tuple[UseChoice, ...]" = ()
    once_per_turn: bool = False
    forgoes_attack: bool = False
    notes: "Callable[[RuleContext, dict], list[str]] | None" = None
    # Testo ``{it, en}`` calcolato dal server e mostrato sulla riga prima dell'uso (Astuzia Magica: quanti slot tornano); ``None``: niente
    preview: "Callable[[RuleContext], dict[str, str] | None] | None" = None
    gives: "Callable[[RuleContext, int], int] | None" = None
    # Come ``gives`` ma legge anche le scelte fatte all'uso (Punizione Ispiratrice: agli altri va ciò che chi usa non tiene)
    gives_by: "Callable[[RuleContext, int, dict], int] | None" = None
    # Il valore di ``gives``/``gives_by`` sono PF temporanei per un'altra creatura (Incoraggiamento, Mantello di Ispirazione): con
    # ``target_character_id`` (o ``target_character_ids``, fino a ``ally_count(ctx)`` creature) il server li consegna ai
    # partecipanti della serata, tenendo per ciascuno il maggiore fra i suoi e i nuovi (Task 46). ``ally_count`` a 0: nessun valore da dare.
    temp_hp_ally: bool = False
    ally_count: "Callable[[RuleContext], int] | None" = None
    # Chiave dello stato di chi usa il privilegio (``rage``) con cui i PF temporanei consegnati svaniscono quando finisce
    temp_hp_ends_with: str | None = None
    # Condizioni che l'uso toglie, a sé o a un PG della serata (Task 48): il meccanismo comune a privilegi e incantesimi
    removal: "ConditionRemoval | None" = None
    # usi minimi da spendere insieme (Frusta d'Acqua: 2 ki) e dadi che dipendono da quanti se ne spendono: la formula
    # ``f(ctx, spesi) -> "NdM"`` sostituisce ``rolls`` e non si ripete per unità
    min_amount: int = 1
    rolls_by_amount: "Callable[[RuleContext, int], str] | None" = None
    # chiave dello stato che l'uso chiude (Palmo Tremante: le vibrazioni finiscono)
    ends_state: str | None = None
    # ``heal_when(ctx, params)``: la cura va a chi usa il privilegio solo se vero (Imposizione delle Mani su un'altra creatura
    # scala la riserva e basta). ``amount_ok(ctx, amount, params)``: quanto si spende è ammesso, altrimenti 409
    # ``amount_invalid`` prima di spendere (la cura di malattie costa multipli di 5).
    heal_when: "Callable[[RuleContext, dict], bool] | None" = None
    amount_ok: "Callable[[RuleContext, int, dict], bool] | None" = None
    # Imposizione delle Mani su un altro (R46). ``ally_modes``: i valori della scelta ``mode`` che si rivolgono a un'altra
    # creatura (la scheda li passa al client, che chiede a chi). ``heal_ally_when(ctx, params)``: la cura va al bersaglio
    # scelto, se siede alla serata: la riserva si spende con un UPDATE condizionato e il bersaglio si rilegge dopo.
    ally_modes: tuple[str, ...] = ()
    heal_ally_when: "Callable[[RuleContext, dict], bool] | None" = None
    # Vendetta Ardente su un altro: i suoi PF salgono a metà del *suo* massimo (letto dal server sul bersaglio) e si rialza
    heal_ally_half_max: bool = False
    heal_ally_full: bool = False  # i PF del bersaglio salgono al suo massimo, letto dal server (Panacea)
    # L'uso è possibile anche a 0 PF, da incapacitato (Vendetta Ardente): la UI non lo spegne
    usable_at_zero_hp: bool = False
    ally_needs_zero_hp: bool = False  # il bersaglio dev'essere a 0 PF, altrimenti 409 ``target_not_down`` prima di spendere (Dono dei Protettori)
    heal_ally_to: bool = False  # ``heal`` è il valore a cui portare i PF del bersaglio, non una cura da sommare (Rivivificazione)
    # chiave della ``UseChoice`` che porta il livello di uno slot incantesimo da spendere (Consapevolezza Primordiale): lo slot si prende
    # con un UPDATE condizionato, normali prima del Patto; senza slot libero l'uso è rifiutato (409 ``no_slot``)
    spends_slot: str | None = None
    # testi liberi da scrivere all'uso (``UseText``)
    texts: "tuple[UseText, ...]" = ()
    # monete d'oro da spendere (Maestro Infiltrato): dalla borsa e poi dai contenitori, 409 ``insufficient_funds`` prima di
    # spendere altro
    gold_cost: int = 0
    # ``effect(ctx, params)``: scrive sulla scheda ciò che l'uso comporta e non ha un campo suo (una nota, un incantesimo
    # rubato). Gira dopo i controlli e i pagamenti, nella stessa transazione.
    effect: "Callable[[RuleContext, dict], None] | None" = None
    # ``check(ctx, params)``: rifiuta l'uso prima di spendere qualcosa, con ``(codice_http, nome)`` oppure ``None``
    check: "Callable[[RuleContext, dict], tuple[int, str] | None] | None" = None
    # Costo in usi che dipende dalla scelta fatta all'uso (Creare Slot Incantesimo: i punti dipendono dal livello dello slot):
    # ``cost_by(ctx, params)`` sostituisce ``cost * amount``
    cost_by: "Callable[[RuleContext, dict], int] | None" = None
    # Slot di turno che dipende dalle scelte: ``slot_by(ctx, params) -> slot | None`` sostituisce ``slot`` (il prolungamento
    # dell'Ira per un TS imposto non costa l'azione bonus)
    slot_by: "Callable[[RuleContext, dict], str | None] | None" = None
    # ``spends_slot`` vale solo se ``spends_slot_when(ctx, params)`` (Mantello di Maestà: lo slot serve a ripristinare l'uso)
    spends_slot_when: "Callable[[RuleContext, dict], bool] | None" = None
    # Lo slot di ``spends_slot`` è solo di Patto (ripristino dei privilegi del Patrono del Warlock)
    spends_slot_pact_only: bool = False
    # Usi di un altro privilegio spesi al posto dei propri quando ``params[alt_param]`` è vero (Presenza Intimidatoria:
    # «ripristina» l'uso spendendo un uso di Ira); lo slot di turno si paga lo stesso
    alt_spends: str | None = None
    alt_param: str = "restore"
    # PF temporanei che l'uso dà a chi lo usa: ``f(ctx, tirato) -> n``; vale il maggiore fra quelli attuali e ``n``
    # (i PF temporanei non si sommano)
    temp_hp: "Callable[[RuleContext, int], int] | None" = None
    # Come ``temp_hp`` ma legge anche le scelte fatte all'uso (Punizione Ispiratrice: quanta parte tiene chi la usa)
    temp_hp_by: "Callable[[RuleContext, int, dict], int] | None" = None
    # Cura che dipende da una scelta fatta all'uso (Raccolto Macabro: il livello dell'incantesimo): ``f(ctx, params) -> PF``,
    # applicata a chi usa il privilegio al posto di ``heal``
    heal_by: "Callable[[RuleContext, dict], int] | None" = None
    # Esito da mostrare dopo l'uso, calcolato sulle scelte e sulla scheda (ore dimenticate, danno residuo): ``f(ctx, params)
    # -> {"it": ..., "en": ...}``. Gira dopo il pagamento e prima dell'``effect``: vede la scheda com'era.
    message: "Callable[[RuleContext, dict], dict[str, str] | None] | None" = None
    # Caratteristica di un attacco con incantesimo a distanza che l'uso tira per davvero (Arciere): il server tira il d20
    # (competenza + caratteristica + modificatori) e i dadi di ``rolls`` solo se colpisce (raddoppiati al critico), e chiude
    # gli stati che finiscono con un attacco. L'esito sta in ``UseResult.attack``.
    spell_attack: str | None = None

    def __post_init__(self) -> None:
        if self.max_amount is not None and (not self.choose_amount or self.max_amount < 1):
            raise ValueError("max_amount (>= 1) vale solo con choose_amount")
        if self.min_amount > 1 and not self.choose_amount:
            raise ValueError("min_amount (> 1) vale solo con choose_amount")
        if isinstance(self.rolls, str) and not parse_dice(self.rolls):
            raise ValueError(f"rolls non valido: {self.rolls!r} (atteso NdM, per esempio 1d10)")


@dataclass(frozen=True)
class Modifier:
    """Effetto su un tiro o su un valore derivato. Vedi ``core.rules.modifiers.collect_modifiers``.

    ``target``: ``attack``, ``damage``, ``ac``, ``speed``, ``initiative``, ``save``, ``skill``, ``passive``,
    ``hp_max`` (somme); ``advantage``, ``disadvantage``, ``auto_fail``, ``note`` (segnali, ``value`` ignorato);
    ``sense:<tipo>`` (senso con portata in piedi, vale il maggiore: ``sense:blindsight``); ``jump_bonus`` (piedi in più al
    salto in lungo con rincorsa, si sommano); ``min_d20``, ``crit_min`` (soglie); ``min_total`` (totale minimo di una prova); ``crit_dice`` (dadi dell'arma in più
    al critico); ``resistance:<tipo>``, ``immunity:<tipo>``, ``vulnerability:<tipo>`` (``all`` = ogni tipo);
    ``damage_reroll`` (i dadi dell'arma che mostrano al più questo valore si ritirano una volta: Combattere con Armi
    Possenti); ``damage_min_die`` (i dadi dell'arma che mostrano meno contano questo valore: Armi a Due Mani 2024); ``half_prof``; ``speed_zero``, ``speed_half``, ``hp_max_half``; ``carry_double`` (capacità di carico doppia);
    ``fly_speed`` (velocità di volo pari a quella a terra); ``climb_speed`` e ``swim_speed`` (idem per scalare e nuotare); ``fly_speed_value`` (velocità di volo fissa, in piedi: vale la
    maggiore fra i valori e quella a terra se c'è ``fly_speed``).
    ``when`` limita l'effetto (di solito su ``ctx.roll``); senza, vale sempre."""
    target: str
    value: "Callable[[RuleContext], int] | int"
    when: "Callable[[RuleContext], bool] | None" = None
    source: str = ""


# slot di turno -> chiave booleana in ``Character.turn_state``
TURN_FLAGS = {
    "action": "action_used",
    "bonus": "bonus_used",
    "reaction": "reaction_used",
    "free_interaction": "free_interaction_used",
    "spell_slot": "spell_slot_cast",
    "bonus_spell": "bonus_spell_cast",
}


@dataclass(frozen=True)
class Cost:
    """Costo di un'opzione al tiro: usi della riga ``feature_key``, uno slot di livello almeno ``spell_slot_min`` e/o lo
    stato attivo ``state_key``, che si chiude (e il rimborso rimette com'era)."""
    feature_key: str | None = None
    amount: int = 1
    spell_slot_min: int | None = None
    state_key: str | None = None
    # Con ``spell_slot_min``: solo uno slot di Patto (Fendente Occulto)
    pact_only: bool = False
    # Costo che dipende dal lancio (Incantesimo Raddoppiato: il livello dell'incantesimo): sostituisce ``amount``
    amount_by: "Callable[[RuleContext], int] | None" = None


@dataclass(frozen=True)
class RollOptionSpec:
    """Conferma al tiro: ciò che l'app non vede lo dichiara il giocatore, il calcolo resta al server.

    ``phase``: ``before`` (prima del d20, del danno da incantesimo o del lancio), ``after_hit`` (dopo il colpo, solo
    attacchi), ``after_damage`` (dadi di danno già visti di ``spell_damage``), ``damage_in`` (danno subito).
    ``rolls``: ``attack``, ``spell_damage``, ``skill``, ``save``, ``initiative``, ``damage_taken``, ``cast`` (il lancio:
    ``/use`` e ``cast_options`` di ``/attack``, ``ctx.spell`` è l'incantesimo). ``available(ctx)``: ciò che l'app sa già.

    ``extra_dice(ctx, inputs) -> "2d6"`` e ``bonus(ctx, inputs) -> int``, dove ``inputs`` è ciò che il giocatore ha
    scelto per l'opzione. Effetto per fase: ``before`` su un attacco, ``bonus`` al colpire e dadi al danno, che
    raddoppiano al critico; ``before`` sugli altri d20, entrambi al totale; ``before`` su ``spell_damage`` e
    ``after_hit``, entrambi al danno; ``damage_in``, entrambi riducono il danno. ``multiplier`` agisce sul danno,
    per difetto; sul danno subito viene prima di resistenza e vulnerabilità.

    ``requires_input="slot"``: il giocatore sceglie ``slot_level`` (con ``cost.spell_slot_min``). ``"recover"``: sceglie
    ``slot_level`` fra gli slot spesi che ``recover_levels(ctx)`` ammette e quello torna disponibile (Divinazione Esperta). ``needs``: un'altra
    opzione da scegliere insieme (+1d8 di Punizione Divina). ``auto_fail``: fallimento automatico confermato.
    ``force_crit``: il colpo a segno è critico (solo ``before``).

    ``group``: una sola opzione del gruppo per richiesta; con ``once_per_turn`` si registra il gruppo, non la chiave.
    ``dice_cost``: dadi tolti all'opzione ``needs`` della stessa richiesta (Colpo Astuto su Attacco Furtivo).
    ``needs`` vale anche per un'opzione confermata prima del tiro di questo attacco (``RuleContext.confirmed``).
    ``crit_doubles=False``: i dadi non raddoppiano al critico. ``separate_damage``: dadi riportati a parte, fuori dal
    totale (seconda creatura). ``on_confirm(session, ctx, inputs)``: effetto collaterale dopo il pagamento, nella
    stessa transazione; è sincrono e ``/hp/undo`` non lo annulla.
    ``after`` (solo ``after_roll``): ``add`` somma al totale, ``reroll`` impone un nuovo d20 (``bonus`` e ``mode``
    valgono su quello), ``succeed`` porta prova o TS a 20 e fa di un attacco un colpo a segno non critico, ``twenty`` porta il d20 a 20 anche in un attacco (colpo critico: Colpo di Fortuna 2024),
    ``miss`` chiude un attacco mancato con il danno ``miss_damage(ctx)`` (Graze).
    ``effect(ctx, inputs) -> {"it": ..., "en": ...}``: esito da mostrare al giocatore (CD, durata).
    ``target_effect(ctx, inputs) -> TargetEffect``: effetto sul combattente scelto; confermata l'opzione, il server lo tiene
    in ``turn_state["target_effects"][key]`` finché il giocatore lo applica (``POST /characters/{id}/target-effects``).
    ``second_attack``: i dadi ``separate_damage`` valgono per un secondo tiro per colpire, fatto dal server (Cleave).
    ``pay_if_success``: si rimborsa se il tiro resta fallito. ``replace_die`` (solo ``before``): il d20 è uno dei
    valori di ``Character.settings["saved_dice"][key]``, dichiarato con ``{"die": n}`` e consumato.
    ``cancels``: la conferma toglie il vantaggio o lo svantaggio dato da quelle fonti, lasciando le altre.
    ``reroll_dice(ctx, inputs) -> n`` (obbligatorio in ``after_damage``): quanti dadi di danno ritirare, scelti dal
    giocatore. ``keep_rolled``: solo dadi al massimo, il nuovo si somma invece di sostituire (Bombardamento Magico)."""
    key: str
    phase: Literal["before", "after_roll", "after_hit", "after_damage", "damage_in"]
    rolls: tuple[str, ...]
    label: dict[str, str]
    available: "Callable[[RuleContext], bool]" = lambda _ctx: True
    extra_dice: "Callable[[RuleContext, dict], str] | None" = None
    bonus: "Callable[[RuleContext, dict], int] | None" = None
    mode: Literal["advantage", "disadvantage"] | None = None
    cost: Cost | None = None
    once_per_turn: bool = False
    slot: str | None = None
    multiplier: float | None = None
    requires_input: Literal["slot", "recover"] | None = None
    needs: str | None = None
    auto_fail: bool = False
    force_crit: bool = False
    group: str | None = None
    # Quante opzioni del gruppo si possono scegliere insieme: ``f(ctx) -> n`` (Colpo Brutale: 1 effetto, 2 dal 17°); default 1
    group_max: "Callable[[RuleContext], int] | None" = None
    dice_cost: int = 0
    # Scelta ``before`` che apre opzioni ``after_hit`` oggi non in elenco (Attacco Irruento → Frenesia, Colpo Brutale):
    # il client fa aspettare il danno anche se nessun'altra opzione lo rinvia.
    defers_damage: bool = False
    crit_doubles: bool = True
    separate_damage: bool = False
    on_confirm: "Callable[[Any, RuleContext, dict], None] | None" = None
    # PF temporanei per un'altra creatura della serata: ``f(ctx, inputs) -> n``. Con ``target_character_id`` fra gli input il server
    # li consegna (``deliver_temp_gifts``), senza resta l'esito scritto (Passo Rinfrescante su un altro, Incantesimi Potenti)
    temp_hp_gift: "Callable[[RuleContext, dict], int] | None" = None
    after: Literal["add", "reroll", "succeed", "twenty", "miss"] | None = None
    pay_if_success: bool = False
    replace_die: bool = False
    miss_damage: "Callable[[RuleContext], int] | None" = None
    miss_damage_adds: bool = False  # il danno al mancato si somma a quello di Graze invece di valere il maggiore dei due (Freccia Folgorante)
    on_miss: bool = False  # si arma con ogni mancato dichiarato (anche da Graze o dal pulsante «Mancato»)
    # Offerta agli altri partecipanti della serata, non a chi possiede il privilegio: l'opzione compare sul tiro del ricevente
    # (``available`` guarda lui; ``{donor}`` nel label è il nome del donatore) e il costo si spende sulla scheda del donatore.
    for_ally: bool = False
    effect: "Callable[[RuleContext, dict], dict[str, str]] | None" = None
    second_attack: bool = False
    target_effect: "Callable[[RuleContext, dict], TargetEffect] | None" = None
    reroll_dice: "Callable[[RuleContext, dict], int] | None" = None
    keep_rolled: bool = False
    self_heal: "Callable[[RuleContext, dict], int] | None" = None  # PF che chi lancia recupera (``spell_healing``, o l'iniziativa: lo applica il router del tiro)
    cancels: tuple[str, ...] = ()  # fonti di vantaggio o svantaggio (`condition:<slug>`) tolte dal tiro
    maximize: bool = False  # i dadi di danno dell'incantesimo valgono il massimo (solo ``before`` su ``spell_damage``)
    maximize_types: tuple[str, ...] = ()  # tipi di danno che la massimizzazione tocca; vuoto = tutti (i dadi a mano mai)
    # L'attacco che l'opzione apre non è dell'azione Attacco, anche senza uno slot proprio (i colpi della Raffica di Colpi,
    # pagati da uno stato): non pesa sul limite di attacchi dell'azione.
    outside_action: bool = False
    # Dopo un danno subito l'app propone questa reazione d'attacco? ``None``: sì se ha lo slot ``reaction`` (Ritorsione,
    # Replica); ``False`` per le reazioni che nascono da un altro evento (Opportunista).
    offered_on_damage: bool | None = None
    # L'attacco è un lancio a distanza senz'armi con il profilo dell'artista marziale (Destrezza, dado di Arti Marziali):
    # il proiettile afferrato con Deviare Proiettili. Sceglierla cambia la modalità del colpo senz'armi.
    ranged_unarmed: bool = False
    # Con ``damage_in``: chiamata se, applicata l'opzione, il danno scende a 0 (il proiettile deviato si afferra)
    on_zero_damage: "Callable[[Any, RuleContext], None] | None" = None
    # Si applica da sola a ogni tiro in cui è disponibile, senza scelta né costo, e non si elenca al giocatore (Punizione
    # Divina Migliorata): vale per le fasi che il server percorre da solo, quindi ``before``.
    automatic: bool = False
    # Con ``damage_in``: se il danno porta a 0 PF senza uccidere sul colpo, il personaggio resta a 1 PF (Sentinella
    # Imperitura). Il costo si rimborsa se il danno non arriva a 0.
    holds_at_one: bool = False
    # Con ``holds_at_one``: vale anche per il danno massiccio, che il manuale non esclude (Interdizione alla Morte)
    holds_vs_massive: bool = False
    # Con ``holds_at_one``: PF che si recuperano oltre al 1 PF (Sentinella Imperitura 2024: 3 x livello da paladino)
    holds_heal: "Callable[[RuleContext], int] | None" = None
    # Danno che l'opzione fa a chi la usa, come ``f(ctx, inputs) -> "NdM"`` o ``None`` (Saturazione Magica: necrotico, ignora
    # resistenze e immunità). Lo tira e lo applica il router del tiro, dopo il pagamento dell'opzione.
    self_damage: "Callable[[RuleContext, dict], str | None] | None" = None
    self_damage_type: str = "necrotic"
    # Con ``requires_input="recover"``: i livelli degli slot spesi che l'opzione può restituire adesso
    recover_levels: "Callable[[RuleContext], list[int]] | None" = None
    # Con ``damage_in``: l'opzione dà resistenza al danno. Conta una volta sola: se la scheda ne ha già una non cambia nulla
    # (un ``multiplier`` invece si somma a ogni altra riduzione).
    grants_resistance: bool = False
    # Con ``skill``: la prova si fa con un'altra caratteristica (Conoscenza Primordiale: Forza al posto di Destrezza)
    ability_override: str | None = None
    # Con ``attack``: il Colpo Senz'Armi infligge questi dadi più Destrezza al posto del danno normale (Danno Bardico);
    # ``f(ctx, inputs) -> "NdM"``
    unarmed_dice: "Callable[[RuleContext, dict], str] | None" = None
    # Con ``attack`` senz'armi: tipo di danno scelto al posto di quello normale (Colpi Potenziati del Monaco 2024: Forza)
    unarmed_damage_type: str | None = None
    # Con ``attack`` senz'armi e ``unarmed_dice``: arma Accurata, la caratteristica è la migliore fra Forza e Destrezza per
    # colpire e per il danno (Lame Psichiche del Coltello dell'Anima)
    finesse_unarmed: bool = False
    # Con ``spell_damage`` prima del tiro: il tipo di danno dell'incantesimo diventa questo (Incantesimo Trasmutato)
    damage_type_to: str | None = None
    # Tipo di danno dei dadi che l'opzione aggiunge (``extra_dice``): arriva nel blocco dell'esito (``extra_types``), per chi lo legge
    extra_damage_type: str | None = None
    # Con ``after_hit``: confermarla lancia un incantesimo a concentrazione (punizioni 2024): il server avvia la concentrazione di
    # ``ctx.spell_data["spell_id"]`` per questi round
    starts_concentration: int | None = None

    def __post_init__(self) -> None:
        if self.phase not in ("before", "after_roll", "after_hit", "after_damage", "damage_in"):
            raise ValueError(f"fase sconosciuta: {self.phase}")
        if (self.phase == "after_roll") != (self.after in ("add", "reroll", "succeed", "twenty", "miss")):
            raise ValueError("after è obbligatorio in after_roll e vale solo lì")
        if self.phase == "after_roll" and self.requires_input:
            raise ValueError("after_roll è un pulsante nel modale di esito: non chiede input")
        if self.pay_if_success and self.phase not in ("after_roll", "before"):
            raise ValueError("pay_if_success vale solo prima o dopo il tiro")
        if self.replace_die and (self.phase != "before" or self.requires_input):
            raise ValueError("replace_die vale solo prima del tiro e il suo input è il dado salvato")
        if self.slot is not None and self.slot not in TURN_FLAGS:
            raise ValueError(f"slot sconosciuto: {self.slot}")
        if self.requires_input not in (None, "slot", "recover"):
            raise ValueError(f"input sconosciuto: {self.requires_input}")
        if (self.requires_input == "recover") != (self.recover_levels is not None):
            raise ValueError("recover e recover_levels vanno insieme")
        if self.force_crit and self.phase != "before":
            raise ValueError("force_crit vale solo prima del tiro")
        if self.cost and self.cost.spell_slot_min is not None and self.requires_input != "slot":
            raise ValueError("uno slot come costo richiede requires_input='slot'")
        if (self.after == "miss") != (self.miss_damage is not None):
            raise ValueError("after='miss' e miss_damage vanno insieme")
        if self.second_attack and not self.separate_damage:
            raise ValueError("second_attack riguarda i dadi separate_damage")
        if (self.phase == "after_damage") != (self.reroll_dice is not None):
            raise ValueError("after_damage e reroll_dice vanno insieme")
        if self.phase == "after_damage" and self.requires_input:
            raise ValueError("after_damage non chiede input: il client manda sempre option_inputs vuoto")
        if self.keep_rolled and self.reroll_dice is None:
            raise ValueError("keep_rolled riguarda reroll_dice")
        if self.self_heal and not ({"spell_healing", "initiative", "death_save"} & set(self.rolls)
                                   or (self.phase == "after_hit" and "attack" in self.rolls)):
            raise ValueError("self_heal vale solo per la cura di un incantesimo, l'iniziativa (Metabolismo Prodigioso), il TS contro la morte "
                             "(Vendetta Ardente) o il danno dopo un colpo (Succhiavita)")
        if self.maximize and (self.phase != "before" or "spell_damage" not in self.rolls):
            raise ValueError("maximize vale solo prima del danno di un incantesimo")
        if self.self_damage and self.phase != "before":
            raise ValueError("self_damage vale solo prima del tiro")
        if self.dice_cost and not self.needs:
            raise ValueError("dice_cost toglie dadi all'opzione indicata da needs")
        if self.damage_type_to and (self.phase != "before" or "spell_damage" not in self.rolls):
            raise ValueError("damage_type_to vale solo prima del danno di un incantesimo")
        if self.on_zero_damage and self.phase != "damage_in":
            raise ValueError("on_zero_damage vale solo per il danno subito")
        if self.outside_action and self.phase != "before":
            raise ValueError("outside_action vale solo prima del tiro: apre un attacco")
        if self.automatic and (self.phase != "before" or self.cost or self.requires_input or self.slot or self.needs):
            raise ValueError("automatic vale solo prima del tiro e senza costo, input, slot né dipendenze")


@dataclass(frozen=True)
class ZeroHpSave:
    """A 0 PF senza morte istantanea, con lo stato ``state`` attivo, tiro salvezza automatico (Ira Implacabile).

    CD = ``base_dc`` + ``step`` per ogni uso già fatto; se riesce i PF tornano a ``hp(ctx)``. Gli usi si azzerano con un
    riposo (breve o lungo)."""
    state: str
    ability: str = "constitution"
    base_dc: int = 10
    step: int = 5
    hp: "Callable[[RuleContext], int]" = lambda _ctx: 1


@dataclass(frozen=True)
class AuraSpec:
    """Aura che un privilegio proietta sugli alleati seduti alla stessa serata (Aura di Protezione, Aura di Interdizione).

    ``kind``: ``protection`` (bonus ai TS) o ``warding`` (resistenza ai danni degli incantesimi). ``range_ft(ctx)`` e
    ``bonus(ctx)`` valgono per chi la proietta. ``needs_conscious``: l'aura c'è solo se chi la proietta è cosciente.
    L'alleato conferma al tiro di essere nella gittata (D1: l'app non conosce le posizioni)."""
    kind: Literal["protection", "warding"]
    range_ft: "Callable[[RuleContext], int]"
    bonus: "Callable[[RuleContext], int]" = lambda _ctx: 0
    needs_conscious: bool = True


@dataclass(frozen=True)
class FeatureSpec:
    key: str
    class_key: str
    edition: Edition
    level: int
    source_title: str  # titolo esatto della scheda
    name: dict[str, str]
    summary: dict[str, str]
    action_type: str | None
    uses: Uses | None = None
    restoration: str | dict[int, str] = "none"  # dict: livello minimo -> tipo di riposo
    short_rest_recovers: "int | dict[int, int] | None" = None  # dict: livello minimo -> usi recuperati (Ripristino Stregonesco)
    subclass: str | None = None
    option_group: str | None = None
    option_key: str | None = None
    choices: tuple = ()
    modifiers: tuple = ()
    roll_options: tuple = ()
    on_use: Any = None
    passive: bool = False
    cast_in_form: bool = False  # in Forma Selvatica si lanciano incantesimi senza conferma (Incantesimi Bestiali)
    attacks_per_action: int = 0
    attacks_with_pact_weapon: int = 0  # attacchi per azione, ma solo con l'arma del patto (Lama Assetata)
    target_effect: Any = None
    # categoria (`armor`/`weapons`/`tools`) -> id di `core.rules.proficiencies.LABELS`, concesse una volta sola
    proficiency_grants: dict[str, tuple[str, ...]] | None = None
    unarmored: UnarmoredAc | None = None
    granted_spells: tuple[str, ...] = ()  # chiavi di `core.rules.catalog.granted_spells.GRANTED_SPELLS`
    granted_ritual_only: bool = False  # gli incantesimi concessi si lanciano solo come rituale (Cercatore di Spiriti)
    condition_immunities: tuple[str, ...] = ()  # condizioni che il privilegio impedisce sempre (Interdizione della Natura)
    needs_conscious: bool = False  # ``condition_immunities`` valgono solo con il personaggio cosciente (Aura di Coraggio)
    ignores_components: bool = False  # Arcidruido: le componenti V, S e M senza costo non servono
    at_will_spells: tuple[str, ...] = ()  # ``srd_index`` degli incantesimi lanciabili a volontà, senza slot (Mille Forme)
    acts_when_surprised: str | None = None  # 2014: con quello stato attivo il turno da sorpreso non toglie le azioni
    zero_hp_save: ZeroHpSave | None = None
    # PF che il privilegio cura all'inizio di ogni turno di chi lo ha (Sopravvissuto); 0 se la condizione non c'è
    turn_start_heal: "Callable[[RuleContext], int] | None" = None
    # Ispirazione Eroica a inizio turno, solo in un incontro, se non c'è già (Guerriero Eroico del Campione 2024)
    turn_start_inspiration: bool = False
    # punteggio -> bonus, con massimo `ability_cap`: scritto sul punteggio dal sync, tolto se il privilegio sparisce
    ability_bonus: dict[str, int] | None = None
    ability_cap: int = 20
    # caratteristica della CD dei tiri salvezza del privilegio (8 + competenza + modificatore): la riga la mostra (ki del Monaco)
    dc_ability: str | None = None
    magic_unarmed: bool = False  # i colpi senz'armi contano come magici (Colpi Ki Potenziati)
    unarmed_die: str | None = None  # dado minimo del colpo senz'armi (Attaccabrighe da taverna: 1d4); vale il migliore
    # una volta per turno i dadi dell'arma si tirano due volte, vale il migliore (Attaccante selvaggio); "melee": solo in mischia (2014)
    weapon_damage_twice: bool | str = False
    ki_spells: tuple = ()  # ``KiSpell`` che il privilegio fa lanciare coi punti invece degli slot
    # Fine di un riposo lungo: lo stato che il privilegio avvia da solo (Tranquillità); ``f(ctx) -> StateSpec | None``
    long_rest_state: "Callable[[RuleContext], StateSpec | None] | None" = None
    # Stato sempre attivo finché il privilegio c'è (Purezza di Spirito): lo mette il sync, che lo toglie se il privilegio sparisce;
    # il suo ``data`` porta ``permanent: True``
    permanent_state: "StateSpec | None" = None
    aura: "AuraSpec | None" = None  # aura proiettata sugli alleati della serata (vedi ``core.rules.auras``)
    # Riserva che due classi condividono (Incanalare Divinità di Chierico e Paladino): una seconda classe non aggiunge usi, ne
    # tiene la riga la classe che ne dà di più (a parità la prima); gli effetti di entrambe spendono quella riga
    shared_pool: str | None = None
    # Il privilegio non vale con il personaggio incapacitato (Inafferrabile): la sua nota per GM e gruppo si nasconde
    suspended_when_incapacitated: bool = False
    no_row: bool = False  # solo catalogo: nessuna riga Ability sulla scheda (regole generali, scelte di livello)
    # dove è coperta una riga senza `Ability` che la mappatura vuole da implementare o correggere: `lavori-successivi`
    # (fuori dai cataloghi, R32) oppure il punto del codice o del test; `check_catalog` lo pretende insieme a `no_row`
    covered_by: str | None = None
    # Supplica che dà un incantesimo da lanciare una volta per riposo lungo con uno slot di Patto (``srd_index``): il lancio
    # spende un uso di questa riga (vedi ``core.rules.pact_casts``)
    pact_spell: str | None = None
    # Arcanum Mistico: gruppo di ``ChoiceSpec`` in cui sta l'incantesimo scelto; si lancia senza slot spendendo un uso
    arcanum_group: str | None = None
    # Il privilegio fa lanciare come rituale gli incantesimi rituali della classe (Libro degli Antichi Segreti)
    ritual_casting: bool = False
    # Gittata che il privilegio dà a un incantesimo: ``((srd_index o nome minuscolo, ...), testo)`` (Lancia Occulta: 90 m)
    spell_range: "tuple[tuple[str, ...], str] | None" = None
    # Metri di gittata in piu per livello della classe a un incantesimo che la ha di almeno 3 m: ``((nomi in minuscolo...), metri)`` (Lancia Occulta)
    spell_range_per_level: "tuple[tuple[str, ...], int] | None" = None
    # Scuola che dimezza tempo e costo della copia nel Libro del Mago (i «Sapienti» delle otto scuole)
    copy_school: str | None = None
    # Incantesimo (``srd_index``) lanciabile senza slot spendendo un uso di questa riga, come l'Arcanum (Mutaforma)
    free_spell: str | None = None
    # PF temporanei a chi finisce un riposo breve o lungo (Resilienza Celestiale): ``f(ctx) -> n``, vale il maggiore con quelli attuali
    rest_temp_hp: "Callable[[RuleContext], int] | None" = None
    # Come ``rest_temp_hp`` ma per altre creature della serata: ``f(ctx) -> (quante, PF temporanei per ciascuna)`` (Resilienza Celestiale)
    rest_temp_hp_ally: "Callable[[RuleContext], tuple[int, int]] | None" = None
    # Resistenza che si sceglie quando finisci un riposo, breve o lungo (Resilienza Immonda): ``(chiave dello stato, tipi di danno ammessi)``;
    # la scelta arriva col riposo (``RestRequest.fiendish_resilience``) e lo stato dura finché non se ne sceglie un'altra
    rest_damage_choice: "tuple[str, tuple[str, ...]] | None" = None
    # Dadi d20 tirati alla fine del riposo lungo e salvati (R29, Portento): ``(chiave dell'opzione, f(ctx) -> quanti)``
    long_rest_dice: "tuple[str, Callable[[RuleContext], int]] | None" = None
    # Incantesimi (``GRANTED_SPELLS``) che il privilegio aggiunge al Libro del Mago senza prepararli (Servitori Non Morti, Mutaforma)
    book_spells: tuple[str, ...] = ()
    # I PF massimi non si riducono (Impervio alla Non Morte): nemmeno la spossatezza li dimezza
    hp_max_locked: bool = False
    # Chi supera il TS contro un tuo trucchetto di danno ne subisce comunque la metà (Trucchetto Potente)
    save_half_cantrips: bool = False
    # Scuole di incantesimi su cui il danno non fa tirare la concentrazione (Evocazione Focalizzata)
    concentration_safe_schools: tuple[str, ...] = ()
    # ``srd_index`` degli incantesimi su cui il danno non fa tirare la concentrazione (Cacciatore Implacabile: Hunter's Mark)
    concentration_safe_spells: tuple[str, ...] = ()
    # Ogni riposo breve toglie un livello di Sfinimento (Instancabile del Ranger 2024)
    short_rest_exhaustion: bool = False
    # Gruppi di ``ChoiceSpec`` i cui incantesimi scelti si lanciano a volontà al livello base se preparati (Maestria)
    mastery_groups: tuple[str, ...] = ()
    # Il tiro per colpire dei Colpi Senz'Armi usa la Destrezza se è migliore, ma solo senza armatura né Scudo (Passo Abbagliante)
    dex_unarmed: bool = False
    # Metri in più alla gittata (3 m o più) dei trucchetti della classe che ha il privilegio (Incantesimi Potenti del Druido, 15°)
    cantrip_range_bonus: int = 0
    # Incantesimi (``srd_index``) che si lanciano in Forma Selvatica senza avviso, solo questi (Incantesimi del Circolo della Luna)
    cast_in_form_spells: tuple[str, ...] = ()
    # Gli incantesimi di questa scuola non hanno componente Verbale e, con gittata di 3 m o più, hanno ``metri`` in più: ``(scuola, m)``
    # (Illusioni Migliorate)
    school_boost: "tuple[str, int] | None" = None
    # ``(scuola, srd_index...)``: questi incantesimi, per chi ha il privilegio, contano della scuola indicata (Creature Fantasmatiche)
    school_as: "tuple[str, tuple[str, ...]] | None" = None
    # ``srd_index`` degli incantesimi da un'azione che il privilegio fa lanciare con un'azione bonus (Rompi-Incantesimi: Dissolvi Magie)
    bonus_cast_spells: tuple[str, ...] = ()
    # Trucchetto Potente 2024: anche il trucchetto con tiro per colpire che manca fa metà danno, non solo quello con TS superato
    cantrip_half_on_miss: bool = False


@dataclass(frozen=True)
class RuleContext:
    char: Any
    edition: Edition
    class_row: Any = None
    class_level: int = 0
    roll: Any = None
    ability: Any = None
    skill: Any = None
    item: Any = None
    spell: Any = None
    turn: Any = None
    damage_type: Any = None
    attack_mode: Any = None  # solo attacchi: `melee`, `thrown` o `ranged`
    grip: Any = None  # solo attacchi: `one` o `two`
    offhand: bool = False  # solo attacchi: l'attacco extra della proprietà Leggera
    casting_level: int | None = None  # ``spell_healing`` e ``cast``: il livello dello slot con cui si lancia
    slotless: bool = False  # solo ``cast``: lancio gratuito o rituale, senza slot
    confirmed: tuple = ()  # opzioni già confermate per questo attacco, nel primo tempo
    damage: int | None = None  # solo ``damage_taken``: il danno che il giocatore sta per inserire, se lo sa
    damage_in: int | None = None  # solo ``damage_taken`` al danno vero: serve ai testi (cosa riflettere), mai alla disponibilità
    proficient: bool = False  # prova già con competenza (strumento): niente mezze competenze («Atleta Straordinario»)
    spell_data: Any = None  # opzione di uno stato ``spell:*``: i ``data`` di quello stato (scelte, livello dello slot)

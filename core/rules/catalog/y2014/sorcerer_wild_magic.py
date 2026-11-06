"""Tabella degli Impulsi di Magia Selvaggia (Stregone 2014, Magia Selvaggia 1): 50 risultati d100 in coppie.

Scheda ``docs/superpowers/rules/2014/classes/sorcerer.md``; i testi sono nostri, brevi, mai quelli del manuale. Ogni risultato dice
cosa l'app applica da sola (``heal``, ``heal_each_turn``, ``slot``, ``points``, ``action``, ``ac``, ``resist_all``) e cosa tira e
mostra (``damage``, ``roll``, ``dc``); le condizioni su di sé (``condition``) e le vulnerabilità (``vulnerable``) le applica lo stato; il resto è testo con un timer (``rounds``) quando dura un minuto o fino al turno seguente.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Surge:
    lo: int
    hi: int
    name: dict[str, str]
    text: dict[str, str]
    rounds: int | None = None  # durata dello stato mostrato (10 round = 1 minuto); ``None`` = nessun timer
    next_turn: bool = False  # lo stato finisce al «Nuovo turno» seguente invece che a tempo
    heal: str | None = None  # dadi di cura applicati subito
    heal_each_turn: int = 0  # PF recuperati all'inizio di ogni turno finché dura lo stato
    slot: bool = False  # restituisce lo slot speso di livello più basso
    points: bool = False  # restituisce tutti i punti stregoneria
    action: bool = False  # un'azione in più, subito
    ac: int = 0  # bonus alla CA finché dura lo stato
    resist_all: bool = False  # resistenza a ogni danno finché dura lo stato
    damage: tuple[str, str] | None = None  # (dadi, tipo): tirati e mostrati
    roll: str | None = None  # un dado tirato e mostrato (altezza, età, giorni, ore)
    dc: bool = False  # l'effetto è un incantesimo con TS: si mostra la CD dello stregone
    state_key: str | None = None  # chiave dello stato, se non è quella delle altre regole (condizione, vulnerabilità, ripetizione)
    condition: str | None = None  # condizione che lo stato imposta finché dura (incapacitato, spaventato, invisibile)
    vulnerable: str | None = None  # ``all`` o un tipo di danno: vulnerabilità finché dura lo stato
    ends_on_act: bool = False  # lo stato finisce se chi lo porta attacca o lancia un incantesimo
    key: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", f"wild_surge_{self.lo}")

    @property
    def label(self) -> str:
        return f"{self.lo:02d}-{self.hi % 100:02d}"


def _s(lo: int, it: str, en: str, text_it: str, text_en: str, **kw) -> Surge:
    return Surge(lo, lo + 1, {"it": it, "en": en}, {"it": text_it, "en": text_en}, **kw)


MINUTE = 10  # round

SURGES: tuple[Surge, ...] = (
    _s(1, "Ripetizione", "Repeat", "Per un minuto tiri sulla tabella all'inizio di ogni tuo turno, ignorando questo risultato.",
       "For one minute you roll on the table at the start of each of your turns, ignoring this result.", rounds=MINUTE, state_key="wild_repeat"),
    _s(3, "Vista dell'invisibile", "See invisible", "Per un minuto vedi le creature invisibili in linea di vista.",
       "For one minute you see invisible creatures in line of sight.", rounds=MINUTE),
    _s(5, "Modron", "Modron", "Un modron scelto dal GM compare entro 1,5 m e svanisce dopo un minuto.",
       "A modron chosen by the GM appears within 5 ft and vanishes after one minute.", rounds=MINUTE),
    _s(7, "Palla di fuoco", "Fireball", "Lanci palla di fuoco di 3° livello centrata su di te: TS Destrezza contro la tua CD.",
       "You cast fireball at 3rd level centered on yourself: Dexterity save against your DC.", dc=True),
    _s(9, "Dardo incantato", "Magic missile", "Lanci dardo incantato di 5° livello.", "You cast magic missile at 5th level."),
    _s(11, "Altezza", "Height", "L'altezza cambia di 2,5 cm per punto del d10: dispari rimpicciolisci, pari cresci.",
       "Your height changes by 1 inch per point of the d10: odd shrinks you, even makes you grow.", roll="1d10"),
    _s(13, "Confusione", "Confusion", "Lanci confusione centrata su di te: TS Saggezza contro la tua CD.",
       "You cast confusion centered on yourself: Wisdom save against your DC.", dc=True),
    _s(15, "Rigenerazione", "Regeneration", "Per un minuto recuperi 5 PF all'inizio di ogni tuo turno.",
       "For one minute you regain 5 hit points at the start of each of your turns.", rounds=MINUTE, heal_each_turn=5),
    _s(17, "Barba di piume", "Feather beard", "Ti spunta una barba di piume fino al prossimo starnuto: poi esplode senza danni.",
       "A beard of feathers grows until your next sneeze, when it bursts harmlessly."),
    _s(19, "Unto", "Grease", "Lanci unto centrato su di te: TS Destrezza contro la tua CD.",
       "You cast grease centered on yourself: Dexterity save against your DC.", dc=True),
    _s(21, "Svantaggio ai TS", "Save disadvantage", "Le creature hanno svantaggio ai TS contro il prossimo incantesimo con TS che lanci in un minuto.",
       "Creatures have disadvantage on saves against the next spell with a save you cast within one minute.", rounds=MINUTE),
    _s(23, "Pelle azzurra", "Blue skin", "La tua pelle diventa azzurra; rimuovi maledizione la annulla.",
       "Your skin turns blue; remove curse ends it."),
    _s(25, "Terzo occhio", "Third eye", "Un occhio sulla fronte: per un minuto vantaggio alle prove di Percezione basate sulla vista.",
       "An eye on your forehead: for one minute advantage on Perception checks that rely on sight.", rounds=MINUTE),
    _s(27, "Magia rapida", "Quick magic", "Per un minuto gli incantesimi da 1 azione hanno tempo di lancio di azione bonus.",
       "For one minute spells with a casting time of 1 action cast as a bonus action.", rounds=MINUTE),
    _s(29, "Teletrasporto", "Teleport", "Ti teletrasporti fino a 18 m in uno spazio libero che vedi.",
       "You teleport up to 60 ft to an unoccupied space you can see."),
    _s(31, "Piano Astrale", "Astral Plane", "Sei sul Piano Astrale fino alla fine del tuo prossimo turno, poi torni dove eri.",
       "You are on the Astral Plane until the end of your next turn, then return where you were.", rounds=2, next_turn=True),
    _s(33, "Danni massimi", "Maximized damage", "Il prossimo incantesimo a danni che lanci entro un minuto fa il massimo dei danni.",
       "The next damaging spell you cast within one minute deals maximum damage.", rounds=MINUTE),
    _s(35, "Età", "Age", "L'età cambia degli anni del d10: dispari ringiovanisci (minimo 1 anno), pari invecchi.",
       "Your age changes by the d10 in years: odd makes you younger (minimum 1 year), even older.", roll="1d10"),
    _s(37, "Flumph", "Flumphs", "Compaiono 1d6 flumph entro 18 m, spaventati da te; svaniscono dopo un minuto.",
       "1d6 flumphs appear within 60 ft, frightened of you; they vanish after one minute.", rounds=MINUTE, roll="1d6"),
    _s(39, "Cura", "Healing", "Recuperi 2d10 punti ferita.", "You regain 2d10 hit points.", heal="2d10"),
    _s(41, "Pianta in vaso", "Potted plant", "Diventi una pianta in vaso fino all'inizio del tuo prossimo turno: incapacitato e vulnerabile a ogni danno.",
       "You become a potted plant until the start of your next turn: incapacitated and vulnerable to all damage.", rounds=2, next_turn=True,
       state_key="wild_vulnerable_all", condition="incapacitated", vulnerable="all"),
    _s(43, "Passo breve", "Short step", "Per un minuto puoi teletrasportarti di 6 m con un'azione bonus a ogni turno.",
       "For one minute you can teleport 20 ft as a bonus action on each of your turns.", rounds=MINUTE),
    _s(45, "Levitazione", "Levitation", "Lanci levitazione su di te.", "You cast levitate on yourself."),
    _s(47, "Unicorno", "Unicorn", "Un unicorno del GM compare entro 1,5 m e svanisce dopo un minuto.",
       "A unicorn of the GM appears within 5 ft and vanishes after one minute.", rounds=MINUTE),
    _s(49, "Bolle rosa", "Pink bubbles", "Per un minuto non puoi parlare: dalla bocca escono bolle rosa.",
       "For one minute you cannot speak: pink bubbles come out of your mouth.", rounds=MINUTE),
    _s(51, "Scudo spettrale", "Spectral shield", "Per un minuto uno scudo spettrale dà +2 alla CA e immunità a dardo incantato.",
       "For one minute a spectral shield gives +2 AC and immunity to magic missile.", rounds=MINUTE, ac=2),
    _s(53, "Sobrietà", "Sobriety", "Sei immune all'intossicazione alcolica per 5d6 giorni.",
       "You are immune to alcohol intoxication for 5d6 days.", roll="5d6"),
    _s(55, "Calvizie", "Baldness", "Perdi tutti i capelli, che ricrescono in 24 ore.", "You lose all your hair; it grows back in 24 hours."),
    _s(57, "Mani infuocate", "Fiery hands", "Per un minuto gli oggetti infiammabili che tocchi, non indossati né portati, prendono fuoco.",
       "For one minute flammable objects you touch, neither worn nor carried, catch fire.", rounds=MINUTE),
    _s(59, "Slot ritrovato", "Slot regained", "Recuperi lo slot incantesimo speso di livello più basso.",
       "You regain your lowest expended spell slot.", slot=True),
    _s(61, "Grida", "Shouting", "Per un minuto devi gridare quando parli.", "For one minute you must shout when you speak.", rounds=MINUTE),
    _s(63, "Nube di nebbia", "Fog cloud", "Lanci nube di nebbia centrata su di te.", "You cast fog cloud centered on yourself."),
    _s(65, "Fulmini", "Lightning", "Fino a tre creature entro 9 m subiscono 4d10 danni da fulmine.",
       "Up to three creatures within 30 ft take 4d10 lightning damage.", damage=("4d10", "lightning")),
    _s(67, "Paura", "Fear", "Sei spaventato dalla creatura più vicina fino alla fine del tuo prossimo turno.",
       "You are frightened of the nearest creature until the end of your next turn.", rounds=2, next_turn=True,
       state_key="wild_frightened", condition="frightened"),
    _s(69, "Invisibilità di gruppo", "Group invisibility", "Ogni creatura entro 9 m è invisibile per un minuto: finisce se attacca o lancia incantesimi.",
       "Each creature within 30 ft is invisible for one minute; it ends if it attacks or casts a spell.", rounds=MINUTE),
    _s(71, "Resistenza", "Resistance", "Per un minuto hai resistenza a tutti i danni.", "For one minute you have resistance to all damage.",
       rounds=MINUTE, resist_all=True),
    _s(73, "Veleno", "Poison", "Una creatura a caso entro 18 m è avvelenata per 1d4 ore.",
       "A random creature within 60 ft is poisoned for 1d4 hours.", roll="1d4"),
    _s(75, "Luce abbagliante", "Dazzling light", "Per un minuto luce intensa entro 9 m: chi finisce il turno entro 1,5 m è accecato fino alla fine del suo turno seguente.",
       "For one minute bright light within 30 ft: whoever ends a turn within 5 ft is blinded until the end of their next turn.", rounds=MINUTE),
    _s(77, "Metamorfosi", "Polymorph", "Lanci metamorfosi su di te: se fallisci il TS Saggezza (CD tua) diventi una pecora per la durata.",
       "You cast polymorph on yourself: if you fail the Wisdom save (your DC) you become a sheep for the duration.", dc=True),
    _s(79, "Farfalle", "Butterflies", "Per un minuto farfalle e petali illusori riempiono l'aria entro 3 m.",
       "For one minute illusory butterflies and petals fill the air within 10 ft.", rounds=MINUTE),
    _s(81, "Azione extra", "Extra action", "Hai subito un'azione aggiuntiva.", "You immediately take an additional action.", action=True),
    _s(83, "Drenaggio", "Drain", "Ogni creatura entro 9 m subisce 1d10 danni necrotici; recuperi PF pari al totale inflitto.",
       "Each creature within 30 ft takes 1d10 necrotic damage; you regain hit points equal to the total dealt.", damage=("1d10", "necrotic")),
    _s(85, "Immagine speculare", "Mirror image", "Lanci immagine speculare.", "You cast mirror image."),
    _s(87, "Volo altrui", "Borrowed flight", "Lanci volare su una creatura a caso entro 18 m.", "You cast fly on a random creature within 60 ft."),
    _s(89, "Silenzio invisibile", "Silent invisibility", "Per un minuto sei invisibile e non udibile: finisce se attacchi o lanci incantesimi.",
       "For one minute you are invisible and inaudible; it ends if you attack or cast a spell.", rounds=MINUTE,
       state_key="wild_invisible", condition="invisible", ends_on_act=True),
    _s(91, "Ritorno in vita", "Return to life", "Se muori entro un minuto torni in vita come con reincarnazione.",
       "If you die within one minute you return to life as if by reincarnate.", rounds=MINUTE),
    _s(93, "Taglia maggiore", "Larger size", "Per un minuto la tua taglia aumenta di una categoria.",
       "For one minute your size increases by one category.", rounds=MINUTE),
    _s(95, "Vulnerabilità", "Vulnerability", "Per un minuto tu e le creature entro 9 m siete vulnerabili ai danni perforanti.",
       "For one minute you and creatures within 30 ft are vulnerable to piercing damage.", rounds=MINUTE,
       state_key="wild_vulnerable_piercing", vulnerable="piercing"),
    _s(97, "Musica eterea", "Ethereal music", "Per un minuto una debole musica eterea ti segue.", "For one minute faint ethereal music follows you.",
       rounds=MINUTE),
    _s(99, "Punti ritrovati", "Points regained", "Recuperi tutti i punti stregoneria spesi.", "You regain all spent sorcery points.", points=True),
)

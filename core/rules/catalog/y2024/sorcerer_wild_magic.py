"""Tabella degli Impulsi di Magia Selvaggia (Stregone 2024, Magia Selvaggia 3): 25 risultati d100 in gruppi di quattro.

Scheda ``docs/superpowers/rules/2024/classes/sorcerer.md``; i testi sono nostri, brevi, mai quelli del manuale. Stessa struttura
e stessi campi della tabella 2014 (``Surge``): cosa l'app applica da sola e cosa tira e mostra. I risultati con un dado
interno (creatura, effetto, incantesimo, recupero) tirano quel dado e ne mostrano l'esito sul testo.
"""
from __future__ import annotations

from core.rules.catalog.y2014.sorcerer_wild_magic import MINUTE, Surge


def _s(lo: int, it: str, en: str, text_it: str, text_en: str, **kw) -> Surge:
    return Surge(lo, lo + 3, {"it": it, "en": en}, {"it": text_it, "en": text_en}, **kw)


SURGES: tuple[Surge, ...] = (
    _s(1, "Ripetizione", "Repeat", "Per un minuto tiri sulla tabella all'inizio di ogni tuo turno, ignorando questo risultato.",
       "For one minute you roll on the table at the start of each of your turns, ignoring this result.", rounds=MINUTE, state_key="wild_repeat"),
    _s(5, "Creatura amichevole", "Friendly creature",
       "Compare una creatura amichevole entro 18 m, del GM, per un minuto. 1d4: 1 duodrone, 2 flumph, 3 monodrone, 4 unicorno.",
       "A friendly creature of the GM appears within 60 ft for a minute. 1d4: 1 duodrone, 2 flumph, 3 monodrone, 4 unicorn.",
       rounds=MINUTE, roll="1d4"),
    _s(9, "Rigenerazione", "Regeneration", "Per un minuto recuperi 5 PF all'inizio di ogni tuo turno.",
       "You regain 5 hit points when each of your turns starts, for one minute.", rounds=MINUTE, heal_each_turn=5),
    _s(13, "Svantaggio ai TS", "Save disadvantage", "Le creature hanno svantaggio ai TS contro il prossimo incantesimo con TS che lanci in un minuto.",
       "Creatures have disadvantage on saves against the next spell with a save you cast within one minute.", rounds=MINUTE),
    _s(17, "Effetto bizzarro", "Odd effect",
       "Per un minuto, 1d8: 1 musica, 2 taglia +1, 3 barba di piume, 4 gridi, 5 farfalle, 6 terzo occhio, 7 bolle rosa, 8 pelle azzurra (24 ore).",
       "For a minute, 1d8: 1 music, 2 size +1, 3 feather beard, 4 shouting, 5 butterflies, 6 third eye, 7 pink bubbles, 8 blue skin (24 hours).",
       rounds=MINUTE, roll="1d8"),
    _s(21, "Magia rapida", "Quick magic", "Per un minuto gli incantesimi da 1 azione hanno tempo di lancio di azione bonus.",
       "For one minute spells with a casting time of 1 action cast as a bonus action.", rounds=MINUTE),
    _s(25, "Piano Astrale", "Astral Plane", "Sei sul Piano Astrale fino alla fine del tuo prossimo turno, poi torni dove eri.",
       "You are on the Astral Plane until the end of your next turn, then return where you were.", end_of_next_turn=True),
    _s(29, "Danni massimi", "Maximized damage", "Il prossimo incantesimo a danni che lanci entro un minuto fa il massimo dei danni.",
       "The next damaging spell you cast within one minute deals maximum damage.", rounds=MINUTE),
    _s(33, "Resistenza", "Resistance", "Per un minuto hai resistenza a tutti i danni.", "For one minute you have resistance to all damage.",
       rounds=MINUTE, resist_all=True),
    _s(37, "Pianta in vaso", "Potted plant",
       "Diventi una pianta in vaso fino all'inizio del tuo prossimo turno: incapacitato e vulnerabile a ogni danno; a 0 PF il vaso si rompe.",
       "You become a potted plant until the start of your next turn: incapacitated and vulnerable to all damage; at 0 HP the pot breaks.",
       rounds=2, next_turn=True, state_key="wild_vulnerable_all", condition="incapacitated", vulnerable="all"),
    _s(41, "Passo breve", "Short step", "Per un minuto puoi teletrasportarti di 6 m con un'azione bonus a ogni turno.",
       "For one minute you can teleport 20 ft as a bonus action on each of your turns.", rounds=MINUTE),
    _s(45, "Invisibilità di gruppo", "Group invisibility",
       "Tu e fino a tre creature entro 9 m siete invisibili per un minuto; per ciascuna finisce dopo un attacco, un danno o un incantesimo.",
       "You and up to three creatures within 30 ft are invisible for a minute; for each it ends after an attack roll, damage or a spell.",
       rounds=MINUTE),
    _s(49, "Scudo spettrale", "Spectral shield", "Per un minuto uno scudo spettrale dà +2 alla CA e immunità a dardo incantato.",
       "For one minute a spectral shield gives +2 AC and immunity to magic missile.", rounds=MINUTE, ac=2),
    _s(53, "Azione extra", "Extra action", "Hai subito un'azione aggiuntiva.", "You immediately take an additional action.", action=True),
    _s(57, "Incantesimo casuale", "Random spell",
       "Lanci un incantesimo senza concentrazione, a durata piena. 1d10: confusione, palla di fuoco, nube, volare, unto, levitazione, dardo 5°, immagine, metamorfosi, vedere invisibilità.",
       "You cast a spell with no concentration, for its full duration. 1d10: confusion, fireball, fog, fly, grease, levitate, missile 5th, image, polymorph, see invisibility.",
       roll="1d10", dc=True),
    _s(61, "Mani infuocate", "Fiery hands", "Per un minuto un oggetto infiammabile non magico che tocchi prende fuoco: 1d4 danni da fuoco.",
       "For one minute a flammable nonmagical object you touch catches fire: 1d4 fire damage.", rounds=MINUTE),
    _s(65, "Ritorno in vita", "Return to life", "Se muori entro un'ora torni in vita come con reincarnazione.",
       "If you die within an hour you return to life as if by reincarnate.", rounds=600),
    _s(69, "Paura", "Fear", "Sei spaventato fino alla fine del tuo prossimo turno; il GM sceglie la fonte.",
       "You are frightened until the end of your next turn; the GM picks the source.", end_of_next_turn=True,
       state_key="wild_frightened", condition="frightened"),
    _s(73, "Teletrasporto", "Teleport", "Ti teletrasporti fino a 18 m in uno spazio libero che vedi.",
       "You teleport up to 60 ft to an unoccupied space you can see."),
    _s(77, "Veleno", "Poison", "Una creatura a caso entro 18 m è avvelenata per 1d4 ore.",
       "A random creature within 60 ft is poisoned for 1d4 hours.", roll="1d4"),
    _s(81, "Luce abbagliante", "Dazzling light", "Per un minuto luce intensa entro 9 m: chi finisce il turno entro 1,5 m è accecato fino al suo turno seguente.",
       "For one minute bright light within 30 ft: whoever ends a turn within 5 ft is blinded until the end of their next turn.", rounds=MINUTE),
    _s(85, "Drenaggio", "Drain", "Fino a tre creature entro 9 m subiscono 1d10 danni necrotici; recuperi PF pari al totale inflitto.",
       "Up to three creatures within 30 ft take 1d10 necrotic damage; you regain hit points equal to the total dealt.", damage=("1d10", "necrotic")),
    _s(89, "Fulmini", "Lightning", "Fino a tre creature entro 9 m subiscono 4d10 danni da fulmine.",
       "Up to three creatures within 30 ft take 4d10 lightning damage.", damage=("4d10", "lightning")),
    _s(93, "Vulnerabilità", "Vulnerability", "Per un minuto tu e le creature entro 9 m siete vulnerabili ai danni perforanti.",
       "For one minute you and creatures within 30 ft are vulnerable to piercing damage.", rounds=MINUTE,
       state_key="wild_vulnerable_piercing", vulnerable="piercing"),
    _s(97, "Recuperi", "Recoveries",
       "1d6: 1 curi 2d10 PF; 2 un alleato entro 90 m li cura; 3 slot più basso; 4 slot di un alleato; 5 tutti i punti; 6 tutti gli effetti 17-20.",
       "1d6: 1 you heal 2d10; 2 an ally within 300 ft heals; 3 lowest slot; 4 an ally's slot; 5 all points; 6 every 17-20 effect.", roll="1d6"),
)

"""Specie 2024 (Manuale del Giocatore 2024, cap. 4): dati mostrati dalla scheda. Gli effetti stanno nel motore
(``core/rules/catalog/species_2024.py``); qui nomi, taglia, velocità, scelte e un riassunto per tratto.

Valori da docs/superpowers/rules/2024/races.md; riassunti scritti da noi. La velocità è quella base della scheda (30 piedi):
i bonus di specie (Goliath +5) sono modificatori del motore.
"""
from __future__ import annotations

from dataclasses import dataclass


def _b(it: str, en: str) -> dict[str, str]:
    return {"it": it, "en": en}


@dataclass(frozen=True)
class SpeciesChoice:
    key: str
    label: dict[str, str]
    options: tuple[str, ...]
    option_labels: dict[str, dict[str, str]]
    from_level: int = 1


@dataclass(frozen=True)
class SpeciesData:
    key: str
    name: dict[str, str]
    size: tuple[str, ...]
    speed_ft: int
    choices: tuple[SpeciesChoice, ...]
    traits: tuple[tuple[str, dict[str, str], dict[str, str]], ...]  # (chiave tratto, nome, riassunto)


# Stirpe draconica -> (nome it, nome en, tipo di danno di Soffio e Resistenza)
DRAGON_ANCESTRY: dict[str, tuple[str, str, str]] = {
    "black": ("Nero", "Black", "acid"), "blue": ("Blu", "Blue", "lightning"), "brass": ("Ottone", "Brass", "fire"),
    "bronze": ("Bronzo", "Bronze", "lightning"), "copper": ("Rame", "Copper", "acid"), "gold": ("Oro", "Gold", "fire"),
    "green": ("Verde", "Green", "poison"), "red": ("Rosso", "Red", "fire"), "silver": ("Argento", "Silver", "cold"),
    "white": ("Bianco", "White", "cold"),
}
GIANTS = (("cloud", "Nuvole", "Cloud"), ("fire", "Fuoco", "Fire"), ("frost", "Gelo", "Frost"),
          ("hill", "Colline", "Hill"), ("stone", "Pietra", "Stone"), ("storm", "Tempesta", "Storm"))

_DARK_60 = ("Scurovisione", "Darkvision"), _b("Vedi al buio entro 18 m (60 piedi).", "You see in the dark within 60 ft.")
_DARK_120 = ("Scurovisione", "Darkvision"), _b("Vedi al buio entro 36 m (120 piedi).", "You see in the dark within 120 ft.")


def _t(key: str, spec: tuple, summary: dict[str, str] | None = None) -> tuple[str, dict[str, str], dict[str, str]]:
    names, text = spec if summary is None else (spec, summary)
    return key, _b(*names), text


SPECIES_2024: dict[str, SpeciesData] = {
    "2024_dragonborn": SpeciesData(
        "2024_dragonborn", _b("Dragonide", "Dragonborn"), ("medium",), 30,
        (SpeciesChoice("ancestry", _b("Stirpe draconica", "Draconic ancestry"), tuple(DRAGON_ANCESTRY),
                       {k: _b(f"{v[0]} ({v[2]})", f"{v[1]} ({v[2]})") for k, v in DRAGON_ANCESTRY.items()}),),
        (_t("breath_weapon", ("Arma a soffio", "Breath Weapon"),
            _b("Al posto di un attacco dell'azione Attacco soffi un cono di 4,5 m o una linea di 9 m: TS Destrezza (CD 8 + Cos + competenza), "
               "danni del tipo della stirpe (1d10, poi 2d10, 3d10, 4d10 ai livelli 5, 11, 17), metà se il TS riesce. Usi pari alla competenza.",
               "Instead of one attack of the Attack action you exhale a 15 ft cone or a 30 ft line: Dexterity save (DC 8 + Con + proficiency), "
               "damage of your ancestry's type (1d10, then 2d10, 3d10, 4d10 at levels 5, 11, 17), half on a success. Uses equal your proficiency.")),
         _t("damage_resistance", ("Resistenza ai danni", "Damage Resistance"),
            _b("Resistenza al tipo di danno della tua stirpe draconica.", "Resistance to the damage type of your draconic ancestry.")),
         _t("darkvision", *_DARK_60),
         _t("draconic_flight", ("Volo draconico", "Draconic Flight"),
            _b("Dal livello 5, azione bonus: ali spettrali per 10 minuti, con velocità di volo pari alla tua velocità. Un uso per riposo lungo.",
               "From level 5, bonus action: spectral wings for 10 minutes, with a fly speed equal to your Speed. One use per long rest.")))),
    "2024_dwarf": SpeciesData(
        "2024_dwarf", _b("Nano", "Dwarf"), ("medium",), 30, (),
        (_t("darkvision", *_DARK_120),
         _t("dwarven_resilience", ("Resilienza nanica", "Dwarven Resilience"),
            _b("Resistenza ai danni da veleno e vantaggio ai TS per evitare o terminare Avvelenato.",
               "Resistance to poison damage and advantage on saves to avoid or end Poisoned.")),
         _t("dwarven_toughness", ("Robustezza nanica", "Dwarven Toughness"),
            _b("I PF massimi aumentano di 1 per ogni livello del personaggio.", "Your hit point maximum rises by 1 for every character level.")),
         _t("stonecunning", ("Conoscenza della pietra", "Stonecunning"),
            _b("Azione bonus, su o a contatto con pietra: percezione tellurica 18 m per 10 minuti. Usi pari alla competenza, riposo lungo.",
               "Bonus action, on or touching stone: tremorsense 60 ft for 10 minutes. Uses equal your proficiency, long rest.")))),
    "2024_goliath": SpeciesData(
        "2024_goliath", _b("Goliath", "Goliath"), ("medium",), 30,
        (SpeciesChoice("giant", _b("Ascendenza gigante", "Giant ancestry"), tuple(k for k, _i, _e in GIANTS),
                       {k: _b(i, e) for k, i, e in GIANTS}),),
        (_t("speed", ("Velocità 35 piedi", "Speed 35 ft"),
            _b("La velocità è di 10,5 m (35 piedi), 1,5 m più della base.", "Your Speed is 35 ft, 5 ft above the base.")),
         _t("giant_ancestry_cloud", ("Balzo delle nuvole", "Cloud's Jaunt"),
            _b("Azione bonus: ti teletrasporti fino a 9 m in uno spazio libero che vedi. Usi pari alla competenza, riposo lungo.",
               "Bonus action: teleport up to 30 ft to an unoccupied space you can see. Uses equal your proficiency, long rest.")),
         _t("giant_ancestry_fire", ("Ardore del fuoco", "Fire's Burn"),
            _b("Quando colpisci e infliggi danni, aggiungi 1d10 danni da fuoco. Usi pari alla competenza, riposo lungo.",
               "When you hit and deal damage, add 1d10 fire damage. Uses equal your proficiency, long rest.")),
         _t("giant_ancestry_frost", ("Gelo del ghiaccio", "Frost's Chill"),
            _b("Quando colpisci e infliggi danni, aggiungi 1d6 danni da freddo e la velocità del bersaglio cala di 3 m fino al tuo prossimo turno. "
               "Usi pari alla competenza, riposo lungo.",
               "When you hit and deal damage, add 1d6 cold damage and the target's Speed drops by 10 ft until your next turn. "
               "Uses equal your proficiency, long rest.")),
         _t("giant_ancestry_hill", ("Capitombolo della collina", "Hill's Tumble"),
            _b("Quando colpisci una creatura Grande o più piccola e infliggi danni, può cadere Prona. Usi pari alla competenza, riposo lungo.",
               "When you hit a Large or smaller creature and deal damage, it can be knocked Prone. Uses equal your proficiency, long rest.")),
         _t("giant_ancestry_stone", ("Resistenza della pietra", "Stone's Endurance"),
            _b("Reazione, quando subisci danni: tira 1d12 + Cos e riduci i danni di quel totale. Usi pari alla competenza, riposo lungo.",
               "Reaction, when you take damage: roll 1d12 + Con and reduce the damage by that total. Uses equal your proficiency, long rest.")),
         _t("giant_ancestry_storm", ("Tuono della tempesta", "Storm's Thunder"),
            _b("Reazione, quando una creatura entro 18 m ti danneggia: subisce 1d8 danni da tuono. Usi pari alla competenza, riposo lungo.",
               "Reaction, when a creature within 60 ft damages you: it takes 1d8 thunder damage. Uses equal your proficiency, long rest.")),
         _t("large_form", ("Forma grande", "Large Form"),
            _b("Dal livello 5, azione bonus: per 10 minuti diventi Grande (se c'è spazio), con vantaggio alle prove di Forza e velocità +3 m. "
               "Un uso per riposo lungo.",
               "From level 5, bonus action: for 10 minutes you become Large (if there is room), with advantage on Strength checks and Speed +10 ft. "
               "One use per long rest.")),
         _t("powerful_build", ("Corporatura possente", "Powerful Build"),
            _b("Vantaggio ai TS per terminare Afferrato; per la capacità di carico conti come una taglia più grande.",
               "Advantage on saves to end Grappled; you count as one size larger for carrying capacity.")))),
    "2024_orc": SpeciesData(
        "2024_orc", _b("Orco", "Orc"), ("medium",), 30, (),
        (_t("adrenaline_rush", ("Scarica di adrenalina", "Adrenaline Rush"),
            _b("Azione bonus: Scatto e PF temporanei pari alla competenza. Usi pari alla competenza, riposo breve o lungo.",
               "Bonus action: Dash and temporary HP equal to your proficiency bonus. Uses equal your proficiency, short or long rest.")),
         _t("darkvision", *_DARK_120),
         _t("relentless_endurance", ("Resistenza implacabile", "Relentless Endurance"),
            _b("Se scendi a 0 PF senza morire sul colpo, resti a 1 PF. Un uso per riposo lungo.",
               "When you drop to 0 HP without being killed outright, you drop to 1 HP instead. One use per long rest.")))),
}


def required_choices(key: str) -> tuple[str, ...]:
    """Chiavi delle scelte da fare dall'inizio per la specie ``key`` (vuoto se sconosciuta o senza scelte)."""
    data = SPECIES_2024.get(key)
    return tuple(c.key for c in data.choices if c.from_level <= 1) if data else ()

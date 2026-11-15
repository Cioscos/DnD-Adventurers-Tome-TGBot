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

_SIZE = SpeciesChoice("size", _b("Taglia", "Size"), ("medium", "small"),
                      {"medium": _b("Media", "Medium"), "small": _b("Piccola", "Small")})
_SPELL_ABILITY = SpeciesChoice("spell_ability", _b("Caratteristica da incantatore", "Spellcasting ability"),
                               ("intelligence", "wisdom", "charisma"),
                               {"intelligence": _b("Intelligenza", "Intelligence"), "wisdom": _b("Saggezza", "Wisdom"),
                                "charisma": _b("Carisma", "Charisma")})


def _choice(key: str, label: tuple[str, str], options: tuple[tuple[str, str, str], ...]) -> SpeciesChoice:
    """Scelta da righe ``(chiave, it, en)``."""
    return SpeciesChoice(key, _b(*label), tuple(k for k, _i, _e in options), {k: _b(i, e) for k, i, e in options})


def _skills() -> tuple[tuple[str, str, str], ...]:
    from core.data.labels import SKILL_LABELS_IT
    return tuple((k, it, k.replace("_", " ").title()) for k, it in SKILL_LABELS_IT.items())


def _origin_feats() -> tuple[tuple[str, str, str], ...]:
    from core.data.feats_2024 import FEATS_2024
    return tuple((f.key, f.name["it"], f.name["en"]) for f in FEATS_2024 if f.category == "origin")


ELF_LINEAGES = (("drow", "Drow", "Drow"), ("high", "Elfo alto", "High Elf"), ("wood", "Elfo dei boschi", "Wood Elf"))
GNOME_LINEAGES = (("forest", "Gnomo delle foreste", "Forest Gnome"), ("rock", "Gnomo delle rocce", "Rock Gnome"))
FIENDISH_LEGACIES = (("abyssal", "Abissale", "Abyssal"), ("chthonic", "Ctonia", "Chthonic"), ("infernal", "Infernale", "Infernal"))
_LINEAGE_SPELLS = _b("Ai livelli 3 e 5 un incantesimo in più, sempre preparato, lanciabile una volta senza slot per riposo lungo.",
                     "At levels 3 and 5 one more spell, always prepared, castable once without a slot per long rest.")


def _with_spells(it: str, en: str) -> dict[str, str]:
    return _b(f"{it} {_LINEAGE_SPELLS['it']}", f"{en} {_LINEAGE_SPELLS['en']}")


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
    "2024_aasimar": SpeciesData(
        "2024_aasimar", _b("Aasimar", "Aasimar"), ("medium", "small"), 30, (_SIZE,),
        (_t("celestial_resistance", ("Resistenza celeste", "Celestial Resistance"),
            _b("Resistenza ai danni necrotici e radianti.", "Resistance to necrotic and radiant damage.")),
         _t("darkvision", *_DARK_60),
         _t("healing_hands", ("Mani guaritrici", "Healing Hands"),
            _b("Azione Magia: tocchi una creatura, che recupera PF pari a tanti d4 quanto la competenza. Un uso per riposo lungo.",
               "Magic action: touch a creature, which regains HP equal to a number of d4s equal to your proficiency. One use per long rest.")),
         _t("light_bearer", ("Portatore di luce", "Light Bearer"),
            _b("Conosci il trucchetto Luce, con Carisma come caratteristica da incantatore.",
               "You know the Light cantrip, with Charisma as your spellcasting ability.")),
         _t("celestial_revelation", ("Rivelazione celeste", "Celestial Revelation"),
            _b("Dal livello 3, azione bonus: per 1 minuto Ali celesti (volo), Radiosità interiore o Manto necrotico; una volta per turno "
               "un colpo infligge danni extra pari alla competenza. Un uso per riposo lungo.",
               "From level 3, bonus action: for 1 minute Heavenly Wings (flight), Inner Radiance or Necrotic Shroud; once per turn "
               "a hit deals extra damage equal to your proficiency. One use per long rest.")))),
    "2024_elf": SpeciesData(
        "2024_elf", _b("Elfo", "Elf"), ("medium",), 30,
        (_choice("lineage", ("Stirpe elfica", "Elven lineage"), ELF_LINEAGES), _SPELL_ABILITY,
         _choice("skill", ("Sensi acuti", "Keen Senses"),
                 (("insight", "Intuizione", "Insight"), ("perception", "Percezione", "Perception"), ("survival", "Sopravvivenza", "Survival")))),
        (_t("darkvision", *_DARK_60),
         _t("lineage_drow", ("Drow", "Drow"), _with_spells(
             "Scurovisione 36 m (120 piedi) e il trucchetto Luci danzanti; Fuoco fatato al 3, Oscurità al 5.",
             "Darkvision 120 ft and the Dancing Lights cantrip; Faerie Fire at 3, Darkness at 5.")),
         _t("lineage_high", ("Elfo alto", "High Elf"), _with_spells(
             "Il trucchetto Prestidigitazione (lo puoi cambiare con un trucchetto da Mago dopo un riposo lungo); Individuazione del magico al 3, "
             "Passo velato al 5.",
             "The Prestidigitation cantrip (you can swap it for a Wizard cantrip after a long rest); Detect Magic at 3, Misty Step at 5.")),
         _t("lineage_wood", ("Elfo dei boschi", "Wood Elf"), _with_spells(
             "Velocità 10,5 m (35 piedi) e il trucchetto Druidismo; Passo lungo al 3, Passare senza tracce al 5.",
             "Speed 35 ft and the Druidcraft cantrip; Longstrider at 3, Pass without Trace at 5.")),
         _t("fey_ancestry", ("Ascendenza fatata", "Fey Ancestry"),
            _b("Vantaggio ai TS per evitare o terminare Affascinato.", "Advantage on saves to avoid or end Charmed.")),
         _t("keen_senses", ("Sensi acuti", "Keen Senses"),
            _b("Competenza in Intuizione, Percezione o Sopravvivenza.", "Proficiency in Insight, Perception or Survival.")),
         _t("trance", ("Trance", "Trance"),
            _b("Non dormi e la magia non ti addormenta; il riposo lungo ti basta in 4 ore di meditazione.",
               "You don't sleep and magic can't put you to sleep; a long rest takes you 4 hours of meditation.")))),
    "2024_gnome": SpeciesData(
        "2024_gnome", _b("Gnomo", "Gnome"), ("small",), 30,
        (_choice("lineage", ("Stirpe gnomesca", "Gnomish lineage"), GNOME_LINEAGES), _SPELL_ABILITY),
        (_t("darkvision", *_DARK_60),
         _t("gnomish_cunning", ("Astuzia gnomesca", "Gnomish Cunning"),
            _b("Vantaggio ai TS su Intelligenza, Saggezza e Carisma.", "Advantage on Intelligence, Wisdom and Charisma saves.")),
         _t("lineage_forest", ("Gnomo delle foreste", "Forest Gnome"),
            _b("Il trucchetto Illusione minore e Parlare con gli animali sempre preparato, senza slot tante volte quanto la competenza "
               "per riposo lungo.",
               "The Minor Illusion cantrip and Speak with Animals always prepared, without a slot a number of times equal to your "
               "proficiency per long rest.")),
         _t("lineage_rock", ("Gnomo delle rocce", "Rock Gnome"),
            _b("I trucchetti Riparare e Prestidigitazione; con 10 minuti crei fino a tre piccoli congegni con un effetto di "
               "Prestidigitazione, che durano 8 ore.",
               "The Mending and Prestidigitation cantrips; in 10 minutes you build up to three tiny devices with a Prestidigitation "
               "effect, lasting 8 hours.")))),
    "2024_halfling": SpeciesData(
        "2024_halfling", _b("Halfling", "Halfling"), ("small",), 30, (),
        (_t("brave", ("Coraggioso", "Brave"),
            _b("Vantaggio ai TS per evitare o terminare Spaventato.", "Advantage on saves to avoid or end Frightened.")),
         _t("halfling_nimbleness", ("Agilità halfling", "Halfling Nimbleness"),
            _b("Attraversi lo spazio di una creatura più grande di te, senza fermarti lì.",
               "You move through the space of a creature larger than you, without stopping there.")),
         _t("luck", ("Fortuna", "Luck"),
            _b("Se il d20 di un Test d20 fa 1 puoi ritirarlo, e tieni il nuovo risultato.",
               "When the d20 of a D20 Test shows a 1 you can reroll it, and you keep the new roll.")),
         _t("naturally_stealthy", ("Furtività naturale", "Naturally Stealthy"),
            _b("Puoi nasconderti anche dietro una creatura di almeno una taglia più grande.",
               "You can hide even behind a creature at least one size larger than you.")))),
    "2024_human": SpeciesData(
        "2024_human", _b("Umano", "Human"), ("medium", "small"), 30,
        (_SIZE, _choice("skill", ("Abile", "Skillful"), _skills()),
         _choice("origin_feat", ("Versatile", "Versatile"), _origin_feats())),
        (_t("resourceful", ("Intraprendente", "Resourceful"),
            _b("Ottieni Ispirazione Eroica alla fine di ogni riposo lungo.", "You gain Heroic Inspiration at the end of every long rest.")),
         _t("skillful", ("Abile", "Skillful"), _b("Competenza in un'abilità a scelta.", "Proficiency in one skill of your choice.")),
         _t("versatile", ("Versatile", "Versatile"), _b("Un talento d'Origine a scelta.", "One Origin feat of your choice.")))),
    "2024_tiefling": SpeciesData(
        "2024_tiefling", _b("Tiefling", "Tiefling"), ("medium", "small"), 30,
        (_SIZE, _choice("legacy", ("Eredità infernale", "Fiendish legacy"), FIENDISH_LEGACIES), _SPELL_ABILITY),
        (_t("darkvision", *_DARK_60),
         _t("legacy_abyssal", ("Abissale", "Abyssal"), _with_spells(
             "Resistenza al veleno e il trucchetto Spruzzo velenoso; Raggio di infermità al 3, Bloccare persone al 5.",
             "Poison resistance and the Poison Spray cantrip; Ray of Sickness at 3, Hold Person at 5.")),
         _t("legacy_chthonic", ("Ctonia", "Chthonic"), _with_spells(
             "Resistenza ai danni necrotici e il trucchetto Tocco gelido; Falsa vita al 3, Raggio di indebolimento al 5.",
             "Necrotic resistance and the Chill Touch cantrip; False Life at 3, Ray of Enfeeblement at 5.")),
         _t("legacy_infernal", ("Infernale", "Infernal"), _with_spells(
             "Resistenza al fuoco e il trucchetto Dardo di fuoco; Rimprovero infernale al 3, Oscurità al 5.",
             "Fire resistance and the Fire Bolt cantrip; Hellish Rebuke at 3, Darkness at 5.")),
         _t("otherworldly_presence", ("Presenza ultraterrena", "Otherworldly Presence"),
            _b("Conosci il trucchetto Taumaturgia, con la caratteristica dell'Eredità infernale.",
               "You know the Thaumaturgy cantrip, with your Fiendish Legacy's ability.")))),
}


def required_choices(key: str) -> tuple[str, ...]:
    """Chiavi delle scelte da fare dall'inizio per la specie ``key`` (vuoto se sconosciuta o senza scelte)."""
    data = SPECIES_2024.get(key)
    return tuple(c.key for c in data.choices if c.from_level <= 1) if data else ()

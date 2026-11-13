"""Talenti 2014 (Manuale del Giocatore 2014, pagg. 165-170): scheda di selezione con nome, riassunto nostro e
prerequisiti. Gli effetti stanno nel motore delle regole (``core/rules/catalog/feats_2014.py``).

Titoli da docs/superpowers/rules/2014/feats.md; riassunti scritti da noi, massimo 200 caratteri per lingua."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

ALL_ABILITIES = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]


@dataclass(frozen=True)
class FeatSpec:
    key: str
    name: dict[str, str]
    summary: dict[str, str]
    ability_increase: Optional[list[str]] = None
    save_proficiency_from_increase: bool = False
    edition: str = "2014"
    category: str = "general"  # general | epic_boon | origin | fighting_style
    min_level: int = 0  # livello totale del personaggio
    prereq_abilities: Optional[tuple[tuple[str, ...], int]] = None  # (una fra queste, minimo)
    needs_spellcasting: bool = False
    max_score: int = 20
    repeatable: bool = False  # si prende più volte (Abile, Iniziato alla magia): ogni riga è un'istanza
    prereq_armor: Optional[str] = None  # addestramento richiesto: light | medium | heavy | shields
    needs_fighting_style: bool = False  # Stile di Combattimento come talento: serve il privilegio Stile di Combattimento


AB = {"S": "strength", "D": "dexterity", "C": "constitution", "I": "intelligence", "W": "wisdom", "H": "charisma"}
ALL6 = "SDCIWH"


def _p14(key, it, en, inc, sit, sen, pre="", caster=False, armor=None, save=False, repeatable=False) -> FeatSpec:
    """`inc` = lettere delle caratteristiche aumentabili, `pre` = lettere + minimo (es. "IW13")."""
    abilities = tuple(AB[c] for c in pre.rstrip("0123456789"))
    return FeatSpec(key=key, name={"it": it, "en": en}, summary={"it": sit, "en": sen},
                    ability_increase=[AB[c] for c in inc] or None, save_proficiency_from_increase=save,
                    prereq_abilities=(abilities, int(pre.lstrip(ALL6))) if pre else None,
                    needs_spellcasting=caster, prereq_armor=armor, repeatable=repeatable)


FEATS: dict[str, FeatSpec] = {f.key: f for f in [
    _p14("skilled", "Abile", "Skilled", "", "Competenza in tre abilità o strumenti a scelta.", "Proficiency in any three skills or tools."),
    _p14("elemental_adept", "Adepto Elementale", "Elemental Adept", "", "Un tipo di energia: i tuoi incantesimi ignorano la resistenza e gli 1 sui dadi valgono 2. Ripetibile.", "One energy type: your spells ignore resistance and 1s on damage dice count as 2. Repeatable.", caster=True, repeatable=True),
    _p14("martial_adept", "Adepto Marziale", "Martial Adept", "", "Due manovre del Maestro di Battaglia e un dado di superiorità d6 per riposo breve.", "Two Battle Master maneuvers and one d6 superiority die per short rest."),
    _p14("savage_attacker", "Aggressore Selvaggio", "Savage Attacker", "", "Una volta per turno ritiri i dadi del danno di un'arma da mischia e tieni il risultato migliore.", "Once per turn reroll a melee weapon's damage dice and use either total."),
    _p14("alert", "Allerta", "Alert", "", "+5 all'iniziativa; da cosciente non puoi essere sorpreso; chi non vedi non ha vantaggio contro di te per questo.", "+5 to initiative; you can't be surprised while conscious; unseen attackers gain no advantage from it."),
    _p14("skulker", "Appostato", "Skulker", "", "Ti nascondi anche in penombra leggera; mancare a distanza non ti rivela; la luce fioca non ostacola la Percezione.", "Hide when lightly obscured; a ranged miss doesn't reveal you; dim light doesn't hinder your Perception.", pre="D13"),
    _p14("athlete", "Atleta", "Athlete", "SD", "Rialzarsi costa 1,5 m; scalare non costa movimento extra; salti con rincorsa di soli 1,5 m.", "Standing up costs 5 feet; climbing costs no extra movement; running jumps after only 5 feet."),
    _p14("actor", "Attore", "Actor", "H", "Vantaggio a Inganno e Intrattenere per spacciarti per un altro; imiti voci e versi.", "Advantage on Deception and Performance to pass as someone else; you mimic voices and sounds."),
    _p14("charger", "Carica", "Charger", "", "Dopo uno Scatto attacchi o spingi con azione bonus; dopo 3 m in linea retta +5 al danno o spinta di 3 m.", "After a Dash, attack or shove as a bonus action; after 10 feet in a straight line, +5 damage or a 10-foot push."),
    _p14("spell_sniper", "Cecchino Magico", "Spell Sniper", "", "Gittata doppia per gli incantesimi con tiro per colpire, ignori la copertura parziale e impari un trucchetto d'attacco.", "Double range for attack-roll spells, ignore partial cover and learn an attack cantrip.", caster=True),
    _p14("dual_wielder", "Combattente a Due Armi", "Dual Wielder", "", "+1 alla CA con un'arma da mischia in ogni mano; due armi anche non leggere; estrai due armi insieme.", "+1 AC with a melee weapon in each hand; fight with two non-light weapons; draw two weapons at once."),
    _p14("mounted_combatant", "Combattente in Sella", "Mounted Combatant", "", "In sella hai vantaggio contro creature più piccole della cavalcatura e la proteggi.", "While mounted you have advantage against creatures smaller than your mount and protect it."),
    _p14("inspiring_leader", "Condottiero Ispiratore", "Inspiring Leader", "", "Un discorso di 10 minuti dà a sei creature PF temporanei pari al livello + Carisma.", "A 10-minute speech gives six creatures temporary HP equal to your level + Charisma.", pre="H13"),
    _p14("lightly_armored", "Corazze Leggere", "Lightly Armored", "SD", "Competenza nelle armature leggere.", "Proficiency with light armor."),
    _p14("moderately_armored", "Corazze Medie", "Moderately Armored", "SD", "Competenza nelle armature medie e negli scudi. Richiede le armature leggere.", "Proficiency with medium armor and shields. Requires light armor proficiency.", armor="light"),
    _p14("heavily_armored", "Corazze Pesanti", "Heavily Armored", "S", "Competenza nelle armature pesanti. Richiede le armature medie.", "Proficiency with heavy armor. Requires medium armor proficiency.", armor="medium"),
    _p14("defensive_duelist", "Duellante Difensivo", "Defensive Duelist", "", "Reazione: con un'arma accurata aggiungi la competenza alla CA contro un attacco in mischia.", "Reaction: with a finesse weapon add your proficiency bonus to AC against a melee attack.", pre="D13"),
    _p14("crossbow_expert", "Esperto di Balestre", "Crossbow Expert", "", "Ignori la ricarica, tiri da vicino senza svantaggio e attacchi con la balestra a mano come azione bonus.", "Ignore loading, no disadvantage up close, and a bonus-action hand crossbow attack."),
    _p14("dungeon_delver", "Esperto di Dungeon", "Dungeon Delver", "", "Vantaggio per trovare porte segrete e ai TS contro le trappole; resistenza ai danni delle trappole.", "Advantage to find secret doors and on saves against traps; resistance to trap damage."),
    _p14("lucky", "Fortunato", "Lucky", "", "3 punti fortuna per riposo lungo: ritiri un tuo d20 (attacco, prova, TS) o quello di un attacco contro di te.", "3 luck points per long rest: reroll your d20 (attack, check, save) or one rolled to attack you."),
    _p14("healer", "Guaritore", "Healer", "", "Con la borsa del guaritore stabilizzi a 1 PF o curi 1d6 + 4 + i Dadi Vita del bersaglio.", "With a healer's kit you stabilize at 1 HP or heal 1d6 + 4 + the target's Hit Dice."),
    _p14("war_caster", "Incantatore da Guerra", "War Caster", "", "Vantaggio ai TS di Costituzione per la concentrazione; componenti somatiche con le mani occupate; un incantesimo come attacco di opportunità.", "Advantage on Constitution saves for concentration; somatic components with full hands; a spell as an opportunity attack.", caster=True),
    _p14("ritual_caster", "Incantatore Rituale", "Ritual Caster", "", "Un libro dei rituali con due rituali di 1º livello di una classe; puoi copiarne altri.", "A ritual book with two 1st-level rituals from one class; you can copy more.", pre="IW13"),
    _p14("magic_initiate", "Iniziato alla Magia", "Magic Initiate", "", "Due trucchetti e un incantesimo di 1º livello di una classe, lanciabile una volta per riposo lungo.", "Two cantrips and one 1st-level spell from one class, castable once per long rest."),
    _p14("linguist", "Linguista", "Linguist", "I", "Tre linguaggi a scelta; crei codici cifrati.", "Three languages of your choice; you can create ciphers."),
    _p14("grappler", "Lottatore", "Grappler", "", "Vantaggio ai tiri per colpire le creature che stai lottando; puoi tentare di immobilizzarle.", "Advantage on attacks against creatures you are grappling; you can try to pin them.", pre="S13"),
    _p14("tavern_brawler", "Lottatore da Taverna", "Tavern Brawler", "SC", "Competenza nelle armi improvvisate; colpo senz'armi 1d4; dopo un colpo afferri con azione bonus.", "Improvised weapon proficiency; unarmed strike 1d4; after a hit you grapple as a bonus action."),
    _p14("weapon_master", "Maestro d'Armi", "Weapon Master", "SD", "Competenza in quattro armi semplici o da guerra a scelta.", "Proficiency with four simple or martial weapons of your choice."),
    _p14("great_weapon_master", "Maestro d'Armi Possenti", "Great Weapon Master", "", "Con un'arma pesante -5 al colpire per +10 al danno; attacco bonus dopo un critico o un nemico a 0 PF.", "With a heavy weapon take -5 to hit for +10 damage; bonus attack after a crit or a kill."),
    _p14("shield_master", "Maestro degli Scudi", "Shield Master", "", "Spingi con lo scudo; la sua CA si somma ai TS di Destrezza; nessun danno se superi un TS a metà danni.", "Shove with your shield; its AC adds to Dexterity saves; no damage on a successful half-damage save."),
    _p14("medium_armor_master", "Maestro delle Armature Medie", "Medium Armor Master", "", "Con armatura media niente svantaggio a Furtività e +3 di Destrezza alla CA con Destrezza 16+.", "In medium armor no Stealth disadvantage and +3 Dexterity to AC with Dexterity 16+.", armor="medium"),
    _p14("heavy_armor_master", "Maestro delle Armature Pesanti", "Heavy Armor Master", "S", "Con armatura pesante subisci 3 danni in meno dalle armi non magiche contundenti, perforanti o taglienti.", "In heavy armor you take 3 less bludgeoning, piercing or slashing damage from nonmagical weapons.", armor="heavy"),
    _p14("polearm_master", "Maestro delle Armi su Asta", "Polearm Master", "", "Attacco bonus d4 con l'altra estremità; attacco di opportunità quando un nemico entra nella portata.", "Bonus d4 attack with the butt end; opportunity attack when a creature enters your reach."),
    _p14("keen_mind", "Mente Acuta", "Keen Mind", "I", "Sai dov'è il nord e quanto manca all'alba; ricordi tutto dell'ultimo mese.", "You always know north and the hours to sunrise; you recall everything from the past month."),
    _p14("mobile", "Mobilità", "Mobile", "", "+10 piedi di velocità; lo Scatto ignora il terreno difficile; chi attacchi in mischia non ti fa attacchi di opportunità.", "+10 feet speed; Dash ignores difficult terrain; creatures you attack in melee get no opportunity attack on you."),
    _p14("observant", "Osservatore", "Observant", "IW", "+5 a Percezione e Indagare passive; leggi le labbra.", "+5 to passive Perception and Investigation; you can read lips."),
    _p14("resilient", "Resiliente", "Resilient", ALL6, "+1 a una caratteristica a scelta e competenza nei suoi tiri salvezza.", "+1 to one ability of your choice and proficiency in its saving throws.", save=True),
    _p14("tough", "Robusto", "Tough", "", "+2 punti ferita massimi per ogni livello.", "+2 maximum hit points per level."),
    _p14("sentinel", "Sentinella", "Sentinel", "", "Chi colpisci con un attacco di opportunità si ferma; il Disimpegno non ti sfugge; reazione contro chi attacca altri.", "Creatures you hit with opportunity attacks stop; Disengage doesn't avoid you; reaction against foes attacking others."),
    _p14("mage_slayer", "Sterminatore di Maghi", "Mage Slayer", "", "Reazione contro chi lancia vicino a te; svantaggio alla sua concentrazione; vantaggio ai TS contro incantesimi vicini.", "Reaction against nearby casters; they have disadvantage on concentration; advantage on saves against nearby spells."),
    _p14("durable", "Tenace", "Durable", "C", "Ogni Dado Vita speso cura almeno il doppio del modificatore di Costituzione (minimo 2).", "Each Hit Die you spend heals at least twice your Constitution modifier (minimum 2)."),
    _p14("sharpshooter", "Tiratore Scelto", "Sharpshooter", "", "Con armi a distanza -5 al colpire per +10 al danno; niente svantaggio a gittata lunga; ignori la copertura parziale.", "With ranged weapons take -5 to hit for +10 damage; no long-range disadvantage; ignore partial cover."),
]}

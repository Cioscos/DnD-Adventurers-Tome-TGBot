"""Talenti generali 2024 e Doni Epici (D3): solo scelta, prerequisiti e testo, nessun effetto automatico.

Titoli da docs/superpowers/rules/2024/feats.md (di lavoro, vedi titoli-da-confermare.md);
riassunti scritti da noi, massimo 200 caratteri per lingua. Gli effetti restano in lavori-successivi.md.
"""
from __future__ import annotations

from core.data.feats import FEATS, FeatSpec

_AB = {"S": "strength", "D": "dexterity", "C": "constitution", "I": "intelligence", "W": "wisdom", "H": "charisma"}
ALL6 = "SDCIWH"


def _p24(key, it, en, inc, sit, sen, pre="", caster=False, boon=False, save=False) -> FeatSpec:
    """`inc` = lettere delle caratteristiche aumentabili, `pre` = lettere + minimo (es. "SD13")."""
    abilities = tuple(_AB[c] for c in pre.rstrip("0123456789"))
    return FeatSpec(
        key=f"2024_{key}", name={"it": it, "en": en}, summary={"it": sit, "en": sen},
        ability_increase=[_AB[c] for c in inc], edition="2024",
        category="epic_boon" if boon else "general", min_level=19 if boon else 4,
        prereq_abilities=(abilities, int(pre.lstrip(ALL6))) if pre else None,
        needs_spellcasting=caster, max_score=30 if boon else 20, save_proficiency_from_increase=save)


FEATS_2024: list[FeatSpec] = [
    _p24("actor", "Attore", "Actor", "H", "Vantaggio nel fingerti un'altra persona; imiti voci e suoni.", "Advantage when posing as someone else; you can mimic voices and sounds.", "H13"),
    _p24("athlete", "Atletico", "Athlete", "SD", "Scalata pari alla Velocità; ti rialzi e salti con poco movimento.", "Climb speed equals your speed; standing up and jumping cost little movement.", "SD13"),
    _p24("charger", "Assalitore", "Charger", "SD", "Scatto più veloce; dopo 10 piedi in linea retta +1d8 al danno oppure spingi il bersaglio.", "Faster Dash; after moving 10 feet straight, +1d8 damage or push the target.", "SD13"),
    _p24("chef", "Cuoco", "Chef", "CW", "Competenza con gli utensili da cuoco; pasti che curano di più e dolcetti che danno PF temporanei.", "Cook's utensils proficiency; meals that heal more and treats granting temporary HP."),
    _p24("crossbow_expert", "Esperto di balestre", "Crossbow Expert", "D", "Ignori Ricarica, tiri senza svantaggio da vicino e attacchi extra con balestra leggera.", "Ignore Loading, no disadvantage up close, and a bonus attack with a light crossbow.", "D13"),
    _p24("crusher", "Frantumatore", "Crusher", "SC", "Con danni contundenti sposti il bersaglio; i critici danno vantaggio agli alleati.", "With bludgeoning damage you shift the target; crits grant advantage against it."),
    _p24("defensive_duelist", "Duellante difensivo", "Defensive Duelist", "D", "Reazione: con arma Accurata aggiungi la competenza alla CA contro un attacco in mischia.", "Reaction: with a Finesse weapon add proficiency to AC against a melee attack.", "D13"),
    _p24("dual_wielder", "Combattente con due armi", "Dual Wielder", "SD", "Attacco extra con due armi da mischia diverse; estrai e riponi due armi insieme.", "Bonus attack with two different melee weapons; draw or stow two weapons at once.", "SD13"),
    _p24("durable", "Durevole", "Durable", "C", "Vantaggio ai TS contro la morte; azione Bonus per spendere un Dado Vita e curarti.", "Advantage on death saves; Bonus Action to spend a Hit Die and heal."),
    _p24("elemental_adept", "Adepto elementale", "Elemental Adept", "IWH", "Un tipo di energia: i tuoi incantesimi ignorano la resistenza e i 1 valgono 2. Ripetibile.", "One energy type: your spells ignore resistance and 1s count as 2. Repeatable.", caster=True),
    _p24("fey_touched", "Toccato dalle fate", "Fey-Touched", "IWH", "Passo velato e un incantesimo di 1º di Divinazione o Ammaliamento, sempre preparati.", "Misty Step and one 1st-level Divination or Enchantment spell, always prepared."),
    _p24("grappler", "Lottatore", "Grappler", "SD", "Colpisci e afferri insieme; vantaggio contro chi afferri; muovi i lottati a velocità piena.", "Hit and grapple together; advantage against grappled foes; move them at full speed.", "SD13"),
    _p24("great_weapon_master", "Maestro di armi pesanti", "Great Weapon Master", "S", "Danni extra pari alla competenza con armi Pesanti; attacco Bonus dopo critico o abbattimento.", "Extra damage equal to proficiency with Heavy weapons; bonus attack after a crit or kill.", "S13"),
    _p24("heavily_armored", "Armatura pesante", "Heavily Armored", "CS", "Addestramento con armature pesanti. Richiede addestramento con armature medie.", "Heavy armor training. Requires medium armor training."),
    _p24("heavy_armor_master", "Maestro di armature pesanti", "Heavy Armor Master", "CS", "Con armatura pesante i danni fisici sono ridotti della competenza. Richiede armature pesanti.", "In heavy armor, physical damage is reduced by proficiency. Requires heavy armor training."),
    _p24("inspiring_leader", "Capo ispiratore", "Inspiring Leader", "WH", "Dopo un riposo dai PF temporanei a sei alleati.", "After a rest, grant temporary HP to up to six allies.", "WH13"),
    _p24("keen_mind", "Mente acuta", "Keen Mind", "I", "Competenza o Maestria in una abilità di conoscenza.", "Proficiency or Expertise in a knowledge skill.", "I13"),
    _p24("lightly_armored", "Armatura leggera", "Lightly Armored", "SD", "Addestramento con armature leggere e scudi.", "Light armor and shield training."),
    _p24("mage_slayer", "Ammazzamaghi", "Mage Slayer", "SD", "Svantaggio alla concentrazione di chi colpisci; vantaggio ai TS contro incantesimi vicini.", "Targets you damage have disadvantage on concentration; advantage on saves against nearby spells."),
    _p24("martial_weapon_training", "Addestramento con armi marziali", "Martial Weapon Training", "SD", "Competenza con le armi da guerra.", "Proficiency with martial weapons."),
    _p24("medium_armor_master", "Maestro di armature medie", "Medium Armor Master", "SD", "Con armatura media sommi 3 alla CA con Destrezza 16+. Richiede armature medie.", "In medium armor add 3 to AC with Dexterity 16+. Requires medium armor training."),
    _p24("moderately_armored", "Armatura media", "Moderately Armored", "SD", "Addestramento con armature medie. Richiede addestramento con armature leggere.", "Medium armor training. Requires light armor training."),
    _p24("mounted_combatant", "Combattente in sella", "Mounted Combatant", "SDW", "In sella hai vantaggio contro creature più piccole e proteggi la cavalcatura.", "While mounted you have advantage against smaller creatures and shield your mount."),
    _p24("observant", "Osservatore", "Observant", "IW", "Competenza o Maestria in Intuizione, Indagare o Percezione.", "Proficiency or Expertise in Insight, Investigation or Perception.", "IW13"),
    _p24("piercer", "Perforatore", "Piercer", "SD", "Una volta per turno ritiri un dado di danno perforante; i critici aggiungono un dado.", "Once per turn reroll a piercing damage die; crits add an extra die."),
    _p24("poisoner", "Avvelenatore", "Poisoner", "DI", "I danni da veleno ignorano la resistenza; prepari veleni potenti.", "Your poison damage ignores resistance; you can brew potent poisons."),
    _p24("polearm_master", "Maestro di armi inastate", "Polearm Master", "DS", "Attacco Bonus con l'altra estremità; attacco di opportunità quando un nemico entra in portata.", "Bonus attack with the butt end; opportunity attack when a foe enters your reach.", "SD13"),
    _p24("resilient", "Resiliente", "Resilient", ALL6, "+1 a una caratteristica in cui non hai competenza nei TS, e ottieni quella competenza.", "+1 to an ability you lack save proficiency in, and gain that proficiency.", save=True),
    _p24("ritual_caster", "Incantatore rituale", "Ritual Caster", "IWH", "Conosci incantesimi rituali di 1º livello e puoi lanciarli come rituali.", "Know 1st-level ritual spells and cast them as rituals.", "IWH13"),
    _p24("sentinel", "Sentinella", "Sentinel", "SD", "Blocchi i nemici che colpisci; attacco di opportunità anche contro chi si disimpegna.", "Stop enemies you hit; opportunity attacks even against Disengage.", "SD13"),
    _p24("shadow_touched", "Toccato dall'ombra", "Shadow-Touched", "IWH", "Invisibilità e un incantesimo di 1º di Illusione o Necromanzia, sempre preparati.", "Invisibility and one 1st-level Illusion or Necromancy spell, always prepared."),
    _p24("sharpshooter", "Tiratore scelto", "Sharpshooter", "D", "Le armi a distanza ignorano la copertura parziale e non soffrono la gittata lunga.", "Ranged weapons ignore partial cover and suffer no long-range penalty.", "D13"),
    _p24("shield_master", "Maestro di scudi", "Shield Master", "S", "Spingi con lo scudo e riduci i danni dei TS. Richiede addestramento con gli scudi.", "Shove with your shield and cut save damage. Requires shield training."),
    _p24("skill_expert", "Esperto di abilità", "Skill Expert", ALL6, "Una competenza in abilità in più e Maestria in una abilità in cui sei competente.", "One extra skill proficiency and Expertise in a skill you know."),
    _p24("skulker", "Furtivo", "Skulker", "D", "Vista cieca 10 piedi; ti nascondi in luce fioca e non ti riveli mancando.", "Blindsight 10 ft; hide in dim light and stay hidden when you miss.", "D13"),
    _p24("slasher", "Tagliente", "Slasher", "SD", "Una volta per turno riduci la Velocità del bersaglio; i critici lo rendono svantaggiato.", "Once per turn reduce the target's speed; crits impose disadvantage."),
    _p24("speedy", "Veloce", "Speedy", "DC", "Velocità +10 piedi e scatto su terreno difficile senza costo extra.", "Speed +10 ft and Dash across difficult terrain at no extra cost.", "DC13"),
    _p24("spell_sniper", "Cecchino magico", "Spell Sniper", "IWH", "Gli incantesimi con tiro per colpire ignorano la copertura e hanno gittata maggiore.", "Attack-roll spells ignore partial cover and have longer range.", caster=True),
    _p24("telekinetic", "Telecinetico", "Telekinetic", "IWH", "Conosci Mano magica invisibile e spingi una creatura con azione Bonus.", "Know an invisible Mage Hand and shove a creature as a Bonus Action."),
    _p24("telepathic", "Telepatico", "Telepathic", "IWH", "Parli a distanza con chi vedi; Individuazione dei pensieri sempre preparato.", "Speak to creatures you see; Detect Thoughts always prepared."),
    _p24("war_caster", "Incantatore da guerra", "War Caster", "IWH", "Vantaggio alla concentrazione; lanci un incantesimo come attacco di opportunità.", "Advantage on concentration; cast a spell as an opportunity attack.", caster=True),
    _p24("weapon_master", "Maestro d'armi", "Weapon Master", "SD", "Usi la proprietà di padronanza di un'arma in più, cambiabile dopo un riposo lungo.", "Use the mastery property of one more weapon, changeable after a long rest."),
    # Doni Epici: livello totale 19+, una caratteristica fino a 30.
    _p24("boon_combat_prowess", "Dono del Prodigio in combattimento", "Boon of Combat Prowess", ALL6, "Quando manchi un attacco puoi trasformarlo in colpo a segno, a turni alterni.", "When you miss an attack you can turn it into a hit, every other turn.", boon=True),
    _p24("boon_dimensional_travel", "Dono del Viaggio dimensionale", "Boon of Dimensional Travel", ALL6, "Dopo Attacco o Magia ti teletrasporti fino a 30 piedi.", "After the Attack or Magic action you teleport up to 30 feet.", boon=True),
    _p24("boon_energy_resistance", "Dono della Resistenza all'energia", "Boon of Energy Resistance", ALL6, "Resistenza a due tipi di energia a scelta; puoi rimandare il danno a un'altra creatura.", "Resistance to two chosen energy types; you can redirect that damage to another creature.", boon=True),
    _p24("boon_fate", "Dono del Fato", "Boon of Fate", ALL6, "Aggiungi o togli 2d4 a un Test d20 tuo o di una creatura vicina.", "Add or subtract 2d4 on a d20 Test of yours or a nearby creature.", boon=True),
    _p24("boon_fortitude", "Dono della Forza d'animo", "Boon of Fortitude", ALL6, "PF massimi +40 e cure potenziate dal modificatore di Costituzione.", "Maximum HP +40 and healing boosted by your Constitution modifier.", boon=True),
    _p24("boon_irresistible_offense", "Dono dell'Offensiva irresistibile", "Boon of Irresistible Offense", "SD", "I danni fisici ignorano la resistenza; il 20 naturale aggiunge danni extra.", "Physical damage ignores resistance; a natural 20 adds bonus damage.", boon=True),
    _p24("boon_recovery", "Dono del Recupero", "Boon of Recovery", ALL6, "Una volta per riposo lungo resti a 1 PF invece di 0 e curi metà del massimo; riserva di dieci d10.", "Once per long rest drop to 1 HP instead of 0 and heal half your maximum; a pool of ten d10.", boon=True),
    _p24("boon_skill", "Dono dell'Abilità", "Boon of Skill", ALL6, "Competenza in tutte le abilità e Maestria in una a scelta.", "Proficiency in every skill and Expertise in one of your choice.", boon=True),
    _p24("boon_speed", "Dono della Velocità", "Boon of Speed", ALL6, "Velocità +30 piedi; Disimpegno come azione Bonus che ti libera dalla presa.", "Speed +30 ft; Disengage as a Bonus Action that also frees you from grapples.", boon=True),
    _p24("boon_spell_recall", "Dono del Richiamo degli incantesimi", "Boon of Spell Recall", "IWH", "Lanciando slot di 1-4 livello tira 1d4: se uguale al livello, lo slot non si consuma.", "Casting with a 1st-4th level slot, roll 1d4: if it equals the slot level, it isn't spent.", caster=True, boon=True),
    _p24("boon_night_spirit", "Dono dello Spirito della notte", "Boon of the Night Spirit", ALL6, "Al buio diventi invisibile e resisti a quasi tutti i danni.", "In dim light or darkness you turn invisible and resist most damage.", boon=True),
    _p24("boon_truesight", "Dono della Vista veritiera", "Boon of Truesight", ALL6, "Vista veritiera fino a 60 piedi.", "Truesight out to 60 feet.", boon=True),
]

# Tutti i talenti selezionabili: 2014 (con effetti) e 2024 (solo testo).
ALL_FEATS: dict[str, FeatSpec] = {**FEATS, **{f.key: f for f in FEATS_2024}}

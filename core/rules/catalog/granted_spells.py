"""Incantesimi concessi dai privilegi (D4): dati meccanici minimi scritti da noi, mai testo dei manuali.

La chiave è l'indice SRD quando esiste: un incantesimo che il giocatore ha già non viene duplicato.
I Task 19-42 riempiono il dizionario e lo citano in ``FeatureSpec.granted_spells``."""
from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class GrantedSpell:
    key: str
    name: dict[str, str]
    level: int
    casting_time: str | None = None
    range_area: str | None = None
    duration: str | None = None
    is_concentration: bool = False
    is_ritual: bool = False
    attack_save: str | None = None
    damage_dice: str | None = None
    damage_type: str | None = None
    higher_levels_dice: str | None = None
    # Seconda parte del danno, di un altro tipo (Colpo infuocato: fuoco e radioso)
    extra_damage_dice: str | None = None
    extra_damage_type: str | None = None
    # Componenti («V, S, M»): servono ai controlli di lancio (Incantesimi Bestiali). Le riempie ``_COMPONENTS``.
    components: str | None = None
    # Scuola di magia (slug inglese): i privilegi delle scuole del Mago la leggono dall'incantesimo
    school: str | None = None


GRANTED_SPELLS: dict[str, GrantedSpell] = {
    # Combattente Totemico 2014 (Cercatore di Spiriti, Viandante Spirituale): solo come rituali
    "beast-sense": GrantedSpell(
        "beast-sense", {"it": "Percezione delle bestie", "en": "Beast Sense"}, 2, "1 azione", "Contatto",
        "Concentrazione, fino a 1 ora", is_concentration=True, is_ritual=True),
    "speak-with-animals": GrantedSpell(
        "speak-with-animals", {"it": "Parlare con gli animali", "en": "Speak with Animals"}, 1, "1 azione",
        "Personale", "10 minuti", is_ritual=True),
    "commune-with-nature": GrantedSpell(
        "commune-with-nature", {"it": "Comunione con la natura", "en": "Commune with Nature"}, 5, "1 minuto",
        "Personale", "Istantanea", is_ritual=True),
    # Domini del Chierico 2014: gli incantesimi di dominio, sempre preparati (D4)
    'command': GrantedSpell(
        'command', {"it": 'Comando', "en": 'Command'}, 1, '1 azione', '18 m', '1 round', attack_save='SAVE'),
    'identify': GrantedSpell(
        'identify', {"it": 'Identificare', "en": 'Identify'}, 1, '1 minuto', 'Contatto', 'Istantanea', is_ritual=True),
    'augury': GrantedSpell(
        'augury', {"it": 'Auspicio', "en": 'Augury'}, 2, '1 minuto', 'Personale', 'Istantanea', is_ritual=True),
    'suggestion': GrantedSpell(
        'suggestion', {"it": 'Suggestione', "en": 'Suggestion'}, 2, '1 azione', '9 m', 'Concentrazione, fino a 8 ore', is_concentration=True, attack_save='SAVE'),
    'nondetection': GrantedSpell(
        'nondetection', {"it": 'Anti-individuazione', "en": 'Nondetection'}, 3, '1 azione', 'Contatto', '8 ore'),
    'speak-with-dead': GrantedSpell(
        'speak-with-dead', {"it": 'Parlare con i morti', "en": 'Speak with Dead'}, 3, '1 azione', '3 m', '10 minuti'),
    'confusion': GrantedSpell(
        'confusion', {"it": 'Confusione', "en": 'Confusion'}, 4, '1 azione', '27 m', 'Concentrazione, fino a 1 minuto', is_concentration=True, attack_save='SAVE'),
    'arcane-eye': GrantedSpell(
        'arcane-eye', {"it": 'Occhio arcano', "en": 'Arcane Eye'}, 4, '1 azione', '9 m', 'Concentrazione, fino a 1 ora', is_concentration=True),
    'legend-lore': GrantedSpell(
        'legend-lore', {"it": 'Conoscenza delle leggende', "en": 'Legend Lore'}, 5, '10 minuti', 'Personale', 'Istantanea'),
    'scrying': GrantedSpell(
        'scrying', {"it": 'Scrutare', "en": 'Scrying'}, 5, '10 minuti', 'Personale', 'Concentrazione, fino a 10 minuti', is_concentration=True, attack_save='SAVE'),
    'divine-favor': GrantedSpell(
        'divine-favor', {"it": 'Favore divino', "en": 'Divine Favor'}, 1, '1 azione bonus', 'Personale', 'Concentrazione, fino a 1 minuto', is_concentration=True),
    'shield-of-faith': GrantedSpell(
        'shield-of-faith', {"it": 'Scudo della fede', "en": 'Shield of Faith'}, 1, '1 azione bonus', '18 m', 'Concentrazione, fino a 10 minuti', is_concentration=True),
    'magic-weapon': GrantedSpell(
        'magic-weapon', {"it": 'Arma magica', "en": 'Magic Weapon'}, 2, '1 azione bonus', 'Contatto', 'Concentrazione, fino a 1 ora', is_concentration=True),
    'spiritual-weapon': GrantedSpell(
        'spiritual-weapon', {"it": 'Arma spirituale', "en": 'Spiritual Weapon'}, 2, '1 azione bonus', '18 m', '1 minuto', attack_save='ATK', damage_dice='1d8', damage_type='force'),
    'spirit-guardians': GrantedSpell(
        'spirit-guardians', {"it": 'Spiriti guardiani', "en": 'Spirit Guardians'}, 3, '1 azione', 'Personale', 'Concentrazione, fino a 10 minuti', is_concentration=True),
    'crusaders-mantle': GrantedSpell(
        'crusaders-mantle', {"it": 'Manto del crociato', "en": "Crusader's Mantle"}, 3, '1 azione', 'Personale (raggio 9 m)', 'Concentrazione, fino a 1 minuto', is_concentration=True),
    'freedom-of-movement': GrantedSpell(
        'freedom-of-movement', {"it": 'Libertà di movimento', "en": 'Freedom of Movement'}, 4, '1 azione', 'Contatto', '1 ora'),
    'stoneskin': GrantedSpell(
        'stoneskin', {"it": 'Pelle di pietra', "en": 'Stoneskin'}, 4, '1 azione', 'Contatto', 'Concentrazione, fino a 1 ora', is_concentration=True),
    'hold-monster': GrantedSpell(
        'hold-monster', {"it": 'Bloccare mostri', "en": 'Hold Monster'}, 5, '1 azione', '27 m', 'Concentrazione, fino a 1 minuto', is_concentration=True, attack_save='SAVE'),
    'flame-strike': GrantedSpell(
        'flame-strike', {"it": 'Colpo infuocato', "en": 'Flame Strike'}, 5, '1 azione', '18 m', 'Istantanea', attack_save='SAVE', damage_dice='4d6', damage_type='fire', higher_levels_dice='1d6',
        extra_damage_dice='4d6', extra_damage_type='radiant'),
    'disguise-self': GrantedSpell(
        'disguise-self', {"it": 'Camuffare se stesso', "en": 'Disguise Self'}, 1, '1 azione', 'Personale', '1 ora'),
    'charm-person': GrantedSpell(
        'charm-person', {"it": 'Charme su persone', "en": 'Charm Person'}, 1, '1 azione', '9 m', '1 ora', attack_save='SAVE'),
    'mirror-image': GrantedSpell(
        'mirror-image', {"it": 'Immagine speculare', "en": 'Mirror Image'}, 2, '1 azione', 'Personale', '1 minuto'),
    'pass-without-trace': GrantedSpell(
        'pass-without-trace', {"it": 'Passare senza tracce', "en": 'Pass Without Trace'}, 2, '1 azione', 'Personale', 'Concentrazione, fino a 1 ora', is_concentration=True),
    'dispel-magic': GrantedSpell(
        'dispel-magic', {"it": 'Dissolvi magie', "en": 'Dispel Magic'}, 3, '1 azione', '36 m', 'Istantanea'),
    'blink': GrantedSpell(
        'blink', {"it": 'Intermittenza', "en": 'Blink'}, 3, '1 azione', 'Personale', '1 minuto'),
    'polymorph': GrantedSpell(
        'polymorph', {"it": 'Metamorfosi', "en": 'Polymorph'}, 4, '1 azione', '18 m', 'Concentrazione, fino a 1 ora', is_concentration=True, attack_save='SAVE'),
    'dimension-door': GrantedSpell(
        'dimension-door', {"it": 'Porta dimensionale', "en": 'Dimension Door'}, 4, '1 azione', '150 m', 'Istantanea'),
    'dominate-person': GrantedSpell(
        'dominate-person', {"it": 'Dominare persone', "en": 'Dominate Person'}, 5, '1 azione', '18 m', 'Concentrazione, fino a 1 minuto', is_concentration=True, attack_save='SAVE'),
    'modify-memory': GrantedSpell(
        'modify-memory', {"it": 'Modificare memoria', "en": 'Modify Memory'}, 5, '1 azione', '9 m', 'Concentrazione, fino a 1 minuto', is_concentration=True, attack_save='SAVE'),
    'burning-hands': GrantedSpell(
        'burning-hands', {"it": 'Mani brucianti', "en": 'Burning Hands'}, 1, '1 azione', 'Personale', 'Istantanea', attack_save='SAVE', damage_dice='3d6', damage_type='fire', higher_levels_dice='1d6'),
    'faerie-fire': GrantedSpell(
        'faerie-fire', {"it": 'Fuoco fatato', "en": 'Faerie Fire'}, 1, '1 azione', '18 m', 'Concentrazione, fino a 1 minuto', is_concentration=True, attack_save='SAVE'),
    'scorching-ray': GrantedSpell(
        'scorching-ray', {"it": 'Raggio rovente', "en": 'Scorching Ray'}, 2, '1 azione', '36 m', 'Istantanea', attack_save='ATK', damage_dice='2d6', damage_type='fire'),
    'flaming-sphere': GrantedSpell(
        'flaming-sphere', {"it": 'Sfera infuocata', "en": 'Flaming Sphere'}, 2, '1 azione', '18 m', 'Concentrazione, fino a 1 minuto', is_concentration=True, attack_save='SAVE', damage_dice='2d6', damage_type='fire', higher_levels_dice='1d6'),
    'daylight': GrantedSpell(
        'daylight', {"it": 'Luce diurna', "en": 'Daylight'}, 3, '1 azione', '18 m', '1 ora'),
    'fireball': GrantedSpell(
        'fireball', {"it": 'Palla di fuoco', "en": 'Fireball'}, 3, '1 azione', '45 m', 'Istantanea', attack_save='SAVE', damage_dice='8d6', damage_type='fire', higher_levels_dice='1d6'),
    'guardian-of-faith': GrantedSpell(
        'guardian-of-faith', {"it": 'Guardiano della fede', "en": 'Guardian of Faith'}, 4, '1 azione', '9 m', '8 ore'),
    'wall-of-fire': GrantedSpell(
        'wall-of-fire', {"it": 'Muro di fuoco', "en": 'Wall of Fire'}, 4, '1 azione', '36 m', 'Concentrazione, fino a 1 minuto', is_concentration=True, attack_save='SAVE', damage_dice='5d8', damage_type='fire', higher_levels_dice='1d8'),
    'animal-friendship': GrantedSpell(
        'animal-friendship', {"it": 'Amicizia con gli animali', "en": 'Animal Friendship'}, 1, '1 azione', '9 m', '24 ore', attack_save='SAVE'),
    'barkskin': GrantedSpell(
        'barkskin', {"it": 'Pelle coriacea', "en": 'Barkskin'}, 2, '1 azione', 'Contatto', 'Concentrazione, fino a 1 ora', is_concentration=True),
    'spike-growth': GrantedSpell(
        'spike-growth', {"it": 'Crescita di spine', "en": 'Spike Growth'}, 2, '1 azione', '45 m', 'Concentrazione, fino a 10 minuti', is_concentration=True),
    'plant-growth': GrantedSpell(
        'plant-growth', {"it": 'Crescita vegetale', "en": 'Plant Growth'}, 3, '1 azione', '45 m', 'Istantanea'),
    'wind-wall': GrantedSpell(
        'wind-wall', {"it": 'Muro di vento', "en": 'Wind Wall'}, 3, '1 azione', '36 m', 'Concentrazione, fino a 1 minuto', is_concentration=True, attack_save='SAVE', damage_dice='3d8', damage_type='bludgeoning'),
    'dominate-beast': GrantedSpell(
        'dominate-beast', {"it": 'Dominare bestie', "en": 'Dominate Beast'}, 4, '1 azione', '18 m', 'Concentrazione, fino a 1 minuto', is_concentration=True, attack_save='SAVE'),
    'grasping-vine': GrantedSpell(
        'grasping-vine', {"it": 'Rampicante afferrante', "en": 'Grasping Vine'}, 4, '1 azione bonus', '9 m', 'Concentrazione, fino a 1 minuto', is_concentration=True),
    'insect-plague': GrantedSpell(
        'insect-plague', {"it": 'Piaga di insetti', "en": 'Insect Plague'}, 5, '1 azione', '90 m', 'Concentrazione, fino a 10 minuti', is_concentration=True, attack_save='SAVE', damage_dice='4d10', damage_type='piercing', higher_levels_dice='1d10'),
    'tree-stride': GrantedSpell(
        'tree-stride', {"it": 'Passo arboreo', "en": 'Tree Stride'}, 5, '1 azione', 'Personale', 'Concentrazione, fino a 1 minuto', is_concentration=True),
    'fog-cloud': GrantedSpell(
        'fog-cloud', {"it": 'Nube di nebbia', "en": 'Fog Cloud'}, 1, '1 azione', '36 m', 'Concentrazione, fino a 1 ora', is_concentration=True),
    'thunderwave': GrantedSpell(
        'thunderwave', {"it": 'Onda tonante', "en": 'Thunderwave'}, 1, '1 azione', 'Personale', 'Istantanea', attack_save='SAVE', damage_dice='2d8', damage_type='thunder', higher_levels_dice='1d8'),
    'gust-of-wind': GrantedSpell(
        'gust-of-wind', {"it": 'Folata di vento', "en": 'Gust of Wind'}, 2, '1 azione', 'Personale', 'Concentrazione, fino a 1 minuto', is_concentration=True, attack_save='SAVE'),
    'shatter': GrantedSpell(
        'shatter', {"it": 'Frantumare', "en": 'Shatter'}, 2, '1 azione', '18 m', 'Istantanea', attack_save='SAVE', damage_dice='3d8', damage_type='thunder', higher_levels_dice='1d8'),
    'call-lightning': GrantedSpell(
        'call-lightning', {"it": 'Invocare fulmine', "en": 'Call Lightning'}, 3, '1 azione', '36 m', 'Concentrazione, fino a 10 minuti', is_concentration=True, attack_save='SAVE', damage_dice='3d10', damage_type='lightning', higher_levels_dice='1d10'),
    'sleet-storm': GrantedSpell(
        'sleet-storm', {"it": 'Tempesta di nevischio', "en": 'Sleet Storm'}, 3, '1 azione', '45 m', 'Concentrazione, fino a 1 minuto', is_concentration=True),
    'control-water': GrantedSpell(
        'control-water', {"it": 'Controllare acqua', "en": 'Control Water'}, 4, '1 azione', '90 m', 'Concentrazione, fino a 10 minuti', is_concentration=True, attack_save='SAVE', damage_dice='2d8', damage_type='bludgeoning'),
    'ice-storm': GrantedSpell(
        'ice-storm', {"it": 'Tempesta di ghiaccio', "en": 'Ice Storm'}, 4, '1 azione', '90 m', 'Istantanea', attack_save='SAVE', damage_dice='2d8', damage_type='bludgeoning', higher_levels_dice='1d8',
        extra_damage_dice='4d6', extra_damage_type='cold'),
    'destructive-wave': GrantedSpell(
        'destructive-wave', {"it": 'Onda distruttiva', "en": 'Destructive Wave'}, 5, '1 azione', 'Personale (raggio 9 m)', 'Istantanea', attack_save='SAVE', damage_dice='5d6', damage_type='thunder',
        extra_damage_dice='5d6', extra_damage_type='radiant|necrotic'),
    'bless': GrantedSpell(
        'bless', {"it": 'Benedizione', "en": 'Bless'}, 1, '1 azione', '9 m', 'Concentrazione, fino a 1 minuto', is_concentration=True),
    'cure-wounds': GrantedSpell(
        'cure-wounds', {"it": 'Cura ferite', "en": 'Cure Wounds'}, 1, '1 azione', 'Contatto', 'Istantanea'),
    'lesser-restoration': GrantedSpell(
        'lesser-restoration', {"it": 'Ristorare inferiore', "en": 'Lesser Restoration'}, 2, '1 azione', 'Contatto', 'Istantanea'),
    'beacon-of-hope': GrantedSpell(
        'beacon-of-hope', {"it": 'Faro di speranza', "en": 'Beacon of Hope'}, 3, '1 azione', '9 m', 'Concentrazione, fino a 1 minuto', is_concentration=True),
    'revivify': GrantedSpell(
        'revivify', {"it": 'Rivivificare', "en": 'Revivify'}, 3, '1 azione', 'Contatto', 'Istantanea'),
    'death-ward': GrantedSpell(
        'death-ward', {"it": 'Interdizione alla morte', "en": 'Death Ward'}, 4, '1 azione', 'Contatto', '8 ore'),
    'mass-cure-wounds': GrantedSpell(
        'mass-cure-wounds', {"it": 'Cura ferite di massa', "en": 'Mass Cure Wounds'}, 5, '1 azione', '18 m', 'Istantanea'),
    'raise-dead': GrantedSpell(
        'raise-dead', {"it": 'Rianimare morti', "en": 'Raise Dead'}, 5, '1 ora', 'Contatto', 'Istantanea'),
    'light': GrantedSpell(
        'light', {"it": 'Luce', "en": 'Light'}, 0, '1 azione', 'Contatto', '1 ora'),
    # Druido 2014: incantesimi dei territori del Circolo della Terra e Mille Forme (Circolo della Luna)
    'hold-person': GrantedSpell(
        'hold-person', {"it": 'Bloccare persone', "en": 'Hold Person'}, 2, '1 azione', '18 m', 'Concentrazione, fino a 1 minuto', is_concentration=True, attack_save='SAVE'),
    'slow': GrantedSpell(
        'slow', {"it": 'Lentezza', "en": 'Slow'}, 3, '1 azione', '36 m', 'Concentrazione, fino a 1 minuto', is_concentration=True, attack_save='SAVE'),
    'cone-of-cold': GrantedSpell(
        'cone-of-cold', {"it": 'Cono di freddo', "en": 'Cone of Cold'}, 5, '1 azione', 'Personale', 'Istantanea', attack_save='SAVE', damage_dice='8d8', damage_type='cold', higher_levels_dice='1d8'),
    'misty-step': GrantedSpell(
        'misty-step', {"it": 'Passo velato', "en": 'Misty Step'}, 2, '1 azione bonus', 'Personale', 'Istantanea'),
    'water-walk': GrantedSpell(
        'water-walk', {"it": "Camminare sull'acqua", "en": 'Water Walk'}, 3, '1 azione', '9 m', '1 ora', is_ritual=True),
    'water-breathing': GrantedSpell(
        'water-breathing', {"it": "Respirare sott'acqua", "en": 'Water Breathing'}, 3, '1 azione', '9 m', '24 ore', is_ritual=True),
    'conjure-elemental': GrantedSpell(
        'conjure-elemental', {"it": 'Evocare elementale', "en": 'Conjure Elemental'}, 5, '1 minuto', '27 m', 'Concentrazione, fino a 1 ora', is_concentration=True),
    'blur': GrantedSpell(
        'blur', {"it": 'Annebbiare', "en": 'Blur'}, 2, '1 azione', 'Personale', 'Concentrazione, fino a 1 minuto', is_concentration=True),
    'silence': GrantedSpell(
        'silence', {"it": 'Silenzio', "en": 'Silence'}, 2, '1 azione', '36 m', 'Concentrazione, fino a 10 minuti', is_concentration=True, is_ritual=True),
    'create-food-and-water': GrantedSpell(
        'create-food-and-water', {"it": 'Creare cibo e acqua', "en": 'Create Food and Water'}, 3, '1 azione', '9 m', 'Istantanea'),
    'protection-from-energy': GrantedSpell(
        'protection-from-energy', {"it": "Protezione dall'energia", "en": 'Protection From Energy'}, 3, '1 azione', 'Contatto', 'Concentrazione, fino a 1 ora', is_concentration=True),
    'blight': GrantedSpell(
        'blight', {"it": 'Avvizzire', "en": 'Blight'}, 4, '1 azione', '9 m', 'Istantanea', attack_save='SAVE', damage_dice='8d8', damage_type='necrotic', higher_levels_dice='1d8'),
    'hallucinatory-terrain': GrantedSpell(
        'hallucinatory-terrain', {"it": 'Terreno illusorio', "en": 'Hallucinatory Terrain'}, 4, '10 minuti', '90 m', '24 ore'),
    'wall-of-stone': GrantedSpell(
        'wall-of-stone', {"it": 'Muro di pietra', "en": 'Wall of Stone'}, 5, '1 azione', '36 m', 'Concentrazione, fino a 10 minuti', is_concentration=True),
    'spider-climb': GrantedSpell(
        'spider-climb', {"it": 'Movimento del ragno', "en": 'Spider Climb'}, 2, '1 azione', 'Contatto', 'Concentrazione, fino a 1 ora', is_concentration=True),
    'divination': GrantedSpell(
        'divination', {"it": 'Divinazione', "en": 'Divination'}, 4, '1 azione', 'Personale', 'Istantanea', is_ritual=True),
    'invisibility': GrantedSpell(
        'invisibility', {"it": 'Invisibilità', "en": 'Invisibility'}, 2, '1 azione', 'Contatto', 'Concentrazione, fino a 1 ora', is_concentration=True),
    'haste': GrantedSpell(
        'haste', {"it": 'Velocità', "en": 'Haste'}, 3, '1 azione', '9 m', 'Concentrazione, fino a 1 minuto', is_concentration=True),
    'dream': GrantedSpell(
        'dream', {"it": 'Sogno', "en": 'Dream'}, 5, '1 minuto', 'Speciale', '8 ore'),
    'meld-into-stone': GrantedSpell(
        'meld-into-stone', {"it": 'Fondersi nella pietra', "en": 'Meld Into Stone'}, 3, '1 azione', 'Contatto', '8 ore', is_ritual=True),
    'lightning-bolt': GrantedSpell(
        'lightning-bolt', {"it": 'Fulmine', "en": 'Lightning Bolt'}, 3, '1 azione', 'Personale', 'Istantanea', attack_save='SAVE', damage_dice='8d6', damage_type='lightning', higher_levels_dice='1d6'),
    'stone-shape': GrantedSpell(
        'stone-shape', {"it": 'Foggiare la pietra', "en": 'Stone Shape'}, 4, '1 azione', 'Contatto', 'Istantanea'),
    'passwall': GrantedSpell(
        'passwall', {"it": 'Passapareti', "en": 'Passwall'}, 5, '1 azione', '9 m', '1 ora'),
    'acid-arrow': GrantedSpell(
        'acid-arrow', {"it": 'Freccia acida di Melf', "en": 'Acid Arrow'}, 2, '1 azione', '27 m', 'Istantanea', attack_save='ATK', damage_dice='4d4', damage_type='acid', higher_levels_dice='1d4'),
    'darkness': GrantedSpell(
        'darkness', {"it": 'Oscurità', "en": 'Darkness'}, 2, '1 azione', '18 m', 'Concentrazione, fino a 10 minuti', is_concentration=True),
    'stinking-cloud': GrantedSpell(
        'stinking-cloud', {"it": 'Nube maleodorante', "en": 'Stinking Cloud'}, 3, '1 azione', '27 m', 'Concentrazione, fino a 1 minuto', is_concentration=True, attack_save='SAVE'),
    'locate-creature': GrantedSpell(
        'locate-creature', {"it": 'Localizzare creatura', "en": 'Locate Creature'}, 4, '1 azione', 'Personale', 'Concentrazione, fino a 1 ora', is_concentration=True),
    'web': GrantedSpell(
        'web', {"it": 'Ragnatela', "en": 'Web'}, 2, '1 azione', '18 m', 'Concentrazione, fino a 1 ora', is_concentration=True, attack_save='SAVE'),
    'gaseous-form': GrantedSpell(
        'gaseous-form', {"it": 'Forma gassosa', "en": 'Gaseous Form'}, 3, '1 azione', 'Contatto', 'Concentrazione, fino a 1 ora', is_concentration=True),
    'greater-invisibility': GrantedSpell(
        'greater-invisibility', {"it": 'Invisibilità superiore', "en": 'Greater Invisibility'}, 4, '1 azione', 'Contatto', 'Concentrazione, fino a 1 minuto', is_concentration=True),
    'cloudkill': GrantedSpell(
        'cloudkill', {"it": 'Nube mortale', "en": 'Cloudkill'}, 5, '1 azione', '36 m', 'Concentrazione, fino a 10 minuti', is_concentration=True, attack_save='SAVE', damage_dice='5d8', damage_type='poison', higher_levels_dice='1d8'),
    'alter-self': GrantedSpell(
        'alter-self', {"it": 'Alterare se stessi', "en": 'Alter Self'}, 2, '1 azione', 'Personale', 'Concentrazione, fino a 1 ora', is_concentration=True),
    # Monaco 2014: Arti dell'Ombra, Corpo Vuoto e le discipline dei Quattro Elementi (si lanciano col ki)
    'darkvision': GrantedSpell(
        'darkvision', {"it": 'Scurovisione', "en": 'Darkvision'}, 2, '1 azione', 'Contatto', '8 ore'),
    # Monaco 2024 (Guerriero degli Elementi): trucchetto 2024, assente dal catalogo SRD 2014
    'elementalism': GrantedSpell(
        'elementalism', {"it": 'Elementalismo', "en": 'Elementalism'}, 0, '1 azione', '9 m', 'Istantaneo'),
    'minor-illusion': GrantedSpell(
        'minor-illusion', {"it": 'Illusione minore', "en": 'Minor Illusion'}, 0, '1 azione', '9 m', '1 minuto'),
    'fly': GrantedSpell(
        'fly', {"it": 'Volare', "en": 'Fly'}, 3, '1 azione', 'Contatto', 'Concentrazione, fino a 10 minuti', is_concentration=True),
    'astral-projection': GrantedSpell(
        'astral-projection', {"it": 'Proiezione astrale', "en": 'Astral Projection'}, 9, '1 ora', '3 m', 'Speciale'),
    # Paladino 2014: incantesimi di giuramento che gli altri cataloghi non concedono
    'protection-from-evil-and-good': GrantedSpell(
        'protection-from-evil-and-good', {"it": 'Protezione dal bene e dal male', "en": 'Protection from Evil and Good'}, 1,
        '1 azione', 'Contatto', 'Concentrazione, fino a 10 minuti', is_concentration=True),
    'sanctuary': GrantedSpell(
        'sanctuary', {"it": 'Santuario', "en": 'Sanctuary'}, 1, '1 azione bonus', '9 m', '1 minuto', attack_save='SAVE'),
    'zone-of-truth': GrantedSpell(
        'zone-of-truth', {"it": 'Zona di verità', "en": 'Zone of Truth'}, 2, '1 azione', '18 m', '10 minuti', attack_save='SAVE'),
    'commune': GrantedSpell(
        'commune', {"it": 'Comunione', "en": 'Commune'}, 5, '1 minuto', 'Personale', '1 minuto', is_ritual=True),
    'ensnaring-strike': GrantedSpell(
        'ensnaring-strike', {"it": 'Colpo intrappolante', "en": 'Ensnaring Strike'}, 1, '1 azione bonus', 'Personale',
        'Concentrazione, fino a 1 minuto', is_concentration=True, attack_save='SAVE', damage_dice='1d6',
        damage_type='piercing', higher_levels_dice='1d6'),
    'moonbeam': GrantedSpell(
        'moonbeam', {"it": 'Bagliore lunare', "en": 'Moonbeam'}, 2, '1 azione', '36 m', 'Concentrazione, fino a 1 minuto',
        is_concentration=True, attack_save='SAVE', damage_dice='2d10', damage_type='radiant', higher_levels_dice='1d10'),
    'bane': GrantedSpell(
        'bane', {"it": 'Anatema', "en": 'Bane'}, 1, '1 azione', '9 m', 'Concentrazione, fino a 1 minuto', is_concentration=True,
        attack_save='SAVE'),
    'hunters-mark': GrantedSpell(
        'hunters-mark', {"it": 'Marchio del cacciatore', "en": "Hunter's Mark"}, 1, '1 azione bonus', '27 m',
        'Concentrazione, fino a 1 ora', is_concentration=True),
    'banishment': GrantedSpell(
        'banishment', {"it": 'Esilio', "en": 'Banishment'}, 4, '1 azione', '18 m', 'Concentrazione, fino a 1 minuto',
        is_concentration=True, attack_save='SAVE'),
    # Warlock 2014: suppliche occulte che concedono incantesimi (a volontà o una volta per riposo lungo con uno slot di Patto)
    'mage-armor': GrantedSpell(
        'mage-armor', {"it": 'Armatura magica', "en": 'Mage Armor'}, 1, '1 azione', 'Contatto', '8 ore'),
    'jump': GrantedSpell(
        'jump', {"it": 'Saltare', "en": 'Jump'}, 1, '1 azione', 'Contatto', '1 minuto'),
    'levitate': GrantedSpell(
        'levitate', {"it": 'Levitazione', "en": 'Levitate'}, 2, '1 azione', '18 m', 'Concentrazione, fino a 10 minuti',
        is_concentration=True, attack_save='SAVE'),
    'detect-magic': GrantedSpell(
        'detect-magic', {"it": 'Individuazione del magico', "en": 'Detect Magic'}, 1, '1 azione', 'Personale',
        'Concentrazione, fino a 10 minuti', is_concentration=True, is_ritual=True),
    'silent-image': GrantedSpell(
        'silent-image', {"it": 'Immagine silenziosa', "en": 'Silent Image'}, 1, '1 azione', '18 m',
        'Concentrazione, fino a 10 minuti', is_concentration=True),
    'find-familiar': GrantedSpell(
        'find-familiar', {"it": 'Trova famiglio', "en": 'Find Familiar'}, 1, '1 ora', '3 m', 'Istantanea', is_ritual=True),
    'bestow-curse': GrantedSpell(
        'bestow-curse', {"it": 'Scagliare maledizione', "en": 'Bestow Curse'}, 3, '1 azione', 'Contatto',
        'Concentrazione, fino a 1 minuto', is_concentration=True, attack_save='SAVE'),
    'compulsion': GrantedSpell(
        'compulsion', {"it": 'Compulsione', "en": 'Compulsion'}, 4, '1 azione', '9 m', 'Concentrazione, fino a 1 minuto',
        is_concentration=True, attack_save='SAVE'),
    # Paladino 2024 (Punizione del Paladino, Destriero Fedele): sempre preparati, un lancio gratuito per riposo lungo
    'divine-smite': GrantedSpell(
        'divine-smite', {"it": 'Punizione Divina', "en": 'Divine Smite'}, 1, '1 azione bonus', 'Personale', 'Istantanea'),
    'find-steed': GrantedSpell(
        'find-steed', {"it": 'Trova destriero', "en": 'Find Steed'}, 2, '1 azione', '9 m', 'Istantanea'),
}


# Componenti di ogni incantesimo concesso: dato meccanico («V, S, M»), non testo dei manuali.
_COMPONENTS: dict[str, str] = {
    "divine-smite": "V",  # Paladino 2024 (Punizione del Paladino): il danno lo calcola il flusso del colpo
    "find-steed": "V, S",  # Paladino 2024 (Destriero Fedele)
    "beast-sense": "S",
    "speak-with-animals": "V, S",
    "commune-with-nature": "V, S",
    "command": "V",
    "identify": "V, S, M",
    "augury": "V, S, M",
    "suggestion": "V, M",
    "nondetection": "V, S, M",
    "speak-with-dead": "V, S, M",
    "confusion": "V, S, M",
    "arcane-eye": "V, S, M",
    "legend-lore": "V, S, M",
    "scrying": "V, S, M",
    "divine-favor": "V, S",
    "shield-of-faith": "V, S, M",
    "magic-weapon": "V, S",
    "spiritual-weapon": "V, S",
    "spirit-guardians": "V, S, M",
    "crusaders-mantle": "V",
    "freedom-of-movement": "V, S, M",
    "stoneskin": "V, S, M",
    "hold-monster": "V, S, M",
    "flame-strike": "V, S, M",
    "disguise-self": "V, S",
    "charm-person": "V, S",
    "mirror-image": "V, S",
    "pass-without-trace": "V, S, M",
    "dispel-magic": "V, S",
    "blink": "V, S",
    "polymorph": "V, S, M",
    "dimension-door": "V",
    "dominate-person": "V, S",
    "modify-memory": "V, S",
    "burning-hands": "V, S",
    "faerie-fire": "V",
    "scorching-ray": "V, S",
    "flaming-sphere": "V, S, M",
    "daylight": "V, S",
    "fireball": "V, S, M",
    "guardian-of-faith": "V",
    "wall-of-fire": "V, S, M",
    "animal-friendship": "V, S, M",
    "barkskin": "V, S, M",
    "spike-growth": "V, S, M",
    "plant-growth": "V, S",
    "wind-wall": "V, S, M",
    "dominate-beast": "V, S",
    "grasping-vine": "V, S",
    "insect-plague": "V, S, M",
    "tree-stride": "V, S",
    "fog-cloud": "V, S",
    "thunderwave": "V, S",
    "gust-of-wind": "V, S, M",
    "shatter": "V, S, M",
    "call-lightning": "V, S",
    "sleet-storm": "V, S, M",
    "control-water": "V, S, M",
    "ice-storm": "V, S, M",
    "destructive-wave": "V",
    "bless": "V, S, M",
    "cure-wounds": "V, S",
    "lesser-restoration": "V, S",
    "beacon-of-hope": "V, S",
    "revivify": "V, S, M",
    "death-ward": "V, S",
    "mass-cure-wounds": "V, S",
    "raise-dead": "V, S, M",
    "light": "V, M",
    "hold-person": "V, S, M",
    "slow": "V, S, M",
    "cone-of-cold": "V, S, M",
    "misty-step": "V",
    "water-walk": "V, S, M",
    "water-breathing": "V, S, M",
    "conjure-elemental": "V, S, M",
    "blur": "V",
    "silence": "V, S",
    "create-food-and-water": "V, S",
    "protection-from-energy": "V, S",
    "blight": "V, S",
    "hallucinatory-terrain": "V, S, M",
    "wall-of-stone": "V, S, M",
    "spider-climb": "V, S, M",
    "divination": "V, S, M",
    "invisibility": "V, S, M",
    "haste": "V, S, M",
    "dream": "V, S, M",
    "meld-into-stone": "V, S",
    "lightning-bolt": "V, S, M",
    "stone-shape": "V, S, M",
    "passwall": "V, S, M",
    "acid-arrow": "V, S, M",
    "darkness": "V, M",
    "stinking-cloud": "V, S, M",
    "locate-creature": "V, S, M",
    "web": "V, S, M",
    "gaseous-form": "V, S, M",
    "greater-invisibility": "V, S",
    "cloudkill": "V, S",
    "alter-self": "V, S",
    "darkvision": "V, S, M",
    "minor-illusion": "S, M",
    "elementalism": "V, S",
    "fly": "V, S, M",
    "astral-projection": "V, S, M",
    "protection-from-evil-and-good": "V, S, M",
    "sanctuary": "V, S, M",
    "zone-of-truth": "V, S",
    "commune": "V, S, M",
    "ensnaring-strike": "V",
    "moonbeam": "V, S, M",
    "bane": "V, S, M",
    "hunters-mark": "V",
    "banishment": "V, S, M",
    "mage-armor": "V, S, M",
    "jump": "V, S, M",
    "levitate": "V, S, M",
    "detect-magic": "V, S",
    "silent-image": "V, S, M",
    "find-familiar": "V, S, M",
    "bestow-curse": "V, S",
    "compulsion": "V, S",
}
GRANTED_SPELLS["animate-dead"] = GrantedSpell(
    "animate-dead", {"it": "Animare morti", "en": "Animate Dead"}, 3, "1 minuto", "3 m", "Istantanea", attack_save=None)
_COMPONENTS["animate-dead"] = "V, S, M"
# Bardo 2024, Parole della Creazione: le due Parole del Potere sempre preparate
for _key, _it, _en in (("power-word-heal", "Parola del Potere: Guarigione", "Power Word Heal"),
                       ("power-word-kill", "Parola del Potere: Uccisione", "Power Word Kill")):
    GRANTED_SPELLS[_key] = GrantedSpell(_key, {"it": _it, "en": _en}, 9, "1 azione", "18 m", "Istantanea")
    _COMPONENTS[_key] = "V, S"
# Chierico 2024, incantesimi di dominio che il 2014 non aveva
for _spell, _comp in (
        (GrantedSpell("aid", {"it": "Aiuto", "en": "Aid"}, 2, "1 azione", "9 m", "8 ore"), "V, S, M"),
        (GrantedSpell("mass-healing-word", {"it": "Parola curativa di massa", "en": "Mass Healing Word"}, 3, "1 azione bonus", "18 m",
                      "Istantanea"), "V"),
        (GrantedSpell("aura-of-life", {"it": "Aura di vita", "en": "Aura of Life"}, 4, "1 azione", "Personale (9 m)",
                      "Concentrazione, fino a 10 minuti", is_concentration=True), "V"),
        (GrantedSpell("greater-restoration", {"it": "Ristorare superiore", "en": "Greater Restoration"}, 5, "1 azione", "Contatto",
                      "Istantanea"), "V, S, M"),
        (GrantedSpell("see-invisibility", {"it": "Vedere invisibile", "en": "See Invisibility"}, 2, "1 azione", "Personale", "1 ora"),
         "V, S, M"),
        (GrantedSpell("hypnotic-pattern", {"it": "Disegno ipnotico", "en": "Hypnotic Pattern"}, 3, "1 azione", "36 m",
                      "Concentrazione, fino a 1 minuto", is_concentration=True, attack_save="SAVE"), "S, M"),
        (GrantedSpell("guiding-bolt", {"it": "Dardo guida", "en": "Guiding Bolt"}, 1, "1 azione", "36 m", "1 round", attack_save="ATK",
                      damage_dice="4d6", damage_type="radiant", higher_levels_dice="1d6"), "V, S"),
        (GrantedSpell("fire-shield", {"it": "Scudo di fuoco", "en": "Fire Shield"}, 4, "1 azione", "Personale", "10 minuti"),
         "V, S, M"),
        (GrantedSpell("steel-wind-strike", {"it": "Colpo del vento d'acciaio", "en": "Steel Wind Strike"}, 5, "1 azione", "9 m",
                      "Istantanea", attack_save="ATK", damage_dice="6d10", damage_type="force"), "S, M")):
    GRANTED_SPELLS[_spell.key] = _spell
    _COMPONENTS[_spell.key] = _comp
# Paladino 2024, giuramenti: incantesimi che il 2014 non concedeva (Presenza Regale di Yolande non è nell'SRD)
for _spell, _comp in (
        (GrantedSpell("heroism", {"it": "Eroismo", "en": "Heroism"}, 1, "1 azione", "Contatto", "Concentrazione, fino a 1 minuto",
                      is_concentration=True), "V, S"),
        (GrantedSpell("enhance-ability", {"it": "Potenziare caratteristica", "en": "Enhance Ability"}, 2, "1 azione", "Contatto",
                      "Concentrazione, fino a 1 ora", is_concentration=True), "V, S, M"),
        (GrantedSpell("yolandes-regal-presence", {"it": "Presenza regale di Yolande", "en": "Yolande's Regal Presence"}, 5, "1 azione",
                      "Personale (3 m)", "Concentrazione, fino a 1 minuto", is_concentration=True, attack_save="SAVE"), "V, S, M")):
    GRANTED_SPELLS[_spell.key] = _spell
    _COMPONENTS[_spell.key] = _comp
# Druido 2024, circoli: incantesimi che il 2014 non concedeva
for _spell, _comp in (
        (GrantedSpell("fire-bolt", {"it": "Dardo di fuoco", "en": "Fire Bolt"}, 0, "1 azione", "36 m", "Istantanea", attack_save="ATK",
                      damage_dice="1d10", damage_type="fire"), "V, S"),
        (GrantedSpell("ray-of-frost", {"it": "Raggio di gelo", "en": "Ray of Frost"}, 0, "1 azione", "18 m", "Istantanea", attack_save="ATK",
                      damage_dice="1d8", damage_type="cold"), "V, S"),
        (GrantedSpell("shocking-grasp", {"it": "Contatto elettrizzante", "en": "Shocking Grasp"}, 0, "1 azione", "Contatto",
                      "Istantanea", attack_save="ATK", damage_dice="1d8", damage_type="lightning"), "V, S"),
        (GrantedSpell("acid-splash", {"it": "Spruzzo acido", "en": "Acid Splash"}, 0, "1 azione", "18 m", "Istantanea", attack_save="SAVE",
                      damage_dice="1d6", damage_type="acid"), "V, S"),
        (GrantedSpell("starry-wisp", {"it": "Fuoco fatuo stellare", "en": "Starry Wisp"}, 0, "1 azione", "18 m", "Istantanea",
                      attack_save="ATK", damage_dice="1d8", damage_type="radiant"), "V, S"),
        (GrantedSpell("guidance", {"it": "Guida", "en": "Guidance"}, 0, "1 azione", "Contatto", "Concentrazione, fino a 1 minuto",
                      is_concentration=True), "V, S"),
        (GrantedSpell("sleep", {"it": "Sonno", "en": "Sleep"}, 1, "1 azione", "18 m", "Concentrazione, fino a 1 minuto",
                      is_concentration=True, attack_save="SAVE"), "V, S, M"),
        (GrantedSpell("ray-of-sickness", {"it": "Raggio di infermità", "en": "Ray of Sickness"}, 1, "1 azione", "18 m", "Istantanea",
                      attack_save="ATK", damage_dice="2d8", damage_type="poison", higher_levels_dice="1d8"), "V, S"),
        (GrantedSpell("conjure-animals", {"it": "Evocare animali", "en": "Conjure Animals"}, 3, "1 azione", "18 m",
                      "Concentrazione, fino a 10 minuti", is_concentration=True, attack_save="SAVE", damage_dice="3d10",
                      damage_type="slashing", higher_levels_dice="1d10"), "V, S"),
        (GrantedSpell("fount-of-moonlight", {"it": "Fonte di luce lunare", "en": "Fount of Moonlight"}, 4, "1 azione", "Personale",
                      "Concentrazione, fino a 10 minuti", is_concentration=True), "V, S")):
    GRANTED_SPELLS[_spell.key] = _spell
    _COMPONENTS[_spell.key] = _comp
# Guerriero Psionico 2024 (Maestro Telecinetico)
GRANTED_SPELLS["telekinesis"] = GrantedSpell(
    "telekinesis", {"it": "Telecinesi", "en": "Telekinesis"}, 5, "1 azione", "18 m", "Concentrazione, fino a 10 minuti",
    is_concentration=True, attack_save="SAVE")
_COMPONENTS["telekinesis"] = "V, S"  # quelle dell'incantesimo; il Maestro Telecinetico le ignora, e l'app non le controlla
# Ranger 2024, Viandante Fatato e Stalker delle Tenebre: incantesimi sempre preparati che il 2014 non concedeva
for _spell, _comp in (
        (GrantedSpell("summon-fey", {"it": "Evocare fatato", "en": "Summon Fey"}, 3, "1 azione", "27 m", "Concentrazione, fino a 1 ora",
                      is_concentration=True), "V, S, M"),
        (GrantedSpell("mislead", {"it": "Inganno", "en": "Mislead"}, 5, "1 azione", "Personale", "Concentrazione, fino a 1 ora",
                      is_concentration=True), "S"),
        (GrantedSpell("rope-trick", {"it": "Trucco della corda", "en": "Rope Trick"}, 2, "1 azione", "Contatto", "1 ora"), "V, S, M"),
        (GrantedSpell("seeming", {"it": "Mascherare", "en": "Seeming"}, 5, "1 azione", "9 m", "8 ore", attack_save="SAVE"), "V, S"),
        (GrantedSpell("fear", {"it": "Paura", "en": "Fear"}, 3, "1 azione", "Personale (9 m)", "Concentrazione, fino a 1 minuto",
                      is_concentration=True, attack_save="SAVE"), "V, S, M")):
    GRANTED_SPELLS[_spell.key] = _spell
    _COMPONENTS[_spell.key] = _comp
# Stregone 2024 (Aberrante, Meccanica, Draconica): incantesimi sempre preparati che il 2014 non concedeva
for _spell, _comp in (
        (GrantedSpell("arms-of-hadar", {"it": "Braccia di Hadar", "en": "Arms of Hadar"}, 1, "1 azione", "Personale (3 m)", "Istantanea",
                      attack_save="SAVE", damage_dice="2d6", damage_type="necrotic", higher_levels_dice="1d6"), "V, S"),
        (GrantedSpell("dissonant-whispers", {"it": "Sussurri dissonanti", "en": "Dissonant Whispers"}, 1, "1 azione", "18 m", "Istantanea",
                      attack_save="SAVE", damage_dice="3d6", damage_type="psychic", higher_levels_dice="1d6"), "V"),
        (GrantedSpell("mind-sliver", {"it": "Scheggia mentale", "en": "Mind Sliver"}, 0, "1 azione", "18 m", "1 round",
                      attack_save="SAVE", damage_dice="1d6", damage_type="psychic"), "V"),
        (GrantedSpell("calm-emotions", {"it": "Calmare le emozioni", "en": "Calm Emotions"}, 2, "1 azione", "18 m",
                      "Concentrazione, fino a 1 minuto", is_concentration=True, attack_save="SAVE"), "V, S"),
        (GrantedSpell("detect-thoughts", {"it": "Individuazione dei pensieri", "en": "Detect Thoughts"}, 2, "1 azione", "Personale",
                      "Concentrazione, fino a 1 minuto", is_concentration=True), "V, S, M"),
        (GrantedSpell("hunger-of-hadar", {"it": "Fame di Hadar", "en": "Hunger of Hadar"}, 3, "1 azione", "45 m",
                      "Concentrazione, fino a 1 minuto", is_concentration=True), "V, S, M"),
        (GrantedSpell("sending", {"it": "Messaggio a distanza", "en": "Sending"}, 3, "1 azione", "Illimitata", "1 round"), "V, S, M"),
        (GrantedSpell("evards-black-tentacles", {"it": "Tentacoli neri di Evard", "en": "Evard's Black Tentacles"}, 4, "1 azione", "27 m",
                      "Concentrazione, fino a 1 minuto", is_concentration=True, attack_save="SAVE", damage_dice="3d6",
                      damage_type="bludgeoning"), "V, S, M"),
        (GrantedSpell("summon-aberration", {"it": "Evocare aberrazione", "en": "Summon Aberration"}, 4, "1 azione", "27 m",
                      "Concentrazione, fino a 1 ora", is_concentration=True), "V, S, M"),
        (GrantedSpell("rarys-telepathic-bond", {"it": "Legame telepatico di Rary", "en": "Rary's Telepathic Bond"}, 5, "1 azione", "9 m",
                      "1 ora", is_ritual=True), "V, S, M"),
        (GrantedSpell("alarm", {"it": "Allarme", "en": "Alarm"}, 1, "1 minuto", "9 m", "8 ore", is_ritual=True), "V, S, M"),
        (GrantedSpell("summon-construct", {"it": "Evocare costrutto", "en": "Summon Construct"}, 4, "1 azione", "3 m",
                      "Concentrazione, fino a 1 ora", is_concentration=True), "V, S, M"),
        (GrantedSpell("wall-of-force", {"it": "Muro di forza", "en": "Wall of Force"}, 5, "1 azione", "36 m",
                      "Concentrazione, fino a 10 minuti", is_concentration=True), "V, S, M"),
        (GrantedSpell("chromatic-orb", {"it": "Sfera cromatica", "en": "Chromatic Orb"}, 1, "1 azione", "27 m", "Istantanea",
                      attack_save="ATK", damage_dice="3d8", damage_type="fire", higher_levels_dice="1d8"), "V, S, M"),
        (GrantedSpell("dragons-breath", {"it": "Soffio del drago", "en": "Dragon's Breath"}, 2, "1 azione bonus", "Contatto",
                      "Concentrazione, fino a 1 minuto", is_concentration=True), "V, S, M"),
        (GrantedSpell("charm-monster", {"it": "Charme su mostri", "en": "Charm Monster"}, 4, "1 azione", "9 m", "1 ora",
                      attack_save="SAVE"), "V, S"),
        (GrantedSpell("summon-dragon", {"it": "Evocare drago", "en": "Summon Dragon"}, 5, "1 azione", "18 m",
                      "Concentrazione, fino a 1 ora", is_concentration=True), "V, S, M")):
    GRANTED_SPELLS[_spell.key] = _spell
    _COMPONENTS[_spell.key] = _comp
# Warlock 2024 (Contattare il Patrono): sempre preparato, un lancio gratuito per riposo lungo
GRANTED_SPELLS["contact-other-plane"] = GrantedSpell(
    "contact-other-plane", {"it": "Contattare altro piano", "en": "Contact Other Plane"}, 5, "1 minuto", "Personale", "1 minuto", is_ritual=True)
_COMPONENTS["contact-other-plane"] = "V"
# Scuola degli incantesimi concessi che un privilegio del Mago può aggiungere al libro o far lanciare
_SCHOOLS = {"contact-other-plane": "divination", "animate-dead": "necromancy", "polymorph": "transmutation", "raise-dead": "necromancy",
            "power-word-heal": "enchantment", "power-word-kill": "enchantment",
            "divine-smite": "evocation", "find-steed": "conjuration",
            "summon-fey": "conjuration", "mislead": "illusion", "rope-trick": "transmutation", "seeming": "illusion",
            "fear": "illusion", "telekinesis": "transmutation", "charm-person": "enchantment", "mirror-image": "illusion", "command": "enchantment"}  # Magia Ammaliante del Bardo 2024
GRANTED_SPELLS = {key: replace(spell, components=_COMPONENTS.get(key), school=_SCHOOLS.get(key)) for key, spell in GRANTED_SPELLS.items()}

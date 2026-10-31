export type StandardBucket = 'action' | 'reaction'

export interface StandardAction {
  id: string
  bucket: StandardBucket
  it: { name: string; desc: string }
  en: { name: string; desc: string }
}

/** Azioni standard 5e (2014): elenco statico localizzato; nessuna azione bonus fissa. */
export const STANDARD_ACTIONS: StandardAction[] = [
  { id: 'attack', bucket: 'action',
    it: { name: 'Attacco', desc: 'Effettui un attacco in mischia o a distanza.' },
    en: { name: 'Attack', desc: 'Make a melee or ranged attack.' } },
  { id: 'cast', bucket: 'action',
    it: { name: 'Lanciare un incantesimo', desc: 'Lanci un incantesimo con tempo di lancio di 1 azione.' },
    en: { name: 'Cast a Spell', desc: 'Cast a spell with a casting time of 1 action.' } },
  { id: 'dash', bucket: 'action',
    it: { name: 'Scatto', desc: 'Il tuo movimento di questo turno raddoppia.' },
    en: { name: 'Dash', desc: 'Gain extra movement equal to your speed this turn.' } },
  { id: 'disengage', bucket: 'action',
    it: { name: 'Disimpegno', desc: 'Il tuo movimento non provoca attacchi di opportunità.' },
    en: { name: 'Disengage', desc: 'Your movement does not provoke opportunity attacks this turn.' } },
  { id: 'dodge', bucket: 'action',
    it: { name: 'Schivata', desc: 'Gli attacchi contro di te hanno svantaggio; vantaggio ai TS su Destrezza.' },
    en: { name: 'Dodge', desc: 'Attacks against you have disadvantage; advantage on Dexterity saves.' } },
  { id: 'help', bucket: 'action',
    it: { name: 'Aiuto', desc: 'Dai vantaggio a un alleato nella prossima prova o attacco.' },
    en: { name: 'Help', desc: 'Give an ally advantage on their next check or attack.' } },
  { id: 'hide', bucket: 'action',
    it: { name: 'Nascondersi', desc: 'Prova di Destrezza (Furtività) per sparire alla vista.' },
    en: { name: 'Hide', desc: 'Make a Dexterity (Stealth) check to avoid being seen.' } },
  { id: 'ready', bucket: 'action',
    it: { name: 'Preparare', desc: 'Scegli un evento e un\'azione da compiere come reazione.' },
    en: { name: 'Ready', desc: 'Choose a trigger and an action to take as a reaction.' } },
  { id: 'search', bucket: 'action',
    it: { name: 'Cercare', desc: 'Prova di Saggezza (Percezione) o Intelligenza (Investigare).' },
    en: { name: 'Search', desc: 'Make a Wisdom (Perception) or Intelligence (Investigation) check.' } },
  { id: 'use_object', bucket: 'action',
    it: { name: 'Usare un oggetto', desc: 'Interagisci con un secondo oggetto o usane uno che richiede un\'azione.' },
    en: { name: 'Use an Object', desc: 'Interact with a second object or use one that needs an action.' } },
  { id: 'opportunity', bucket: 'reaction',
    it: { name: 'Attacco di opportunità', desc: 'Un nemico lascia la tua portata: un attacco in mischia come reazione.' },
    en: { name: 'Opportunity Attack', desc: 'A foe leaves your reach: make one melee attack as a reaction.' } },
]

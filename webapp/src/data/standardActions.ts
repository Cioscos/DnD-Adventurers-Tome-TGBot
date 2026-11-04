export type StandardBucket = 'action' | 'reaction'
type Edition = '2014' | '2024'
type Text = { name: string; desc: string }

export interface StandardAction {
  id: string
  bucket: StandardBucket
  it: Text
  en: Text
  /** Solo in queste edizioni (default: entrambe). */
  editions?: Edition[]
  /** Testi alternativi per edizione: la voce resta la stessa, cambiano nome e descrizione. */
  by_edition?: Partial<Record<Edition, { it: Text; en: Text; skills?: string[] }>>
  /** Abilità tirabili dall'azione (chiavi del backend), da `POST /skills/{skill}/roll`. */
  skills?: string[]
}

/** Azioni standard 5e per edizione: elenco localizzato; nessuna azione bonus fissa. */
export const STANDARD_ACTIONS: StandardAction[] = [
  { id: 'attack', bucket: 'action',
    it: { name: 'Attacco', desc: 'Effettui un attacco in mischia o a distanza.' },
    en: { name: 'Attack', desc: 'Make a melee or ranged attack.' } },
  { id: 'cast', bucket: 'action',
    it: { name: 'Lanciare un incantesimo', desc: 'Lanci un incantesimo con tempo di lancio di 1 azione.' },
    en: { name: 'Cast a Spell', desc: 'Cast a spell with a casting time of 1 action.' },
    by_edition: { '2024': {
      it: { name: 'Magia', desc: 'Lanci un incantesimo con tempo di lancio di 1 azione o usi un privilegio che richiede l\'azione Magia.' },
      en: { name: 'Magic', desc: 'Cast a spell with a casting time of 1 action or use a feature that requires the Magic action.' } } } },
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
    en: { name: 'Help', desc: 'Give an ally advantage on their next check or attack.' },
    by_edition: { '2024': {
      it: { name: 'Aiuto', desc: 'Dai vantaggio a un alleato nella prossima prova o attacco, oppure presti primo soccorso a una creatura a 0 PF.' },
      en: { name: 'Help', desc: 'Give an ally advantage on their next check or attack, or administer first aid to a creature at 0 HP.' } } } },
  { id: 'hide', bucket: 'action', skills: ['stealth'],
    it: { name: 'Nascondersi', desc: 'Prova di Destrezza (Furtività) per sparire alla vista.' },
    en: { name: 'Hide', desc: 'Make a Dexterity (Stealth) check to avoid being seen.' },
    by_edition: { '2024': {
      it: { name: 'Nascondersi', desc: 'Prova di Furtività CD 15 con oscuramento o copertura e fuori dalla vista dei nemici: riuscendo sei Invisibile.' },
      en: { name: 'Hide', desc: 'DC 15 Stealth check while heavily obscured or behind cover and out of enemy sight: on success you are Invisible.' } } } },
  { id: 'influence', bucket: 'action', editions: ['2024'],
    skills: ['deception', 'intimidation', 'performance', 'persuasion', 'animal_handling'],
    it: { name: 'Influenzare', desc: 'Esorti un mostro: Carisma (Inganno, Intimidire, Intrattenere, Persuasione) o Saggezza (Addestrare Animali) contro CD 15 o la sua Intelligenza.' },
    en: { name: 'Influence', desc: 'Urge a monster: Charisma (Deception, Intimidation, Performance, Persuasion) or Wisdom (Animal Handling) against DC 15 or its Intelligence.' } },
  { id: 'ready', bucket: 'action',
    it: { name: 'Preparare', desc: 'Scegli un evento e un\'azione da compiere come reazione.' },
    en: { name: 'Ready', desc: 'Choose a trigger and an action to take as a reaction.' } },
  { id: 'search', bucket: 'action', skills: ['perception', 'investigation'],
    it: { name: 'Cercare', desc: 'Prova di Saggezza (Percezione) o Intelligenza (Investigare).' },
    en: { name: 'Search', desc: 'Make a Wisdom (Perception) or Intelligence (Investigation) check.' },
    by_edition: { '2024': {
      skills: ['insight', 'medicine', 'perception', 'survival'],
      it: { name: 'Cercare', desc: 'Prova di Saggezza (Intuizione, Medicina, Percezione o Sopravvivenza).' },
      en: { name: 'Search', desc: 'Make a Wisdom check (Insight, Medicine, Perception or Survival).' } } } },
  { id: 'study', bucket: 'action', editions: ['2024'],
    skills: ['arcana', 'history', 'investigation', 'nature', 'religion'],
    it: { name: 'Studiare', desc: 'Prova di Intelligenza (Arcano, Indagare, Natura, Religione o Storia) per richiamare informazioni.' },
    en: { name: 'Study', desc: 'Intelligence check (Arcana, History, Investigation, Nature or Religion) to recall information.' } },
  { id: 'use_object', bucket: 'action',
    it: { name: 'Usare un oggetto', desc: 'Interagisci con un secondo oggetto o usane uno che richiede un\'azione.' },
    en: { name: 'Use an Object', desc: 'Interact with a second object or use one that needs an action.' },
    by_edition: { '2024': {
      it: { name: 'Utilizzare', desc: 'Usi un oggetto non magico che richiede un\'azione; l\'interazione gratuita resta una per turno.' },
      en: { name: 'Utilize', desc: 'Use a nonmagical object that needs an action; the free interaction stays one per turn.' } } } },
  { id: 'opportunity', bucket: 'reaction',
    it: { name: 'Attacco di opportunità', desc: 'Un nemico lascia la tua portata: un attacco in mischia come reazione.' },
    en: { name: 'Opportunity Attack', desc: 'A foe leaves your reach: make one melee attack as a reaction.' } },
]

/** Azioni valide per l'edizione, con nome e testo già risolti. */
export function standardActionsFor(edition: Edition | undefined): StandardAction[] {
  const ed = edition ?? '2014'
  return STANDARD_ACTIONS
    .filter((a) => !a.editions || a.editions.includes(ed))
    .map((a) => ({ ...a, ...a.by_edition?.[ed] }))
}

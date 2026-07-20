/**
 * Scenari di misura (spec §Metodo di misura). Tutti manuali tranne `smoke`:
 * in modalità device è l'utente a eseguire i gesti sul telefono; in modalità
 * locale si eseguono a mano nel Chrome headed. Ogni gesto va ripetuto come
 * indicato per dare massa statistica alla trace.
 */
export const scenarios = [
  {
    id: 'smoke',
    title: 'Smoke (verifica harness)',
    instructions: 'Nessuna azione richiesta.',
    auto: async (page) => {
      await page.evaluate(() => window.scrollTo(0, 200))
      await page.waitForTimeout(3000)
    },
  },
  {
    id: 'overlay-modal',
    title: 'Modale generica (ModalProvider)',
    instructions: 'Apri e chiudi 3 volte una modale generica (es. Skills → dettaglio di una abilità).',
  },
  {
    id: 'overlay-sheet',
    title: 'Bottom sheet (Sheet)',
    instructions: 'Apri e chiudi 3 volte uno sheet (es. Inventory → aggiungi oggetto).',
  },
  {
    id: 'overlay-select-confirm',
    title: 'SelectSheet / ConfirmSheet',
    instructions: 'Apri e chiudi 3 volte una selezione o conferma (es. cambio slot equipaggiamento).',
  },
  {
    id: 'overlay-roll-result',
    title: 'RollResultModal',
    instructions: 'Da Dice: tira 1d20 e chiudi il risultato. Ripeti 3 volte.',
  },
  {
    id: 'overlay-weapon-attack',
    title: 'WeaponAttackModal',
    instructions: 'Da Actions: apri un attacco con arma e chiudi. Ripeti 3 volte.',
  },
  {
    id: 'dice-full',
    title: 'Animazione dadi completa',
    instructions: 'Tiro con animazione 3D fino al risultato. Ripeti 2 volte.',
  },
  {
    id: 'swiper-hub',
    title: 'Swipe hub personaggio',
    instructions: 'Nella pagina personaggio: swipe avanti e indietro fra le 3 schermate, 4 passaggi totali.',
  },
  {
    id: 'nav-cold',
    title: 'Navigazione a freddo',
    instructions: 'Dal menu: entra in Spells, Inventory, Skills, HP e Notes tornando indietro ogni volta.',
  },
  {
    id: 'scroll-spells',
    title: 'Scroll lista incantesimi',
    instructions: 'In Spells: scorri la lista su e giù, poi espandi e richiudi 3 voci.',
  },
  {
    id: 'scroll-inventory',
    title: 'Scroll inventario',
    instructions: 'In Inventory: scorri la lista su e giù, poi apri e chiudi 3 oggetti.',
  },
  {
    id: 'scroll-skills',
    title: 'Scroll abilità',
    instructions: 'In Skills: scorri la lista su e giù, poi espandi e richiudi 3 voci.',
  },
  {
    id: 'scroll-history',
    title: 'Scroll storia tiri',
    instructions: 'In History: scorri la lista su e giù fino in fondo e torna su.',
  },
]

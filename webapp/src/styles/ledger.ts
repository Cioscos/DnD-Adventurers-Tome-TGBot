// Righe a registro (DESIGN.md, "Ledger Rows"): filetti, niente riempimento né raggio.
export const LEDGER_TITLE = 'font-cinzel text-xs font-bold uppercase tracking-widest text-dnd-gold-dim'
export const LEDGER_LABEL = 'min-w-0 font-cinzel text-xs font-bold uppercase tracking-wider leading-tight text-dnd-text-muted'
/** Etichetta a sinistra, valore a destra. */
export const LEDGER_ROW = 'flex w-full min-h-[48px] items-center justify-between gap-3 px-1 py-2 text-left hover:bg-dnd-surface/60 transition-colors'
/** Icona + voce, a due colonne su telefono: `my-0.5` tiene 4px fra i bersagli vicini. */
export const LEDGER_INDEX_ROW = 'my-0.5 flex w-full min-h-[48px] items-center gap-2.5 px-1 py-1 text-left'
/** Voce di una lista lunga: riga da chiusa, card solo da aperta (un incantesimo aperto è un'unità). */
export const ledgerEntry = (open: boolean) =>
  open
    ? 'my-2 overflow-hidden rounded-2xl border border-dnd-gold-dim/40 bg-dnd-surface'
    : 'border-b border-dnd-border/60'
/** Pallino di uno slot o di un uso: pieno = speso. Niente alone: non è un segnale. */
export const gemClass = (used: boolean) =>
  `hit-44 h-7 w-7 rounded-full border-2 transition-colors ${
    used ? 'border-dnd-gold-bright bg-dnd-gold' : 'border-dnd-gold-dim hover:border-dnd-gold-bright'
  }`

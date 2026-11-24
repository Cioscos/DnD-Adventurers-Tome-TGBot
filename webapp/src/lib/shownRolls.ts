/** I dadi da elencare accanto al totale, come `_shown_rolls` in `api/routers/dice.py`: con `khN`/`klN` solo quelli tenuti;
 * nessuno per il d100, dove i due d10 sono decine e unità e la loro somma non è il totale. */
export function shownRolls(notation: string | null | undefined, rolls: number[]): number[] {
  const kept = /k([hl])(\d+)/.exec(notation ?? '')
  if (kept) return [...rolls].sort((a, b) => (kept[1] === 'h' ? b - a : a - b)).slice(0, Number(kept[2]))
  return notation?.includes('d100') ? [] : rolls
}

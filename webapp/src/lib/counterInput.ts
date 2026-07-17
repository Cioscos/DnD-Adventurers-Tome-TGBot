/** Valida l'input manuale di un contatore: intero >= 0, clampato a max se presente.
 *  Ritorna null per input vuoto/non numerico/non intero. */
export function parseCounterInput(raw: string, max: number | null): number | null {
  const trimmed = raw.trim()
  if (trimmed === '') return null
  const n = Number(trimmed)
  if (!Number.isFinite(n) || !Number.isInteger(n)) return null
  const floored = Math.max(0, n)
  return max != null ? Math.min(floored, max) : floored
}

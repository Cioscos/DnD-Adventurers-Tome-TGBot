// webapp/src/dice/d100.ts

export type D100Role = 'tens' | 'units'

/**
 * Coppie (decine, unità) di d10 → somma dei percentili. Le facce valgono 1..10:
 * "10" è la cifra 0 (decine 10 → 00, unità 10 → 0), e 00 + 0 vale 100.
 */
export function pairD100(vals: number[]): number {
  let total = 0
  for (let i = 0; i < vals.length; i += 2) {
    const v = (vals[i] % 10) * 10 + vals[i + 1] % 10
    total += v === 0 ? 100 : v
  }
  return total
}

/** Etichetta di una faccia d10 quando il dado fa parte di un d100. */
export function d100FaceLabel(value: number, role: D100Role): string {
  const digit = value % 10
  return role === 'tens' ? `${digit}0` : String(digit)
}

// webapp/src/dice/rng.ts
import type { DiceKind } from './types'

const SIDES: Record<Exclude<DiceKind, 'd100'>, number> = {
  d4: 4,
  d6: 6,
  d8: 8,
  d10: 10,
  d12: 12,
  d20: 20,
}

/**
 * Genera un intero uniforme in [min, max] (incluso) usando crypto.getRandomValues
 * con rejection sampling per evitare bias modulo.
 */
function uniformInt(min: number, max: number): number {
  if (min > max) throw new Error('min > max')
  const range = max - min + 1
  const maxUint32 = 0xffffffff
  const limit = maxUint32 - (maxUint32 % range)
  const buf = new Uint32Array(1)
  for (let i = 0; i < 256; i++) {
    crypto.getRandomValues(buf)
    if (buf[0] < limit) return min + (buf[0] % range)
  }
  return min + (buf[0] % range)
}

/** Tira N volte un dado di tipo `kind`. d100 è restituito come 2 entry d10 (decine, unità). */
export function rollMany(
  kind: DiceKind,
  count: number,
): { kind: Exclude<DiceKind, 'd100'>; value: number }[] {
  const out: { kind: Exclude<DiceKind, 'd100'>; value: number }[] = []
  for (let i = 0; i < count; i++) {
    if (kind === 'd100') {
      // d10 faces are 1..10 (consistent with physics geometry); pairD100 maps
      // value 10 → digit 0 in percentile.
      out.push({ kind: 'd10', value: uniformInt(1, 10) })
      out.push({ kind: 'd10', value: uniformInt(1, 10) })
    } else {
      const sides = SIDES[kind]
      out.push({ kind, value: uniformInt(1, sides) })
    }
  }
  return out
}

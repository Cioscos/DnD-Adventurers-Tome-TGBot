/** Resistenza (metà) o vulnerabilità (doppio) applicata al danno. */
export type DamageModifier = 'half' | 'double' | null

export function applyDamageModifier(value: number, mod: DamageModifier): number {
  if (mod === 'half') return Math.floor(value / 2)
  if (mod === 'double') return value * 2
  return value
}

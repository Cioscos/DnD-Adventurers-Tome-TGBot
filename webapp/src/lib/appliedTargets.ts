type T = (k: string, o?: Record<string, unknown>) => string

/** I bersagli di un effetto di incantesimo per il testo del toast: chi lancia non si nomina per esteso, è «te stesso». */
export function appliedTargets(applied: { id: number; name: string }[], casterId: number, t: T): string {
  return applied.map((a) => (a.id === casterId ? t('character.spells.effect_self') : a.name)).join(', ')
}

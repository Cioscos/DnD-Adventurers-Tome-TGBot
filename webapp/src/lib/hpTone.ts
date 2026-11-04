/** Colore e alone del numero PF: stesse soglie (75/25) della barra in HPGauge. */
export function hpNumeralTone(pct: number): string {
  if (pct >= 75) return 'text-dnd-emerald-bright hp-glow-emerald'
  if (pct > 25) return 'text-dnd-gold-bright hp-glow-gold'
  return 'text-dnd-crimson-bright hp-glow-crimson'
}

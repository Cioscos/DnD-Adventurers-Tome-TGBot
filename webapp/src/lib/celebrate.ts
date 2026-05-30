import confetti from 'canvas-confetti'

/**
 * Two bursts of gold/arcane confetti from the bottom corners — the celebratory
 * beat for a level-up. Shared by the XP page and the multiclass level-up modal
 * so both level-up paths feel the same. Callers should gate this behind
 * `prefers-reduced-motion` (the toast + icon carry the signal otherwise).
 */
export function fireLevelUpConfetti(): void {
  const palette = ['#f4d06f', '#d4a64a', '#a78bfa', '#fff6c2']
  const base = { spread: 60, startVelocity: 45, ticks: 200, gravity: 0.8, colors: palette, zIndex: 9999 } as const
  confetti({ ...base, particleCount: 70, angle: 60, origin: { x: 0.05, y: 0.9 } })
  confetti({ ...base, particleCount: 70, angle: 120, origin: { x: 0.95, y: 0.9 } })
}

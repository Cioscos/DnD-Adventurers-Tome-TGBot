/** Durata di un effetto in round (1 round = 6 s): sopra i 10 round si legge in minuti od ore (100 → «10 minuti», 600 → «1 ora»). */
export function formatRounds(t: (key: string, opts?: Record<string, unknown>) => string, rounds: number): string {
  if (rounds <= 10) return t('character.turn.state_rounds_total', { n: rounds })
  const minutes = Math.round(rounds / 10)
  return minutes % 60 === 0
    ? t('character.turn.state_duration_hours', { count: minutes / 60 })
    : t('character.turn.state_duration_minutes', { count: minutes })
}

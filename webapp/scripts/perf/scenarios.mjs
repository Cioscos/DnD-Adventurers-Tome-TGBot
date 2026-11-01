/**
 * Scenari automatici dell'harness perf. REGOLA: solo lettura — aprire, chiudere,
 * navigare, scorrere. Mai tiri, salvataggi o toggle: gira sui dati reali.
 *
 * Ogni scenario: { id, title, run(ctx) } con ctx = { page, settle, go(hash), charId(), swipe(dx) }.
 */
export const scenarios = [
  {
    id: 'idle-home',
    title: 'Home ferma (5 s)',
    run: async ({ page, go }) => {
      await go('#/')
      await page.waitForTimeout(5000)
    },
  },
]

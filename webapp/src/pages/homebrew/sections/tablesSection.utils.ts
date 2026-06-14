import type { Table } from '@/lib/homebrew/types'

/**
 * Display a [lo, hi] tuple as "lo-hi", collapsing to "lo" when lo === hi.
 */
export function formatBin(bin: [number, number]): string {
  return bin[0] === bin[1] ? String(bin[0]) : `${bin[0]}-${bin[1]}`
}

/**
 * Inline validation mirroring the backend Table rules (#26) so the author sees
 * problems before the save 422s. Returns i18n {key, params} specs (#43 / D4).
 *
 * Lives in a `.utils.ts` (not the component file) so it can be exported and unit
 * tested without tripping `react-refresh/only-export-components`.
 */
export function computeTableWarnings(
  table: Table,
): Array<{ key: string; params?: Record<string, string> }> {
  const warnings: Array<{ key: string; params?: Record<string, string> }> = []
  // Overlapping bins — the backend rejects them (first match wins, so any later
  // overlapping bin is unreachable).
  const ordered = [...table.col_bins].sort((a, b) => a[0] - b[0])
  for (let i = 1; i < ordered.length; i++) {
    if (ordered[i][0] <= ordered[i - 1][1]) {
      warnings.push({
        key: 'homebrew.tables.warn_overlap',
        params: {
          a: formatBin(ordered[i - 1] as [number, number]),
          b: formatBin(ordered[i] as [number, number]),
        },
      })
      break
    }
  }
  // No outcome anywhere — the backend rejects an empty cells dict, and a table with
  // no filled cell does nothing at runtime.
  const hasOutcome = Object.values(table.cells).some((row) =>
    row.some((c) => c.trim() !== ''),
  )
  if (!hasOutcome) warnings.push({ key: 'homebrew.tables.warn_no_outcomes' })
  return warnings
}

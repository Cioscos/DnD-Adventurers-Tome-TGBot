import { describe, it, expect } from 'vitest'
import {
  computeTableWarnings,
  formatBin,
} from '@/pages/homebrew/sections/tablesSection.utils'
import type { Table } from '@/lib/homebrew/types'

function table(over: Partial<Table> = {}): Table {
  return {
    id: 'usura',
    row_axis: 'quality',
    col_axis: 'd20',
    col_bins: [
      [1, 5],
      [6, 10],
      [11, 20],
    ],
    cells: { pessima: ['X', 'D', 'S'] },
    ...over,
  }
}

describe('formatBin', () => {
  it('collapses lo === hi to a single number, else shows the range', () => {
    expect(formatBin([3, 3])).toBe('3')
    expect(formatBin([1, 5])).toBe('1-5')
  })
})

describe('computeTableWarnings (#43)', () => {
  it('returns no warnings for a well-formed table', () => {
    expect(computeTableWarnings(table())).toEqual([])
  })

  it('flags overlapping bins (mirrors the backend rejection)', () => {
    const w = computeTableWarnings(
      table({ col_bins: [[1, 5], [4, 10]], cells: { pessima: ['X', 'D'] } }),
    )
    expect(w.some((x) => x.key === 'homebrew.tables.warn_overlap')).toBe(true)
  })

  it('flags a table with no rows at all', () => {
    const w = computeTableWarnings(table({ cells: {} }))
    expect(w.some((x) => x.key === 'homebrew.tables.warn_no_outcomes')).toBe(true)
  })

  it('flags a table whose cells are all empty strings', () => {
    const w = computeTableWarnings(table({ cells: { pessima: ['', '', ''] } }))
    expect(w.some((x) => x.key === 'homebrew.tables.warn_no_outcomes')).toBe(true)
  })
})

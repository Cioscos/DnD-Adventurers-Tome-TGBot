import { describe, it, expect } from 'vitest'
import {
  formatRelative,
  formatAbsolute,
  dayKey,
  dayHeader,
} from '@/lib/relativeTime'

/**
 * Pure date helpers used by History/timelines. Tests pin the locale-aware
 * branches against the same Intl APIs the implementation uses, and feed a fixed
 * `now` so the relative buckets are deterministic regardless of when the suite
 * runs. Dates are constructed with local components and read back with local
 * getters, so the assertions are timezone-independent.
 */
const baseOpts = {
  locale: 'it' as const,
  todayLabel: 'Oggi',
  yesterdayLabel: 'Ieri',
}

function at(y: number, mo: number, d: number, h = 12, mi = 0): Date {
  return new Date(y, mo, d, h, mi, 0, 0)
}

describe('formatRelative', () => {
  const now = at(2026, 5, 9, 15, 30) // 9 Jun 2026, 15:30 local

  it('same day → today label + HH:MM (zero-padded)', () => {
    expect(formatRelative(at(2026, 5, 9, 9, 5), { ...baseOpts, now })).toBe('Oggi 09:05')
  })

  it('yesterday → yesterday label + HH:MM', () => {
    expect(formatRelative(at(2026, 5, 8, 23, 0), { ...baseOpts, now })).toBe('Ieri 23:00')
  })

  it('2–6 days ago → Intl relative "day"', () => {
    const expected = new Intl.RelativeTimeFormat('it-IT', { numeric: 'auto' }).format(-3, 'day')
    expect(formatRelative(at(2026, 5, 6, 12, 0), { ...baseOpts, now })).toBe(expected)
  })

  it('7–30 days ago → Intl relative "week"', () => {
    // 30 May → 9 Jun = 10 days → round(10/7) = 1 week.
    const expected = new Intl.RelativeTimeFormat('it-IT', { numeric: 'auto' }).format(-1, 'week')
    expect(formatRelative(at(2026, 4, 30, 12, 0), { ...baseOpts, now })).toBe(expected)
  })

  it('older than 30 days, same year → absolute short date', () => {
    const d = at(2026, 2, 1, 12, 0) // 1 Mar 2026 (~100 days before now)
    const result = formatRelative(d, { ...baseOpts, now })
    expect(result).not.toBe('Oggi 12:00')
    const expected = new Intl.DateTimeFormat('it-IT', {
      day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
    }).format(d)
    expect(result).toBe(expected)
  })

  it('older than 30 days, different year → absolute long date with year', () => {
    const d = at(2024, 0, 15, 8, 0) // Jan 2024 → not the same year as 2026 now
    const result = formatRelative(d, { ...baseOpts, now })
    const expected = new Intl.DateTimeFormat('it-IT', {
      day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
    }).format(d)
    expect(result).toBe(expected)
  })

  it('accepts an ISO string (round-trips to the same local instant)', () => {
    const iso = at(2026, 5, 9, 9, 5).toISOString()
    expect(formatRelative(iso, { ...baseOpts, now })).toBe('Oggi 09:05')
  })

  it('does not mutate the supplied now/date when diffing', () => {
    const fixedNow = at(2026, 5, 9, 15, 30)
    const subject = at(2026, 5, 6, 12, 0)
    formatRelative(subject, { ...baseOpts, now: fixedNow })
    // diffInDays mutates copies, never the originals.
    expect(fixedNow.getHours()).toBe(15)
    expect(subject.getHours()).toBe(12)
  })
})

describe('formatAbsolute', () => {
  it('formats a full date/time in the requested locale', () => {
    const d = at(2026, 4, 23, 14, 32)
    const expected = new Intl.DateTimeFormat('it-IT', {
      day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
    }).format(d)
    expect(formatAbsolute(d, 'it')).toBe(expected)
  })

  it('defaults to the Italian locale', () => {
    const d = at(2026, 4, 23, 14, 32)
    expect(formatAbsolute(d)).toBe(formatAbsolute(d, 'it'))
  })
})

describe('dayKey', () => {
  it('returns a zero-padded YYYY-MM-DD bucket key', () => {
    expect(dayKey(at(2026, 0, 5))).toBe('2026-01-05') // month 0 → "01", day 5 → "05"
    expect(dayKey(at(2026, 11, 31))).toBe('2026-12-31')
  })

  it('accepts an ISO string', () => {
    expect(dayKey(at(2026, 0, 5).toISOString())).toBe('2026-01-05')
  })
})

describe('dayHeader', () => {
  it('formats a long-form day header in the requested locale', () => {
    const d = at(2026, 4, 23)
    const expected = new Intl.DateTimeFormat('it-IT', {
      day: '2-digit', month: 'long', year: 'numeric',
    }).format(d)
    expect(dayHeader(d, 'it')).toBe(expected)
  })
})

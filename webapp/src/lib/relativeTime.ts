/** Human-friendly relative date helpers used by History and other timelines. */

type Locale = 'it' | 'en'

const LOCALE_TAGS: Record<Locale, string> = {
  it: 'it-IT',
  en: 'en-US',
}

function pad(n: number): string {
  return n < 10 ? `0${n}` : String(n)
}

function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear()
    && a.getMonth() === b.getMonth()
    && a.getDate() === b.getDate()
  }

function diffInDays(a: Date, b: Date): number {
  const ms = a.setHours(0, 0, 0, 0) - b.setHours(0, 0, 0, 0)
  return Math.round(ms / 86_400_000)
}

export interface FormatRelativeOptions {
  locale: Locale
  todayLabel: string
  yesterdayLabel: string
  /** Use a year-less short format when the date is in the current year. */
  shortWhenSameYear?: boolean
  /** Optional reference "now" (mostly for tests). */
  now?: Date
}

/**
 * Same-day → "Oggi HH:MM"
 * Yesterday → "Ieri HH:MM"
 * Same day-of-week within a week → "lunedì HH:MM"
 * Past week → Intl.RelativeTimeFormat ("3 giorni fa", "2 settimane fa")
 * Older → absolute date
 */
export function formatRelative(iso: string | Date, opts: FormatRelativeOptions): string {
  const date = iso instanceof Date ? iso : new Date(iso)
  const now = opts.now ?? new Date()
  const tag = LOCALE_TAGS[opts.locale] ?? opts.locale
  const time = `${pad(date.getHours())}:${pad(date.getMinutes())}`

  if (isSameDay(new Date(date), new Date(now))) return `${opts.todayLabel} ${time}`

  const days = diffInDays(new Date(now), new Date(date))
  if (days === 1) return `${opts.yesterdayLabel} ${time}`

  // Use Intl.RelativeTimeFormat for the 2-30 day window to surface "X giorni fa".
  if (days >= 2 && days <= 30) {
    try {
      const rtf = new Intl.RelativeTimeFormat(tag, { numeric: 'auto' })
      if (days < 7) return rtf.format(-days, 'day')
      const weeks = Math.round(days / 7)
      return rtf.format(-weeks, 'week')
    } catch {
      // fall through to absolute date below
    }
  }

  const sameYear = date.getFullYear() === now.getFullYear()
  const dtfOpts: Intl.DateTimeFormatOptions = sameYear && opts.shortWhenSameYear !== false
    ? { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }
    : { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }

  try {
    return new Intl.DateTimeFormat(tag, dtfOpts).format(date)
  } catch {
    return date.toLocaleString(tag, dtfOpts)
  }
}

/** Absolute date formatted for tooltip (e.g. "23/05/2026 14:32"). */
export function formatAbsolute(iso: string | Date, locale: Locale = 'it'): string {
  const date = iso instanceof Date ? iso : new Date(iso)
  const tag = LOCALE_TAGS[locale] ?? locale
  try {
    return new Intl.DateTimeFormat(tag, {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    }).format(date)
  } catch {
    return date.toLocaleString(tag)
  }
}

/** Day-bucket key for grouping (e.g. "2026-05-23"). */
export function dayKey(iso: string | Date): string {
  const d = iso instanceof Date ? iso : new Date(iso)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** Long-form day header for sticky group titles ("23 maggio 2026"). */
export function dayHeader(iso: string | Date, locale: Locale): string {
  const d = iso instanceof Date ? iso : new Date(iso)
  const tag = LOCALE_TAGS[locale] ?? locale
  try {
    return new Intl.DateTimeFormat(tag, { day: '2-digit', month: 'long', year: 'numeric' }).format(d)
  } catch {
    return d.toLocaleDateString(tag, { day: '2-digit', month: 'long', year: 'numeric' })
  }
}

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

export function formatRelative(iso: string | Date, opts: FormatRelativeOptions): string {
  const date = iso instanceof Date ? iso : new Date(iso)
  const now = opts.now ?? new Date()
  const tag = LOCALE_TAGS[opts.locale] ?? opts.locale
  const time = `${pad(date.getHours())}:${pad(date.getMinutes())}`
  const a = new Date(date)
  const b = new Date(now)

  if (isSameDay(a, b)) return `${opts.todayLabel} ${time}`

  const days = diffInDays(new Date(now), new Date(date))
  if (days === 1) return `${opts.yesterdayLabel} ${time}`

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

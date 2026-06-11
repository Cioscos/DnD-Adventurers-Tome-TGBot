/**
 * Formatter numerici e orari legati al locale ATTIVO dell'app (i18n.language),
 * non a quello del browser: l'app vive dentro Telegram e la lingua la decide
 * l'utente/Telegram, non navigator.language (audit FE 2026-06-11, #V4).
 *
 * Gli orari sono SEMPRE 24h, coerenti con la Cronologia (lib/relativeTime.ts,
 * che formatta HH:MM a mano).
 */

const LOCALE_TAGS: Record<string, string> = {
  it: 'it-IT',
  en: 'en-US',
}

/** BCP-47 tag per il locale corto dell'app ('it' → 'it-IT'); passthrough altrimenti. */
export function localeTag(locale: string): string {
  return LOCALE_TAGS[locale] ?? locale
}

/** Intero con separatore delle migliaia del locale app ("2.700" it / "2,700" en). */
export function formatInt(value: number, locale: string): string {
  return new Intl.NumberFormat(localeTag(locale)).format(value)
}

/** Orario HH:MM in formato 24h indipendentemente dal locale. */
export function formatTime24(date: Date | string, locale: string): string {
  const d = typeof date === 'string' ? new Date(date) : date
  return new Intl.DateTimeFormat(localeTag(locale), {
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).format(d)
}

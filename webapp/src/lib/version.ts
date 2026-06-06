import changelogData from '@/data/changelog.json'

/** A single per-language list of bullet lines for one change category. */
export interface LocalizedLines {
  it: string[]
  en: string[]
}

export interface ChangelogEntry {
  /** SemVer string without the leading "v" (e.g. "2.0.0"). */
  version: string
  /** ISO date (YYYY-MM-DD) the version was released. */
  date: string
  /** Optional localized headline for the release. */
  title?: { it: string; en: string }
  added?: LocalizedLines
  improved?: LocalizedLines
  fixed?: LocalizedLines
}

interface ChangelogFile {
  entries: ChangelogEntry[]
}

const data = changelogData as ChangelogFile

/**
 * All changelog entries, newest first. The data file is authored with the most
 * recent release at index 0 and the CI guard enforces that ordering.
 */
export const changelog: ChangelogEntry[] = data.entries

/** The current application version = the version of the newest changelog entry. */
export function currentVersion(): string {
  return changelog[0]?.version ?? '0.0.0'
}

/** Pick the language list for a category, falling back to Italian (the default locale). */
export function localizedLines(lines: LocalizedLines | undefined, lang: string): string[] {
  if (!lines) return []
  return lang.startsWith('it') ? lines.it : (lines.en.length ? lines.en : lines.it)
}

/** Pick the localized title, falling back to Italian. */
export function localizedTitle(entry: ChangelogEntry, lang: string): string | undefined {
  if (!entry.title) return undefined
  return lang.startsWith('it') ? entry.title.it : (entry.title.en || entry.title.it)
}

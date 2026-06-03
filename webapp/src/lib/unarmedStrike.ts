/**
 * Frontend mirror of the backend unarmed-strike damage logic
 * (`core/game/attacks.py`). Kept in sync so the Actions page can describe the
 * *actual* damage the backend will roll instead of a hardcoded "1 + mod".
 */

/** Monk Martial Arts die by monk level: 1d4 (1-4), 1d6 (5-10), 1d8 (11-16), 1d10 (17-20). */
export function martialArtsDie(monkLevel: number): string {
  if (monkLevel <= 0) return ''
  if (monkLevel < 5) return '1d4'
  if (monkLevel < 11) return '1d6'
  if (monkLevel < 17) return '1d8'
  return '1d10'
}

type ClassLike = { class_name: string; level: number }

/**
 * Damage dice for a character's unarmed strike: the Monk's Martial Arts die when
 * the character has Monk levels, otherwise the flat "1". `class_name` is the stored
 * localized label, so we match both the Italian ("Monaco") and English ("Monk") keys
 * — same normalization the backend applies.
 */
export function unarmedDamageDice(classes: ClassLike[] | undefined): string {
  const monkLevel =
    (classes ?? []).find((c) => ['monaco', 'monk'].includes(c.class_name.trim().toLowerCase()))
      ?.level ?? 0
  return monkLevel > 0 ? martialArtsDie(monkLevel) : '1'
}

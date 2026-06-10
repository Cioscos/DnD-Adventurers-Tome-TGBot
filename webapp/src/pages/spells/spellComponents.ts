/** Pure round-trip logic for the spell `components` string ("V, S, M (un
 *  pizzico di sabbia)"). The DB stores a free string; the form edits it as
 *  V/S/M toggles + a material detail input. */

export type ComponentToken = 'V' | 'S' | 'M'

const CANONICAL_ORDER: readonly ComponentToken[] = ['V', 'S', 'M']

export interface ParsedComponents {
  tokens: ComponentToken[]
  material: string
  /** False when the raw string cannot be represented by the guided editor
   *  (unknown tokens, or a material detail without M) — the form falls back
   *  to the plain free-text input so nothing is lost. */
  conformant: boolean
}

export function parseComponents(raw: string): ParsedComponents {
  const trimmed = raw.trim()
  if (!trimmed) return { tokens: [], material: '', conformant: true }

  let rest = trimmed
  let material = ''
  const m = trimmed.match(/^(.*?)\s*\(([^()]*)\)$/s)
  if (m) {
    rest = m[1].trim()
    material = m[2].trim()
  }

  const tokens: ComponentToken[] = []
  let conformant = true
  for (const part of rest.split(',').map((p) => p.trim()).filter(Boolean)) {
    const upper = part.toUpperCase()
    if (upper === 'V' || upper === 'S' || upper === 'M') {
      if (!tokens.includes(upper)) tokens.push(upper)
    } else {
      conformant = false
    }
  }
  // A material detail without the M token would be dropped on serialize.
  if (material && !tokens.includes('M')) conformant = false
  if (tokens.length === 0) conformant = false

  tokens.sort((a, b) => CANONICAL_ORDER.indexOf(a) - CANONICAL_ORDER.indexOf(b))
  return { tokens, material, conformant }
}

export function serializeComponents(tokens: readonly ComponentToken[], material: string): string {
  const ordered = CANONICAL_ORDER.filter((t) => tokens.includes(t))
  if (ordered.length === 0) return ''
  const base = ordered.join(', ')
  const detail = material.trim()
  return ordered.includes('M') && detail ? `${base} (${detail})` : base
}

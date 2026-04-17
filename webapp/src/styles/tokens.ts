/**
 * Runtime access to design tokens for use inside JS (motion particle colors,
 * dynamic SVG fills, etc.). CSS variables remain the source of truth.
 */
export function cssVar(name: string): string {
  if (typeof window === 'undefined') return ''
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

export const tokens = {
  get gold() {
    return cssVar('--dnd-gold') || '#d4a847'
  },
  get goldBright() {
    return cssVar('--dnd-gold-bright') || '#f0c970'
  },
  get arcane() {
    return cssVar('--dnd-arcane') || '#9b59b6'
  },
  get crimson() {
    return cssVar('--dnd-crimson') || '#b33a3a'
  },
  get emerald() {
    return cssVar('--dnd-emerald') || '#3fa66a'
  },
}

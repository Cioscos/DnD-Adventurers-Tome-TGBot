// webapp/src/dice/packs/registry.ts
export const BUNDLED_PACKS = ['default', 'hell_dice', 'poison_dice'] as const
export type PackId = (typeof BUNDLED_PACKS)[number]

export function isBundledPack(id: string): id is PackId {
  return (BUNDLED_PACKS as readonly string[]).includes(id)
}

/**
 * Static preview swatches per bundled pack — drives the Settings thumbnails.
 * `body` is the primary die face color, `accent` the engraving/numeral tint.
 * (pack.json tints would also work but procedural-numerals packs reuse the
 * same ink/outline so they don't differentiate visually.)
 */
export const PACK_PREVIEW: Record<PackId, { body: string; accent: string }> = {
  default: { body: '#dfc9a0', accent: '#5b3b1f' },
  hell_dice: { body: '#5a0c0c', accent: '#ffd66b' },
  poison_dice: { body: '#2d5a3a', accent: '#bef0a0' },
}

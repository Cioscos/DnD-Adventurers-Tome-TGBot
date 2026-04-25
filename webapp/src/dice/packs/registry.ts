// webapp/src/dice/packs/registry.ts
export const BUNDLED_PACKS = ['default', 'hell_dice', 'poison_dice'] as const
export type PackId = (typeof BUNDLED_PACKS)[number]

export function isBundledPack(id: string): id is PackId {
  return (BUNDLED_PACKS as readonly string[]).includes(id)
}

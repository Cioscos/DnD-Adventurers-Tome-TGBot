// webapp/src/dice/packs/manifest.ts
import { z } from 'zod'
import type { DiceTint } from '../types'

const HexColor = z.string().regex(/^#[0-9a-fA-F]{6}$/)

const TintColorsSchema = z.object({
  ink: HexColor.optional(),
  outline: HexColor.optional(),
})

const DiceMapsSchema = z.object({
  albedo: z.string().min(1),
  normal: z.string().optional(),
  roughness: z.string().optional(),
  emissive: z.string().optional(),
  emissiveIntensity: z.number().min(0).max(5).optional(),
})

export const PackManifestSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  author: z.string().optional(),
  version: z.string().optional(),
  numerals: z.enum(['procedural', 'embedded']),
  tints: z
    .object({
      normal: TintColorsSchema.optional(),
      crit: TintColorsSchema.optional(),
      fumble: TintColorsSchema.optional(),
      arcane: TintColorsSchema.optional(),
      ember: TintColorsSchema.optional(),
    })
    .partial()
    .optional(),
  material: z
    .object({
      metalness: z.number().min(0).max(1).optional(),
      roughness: z.number().min(0).max(1).optional(),
      envMapIntensity: z.number().min(0).max(5).optional(),
    })
    .optional(),
  dice: z.object({
    d4: DiceMapsSchema.optional(),
    d6: DiceMapsSchema.optional(),
    d8: DiceMapsSchema.optional(),
    d10: DiceMapsSchema.optional(),
    d12: DiceMapsSchema.optional(),
    d20: DiceMapsSchema.optional(),
  }),
})

export type PackManifest = z.infer<typeof PackManifestSchema>
export type DiceMaps = z.infer<typeof DiceMapsSchema>
export type TintOverride = { ink?: string; outline?: string }

export function getTintOverride(manifest: PackManifest, tint: DiceTint): TintOverride | undefined {
  return manifest.tints?.[tint]
}

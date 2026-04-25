import * as THREE from 'three'
import type { DiceTint, DiceKind } from './types'
import { getNumeralTexture, type NumeralColors } from './numeralTexture'
import type { LoadedPack } from './packs/loader'

type DiceKindNoD100 = Exclude<DiceKind, 'd100'>

const palette: Record<DiceTint, {
  color: number
  emissive: number
  emissiveIntensity: number
  metalness: number
  roughness: number
}> = {
  normal: { color: 0xe6d49a, emissive: 0x000000, emissiveIntensity: 0, metalness: 0.15, roughness: 0.55 },
  crit:   { color: 0xf0c970, emissive: 0xf0c970, emissiveIntensity: 0.35, metalness: 0.3, roughness: 0.4 },
  fumble: { color: 0xb33030, emissive: 0xe85050, emissiveIntensity: 0.4, metalness: 0.2, roughness: 0.5 },
  arcane: { color: 0x6a56c8, emissive: 0x8b6ff0, emissiveIntensity: 0.3, metalness: 0.25, roughness: 0.45 },
  ember:  { color: 0xc46436, emissive: 0xd96040, emissiveIntensity: 0.3, metalness: 0.2, roughness: 0.5 },
}

const cache = new Map<string, THREE.MeshStandardMaterial>()

export function getDiceMaterial(
  tint: DiceTint = 'normal',
  pack?: LoadedPack | null,
  kind?: DiceKindNoD100,
): THREE.MeshStandardMaterial {
  const packMaps = pack && kind ? pack.maps[kind] : undefined
  const key = packMaps ? `pack:${pack!.manifest.id}:${kind}:${tint}` : `proc:${tint}`
  const cached = cache.get(key)
  if (cached) return cached

  if (packMaps) {
    const m = pack!.manifest.material ?? {}
    const mat = new THREE.MeshStandardMaterial({
      map: packMaps.albedo,
      normalMap: packMaps.normal ?? null,
      roughnessMap: packMaps.roughness ?? null,
      emissiveMap: packMaps.emissive ?? null,
      emissive: packMaps.emissive ? 0xffffff : 0x000000,
      emissiveIntensity: packMaps.emissiveIntensity ?? (packMaps.emissive ? 1.0 : 0),
      metalness: m.metalness ?? palette[tint].metalness,
      roughness: m.roughness ?? palette[tint].roughness,
      envMapIntensity: m.envMapIntensity ?? 1,
    })
    if (pack!.manifest.numerals === 'procedural') {
      mat.color.setHex(palette[tint].color)
    } else {
      mat.color.setHex(0xffffff)
    }
    cache.set(key, mat)
    return mat
  }

  const p = palette[tint]
  const mat = new THREE.MeshStandardMaterial({
    color: p.color,
    emissive: p.emissive,
    emissiveIntensity: p.emissiveIntensity,
    metalness: p.metalness,
    roughness: p.roughness,
  })
  cache.set(key, mat)
  return mat
}

export function disposeDiceMaterials(): void {
  for (const mat of cache.values()) mat.dispose()
  cache.clear()
  for (const mat of numeralMatCache.values()) mat.dispose()
  numeralMatCache.clear()
}

const numeralMatCache = new Map<string, THREE.MeshStandardMaterial>()

export function getNumeralMaterial(
  label: string,
  tint: DiceTint = 'normal',
  override?: NumeralColors,
): THREE.MeshStandardMaterial {
  const key = `${tint}:${label}:${override?.ink ?? '_'}:${override?.outline ?? '_'}`
  const cached = numeralMatCache.get(key)
  if (cached) return cached
  const tex = getNumeralTexture(label, tint, override)
  const mat = new THREE.MeshStandardMaterial({
    map: tex,
    transparent: true,
    alphaTest: 0.05,
    depthWrite: false,
    metalness: 0,
    roughness: 0.8,
    polygonOffset: true,
    polygonOffsetFactor: -2,
    polygonOffsetUnits: -2,
  })
  numeralMatCache.set(key, mat)
  return mat
}

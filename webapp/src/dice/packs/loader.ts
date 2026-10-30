// webapp/src/dice/packs/loader.ts
import * as THREE from 'three'
import { loadManifest, type PackManifest, type DiceMaps } from './manifest'
import type { PackId } from './registry'
import type { DiceKind } from '../types'

type DiceKindNoD100 = Exclude<DiceKind, 'd100'>

export interface LoadedDiceMaps {
  albedo: THREE.Texture
  normal?: THREE.Texture
  roughness?: THREE.Texture
  emissive?: THREE.Texture
  emissiveIntensity?: number
}

export interface LoadedPack {
  manifest: PackManifest
  maps: Partial<Record<DiceKindNoD100, LoadedDiceMaps>>
}

const cache = new Map<PackId, Promise<LoadedPack>>()
const allTextures = new Map<PackId, THREE.Texture[]>()

const loader = new THREE.TextureLoader()

async function loadTexture(url: string, srgb: boolean): Promise<THREE.Texture> {
  const tex = await loader.loadAsync(url)
  tex.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.LinearSRGBColorSpace
  tex.wrapS = THREE.ClampToEdgeWrapping
  tex.wrapT = THREE.ClampToEdgeWrapping
  return tex
}

async function loadKindMaps(packId: PackId, maps: DiceMaps): Promise<LoadedDiceMaps> {
  const base = `${import.meta.env.BASE_URL}dice-packs/${packId}`
  // Le mappe di un dado si scaricano in parallelo (prima: una dopo l'altra).
  const [albedo, normal, roughness, emissive] = await Promise.all([
    loadTexture(`${base}/${maps.albedo}`, true),
    maps.normal ? loadTexture(`${base}/${maps.normal}`, false) : undefined,
    maps.roughness ? loadTexture(`${base}/${maps.roughness}`, false) : undefined,
    maps.emissive ? loadTexture(`${base}/${maps.emissive}`, true) : undefined,
  ])
  const out: LoadedDiceMaps = { albedo }
  if (normal) out.normal = normal
  if (roughness) out.roughness = roughness
  if (emissive) out.emissive = emissive
  if (maps.emissiveIntensity !== undefined) out.emissiveIntensity = maps.emissiveIntensity
  return out
}

async function loadPackInternal(id: PackId): Promise<LoadedPack> {
  const manifest = await loadManifest(id)

  const maps: Partial<Record<DiceKindNoD100, LoadedDiceMaps>> = {}
  const collected: THREE.Texture[] = []
  // Tutti i dadi in parallelo: un pack con texture sono ~18 PNG da 1024².
  await Promise.all(
    (Object.keys(manifest.dice) as DiceKindNoD100[]).map(async (kindKey) => {
      const def = manifest.dice[kindKey]
      if (!def) return
      try {
        const loaded = await loadKindMaps(id, def)
        maps[kindKey] = loaded
        collected.push(loaded.albedo)
        if (loaded.normal) collected.push(loaded.normal)
        if (loaded.roughness) collected.push(loaded.roughness)
        if (loaded.emissive) collected.push(loaded.emissive)
      } catch (err) {
        console.warn(`[dice-pack] failed to load ${id}/${kindKey}`, err)
      }
    }),
  )
  allTextures.set(id, collected)
  return { manifest, maps }
}

export async function loadPack(id: PackId): Promise<LoadedPack> {
  const cached = cache.get(id)
  if (cached) return cached
  const promise = loadPackInternal(id).catch((err) => {
    cache.delete(id)
    throw err
  })
  cache.set(id, promise)
  return promise
}

export function disposePack(id: PackId): void {
  const textures = allTextures.get(id)
  if (textures) for (const tex of textures) tex.dispose()
  allTextures.delete(id)
  cache.delete(id)
}

export async function loadPackWithFallback(id: PackId): Promise<LoadedPack> {
  try {
    return await loadPack(id)
  } catch (err) {
    console.warn(`[dice-pack] falling back to default (failed to load ${id})`, err)
    if (id !== 'default') return await loadPack('default' as PackId)
    throw err
  }
}

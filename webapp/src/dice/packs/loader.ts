// webapp/src/dice/packs/loader.ts
import * as THREE from 'three'
import { PackManifestSchema, type PackManifest, type DiceMaps } from './manifest'
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
  const base = `/dice-packs/${packId}`
  const albedo = await loadTexture(`${base}/${maps.albedo}`, true)
  const out: LoadedDiceMaps = { albedo }
  if (maps.normal) out.normal = await loadTexture(`${base}/${maps.normal}`, false)
  if (maps.roughness) out.roughness = await loadTexture(`${base}/${maps.roughness}`, false)
  if (maps.emissive) out.emissive = await loadTexture(`${base}/${maps.emissive}`, true)
  if (maps.emissiveIntensity !== undefined) out.emissiveIntensity = maps.emissiveIntensity
  return out
}

async function loadPackInternal(id: PackId): Promise<LoadedPack> {
  const manifestRes = await fetch(`/dice-packs/${id}/pack.json`)
  if (!manifestRes.ok) throw new Error(`pack.json not found for ${id}`)
  const raw = await manifestRes.json()
  const manifest = PackManifestSchema.parse(raw)

  const maps: Partial<Record<DiceKindNoD100, LoadedDiceMaps>> = {}
  const collected: THREE.Texture[] = []
  for (const kindKey of Object.keys(manifest.dice) as DiceKindNoD100[]) {
    const def = manifest.dice[kindKey]
    if (!def) continue
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
  }
  allTextures.set(id, collected)
  return { manifest, maps }
}

export async function loadManifest(id: PackId): Promise<PackManifest> {
  const res = await fetch(`/dice-packs/${id}/pack.json`)
  if (!res.ok) throw new Error(`pack.json not found for ${id}`)
  return PackManifestSchema.parse(await res.json())
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

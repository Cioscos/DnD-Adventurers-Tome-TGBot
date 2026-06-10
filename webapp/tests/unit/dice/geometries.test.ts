import { describe, expect, it, vi } from 'vitest'
import * as THREE from 'three'
import type * as CANNON from 'cannon-es'
import { getDiceGeometry, type DiceGeometryData } from '@/dice/geometries'
import { faceUp } from '@/dice/physics/faceDetector'
import type { DiceKind } from '@/dice/types'

const KINDS: Array<Exclude<DiceKind, 'd100'>> = ['d4', 'd6', 'd8', 'd10', 'd12', 'd20']

/** Somma delle facce opposte sui dadi reali (d4 escluso: numerazione apex). */
const OPPOSITE_SUM: Record<string, number> = {
  d6: 7,
  d8: 9,
  d10: 11,
  d12: 13,
  d20: 21,
}

function shapeFaceVerts(shape: CANNON.ConvexPolyhedron, faceIdx: number): THREE.Vector3[] {
  return shape.faces[faceIdx].map((vi) => {
    const v = shape.vertices[vi]
    return new THREE.Vector3(v.x, v.y, v.z)
  })
}

function faceCentroid(verts: THREE.Vector3[]): THREE.Vector3 {
  const c = new THREE.Vector3()
  for (const v of verts) c.add(v)
  return c.multiplyScalar(1 / verts.length)
}

/** Normale alla cannon (primi 3 vertici, winding outward). */
function faceNormalFromVerts(verts: THREE.Vector3[]): THREE.Vector3 {
  const e1 = verts[1].clone().sub(verts[0])
  const e2 = verts[2].clone().sub(verts[0])
  return e1.cross(e2).normalize()
}

function minEdgeDistance(point: THREE.Vector3, verts: THREE.Vector3[]): number {
  let min = Infinity
  for (let i = 0; i < verts.length; i++) {
    const a = verts[i]
    const b = verts[(i + 1) % verts.length]
    const ab = b.clone().sub(a)
    const t = Math.min(1, Math.max(0, point.clone().sub(a).dot(ab) / (ab.lengthSq() || 1)))
    const closest = a.clone().add(ab.multiplyScalar(t))
    min = Math.min(min, point.distanceTo(closest))
  }
  return min
}

// Primo test del file: il primo getDiceGeometry costruisce le ConvexPolyhedron
// (cache module-level) — cannon logga console.error su winding/planarità rotti.
it('builds every cannon shape without warnings (winding + planarity canary)', () => {
  const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
  for (const kind of KINDS) getDiceGeometry(kind)
  expect(spy).not.toHaveBeenCalled()
  spy.mockRestore()
})

describe.each(KINDS)('%s geometry', (kind) => {
  const data: DiceGeometryData = getDiceGeometry(kind)

  it('has outward-wound faces', () => {
    for (let f = 0; f < data.shape.faces.length; f++) {
      const verts = shapeFaceVerts(data.shape, f)
      const normal = faceNormalFromVerts(verts)
      expect(normal.dot(faceCentroid(verts))).toBeGreaterThan(0)
    }
  })

  it('has planar faces', () => {
    for (let f = 0; f < data.shape.faces.length; f++) {
      const verts = shapeFaceVerts(data.shape, f)
      const normal = faceNormalFromVerts(verts)
      for (const v of verts) {
        expect(Math.abs(v.clone().sub(verts[0]).dot(normal))).toBeLessThan(1e-6)
      }
    }
  })

  it('detects the mapped value for every reading direction', () => {
    const up = new THREE.Vector3(0, 1, 0)
    for (const [valueStr, normal] of Object.entries(data.faceNormals)) {
      const q = new THREE.Quaternion().setFromUnitVectors(normal, up)
      const { value, dot } = faceUp(data.faceNormals, q)
      expect(value).toBe(Number(valueStr))
      expect(dot).toBeGreaterThan(0.999)
    }
  })

  it('keeps numeral ink inside the face polygon', () => {
    for (const frame of data.faceFrames) {
      const frameNormal = new THREE.Vector3(0, 0, 1).applyQuaternion(frame.quaternion)
      // trova la faccia su cui giace il quad
      const owner = data.shape.faces
        .map((_, f) => f)
        .find((f) => {
          const verts = shapeFaceVerts(data.shape, f)
          if (faceNormalFromVerts(verts).dot(frameNormal) < 0.999) return false
          const planeDist = frame.offsetPosition.clone().sub(verts[0]).dot(frameNormal)
          return Math.abs(planeDist) < 0.01
        })
      expect(owner).toBeDefined()
      const verts = shapeFaceVerts(data.shape, owner!)
      // glifo ≈ 72% del canvas → semiestensione inchiostro = size/2 × 0.72
      expect(minEdgeDistance(frame.offsetPosition, verts)).toBeGreaterThanOrEqual(
        frame.size * 0.36,
      )
    }
  })
})

describe.each(Object.entries(OPPOSITE_SUM))('%s opposite faces', (kind, sum) => {
  it(`sum to ${sum} like real dice`, () => {
    const data = getDiceGeometry(kind as DiceKind)
    const entries = Object.entries(data.faceNormals)
    for (const [valueStr, normal] of entries) {
      const opposite = entries.find(([, n]) => normal.dot(n) < -0.999)
      expect(opposite).toBeDefined()
      expect(Number(valueStr) + Number(opposite![0])).toBe(sum)
    }
  })
})

describe('d4 apex numbering', () => {
  const data = getDiceGeometry('d4')

  it('reads from vertex directions (4 entries, unit vectors)', () => {
    const values = Object.keys(data.faceNormals).map(Number).sort()
    expect(values).toEqual([1, 2, 3, 4])
    for (const dir of Object.values(data.faceNormals)) {
      expect(dir.length()).toBeCloseTo(1, 6)
    }
  })

  it('has 3 corner numerals per face (12 total)', () => {
    expect(data.faceFrames).toHaveLength(12)
    const counts = new Map<number, number>()
    for (const f of data.faceFrames) counts.set(f.value, (counts.get(f.value) ?? 0) + 1)
    // ogni valore appare su 3 facce (tutte quelle che toccano il suo vertice)
    expect([...counts.values()]).toEqual([3, 3, 3, 3])
  })

  it('resting on any face reads the opposite vertex unambiguously', () => {
    const down = new THREE.Vector3(0, -1, 0)
    for (let f = 0; f < data.shape.faces.length; f++) {
      const verts = shapeFaceVerts(data.shape, f)
      const q = new THREE.Quaternion().setFromUnitVectors(faceNormalFromVerts(verts), down)
      const { value, dot } = faceUp(data.faceNormals, q)
      expect(dot).toBeGreaterThan(0.999)
      // il vertice letto è quello NON appartenente alla faccia d'appoggio
      const missing = [0, 1, 2, 3].find((vi) => !data.shape.faces[f].includes(vi))!
      const mv = data.shape.vertices[missing]
      const missingDir = new THREE.Vector3(mv.x, mv.y, mv.z).normalize()
      expect(data.faceNormals[value].dot(missingDir)).toBeGreaterThan(0.999)
    }
  })
})

describe('d10 trapezohedron', () => {
  it('pairs each top-family kite with a parallel bottom-family kite', () => {
    const data = getDiceGeometry('d10')
    // con kite planari le facce antipodali sono parallele: ogni normale ha
    // un'antipodale a dot ≈ −1 (già coperto sopra) e nessuna coppia di
    // normali coincide (10 direzioni distinte)
    const normals = Object.values(data.faceNormals)
    expect(normals).toHaveLength(10)
    for (let i = 0; i < normals.length; i++) {
      for (let j = i + 1; j < normals.length; j++) {
        expect(normals[i].dot(normals[j])).toBeLessThan(0.999)
      }
    }
  })
})

describe('d8 numeral orientation', () => {
  it('keeps every digit upright when the polar axis is vertical', () => {
    // Convenzione dei d8 reali: con l'asse polare (±Y) verticale tutte le
    // cifre si leggono dritte — il loro up coincide con la proiezione di
    // world-Y sul piano della faccia (verso l'apice +Y sulla piramide alta,
    // via dall'apice −Y su quella bassa).
    const data = getDiceGeometry('d8')
    const worldY = new THREE.Vector3(0, 1, 0)
    expect(data.faceFrames).toHaveLength(8)
    for (const frame of data.faceFrames) {
      const up3D = new THREE.Vector3(0, 1, 0).applyQuaternion(frame.quaternion)
      const normal = new THREE.Vector3(0, 0, 1).applyQuaternion(frame.quaternion)
      const expected = worldY
        .clone()
        .sub(normal.clone().multiplyScalar(worldY.dot(normal)))
        .normalize()
      expect(up3D.dot(expected)).toBeGreaterThan(0.999)
    }
  })
})

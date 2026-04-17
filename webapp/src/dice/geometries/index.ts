import * as THREE from 'three'
import * as CANNON from 'cannon-es'
import type { DiceKind } from '../types'

const PHI = (1 + Math.sqrt(5)) / 2
const INV_PHI = 1 / PHI

type V = [number, number, number]

const TARGET_CIRCUMRADIUS = 0.38

function normalize(verts: V[], targetR: number = TARGET_CIRCUMRADIUS): V[] {
  const r = Math.max(...verts.map(([x, y, z]) => Math.hypot(x, y, z)))
  const k = targetR / r
  return verts.map(([x, y, z]) => [x * k, y * k, z * k])
}

function ensureOutward(vertices: V[], face: number[]): number[] {
  const v0 = vertices[face[0]]
  const v1 = vertices[face[1]]
  const v2 = vertices[face[2]]
  const ex = v1[0] - v0[0], ey = v1[1] - v0[1], ez = v1[2] - v0[2]
  const fx = v2[0] - v0[0], fy = v2[1] - v0[1], fz = v2[2] - v0[2]
  const nx = ey * fz - ez * fy
  const ny = ez * fx - ex * fz
  const nz = ex * fy - ey * fx
  let cx = 0, cy = 0, cz = 0
  for (const vi of face) {
    cx += vertices[vi][0]
    cy += vertices[vi][1]
    cz += vertices[vi][2]
  }
  cx /= face.length
  cy /= face.length
  cz /= face.length
  return nx * cx + ny * cy + nz * cz < 0 ? [...face].reverse() : [...face]
}

interface DieTemplate {
  vertices: V[]
  faces: number[][]
  faceValues: number[]
}

function buildBufferGeometry(t: DieTemplate): THREE.BufferGeometry {
  const pos: number[] = []
  const nor: number[] = []
  for (const face of t.faces) {
    for (let i = 1; i < face.length - 1; i++) {
      const v0 = t.vertices[face[0]]
      const v1 = t.vertices[face[i]]
      const v2 = t.vertices[face[i + 1]]
      const ex = v1[0] - v0[0], ey = v1[1] - v0[1], ez = v1[2] - v0[2]
      const fx = v2[0] - v0[0], fy = v2[1] - v0[1], fz = v2[2] - v0[2]
      let nx = ey * fz - ez * fy
      let ny = ez * fx - ex * fz
      let nz = ex * fy - ey * fx
      const m = Math.hypot(nx, ny, nz) || 1
      nx /= m; ny /= m; nz /= m
      pos.push(...v0, ...v1, ...v2)
      nor.push(nx, ny, nz, nx, ny, nz, nx, ny, nz)
    }
  }
  const g = new THREE.BufferGeometry()
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3))
  g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3))
  return g
}

function buildCannonShape(t: DieTemplate): CANNON.ConvexPolyhedron {
  return new CANNON.ConvexPolyhedron({
    vertices: t.vertices.map(([x, y, z]) => new CANNON.Vec3(x, y, z)),
    faces: t.faces.map((f) => [...f]),
  })
}

function buildFaceNormals(t: DieTemplate): Record<number, THREE.Vector3> {
  const map: Record<number, THREE.Vector3> = {}
  t.faces.forEach((face, idx) => {
    let cx = 0, cy = 0, cz = 0
    for (const vi of face) {
      cx += t.vertices[vi][0]
      cy += t.vertices[vi][1]
      cz += t.vertices[vi][2]
    }
    cx /= face.length; cy /= face.length; cz /= face.length
    const m = Math.hypot(cx, cy, cz) || 1
    map[t.faceValues[idx]] = new THREE.Vector3(cx / m, cy / m, cz / m)
  })
  return map
}

function buildFaceFrames(t: DieTemplate): FaceFrame[] {
  const frames: FaceFrame[] = []
  t.faces.forEach((face, idx) => {
    let cx = 0, cy = 0, cz = 0
    for (const vi of face) {
      cx += t.vertices[vi][0]
      cy += t.vertices[vi][1]
      cz += t.vertices[vi][2]
    }
    cx /= face.length; cy /= face.length; cz /= face.length
    const centroid = new THREE.Vector3(cx, cy, cz)
    const normal = centroid.clone().normalize()

    const worldY = new THREE.Vector3(0, 1, 0)
    let up = worldY.clone().sub(normal.clone().multiplyScalar(worldY.dot(normal)))
    if (up.lengthSq() < 0.01) {
      const worldX = new THREE.Vector3(1, 0, 0)
      up = worldX.clone().sub(normal.clone().multiplyScalar(worldX.dot(normal)))
    }
    up.normalize()

    let minEdgeDist = Infinity
    for (let i = 0; i < face.length; i++) {
      const a = new THREE.Vector3(...t.vertices[face[i]])
      const b = new THREE.Vector3(...t.vertices[face[(i + 1) % face.length]])
      const ab = b.clone().sub(a)
      const lenSq = ab.lengthSq() || 1
      const ac = centroid.clone().sub(a)
      const proj = Math.min(1, Math.max(0, ab.dot(ac) / lenSq))
      const closest = a.clone().add(ab.clone().multiplyScalar(proj))
      const d = centroid.distanceTo(closest)
      if (d < minEdgeDist) minEdgeDist = d
    }

    const offsetPosition = centroid.clone().add(normal.clone().multiplyScalar(0.002))
    const xAxis = new THREE.Vector3().crossVectors(up, normal).normalize()
    const basis = new THREE.Matrix4().makeBasis(xAxis, up, normal)
    const quaternion = new THREE.Quaternion().setFromRotationMatrix(basis)

    let halfW = 0
    let halfH = 0
    for (const vi of face) {
      const v = new THREE.Vector3(...t.vertices[vi])
      const rel = v.clone().sub(centroid)
      const px = Math.abs(rel.dot(xAxis))
      const py = Math.abs(rel.dot(up))
      if (px > halfW) halfW = px
      if (py > halfH) halfH = py
    }

    frames.push({
      value: t.faceValues[idx],
      centroid,
      normal,
      up,
      inradius: minEdgeDist,
      halfWidth: halfW,
      halfHeight: halfH,
      offsetPosition,
      quaternion,
    })
  })
  return frames
}

function applyWinding(verts: V[], faces: number[][]): number[][] {
  return faces.map((f) => ensureOutward(verts, f))
}

/** d4 — tetrahedron, 4 faces, values 1-4 */
function d4Template(): DieTemplate {
  const vertices = normalize([
    [1, 1, 1],
    [1, -1, -1],
    [-1, 1, -1],
    [-1, -1, 1],
  ])
  const rawFaces = [
    [0, 1, 2],
    [0, 3, 1],
    [0, 2, 3],
    [1, 3, 2],
  ]
  return {
    vertices,
    faces: applyWinding(vertices, rawFaces),
    faceValues: [1, 2, 3, 4],
  }
}

/** d6 — cube, 6 faces, values 1-6 (opposite faces sum to 7) */
function d6Template(): DieTemplate {
  const vertices = normalize([
    [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
    [-1, -1, 1],  [1, -1, 1],  [1, 1, 1],  [-1, 1, 1],
  ])
  const rawFaces = [
    [0, 3, 2, 1], // -Z
    [4, 5, 6, 7], // +Z
    [0, 1, 5, 4], // -Y
    [3, 7, 6, 2], // +Y
    [0, 4, 7, 3], // -X
    [1, 2, 6, 5], // +X
  ]
  return {
    vertices,
    faces: applyWinding(vertices, rawFaces),
    faceValues: [1, 6, 2, 5, 3, 4],
  }
}

/** d8 — octahedron, 8 faces, values 1-8 */
function d8Template(): DieTemplate {
  const vertices = normalize([
    [1, 0, 0], [-1, 0, 0],
    [0, 1, 0], [0, -1, 0],
    [0, 0, 1], [0, 0, -1],
  ])
  const rawFaces = [
    [0, 2, 4], [2, 1, 4], [1, 3, 4], [3, 0, 4],
    [0, 5, 2], [2, 5, 1], [1, 5, 3], [3, 5, 0],
  ]
  return {
    vertices,
    faces: applyWinding(vertices, rawFaces),
    faceValues: [1, 2, 3, 4, 5, 6, 7, 8],
  }
}

/** d10 — pentagonal trapezohedron, 10 kite faces, values 1-10 */
function d10Template(): DieTemplate {
  const verts: V[] = []
  verts.push([0, 1, 0])        // 0: top apex
  verts.push([0, -1, 0])       // 1: bottom apex
  const upperY = 0.15
  const lowerY = -0.15
  for (let i = 0; i < 5; i++) {
    const a = (i / 5) * Math.PI * 2
    verts.push([Math.cos(a), upperY, Math.sin(a)])
  }
  for (let i = 0; i < 5; i++) {
    const a = ((i + 0.5) / 5) * Math.PI * 2
    verts.push([Math.cos(a), lowerY, Math.sin(a)])
  }
  const vertices = normalize(verts)
  const rawFaces: number[][] = []
  for (let i = 0; i < 5; i++) {
    rawFaces.push([0, 2 + i, 7 + i, 2 + ((i + 1) % 5)])
  }
  for (let i = 0; i < 5; i++) {
    rawFaces.push([1, 7 + i, 2 + ((i + 1) % 5), 7 + ((i + 1) % 5)])
  }
  return {
    vertices,
    faces: applyWinding(vertices, rawFaces),
    faceValues: Array.from({ length: 10 }, (_, i) => i + 1),
  }
}

/** d12 — dodecahedron, 12 pentagonal faces, values 1-12 */
function d12Template(): DieTemplate {
  const vertices = normalize([
    [1, 1, 1], [1, 1, -1], [1, -1, 1], [1, -1, -1],
    [-1, 1, 1], [-1, 1, -1], [-1, -1, 1], [-1, -1, -1],
    [0, INV_PHI, PHI], [0, INV_PHI, -PHI], [0, -INV_PHI, PHI], [0, -INV_PHI, -PHI],
    [INV_PHI, PHI, 0], [INV_PHI, -PHI, 0], [-INV_PHI, PHI, 0], [-INV_PHI, -PHI, 0],
    [PHI, 0, INV_PHI], [PHI, 0, -INV_PHI], [-PHI, 0, INV_PHI], [-PHI, 0, -INV_PHI],
  ])
  const rawFaces = [
    [0, 8, 10, 2, 16],
    [0, 16, 17, 1, 12],
    [12, 1, 9, 5, 14],
    [8, 0, 12, 14, 4],
    [8, 4, 18, 6, 10],
    [2, 10, 6, 15, 13],
    [2, 13, 3, 17, 16],
    [17, 3, 11, 9, 1],
    [14, 5, 19, 18, 4],
    [7, 19, 5, 9, 11],
    [18, 19, 7, 15, 6],
    [3, 13, 15, 7, 11],
  ]
  return {
    vertices,
    faces: applyWinding(vertices, rawFaces),
    faceValues: Array.from({ length: 12 }, (_, i) => i + 1),
  }
}

/** d20 — icosahedron, 20 triangular faces, values 1-20 */
function d20Template(): DieTemplate {
  const vertices = normalize([
    [0, 1, PHI], [0, 1, -PHI], [0, -1, PHI], [0, -1, -PHI],
    [1, PHI, 0], [1, -PHI, 0], [-1, PHI, 0], [-1, -PHI, 0],
    [PHI, 0, 1], [PHI, 0, -1], [-PHI, 0, 1], [-PHI, 0, -1],
  ])
  const rawFaces = [
    [0, 2, 8], [0, 8, 4], [0, 4, 6], [0, 6, 10], [0, 10, 2],
    [3, 1, 11], [3, 11, 7], [3, 7, 5], [3, 5, 9], [3, 9, 1],
    [2, 5, 8], [5, 2, 7], [7, 2, 10], [7, 10, 11], [11, 10, 6],
    [11, 6, 1], [1, 6, 4], [1, 4, 9], [9, 4, 8], [8, 5, 9],
  ]
  return {
    vertices,
    faces: applyWinding(vertices, rawFaces),
    faceValues: Array.from({ length: 20 }, (_, i) => i + 1),
  }
}

const TEMPLATES: Record<Exclude<DiceKind, 'd100'>, DieTemplate> = {
  d4: d4Template(),
  d6: d6Template(),
  d8: d8Template(),
  d10: d10Template(),
  d12: d12Template(),
  d20: d20Template(),
}

export interface FaceFrame {
  value: number
  centroid: THREE.Vector3
  normal: THREE.Vector3
  up: THREE.Vector3
  inradius: number
  /** Half-extent of face in local 2D frame along right axis. */
  halfWidth: number
  /** Half-extent of face in local 2D frame along up axis. */
  halfHeight: number
  /** Slightly-offset world position in local die space to avoid z-fighting. */
  offsetPosition: THREE.Vector3
  /** Orientation that aligns a PlaneGeometry (+Z normal, +Y up) to this face. */
  quaternion: THREE.Quaternion
}

export interface DiceGeometryData {
  geometry: THREE.BufferGeometry
  shape: CANNON.ConvexPolyhedron
  faceNormals: Record<number, THREE.Vector3>
  /** Per-face frame data used to place numeral quads */
  faceFrames: FaceFrame[]
  /** Number of faces */
  faceCount: number
  /** Ordered list of all valid face values for fallback selection */
  faceValues: number[]
}

const cache = new Map<string, DiceGeometryData>()

export function getDiceGeometry(kind: DiceKind): DiceGeometryData {
  const key = kind === 'd100' ? 'd10' : kind
  const cached = cache.get(key)
  if (cached) return cached
  const template = TEMPLATES[key as Exclude<DiceKind, 'd100'>]
  const data: DiceGeometryData = {
    geometry: buildBufferGeometry(template),
    shape: buildCannonShape(template),
    faceNormals: buildFaceNormals(template),
    faceFrames: buildFaceFrames(template),
    faceCount: template.faces.length,
    faceValues: [...template.faceValues],
  }
  cache.set(key, data)
  return data
}

export function disposeDiceGeometries(): void {
  for (const { geometry } of cache.values()) {
    geometry.dispose()
  }
  cache.clear()
}

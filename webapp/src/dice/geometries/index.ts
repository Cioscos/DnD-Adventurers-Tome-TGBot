import * as THREE from 'three'
import * as CANNON from 'cannon-es'
import type { DiceKind } from '../types'
import { UV_LAYOUTS, cellForIndex, projectFaceUvs, type DiceUvKind } from './uvLayouts'

const TRIS_PER_FACE: Record<DiceUvKind, number> = {
  d4: 1,
  d6: 2,
  d8: 1,
  d10: 2,
  d12: 3,
  d20: 1,
}

const PHI = (1 + Math.sqrt(5)) / 2
const INV_PHI = 1 / PHI

type V = [number, number, number]

const TARGET_CIRCUMRADIUS = 0.38

// Altezza dell'anello equatoriale che rende PLANARI le facce kite del
// trapezoedro pentagonale (apici a y=±1, anello di raggio 1). Con altri valori
// il 4° vertice di ogni kite esce dal piano della faccia: la ConvexPolyhedron
// di cannon diventa invalida (contatti instabili) e il rigonfiamento taglia i
// quad dei numerali.
const D10_RING_Y =
  (2 * Math.sin(Math.PI / 5) - Math.sin((2 * Math.PI) / 5)) /
  (2 * Math.sin(Math.PI / 5) + Math.sin((2 * Math.PI) / 5))

/** Distanza del quad numerale dal piano della faccia (anti z-fighting). */
const NUMERAL_LIFT = 0.002

/** Lato del quad numerale = fattore × raggio di Chebyshev della faccia. */
const NUMERAL_SIZE_FACTOR: Record<DiceUvKind, number> = {
  d4: 0.7, // cifre per-angolo (numerazione apex)
  d6: 1.7,
  d8: 1.5,
  d10: 1.45,
  d12: 1.6,
  d20: 1.45,
}

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
  /**
   * Numerazione apex (d4): il valore letto appartiene al VERTICE rivolto in
   * alto, non a una faccia. vertexValues[i] = valore del vertice i.
   */
  vertexValues?: number[]
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

/** Normale planare (Newell) di una faccia con winding outward. */
function polygonNormal(verts: THREE.Vector3[]): THREE.Vector3 {
  const n = new THREE.Vector3()
  for (let i = 0; i < verts.length; i++) {
    const a = verts[i]
    const b = verts[(i + 1) % verts.length]
    n.x += (a.y - b.y) * (a.z + b.z)
    n.y += (a.z - b.z) * (a.x + b.x)
    n.z += (a.x - b.x) * (a.y + b.y)
  }
  return n.normalize()
}

interface FaceBasis {
  centroid: THREE.Vector3
  /** Vera normale del piano della faccia (NON la direzione del centroide: sul
   *  kite del d10 differiscono di ~19° e l'inclinazione affonderebbe i numerali). */
  normal: THREE.Vector3
  xAxis: THREE.Vector3
  yAxis: THREE.Vector3
  /** Vertici della faccia nel frame (xAxis, yAxis), relativi al centroide. */
  verts2D: Array<{ x: number; y: number }>
}

function buildFaceBasis(t: DieTemplate, face: number[]): FaceBasis {
  const verts = face.map((vi) => new THREE.Vector3(...t.vertices[vi]))
  const centroid = new THREE.Vector3()
  for (const v of verts) centroid.add(v)
  centroid.multiplyScalar(1 / verts.length)

  const normal = polygonNormal(verts)

  const worldY = new THREE.Vector3(0, 1, 0)
  let yAxis = worldY.clone().sub(normal.clone().multiplyScalar(worldY.dot(normal)))
  if (yAxis.lengthSq() < 0.01) {
    const worldX = new THREE.Vector3(1, 0, 0)
    yAxis = worldX.clone().sub(normal.clone().multiplyScalar(worldX.dot(normal)))
  }
  yAxis.normalize()
  // Frame right-handed: guardando la faccia da fuori, xAxis punta a destra.
  const xAxis = new THREE.Vector3().crossVectors(yAxis, normal).normalize()

  const verts2D = verts.map((v) => {
    const rel = v.clone().sub(centroid)
    return { x: rel.dot(xAxis), y: rel.dot(yAxis) }
  })
  return { centroid, normal, xAxis, yAxis, verts2D }
}

interface Point2D {
  x: number
  y: number
}

function norm2D(p: Point2D): Point2D {
  const l = Math.hypot(p.x, p.y) || 1
  return { x: p.x / l, y: p.y / l }
}

/**
 * Centro di Chebyshev (centro del massimo cerchio inscritto) di un poligono
 * convesso 2D. Grid-search a raffinamento dal centroide: la funzione
 * min-distanza-dai-lati è concava sul convesso, quindi la ricerca converge
 * all'ottimo globale. Triangolo equilatero → incentro; quadrato/pentagono
 * regolare → centro; kite (d10) → punto sull'asse di simmetria.
 */
function chebyshevCenter2D(pts: Point2D[]): { x: number; y: number; r: number } {
  const n = pts.length
  let cx = 0, cy = 0
  for (const p of pts) { cx += p.x; cy += p.y }
  cx /= n
  cy /= n

  // Rette dei lati con normale interna (positiva sul centroide).
  const edges: Array<{ nx: number; ny: number; d: number }> = []
  for (let i = 0; i < n; i++) {
    const a = pts[i]
    const b = pts[(i + 1) % n]
    let nx = -(b.y - a.y)
    let ny = b.x - a.x
    const len = Math.hypot(nx, ny) || 1
    nx /= len; ny /= len
    let d = -(nx * a.x + ny * a.y)
    if (nx * cx + ny * cy + d < 0) { nx = -nx; ny = -ny; d = -d }
    edges.push({ nx, ny, d })
  }
  const clearance = (x: number, y: number) => {
    let m = Infinity
    for (const e of edges) m = Math.min(m, e.nx * x + e.ny * y + e.d)
    return m
  }

  let bx = cx, by = cy, br = clearance(cx, cy)
  let span = 0
  for (const p of pts) span = Math.max(span, Math.hypot(p.x - cx, p.y - cy))
  let step = span / 2
  for (let round = 0; round < 6; round++) {
    for (let i = -2; i <= 2; i++) {
      for (let j = -2; j <= 2; j++) {
        const x = bx + (i * step) / 2
        const y = by + (j * step) / 2
        const r = clearance(x, y)
        if (r > br) { br = r; bx = x; by = y }
      }
    }
    step /= 2
  }
  return { x: bx, y: by, r: br }
}

function buildFaceNormals(t: DieTemplate): Record<number, THREE.Vector3> {
  const map: Record<number, THREE.Vector3> = {}
  if (t.vertexValues) {
    // d4 apex: il risultato è il vertice in alto (a riposo dot = 1.0, mai
    // ambiguo — un tetraedro fermo non ha alcuna FACCIA rivolta in su).
    t.vertexValues.forEach((value, vi) => {
      map[value] = new THREE.Vector3(...t.vertices[vi]).normalize()
    })
    return map
  }
  t.faces.forEach((face, idx) => {
    map[t.faceValues[idx]] = buildFaceBasis(t, face).normal
  })
  return map
}

function buildFaceFrames(t: DieTemplate, kind: DiceUvKind): FaceFrame[] {
  const frames: FaceFrame[] = []
  const sizeFactor = NUMERAL_SIZE_FACTOR[kind]

  t.faces.forEach((face, faceIdx) => {
    const { centroid, normal, xAxis, yAxis, verts2D } = buildFaceBasis(t, face)
    const cheby = chebyshevCenter2D(verts2D)

    const to3D = (p: Point2D) =>
      centroid
        .clone()
        .add(xAxis.clone().multiplyScalar(p.x))
        .add(yAxis.clone().multiplyScalar(p.y))

    const pushFrame = (value: number, center2D: Point2D, up2D: Point2D, size: number) => {
      const up3D = xAxis
        .clone()
        .multiplyScalar(up2D.x)
        .add(yAxis.clone().multiplyScalar(up2D.y))
        .normalize()
      const x3D = new THREE.Vector3().crossVectors(up3D, normal).normalize()
      const basis = new THREE.Matrix4().makeBasis(x3D, up3D, normal)
      frames.push({
        value,
        quaternion: new THREE.Quaternion().setFromRotationMatrix(basis),
        offsetPosition: to3D(center2D).add(normal.clone().multiplyScalar(NUMERAL_LIFT)),
        size,
      })
    }

    if (t.vertexValues) {
      // d4 apex: 3 cifre per faccia, una per angolo, ciascuna col valore del
      // vertice di quell'angolo e il top della cifra rivolto verso l'angolo
      // (come i d4 reali: il risultato si legge in alto su tutte le facce).
      face.forEach((vi, j) => {
        const corner = verts2D[j]
        const center2D = {
          x: cheby.x + (corner.x - cheby.x) * 0.5,
          y: cheby.y + (corner.y - cheby.y) * 0.5,
        }
        const up2D = norm2D({ x: corner.x - center2D.x, y: corner.y - center2D.y })
        pushFrame(t.vertexValues![vi], center2D, up2D, sizeFactor * cheby.r)
      })
      return
    }

    let up2D: Point2D
    if (kind === 'd10') {
      // Convenzione d10 reali: top della cifra verso l'apice del proprio polo.
      const poleIdx = face.indexOf(face.includes(0) ? 0 : 1)
      up2D = norm2D({ x: verts2D[poleIdx].x - cheby.x, y: verts2D[poleIdx].y - cheby.y })
    } else if (kind === 'd6' || kind === 'd8') {
      // d8: la proiezione di world-Y sul piano di ogni faccia È già un asse
      // di simmetria del triangolo (verso l'apice +Y sulle facce alte, via
      // dall'apice −Y su quelle basse) = convenzione dei d8 reali. Lo snap
      // generico qui degenera: i due vertici equatoriali pareggiano
      // (c.y = 0.5) e la cifra finisce ruotata di ±60° a seconda
      // dell'ordine dei vertici.
      up2D = { x: 0, y: 1 }
    } else {
      // Snap della proiezione di world-Y (= (0,1) in questo frame) alla
      // direzione centro→vertice più vicina: cifra allineata alla geometria
      // della faccia invece che ruotata di un angolo arbitrario.
      let best: Point2D = { x: 0, y: 1 }
      let bestDot = -Infinity
      for (const v of verts2D) {
        const c = norm2D({ x: v.x - cheby.x, y: v.y - cheby.y })
        if (c.y > bestDot) { bestDot = c.y; best = c }
      }
      up2D = best
    }
    pushFrame(t.faceValues[faceIdx], { x: cheby.x, y: cheby.y }, up2D, sizeFactor * cheby.r)
  })
  return frames
}

function applyWinding(verts: V[], faces: number[][]): number[][] {
  return faces.map((f) => ensureOutward(verts, f))
}

/** d4 — tetrahedron; numerazione apex: valori sui VERTICI (1-4) */
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
    vertexValues: [1, 2, 3, 4],
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

/** d8 — octahedron, 8 faces, opposite faces sum to 9 */
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
    // Coppie antipodali (0,6),(1,7),(2,4),(3,5) → somma 9 come i d8 reali,
    // con valori alti/bassi mescolati tra le due piramidi.
    faceValues: [1, 7, 4, 6, 5, 3, 8, 2],
  }
}

/** d10 — pentagonal trapezohedron (kite planari), opposite faces sum to 11 */
function d10Template(): DieTemplate {
  const verts: V[] = []
  verts.push([0, 1, 0])        // 0: top apex
  verts.push([0, -1, 0])       // 1: bottom apex
  for (let i = 0; i < 5; i++) {
    const a = (i / 5) * Math.PI * 2
    verts.push([Math.cos(a), D10_RING_Y, Math.sin(a)])
  }
  for (let i = 0; i < 5; i++) {
    const a = ((i + 0.5) / 5) * Math.PI * 2
    verts.push([Math.cos(a), -D10_RING_Y, Math.sin(a)])
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
    // Dispari intorno al polo superiore (alternati come i d10 reali), pari
    // all'inferiore; la faccia top i è antipodale alla bottom (i+2)%5 →
    // ogni coppia somma 11.
    faceValues: [1, 7, 3, 9, 5, 2, 6, 10, 4, 8],
  }
}

/** d12 — dodecahedron, 12 pentagonal faces, opposite faces sum to 13 */
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
    // Coppie antipodali (0,9),(1,10),(2,5),(3,11),(4,7),(6,8) → somma 13,
    // con valori alti/bassi mescolati tra facce vicine.
    faceValues: [1, 8, 3, 6, 11, 10, 4, 2, 9, 12, 5, 7],
  }
}

/** d20 — icosahedron, 20 triangular faces, opposite faces sum to 21 */
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
    // Le facce i e i+5 sono antipodali (per i∈0..4 e i∈10..14) → somma 21;
    // valori alternati alti/bassi su calotte ed equatore (niente cluster
    // 20-19-18 in stile spindown).
    faceValues: [1, 13, 9, 5, 17, 20, 8, 12, 16, 4, 6, 14, 10, 19, 3, 15, 7, 11, 2, 18],
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
  /** Orientazione che allinea una PlaneGeometry (+Z normal, +Y up) al numerale. */
  quaternion: THREE.Quaternion
  /** Centro del quad in spazio locale del dado, sollevato dalla faccia. */
  offsetPosition: THREE.Vector3
  /** Lato del quad (quadrato) del numerale. */
  size: number
}

export interface DiceGeometryData {
  geometry: THREE.BufferGeometry
  shape: CANNON.ConvexPolyhedron
  /** Direzioni di lettura keyed by valore (normali di faccia; vertici per il d4). */
  faceNormals: Record<number, THREE.Vector3>
  /** Frame dei quad numerali (3 per faccia sul d4, 1 altrove). */
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
  const uvKind = key as DiceUvKind
  const data: DiceGeometryData = {
    geometry: buildBufferGeometry(template),
    shape: buildCannonShape(template),
    faceNormals: buildFaceNormals(template),
    faceFrames: buildFaceFrames(template, uvKind),
    faceCount: template.faces.length,
    faceValues: [...template.faceValues],
  }

  // UV atlas per-faccia (d100 riusa la geometria d10 → cache key 'd10').
  const layout = UV_LAYOUTS[uvKind]
  const trisPerFace = TRIS_PER_FACE[uvKind]
  const positionAttr = data.geometry.getAttribute('position') as THREE.BufferAttribute
  const uvArray = new Float32Array(positionAttr.count * 2)

  let triCursor = 0
  template.faces.forEach((face, faceIdx) => {
    const { centroid, xAxis, yAxis, verts2D } = buildFaceBasis(template, face)
    const cell = cellForIndex(uvKind, faceIdx)
    let halfW = 0
    let halfH = 0
    for (const v of verts2D) {
      if (Math.abs(v.x) > halfW) halfW = Math.abs(v.x)
      if (Math.abs(v.y) > halfH) halfH = Math.abs(v.y)
    }
    for (let v = 0; v < trisPerFace * 3; v++) {
      const idx = triCursor + v
      const pos = new THREE.Vector3(
        positionAttr.getX(idx),
        positionAttr.getY(idx),
        positionAttr.getZ(idx),
      )
      const rel = pos.sub(centroid)
      const uvs = projectFaceUvs(
        [{ x: rel.dot(xAxis), y: rel.dot(yAxis) }],
        cell,
        layout,
        halfW,
        halfH,
      )
      uvArray[idx * 2] = uvs[0]
      uvArray[idx * 2 + 1] = uvs[1]
    }
    triCursor += trisPerFace * 3
  })

  data.geometry.setAttribute('uv', new THREE.BufferAttribute(uvArray, 2))

  cache.set(key, data)
  return data
}

export function disposeDiceGeometries(): void {
  for (const { geometry } of cache.values()) {
    geometry.dispose()
  }
  cache.clear()
}

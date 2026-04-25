// webapp/src/dice/geometries/uvLayouts.ts
export type DiceUvKind = 'd4' | 'd6' | 'd8' | 'd10' | 'd12' | 'd20'

export interface UvCellLayout {
  cols: number
  rows: number
}

export const UV_LAYOUTS: Record<DiceUvKind, UvCellLayout> = {
  d4: { cols: 2, rows: 2 },
  d6: { cols: 3, rows: 2 },
  d8: { cols: 4, rows: 2 },
  d10: { cols: 5, rows: 2 },
  d12: { cols: 4, rows: 3 },
  d20: { cols: 5, rows: 4 },
}

/**
 * Mapping deterministico face index → cella nell'atlas.
 * Index 0 = top-left, scorre per righe.
 */
export function cellForIndex(kind: DiceUvKind, index: number): { row: number; col: number } {
  const { cols } = UV_LAYOUTS[kind]
  return { row: Math.floor(index / cols), col: index % cols }
}

export interface FaceUv {
  value: number
  uvs: number[]
}

/**
 * Genera coordinate UV per i vertici 2D di una faccia, mappandoli nella cella della griglia.
 * faceVerts2D: vertici della faccia in spazio 2D locale (basis = faceUp / faceNormal × faceUp).
 */
export function projectFaceUvs(
  faceVerts2D: Array<{ x: number; y: number }>,
  cell: { row: number; col: number },
  layout: UvCellLayout,
  faceHalfWidth: number,
  faceHalfHeight: number,
): number[] {
  const cellW = 1 / layout.cols
  const cellH = 1 / layout.rows
  const cellCenterU = cell.col * cellW + cellW / 2
  // y-flip: row 0 in atlas = top
  const cellCenterV = 1 - (cell.row * cellH + cellH / 2)

  const uvs: number[] = []
  for (const v of faceVerts2D) {
    const u = cellCenterU + (v.x / faceHalfWidth) * (cellW * 0.5 * 0.95)
    const vv = cellCenterV + (v.y / faceHalfHeight) * (cellH * 0.5 * 0.95)
    uvs.push(u, vv)
  }
  return uvs
}

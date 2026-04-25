// webapp/scripts/generate-uv-templates.mjs
// Genera template UV PNG per ComfyUI (uno per kind).
// Usa node-canvas (zero deps three.js / cannon — solo grafica 2D).
// Run: node webapp/scripts/generate-uv-templates.mjs

import { createCanvas } from 'canvas'
import { writeFileSync, mkdirSync } from 'fs'
import { dirname } from 'path'

const SIZE = 1024
const OUT_DIR = 'webapp/public/dice-packs/_templates'

const LAYOUTS = {
  d4:  { cols: 2, rows: 2, faces: 4 },
  d6:  { cols: 3, rows: 2, faces: 6 },
  d8:  { cols: 4, rows: 2, faces: 8 },
  d10: { cols: 5, rows: 2, faces: 10 },
  d12: { cols: 4, rows: 3, faces: 12 },
  d20: { cols: 5, rows: 4, faces: 20 },
}

function generateOne(kind) {
  const { cols, rows, faces } = LAYOUTS[kind]
  const canvas = createCanvas(SIZE, SIZE)
  const ctx = canvas.getContext('2d')
  // sfondo grigio scuro (zone fuori cella che non saranno mappate)
  ctx.fillStyle = '#1a1a1a'
  ctx.fillRect(0, 0, SIZE, SIZE)

  const cellW = SIZE / cols
  const cellH = SIZE / rows

  for (let i = 0; i < faces; i++) {
    const col = i % cols
    const row = Math.floor(i / cols)
    const x0 = col * cellW
    const y0 = row * cellH

    // sfondo cella (variante alternata per vedere il bordo)
    ctx.fillStyle = i % 2 === 0 ? '#888888' : '#aaaaaa'
    ctx.fillRect(x0, y0, cellW, cellH)
    // bordo cella
    ctx.strokeStyle = '#000000'
    ctx.lineWidth = 6
    ctx.strokeRect(x0, y0, cellW, cellH)
    // numero faccia
    ctx.fillStyle = '#ff0000'
    ctx.font = `bold ${Math.floor(Math.min(cellW, cellH) * 0.6)}px sans-serif`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(String(i + 1), x0 + cellW / 2, y0 + cellH / 2)
  }

  const outPath = `${OUT_DIR}/${kind}.uv.png`
  mkdirSync(dirname(outPath), { recursive: true })
  writeFileSync(outPath, canvas.toBuffer('image/png'))
  console.log(`generated ${outPath}`)
}

for (const kind of Object.keys(LAYOUTS)) generateOne(kind)

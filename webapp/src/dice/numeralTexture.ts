import * as THREE from 'three'
import type { DiceTint } from './types'

const cache = new Map<string, THREE.CanvasTexture>()

const SIZE = 384

function inkColorFor(tint: DiceTint): string {
  switch (tint) {
    case 'crit':
      return '#3a2400'
    case 'fumble':
      return '#f8e0d6'
    case 'arcane':
      return '#f0eaff'
    case 'ember':
      return '#2a1400'
    case 'normal':
    default:
      return '#2a1d10'
  }
}

function drawLabel(ctx: CanvasRenderingContext2D, label: string, ink: string) {
  ctx.clearRect(0, 0, SIZE, SIZE)

  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'

  const length = label.length
  const px = length >= 3 ? 155 : length === 2 ? 215 : 275
  ctx.font = `900 ${px}px "Cinzel", "Georgia", serif`

  const cx = SIZE / 2
  const cy = SIZE / 2 + px * 0.03

  ctx.lineJoin = 'round'
  ctx.miterLimit = 2
  ctx.strokeStyle = 'rgba(0,0,0,0.65)'
  ctx.lineWidth = Math.max(6, px * 0.06)
  ctx.strokeText(label, cx, cy)

  ctx.fillStyle = ink
  ctx.fillText(label, cx, cy)

  if (label === '6' || label === '9' || label === '66' || label === '99') {
    const dotSize = Math.round(px * 0.42)
    ctx.font = `900 ${dotSize}px "Cinzel", "Georgia", serif`
    const dotY = cy + px * 0.55
    ctx.lineWidth = Math.max(4, dotSize * 0.1)
    ctx.strokeText('_', cx, dotY)
    ctx.fillText('_', cx, dotY)
  }
}

export function getNumeralTexture(label: string, tint: DiceTint = 'normal'): THREE.CanvasTexture {
  const key = `${tint}:${label}`
  const cached = cache.get(key)
  if (cached) return cached

  const canvas = document.createElement('canvas')
  canvas.width = SIZE
  canvas.height = SIZE
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('2d context unavailable')
  drawLabel(ctx, label, inkColorFor(tint))

  const tex = new THREE.CanvasTexture(canvas)
  tex.anisotropy = 4
  tex.colorSpace = THREE.SRGBColorSpace
  tex.needsUpdate = true

  if (typeof document !== 'undefined' && document.fonts?.ready) {
    document.fonts.ready
      .then(() => {
        drawLabel(ctx, label, inkColorFor(tint))
        tex.needsUpdate = true
      })
      .catch(() => {})
  }

  cache.set(key, tex)
  return tex
}

export function disposeNumeralTextures(): void {
  for (const tex of cache.values()) tex.dispose()
  cache.clear()
}

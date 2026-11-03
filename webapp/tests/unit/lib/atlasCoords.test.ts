import { describe, expect, it } from 'vitest'
import { centerToImage, imageToCenter } from '@/lib/atlasCoords'

const vp = { width: 400, height: 800 }
const img = { width: 800, height: 1600 }

describe('atlasCoords', () => {
  it('maps the viewport centre to image fractions', () => {
    expect(centerToImage({ positionX: 0, positionY: 0, scale: 1 }, vp, img)).toEqual({ x: 0.25, y: 0.25 })
    expect(centerToImage({ positionX: -400, positionY: -800, scale: 2 }, vp, img)).toEqual({ x: 0.375, y: 0.375 })
  })
  it('returns null when the centre is off the image', () => {
    expect(centerToImage({ positionX: 300, positionY: 0, scale: 1 }, vp, img)).toBeNull()
  })
  it('round-trips', () => {
    const t = { ...imageToCenter({ x: 0.7, y: 0.2 }, vp, img, 3), scale: 3 }
    const p = centerToImage(t, vp, img)!
    expect(p.x).toBeCloseTo(0.7)
    expect(p.y).toBeCloseTo(0.2)
  })
})

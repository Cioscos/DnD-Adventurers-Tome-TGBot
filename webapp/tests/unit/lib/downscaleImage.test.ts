import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { downscaleImage } from '@/lib/downscaleImage'

const MB = 1024 * 1024
const fileOf = (size: number) => new File([new Uint8Array(size)], 'map.png', { type: 'image/png' })

beforeEach(() => {
  vi.stubGlobal('createImageBitmap', vi.fn(async () => ({ width: 4096, height: 4096, close: () => {} })))
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({ drawImage: () => {} } as never)
  vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(function (cb) {
    cb(new Blob(['x'], { type: 'image/webp' }))
  })
})
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('downscaleImage', () => {
  it('keeps a small file within the side limit as is', async () => {
    const f = fileOf(1 * MB)
    expect(await downscaleImage(f)).toBe(f)
  })

  it('re-encodes a file over 10 MB even when no resize is needed', async () => {
    const out = await downscaleImage(fileOf(11 * MB))
    expect(out.type).toBe('image/webp')
    expect(out.name).toBe('map.webp')
    expect(out.size).toBeLessThan(10 * MB)
  })
})

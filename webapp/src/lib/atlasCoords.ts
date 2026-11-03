interface Transform { positionX: number; positionY: number; scale: number }
interface Size { width: number; height: number }

/** Image fraction (0..1) under the viewport centre, or null when the centre is off the image. */
export function centerToImage(t: Transform, viewport: Size, image: Size): { x: number; y: number } | null {
  const x = (viewport.width / 2 - t.positionX) / t.scale / image.width
  const y = (viewport.height / 2 - t.positionY) / t.scale / image.height
  return x < 0 || x > 1 || y < 0 || y > 1 ? null : { x, y }
}

/** Inverse of centerToImage: the pan that puts image point p at the viewport centre. */
export function imageToCenter(p: { x: number; y: number }, viewport: Size, image: Size, scale: number) {
  return {
    positionX: viewport.width / 2 - p.x * image.width * scale,
    positionY: viewport.height / 2 - p.y * image.height * scale,
  }
}

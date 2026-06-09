import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useOverlayStore, useRegisterOverlay } from '@/store/overlayStore'

beforeEach(() => useOverlayStore.setState({ count: 0 }))

describe('overlayStore', () => {
  it('acquire increments and release decrements, clamped at 0', () => {
    const { acquire, release } = useOverlayStore.getState()
    acquire()
    acquire()
    expect(useOverlayStore.getState().count).toBe(2)
    release()
    expect(useOverlayStore.getState().count).toBe(1)
    release()
    release() // extra release must not go negative
    expect(useOverlayStore.getState().count).toBe(0)
  })

  it('useRegisterOverlay registers while open and releases on unmount', () => {
    const { unmount } = renderHook(() => useRegisterOverlay(true))
    expect(useOverlayStore.getState().count).toBe(1)
    unmount()
    expect(useOverlayStore.getState().count).toBe(0)
  })

  it('useRegisterOverlay(false) does not register an overlay', () => {
    renderHook(() => useRegisterOverlay(false))
    expect(useOverlayStore.getState().count).toBe(0)
  })
})

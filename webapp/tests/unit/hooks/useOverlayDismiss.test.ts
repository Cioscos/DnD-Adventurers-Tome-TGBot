import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'

// BackButton nativa di Telegram: il back hardware Android in fullscreen non
// produce popstate, quindi overlay e pagine devono passare dalla BackButton.
const bb = {
  isVisible: false,
  show: vi.fn(() => { bb.isVisible = true }),
  hide: vi.fn(() => { bb.isVisible = false }),
  onClick: vi.fn(),
  offClick: vi.fn(),
}

let hook: typeof import('@/hooks/useOverlayDismiss')

beforeAll(async () => {
  ;(window as unknown as { Telegram: unknown }).Telegram = { WebApp: { BackButton: bb } }
  hook = await import('@/hooks/useOverlayDismiss')
})

beforeEach(() => {
  bb.isVisible = false
})

const pressBack = () => {
  const handler = bb.onClick.mock.calls[0][0] as () => void
  act(() => handler())
}

describe('BackButton Telegram', () => {
  it('visibile con una pagina che ha un genitore, chiama il suo back', () => {
    const onBack = vi.fn()
    const { unmount } = renderHook(() => hook.usePageBack(onBack))
    expect(bb.isVisible).toBe(true)
    pressBack()
    expect(onBack).toHaveBeenCalledTimes(1)
    unmount()
    expect(bb.isVisible).toBe(false)
  })

  it("un overlay aperto ha la precedenza sul back di pagina", () => {
    const onBack = vi.fn()
    const onClose = vi.fn()
    const page = renderHook(() => hook.usePageBack(onBack))
    const overlay = renderHook(() => hook.useOverlayDismiss(true, onClose))
    pressBack()
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(onBack).not.toHaveBeenCalled()
    overlay.unmount()
    expect(bb.isVisible).toBe(true)
    pressBack()
    expect(onBack).toHaveBeenCalledTimes(1)
    page.unmount()
  })

  it('un overlay non dismissible blocca il back', () => {
    const onBack = vi.fn()
    const onClose = vi.fn()
    const page = renderHook(() => hook.usePageBack(onBack))
    const overlay = renderHook(() => hook.useOverlayDismiss(true, onClose, false))
    pressBack()
    expect(onClose).not.toHaveBeenCalled()
    expect(onBack).not.toHaveBeenCalled()
    overlay.unmount()
    page.unmount()
  })

  it('nascosta senza overlay né back di pagina (es. lista personaggi)', () => {
    const { unmount } = renderHook(() => hook.usePageBack(null))
    expect(bb.isVisible).toBe(false)
    unmount()
  })
})

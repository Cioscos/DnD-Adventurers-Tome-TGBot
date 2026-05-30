import { useEffect } from 'react'
import { create } from 'zustand'

/**
 * Tracks how many modal/sheet/dialog overlays are currently mounted-open.
 * Overlays sit at z-50+ and cover the viewport; the floating dice launcher
 * (DiceOverlay) must hide while any of them is open so it never floats above a
 * backdrop and steals taps from modal buttons (e.g. "Conferma"). See finding
 * #3 in the FE audit.
 */
interface OverlayStore {
  count: number
  acquire: () => void
  release: () => void
}

export const useOverlayStore = create<OverlayStore>((set) => ({
  count: 0,
  acquire: () => set((s) => ({ count: s.count + 1 })),
  release: () => set((s) => ({ count: Math.max(0, s.count - 1) })),
}))

/** True while at least one overlay is open. */
export const useAnyOverlayOpen = () => useOverlayStore((s) => s.count > 0)

/**
 * Register an overlay as open for the lifetime the `open` flag is truthy.
 * Call from each overlay primitive (Sheet, ResultDialog, ModalProvider).
 */
export function useRegisterOverlay(open: boolean): void {
  useEffect(() => {
    if (!open) return
    const { acquire, release } = useOverlayStore.getState()
    acquire()
    return release
  }, [open])
}

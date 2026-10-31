import { describe, it, expect, vi } from 'vitest'
import type { ReactNode } from 'react'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useTurnState } from '@/hooks/useTurnState'

const { turnState } = vi.hoisted(() => ({ turnState: vi.fn() }))
vi.mock('@/api/client', () => ({ api: { characters: { turnState } } }))

describe('useTurnState', () => {
  it('invalidates the character when the turn or round changes', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const spy = vi.spyOn(qc, 'invalidateQueries')
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    )
    turnState.mockResolvedValue({ in_encounter: true, is_my_turn: false, round: 1, session_id: 1 })
    const { result } = renderHook(() => useTurnState(7, true), { wrapper })
    await waitFor(() => expect(result.current.data).toBeTruthy())
    expect(spy).not.toHaveBeenCalled()

    turnState.mockResolvedValue({ in_encounter: true, is_my_turn: true, round: 1, session_id: 1 })
    await qc.refetchQueries({ queryKey: ['turn-state', 7] })
    await waitFor(() => expect(spy).toHaveBeenCalledWith({ queryKey: ['character', 7] }))
  })
})

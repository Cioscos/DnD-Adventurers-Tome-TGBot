import { describe, it, expect, vi } from 'vitest'
import type { ReactNode } from 'react'
import { renderHook, waitFor, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useTurnState } from '@/hooks/useTurnState'
import { renderWithProviders } from '../utils/renderWithProviders'
import SongOfRestToggle from '@/components/character/SongOfRestToggle'
import type { CharacterFull } from '@/types'

const { turnState, featureUse, endActiveState } = vi.hoisted(() => ({ turnState: vi.fn(), featureUse: vi.fn(), endActiveState: vi.fn() }))
vi.mock('@/api/client', () => ({
  api: { characters: { turnState, featureUse, endActiveState } },
  ApiError: class ApiError extends Error {},
}))

const wrap = (qc: QueryClient) => ({ children }: { children: ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>

describe('useTurnState polling (punto 37)', () => {
  it('reads once but does not poll outside an active evening, and polls every 5 s inside one', async () => {
    turnState.mockResolvedValue({ in_encounter: false, is_my_turn: false, round: null, session_id: null })
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { result } = renderHook(() => useTurnState(7, true, false), { wrapper: wrap(qc) })
    await waitFor(() => expect(result.current.data).toBeTruthy())
    expect(qc.getQueryCache().find({ queryKey: ['turn-state', 7] })?.observers[0].options.refetchInterval).toBe(false)

    const live = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { result: r2 } = renderHook(() => useTurnState(7, true, true), { wrapper: wrap(live) })
    await waitFor(() => expect(r2.current.data).toBeTruthy())
    expect(live.getQueryCache().find({ queryKey: ['turn-state', 7] })?.observers[0].options.refetchInterval).toBe(5000)
  })
})

describe('turn-state invalidation after mutations (punto 38)', () => {
  it('Song of Rest refreshes the character and the turn', async () => {
    featureUse.mockResolvedValue({})
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const spy = vi.spyOn(qc, 'invalidateQueries')
    const char = { id: 7, rules_edition: '2014', active_states: [], abilities: [{ feature_key: 'bard.song_of_rest', has_on_use: true }] } as unknown as CharacterFull
    renderWithProviders(<SongOfRestToggle char={char} />, { client: qc })
    await userEvent.click(screen.getByRole('switch'))
    await waitFor(() => expect(spy).toHaveBeenCalledWith({ queryKey: ['turn-state', 7] }))
    expect(spy).toHaveBeenCalledWith({ queryKey: ['character', 7] })
  })
})

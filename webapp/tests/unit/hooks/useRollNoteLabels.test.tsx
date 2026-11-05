import { describe, it, expect, vi } from 'vitest'
import type { ReactNode } from 'react'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useRollNoteLabels } from '@/hooks/useRollNoteLabels'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return {
    ...actual,
    useTranslation: () => ({
      t: (k: string, o?: { context?: string }) => (o?.context ? `${k}:${o.context}` : k),
      i18n: { language: 'it' },
    }),
  }
})
const { getSpy } = vi.hoisted(() => ({ getSpy: vi.fn() }))
vi.mock('@/api/client', () => ({ api: { characters: { get: getSpy } } }))
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useParams: () => ({ id: '7' }) }
})

function labels(notes: string[], charId?: number) {
  const qc = new QueryClient()
  qc.setQueryData(['character', 7], { rules_edition: '2024', abilities: [{ feature_key: 'monk.ki', name: 'Ki' }] })
  qc.setQueryData(['character', 9], { rules_edition: '2014', abilities: [] })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
  return renderHook(() => useRollNoteLabels(charId), { wrapper }).result.current(notes)
}

describe('useRollNoteLabels', () => {
  it('names exhaustion after the edition of the character on the page', () => {
    expect(labels(['condition:exhaustion'])).toEqual(['character.conditions.exhaustion_condition:2024'])
  })

  it('an explicit character wins over the page (session views have no id in the route)', () => {
    expect(labels(['condition:exhaustion'], 9)).toEqual(['character.conditions.exhaustion_condition:2014'])
  })

  it('translates the other kinds of note', () => {
    expect(labels(['condition:poisoned', 'armor:untrained', 'feature:monk.ki'])).toEqual([
      'character.conditions.poisoned', 'character.roll_notes.armor_untrained', 'Ki',
    ])
  })

  it('names a feature of a character that is not in the cache yet (session pages never load it)', async () => {
    getSpy.mockResolvedValue({ rules_edition: '2014', abilities: [{ feature_key: 'monk.perfect_self', name: 'Perfezione Interiore' }] })
    const qc = new QueryClient()
    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    const { result } = renderHook(() => useRollNoteLabels(11), { wrapper })
    await waitFor(() => expect(result.current(['feature:monk.perfect_self'])).toEqual(['Perfezione Interiore']))
    expect(getSpy).toHaveBeenCalledWith(11)
  })
})

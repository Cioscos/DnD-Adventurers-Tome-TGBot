import { describe, it, expect, vi } from 'vitest'
import type { ReactNode } from 'react'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useTradePartners } from '@/hooks/useTradePartners'

const { me } = vi.hoisted(() => ({ me: vi.fn() }))
vi.mock('@/api/client', () => ({ api: { sessions: { me } } }))

const P = (user_id: number, character_id: number | null, role = 'player') =>
  ({ user_id, role, character_id, display_name: `U${user_id}`, joined_at: '' })
const sess = (over = {}) => ({ id: 9, status: 'active', participants: [P(1, 10), P(2, 20), P(3, null), P(4, 40, 'gm')], ...over })

async function run(data: unknown, charId = 10) {
  me.mockResolvedValue(data)
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  const r = renderHook(() => useTradePartners(charId), { wrapper })
  await waitFor(() => expect(me).toHaveBeenCalled())
  await new Promise((res) => setTimeout(res, 20))
  return r.result.current
}

describe('useTradePartners', () => {
  it('null senza sessione', async () => expect(await run(null)).toBeNull())
  it('null con sessione chiusa', async () => expect(await run(sess({ status: 'closed' }))).toBeNull())
  it('null se il PG non partecipa', async () => expect(await run(sess(), 99)).toBeNull())
  it('null senza compagni con PG', async () =>
    expect(await run(sess({ participants: [P(1, 10), P(3, null), P(4, 40, 'gm')] }))).toBeNull())
  it('in campagna senza altri compagni resta non null (il deposito è un destinatario)', async () => {
    const r = await run(sess({ campaign_id: 3, participants: [P(1, 10), P(4, 40, 'gm')] }))
    expect(r).toMatchObject({ sessionId: 9, partners: [], stash: true })
  })
  it('ritorna solo gli altri giocatori con PG', async () => {
    const r = await run(sess())
    expect(r?.sessionId).toBe(9)
    expect(r?.partners.map((p) => p.user_id)).toEqual([2])
  })
})

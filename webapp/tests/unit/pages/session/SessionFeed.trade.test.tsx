import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import SessionFeed from '@/pages/session/SessionFeed'
import itLocale from '@/locales/it.json'
import type { SessionFeedItem, TradePayload } from '@/types'

const { getFeed, enqueueSpy, loreList } = vi.hoisted(() => ({ getFeed: vi.fn(), enqueueSpy: vi.fn(), loreList: vi.fn() }))

vi.mock('@/api/client', () => ({
  api: { sessions: { getFeed, sendMessage: vi.fn() }, lore: { list: loreList, imageUrl: () => '', audioUrl: () => '' } },
  ApiError: class ApiError extends Error {},
}))
vi.mock('@/lib/rewardQueue', () => ({ enqueue: enqueueSpy }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('sonner', () => ({ toast: { error: vi.fn(), warning: vi.fn() } }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  const t = (k: string, o?: Record<string, string>) => {
    const raw = k.split('.').reduce<unknown>((a, p) => (a as Record<string, unknown> | undefined)?.[p], itLocale) as string | undefined
    return (raw ?? k).replace(/\{\{(\w+)\}\}/g, (_, n) => String(o?.[n] ?? ''))
  }
  return { ...actual, useTranslation: () => ({ t, i18n: { language: 'it' } }) }
})

const feedItem = (trade: TradePayload): SessionFeedItem => ({
  type: 'message', message_id: 1, user_id: 1, role: 'player', display_name: 'Thorin',
  body: 'x', recipient_user_id: null, item_id: null, item_name: null, item_quantity: null,
  timestamp: '2026-01-01T10:00:00Z', trade,
}) as SessionFeedItem

const base = { from: { character_id: 1, name: 'Thorin' }, to: { character_id: 2, name: 'Lyra' } }

function setup(trade: TradePayload) {
  getFeed.mockResolvedValue({ items: [feedItem(trade)], has_more: false })
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <SessionFeed code="ABC" sessionId={1} gmUserId={9} myUserId={2} myCharId={2}
          participants={[]} whisperTarget={null} onClearWhisperTarget={() => {}} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('SessionFeed trade row', () => {
  beforeEach(() => { Element.prototype.scrollTo = vi.fn(); getFeed.mockReset(); enqueueSpy.mockReset() })

  it('espande uno zaino con figli e monete, senza ricompensa né icona regalo', async () => {
    setup({
      ...base, coins: {},
      items: [{ name: 'Zaino', quantity: 1, coins: { gold: 35 }, children: [{ name: 'Corda', quantity: 1, coins: null, children: [] }] }],
    })
    const row = await screen.findByRole('button', { name: /Thorin ha dato a Lyra: Zaino/ })
    expect(screen.queryByText('Corda')).toBeNull()
    await userEvent.click(row)
    expect(screen.getByText('Corda')).toBeTruthy()
    expect(screen.getByText(/35 GP/)).toBeTruthy()
    expect(enqueueSpy).not.toHaveBeenCalled()
    expect(document.querySelector('.lucide-gift')).toBeNull()
  })

  it('oggetto semplice non è espandibile', async () => {
    setup({ ...base, coins: {}, items: [{ name: 'Spada', quantity: 2, coins: null, children: [] }] })
    await screen.findByText(/Thorin ha dato a Lyra: Spada ×2/)
    expect(screen.queryByRole('button', { name: /Spada/ })).toBeNull()
  })

  it('solo monete mostra gli importi', async () => {
    setup({ ...base, items: [], coins: { gold: 1200, silver: 5 } })
    await waitFor(() => expect(screen.getByText(/Thorin ha dato a Lyra: 1200 GP · 5 SP/)).toBeTruthy())
  })

  const stashSide = { character_id: null, name: 'stash' }
  const gmSide = { character_id: null, name: 'gm' }
  const rows: [string, Partial<TradePayload>, RegExp][] = [
    ['stash_put', { from: base.from, to: stashSide }, /Thorin ha messo nel deposito: Spada/],
    ['stash_take', { from: stashSide, to: base.to }, /Lyra ha preso dal deposito: Spada/],
    ['gm_stash_add', { from: gmSide, to: stashSide }, /Il master ha messo nel deposito: Spada/],
    ['gm_stash_remove', { from: stashSide, to: gmSide }, /Il master ha tolto dal deposito: Spada/],
  ]
  it.each(rows)('riga %s con la copia fissata', async (kind, sides, re) => {
    setup({ ...base, ...sides, kind, coins: {}, items: [{ name: 'Spada', quantity: 1, coins: null, children: [] }] } as TradePayload)
    await waitFor(() => expect(screen.getByText(re)).toBeTruthy())
  })

  it('riga di deposito espandibile come uno scambio', async () => {
    setup({
      ...base, to: stashSide, kind: 'stash_put', coins: {},
      items: [{ name: 'Zaino', quantity: 1, coins: null, children: [{ name: 'Corda', quantity: 1, coins: null, children: [] }] }],
    } as TradePayload)
    await userEvent.click(await screen.findByRole('button', { name: /Thorin ha messo nel deposito: Zaino/ }))
    expect(screen.getByText('Corda')).toBeTruthy()
  })
})

describe('SessionFeed lore_reveal row', () => {
  beforeEach(() => { Element.prototype.scrollTo = vi.fn(); getFeed.mockReset() })
  const loreRow = {
    type: 'message', message_id: 5, user_id: 9, role: 'game_master', display_name: 'GM',
    body: 'testo italiano del server', timestamp: '2026-01-01T10:00:00Z',
    trade: { kind: 'lore_reveal', lore_id: 3, title: 'La torre' },
  } as unknown as SessionFeedItem
  const mount = () => render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <SessionFeed code="ABC" sessionId={1} campaignId={7} gmUserId={9} myUserId={2} myCharId={2}
          participants={[]} whisperTarget={null} onClearWhisperTarget={() => {}} />
      </MemoryRouter>
    </QueryClientProvider>,
  )

  it('mostra il testo da i18n e al tocco apre la voce', async () => {
    getFeed.mockResolvedValue({ items: [loreRow], has_more: false })
    loreList.mockResolvedValue([{ id: 3, title: 'La torre', body: 'Corpo della voce', tags: [], has_image: false, has_audio: false, revealed: true }])
    mount()
    const row = await screen.findByRole('button', { name: /Il master ha rivelato: La torre/ })
    expect(screen.queryByText(/testo italiano/)).toBeNull()
    await userEvent.click(row)
    await waitFor(() => expect(screen.getByText('Corpo della voce')).toBeTruthy())
  })

  it('voce non più disponibile', async () => {
    getFeed.mockResolvedValue({ items: [loreRow], has_more: false })
    loreList.mockResolvedValue([])
    mount()
    await userEvent.click(await screen.findByRole('button', { name: /Il master ha rivelato/ }))
    await waitFor(() => expect(screen.getByText(itLocale.campaign.lore.unavailable)).toBeTruthy())
  })
})

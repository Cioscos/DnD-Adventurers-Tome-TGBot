import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '../utils/renderWithProviders'
import DiceStats from '@/pages/DiceStats'
import { formatRelative } from '@/lib/relativeTime'

const { stats } = vi.hoisted(() => ({ stats: vi.fn() }))

vi.mock('@/api/client', () => ({ api: { dice: { stats, resetStats: vi.fn() } } }))
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useParams: () => ({ id: '7' }) }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/components/Layout', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/ui/ConfirmSheet', () => ({ default: () => null }))

const tzOriginale = process.env.TZ
afterEach(() => {
  stats.mockReset()
  if (tzOriginale === undefined) delete process.env.TZ
  else process.env.TZ = tzOriginale
})

describe('caccia: dadi', () => {
  // caccia: {"id": "CB-755", "fonte": "invariante: il numero dei tiri conta solo dadi, non il totale di una prova", "zona": "flusso:dadi", "voce": "normale", "copre": ["route:/char/:id/dice/stats"]}
  it('le statistiche contano i dadi e calcolano la media di faccia', async () => {
    stats.mockResolvedValue({ stats: { d6: { '2': 1, '6': 3 }, d20: { '1': 2, '20': 1 }, d20_total: { '57': 1 } } })
    renderWithProviders(<DiceStats />)
    expect(await screen.findByText('5.0')).toBeInTheDocument()
    expect(screen.getByText('7')).toBeInTheDocument()
  })

  // caccia: {"id": "CB-756", "fonte": "invariante: un orario UTC dell'API si mostra nell'ora locale di chi guarda", "zona": "flusso:dadi", "voce": "normale", "copre": ["route:/char/:id/history", "route:/char/:id/dice"]}
  it.fails("l'orario di un evento scritto dall'API in UTC si mostra nell'ora locale", () => {
    process.env.TZ = 'Europe/Rome' // fissa il fuso: Node lo rispetta a runtime su Windows e Linux, e lo ripristina afterEach
    expect(new Date(2026, 10, 24, 12).getTimezoneOffset()).toBe(-60)
    const ora = formatRelative('2026-11-24T09:00:00', {
      locale: 'it', todayLabel: 'Oggi', yesterdayLabel: 'Ieri', now: new Date('2026-11-24T09:30:00Z'),
    })
    expect(ora).toBe('Oggi 10:00')
  })
})

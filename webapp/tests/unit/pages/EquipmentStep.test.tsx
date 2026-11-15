import { describe, it, expect, vi } from 'vitest'
import { useState } from 'react'
import { render, renderHook, act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import EquipmentStep from '@/pages/creation/EquipmentStep'
import { useEquipPicks } from '@/pages/creation/useEquipPicks'

const { startingEquipment } = vi.hoisted(() => ({ startingEquipment: vi.fn() }))

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/api/client', () => ({ api: { rules: { startingEquipment } } }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/components/ui/Pressable', async () => {
  const React = await import('react')
  return {
    default: (p: { onClick?: () => void; className?: string; children?: unknown }) =>
      React.createElement('button', { onClick: p.onClick, className: p.className }, p.children),
  }
})

function Harness({ onPicks, onWealth = () => {} }: { onPicks: (p: number[]) => void; onWealth?: (w: boolean) => void }) {
  const [picks, setPicks] = useState<number[] | null>(null)
  const [wealth, setWealth] = useState(false)
  return (
    <EquipmentStep edition="2014" className="Mago" picks={picks} onPicks={(p) => { setPicks(p); onPicks(p) }}
      wealth={wealth} onWealth={(w) => { setWealth(w); onWealth(w) }} />
  )
}

describe('EquipmentStep', () => {
  it('parte dalla prima alternativa, mostra i gruppi fissi e salva la scelta', async () => {
    startingEquipment.mockResolvedValue({ groups: [['Bastone ferrato', 'Pugnale'], ['Libro degli incantesimi']] })
    const seen = vi.fn()
    render(
      <QueryClientProvider client={new QueryClient()}>
        <Harness onPicks={seen} />
      </QueryClientProvider>,
    )
    await screen.findByText('Pugnale')
    await waitFor(() => expect(seen).toHaveBeenLastCalledWith([0, 0]))
    expect(screen.getByText('Libro degli incantesimi')).toBeTruthy()
    await userEvent.click(screen.getByText('Pugnale'))
    expect(seen).toHaveBeenLastCalledWith([1, 0])
  })

  it('classe senza equipaggiamento: messaggio e nessuna scelta', async () => {
    startingEquipment.mockResolvedValue({ groups: [] })
    const seen = vi.fn()
    render(
      <QueryClientProvider client={new QueryClient()}>
        <Harness onPicks={seen} />
      </QueryClientProvider>,
    )
    await screen.findByText('character.create.equipment_none')
    expect(seen).not.toHaveBeenCalled()
  })
})

describe('EquipmentStep wealth', () => {
  const wrap = (ui: React.ReactElement) => render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>)

  it('con la ricchezza disponibile mostra l\'interruttore; acceso, nasconde i gruppi', async () => {
    startingEquipment.mockResolvedValue({ groups: [['Bastone ferrato', 'Pugnale']], wealth: { dice: '4d4', multiplier: 10 } })
    const seen = vi.fn()
    wrap(<Harness onPicks={() => {}} onWealth={seen} />)
    const toggle = await screen.findByRole('button', { name: /character\.create\.equipment_wealth/ })
    await userEvent.click(toggle)
    expect(seen).toHaveBeenLastCalledWith(true)
    expect(screen.queryByText('Pugnale')).toBeNull()
    await userEvent.click(toggle)
    expect(seen).toHaveBeenLastCalledWith(false)
    expect(screen.getByText('Pugnale')).toBeTruthy()
  })

  it('senza ricchezza (2024) non c\'è l\'interruttore', async () => {
    startingEquipment.mockResolvedValue({ groups: [['Bastone ferrato', 'Pugnale']], wealth: null })
    wrap(<Harness onPicks={() => {}} />)
    await screen.findByText('Pugnale')
    expect(screen.queryByRole('button', { name: /equipment_wealth/ })).toBeNull()
  })
})

describe('useEquipPicks', () => {
  it('azzera le scelte quando cambia classe o edizione', () => {
    const { result, rerender } = renderHook(({ k }) => useEquipPicks(k), { initialProps: { k: '2014:Guerriero' } })
    act(() => result.current[1]([0, 1, 0, 1]))
    expect(result.current[0]).toEqual([0, 1, 0, 1])
    rerender({ k: '2014:Mago' })
    expect(result.current[0]).toBeNull()
    rerender({ k: '2014:Guerriero' })
    expect(result.current[0]).toBeNull()
  })
})

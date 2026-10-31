import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ItemCastSheet from '@/pages/spells/ItemCastSheet'
import { resolveItemCast } from '@/lib/itemCast'
import type { CharacterFull, Item } from '@/types'

const { result } = vi.hoisted(() => ({ result: vi.fn() }))
vi.mock('@/api/client', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, api: { dice: { result } } }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/hooks/useD20Roll', () => ({ useD20Roll: () => async () => [14] }))
vi.mock('@/components/ui/ResultDialog', () => ({
  default: (p: { children: unknown }) => <div>{p.children as never}</div>,
}))
vi.mock('@/components/RollResultModal', () => ({
  default: (p: { result: { total: number } }) => <div>total:{p.result.total}</div>,
}))
vi.mock('@/components/ui/RollButton', () => ({
  default: (p: { onRoll: (m: string) => void; ariaLabel: string }) => (
    <button onClick={() => p.onRoll('normal')}>{p.ariaLabel}</button>
  ),
}))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return {
    ...actual,
    useTranslation: () => ({
      t: (k: string, o?: Record<string, unknown>) => (o ? `${k}|${Object.values(o).join(',')}` : k),
      i18n: { language: 'it' },
    }),
  }
})

const item = (g: Record<string, unknown>): Item => ({
  id: 1, name: 'Bacchetta', item_type: 'generic', quantity: 1, weight: 0, is_equipped: false,
  item_metadata: {
    charges: { max: 7, current: 4, recharge: 'none', recharge_amount: 'all' },
    granted_spells: [{ name: 'Palla di Fuoco', level: 3, charges_cost: 3, is_concentration: false, ...g }],
  },
} as unknown as Item)

const char = {
  id: 7,
  spellcasting: { casters: [{ class_id: 1, class_name: 'wizard', ability: 'intelligence', save_dc: 15, attack_bonus: 7 }] },
  spells: [
    { id: 1, name: 'Palla di Fuoco', attack_save: 'DEX' },
    { id: 2, name: 'Raggio di Fuoco', attack_save: 'ATK' },
  ],
} as unknown as CharacterFull

afterEach(() => vi.clearAllMocks())

function renderSheet(c: CharacterFull, it: Item) {
  const resolved = resolveItemCast(c, it, 0)!
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <ItemCastSheet charId={7} resolved={resolved} onClose={() => {}} />
    </QueryClientProvider>,
  )
}

describe('resolveItemCast', () => {
  it('item values override character values', () => {
    const r = resolveItemCast(char, item({ save_dc: 18, attack_bonus: 9 }), 0)!
    expect(r.saveDc).toBe(18)
    expect(r.attackBonus).toBe(9)
    expect(r.isAttack).toBe(true)
  })
  it('falls back to the character values and finds the save ability', () => {
    const r = resolveItemCast(char, item({}), 0)!
    expect(r.saveDc).toBe(15)
    expect(r.attackBonus).toBe(7)
    expect(r.isAttack).toBe(false)
    expect(r.saveAbility).toBe('DEX')
    expect(r.spent).toBe(3)
    expect(r.remaining).toBe(4)
  })
  it('treats a matching ATK character spell as an attack', () => {
    expect(resolveItemCast(char, item({ name: 'Raggio di Fuoco' }), 0)!.isAttack).toBe(true)
  })
})

describe('ItemCastSheet', () => {
  it('shows DC and save ability, with no attack button for a save spell', () => {
    renderSheet(char, item({}))
    expect(screen.getByText(/dc_save\|15,DEX/)).toBeTruthy()
    expect(screen.queryByText('character.inventory.magic.roll_attack')).toBeNull()
  })

  it('offers the attack roll only for attack spells and rolls d20 + resolved bonus', async () => {
    result.mockResolvedValue({})
    renderSheet(char, item({ attack_bonus: 9 }))
    await userEvent.click(screen.getByText('character.inventory.magic.roll_attack'))
    await waitFor(() => expect(result).toHaveBeenCalled())
    expect(result.mock.calls[0][1]).toMatchObject({ modifier: 9, mode: 'normal', rolls: [{ kind: 'd20', value: 14 }] })
    expect(await screen.findByText('total:23')).toBeTruthy()
  })
})

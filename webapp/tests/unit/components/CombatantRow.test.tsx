import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import CombatantRow from '@/components/session/CombatantRow'
import type { CharacterLiveSnapshot, CombatantLive } from '@/types'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/components/ui/ConditionBadge', () => ({
  default: ({ conditionKey }: { conditionKey: string }) => (
    <span data-testid={`cond-${conditionKey}`} />
  ),
}))

const monster = (over: Partial<CombatantLive> = {}): CombatantLive => ({
  id: 1, kind: 'monster', character_id: null, owner_user_id: null,
  name: 'Goblin 1', initiative: 12, initiative_die: 10, initiative_mod: 2,
  sort_order: 20, is_dead: false, conditions: {},
  current_hp: null, max_hp: null, ac: null, hp_bucket: null,
  ...over,
})

const pcSnapshot: CharacterLiveSnapshot = {
  id: 7, name: 'Eroe', race: null, class_summary: 'Guerriero 3', total_level: 3,
  hit_points: 20, current_hit_points: 12, temp_hp: 0, ac: 16,
  conditions: { prone: true }, death_saves: {}, heroic_inspiration: false,
  last_roll: null, hp_bucket: 'lightly_wounded', armor_category: 'heavy',
}

describe('CombatantRow', () => {
  it('mostro vista GM: PF esatti e CA', () => {
    render(
      <CombatantRow
        combatant={monster({ current_hp: 4, max_hp: 7, ac: 15 })}
        isActive={false} amGm={true} mode="full"
      />,
    )
    expect(screen.getByText('4/7')).toBeInTheDocument()
    expect(screen.getByText('15')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()   // iniziativa
  })

  it('mostro vista giocatore: niente numeri, barra a fascia', () => {
    render(
      <CombatantRow
        combatant={monster({ hp_bucket: 'badly_wounded' })}
        isActive={false} amGm={false} mode="full"
      />,
    )
    expect(screen.queryByText('4/7')).not.toBeInTheDocument()
    expect(screen.getByTestId('hp-bucket-bar')).toBeInTheDocument()
  })

  it('PG: PF dallo snapshot live e condizioni dalla scheda', () => {
    render(
      <CombatantRow
        combatant={monster({ id: 2, kind: 'pc', character_id: 7, name: 'Eroe' })}
        snapshot={pcSnapshot}
        isActive={false} amGm={false} mode="full"
      />,
    )
    expect(screen.getByText('12/20')).toBeInTheDocument()
    expect(screen.getByTestId('cond-prone')).toBeInTheDocument()
  })

  it('turno attivo marcato, morto in grigio', () => {
    const { rerender } = render(
      <CombatantRow combatant={monster()} isActive={true} amGm={false} mode="light" />,
    )
    expect(screen.getByTestId('combatant-row').dataset.active).toBe('true')
    rerender(
      <CombatantRow combatant={monster({ is_dead: true })} isActive={false} amGm={false} mode="light" />,
    )
    expect(screen.getByTestId('combatant-row').dataset.dead).toBe('true')
  })
})

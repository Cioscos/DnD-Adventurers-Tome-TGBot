import { describe, expect, it, vi } from 'vitest'
import { render } from '@testing-library/react'
import CombatantRow from '@/components/session/CombatantRow'
import { conditionRounds } from '@/lib/conditionEffects'
import type { CombatantLive, ConditionEffect } from '@/types'

vi.mock('react-i18next', async (orig) => ({
  ...(await orig<typeof import('react-i18next')>()),
  useTranslation: () => ({ t: (k: string, o?: Record<string, unknown>) => (o ? `${k}|${JSON.stringify(o)}` : k), i18n: { language: 'it' } }),
}))
const badge = vi.fn()
vi.mock('@/components/ui/ConditionBadge', () => ({
  default: (props: { conditionKey: string; detail?: string; notes?: string[] }) => { badge(props); return null },
}))

const istanza = (extra: Partial<ConditionEffect>): ConditionEffect => ({
  slug: 'frightened', expiry_anchor: null, expiry_edge: null, expiry_count: null, save_ability: null, save_dc: null, save_edge: null,
  source_name: null, ends_with_concentration: false, applied_by_gm: false, source_note: null, ...extra,
} as ConditionEffect)

describe('caccia: regola 2024 generali', () => {
  // caccia: {"id": "CB-4243", "fonte": "2024 · Condizioni · pag. 29: ogni istanza ha la sua durata, la condizione resta finché ne resta una", "zona": "regola:2024/generali", "voce": "interazione", "copre": ["carta:2024/general.md#Condizioni / Conditions (pag. 29)", "route:/char/:id/conditions"]}
  it('il conteggio dei round è quello dell\'istanza più lunga, e nessuno se una non ha durata', () => {
    const drago = istanza({ expiry_count: 10, source_name: 'Drago' })
    // l'istanza più nuova (1 round) non accorcia la condizione, che dura ancora 10 round
    expect(conditionRounds([drago, istanza({ expiry_count: 1, source_name: 'Goblin' })])).toEqual({ frightened: 10 })
    expect(conditionRounds([istanza({ expiry_count: 1, source_name: 'Goblin' }), drago])).toEqual({ frightened: 10 })
    expect(conditionRounds([drago, istanza({ save_ability: 'wisdom', save_dc: 13 })])).toEqual({})
  })

  // caccia: {"id": "CB-4244", "fonte": "2024 · Condizioni · pag. 29: ogni istanza ha la sua durata, il suo TS e la sua fonte", "zona": "regola:2024/generali", "voce": "interazione", "copre": ["carta:2024/general.md#Condizioni / Conditions (pag. 29)", "route:/session/:id/combat"]}
  it('la riga del combattente mostra durata e fonte di ogni istanza della condizione', () => {
    const mostro = {
      id: 1, kind: 'monster', character_id: null, owner_user_id: null, name: 'Orco', initiative: 12, initiative_die: 10,
      initiative_mod: 2, sort_order: 20, is_dead: false, conditions: { frightened: true },
      current_hp: 10, max_hp: 15, ac: 13, hp_bucket: null,
      condition_effects: [istanza({ expiry_count: 10, source_name: 'Drago' }), istanza({ expiry_count: 1, source_name: 'Goblin' })],
    } as unknown as CombatantLive
    render(<CombatantRow combatant={mostro} isActive={false} amGm mode="full" />)
    const { detail, notes } = badge.mock.calls.at(-1)![0]
    expect(detail).toContain('"count":10')
    expect(notes.filter((n: string) => n.startsWith('session.combat.source_label'))).toEqual([
      'session.combat.source_label|{"name":"Drago"}', 'session.combat.source_label|{"name":"Goblin"}'])
  })
})

import { describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'
import { render, screen } from '@testing-library/react'
import WeaponAttackModal, { type WeaponAttackResult } from '@/components/WeaponAttackModal'

vi.mock('framer-motion', async () => {
  const React = await import('react')
  const make = (tag: string) => (props: Record<string, unknown>) => {
    const clean: Record<string, unknown> = {}
    for (const k in props) if (!['initial', 'animate', 'transition'].includes(k)) clean[k] = props[k]
    return React.createElement(tag, clean)
  }
  return { useReducedMotion: () => false, m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }) }
})
vi.mock('@/components/ui/ResultDialog', async () => {
  const React = await import('react')
  return { default: (p: { children?: ReactNode }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/rules/RollNotes', () => ({ default: () => null }))
vi.mock('@/components/rules/AfterDamageOptions', () => ({ default: () => null }))
vi.mock('@/components/InspirationRerollButton', () => ({ default: () => null }))
vi.mock('@/components/ui/D20Faces', () => ({ default: () => null }))
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (k: string, o?: Record<string, unknown>) => (o ? `${k} ${JSON.stringify(o)}` : k) }),
}))

const base: WeaponAttackResult = {
  weapon_name: 'Arco corto', to_hit_die: 12, dice: [12], mode: 'normal', mode_applied: 'normal', notes: [],
  to_hit_bonus: 5, to_hit_total: 17, is_critical: false, is_fumble: false, damage_dice: '1d6', damage_rolls: [4],
  damage_bonus: 3, damage_total: 7, magic_bonus: 0, proficiency_warning: false, ammo: null, ammo_missing: false,
} as WeaponAttackResult

// caccia: {"id": "CB-070", "fonte": "invariante: il modale mostra le munizioni rimaste e quando mancano", "zona": "flusso:attacco-danno", "voce": "contratto", "copre": ["route:/char/:id/inventory"]}
describe('WeaponAttackModal', () => {
  it('mostra le munizioni rimaste o l\'avviso di munizioni mancanti', () => {
    const { rerender } = render(<WeaponAttackModal result={{ ...base, ammo: { item_id: 1, name: 'Frecce', remaining: 9 } }} onClose={() => {}} />)
    expect(screen.getByText('Frecce: 9')).toBeTruthy()
    expect(screen.queryByText('character.attack.ammo_missing')).toBeNull()
    rerender(<WeaponAttackModal result={{ ...base, ammo_missing: true }} onClose={() => {}} />)
    expect(screen.getByText('character.attack.ammo_missing')).toBeTruthy()
  })

  // caccia: {"id": "CB-071", "fonte": "2014 · Tiri per colpire e danni · pag. 194-196: un fumble non fa danno", "zona": "flusso:attacco-danno", "voce": "limiti", "copre": ["route:/char/:id/inventory"]}
  it('un fumble non mostra il blocco del danno e un critico mostra i dadi raddoppiati', () => {
    const { rerender } = render(<WeaponAttackModal result={{ ...base, to_hit_die: 1, is_fumble: true, damage_rolls: [0], damage_total: 0, damage_bonus: 0 }} onClose={() => {}} />)
    expect(screen.getByText('character.dice.fumble_banner', { exact: false })).toBeTruthy()
    expect(screen.queryByText('character.attack.damage', { exact: false })).toBeNull()
    rerender(<WeaponAttackModal result={{ ...base, is_critical: true, damage_rolls: [4, 5], damage_total: 12 }} onClose={() => {}} />)
    expect(screen.getByText('[4, 5] +3')).toBeTruthy()
    expect(screen.getByText('12')).toBeTruthy()
  })
})

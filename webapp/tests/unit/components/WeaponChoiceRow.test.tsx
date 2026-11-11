import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import WeaponChoiceRow from '@/components/WeaponChoiceRow'
import { DEFAULT_WEAPON_CHOICE } from '@/lib/weaponOptions'

vi.mock('react-i18next', async (orig) => ({
  ...(await orig() as object), useTranslation: () => ({ t: (k: string) => k }),
}))

const light = { id: 1, item_type: 'weapon', is_equipped: true, item_metadata: { properties: ['prop_light'] } }
const other = { id: 2, item_type: 'weapon', is_equipped: true, item_metadata: { properties: ['prop_light'] } }
const scores = [{ name: 'strength', modifier: 3 }, { name: 'dexterity', modifier: 1 }]
const char = (over = {}) => ({ items: [light, other], classes: [], ability_scores: scores, rules_edition: '2014', ...over })

describe('WeaponChoiceRow', () => {
  it('offers the other hand only with a second equipped light weapon', async () => {
    const onChange = vi.fn()
    render(<WeaponChoiceRow item={light} char={char()} choice={DEFAULT_WEAPON_CHOICE} onChange={onChange} />)
    await userEvent.click(screen.getByText('character.attack.offhand'))
    expect(onChange).toHaveBeenCalledWith({ ...DEFAULT_WEAPON_CHOICE, attack_mode: 'offhand' })
  })

  it('no other hand with a single light weapon', () => {
    const { container } = render(
      <WeaponChoiceRow item={light} char={char({ items: [light] })} choice={DEFAULT_WEAPON_CHOICE} onChange={vi.fn()} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('finesse: the best ability is lit and can be changed', async () => {
    const rapier = { id: 3, item_type: 'weapon', item_metadata: { properties: ['prop_finesse'] } }
    const onChange = vi.fn()
    render(<WeaponChoiceRow item={rapier} char={char()} choice={DEFAULT_WEAPON_CHOICE} onChange={onChange} />)
    expect(screen.getByText('character.attack.ability_strength')).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByText('character.attack.ability_dexterity'))
    expect(onChange).toHaveBeenCalledWith({ ...DEFAULT_WEAPON_CHOICE, ability: 'dexterity' })
  })

  it('a weapon the server marks for Martial Arts has the choice too (punto 42: the rule belongs to the server)', () => {
    const staff = { id: 4, item_type: 'weapon', martial_arts: true, item_metadata: { weapon_category: 'simple' } }
    const monk = char({ items: [], classes: [{ class_name: 'monk', level: 1 }] })
    const { rerender } = render(<WeaponChoiceRow item={staff} char={monk} choice={DEFAULT_WEAPON_CHOICE} onChange={vi.fn()} />)
    expect(screen.getByText('character.attack.ability_dexterity')).toBeInTheDocument()
    rerender(<WeaponChoiceRow item={{ ...staff, martial_arts: false }} char={monk} choice={DEFAULT_WEAPON_CHOICE} onChange={vi.fn()} />)
    expect(screen.queryByText('character.attack.ability_dexterity')).toBeNull()
  })
})

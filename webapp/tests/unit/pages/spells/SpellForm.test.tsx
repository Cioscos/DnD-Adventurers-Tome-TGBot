import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SpellForm from '@/pages/spells/SpellForm'
import type { Spell } from '@/types'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
const FIREBALL = {
  index: 'fireball', name: { en: 'Fireball', it: 'Palla di fuoco' }, level: 3, school: 'evocation',
  casting_time: { en: '1 action', it: '1 azione' }, range_ft: 150, range_text: { en: '150 feet', it: '150 piedi' },
  area: { type: 'sphere', size_ft: 20 }, components: ['V', 'S', 'M'],
  material: { en: 'A tiny ball of bat guano and sulfur.', it: 'Guano e zolfo.' },
  duration: { en: 'Instantaneous', it: 'Istantanea' }, concentration: false, ritual: false,
  desc: { en: 'A bright streak.', it: 'Un lampo.' }, higher_level: { en: 'More.', it: 'Di piu.' },
  attack_type: 'SAVE', save_ability: 'dex', damage_dice: '8d6', damage_type: 'fire', higher_levels_dice: '1d6',
}
vi.mock('@/components/catalog/CatalogPicker', async () => {
  const React = await import('react')
  return { default: (p: { onPick: (e: unknown) => void }) => React.createElement('button', { onClick: () => p.onPick(FIREBALL) }, 'pick-fireball') }
})
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; title?: unknown; children?: unknown }) => (p.open ? React.createElement('div', null, React.createElement('h2', null, p.title), p.children) : null) }
})
vi.mock('@/components/ui/Input', async () => {
  const React = await import('react')
  return { default: (p: { label?: string; placeholder?: string; value: string; onChange: (v: string) => void }) => React.createElement('input', { 'aria-label': p.label || p.placeholder, value: p.value, onChange: (e: { target: { value: string } }) => p.onChange(e.target.value) }) }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return { default: (p: { onClick?: () => void; disabled?: boolean; loading?: boolean; children?: unknown }) => React.createElement('button', { onClick: p.onClick, disabled: p.disabled || p.loading }, p.children) }
})

describe('SpellForm', () => {
  it('add mode: title, name-gated submit, emits the form', async () => {
    const onSubmit = vi.fn()
    render(<SpellForm onSubmit={onSubmit} onCancel={() => {}} isPending={false} />)
    expect(screen.getByRole('heading', { name: 'character.spells.add' })).toBeInTheDocument()
    const add = screen.getByRole('button', { name: 'common.add' })
    expect(add).toBeDisabled()
    fireEvent.change(screen.getByLabelText('character.spells.name'), { target: { value: 'Scudo' } })
    expect(add).toBeEnabled()
    await userEvent.click(add)
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ name: 'Scudo', level: '0' }))
  })

  it('edit mode: seeds the name and shows the edit title + save', () => {
    const initial = { id: 1, name: 'Palla di Fuoco', level: 3, is_concentration: false, is_ritual: false } as Spell
    render(<SpellForm initialData={initial} onSubmit={() => {}} onCancel={() => {}} isPending={false} />)
    expect(screen.getByRole('heading', { name: 'character.spells.edit' })).toBeInTheDocument()
    expect(screen.getByLabelText('character.spells.name')).toHaveValue('Palla di Fuoco')
    expect(screen.getByRole('button', { name: 'common.save' })).toBeInTheDocument()
  })

  it('cancels', async () => {
    const onCancel = vi.fn()
    render(<SpellForm onSubmit={() => {}} onCancel={onCancel} isPending={false} />)
    await userEvent.click(screen.getByRole('button', { name: 'common.cancel' }))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('picking a level chip emits the level on submit', async () => {
    const onSubmit = vi.fn()
    render(<SpellForm onSubmit={onSubmit} onCancel={() => {}} isPending={false} />)
    fireEvent.change(screen.getByLabelText('character.spells.name'), { target: { value: 'Scudo' } })
    await userEvent.click(screen.getByRole('radio', { name: '3' }))
    await userEvent.click(screen.getByRole('button', { name: 'common.add' }))
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ level: '3' }))
  })

  it('edit mode: an out-of-preset duration lands on the Altro chip with the text editable', () => {
    const initial = {
      id: 1, name: 'X', level: 1, duration: 'Finché non si dissolve',
      is_concentration: false, is_ritual: false,
    } as Spell
    render(<SpellForm initialData={initial} onSubmit={() => {}} onCancel={() => {}} isPending={false} />)
    const group = screen.getByRole('radiogroup', { name: 'character.spells.duration' })
    expect(within(group).getByRole('radio', { name: 'common.other' })).toHaveAttribute('aria-checked', 'true')
  })

  it('turning the damage toggle off clears dice and type on submit', async () => {
    const onSubmit = vi.fn()
    const initial = {
      id: 1, name: 'Palla di Fuoco', level: 3, damage_dice: '8d6', damage_type: 'fire',
      is_concentration: false, is_ritual: false,
    } as Spell
    render(<SpellForm initialData={initial} onSubmit={onSubmit} onCancel={() => {}} isPending={false} />)
    const dealsDamage = screen.getByRole('switch', { name: 'character.spells.deals_damage' })
    expect(dealsDamage).toHaveAttribute('aria-checked', 'true')
    await userEvent.click(dealsDamage)
    await userEvent.click(screen.getByRole('button', { name: 'common.save' }))
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ damage_dice: '', damage_type: '' }))
  })

  it('V/S/M toggles serialize the components string', async () => {
    const onSubmit = vi.fn()
    render(<SpellForm onSubmit={onSubmit} onCancel={() => {}} isPending={false} />)
    fireEvent.change(screen.getByLabelText('character.spells.name'), { target: { value: 'Scudo' } })
    await userEvent.click(screen.getByRole('button', { name: 'S' }))
    await userEvent.click(screen.getByRole('button', { name: 'V' }))
    await userEvent.click(screen.getByRole('button', { name: 'common.add' }))
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ components: 'V, S' }))
  })
  it('picking Attacco in the Tipo selector emits attack_save ATK', async () => {
    const onSubmit = vi.fn()
    render(<SpellForm onSubmit={onSubmit} onCancel={() => {}} isPending={false} />)
    fireEvent.change(screen.getByLabelText('character.spells.name'), { target: { value: 'Scudo' } })
    await userEvent.click(screen.getByRole('radio', { name: 'character.spells.attack_save.atk' }))
    await userEvent.click(screen.getByRole('button', { name: 'common.add' }))
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ attack_save: 'ATK' }))
  })

  it('catalogue pick prefills the form incl. srd_index, school and upcast dice', async () => {
    const onSubmit = vi.fn()
    render(<SpellForm onSubmit={onSubmit} onCancel={() => {}} isPending={false} />)
    await userEvent.click(screen.getByRole('button', { name: 'character.spells.from_catalog' }))
    await userEvent.click(screen.getByRole('button', { name: 'pick-fireball' }))
    expect(screen.getByLabelText('character.spells.name')).toHaveValue('Palla di fuoco')
    expect(screen.getByRole('radio', { name: '1 azione' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('switch', { name: 'character.spells.deals_damage' })).toHaveAttribute('aria-checked', 'true')
    await userEvent.click(screen.getByRole('button', { name: 'common.add' }))
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
      srd_index: 'fireball', school: 'evocation', higher_levels_dice: '1d6',
      damage_dice: '8d6', damage_type: 'fire', attack_save: 'SAVE', level: '3',
    }))
  })

  it('edit with srd_index offers reload from catalogue', () => {
    const initial = { id: 1, name: 'X', level: 3, srd_index: 'fireball', is_concentration: false, is_ritual: false } as Spell
    render(<SpellForm initialData={initial} onSubmit={() => {}} onCancel={() => {}} isPending={false} />)
    expect(screen.getByRole('button', { name: 'character.spells.reload_catalog' })).toBeInTheDocument()
  })
})

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
  return { default: (p: { kind: string; onPick: (e: unknown) => void; note?: string; filters?: (e: unknown) => boolean }) =>
    React.createElement('div', { 'data-filtered': p.filters ? 'yes' : 'no', 'data-kind': p.kind },
      p.note && React.createElement('p', null, p.note),
      React.createElement('button', { onClick: () => p.onPick(FIREBALL) }, 'pick-fireball')) }
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
  const casters = [{ class_id: 1, class_name: 'wizard' }, { class_id: 2, class_name: 'cleric' }]

  it('asks for the class only with two casters, and sends it', async () => {
    const onSubmit = vi.fn()
    const { unmount } = render(<SpellForm onSubmit={onSubmit} onCancel={() => {}} isPending={false} casters={casters.slice(0, 1)} />)
    expect(screen.queryByText('character.spells.class_label')).not.toBeInTheDocument()
    unmount()
    render(<SpellForm onSubmit={onSubmit} onCancel={() => {}} isPending={false} casters={casters} />)
    fireEvent.change(screen.getByLabelText('character.spells.name'), { target: { value: 'Scudo' } })
    await userEvent.click(screen.getByRole('radio', { name: /cleric/ }))
    await userEvent.click(screen.getByRole('button', { name: 'common.add' }))
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ class_id: '2' }))
  })

  it('an unassigned spell stays unassigned, and a saved class is kept', async () => {
    const onSubmit = vi.fn()
    const saved = { id: 1, name: 'Scudo', level: 1, class_id: 2, always_prepared: true, is_concentration: false, is_ritual: false } as Spell
    render(<SpellForm initialData={saved} onSubmit={onSubmit} onCancel={() => {}} isPending={false} casters={casters} />)
    await userEvent.click(screen.getByRole('button', { name: 'common.save' }))
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ class_id: '2', always_prepared: true }))
  })

  it('a cantrip pick narrows the catalogue and says how to add a spell that is not listed', async () => {
    render(<SpellForm onSubmit={() => {}} onCancel={() => {}} isPending={false} pickFilter={{ max_level: 0, list: 'druid' }} />)
    await userEvent.click(screen.getByRole('button', { name: 'character.spells.from_catalog' }))
    expect(screen.getByText('character.spells.pick_filter_note')).toBeInTheDocument()
    expect(screen.getByText('pick-fireball').parentElement).toHaveAttribute('data-filtered', 'yes')
  })

  it('without a pick the catalogue is whole and has no note', async () => {
    render(<SpellForm onSubmit={() => {}} onCancel={() => {}} isPending={false} />)
    await userEvent.click(screen.getByRole('button', { name: 'character.spells.from_catalog' }))
    expect(screen.queryByText('character.spells.pick_filter_note')).toBeNull()
    expect(screen.getByText('pick-fireball').parentElement).toHaveAttribute('data-filtered', 'no')
  })

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

  it('a 2024 character picks from the 2024 catalogue', async () => {
    const { container } = render(<SpellForm edition="2024" onSubmit={() => {}} onCancel={() => {}} isPending={false} />)
    await userEvent.click(screen.getByRole('button', { name: 'character.spells.from_catalog' }))
    expect(container.querySelector('[data-kind]')?.getAttribute('data-kind')).toBe('spells-2024')
  })

  it('reload reads the catalogue of the character edition', async () => {
    const initial = { id: 1, name: 'X', level: 2, srd_index: 'arcane-vigor', is_concentration: false, is_ritual: false } as Spell
    render(<SpellForm edition="2024" initialData={initial} onSubmit={() => {}} onCancel={() => {}} isPending={false} />)
    await userEvent.click(screen.getByRole('button', { name: 'character.spells.reload_catalog' }))
    await userEvent.click(await screen.findByRole('button', { name: 'character.spells.reload_confirm' }))
    expect(await screen.findByDisplayValue('Vigore Arcano')).toBeInTheDocument()
  })

  it('reload says so when the spell is not in the edition catalogue', async () => {
    const initial = { id: 1, name: 'Punizione Marchiante', level: 2, srd_index: 'branding-smite', is_concentration: false, is_ritual: false } as Spell
    render(<SpellForm edition="2024" initialData={initial} onSubmit={() => {}} onCancel={() => {}} isPending={false} />)
    await userEvent.click(screen.getByRole('button', { name: 'character.spells.reload_catalog' }))
    await userEvent.click(await screen.findByRole('button', { name: 'character.spells.reload_confirm' }))
    expect(await screen.findByText('character.spells.reload_missing')).toBeInTheDocument()
  })

  it('editing keeps the second part of the damage', async () => {
    const onSubmit = vi.fn()
    const saved = { id: 1, name: 'Onda', level: 5, damage_dice: '5d6', damage_type: 'thunder', extra_damage_dice: '5d6',
      extra_damage_type: 'radiant|necrotic', is_concentration: false, is_ritual: false } as Spell
    render(<SpellForm initialData={saved} onSubmit={onSubmit} onCancel={() => {}} isPending={false} />)
    await userEvent.click(screen.getByRole('button', { name: 'common.save' }))
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ extra_damage_dice: '5d6', extra_damage_type: 'radiant|necrotic' }))
  })
})

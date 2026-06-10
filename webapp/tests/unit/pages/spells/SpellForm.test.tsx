import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SpellForm from '@/pages/spells/SpellForm'
import type { Spell } from '@/types'

const { srd } = vi.hoisted(() => ({ srd: { value: null as unknown } }))

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/lib/spellSrd', () => ({ lookupSrdSpell: () => srd.value }))
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
    srd.value = null
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
    srd.value = null
    const initial = { id: 1, name: 'Palla di Fuoco', level: 3, is_concentration: false, is_ritual: false } as Spell
    render(<SpellForm initialData={initial} onSubmit={() => {}} onCancel={() => {}} isPending={false} />)
    expect(screen.getByRole('heading', { name: 'character.spells.edit' })).toBeInTheDocument()
    expect(screen.getByLabelText('character.spells.name')).toHaveValue('Palla di Fuoco')
    expect(screen.getByRole('button', { name: 'common.save' })).toBeInTheDocument()
  })

  it('offers the SRD autofill affordance on a recognized name', () => {
    srd.value = { level: 1, casting_time: '1 azione', range_area: '18m', components: 'V,S', duration: 'Ist.', damage_dice: '', damage_type: '' }
    render(<SpellForm onSubmit={() => {}} onCancel={() => {}} isPending={false} />)
    expect(screen.getByText('character.spells.srd_autofill')).toBeInTheDocument()
  })

  it('cancels', async () => {
    srd.value = null
    const onCancel = vi.fn()
    render(<SpellForm onSubmit={() => {}} onCancel={onCancel} isPending={false} />)
    await userEvent.click(screen.getByRole('button', { name: 'common.cancel' }))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('picking a level chip emits the level on submit', async () => {
    srd.value = null
    const onSubmit = vi.fn()
    render(<SpellForm onSubmit={onSubmit} onCancel={() => {}} isPending={false} />)
    fireEvent.change(screen.getByLabelText('character.spells.name'), { target: { value: 'Scudo' } })
    await userEvent.click(screen.getByRole('radio', { name: '3' }))
    await userEvent.click(screen.getByRole('button', { name: 'common.add' }))
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ level: '3' }))
  })

  it('SRD autofill highlights the matching preset chips and turns the damage toggle on', async () => {
    srd.value = {
      level: 3,
      casting_time: '1 azione',
      range_area: '45 m',
      components: 'V, S, M (guano e zolfo)',
      duration: 'Istantanea',
      damage_dice: '8d6',
      damage_type: 'fire',
    }
    render(<SpellForm onSubmit={() => {}} onCancel={() => {}} isPending={false} />)
    await userEvent.click(screen.getByText('character.spells.srd_autofill'))

    expect(screen.getByRole('radio', { name: '1 azione' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('radio', { name: '45 m' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('radio', { name: 'Istantanea' })).toHaveAttribute('aria-checked', 'true')
    // V/S/M toggles on + material detail extracted
    expect(screen.getByRole('button', { name: 'M' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByLabelText('character.spells.material_detail_label')).toHaveValue('guano e zolfo')
    // damage section revealed with dice + type selected
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByText('8d6')).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'character.inventory.damage_types.dmg_fire' }))
      .toHaveAttribute('aria-checked', 'true')
  })

  it('edit mode: an out-of-preset duration lands on the Altro chip with the text editable', () => {
    srd.value = null
    const initial = {
      id: 1, name: 'X', level: 1, duration: 'Finché non si dissolve',
      is_concentration: false, is_ritual: false,
    } as Spell
    render(<SpellForm initialData={initial} onSubmit={() => {}} onCancel={() => {}} isPending={false} />)
    const group = screen.getByRole('radiogroup', { name: 'character.spells.duration' })
    expect(within(group).getByRole('radio', { name: 'common.other' })).toHaveAttribute('aria-checked', 'true')
  })

  it('turning the damage toggle off clears dice and type on submit', async () => {
    srd.value = null
    const onSubmit = vi.fn()
    const initial = {
      id: 1, name: 'Palla di Fuoco', level: 3, damage_dice: '8d6', damage_type: 'fire',
      is_concentration: false, is_ritual: false,
    } as Spell
    render(<SpellForm initialData={initial} onSubmit={onSubmit} onCancel={() => {}} isPending={false} />)
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'true')
    await userEvent.click(screen.getByRole('switch'))
    await userEvent.click(screen.getByRole('button', { name: 'common.save' }))
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ damage_dice: '', damage_type: '' }))
  })

  it('V/S/M toggles serialize the components string', async () => {
    srd.value = null
    const onSubmit = vi.fn()
    render(<SpellForm onSubmit={onSubmit} onCancel={() => {}} isPending={false} />)
    fireEvent.change(screen.getByLabelText('character.spells.name'), { target: { value: 'Scudo' } })
    await userEvent.click(screen.getByRole('button', { name: 'S' }))
    await userEvent.click(screen.getByRole('button', { name: 'V' }))
    await userEvent.click(screen.getByRole('button', { name: 'common.add' }))
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ components: 'V, S' }))
  })
})

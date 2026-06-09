import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
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
})

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AddClassForm from '@/pages/multiclass/AddClassForm'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/store/overlayStore', () => ({ useRegisterOverlay: () => {} }))
vi.mock('@/components/Card', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/DndInput', async () => {
  const React = await import('react')
  return {
    default: (p: { label?: string; placeholder?: string; value: string; onChange: (v: string) => void }) =>
      React.createElement('input', {
        'aria-label': p.label || p.placeholder,
        value: p.value,
        onChange: (e: { target: { value: string } }) => p.onChange(e.target.value),
      }),
  }
})
vi.mock('@/components/DndButton', async () => {
  const React = await import('react')
  return {
    default: (p: { onClick?: () => void; disabled?: boolean; loading?: boolean; children?: unknown }) =>
      React.createElement('button', { onClick: p.onClick, disabled: p.disabled || p.loading }, p.children),
  }
})

const noop = () => {}

describe('AddClassForm', () => {
  it('selecting a predefined class auto-fills and locks its hit die', async () => {
    render(<AddClassForm onAdd={noop} onCancel={noop} isPending={false} />)
    const [classSelect, hitDieSelect] = screen.getAllByRole('combobox')
    await userEvent.selectOptions(classSelect, 'fighter')
    expect(hitDieSelect).toBeDisabled()
    expect(hitDieSelect).toHaveValue('10') // fighter → d10
  })

  it('keeps Add disabled until a class is chosen', async () => {
    render(<AddClassForm onAdd={noop} onCancel={noop} isPending={false} />)
    const add = screen.getByRole('button', { name: 'common.add' })
    expect(add).toBeDisabled()
    await userEvent.selectOptions(screen.getAllByRole('combobox')[0], 'wizard')
    expect(add).toBeEnabled()
  })

  it('a custom class needs a name before it can be added', async () => {
    render(<AddClassForm onAdd={noop} onCancel={noop} isPending={false} />)
    await userEvent.selectOptions(screen.getAllByRole('combobox')[0], '__custom__')
    const add = screen.getByRole('button', { name: 'common.add' })
    expect(add).toBeDisabled()
    fireEvent.change(screen.getByLabelText('character.multiclass.custom_class_name'), { target: { value: 'Warden' } })
    expect(add).toBeEnabled()
  })

  it('submitting emits the assembled class form', async () => {
    const onAdd = vi.fn()
    render(<AddClassForm onAdd={onAdd} onCancel={noop} isPending={false} />)
    await userEvent.selectOptions(screen.getAllByRole('combobox')[0], 'fighter')
    await userEvent.click(screen.getByRole('button', { name: 'common.add' }))
    expect(onAdd).toHaveBeenCalledWith(expect.objectContaining({ class_key: 'fighter', hit_die: '10', level: '1' }))
  })

  it('cancel calls onCancel', async () => {
    const onCancel = vi.fn()
    render(<AddClassForm onAdd={noop} onCancel={onCancel} isPending={false} />)
    await userEvent.click(screen.getByRole('button', { name: 'common.cancel' }))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('hides the level input when the level is locked (level-up flow)', () => {
    render(<AddClassForm onAdd={noop} onCancel={noop} isPending={false} lockLevelTo={3} />)
    expect(screen.queryByLabelText('character.multiclass.level')).not.toBeInTheDocument()
  })
})

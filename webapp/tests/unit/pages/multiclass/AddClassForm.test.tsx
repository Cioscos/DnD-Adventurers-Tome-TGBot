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

// Drive the SelectSheet class picker: tap the trigger, then tap the option row.
async function pickClass(optionLabel: string) {
  await userEvent.click(screen.getByRole('button', { name: /character\.multiclass\.class_name/ }))
  await userEvent.click(screen.getByRole('radio', { name: optionLabel }))
}

describe('AddClassForm', () => {
  it('selecting a predefined class auto-fills and locks its hit die', async () => {
    render(<AddClassForm onAdd={noop} onCancel={noop} isPending={false} />)
    await pickClass('dnd.classes.fighter')
    const d10 = screen.getByRole('radio', { name: 'd10' })
    expect(d10).toHaveAttribute('aria-checked', 'true') // fighter → d10
    expect(d10).toBeDisabled()
  })

  it('keeps Add disabled until a class is chosen', async () => {
    render(<AddClassForm onAdd={noop} onCancel={noop} isPending={false} />)
    const add = screen.getByRole('button', { name: 'common.add' })
    expect(add).toBeDisabled()
    await pickClass('dnd.classes.wizard')
    expect(add).toBeEnabled()
  })

  it('a custom class needs a name before it can be added', async () => {
    render(<AddClassForm onAdd={noop} onCancel={noop} isPending={false} />)
    await pickClass('character.multiclass.custom_class')
    const add = screen.getByRole('button', { name: 'common.add' })
    expect(add).toBeDisabled()
    fireEvent.change(screen.getByLabelText('character.multiclass.custom_class_name'), { target: { value: 'Warden' } })
    expect(add).toBeEnabled()
  })

  it('submitting emits the assembled class form', async () => {
    const onAdd = vi.fn()
    render(<AddClassForm onAdd={onAdd} onCancel={noop} isPending={false} />)
    await pickClass('dnd.classes.fighter')
    await userEvent.click(screen.getByRole('button', { name: 'common.add' }))
    expect(onAdd).toHaveBeenCalledWith(expect.objectContaining({ class_key: 'fighter', hit_die: '10', level: '1' }))
  })

  it('a custom class lets the user pick the hit die via chips', async () => {
    const onAdd = vi.fn()
    render(<AddClassForm onAdd={onAdd} onCancel={noop} isPending={false} />)
    await pickClass('character.multiclass.custom_class')
    fireEvent.change(screen.getByLabelText('character.multiclass.custom_class_name'), { target: { value: 'Warden' } })
    await userEvent.click(screen.getByRole('radio', { name: 'd12' }))
    await userEvent.click(screen.getByRole('button', { name: 'common.add' }))
    expect(onAdd).toHaveBeenCalledWith(expect.objectContaining({ class_key: '__custom__', hit_die: '12' }))
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

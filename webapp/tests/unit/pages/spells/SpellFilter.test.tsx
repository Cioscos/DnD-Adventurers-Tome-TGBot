import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SpellFilter from '@/pages/spells/SpellFilter'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/components/ui/Input', async () => {
  const React = await import('react')
  return { default: (p: { value: string; onChange: (v: string) => void; placeholder?: string }) => React.createElement('input', { placeholder: p.placeholder, value: p.value, onChange: (e: { target: { value: string } }) => p.onChange(e.target.value) }) }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return { default: (p: { onClick?: () => void }) => React.createElement('button', { onClick: p.onClick }, 'add') }
})

describe('SpellFilter', () => {
  it('reports search changes', () => {
    const onSearchChange = vi.fn()
    render(<SpellFilter search="" onSearchChange={onSearchChange} onAddClick={() => {}} />)
    fireEvent.change(screen.getByPlaceholderText('character.spells.search'), { target: { value: 'fire' } })
    expect(onSearchChange).toHaveBeenCalledWith('fire')
  })

  it('fires onAddClick from the add button', async () => {
    const onAddClick = vi.fn()
    render(<SpellFilter search="" onSearchChange={() => {}} onAddClick={onAddClick} />)
    await userEvent.click(screen.getByRole('button', { name: 'add' }))
    expect(onAddClick).toHaveBeenCalledTimes(1)
  })
})

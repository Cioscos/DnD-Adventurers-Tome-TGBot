import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import SubclassSelect from '@/pages/multiclass/SubclassSelect'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/api/client', () => ({
  api: {
    rules: {
      subclasses: vi.fn(async (_e: string, c: string) =>
        c === 'Ladro custom'
          ? []
          : [
              { key: 'berserker', name: { it: 'Cammino del Berserker', en: 'Path of the Berserker' }, choice_level: 3 },
              { key: 'totem_warrior', name: { it: 'Cammino del Combattente Totemico', en: 'Path of the Totem Warrior' }, choice_level: 3 },
            ]),
    },
  },
}))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return {
    default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null),
  }
})

const wrap = (ui: React.ReactElement) =>
  render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>)

describe('SubclassSelect', () => {
  it('picking a catalog entry emits its title in the UI language', async () => {
    const onChange = vi.fn()
    wrap(<SubclassSelect edition="2014" className="Barbaro" value="" onChange={onChange} />)
    await userEvent.click(await screen.findByRole('button', { name: /character.multiclass.subclass/ }))
    await userEvent.click(await screen.findByRole('radio', { name: 'Cammino del Combattente Totemico' }))
    expect(onChange).toHaveBeenCalledWith('Cammino del Combattente Totemico')
  })

  it('picking "Other" after a catalog entry clears the value so the free input can be typed', async () => {
    const onChange = vi.fn()
    wrap(<SubclassSelect edition="2014" className="Barbaro" value="Cammino del Berserker" onChange={onChange} />)
    await userEvent.click(await screen.findByRole('button', { name: /Cammino del Berserker/ }))
    await userEvent.click(await screen.findByRole('radio', { name: 'character.multiclass.subclass_other' }))
    expect(onChange).toHaveBeenCalledWith('')
  })

  it('keeps an unrecognised text visible under "Other"', async () => {
    wrap(<SubclassSelect edition="2014" className="Barbaro" value="Cammino Strano" onChange={() => {}} />)
    expect(await screen.findByDisplayValue('Cammino Strano')).toBeInTheDocument()
    expect(await screen.findByText('character.multiclass.subclass_other')).toBeInTheDocument()
  })

  it('shows a recognised text as the selected catalog entry, without the free input', async () => {
    wrap(<SubclassSelect edition="2014" className="Barbaro" value="Path of the Berserker" onChange={() => {}} />)
    expect(await screen.findByText('Cammino del Berserker')).toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('falls back to a plain input for a class without catalog', async () => {
    wrap(<SubclassSelect edition="2014" className="Ladro custom" value="Boh" onChange={() => {}} />)
    expect(await screen.findByDisplayValue('Boh')).toBeInTheDocument()
    expect(screen.queryByRole('radio')).not.toBeInTheDocument()
  })
})

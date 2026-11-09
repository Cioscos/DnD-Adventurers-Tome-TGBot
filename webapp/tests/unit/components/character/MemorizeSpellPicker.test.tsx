import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MemorizeSpellPicker from '@/components/character/MemorizeSpellPicker'
import type { CharacterFull } from '@/types'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})

const wizard = (feature = true) => ({
  id: 3,
  abilities: feature ? [{ id: 1, feature_key: 'wizard.memorize_spell' }] : [],
  spell_slots: [{ level: 1, total: 4, used: 0, is_pact: false }, { level: 2, total: 3, used: 0, is_pact: false }],
  spells: [
    { id: 10, name: 'Scudo', level: 1, is_prepared: true, always_prepared: false, in_spellbook: true },
    { id: 11, name: 'Sonno', level: 1, is_prepared: false, always_prepared: false, in_spellbook: true },
    { id: 12, name: 'Palla di fuoco', level: 3, is_prepared: false, always_prepared: false, in_spellbook: true },
    { id: 13, name: 'Armatura magica', level: 1, is_prepared: true, always_prepared: true, in_spellbook: true },
    { id: 14, name: 'Dardo', level: 1, is_prepared: false, always_prepared: false, in_spellbook: false },
  ],
}) as unknown as CharacterFull

describe('MemorizeSpellPicker', () => {
  it('offers only prepared (not always prepared) spells to give up and unprepared book spells within the slots', () => {
    render(<MemorizeSpellPicker char={wizard()} onChange={() => {}} />)
    const out = Array.from(screen.getByTestId('memorize-out').querySelectorAll('option')).map((o) => o.textContent)
    const into = Array.from(screen.getByTestId('memorize-into').querySelectorAll('option')).map((o) => o.textContent)
    expect(out).toEqual(['character.quick_actions.memorize_spell_out', 'Scudo'])
    expect(into).toEqual(['character.quick_actions.memorize_spell_into', 'Sonno'])
  })

  it('reports a swap only when both spells are chosen', async () => {
    const onChange = vi.fn()
    render(<MemorizeSpellPicker char={wizard()} onChange={onChange} />)
    await userEvent.selectOptions(screen.getByTestId('memorize-out'), '10')
    expect(onChange).toHaveBeenLastCalledWith(null)
    await userEvent.selectOptions(screen.getByTestId('memorize-into'), '11')
    expect(onChange).toHaveBeenLastCalledWith({ out: 10, into: 11 })
  })

  it('is hidden without the feature', () => {
    const { container } = render(<MemorizeSpellPicker char={wizard(false)} onChange={() => {}} />)
    expect(container).toBeEmptyDOMElement()
  })
})

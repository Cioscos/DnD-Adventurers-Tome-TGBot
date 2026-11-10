import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import MagicFieldsEditor from '@/pages/inventory/MagicFieldsEditor'
import { emptyForm } from '@/pages/inventory/itemMetadata'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})

describe('MagicFieldsEditor, casting level of a granted spell (67)', () => {
  it('offers an optional casting level and writes it into the granted spell', () => {
    const onChange = vi.fn()
    const spell = { name: 'Palla di Fuoco', level: 3, charges_cost: 5, is_concentration: false }
    render(<MagicFieldsEditor form={{ ...emptyForm, is_magic: true, charges: { max: 20, current: 20, recharge: 'dawn', recharge_amount: '1d6' }, granted_spells: [spell] }} onChange={onChange} />)
    fireEvent.change(screen.getByLabelText('character.inventory.magic.spell_cast_level'), { target: { value: '5' } })
    expect(onChange).toHaveBeenCalledWith({ granted_spells: [{ ...spell, slot_level: 5 }] })
  })
})

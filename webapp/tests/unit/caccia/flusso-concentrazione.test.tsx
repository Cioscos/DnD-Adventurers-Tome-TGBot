import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '../utils/renderWithProviders'
import ConcentrationSaveDialog from '@/pages/hp/ConcentrationSaveDialog'
import { concentrationLabel, isConcentrating, itemSpellConcentration } from '@/lib/concentration'
import type { ConcentrationSaveResult } from '@/api/client'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))

const base: ConcentrationSaveResult = {
  die: 12, bonus: 0, total: 12, dc: 15, success: false, lost_concentration: true, is_critical: false, is_fumble: false, dice: [12], mode: 'normal',
} as ConcentrationSaveResult

describe('caccia: concentrazione', () => {
  // caccia: {"id": "CB-463", "fonte": "2014 · Concentrazione · pag. 203", "zona": "flusso:concentrazione", "voce": "normale", "copre": ["route:/char/:id/spells"]}
  it('un tiro fallito che fa cadere la concentrazione lo dice', () => {
    renderWithProviders(<ConcentrationSaveDialog result={base} onClose={() => {}} />)
    expect(screen.getByText('character.spells.conc_save_fail')).toBeInTheDocument()
    expect(screen.getByText('character.spells.conc_lost')).toBeInTheDocument()
  })

  // caccia: {"id": "CB-464", "fonte": "2014 · Concentrazione · pag. 203", "zona": "flusso:concentrazione", "voce": "normale", "copre": ["route:/char/:id/spells"]}
  it('un tiro riuscito non dice che la concentrazione è caduta', () => {
    renderWithProviders(<ConcentrationSaveDialog result={{ ...base, success: true, lost_concentration: false, total: 15, die: 15 }} onClose={() => {}} />)
    expect(screen.getByText('character.spells.conc_save_success')).toBeInTheDocument()
    expect(screen.queryByText('character.spells.conc_lost')).toBeNull()
  })

  // caccia: {"id": "CB-465", "fonte": "invariante: il frontend riconosce la concentrazione da incantesimo di oggetto come l'API", "zona": "flusso:concentrazione", "voce": "contratto", "copre": ["route:/char/:id/spells"]}
  it('la concentrazione da oggetto è riconosciuta e ha il nome', () => {
    const char = { concentrating_spell_id: null, spells: [], settings: { concentration_item_spell: { item_id: 3, name: 'Bacchetta' } } }
    expect(itemSpellConcentration(char as never)).toEqual({ item_id: 3, name: 'Bacchetta' })
    expect(isConcentrating(char as never)).toBe(true)
    expect(concentrationLabel(char as never)).toBe('Bacchetta')
  })

  // caccia: {"id": "CB-466", "fonte": "invariante: senza concentrazione in corso il frontend non ne mostra una", "zona": "flusso:concentrazione", "voce": "limiti", "copre": ["route:/char/:id/spells"]}
  it('senza concentrazione né nome non c\'è niente da mostrare', () => {
    const char = { concentrating_spell_id: null, spells: [], settings: {} }
    expect(isConcentrating(char as never)).toBe(false)
    expect(concentrationLabel(char as never)).toBeUndefined()
    expect(concentrationLabel({ ...char, concentrating_spell_id: 99 } as never)).toBeUndefined()
  })
})

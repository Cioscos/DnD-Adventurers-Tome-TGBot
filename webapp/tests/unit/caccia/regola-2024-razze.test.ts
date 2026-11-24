import { createElement } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '../utils/renderWithProviders'
import SpeciesStep from '@/pages/creation/SpeciesStep'
import species from '@/data/srd/species-2024.json'
import type { Species2024Entry } from '@/lib/species'
import { useUnitSettings } from '@/store/unitSettings'

vi.mock('react-i18next', async (orig) => ({
  ...((await orig()) as Record<string, unknown>), useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }),
}))

const specie = (key: string) => (species as unknown as Species2024Entry[]).find((e) => e.key === key)!

/** Il riquadro della specie scelta nella creazione 2024: il testo della riga «Velocità». */
function velocitaMostrata(key: string, options: Record<string, string>): string {
  useUnitSettings.setState({ system: 'imperial' })
  renderWithProviders(createElement(SpeciesStep, {
    choice: { race: null, sub: null }, onChoice: () => {}, freeText: '', onFreeText: () => {},
    edition: '2024', species24: { entry: specie(key), options }, onSpecies24: () => {},
  }))
  return screen.getByText(/character\.create\.species_speed/).textContent ?? ''
}

describe('caccia: regola 2024 razze', () => {
  // caccia: {"id": "CB-3516", "fonte": "2024 · Specie · Goliath, velocità 35 piedi (pag. 192) ed Elfo dei boschi, velocità 35 piedi (pag. 190)", "zona": "regola:2024/razze", "voce": "regola", "copre": ["carta:2024/races.md#Goliath / Goliath (pag. 192)", "carta:2024/races.md#Elfo dei boschi (lignaggio elfico) / Wood Elf (pag. 190)", "route:/"]}
  it.fails.each([
    ['2024_goliath', { giant: 'hill' }],
    ['2024_elf', { lineage: 'wood', spell_ability: 'wisdom', skill: 'survival' }],
  ])('la creazione mostra la velocità della specie scelta (%s): 35 piedi', (key, options) => {
    expect(velocitaMostrata(key, options)).toContain('35 ft')
  })
})

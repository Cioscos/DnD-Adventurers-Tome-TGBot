import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import FeatOptionsSheet from '@/components/character/FeatOptionsSheet'
import type { Ability, CharacterFull } from '@/types'

const { complete } = vi.hoisted(() => ({ complete: vi.fn() }))
vi.mock('@/api/client', () => ({ api: { feats: { complete } } }))
vi.mock('@/components/ui/Sheet', () => ({ default: (p: { children?: unknown }) => <div>{p.children as never}</div> }))
vi.mock('react-i18next', async (orig) => ({
  ...(await orig<typeof import('react-i18next')>()), useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }),
}))

describe('caccia: revisione del gruppo scelte', () => {
  // caccia: {"id": "CB-4793", "fonte": "2024 · Talenti · Maestro d'Armi / Weapon Master · pag. 209 (un'arma in cui si è competenti)", "zona": "regola:2024/talenti", "voce": "limiti", "copre": ["route:/char/:id/abilities"]}
  it('2024: Maestro d\'armi con un\'arma senza competenza dice perché la scelta è rifiutata', async () => {
    complete.mockRejectedValue({ detail: 'feat_weapon_not_proficient' })
    const mago = { id: 7, rules_edition: '2024', total_level: 4, classes: [], abilities: [], ability_scores: [], proficiency_bonus: 2, skills: {} }
    const talento = { id: 3, name: "Maestro d'armi", feature_key: 'feat.2024_weapon_master', feat_status: 'incomplete' }
    renderWithProviders(<FeatOptionsSheet char={mago as unknown as CharacterFull} ability={talento as unknown as Ability} open onClose={() => {}} />)
    await userEvent.selectOptions(screen.getByLabelText('character.feats.weapon'), 'greatsword')
    await userEvent.click(screen.getByText('character.feats.complete_confirm'))
    expect(await screen.findByText('character.feats.weapon_not_proficient')).toBeTruthy()
  })
})

import { describe, expect, it, vi } from 'vitest'
import { fireEvent, screen, within } from '@testing-library/react'
import { renderWithProviders } from '../utils/renderWithProviders'
import ClassSkillChoice from '@/components/ClassSkillChoice'
import FeatChoiceList from '@/components/character/FeatChoiceList'
import TomeReopenToggle from '@/components/character/TomeReopenToggle'
import { featsFor } from '@/lib/feats'
import type { CharacterFull } from '@/types'

const RANGER = ['animal_handling', 'athletics', 'insight', 'investigation', 'nature', 'perception', 'stealth', 'survival']

vi.mock('@/hooks/useClassProficiencies', () => ({
  useClassProficiencies: () => ({ data: { skills_from: RANGER, skills_count: 1 } }),
}))
vi.mock('react-i18next', async (orig) => ({
  ...(await orig<typeof import('react-i18next')>()), useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }),
}))

const bottone = (slug: string) => screen.queryByRole('button', { name: `character.skills.${slug}` })

/** Il talento con +1 scelto, con `caratteristica` già a 20: la caratteristica resta nel menu e si conferma. */
const scegliAlMassimo = (edizione: '2014' | '2024', talento: string, caratteristica: string) => {
  const onAbility = vi.fn()
  renderWithProviders(<FeatChoiceList items={featsFor(null, edizione, 'manual', 'it')} value={talento} onPick={() => {}}
    ability="" onAbility={onAbility} score={(a) => (a === caratteristica ? 20 : 12)} />)
  const menu = screen.getByRole('combobox')
  expect(within(menu).getAllByRole('option').map((o) => (o as HTMLOptionElement).value)).toContain(caratteristica)
  fireEvent.change(menu, { target: { value: caratteristica } })
  expect(onAbility).toHaveBeenCalledWith(caratteristica)
}

describe('caccia: correzioni del gruppo scelte', () => {
  // caccia: {"id": "CB-4113", "fonte": "2014 · Personalità e Background · Regole generali dei background: la stessa competenza da due fonti, se ne sceglie un'altra dello stesso tipo · pag. 125", "zona": "regola:2014/background", "voce": "limiti", "copre": ["carta:2014/backgrounds.md#Regole generali dei background (pag. 125)", "route:/char/:id/class"]}
  it('2014: le abilità già possedute non si scelgono, e con l\'elenco esaurito se ne sceglie un\'altra', () => {
    const { unmount } = renderWithProviders(
      <ClassSkillChoice edition="2014" className="ranger" asMulticlass value={[]} onChange={() => {}} takenSkills={['stealth']} />)
    expect(bottone('stealth')).toBeDisabled()
    expect(bottone('arcana')).toBeNull()  // restano sette abilità dell'elenco: solo quelle
    unmount()
    renderWithProviders(
      <ClassSkillChoice edition="2014" className="ranger" asMulticlass value={[]} onChange={() => {}} takenSkills={RANGER} />)
    expect(bottone('stealth')).toBeDisabled()
    expect(bottone('arcana')).toBeEnabled()
  })

  // caccia: {"id": "CB-4112", "fonte": "2014 · Warlock · Patto del Tomo / Pact of the Tome (Warlock 3) · pag. 116", "zona": "regola:2014/warlock", "voce": "edizioni", "copre": ["carta:2014/classes/warlock.md#Patto del Tomo / Pact of the Tome (Warlock 3, pag. 116)", "route:/char/:id/hp"]}
  it('2014: il riposo non offre di rifare le scelte del Libro delle Ombre (solo nel 2024)', () => {
    const tomo = (edizione: string) => ({ id: 7, rules_edition: edizione,
      abilities: [{ id: 5, feature_key: 'warlock.pact_of_the_tome', name: 'Patto del Tomo' }] }) as unknown as CharacterFull
    const { unmount } = renderWithProviders(<TomeReopenToggle char={tomo('2014')} value={false} onChange={() => {}} />)
    expect(screen.queryByTestId('tome-reopen')).toBeNull()
    unmount()
    renderWithProviders(<TomeReopenToggle char={tomo('2024')} value={false} onChange={() => {}} />)
    expect(screen.queryByTestId('tome-reopen')).not.toBeNull()
  })

  // caccia: {"id": "CB-4116", "fonte": "2014 · Talenti · Regole generali: «fino a un massimo di 20», il punteggio non supera 20 · pag. 165; Resiliente · pag. 170", "zona": "regola:2014/talenti", "voce": "limiti", "copre": ["carta:2014/feats.md#Regole generali (pag. 165)", "carta:2014/feats.md#Resiliente / Resilient (pag. 170)", "route:/char/:id/abilities"]}
  it('2014: un talento con +1 si sceglie anche con la caratteristica già a 20 (Resiliente su Costituzione)', () => {
    scegliAlMassimo('2014', 'resilient', 'constitution')
  })

  // caccia: {"id": "CB-4117", "fonte": "2024 · Talenti · Regole comuni: +1 a una caratteristica (max 20) · pag. 199; Attore · pag. 202", "zona": "regola:2024/talenti", "voce": "limiti", "copre": ["carta:2024/feats.md#Attore / Actor (pag. 202) - Generale (livello 4+, Carisma 13+)", "route:/char/:id/abilities"]}
  it('2024: un talento con +1 si sceglie anche con la caratteristica già a 20 (Attore con Carisma 20)', () => {
    scegliAlMassimo('2024', '2024_actor', 'charisma')
  })
})

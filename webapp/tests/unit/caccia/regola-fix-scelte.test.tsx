import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '../utils/renderWithProviders'
import ClassSkillChoice from '@/components/ClassSkillChoice'

const RANGER = ['animal_handling', 'athletics', 'insight', 'investigation', 'nature', 'perception', 'stealth', 'survival']

vi.mock('@/hooks/useClassProficiencies', () => ({
  useClassProficiencies: () => ({ data: { skills_from: RANGER, skills_count: 1 } }),
}))
vi.mock('react-i18next', async (orig) => ({
  ...(await orig<typeof import('react-i18next')>()), useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }),
}))

const bottone = (slug: string) => screen.queryByRole('button', { name: `character.skills.${slug}` })

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
})

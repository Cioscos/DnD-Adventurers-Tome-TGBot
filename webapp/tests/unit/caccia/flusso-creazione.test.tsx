import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import CharacterSelect from '@/pages/CharacterSelect'
import { background24Payload, creationExtras, increasesValid, type Background2024Choice } from '@/lib/species'

const { create } = vi.hoisted(() => ({ create: vi.fn() }))
vi.mock('@/api/client', () => ({
  api: { characters: { list: vi.fn().mockResolvedValue([]), create }, sessions: { me: vi.fn().mockResolvedValue(null) } },
  ApiError: class ApiError extends Error {},
}))
vi.mock('react-router-dom', async (orig) => ({ ...((await orig()) as Record<string, unknown>), useNavigate: () => vi.fn() }))
vi.mock('react-i18next', async (orig) => ({
  ...((await orig()) as Record<string, unknown>), useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }),
}))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }), telegramConfirm: vi.fn() }))
vi.mock('@/hooks/useClassProficiencies', () => ({
  useClassProficiencies: (_e: string, cls: string | null) => ({
    isLoading: false, data: cls ? { skills_count: 2, skills_from: ['history', 'insight', 'medicine', 'religion'] } : undefined,
  }),
}))
vi.mock('@/pages/creation/AbilityScoresStep', async (orig) => ({ ...((await orig()) as Record<string, unknown>), default: () => null }))
vi.mock('@/pages/creation/EquipmentStep', async (orig) => ({ ...((await orig()) as Record<string, unknown>), default: () => null }))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children as never) : null) }
})

describe('caccia: creazione', () => {
  // caccia: {"id": "CB-653", "fonte": "2024 · Background · pag. 177 (+2/+1 oppure +1/+1/+1 su tre caratteristiche)", "zona": "flusso:creazione", "voce": "limiti", "copre": ["route:/"]}
  it('gli aumenti del background validi sono solo +2/+1 e +1/+1/+1', () => {
    expect(increasesValid({ strength: 2, dexterity: 1 })).toBe(true)
    expect(increasesValid({ strength: 1, dexterity: 1, wisdom: 1 })).toBe(true)
    expect(increasesValid({ strength: 2, dexterity: 1, wisdom: 0 })).toBe(true)
    expect(increasesValid({ strength: 2, dexterity: 2 })).toBe(false)
    expect(increasesValid({ strength: 3 })).toBe(false)
    expect(increasesValid({ strength: 2 })).toBe(false)
    expect(increasesValid({ strength: 1, dexterity: 1 })).toBe(false)
    expect(increasesValid({ strength: 2, dexterity: 1, wisdom: 1 })).toBe(false)
    expect(increasesValid({})).toBe(false)
  })

  // caccia: {"id": "CB-654", "fonte": "invariante: il corpo inviato al server contiene solo ciò che il giocatore ha scelto", "zona": "flusso:creazione", "voce": "contratto", "copre": ["route:/"]}
  it('il corpo della creazione non manda aumenti a zero né punteggi se il passo è saltato', () => {
    const scelta = {
      entry: { key: 'soldier', tool: ['dice_set', 'chess_set'] }, increases: { strength: 2, dexterity: 1, wisdom: 0 }, tool: 'dice_set', equipment: 'gold',
    } as unknown as Background2024Choice
    expect(background24Payload(scelta)).toEqual({ key: 'soldier', increases: { strength: 2, dexterity: 1 }, tool: 'dice_set', equipment: 'gold' })
    expect(background24Payload({ ...scelta, tool: null })).not.toHaveProperty('tool')
    const punteggi = { strength: 15 }
    expect(creationExtras({ scores: punteggi, skipped: true, species: null, skills: [] })).toEqual({})
    expect(creationExtras({ scores: punteggi, skipped: false, species: null, skills: ['stealth', 'arcana'] }))
      .toEqual({ ability_scores: punteggi, skills: { stealth: true, arcana: true } })
  })

  // caccia: {"id": "CB-768", "fonte": "decisione D-006 (un'abilità del background non si sceglie per la classe) e D-008 (nel 2024 il background viene prima della classe)", "zona": "flusso:creazione", "voce": "edizioni", "copre": ["route:/"]}
  it('2024: le abilità del background non si possono scegliere per la classe, nemmeno cambiandolo dopo', async () => {
    const user = userEvent.setup()
    const clic = (name: string | RegExp) => user.click(screen.getByRole('button', { name }))
    const avanti = () => screen.getByRole('button', { name: 'common.next →' })
    renderWithProviders(<CharacterSelect />)
    await user.click(await screen.findByRole('button', { name: /character.select.new/ }))
    await user.type(screen.getByPlaceholderText('character.create.name_placeholder'), 'Lia')
    await clic('character.settings.rules_edition.2024')
    await user.click(avanti())
    await clic(/character.create.background_pick/)
    await user.click(await screen.findByText('Marinaio')) // acrobatics, perception
    await user.click(avanti())
    await user.click(avanti()) // specie libera
    await clic(/dnd.classes.cleric/)
    await clic('character.skills.insight')
    await clic('character.skills.history')
    expect(avanti()).toBeEnabled()
    await clic('common.back')
    await clic('common.back')
    await clic(/Marinaio/)
    await user.click(await screen.findByText('Accolito')) // Intuizione e Religione
    await user.click(avanti())
    await user.click(avanti())
    expect(screen.getByRole('button', { name: 'character.skills.insight' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'character.skills.religion' })).toBeDisabled()
    expect(avanti()).toBeDisabled() // la scelta caduta va rifatta
    await clic('character.skills.medicine')
    expect(avanti()).toBeEnabled()
  })

  // caccia: {"id": "CB-772", "fonte": "2014 · Background · competenza da due fonti: se ne sceglie un'altra; decisione D-012", "zona": "flusso:creazione", "voce": "interazione", "copre": ["route:/"]}
  it('2014: il background viene prima della classe, le sue abilità non si scelgono e «Salta» lo conserva', async () => {
    create.mockResolvedValue({ id: 9 })
    const user = userEvent.setup()
    const clic = (name: string | RegExp) => user.click(screen.getByRole('button', { name }))
    const avanti = () => screen.getByRole('button', { name: 'common.next →' })
    renderWithProviders(<CharacterSelect />)
    await user.click(await screen.findByRole('button', { name: /character.select.new/ }))
    await user.type(screen.getByPlaceholderText('character.create.name_placeholder'), 'Lia')
    await user.click(avanti())
    await user.click(avanti())
    await clic(/dnd.classes.cleric/)
    await clic('character.skills.insight')
    await clic('character.skills.history')
    await clic('common.back') // il background scelto dopo fa cadere l'abilità doppia
    await clic(/character.create.background_pick/)
    await user.click(await screen.findByText('Accolito'))
    await user.click(avanti())
    expect(screen.getByRole('button', { name: 'character.skills.insight' })).toBeDisabled()
    expect(avanti()).toBeDisabled()
    await clic('character.skills.medicine')
    await user.click(avanti())
    await user.click(avanti())
    await clic('character.create.scores_skip')
    await clic('character.create.equipment_skip')
    await clic('character.create.identity_skip')
    expect(create.mock.calls[0][1].skill_choices).toEqual(['history', 'medicine'])
    expect(create.mock.calls[0][2]).toEqual({ background: 'Accolito' })
    expect(create.mock.calls[0][3].skills).toEqual({ insight: true, religion: true })
  })
})

import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import Experience from '@/pages/Experience'
import SaveRollSheet from '@/components/SaveRollSheet'

const { getChar, updateXP, rollSave } = vi.hoisted(() => ({ getChar: vi.fn(), updateXP: vi.fn(), rollSave: vi.fn() }))

vi.mock('@/api/client', () => ({
  api: { characters: { get: getChar, updateXP, rollOptions: vi.fn(async () => []), pendingSaves: { roll: rollSave } } },
  ApiError: class ApiError extends Error {},
}))
vi.mock('@/hooks/useD20Roll', () => ({ useD20Roll: () => async () => undefined, d20Arg: () => undefined }))
vi.mock('react-router-dom', async (orig) => ({ ...(await orig<typeof import('react-router-dom')>()), useParams: () => ({ id: '5' }) }))
vi.mock('react-i18next', async (orig) => ({
  ...(await orig<typeof import('react-i18next')>()), useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }),
}))
vi.mock('@/components/Layout', () => ({ default: (p: { children?: React.ReactNode }) => <div>{p.children}</div> }))
vi.mock('@/pages/multiclass/LevelUpModal', () => ({ default: () => null }))

afterEach(() => { getChar.mockReset(); updateXP.mockReset() })

describe('caccia: decisioni', () => {
  // caccia: {"id": "CB-4605", "fonte": "decisione D-028 (tests/caccia/decisioni.md): la scheda mostra il livello più alto fra classe e PE, la soglia successiva è di quel livello", "zona": "regola:2024/generali", "voce": "interazione", "copre": ["carta:2024/general.md#Experience Points (Punti Esperienza) (pag. 366-367)", "route:/char/:id/xp"]}
  it('un guerriero di 5° con 0 PE è mostrato di 5° e il prossimo livello è il 6°', async () => {
    const pg = { id: 5, experience_points: 0, abilities: [], rules_edition: '2024', classes: [{ id: 9, class_name: 'fighter', level: 5 }] }
    getChar.mockResolvedValue(pg)
    updateXP.mockResolvedValue(pg)
    renderWithProviders(<Experience />)
    expect(await screen.findByText('5')).toBeInTheDocument()
    expect(screen.getByText('0%')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /level_up_to/ }))
    await waitFor(() => expect(updateXP).toHaveBeenCalledWith(5, { add: undefined, set: 14000 }))
  })

  // caccia: {"id": "CB-4616", "fonte": "decisione D-040 (tests/caccia/decisioni.md): Collera della Natura 2014, il bersaglio sceglie Forza o Destrezza al tiro", "zona": "regola:2014/paladin", "voce": "interazione", "copre": ["carta:2014/classes/paladin.md#Collera della Natura / Nature's Wrath (Incanalare Divinità, Giuramento degli Antichi, Paladino 3, pag. 100)", "POST /characters/{char_id}/pending-saves/{psid}/roll"]}
  it('il bersaglio sceglie la caratteristica del tiro salvezza', async () => {
    getChar.mockResolvedValue({ id: 5, rules_edition: '2014' })
    const save = { id: 1, slug: 'restrained', ability: 'strength', alt_ability: 'dexterity', dc: 14, status: 'pending' as const, created_at: '' }
    rollSave.mockResolvedValue({ save: { ...save, ability: 'dexterity', status: 'passed' }, roll: { die: 11, bonus: 3, total: 14 }, passed: true, condition_removed: true })
    renderWithProviders(<SaveRollSheet charId={5} saves={[save]} onClose={() => {}} />)
    const user = userEvent.setup({ pointerEventsCheck: 0 })  // il foglio entra con un'animazione che jsdom non completa
    await user.click(screen.getByRole('radio', { name: 'character.stats.dexterity' }))
    await user.click(screen.getByText('pendingSaves.roll'))
    await waitFor(() => expect(rollSave).toHaveBeenCalledWith(5, 1, undefined, false, 'dexterity'))
  })
})

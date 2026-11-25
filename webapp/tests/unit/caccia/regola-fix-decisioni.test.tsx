import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import Experience from '@/pages/Experience'
import SaveRollSheet from '@/components/SaveRollSheet'
import Extras from '@/pages/Extras'
import Spells from '@/pages/Spells'
import CharacterSelect from '@/pages/CharacterSelect'
import DeathSaveResultDialog from '@/pages/hp/DeathSaveResultDialog'
import Settings from '@/pages/Settings'
import SpellHealingSheet from '@/pages/spells/SpellHealingSheet'
import { ApiError } from '@/api/client'
import type { Spell } from '@/types'

const { getChar, updateXP, rollSave, createComp, useSpell, rollHealing, updateSpell } = vi.hoisted(() => ({
  getChar: vi.fn(), updateXP: vi.fn(), rollSave: vi.fn(), createComp: vi.fn(), useSpell: vi.fn(), rollHealing: vi.fn(), updateSpell: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  api: {
    characters: { get: getChar, updateXP, rollOptions: vi.fn(async () => []), pendingSaves: { roll: rollSave }, sessionAllies: vi.fn(async () => [{ id: 9, name: 'Brann' }]), list: vi.fn(async () => []) },
    sessions: { me: vi.fn(async () => null) }, history: { retentionPreview: vi.fn(async () => ({ total: 0, would_purge_events: 0, would_purge_days: 0 })) },
    companions: { list: vi.fn(async () => []), create: createComp }, spells: { use: useSpell, rollHealing, update: updateSpell },
  },
  ApiError: class ApiError extends Error { constructor(public status: number, public detail: unknown) { super('x') } },
}))
vi.mock('@/dice/useDiceAnimation', () => ({ useDiceAnimation: () => ({ playAndCollect: vi.fn() }) }))
vi.mock('@/hooks/useD20Roll', () => ({ useD20Roll: () => async () => undefined, d20Arg: () => undefined }))
vi.mock('react-router-dom', async (orig) => ({ ...(await orig<typeof import('react-router-dom')>()), useParams: () => ({ id: '5' }) }))
vi.mock('react-i18next', async (orig) => ({
  ...(await orig<typeof import('react-i18next')>()), useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }),
}))
vi.mock('@/components/Layout', () => ({ default: (p: { children?: React.ReactNode }) => <div>{p.children}</div> }))
vi.mock('@/dice/packs/dicePackContext', () => ({ useDicePack: () => ({ loading: false, error: null }) }))
vi.mock('@/dice/packs/manifest', () => ({ loadManifest: async () => ({ name: 'x' }) }))
vi.mock('@/pages/multiclass/LevelUpModal', () => ({ default: () => null }))
vi.mock('@/pages/extras/CompanionForm', () => ({ default: (p: { onSubmit: (b: object) => void }) => <button onClick={() => p.onSubmit({ name: 'Orso' })}>invia</button> }))

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

  // caccia: {"id": "CB-4618", "fonte": "decisione D-042 (tests/caccia/decisioni.md): la bestia del ranger 2014 fuori regola si aggiunge solo confermando; pag. 106", "zona": "regola:2014/ranger", "voce": "interazione", "copre": ["carta:2014/classes/ranger.md#Compagno del Ranger / Ranger's Companion (Signore delle Bestie 3, pag. 106)", "route:/char/:id/extras"]}
  it('la bestia fuori regola chiede conferma e la conferma la aggiunge', async () => {
    getChar.mockResolvedValue({ id: 5, classes: [], abilities: [], spell_slots: [], rules_edition: '2014' })
    createComp.mockRejectedValueOnce(new ApiError(409, { code: 'beast_not_allowed' })).mockResolvedValue({})
    renderWithProviders(<Extras />)
    const user = userEvent.setup({ pointerEventsCheck: 0 })
    await user.click(await screen.findByText('character.extras.add'))
    await user.click(screen.getByText('invia'))
    await user.click(await screen.findByText('character.extras.beast.not_allowed_confirm'))
    await waitFor(() => expect(createComp).toHaveBeenLastCalledWith(5, { name: 'Orso', force: true }))
  })

  // caccia: {"id": "CB-4641", "fonte": "decisione D-038 (tests/caccia/decisioni.md): quantità scelta per ogni bersaglio, somma massima 700; 2014 pag. 240, 2024 pag. 296", "zona": "regola:2024/incantesimi-G-L", "voce": "interazione", "copre": ["carta:2014/spells.md#Guarigione di Massa", "carta:2024/spells.md#Guarigione di Massa", "POST /characters/{char_id}/spells/{spell_id}/roll_healing"]}
  it('Guarigione di Massa chiede i PF di ogni bersaglio e non si lancia oltre i 700', async () => {
    useSpell.mockResolvedValue({ id: 5 })
    rollHealing.mockResolvedValue({ total: 700, breakdown: '', healed: 100, healed_allies: [], self_healed: 0 })
    const spell = { id: 3, name: 'Guarigione di Massa', level: 9, srd_index: 'mass-heal', is_healing: true } as Spell
    renderWithProviders(<SpellHealingSheet charId={5} spell={spell} slotLevel={9} onClose={() => {}} />)
    await userEvent.click(await screen.findByRole('switch', { name: 'Brann' }))
    const lancia = screen.getByRole('button', { name: /roll_button/ })
    const [io, brann] = screen.getAllByRole('textbox')
    await userEvent.type(io, '200')
    expect(lancia).toBeDisabled()  // manca la parte di Brann
    await userEvent.type(brann, '501')
    expect(screen.getByText('character.spells.roll_healing.pool_over')).toBeInTheDocument()
    expect(lancia).toBeDisabled()
    await userEvent.clear(brann)
    await userEvent.type(brann, '500')
    await userEvent.click(lancia)
    await waitFor(() => expect(rollHealing).toHaveBeenCalledWith(5, 3, expect.objectContaining({ target_character_ids: [9], amounts: { 5: 200, 9: 500 } })))
  })

  // caccia: {"id": "CB-4642", "fonte": "decisione D-035 (tests/caccia/decisioni.md): il talento non ripetibile del background non è sceglibile per Versatile e cambiando background la scelta in conflitto si toglie; 2024 · Umano · pag. 194", "zona": "regola:2024/razze", "voce": "interazione", "copre": ["carta:2024/races.md#Umano / Human (pag. 194)", "route:/"]}
  it('Versatile non offre il talento non ripetibile del background e lo perde cambiando background', async () => {
    renderWithProviders(<CharacterSelect />)
    const user = userEvent.setup({ pointerEventsCheck: 0 })
    const clic = async (name: string | RegExp) => user.click(await screen.findByRole('button', { name }))
    const background = async (attuale: RegExp, nuovo: string) => { await clic(attuale); await user.click(await screen.findByText(nuovo)) }
    await clic(/character.select.new/)
    await user.type(await screen.findByPlaceholderText('character.create.name_placeholder'), 'Lia')
    await clic('character.settings.rules_edition.2024')
    await clic('common.next →')
    await background(/background_pick/, 'Criminale') // Allerta
    await clic('common.next →')
    await clic(/species_pick/)
    await user.click(await screen.findByText('Umano'))
    expect(await screen.findByRole('button', { name: 'Allerta' })).toBeDisabled()
    await clic('Abile') // ripetibile: sempre libero
    await clic('Fortunato')
    await clic('common.back')
    await background(/Criminale/, 'Viandante') // Fortunato
    await clic('common.next →')
    const fortunato = await screen.findByRole('button', { name: 'Fortunato' })
    expect(fortunato).toBeDisabled()
    expect(fortunato).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('button', { name: 'Allerta' })).toBeEnabled()
  })

  // caccia: {"id": "CB-4648", "fonte": "decisione D-020 (tests/caccia/decisioni.md): il cambio di un preparato lontano dal riposo lungo si conferma", "zona": "regola:2024/wizard", "voce": "interazione", "copre": ["carta:2024/classes/wizard.md#Incantesimi / Spellcasting (Mago 1, pag. 165)", "route:/char/:id/spells"]}
  it('preparare un incantesimo lontano dal riposo lungo chiede conferma, poi ripete il cambio confermato', async () => {
    const bless = { id: 101, name: 'Benedizione', level: 1, is_prepared: false, is_pinned: false, is_concentration: false, is_ritual: false }
    getChar.mockResolvedValue({
      id: 5, rules_edition: '2014', settings: {}, classes: [{ id: 1, class_name: 'cleric', level: 5 }], abilities: [], items: [], spell_slots: [], spells: [bless],
      spellcasting: { has_preparing_class: true, prepared_cap: 8, prepared_count: 0, cap_mode: 'auto', limits: [], casters: [] },
    })
    vi.stubGlobal('IntersectionObserver', class { observe() {} unobserve() {} disconnect() {} })
    updateSpell.mockRejectedValueOnce(new ApiError(409, { code: 'change_after_long_rest' })).mockResolvedValueOnce({})
    renderWithProviders(<Spells />)
    const user = userEvent.setup({ pointerEventsCheck: 0 })
    await user.click(await screen.findByTitle('character.spells.not_prepared'))
    await user.click(await screen.findByText('character.spells.off_rest_confirm'))
    await waitFor(() => expect(updateSpell).toHaveBeenLastCalledWith(5, 101, { is_prepared: true }, true))
  })

  // caccia: {"id": "CB-4884", "fonte": "decisione D-050 (tests/caccia/decisioni.md): la Variante dell'ingombro non ha effetto nel 2024, l'interruttore non si mostra; 2014 · Variante: Ingombro · pag. 176", "zona": "regola:2024/generali", "voce": "edizioni", "copre": ["carta:2014/general.md#Forza / Strength (pag. 175-176)", "route:/char/:id/settings"]}
  it.each([['2014', true], ['2024', false]])('interruttore della Variante dell\'ingombro nel %s: %s', async (rules_edition, visibile) => {
    getChar.mockResolvedValue({ id: 5, name: 'Lia', settings: {}, spellcasting: null, rules_edition })
    renderWithProviders(<Settings />)
    await screen.findByText('character.settings.coin_weight_label')
    expect(screen.queryByText('character.settings.encumbrance_variant_label') !== null).toBe(visibile)
  })

  // caccia: {"id": "CB-4888", "fonte": "decisione D-052 (tests/caccia/decisioni.md): il dettaglio del TS contro la morte mostra la competenza; 2014 · Monaco · Anima Adamantina · pag. 92", "zona": "regola:2014/monk", "voce": "regola", "copre": ["carta:2014/classes/monk.md#Anima Adamantina / Diamond Soul (Monaco 14, pag. 92)", "route:/char/:id/hp"]}
  it.each([['success', 6, '11', true], ['nat1', 1, '1', true], ['failure', 6, '6', false]] as const)('dettaglio del TS contro la morte: %s con %i mostra %s', (outcome, die, grande, conBonus) => {
    renderWithProviders(<DeathSaveResultDialog onClose={() => {}} result={{
      die, outcome, bonus: conBonus ? 5 : 0, successes: 1, failures: 0, stable: false, revived: false, current_hp: 0 }} />)
    expect(screen.getByText(grande)).toBeInTheDocument()
    expect(screen.queryByText(`d20 (${die}) +5`) !== null).toBe(conBonus)
  })
})

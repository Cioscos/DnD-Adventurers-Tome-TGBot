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


// --- Giro 3 ---------------------------------------------------------------------------------------------------------
import { useState } from 'react'
import races from '@/data/srd/races.json'
import { buildSpecies, type RaceEntry } from '@/lib/species'
import { STANDARD_ARRAY, arrayScores, assignFromArray, defaultScores, pointBuyCost, scoresValid, type Scores } from '@/lib/pointBuy'

const { playAndCollect } = vi.hoisted(() => ({ playAndCollect: vi.fn() }))
vi.mock('@/dice/useDiceAnimation', () => ({ useDiceAnimation: () => ({ playAndCollect, isPlaying: false }) }))

async function realScoresStep() {
  return (await vi.importActual<typeof import('@/pages/creation/AbilityScoresStep')>('@/pages/creation/AbilityScoresStep')).default
}

describe('caccia: creazione, giro 3', () => {
  // caccia: {"id": "CB-1387", "fonte": "2024 · Background · pag. 177 (massimo 20 dopo gli aumenti) e Punteggi di caratteristica: nessun punteggio oltre 20", "zona": "flusso:creazione", "voce": "limiti", "copre": ["route:/"]}
  it('punteggi manuali: con +2 del background il totale mostrato non supera 20', async () => {
    const Step = await realScoresStep()
    function Harness() {
      const [s, setS] = useState<Scores>(defaultScores(10))
      return <Step mode="manual" scores={s} pool={[]} bonuses={{ strength: 2, dexterity: 1 }} onChange={(_m, sc) => setS(sc)} />
    }
    const user = userEvent.setup()
    renderWithProviders(<Harness />)
    const piu = screen.getAllByLabelText('+1')
    for (let i = 0; i < 12; i++) await user.click(piu[0])
    const totale = Number(screen.getAllByRole('listitem')[0].textContent?.match(/\d+/)?.[0])
    expect(totale).toBeLessThanOrEqual(20)
  })

  // caccia: {"id": "CB-1519", "fonte": "2024 · Background · pag. 177 (massimo 20 dopo gli aumenti)", "zona": "flusso:creazione", "voce": "limiti", "copre": ["route:/"]}
  it('punteggi tirati: un totale oltre 20 si vede e dice perché', async () => {
    const Step = await realScoresStep()
    const s = { ...defaultScores(10), strength: 18 }
    const { rerender } = renderWithProviders(<Step mode="roll" scores={s} pool={[18]} bonuses={{ str: 3 }} onChange={vi.fn()} />)
    expect(screen.getByText('character.create.score_over_max')).toBeTruthy()
    rerender(<Step mode="roll" scores={s} pool={[18]} bonuses={{ str: 2 }} onChange={vi.fn()} />)
    expect(screen.queryByText('character.create.score_over_max')).toBeNull()
  })

  // caccia: {"id": "CB-1388", "fonte": "2014 · Punteggi di caratteristica · pag. 13: acquisto a punti (27 punti, punteggi da 8 a 15) e matrice standard 15, 14, 13, 12, 10, 8", "zona": "flusso:creazione", "voce": "limiti", "copre": ["route:/"]}
  it('acquisto a punti: costi, budget di 27 e scambio nella matrice standard', () => {
    expect([8, 9, 10, 11, 12, 13, 14, 15].map(pointBuyCost)).toEqual([0, 1, 2, 3, 4, 5, 7, 9])
    expect(pointBuyCost(7)).toBeNaN()
    expect(pointBuyCost(16)).toBeNaN()
    const s = (v: number[]) => arrayScores(v)
    expect(scoresValid('pointbuy', s([15, 15, 15, 8, 8, 8]))).toBe(true)
    expect(scoresValid('pointbuy', s([15, 15, 14, 10, 8, 8]))).toBe(true)
    expect(scoresValid('pointbuy', s([15, 15, 14, 11, 8, 8]))).toBe(false)
    expect(scoresValid('pointbuy', s([16, 8, 8, 8, 8, 8]))).toBe(false)
    expect(scoresValid('pointbuy', defaultScores(8))).toBe(true)
    expect([...STANDARD_ARRAY].sort((a, b) => b - a)).toEqual([15, 14, 13, 12, 10, 8])
    const scambio = assignFromArray(arrayScores(), 'charisma', 15)
    expect(Object.values(scambio).sort((a, b) => b - a)).toEqual([15, 14, 13, 12, 10, 8])
    expect(scambio).toMatchObject({ charisma: 15, strength: 8 })
  })

  // caccia: {"id": "CB-1389", "fonte": "2014 · Punteggi di caratteristica · pag. 13: 4d6 scartando il più basso, sei valori assegnati alle sei caratteristiche", "zona": "flusso:creazione", "voce": "normale", "copre": ["route:/"]}
  it('tiro 4d6: scarta il dado più basso e assegna i sei valori in ordine decrescente', async () => {
    const Step = await realScoresStep()
    const gruppi = [[6, 6, 6, 1], [1, 1, 1, 1], [5, 4, 3, 2], [6, 5, 5, 5], [2, 2, 3, 3], [6, 1, 1, 6]]
    playAndCollect.mockResolvedValue(gruppi.flatMap((g, groupIndex) => g.map((value) => ({ groupIndex, kind: 'd6', value }))))
    const onChange = vi.fn()
    const user = userEvent.setup()
    renderWithProviders(<Step mode="roll" scores={defaultScores(10)} pool={[]} bonuses={{}} onChange={onChange} />)
    await user.click(screen.getByRole('button', { name: 'character.create.roll_4d6' }))
    await vi.waitFor(() => expect(onChange).toHaveBeenCalled())
    expect(onChange).toHaveBeenCalledWith('roll',
      { strength: 18, dexterity: 16, constitution: 13, intelligence: 12, wisdom: 8, charisma: 3 }, [18, 16, 13, 12, 8, 3])
  })

  // caccia: {"id": "CB-1390", "fonte": "2014 · Razze · pag. 17-43: velocità, scurovisione e aumenti di caratteristica di razza e sottorazza", "zona": "flusso:creazione", "voce": "regola", "copre": ["route:/"]}
  it('razze 2014: il payload di creazione ha velocità, sensi e aumenti del manuale', () => {
    const atteso: Record<string, [string | null, number, number | null, Record<string, number>, string[]]> = {
      dragonborn: [null, 30, null, { str: 2, cha: 1 }, ['Comune', 'Draconico']],
      dwarf: [null, 25, 60, { con: 2 }, ['Comune', 'Nanico']],
      'hill-dwarf': ['dwarf', 25, 60, { con: 2, wis: 1 }, ['Comune', 'Nanico']],
      elf: [null, 30, 60, { dex: 2 }, ['Comune', 'Elfico']],
      'high-elf': ['elf', 30, 60, { dex: 2, int: 1 }, ['Comune', 'Elfico']],
      gnome: [null, 25, 60, { int: 2 }, ['Comune', 'Gnomesco']],
      'rock-gnome': ['gnome', 25, 60, { int: 2, con: 1 }, ['Comune', 'Gnomesco']],
      'half-orc': [null, 30, 60, { str: 2, con: 1 }, ['Comune', 'Orchesco']],
      halfling: [null, 25, null, { dex: 2 }, ['Comune', 'Halfling']],
      'lightfoot-halfling': ['halfling', 25, null, { dex: 2, cha: 1 }, ['Comune', 'Halfling']],
      human: [null, 30, null, { str: 1, dex: 1, con: 1, int: 1, wis: 1, cha: 1 }, ['Comune']],
      tiefling: [null, 30, 60, { int: 1, cha: 2 }, ['Comune', 'Infernale']],
    }
    const razze = (races as unknown as { items: RaceEntry[] }).items
    for (const [indice, [padre, velocita, buio, aumenti, lingue]] of Object.entries(atteso)) {
      const race = razze.find((r) => r.index === (padre ?? indice))!
      const sub = padre ? race.subraces.find((s) => s.index === indice)! : null
      const p = buildSpecies(race, sub, 'it')
      expect([indice, p.speed_ft, p.senses.find((s) => s.type === 'darkvision')?.range_ft ?? null, p.ability_bonuses, p.languages])
        .toEqual([indice, velocita, buio, aumenti, lingue])
    }
    const note = (i: string) => Object.keys(buildSpecies(razze.find((r) => r.index === i)!, null, 'it').roll_notes)
    expect([note('dwarf'), note('elf'), note('halfling')]).toEqual([['save.constitution'], ['save.wisdom'], ['save.wisdom']])
  })

  // caccia: {"id": "CB-1391", "fonte": "2024 · Background · pag. 177 e Talenti d'Origine: col background scelto il talento d'Origine è il suo e il passo del talento non compare", "zona": "flusso:creazione", "voce": "interazione", "copre": ["route:/"]}
  it('2024: il passo del talento compare solo senza background', async () => {
    const user = userEvent.setup()
    const avanti = () => screen.getByRole('button', { name: 'common.next →' })
    renderWithProviders(<CharacterSelect />)
    await user.click(await screen.findByRole('button', { name: /character.select.new/ }))
    await user.type(screen.getByPlaceholderText('character.create.name_placeholder'), 'Tia')
    await user.click(screen.getByRole('button', { name: 'character.settings.rules_edition.2024' }))
    await user.click(avanti())
    await user.click(avanti()) // background saltato
    expect(screen.getByText('character.feats.origin_hint')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'common.back' }))
    await user.click(screen.getByRole('button', { name: /character.create.background_pick/ }))
    await user.click(await screen.findByText('Marinaio'))
    await user.click(avanti())
    expect(screen.queryByText('character.feats.origin_hint')).not.toBeInTheDocument()
    expect(screen.getByText('character.create.species_hint')).toBeInTheDocument()
  })
})

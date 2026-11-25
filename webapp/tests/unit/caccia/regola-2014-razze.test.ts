import { createElement } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import CharacterSelect from '@/pages/CharacterSelect'
import races from '@/data/srd/races.json'
import { buildSpecies, type RaceEntry } from '@/lib/species'

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
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children as never) : null) }
})

const razza = (i: string) => (races as unknown as { items: RaceEntry[] }).items.find((r) => r.index === i)!

/** Chiavi e valori testuali (minuscoli) di tutto ciò che il wizard manda al server: le descrizioni sono frasi intere. */
function voci(x: unknown): string[] {
  if (typeof x === 'string') return [x.toLowerCase()]
  if (Array.isArray(x)) return x.flatMap(voci)
  if (x && typeof x === 'object') return Object.entries(x).flatMap(([k, v]) => [k.toLowerCase(), ...voci(v)])
  return []
}

/** Creazione 2014 dal wizard (chierico, razza dal catalogo, tutto il resto saltato): gli argomenti passati a create. */
async function creaConRazza(nome: string, sottorazza: string | null): Promise<unknown[]> {
  create.mockReset()
  create.mockResolvedValue({ id: 9 })
  const user = userEvent.setup()
  const clic = (name: string | RegExp) => user.click(screen.getByRole('button', { name }))
  const avanti = () => clic('common.next →')
  renderWithProviders(createElement(CharacterSelect))
  await user.click(await screen.findByRole('button', { name: /character.select.new/ }))
  await user.type(screen.getByPlaceholderText('character.create.name_placeholder'), 'Lia')
  await avanti()
  await avanti() // nessun background
  await clic(/character.create.species_pick/)
  await user.click(await screen.findByText(nome))
  // 2014 pag. 17: la sottorazza è obbligatoria dove la razza ne ha; senza una del catalogo si sceglie «altra», a mano
  const altra = screen.queryByRole('button', { name: 'character.create.subrace_other' })
  if (sottorazza) await clic(sottorazza)
  else if (altra) await user.click(altra)
  await avanti()
  await clic(/dnd.classes.cleric/) // la classe viene dopo la specie (CB-4555)
  await clic('character.skills.history')
  await clic('character.skills.medicine')
  await avanti()
  await clic('character.create.scores_skip')
  await clic('character.create.equipment_skip')
  await clic('character.create.identity_skip')
  expect(create).toHaveBeenCalledTimes(1)
  expect(voci(create.mock.calls[0])).toContain((sottorazza ?? nome).toLowerCase()) // la razza scelta è arrivata
  return create.mock.calls[0]
}

describe('caccia: regola 2014 razze', () => {
  // caccia: {"id": "CB-3067", "fonte": "2014 · Razze · Elfo, Sensi Acuti (pag. 20) e Mezzorco, Minaccioso (pag. 41): competenza in un'abilità fissa", "zona": "regola:2014/razze", "voce": "regola", "copre": ["carta:2014/races.md#Elfo / Elf - tratti base (pag. 20)", "carta:2014/races.md#Mezzorco / Half-Orc (pag. 41)", "route:/"]}
  it.each([
    ['Elfo', null, 'perception'],
    ['Mezzorco', null, 'intimidation'],
  ])('%s (%s): la creazione dà la competenza razziale in %s', async (nome, sotto, abilita) => {
    expect(voci(await creaConRazza(nome, sotto))).toContain(abilita)
  })

  // caccia: {"id": "CB-3068", "fonte": "2014 · Razze · Nano, Resilienza Nanica (pag. 28) e Tiefling, Resistenza Infernale (pag. 43): resistenza a un tipo di danno", "zona": "regola:2014/razze", "voce": "regola", "copre": ["carta:2014/races.md#Nano / Dwarf - tratti base (pag. 28)", "carta:2014/races.md#Tiefling / Tiefling (pag. 43)", "route:/"]}
  it.each([
    ['Nano', null, 'poison'],
    ['Tiefling', null, 'fire'],
  ])('%s (%s): la creazione dà la resistenza razziale ai danni da %s', async (nome, sotto, danno) => {
    expect(voci(await creaConRazza(nome, sotto))).toContain(danno)
  })

  // caccia: {"id": "CB-3069", "fonte": "2014 · Razze · Elfo Alto, Addestramento nelle Armi Elfiche (pag. 21); Nano, Addestramento da Combattimento Nanico (pag. 28); Gnomo delle Rocce, Inventore (pag. 37)", "zona": "regola:2014/razze", "voce": "regola", "copre": ["carta:2014/races.md#Elfo Alto / High Elf (pag. 21)", "carta:2014/races.md#Nano / Dwarf - tratti base (pag. 28)", "carta:2014/races.md#Gnomo delle Rocce / Rock Gnome (pag. 37)", "route:/"]}
  it.each([
    ['Elfo', 'Elfo alto', [['longsword', 'spada lunga'], ['shortsword', 'spada corta'], ['shortbow', 'arco corto'], ['longbow', 'arco lungo']]],
    ['Nano', null, [['battleaxe', 'ascia da battaglia'], ['handaxe', 'accetta'], ['light_hammer', 'light hammer', 'martello leggero'],
      ['warhammer', 'martello da guerra']]],
    ['Gnomo', 'Gnomo delle rocce', [['tinkers_tools', "tinker's tools", 'strumenti da inventore']]],
  ])('%s (%s): la creazione dà le competenze razziali in armi e strumenti', async (nome, sotto, attese) => {
    const mandate = voci(await creaConRazza(nome, sotto))
    expect(attese.filter((nomi) => !nomi.some((n) => mandate.includes(n)))).toEqual([])
  })

  // caccia: {"id": "CB-3070", "fonte": "2014 · Razze · Mezzelfo: Carisma +2 e altri due punteggi a scelta +1 ciascuno · pag. 39", "zona": "regola:2014/razze", "voce": "regola", "copre": ["carta:2014/races.md#Mezzelfo / Half-Elf (pag. 39)", "route:/"]}
  it.fails('mezzelfo: oltre a Carisma +2 riceve +1 a due altre caratteristiche', () => {
    const aumenti = buildSpecies(razza('half-elf'), null, 'it').ability_bonuses
    const altri = Object.entries(aumenti).filter(([k, v]) => k !== 'cha' && v === 1)
    expect([aumenti.cha, altri.length]).toEqual([2, 2])
  })

  // caccia: {"id": "CB-3071", "fonte": "2014 · Razze · Mezzelfo, Retaggio Fatato (pag. 39) e Gnomo, Astuzia Gnomesca (pag. 36-37): vantaggio a tiri salvezza, come le note di Elfo, Nano e Halfling", "zona": "regola:2014/razze", "voce": "regola", "copre": ["carta:2014/races.md#Mezzelfo / Half-Elf (pag. 39)", "carta:2014/races.md#Gnomo / Gnome - tratti base (pag. 36-37)", "route:/"]}
  it.each([
    ['half-elf', 'save.wisdom'],
    ['gnome', 'save.intelligence'],
    ['gnome', 'save.wisdom'],
    ['gnome', 'save.charisma'],
  ])('%s: il vantaggio razziale ai tiri salvezza ha la nota su %s', (indice, tiro) => {
    expect(Object.keys(buildSpecies(razza(indice), null, 'it').roll_notes)).toContain(tiro)
  })
})

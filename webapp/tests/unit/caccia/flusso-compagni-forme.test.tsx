import { describe, it, expect, vi } from 'vitest'
import type { ReactNode } from 'react'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '../utils/renderWithProviders'
import CompanionCard from '@/pages/extras/CompanionCard'
import { wildShapeMaxCr, wildShapeWarning } from '@/lib/companionRules'
import type { Companion } from '@/types'

vi.mock('@/api/client', () => ({
  api: { companions: { attack: vi.fn(), hp: vi.fn(), remove: vi.fn(), deactivate: vi.fn(), activate: vi.fn(), hitDice: vi.fn() } },
  ApiError: class ApiError extends Error { constructor(public status: number, public detail: unknown) { super('x') } },
}))
vi.mock('react-i18next', async (orig) => ({
  ...((await orig()) as Record<string, unknown>),
  useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }),
}))
vi.mock('@/hooks/useD20Roll', () => ({ useD20Roll: () => vi.fn().mockResolvedValue([12]) }))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: vi.fn(), info: vi.fn(), success: vi.fn() }) }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/pages/hp/ConcentrationSaveDialog', () => ({ default: () => null }))
vi.mock('@/pages/extras/WildHealSheet', () => ({ default: () => null }))
vi.mock('@/components/ui/RollButton', async () => {
  const React = await import('react')
  return { default: (p: { children?: ReactNode }) => React.createElement('button', null, p.children) }
})

const scheda = (extra: Partial<Companion>) => ({
  id: 1, character_id: 7, kind: 'companion', name: 'Bestia', srd_index: null, max_hp: 30, current_hp: 30, temp_hp: 0,
  armor_class: 15, notes: null, is_active: false, created_at: '', down: false,
  statblock: { actions: [{ name: 'Colpo della Bestia', attack_bonus: 0, damage_dice: '1d8+2', damage_type: 'slashing' }] },
  ...extra,
}) as unknown as Companion

const entry = (type: string, cr: number, speed: Record<string, number> = {}) =>
  ({ index: 'x', type, challenge_rating: cr, speed: { walk_ft: 30, ...speed } }) as Parameters<typeof wildShapeWarning>[0]

// caccia: {"id": "CB-359", "fonte": "invariante: un bonus negativo si scrive con il segno meno, mai come «+-1» (Saggezza 8 dà -1 ai danni della bestia 2024)", "zona": "flusso:compagni-forme", "voce": "limiti", "copre": ["route:/char/:id/extras"]}
it.fails('il bonus ai danni negativo della bestia non appare come «+-1»', () => {
  const { container } = renderWithProviders(
    <CompanionCard charId={7} comp={scheda({ feature_key: 'ranger.primal_companion', attack_bonus_extra: 1, damage_bonus_extra: -1 })} wildShapeUses={null} />,
  )
  expect(container.textContent).toContain('1d8+2')
  expect(container.textContent).not.toContain('+-')
})

// caccia: {"id": "CB-360", "fonte": "2014 e 2024 · Druido · Forme Bestiali e Forme del Circolo · pag. 66-69 e 80-86", "zona": "flusso:compagni-forme", "voce": "regola", "copre": ["route:/char/:id/extras"]}
it.each([
  ['2014', 2, false, 0.25], ['2014', 4, false, 0.5], ['2014', 8, false, 1], ['2014', 2, true, 1], ['2014', 5, true, 1], ['2014', 6, true, 2], ['2014', 12, true, 4],
  ['2024', 2, false, 0.25], ['2024', 4, false, 0.5], ['2024', 8, false, 1], ['2024', 3, true, 1], ['2024', 6, true, 2], ['2024', 12, true, 4],
])('il GS massimo mostrato in avviso segue la scheda: %s, livello %i, Luna %s -> %f', (edizione, livello, luna, gs) => {
  expect(wildShapeMaxCr(livello, luna, edizione)).toBe(gs)
})

// caccia: {"id": "CB-361", "fonte": "2014 · Druido · Forme Bestiali · pag. 66; 2024 · Druido · Forma Selvatica · pag. 80", "zona": "flusso:compagni-forme", "voce": "edizioni", "copre": ["route:/char/:id/extras"]}
it('l\'avviso su nuoto e volo segue l\'edizione: nel 2024 il nuoto è libero', () => {
  expect(wildShapeWarning(entry('beast', 0.25, { swim_ft: 30 }), 2, false, '2014')).toBe('character.extras.warn.swim')
  expect(wildShapeWarning(entry('beast', 0.25, { swim_ft: 30 }), 4, false, '2014')).toBeNull()
  expect(wildShapeWarning(entry('beast', 0.25, { swim_ft: 30 }), 2, false, '2024')).toBeNull()
  expect(wildShapeWarning(entry('beast', 0.25, { fly_ft: 30 }), 7, false, '2024')).toBe('character.extras.warn.fly')
  expect(wildShapeWarning(entry('beast', 0.25, { fly_ft: 30 }), 8, false, '2024')).toBeNull()
})

// caccia: {"id": "CB-362", "fonte": "2024 · Druido · Regole della Forma Selvatica · pag. 81 (i PF restano quelli del druido)", "zona": "flusso:compagni-forme", "voce": "edizioni", "copre": ["route:/char/:id/extras"]}
it('nel 2024 la forma attiva non mostra PF propri, quella non attiva sì', () => {
  const forma = (attiva: boolean) => scheda({ kind: 'wild_shape', is_active: attiva })
  const { unmount } = renderWithProviders(<CompanionCard charId={7} comp={forma(true)} wildShapeUses={2} formHasNoHp />)
  expect(screen.queryByText('character.hp.quick_damage')).toBeNull()
  unmount()
  renderWithProviders(<CompanionCard charId={7} comp={forma(false)} wildShapeUses={2} formHasNoHp />)
  expect(screen.getByText('character.hp.quick_damage')).toBeInTheDocument()
})

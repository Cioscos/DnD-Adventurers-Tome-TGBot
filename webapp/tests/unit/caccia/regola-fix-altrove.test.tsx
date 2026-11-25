import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import CompanionCard from '@/pages/extras/CompanionCard'
import { useCastFlow } from '@/pages/spells/useCastFlow'
import { featByKey, meetsPrerequisites } from '@/lib/feats'
import type { CharacterFull, Companion, Spell } from '@/types'

const { attack, lancia, toastSuccess } = vi.hoisted(() => ({ attack: vi.fn(), lancia: vi.fn(), toastSuccess: vi.fn() }))

vi.mock('@/api/client', async (orig) => ({
  ...(await orig<Record<string, unknown>>()),
  api: {
    spells: { use: lancia, castCheck: vi.fn(async () => []) },
    characters: { rollOptions: vi.fn(async () => []), turnState: vi.fn(async () => ({})), sessionAllies: vi.fn(async () => []) },
    companions: { attack },
  },
}))
vi.mock('react-i18next', async (orig) => ({
  ...(await orig<typeof import('react-i18next')>()), useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }),
}))
vi.mock('sonner', () => ({ toast: { success: toastSuccess, info: vi.fn(), error: vi.fn(), warning: vi.fn() } }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/dice/useAnimatedRoll', () => ({ useAnimatedRoll: () => async () => undefined }))
vi.mock('@/hooks/useD20Roll', async (orig) => ({ ...(await orig<Record<string, unknown>>()), useD20Roll: () => async () => undefined }))
vi.mock('@/components/ui/Sheet', () => ({ default: (p: { open: boolean; children?: React.ReactNode }) => (p.open ? <div>{p.children}</div> : null) }))
vi.mock('@/pages/spells/CastSpellModal', () => ({
  default: (p: { onCast: (s: { id: number; level: number }) => void }) => <button onClick={() => p.onCast({ id: 1, level: 6 })}>slot</button>,
}))

afterEach(() => vi.clearAllMocks())

const immagine = { id: 4, name: 'Immagine Maggiore', level: 3, is_concentration: true, is_ritual: false, is_prepared: true } as Spell
const mago = {
  id: 7, rules_edition: '2014', spells: [immagine], settings: {}, classes: [], spellcasting: null,
  spell_slots: [{ id: 1, level: 6, total: 1, used: 0, available: 1, is_pact: false }],
} as unknown as CharacterFull

function Banco() {
  const flow = useCastFlow(7, mago)
  return <><button onClick={() => flow.beginCast(immagine)}>lancia</button>{flow.elements}</>
}

describe('caccia: revisioni delle correzioni regole', () => {
  // caccia: {"id": "CB-4715", "fonte": "2014 · Incantesimi · Immagine Maggiore (dal 6° senza concentrazione) · pag. 242", "zona": "regola:2014/incantesimi-G-L", "voce": "interazione", "copre": ["carta:2014/spells.md#Immagine Maggiore", "route:/char/:id/spells"]}
  it.each([[null, false], [4, true]])('l\'avviso del lancio dice la concentrazione solo se il server l\'ha avviata (%s)', async (concentrating_spell_id, detta) => {
    lancia.mockResolvedValue({ ...mago, concentrating_spell_id })
    renderWithProviders(<Banco />)
    const user = userEvent.setup({ pointerEventsCheck: 0 })
    await user.click(screen.getByText('lancia'))
    await user.click(await screen.findByText('slot'))
    await waitFor(() => expect(toastSuccess).toHaveBeenCalled())
    expect(String(toastSuccess.mock.calls[0][0]).includes('cast_done_concentration')).toBe(detta)
  })

  // caccia: {"id": "CB-4716", "fonte": "2024 · Ranger · Compagno Primordiale (può usare la reazione da sola) · pag. 122", "zona": "regola:2024/ranger", "voce": "regola", "copre": ["carta:2024/classes/ranger.md#Compagno Primordiale / Primal Companion (Signore delle Bestie 3, pag. 122)", "POST /characters/{char_id}/companions/{comp_id}/attack", "route:/char/:id/extras"]}
  it('la bestia primordiale ha l\'attacco di reazione senza un ordine', async () => {
    attack.mockResolvedValue({ to_hit_die: 12, to_hit_bonus: 6, to_hit_total: 18, is_critical: false, damage_total: 5, notes: [] })
    const bestia = {
      id: 3, kind: 'companion', name: 'Bestia della Terra', max_hp: 20, current_hp: 20, temp_hp: 0, armor_class: 14, is_active: false,
      down: false, feature_key: 'ranger.primal_companion',
      statblock: { hit_dice: '3d8', actions: [{ name: 'Colpo della Bestia', attack_bonus: 5, damage_dice: '1d8+2' }] },
    } as unknown as Companion
    renderWithProviders(<CompanionCard charId={7} comp={bestia} wildShapeUses={null} />)
    await userEvent.setup({ pointerEventsCheck: 0 }).click(screen.getByLabelText('character.extras.beast.reaction_attack Colpo della Bestia'))
    await waitFor(() => expect(attack).toHaveBeenCalled())
    expect(attack.mock.calls[0][6]).toBe(true)
  })

  // caccia: {"id": "CB-4717", "fonte": "2014 · Talenti · Incantatore da Guerra (capacità di lanciare almeno un incantesimo, da qualsiasi fonte) · pag. 168", "zona": "regola:2014/talenti", "voce": "interazione", "copre": ["carta:2014/feats.md#Incantatore da Guerra / War Caster (pag. 168)", "route:/char/:id/abilities"]}
  it('i talenti da incantatore seguono il server: un elfo alto guerriero può, un umano no', () => {
    const guerriero = (casts_spells: boolean) => ({
      rules_edition: '2014', total_level: 4, ability_scores: [], abilities: [], settings: {}, computed: { casts_spells },
      classes: [{ id: 1, class_name: 'fighter', level: 4, spellcasting_ability: null }],
    }) as unknown as CharacterFull
    const talento = featByKey('war_caster')!
    expect([true, false].map((sa) => meetsPrerequisites(talento, guerriero(sa)))).toEqual([true, false])
  })
})

import { useState } from 'react'
import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import HpQuickSheet from '@/components/character/HpQuickSheet'
import { ApiError } from '@/api/client'
import type { CharacterFull } from '@/types'

const flowElements = vi.hoisted(() => vi.fn(() => null as unknown))
const { updateHpSpy, undoHpSpy, showUndoToastSpy, toastError, notifySpy, attackWeaponSpy, attackUnarmedSpy } = vi.hoisted(() => ({
  attackWeaponSpy: vi.fn(),
  attackUnarmedSpy: vi.fn(),
  updateHpSpy: vi.fn(),
  undoHpSpy: vi.fn(),
  showUndoToastSpy: vi.fn(),
  toastError: vi.fn(),
  notifySpy: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  api: { characters: { updateHp: updateHpSpy, undoHp: undoHpSpy } },
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: unknown) {
      super(`API ${status}`)
    }
  },
}))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/hooks/useWeaponAttackFlow', () => ({
  useWeaponAttackFlow: () => ({
    attackWeapon: attackWeaponSpy, attackUnarmed: attackUnarmedSpy, attackUnarmedEffect: vi.fn(),
    isWeaponPending: () => false, isUnarmedPending: false, elements: flowElements(),
  }),
}))
vi.mock('@/components/ui/UndoToast', () => ({ showUndoToast: showUndoToastSpy }))
vi.mock('@/hooks/useToast', () => ({
  useToast: () => ({ error: toastError, warning: vi.fn(), success: vi.fn() }),
}))
vi.mock('@/lib/mutationError', () => ({ notifyMutationError: notifySpy }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})

const char = { id: 42, current_hit_points: 10, hit_points: 20 } as CharacterFull

afterEach(() => {
  updateHpSpy.mockReset()
  undoHpSpy.mockReset()
  showUndoToastSpy.mockReset()
  toastError.mockReset()
  notifySpy.mockReset()
})

async function applyDamage() {
  renderWithProviders(<HpQuickSheet char={char} open onClose={() => {}} />)
  await userEvent.type(screen.getByPlaceholderText('0'), '4')
  await userEvent.click(screen.getByRole('button', { name: 'character.hp.apply_damage' }))
  await waitFor(() => expect(updateHpSpy).toHaveBeenCalled())
}

describe('HpQuickSheet quick values', () => {
  it('a chip applies at once, with the same undo as a typed value', async () => {
    updateHpSpy.mockResolvedValue({ ...char, hp_undo_id: 'abc' })
    const onClose = vi.fn()
    renderWithProviders(<HpQuickSheet char={char} open onClose={onClose} />)
    await userEvent.click(screen.getByRole('button', { name: '−5' }))
    await waitFor(() => expect(updateHpSpy).toHaveBeenCalledWith(42, 'damage', 5))
    await waitFor(() => expect(showUndoToastSpy).toHaveBeenCalled())
    expect(onClose).toHaveBeenCalled()
  })

  it('heal chips heal, and the optional damage controls start closed', async () => {
    updateHpSpy.mockResolvedValue({ ...char })
    renderWithProviders(<HpQuickSheet char={char} open onClose={() => {}} />)
    expect(screen.getByRole('button', { name: 'character.hp.damage_type' })).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(screen.getByText('character.hp.quick_heal'))
    await userEvent.click(screen.getByRole('button', { name: '+10' }))
    await waitFor(() => expect(updateHpSpy).toHaveBeenCalledWith(42, 'heal', 10))
  })
})

describe('HpQuickSheet undo', () => {
  it('undo calls undoHp with the op id', async () => {
    updateHpSpy.mockResolvedValue({ ...char, hp_undo_id: 'abc' })
    undoHpSpy.mockResolvedValue(char)
    await applyDamage()
    await waitFor(() => expect(showUndoToastSpy).toHaveBeenCalled())
    showUndoToastSpy.mock.calls[0][0].onUndo()
    await waitFor(() => expect(undoHpSpy).toHaveBeenCalledWith(42, 'abc'))
    expect(updateHpSpy).toHaveBeenCalledTimes(1)
  })

  it('shows stale message on 409', async () => {
    updateHpSpy.mockResolvedValue({ ...char, hp_undo_id: 'abc' })
    undoHpSpy.mockRejectedValue(new ApiError(409, 'x'))
    await applyDamage()
    await waitFor(() => expect(showUndoToastSpy).toHaveBeenCalled())
    showUndoToastSpy.mock.calls[0][0].onUndo()
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('character.hp.undo_stale'))
    expect(notifySpy).not.toHaveBeenCalled()
  })

  it('shows network message when undo fails without a response', async () => {
    updateHpSpy.mockResolvedValue({ ...char, hp_undo_id: 'abc' })
    undoHpSpy.mockRejectedValue(new TypeError('Failed to fetch'))
    await applyDamage()
    await waitFor(() => expect(showUndoToastSpy).toHaveBeenCalled())
    showUndoToastSpy.mock.calls[0][0].onUndo()
    await waitFor(() => expect(notifySpy).toHaveBeenCalled())
    expect(toastError).not.toHaveBeenCalledWith('character.hp.undo_stale')
  })

  it('no undo toast without hp_undo_id', async () => {
    updateHpSpy.mockResolvedValue({ ...char, hp_undo_id: null })
    await applyDamage()
    await waitFor(() => expect(updateHpSpy).toHaveBeenCalled())
    expect(showUndoToastSpy).not.toHaveBeenCalled()
  })

  it('undo toast mentions homebrew effects', async () => {
    updateHpSpy.mockResolvedValue({ ...char, hp_undo_id: 'abc', homebrew_notifications: [{ a: 1 }] })
    await applyDamage()
    await waitFor(() => expect(showUndoToastSpy).toHaveBeenCalled())
    expect(showUndoToastSpy.mock.calls[0][0].message).toContain('character.hp.undo_homebrew_note')
  })
})

describe('HpQuickSheet wild shape', () => {
  it('shows the form HP as primary and the character HP as secondary', () => {
    const shaped = {
      ...char, name: 'Elandor', temp_hp: 0,
      active_form: { companion_id: 9, name: 'Lupo', current_hp: 8, max_hp: 11, temp_hp: 2, armor_class: 13 },
    } as CharacterFull
    renderWithProviders(<HpQuickSheet char={shaped} open onClose={() => {}} />)
    expect(screen.getByText('Lupo')).toBeInTheDocument()
    expect(screen.getByTestId('form-hp-primary')).toHaveTextContent('8/11')
    expect(screen.getByTestId('form-hp-primary')).toHaveTextContent('+2')
    expect(screen.getByTestId('character-hp-secondary')).toHaveTextContent('Elandor')
    expect(screen.getByTestId('character-hp-secondary')).toHaveTextContent('10/20')
  })

  it('shows no form block without an active form', () => {
    renderWithProviders(<HpQuickSheet char={char} open onClose={() => {}} />)
    expect(screen.queryByTestId('form-hp-primary')).toBeNull()
  })
})

// Su telefono la tastiera automatica ridimensiona la WebView e fa scattare l'hub (S22): niente autofocus.
// Con mouse/trackpad (Telegram Desktop) non c'è tastiera a schermo: il campo si attiva da solo.
describe('HpQuickSheet autofocus', () => {
  const stubPointer = (fine: boolean) =>
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: q === '(pointer: fine)' ? fine : false }))
  afterEach(() => vi.unstubAllGlobals())

  it('con puntatore preciso (desktop) il campo importo ha subito il focus', () => {
    stubPointer(true)
    renderWithProviders(<HpQuickSheet char={char} open onClose={() => {}} />)
    expect(screen.getByPlaceholderText('0')).toHaveFocus()
  })

  it('su touch (telefono) il campo importo non prende il focus da solo', () => {
    stubPointer(false)
    renderWithProviders(<HpQuickSheet char={char} open onClose={() => {}} />)
    expect(screen.getByPlaceholderText('0')).not.toHaveFocus()
  })
})

describe('HpQuickSheet reactions opened by the damage', () => {
  const retaliation = { key: 'barbarian.retaliation', label: 'Ritorsione: ti ha colpito?', phase: 'before', slot: 'reaction' }
  const sword = { id: 31, name: 'Ascia', item_type: 'weapon', is_equipped: true, equipment_slot: 'main_hand' }
  const armed = { ...char, items: [sword] } as unknown as CharacterFull

  it('keeps the sheet open, proposes the reaction and attacks in one tap', async () => {
    updateHpSpy.mockResolvedValue({ ...armed, reactions: [retaliation], hp_undo_id: 'op1' })
    const onClose = vi.fn()
    renderWithProviders(<HpQuickSheet char={armed} open onClose={onClose} />)
    await userEvent.type(screen.getByPlaceholderText('0'), '4')
    await userEvent.click(screen.getByRole('button', { name: 'character.hp.apply_damage' }))
    expect(await screen.findByText('Ritorsione: ti ha colpito?')).toBeInTheDocument()
    expect(onClose).not.toHaveBeenCalled()
    await userEvent.click(screen.getByText('character.hp.reaction_attack'))
    expect(attackWeaponSpy).toHaveBeenCalledWith(31, 'normal', ['barbarian.retaliation'])
    await waitFor(() => expect(screen.queryByText('Ritorsione: ti ha colpito?')).toBeNull())
  })

  it('throws the caught missile unarmed even with a weapon in hand', async () => {
    attackWeaponSpy.mockClear()
    attackUnarmedSpy.mockClear()
    const throwBack = { key: 'monk.deflect_missiles_throw', label: 'Deviare Proiettili: rilancia', phase: 'before', slot: null, ranged_unarmed: true }
    updateHpSpy.mockResolvedValue({ ...armed, reactions: [throwBack], hp_undo_id: 'op1' })
    renderWithProviders(<HpQuickSheet char={armed} open onClose={() => {}} />)
    await userEvent.type(screen.getByPlaceholderText('0'), '4')
    await userEvent.click(screen.getByRole('button', { name: 'character.hp.apply_damage' }))
    await userEvent.click(await screen.findByText('character.hp.reaction_attack'))
    expect(attackUnarmedSpy).toHaveBeenCalledWith('normal', ['monk.deflect_missiles_throw'])
    expect(attackWeaponSpy).not.toHaveBeenCalled()
  })

  it('takes the proposal away when the damage is undone', async () => {
    updateHpSpy.mockResolvedValue({ ...armed, reactions: [retaliation], hp_undo_id: 'op1' })
    undoHpSpy.mockResolvedValue(armed)
    renderWithProviders(<HpQuickSheet char={armed} open onClose={() => {}} />)
    await userEvent.type(screen.getByPlaceholderText('0'), '4')
    await userEvent.click(screen.getByRole('button', { name: 'character.hp.apply_damage' }))
    expect(await screen.findByText('Ritorsione: ti ha colpito?')).toBeInTheDocument()
    showUndoToastSpy.mock.calls[0][0].onUndo()
    await waitFor(() => expect(undoHpSpy).toHaveBeenCalledWith(42, 'op1'))
    await waitFor(() => expect(screen.queryByText('Ritorsione: ti ha colpito?')).toBeNull())
  })

  it('keeps the outcome of the attack when the sheet is closed while it runs', async () => {
    flowElements.mockReturnValue(<div>esito-attacco</div>)
    updateHpSpy.mockResolvedValue({ ...armed, reactions: [retaliation], hp_undo_id: 'op1' })
    function Harness() {
      const [open, setOpen] = useState(true)
      return <><button onClick={() => setOpen(false)}>chiudi-esterno</button><HpQuickSheet char={armed} open={open} onClose={() => setOpen(false)} /></>
    }
    renderWithProviders(<Harness />)
    await userEvent.type(screen.getByPlaceholderText('0'), '4')
    await userEvent.click(screen.getByRole('button', { name: 'character.hp.apply_damage' }))
    await screen.findByText('Ritorsione: ti ha colpito?')
    await userEvent.click(screen.getByText('chiudi-esterno'))
    expect(screen.queryByText('Ritorsione: ti ha colpito?')).toBeNull()
    expect(screen.getByText('esito-attacco')).toBeInTheDocument()
    flowElements.mockReturnValue(null)
  })

  it('closes as before when the damage opens no reaction', async () => {
    updateHpSpy.mockResolvedValue({ ...armed, reactions: [], hp_undo_id: 'op1' })
    const onClose = vi.fn()
    renderWithProviders(<HpQuickSheet char={armed} open onClose={onClose} />)
    await userEvent.type(screen.getByPlaceholderText('0'), '4')
    await userEvent.click(screen.getByRole('button', { name: 'character.hp.apply_damage' }))
    await waitFor(() => expect(onClose).toHaveBeenCalled())
    expect(screen.queryByText('character.hp.reaction_title')).toBeNull()
  })
})

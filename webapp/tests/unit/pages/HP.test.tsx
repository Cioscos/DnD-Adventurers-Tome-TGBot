import { describe, it, expect, vi, afterEach } from 'vitest'
import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import HP from '@/pages/HP'
import { ApiError } from '@/api/client'

// Spies hoisted so the vi.mock factories can close over them.
const {
  getChar, updateHpSpy, restSpy, reviveSpy, updateDeathSavesSpy,
  rollDeathSaveSpy, rollOptionsSpy, spendHitDiceSpy, undoHpSpy, showUndoToastSpy, toastWarning, playAndCollect,
} = vi.hoisted(() => ({
  getChar: vi.fn(),
  updateHpSpy: vi.fn(),
  restSpy: vi.fn(),
  reviveSpy: vi.fn(),
  updateDeathSavesSpy: vi.fn(),
  rollDeathSaveSpy: vi.fn(),
  rollOptionsSpy: vi.fn(),
  spendHitDiceSpy: vi.fn(),
  undoHpSpy: vi.fn(),
  showUndoToastSpy: vi.fn(),
  toastWarning: vi.fn(),
  playAndCollect: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  api: {
    characters: {
      get: getChar,
      updateHp: updateHpSpy,
      rest: restSpy,
      revive: reviveSpy,
      updateDeathSaves: updateDeathSavesSpy,
      rollDeathSave: rollDeathSaveSpy,
      rollOptions: rollOptionsSpy,
      spendHitDice: spendHitDiceSpy,
      undoHp: undoHpSpy,
    },
  },
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: unknown) {
      super(`API ${status}`)
    }
  },
}))

// useParams drives charId → pin the page to character 7.
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useParams: () => ({ id: '7' }) }
})

// Identity translator → button labels resolve to their i18n KEY (stable, locale-free).
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})

// framer-motion: strip motion props, keep DOM-valid ones; AnimatePresence is a passthrough.
vi.mock('framer-motion', async () => {
  const React = await import('react')
  const MOTION = new Set(['initial', 'animate', 'exit', 'transition', 'variants', 'whileTap', 'whileHover', 'drag', 'layout'])
  const make = (tag: string) => (props: Record<string, unknown>) => {
    const clean: Record<string, unknown> = {}
    for (const k in props) if (!MOTION.has(k)) clean[k] = props[k]
    return React.createElement(tag, clean)
  }
  return {
    m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }),
    AnimatePresence: (p: { children?: unknown }) => React.createElement(React.Fragment, null, p.children),
  }
})

vi.mock('sonner', () => ({ toast: { warning: toastWarning, error: vi.fn(), success: vi.fn() } }))
vi.mock('@/auth/telegram', () => ({ haptic: { success: () => {}, error: () => {}, light: () => {} } }))
vi.mock('@/styles/motion', () => ({ spring: new Proxy({}, { get: () => ({}) }) }))
vi.mock('@/dice/useDiceAnimation', () => ({ useDiceAnimation: () => ({ playAndCollect }) }))
vi.mock('@/store/diceSettings', () => ({ useDiceSettings: (sel: (s: { animate3d: boolean }) => unknown) => sel({ animate3d: false }) }))
vi.mock('@/hooks/useReducedMotion', () => ({ useReducedMotion: () => true }))
vi.mock('@/components/ui/UndoToast', () => ({ showUndoToast: showUndoToastSpy }))
const { attackWeaponSpy, attackUnarmedSpy } = vi.hoisted(() => ({ attackWeaponSpy: vi.fn(), attackUnarmedSpy: vi.fn() }))
vi.mock('@/hooks/useWeaponAttackFlow', () => ({
  useWeaponAttackFlow: () => ({
    attackWeapon: attackWeaponSpy, attackUnarmed: attackUnarmedSpy, attackUnarmedEffect: vi.fn(),
    isWeaponPending: () => false, isUnarmedPending: false, elements: null,
  }),
}))

// Hoisted so the (also hoisted) vi.mock factories below can use it.
const makePassthrough = vi.hoisted(() => (testid?: string) => async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', testid ? { 'data-testid': testid } : null, p.children) }
})
vi.mock('@/components/Layout', makePassthrough('layout'))
vi.mock('@/components/ui/Surface', makePassthrough())
vi.mock('@/components/homebrew/HomebrewBreakdownRow', makePassthrough())
vi.mock('@/components/ui/StatPill', makePassthrough())

vi.mock('@/components/skeletons/HPSkeleton', async () => {
  const React = await import('react')
  return { default: () => React.createElement('div', { 'data-testid': 'hp-skeleton' }) }
})
vi.mock('@/components/ui/HPGauge', async () => {
  const React = await import('react')
  return {
    default: (p: { current: number; max: number; temp: number }) =>
      React.createElement('div', { 'data-testid': 'hp-gauge', 'data-current': p.current, 'data-max': p.max, 'data-temp': p.temp }),
  }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return {
    default: (p: { onClick?: () => void; disabled?: boolean; children?: unknown }) =>
      React.createElement('button', { onClick: p.onClick, disabled: p.disabled }, p.children),
  }
})
vi.mock('@/components/ui/ConfirmSheet', async () => {
  const React = await import('react')
  return {
    default: (p: { open: boolean; body?: unknown; onConfirm: () => void; confirmLabel: string }) =>
      p.open
        ? React.createElement('div', { 'data-testid': 'confirm-sheet' }, p.body as never,
            React.createElement('button', { 'data-testid': 'confirm-ok', onClick: p.onConfirm }, p.confirmLabel))
        : null,
  }
})

// HP sub-components: stand-ins exposing the callbacks the page wires up.
vi.mock('@/pages/hp/HpOperationForm', async () => {
  const React = await import('react')
  return {
    default: (p: {
      value: string
      setValue: (v: string) => void
      onApply: () => void
      hpMutate: (a: { op: string; val: number }) => void
      setCrit: (v: boolean) => void
      setActiveOp: (op: string) => void
      activeOp: string
      damageModifier: 'half' | 'double' | null
      setDamageModifier: (m: 'half' | 'double' | null) => void
    }) =>
      React.createElement('div', { 'data-testid': 'hp-op-form' },
        React.createElement('input', { 'data-testid': 'hp-value', value: p.value, onChange: (e: { target: { value: string } }) => p.setValue(e.target.value) }),
        React.createElement('button', { 'data-testid': 'hp-apply', onClick: p.onApply }, 'apply'),
        React.createElement('button', { 'data-testid': 'hp-quick-heal', onClick: () => p.hpMutate({ op: 'heal', val: 3 }) }, 'quick'),
        React.createElement('button', { 'data-testid': 'hp-crit', onClick: () => p.setCrit(true) }, 'crit'),
        React.createElement('button', { 'data-testid': 'hp-quick-damage', onClick: () => p.hpMutate({ op: 'damage', val: 10 }) }, 'quickdmg'),
        React.createElement('button', { 'data-testid': 'hp-tab-heal', onClick: () => p.setActiveOp('heal') }, 'tabheal'),
        React.createElement('button', { 'data-testid': 'hp-tab-damage', onClick: () => p.setActiveOp('damage') }, 'tabdmg'),
        React.createElement('button', { 'data-testid': 'hp-mod-half', onClick: () => p.setDamageModifier('half') }, 'half'),
        React.createElement('span', { 'data-testid': 'hp-mod-state' }, String(p.damageModifier)),
      ),
  }
})
vi.mock('@/pages/hp/DeathSaves', async () => {
  const React = await import('react')
  return {
    default: (p: { onRoll: (m: string) => void; onAction: (a: string) => void }) =>
      React.createElement('div', { 'data-testid': 'death-saves' },
        React.createElement('button', { 'data-testid': 'ds-roll', onClick: () => p.onRoll('normal') }, 'roll'),
        React.createElement('button', { 'data-testid': 'ds-action', onClick: () => p.onAction('mark_success') }, 'action'),
      ),
  }
})
vi.mock('@/pages/hp/HitDiceModal', async () => {
  const React = await import('react')
  return {
    default: (p: { classes: { id: number }[]; onSpend: (cid: number, n: number) => void; onConfirmRest: () => void; preview?: unknown }) =>
      React.createElement('div', { 'data-testid': 'hit-dice-modal' },
        React.createElement('button', { 'data-testid': 'hd-spend', onClick: () => p.onSpend(p.classes[0].id, 2) }, 'spend'),
        p.preview,
        React.createElement('button', { 'data-testid': 'hd-rest', onClick: p.onConfirmRest }, 'rest'),
      ),
  }
})
vi.mock('@/pages/hp/DeadState', async () => {
  const React = await import('react')
  return {
    default: (p: { onRevive: () => void }) =>
      React.createElement('div', { 'data-testid': 'dead-state' },
        React.createElement('button', { 'data-testid': 'revive', onClick: p.onRevive }, 'revive')),
  }
})
vi.mock('@/pages/hp/HitDiceResultDialog', makePassthrough('hit-dice-result'))
vi.mock('@/pages/hp/DeathSaveResultDialog', makePassthrough('death-roll-result'))
vi.mock('@/pages/hp/ConcentrationSaveDialog', async () => {
  const React = await import('react')
  return { default: () => React.createElement('div', { 'data-testid': 'conc-dialog' }) }
})
vi.mock('@/pages/hp/InstantDeathDialog', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean }) => (p.open ? React.createElement('div', { 'data-testid': 'instant-death' }) : null) }
})

// CharacterFull fixtures (only the fields HP.tsx reads).
const aliveChar = {
  id: 7,
  current_hit_points: 20,
  hit_points: 30,
  temp_hp: 0,
  death_saves: { successes: 0, failures: 0, stable: false },
  is_dead: false,
  concentrating_spell_id: null,
  classes: [{ id: 1, class_name: 'fighter', level: 5 }],
  hp_max_homebrew_modifier: 5,
  concentration_save: null,
}

const landDruid = {
  ...aliveChar,
  classes: [{ id: 1, class_name: 'Druido', level: 5 }],
  active_states: [],
  abilities: [{ id: 9, feature_key: 'druid.natural_recovery', uses: 1, max_uses: 1 }],
  spell_slots: [
    { id: 1, level: 1, total: 4, used: 3, available: 1, is_pact: false },
    { id: 2, level: 2, total: 3, used: 0, available: 3, is_pact: false },
  ],
}
const dyingChar = { ...aliveChar, current_hit_points: 0, death_saves: { successes: 0, failures: 0, stable: false } }
const deadChar = { ...aliveChar, is_dead: true, current_hit_points: 0, death_saves: { successes: 0, failures: 3, stable: false } }

afterEach(() => {
  getChar.mockReset()
  updateHpSpy.mockReset()
  restSpy.mockReset()
  reviveSpy.mockReset()
  updateDeathSavesSpy.mockReset()
  rollDeathSaveSpy.mockReset()
  spendHitDiceSpy.mockReset()
  showUndoToastSpy.mockReset()
  toastWarning.mockReset()
})

describe('HP page — wild shape', () => {
  it('shows the active form HP as primary and the character HP as secondary', async () => {
    getChar.mockResolvedValue({
      ...aliveChar, name: 'Elandor', temp_hp: 3,
      active_form: { companion_id: 9, name: 'Lupo', current_hp: 8, max_hp: 11, temp_hp: 2, armor_class: 13 },
    })
    renderWithProviders(<HP />)
    expect(await screen.findByText('8')).toBeInTheDocument()
    expect(screen.getByText('/11')).toBeInTheDocument()
    expect(screen.getByText('Lupo')).toBeInTheDocument()
    const gauge = screen.getByTestId('hp-gauge')
    expect(gauge).toHaveAttribute('data-current', '8')
    expect(gauge).toHaveAttribute('data-max', '11')
    expect(gauge).toHaveAttribute('data-temp', '2')
    const secondary = screen.getByTestId('character-hp-secondary')
    expect(secondary).toHaveTextContent('Elandor')
    expect(secondary).toHaveTextContent('20/35')
    expect(secondary).toHaveTextContent('+3')
  })
})

describe('HP page', () => {
  it('shows the skeleton while the character query is pending', () => {
    getChar.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<HP />)
    expect(screen.getByTestId('hp-skeleton')).toBeInTheDocument()
  })

  it('renders current HP and max = hit_points + homebrew modifier (read contract)', async () => {
    getChar.mockResolvedValue(aliveChar)
    renderWithProviders(<HP />)
    // current_hit_points = 20, max = 30 + 5 = 35
    expect(await screen.findByText('20')).toBeInTheDocument()
    expect(screen.getByText('/35')).toBeInTheDocument()
    const gauge = screen.getByTestId('hp-gauge')
    expect(gauge).toHaveAttribute('data-current', '20')
    expect(gauge).toHaveAttribute('data-max', '35')
  })

  it('shows the concentration banner for a spell cast from an item', async () => {
    getChar.mockResolvedValue({ ...aliveChar, settings: { concentration_item_spell: { item_id: 9, name: 'Volare' } } })
    renderWithProviders(<HP />)
    expect(await screen.findByText('character.hp.concentration_active')).toBeInTheDocument()
    expect(screen.getByText('Volare')).toBeInTheDocument()
  })

  it('handleApply parses the value and calls updateHp(id, op, val, wasCritical=false) when alive', async () => {
    getChar.mockResolvedValue(aliveChar)
    updateHpSpy.mockResolvedValue(aliveChar)
    renderWithProviders(<HP />)
    await screen.findByTestId('hp-op-form')

    await userEvent.type(screen.getByTestId('hp-value'), '5')
    await userEvent.click(screen.getByTestId('hp-apply'))
    await waitFor(() => expect(updateHpSpy).toHaveBeenCalledWith(7, 'damage', 5, false))
  })

  it('typed value also shows one undo toast that undoes with the op id', async () => {
    getChar.mockResolvedValue(aliveChar)
    updateHpSpy.mockResolvedValue({ ...aliveChar, hp_undo_id: 'typed' })
    undoHpSpy.mockResolvedValue(aliveChar)
    renderWithProviders(<HP />)
    await screen.findByTestId('hp-op-form')

    await userEvent.type(screen.getByTestId('hp-value'), '5')
    await userEvent.click(screen.getByTestId('hp-apply'))
    await waitFor(() => expect(showUndoToastSpy).toHaveBeenCalledTimes(1))
    showUndoToastSpy.mock.calls[0][0].onUndo()
    await waitFor(() => expect(undoHpSpy).toHaveBeenCalledWith(7, 'typed'))
  })

  it('does not call updateHp for non-positive / NaN input (guard)', async () => {
    getChar.mockResolvedValue(aliveChar)
    renderWithProviders(<HP />)
    await screen.findByTestId('hp-op-form')
    // value left empty → parseInt('') is NaN → guarded
    await userEvent.click(screen.getByTestId('hp-apply'))
    expect(updateHpSpy).not.toHaveBeenCalled()
  })

  it('sets was_critical_hit=true only when damaging at 0 HP with crit toggled', async () => {
    getChar.mockResolvedValue(dyingChar) // current_hit_points = 0
    updateHpSpy.mockResolvedValue(dyingChar)
    renderWithProviders(<HP />)
    await screen.findByTestId('hp-op-form')

    await userEvent.click(screen.getByTestId('hp-crit')) // setCrit(true)
    await userEvent.type(screen.getByTestId('hp-value'), '5')
    await userEvent.click(screen.getByTestId('hp-apply'))
    await waitFor(() => expect(updateHpSpy).toHaveBeenCalledWith(7, 'damage', 5, true))
  })

  it('quick apply fires updateHp(heal) and shows an undo toast', async () => {
    getChar.mockResolvedValue(aliveChar)
    updateHpSpy.mockResolvedValue({ ...aliveChar, hp_undo_id: 'abc' })
    renderWithProviders(<HP />)
    await screen.findByTestId('hp-op-form')

    await userEvent.click(screen.getByTestId('hp-quick-heal'))
    await waitFor(() => expect(updateHpSpy).toHaveBeenCalledWith(7, 'heal', 3, false))
    await waitFor(() => expect(showUndoToastSpy).toHaveBeenCalled())
  })

  it('quick apply undo calls undoHp with the op id', async () => {
    getChar.mockResolvedValue(aliveChar)
    updateHpSpy.mockResolvedValue({ ...aliveChar, hp_undo_id: 'abc' })
    undoHpSpy.mockResolvedValue(aliveChar)
    renderWithProviders(<HP />)
    await screen.findByTestId('hp-op-form')

    await userEvent.click(screen.getByTestId('hp-quick-heal'))
    await waitFor(() => expect(showUndoToastSpy).toHaveBeenCalled())
    showUndoToastSpy.mock.calls[0][0].onUndo()
    await waitFor(() => expect(undoHpSpy).toHaveBeenCalledWith(7, 'abc'))
    expect(updateHpSpy).toHaveBeenCalledTimes(1)
  })

  // L'annullamento riporta indietro lo stato: i dialog dell'operazione annullata non
  // devono restare aperti a raccontare una morte o un TS che non valgono più.
  it('undo closes the instant-death and concentration dialogs', async () => {
    getChar.mockResolvedValue(aliveChar)
    updateHpSpy.mockResolvedValue({
      ...aliveChar,
      hp_undo_id: 'abc',
      is_dead: true,
      current_hit_points: 0,
      death_saves: { successes: 0, failures: 1, stable: false },
      concentration_save: { dc: 10, die: 4, total: 6, success: false, lost_concentration: true },
    })
    undoHpSpy.mockResolvedValue(aliveChar)
    renderWithProviders(<HP />)
    await screen.findByTestId('hp-op-form')

    await userEvent.click(screen.getByTestId('hp-quick-heal'))
    expect(await screen.findByTestId('instant-death')).toBeInTheDocument()
    expect(screen.getByTestId('conc-dialog')).toBeInTheDocument()
    await waitFor(() => expect(showUndoToastSpy).toHaveBeenCalled())

    act(() => { showUndoToastSpy.mock.calls[0][0].onUndo() })
    await waitFor(() => expect(screen.queryByTestId('instant-death')).toBeNull())
    expect(screen.queryByTestId('conc-dialog')).toBeNull()
  })

  it('short rest spends hit dice and rests; long rest goes through the confirm sheet', async () => {
    getChar.mockResolvedValue(aliveChar)
    restSpy.mockResolvedValue(aliveChar)
    spendHitDiceSpy.mockResolvedValue({})
    renderWithProviders(<HP />)
    await screen.findByTestId('hp-op-form')

    // short rest button → opens HitDiceModal
    await userEvent.click(screen.getByRole('button', { name: 'character.hp.short_rest' }))
    await userEvent.click(await screen.findByTestId('hd-spend'))
    await waitFor(() => expect(spendHitDiceSpy).toHaveBeenCalledWith(7, 1, 2, undefined))
    await userEvent.click(screen.getByTestId('hd-rest'))
    await waitFor(() => expect(restSpy).toHaveBeenCalledWith(7, 'short', expect.objectContaining({ interrupted: false, ate_and_drank: true })))

    // long rest button → opens ConfirmSheet → confirm
    await userEvent.click(screen.getByRole('button', { name: 'character.hp.long_rest' }))
    await userEvent.click(await screen.findByTestId('confirm-ok'))
    await waitFor(() => expect(restSpy).toHaveBeenCalledWith(7, 'long', expect.objectContaining({ interrupted: false, ate_and_drank: true })))
  })

  it('offers Natural Recovery in the short rest and sends the chosen slots with it', async () => {
    getChar.mockResolvedValue(landDruid)
    restSpy.mockResolvedValue(landDruid)
    renderWithProviders(<HP />)
    await screen.findByTestId('hp-op-form')
    await userEvent.click(screen.getByRole('button', { name: 'character.hp.short_rest' }))
    expect(await screen.findByTestId('natural-recovery')).toBeInTheDocument()
    await userEvent.click(within(screen.getByTestId('nr-plus-1')).getByRole('button'))
    await userEvent.click(screen.getByTestId('hd-rest'))
    await waitFor(() => expect(restSpy).toHaveBeenCalledWith(7, 'short', expect.objectContaining({ natural_recovery: { 1: 1 } })))
  })

  it('offers the Book of Shadows switch in the long rest and sends reopen_tome', async () => {
    const tomeLock = { ...aliveChar, rules_edition: '2024', classes: [{ id: 1, class_name: 'warlock', level: 3 }], active_states: [],
      abilities: [{ id: 5, feature_key: 'warlock.pact_of_the_tome', name: 'Patto del Tomo' }] }
    getChar.mockResolvedValue(tomeLock)
    restSpy.mockResolvedValue(tomeLock)
    renderWithProviders(<HP />)
    await screen.findByTestId('hp-op-form')
    await userEvent.click(screen.getByRole('button', { name: 'character.hp.long_rest' }))
    await userEvent.click(within(await screen.findByTestId('tome-reopen')).getByRole('switch'))
    await userEvent.click(screen.getByTestId('confirm-ok'))
    await waitFor(() => expect(restSpy).toHaveBeenCalledWith(7, 'long', expect.objectContaining({ reopen_tome: true })))
  })

  it('asks if the rest was interrupted and if the character ate, and confirms a too-soon long rest', async () => {
    getChar.mockResolvedValue(aliveChar)
    restSpy.mockRejectedValueOnce(new ApiError(409, 'long_rest_too_soon')).mockResolvedValue(aliveChar)
    renderWithProviders(<HP />)
    await screen.findByTestId('hp-op-form')
    await userEvent.click(screen.getByRole('button', { name: 'character.hp.long_rest' }))
    const switches = await screen.findAllByRole('switch')
    expect(switches).toHaveLength(2) // interrotto + ha mangiato e bevuto (2014)
    await userEvent.click(switches[0])
    await userEvent.click(screen.getByTestId('confirm-ok'))
    await waitFor(() => expect(restSpy).toHaveBeenCalledWith(7, 'long', expect.objectContaining({ interrupted: true, ate_and_drank: true })))
    await screen.findByText('character.quick_actions.rest_too_soon_body')
    await userEvent.click(screen.getByTestId('confirm-ok'))
    await waitFor(() => expect(restSpy).toHaveBeenLastCalledWith(7, 'long', expect.objectContaining({ confirm_early: true })))
  })

  it('does not offer the Book of Shadows switch without the pact', async () => {
    getChar.mockResolvedValue(aliveChar)
    renderWithProviders(<HP />)
    await screen.findByTestId('hp-op-form')
    await userEvent.click(screen.getByRole('button', { name: 'character.hp.long_rest' }))
    await screen.findByTestId('confirm-ok')
    expect(screen.queryByTestId('tome-reopen')).toBeNull()
  })

  it('does not offer Natural Recovery to a character without the feature', async () => {
    getChar.mockResolvedValue(aliveChar)
    renderWithProviders(<HP />)
    await screen.findByTestId('hp-op-form')
    await userEvent.click(screen.getByRole('button', { name: 'character.hp.short_rest' }))
    await screen.findByTestId('hd-rest')
    expect(screen.queryByTestId('natural-recovery')).toBeNull()
  })

  it('when dying shows DeathSaves: roll → rollDeathSave(id, undefined); action → updateDeathSaves(id, action)', async () => {
    getChar.mockResolvedValue(dyingChar)
    rollDeathSaveSpy.mockResolvedValue({})
    updateDeathSavesSpy.mockResolvedValue(dyingChar)
    renderWithProviders(<HP />)
    await screen.findByTestId('death-saves')

    await userEvent.click(screen.getByTestId('ds-roll'))
    // reducedMotion=true → no 3D animation → die left undefined (server rolls)
    await waitFor(() => expect(rollDeathSaveSpy).toHaveBeenCalledWith(7, undefined))
    expect(rollOptionsSpy).toHaveBeenCalledWith(7, { roll: 'death_save' })

    await userEvent.click(screen.getByTestId('ds-action'))
    await waitFor(() => expect(updateDeathSavesSpy).toHaveBeenCalledWith(7, 'mark_success'))
  })

  it('when dead shows DeadState and revive calls api.characters.revive', async () => {
    getChar.mockResolvedValue(deadChar)
    reviveSpy.mockResolvedValue(aliveChar)
    renderWithProviders(<HP />)
    await screen.findByTestId('dead-state')
    // operation form + rest buttons are hidden while dead
    expect(screen.queryByTestId('hp-op-form')).not.toBeInTheDocument()

    await userEvent.click(screen.getByTestId('revive'))
    await waitFor(() => expect(reviveSpy).toHaveBeenCalledWith(7))
  })

  it('surfaces the concentration save dialog and a warning toast when concentration is lost', async () => {
    getChar.mockResolvedValue(aliveChar)
    updateHpSpy.mockResolvedValue({
      ...aliveChar,
      concentration_save: { dc: 10, die: 4, total: 6, success: false, lost_concentration: true },
    })
    renderWithProviders(<HP />)
    await screen.findByTestId('hp-op-form')

    await userEvent.type(screen.getByTestId('hp-value'), '8')
    await userEvent.click(screen.getByTestId('hp-apply'))
    expect(await screen.findByTestId('conc-dialog')).toBeInTheDocument()
    await waitFor(() => expect(toastWarning).toHaveBeenCalled())
  })

  it('opens the instant-death dialog when an HP update reports massive-damage death (failures < 3)', async () => {
    getChar.mockResolvedValue(aliveChar)
    updateHpSpy.mockResolvedValue({ ...aliveChar, is_dead: true, current_hit_points: 0, death_saves: { successes: 0, failures: 1, stable: false } })
    renderWithProviders(<HP />)
    await screen.findByTestId('hp-op-form')

    await userEvent.type(screen.getByTestId('hp-value'), '99')
    await userEvent.click(screen.getByTestId('hp-apply'))
    expect(await screen.findByTestId('instant-death')).toBeInTheDocument()
  })

  describe('damage modifier', () => {
    it('halves a typed damage and sends the raw value', async () => {
      getChar.mockResolvedValue(aliveChar)
      updateHpSpy.mockResolvedValue(aliveChar)
      renderWithProviders(<HP />)
      await screen.findByTestId('hp-op-form')

      await userEvent.click(screen.getByTestId('hp-mod-half'))
      await userEvent.type(screen.getByTestId('hp-value'), '15')
      await userEvent.click(screen.getByTestId('hp-apply'))
      await waitFor(() => expect(updateHpSpy).toHaveBeenCalledWith(7, 'damage', 7, false, { damage_modifier: 'half', raw_value: 15 }))
    })

    it('halves a quick damage button', async () => {
      getChar.mockResolvedValue(aliveChar)
      updateHpSpy.mockResolvedValue(aliveChar)
      renderWithProviders(<HP />)
      await screen.findByTestId('hp-op-form')

      await userEvent.click(screen.getByTestId('hp-mod-half'))
      await userEvent.click(screen.getByTestId('hp-quick-damage'))
      await waitFor(() => expect(updateHpSpy).toHaveBeenCalledWith(7, 'damage', 5, false, { damage_modifier: 'half', raw_value: 10 }))
    })

    it('turns the modifier off after one damage', async () => {
      getChar.mockResolvedValue(aliveChar)
      updateHpSpy.mockResolvedValue(aliveChar)
      renderWithProviders(<HP />)
      await screen.findByTestId('hp-op-form')

      await userEvent.click(screen.getByTestId('hp-mod-half'))
      expect(screen.getByTestId('hp-mod-state')).toHaveTextContent('half')
      await userEvent.click(screen.getByTestId('hp-quick-damage'))
      await waitFor(() => expect(screen.getByTestId('hp-mod-state')).toHaveTextContent('null'))
    })

    it('resets the modifier when leaving the damage tab', async () => {
      getChar.mockResolvedValue(aliveChar)
      renderWithProviders(<HP />)
      await screen.findByTestId('hp-op-form')

      await userEvent.click(screen.getByTestId('hp-mod-half'))
      await userEvent.click(screen.getByTestId('hp-tab-heal'))
      expect(screen.getByTestId('hp-mod-state')).toHaveTextContent('null')
    })
  })
})

describe('HP page — reactions opened by the damage', () => {
  const retaliation = { key: 'barbarian.retaliation', label: 'Ritorsione: ti ha colpito?', phase: 'before', slot: 'reaction' }
  const sword = { id: 31, name: 'Ascia', item_type: 'weapon', is_equipped: true, equipment_slot: 'main_hand' }
  const withReaction = (over: Record<string, unknown> = {}) => ({ ...aliveChar, items: [sword], ...over })

  it('proposes the reaction after a hit and attacks with the main-hand weapon in one tap', async () => {
    getChar.mockResolvedValue(withReaction())
    updateHpSpy.mockResolvedValue(withReaction({ reactions: [retaliation], hp_undo_id: 'op1' }))
    renderWithProviders(<HP />)
    await userEvent.type(await screen.findByTestId('hp-value'), '4')
    await userEvent.click(screen.getByTestId('hp-apply'))
    expect(await screen.findByText('Ritorsione: ti ha colpito?')).toBeInTheDocument()
    expect(screen.getByText('character.hp.reaction_title')).toBeInTheDocument()
    await userEvent.click(screen.getByText('character.hp.reaction_attack'))
    expect(attackWeaponSpy).toHaveBeenCalledWith(31, 'normal', ['barbarian.retaliation'])
    await waitFor(() => expect(screen.queryByText('Ritorsione: ti ha colpito?')).toBeNull())
  })

  it('without a weapon in hand the reaction is an unarmed strike', async () => {
    getChar.mockResolvedValue(withReaction({ items: [] }))
    updateHpSpy.mockResolvedValue(withReaction({ items: [], reactions: [retaliation], hp_undo_id: 'op1' }))
    renderWithProviders(<HP />)
    await userEvent.type(await screen.findByTestId('hp-value'), '4')
    await userEvent.click(screen.getByTestId('hp-apply'))
    await userEvent.click(await screen.findByText('character.hp.reaction_attack'))
    expect(attackUnarmedSpy).toHaveBeenCalledWith('normal', ['barbarian.retaliation'])
  })

  it('takes the proposal away when the damage is undone', async () => {
    getChar.mockResolvedValue(withReaction())
    updateHpSpy.mockResolvedValue(withReaction({ reactions: [retaliation], hp_undo_id: 'op1' }))
    undoHpSpy.mockResolvedValue(withReaction())
    renderWithProviders(<HP />)
    await userEvent.type(await screen.findByTestId('hp-value'), '4')
    await userEvent.click(screen.getByTestId('hp-apply'))
    expect(await screen.findByText('Ritorsione: ti ha colpito?')).toBeInTheDocument()
    showUndoToastSpy.mock.calls[0][0].onUndo()
    await waitFor(() => expect(undoHpSpy).toHaveBeenCalledWith(7, 'op1'))
    await waitFor(() => expect(screen.queryByText('Ritorsione: ti ha colpito?')).toBeNull())
  })

  it('offers nothing when the damage opens no reaction', async () => {
    getChar.mockResolvedValue(withReaction())
    updateHpSpy.mockResolvedValue(withReaction({ reactions: [], hp_undo_id: 'op1' }))
    renderWithProviders(<HP />)
    await userEvent.type(await screen.findByTestId('hp-value'), '4')
    await userEvent.click(screen.getByTestId('hp-apply'))
    await waitFor(() => expect(updateHpSpy).toHaveBeenCalled())
    expect(screen.queryByText('character.hp.reaction_title')).toBeNull()
  })
})

import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import HP from '@/pages/HP'

// Spies hoisted so the vi.mock factories can close over them.
const {
  getChar, updateHpSpy, restSpy, reviveSpy, updateDeathSavesSpy,
  rollDeathSaveSpy, spendHitDiceSpy, showUndoToastSpy, toastWarning, playAndCollect,
} = vi.hoisted(() => ({
  getChar: vi.fn(),
  updateHpSpy: vi.fn(),
  restSpy: vi.fn(),
  reviveSpy: vi.fn(),
  updateDeathSavesSpy: vi.fn(),
  rollDeathSaveSpy: vi.fn(),
  spendHitDiceSpy: vi.fn(),
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
      spendHitDice: spendHitDiceSpy,
    },
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
vi.mock('@/auth/telegram', () => ({ haptic: { success: () => {}, error: () => {} } }))
vi.mock('@/styles/motion', () => ({ spring: new Proxy({}, { get: () => ({}) }) }))
vi.mock('@/dice/useDiceAnimation', () => ({ useDiceAnimation: () => ({ playAndCollect }) }))
vi.mock('@/store/diceSettings', () => ({ useDiceSettings: (sel: (s: { animate3d: boolean }) => unknown) => sel({ animate3d: false }) }))
vi.mock('@/hooks/useReducedMotion', () => ({ useReducedMotion: () => true }))
vi.mock('@/components/ui/UndoToast', () => ({ showUndoToast: showUndoToastSpy }))

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
    default: (p: { open: boolean; onConfirm: () => void; confirmLabel: string }) =>
      p.open
        ? React.createElement('div', { 'data-testid': 'confirm-sheet' },
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
    }) =>
      React.createElement('div', { 'data-testid': 'hp-op-form' },
        React.createElement('input', { 'data-testid': 'hp-value', value: p.value, onChange: (e: { target: { value: string } }) => p.setValue(e.target.value) }),
        React.createElement('button', { 'data-testid': 'hp-apply', onClick: p.onApply }, 'apply'),
        React.createElement('button', { 'data-testid': 'hp-quick-heal', onClick: () => p.hpMutate({ op: 'heal', val: 3 }) }, 'quick'),
        React.createElement('button', { 'data-testid': 'hp-crit', onClick: () => p.setCrit(true) }, 'crit'),
      ),
  }
})
vi.mock('@/pages/hp/DeathSaves', async () => {
  const React = await import('react')
  return {
    default: (p: { onRoll: () => void; onAction: (a: string) => void }) =>
      React.createElement('div', { 'data-testid': 'death-saves' },
        React.createElement('button', { 'data-testid': 'ds-roll', onClick: p.onRoll }, 'roll'),
        React.createElement('button', { 'data-testid': 'ds-action', onClick: () => p.onAction('mark_success') }, 'action'),
      ),
  }
})
vi.mock('@/pages/hp/HitDiceModal', async () => {
  const React = await import('react')
  return {
    default: (p: { classes: { id: number }[]; onSpend: (cid: number, n: number) => void; onConfirmRest: () => void }) =>
      React.createElement('div', { 'data-testid': 'hit-dice-modal' },
        React.createElement('button', { 'data-testid': 'hd-spend', onClick: () => p.onSpend(p.classes[0].id, 2) }, 'spend'),
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

  it('handleApply parses the value and calls updateHp(id, op, val, wasCritical=false) when alive', async () => {
    getChar.mockResolvedValue(aliveChar)
    updateHpSpy.mockResolvedValue(aliveChar)
    renderWithProviders(<HP />)
    await screen.findByTestId('hp-op-form')

    await userEvent.type(screen.getByTestId('hp-value'), '5')
    await userEvent.click(screen.getByTestId('hp-apply'))
    await waitFor(() => expect(updateHpSpy).toHaveBeenCalledWith(7, 'damage', 5, false))
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
    updateHpSpy.mockResolvedValue(aliveChar)
    renderWithProviders(<HP />)
    await screen.findByTestId('hp-op-form')

    await userEvent.click(screen.getByTestId('hp-quick-heal'))
    await waitFor(() => expect(updateHpSpy).toHaveBeenCalledWith(7, 'heal', 3, false))
    await waitFor(() => expect(showUndoToastSpy).toHaveBeenCalled())
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
    await waitFor(() => expect(spendHitDiceSpy).toHaveBeenCalledWith(7, 1, 2))
    await userEvent.click(screen.getByTestId('hd-rest'))
    await waitFor(() => expect(restSpy).toHaveBeenCalledWith(7, 'short'))

    // long rest button → opens ConfirmSheet → confirm
    await userEvent.click(screen.getByRole('button', { name: 'character.hp.long_rest' }))
    await userEvent.click(await screen.findByTestId('confirm-ok'))
    await waitFor(() => expect(restSpy).toHaveBeenCalledWith(7, 'long'))
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
})

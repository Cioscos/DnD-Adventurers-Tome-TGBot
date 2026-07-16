import { describe, it, expect, vi } from 'vitest'
import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import HpOperationForm from '@/pages/hp/HpOperationForm'

type HPOp = 'damage' | 'heal' | 'set_max' | 'set_current' | 'set_temp'

// i18n → keys are returned verbatim, so assertions are locale-free.
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
// framer-motion: strip motion props, keep DOM-valid ones (onClick survives).
// The per-tag cache matters: real framer-motion's `m.button` is a stable
// component reference across renders. Without caching here, every access of
// `m.button` (e.g. from Pressable's own JSX, re-evaluated on every render)
// mints a *new* function identity, which React treats as a different
// component type — unmounting/remounting the DOM node on every state update.
// That breaks any test holding a pre-interaction element reference and
// re-asserting on it post-interaction (e.g. an aria-pressed toggle check).
vi.mock('framer-motion', async () => {
  const React = await import('react')
  const MOTION = new Set(['initial', 'animate', 'exit', 'transition', 'variants', 'whileTap', 'whileHover', 'drag', 'layout'])
  const make = (tag: string) => (props: Record<string, unknown>) => {
    const clean: Record<string, unknown> = {}
    for (const k in props) if (!MOTION.has(k)) clean[k] = props[k]
    return React.createElement(tag, clean)
  }
  const cache = new Map<string, ReturnType<typeof make>>()
  return {
    m: new Proxy({}, {
      get: (_t: object, tag: string | symbol) => {
        const key = String(tag)
        if (!cache.has(key)) cache.set(key, make(key))
        return cache.get(key)!
      },
    }),
  }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/components/ui/Surface', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return {
    default: (p: { onClick?: () => void; disabled?: boolean; children?: unknown }) =>
      React.createElement('button', { onClick: p.onClick, disabled: p.disabled }, p.children),
  }
})
vi.mock('@/components/ui/Input', async () => {
  const React = await import('react')
  return {
    default: (p: { value: string; onChange: (v: string) => void }) =>
      React.createElement('input', {
        'data-testid': 'hp-input',
        value: p.value,
        onChange: (e: { target: { value: string } }) => p.onChange(e.target.value),
      }),
  }
})

// HpOperationForm is fully controlled; a stateful harness reproduces the parent
// so interactions feed back into the UI realistically.
function Harness({
  onApply = () => {},
  hpMutate = () => {},
  atZero = false,
  isPending = false,
}: {
  onApply?: () => void
  hpMutate?: (a: { op: HPOp; val: number }) => void
  atZero?: boolean
  isPending?: boolean
}) {
  const [activeOp, setActiveOp] = useState<HPOp>('damage')
  const [value, setValue] = useState('')
  const [crit, setCrit] = useState(false)
  return (
    <HpOperationForm
      activeOp={activeOp}
      setActiveOp={setActiveOp}
      value={value}
      setValue={setValue}
      onApply={onApply}
      isPending={isPending}
      hpMutate={hpMutate}
      atZero={atZero}
      crit={crit}
      setCrit={setCrit}
    />
  )
}

// − is the U+2212 MINUS SIGN used by the component for damage shortcuts.
const MINUS = '−'

describe('HpOperationForm', () => {
  it('renders all five HP operations (damage/heal/current/max/temp)', () => {
    render(<Harness />)
    for (const key of [
      'character.hp.damage_short',
      'character.hp.heal_short',
      'character.hp.current_short',
      'character.hp.max_short',
      'character.hp.temp_short',
    ]) {
      expect(screen.getByText(key)).toBeInTheDocument()
    }
  })

  it('quick shortcuts show a − sign in damage mode and flip to + after switching to heal', async () => {
    render(<Harness />)
    expect(screen.getByText(`${MINUS}5`)).toBeInTheDocument()
    await userEvent.click(screen.getByText('character.hp.heal_short'))
    expect(screen.getByText('+5')).toBeInTheDocument()
    expect(screen.queryByText(`${MINUS}5`)).not.toBeInTheDocument()
  })

  it('a quick shortcut fires hpMutate with the active op and that value', async () => {
    const hpMutate = vi.fn()
    render(<Harness hpMutate={hpMutate} />)
    await userEvent.click(screen.getByText(`${MINUS}10`))
    expect(hpMutate).toHaveBeenCalledWith({ op: 'damage', val: 10 })
  })

  it('confirm is disabled until a value is typed, then calls onApply', async () => {
    const onApply = vi.fn()
    render(<Harness onApply={onApply} />)
    const confirm = screen.getByRole('button', { name: 'common.confirm' })
    expect(confirm).toBeDisabled()
    await userEvent.type(screen.getByTestId('hp-input'), '7')
    expect(confirm).toBeEnabled()
    await userEvent.click(confirm)
    expect(onApply).toHaveBeenCalledTimes(1)
  })

  it('hides the critical-hit toggle unless damaging at 0 HP', () => {
    render(<Harness atZero={false} />)
    expect(screen.queryByText('character.hp.critical_hit')).not.toBeInTheDocument()
  })

  it('shows the critical-hit toggle at 0 HP and flips aria-pressed on click (D&D 5e crit-while-dying)', async () => {
    render(<Harness atZero={true} />)
    const crit = screen.getByRole('button', { name: 'character.hp.critical_hit' })
    expect(crit).toHaveAttribute('aria-pressed', 'false')
    await userEvent.click(crit)
    expect(crit).toHaveAttribute('aria-pressed', 'true')
  })
})

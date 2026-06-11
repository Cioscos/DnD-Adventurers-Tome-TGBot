import { describe, it, expect, vi } from 'vitest'
import type { ReactNode } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import WeaponAttackModal, { type WeaponAttackResult } from '@/components/WeaponAttackModal'

// framer-motion: WeaponAttackModal uses `m.div` for the to-hit / damage blocks.
// Strip motion-only props and render plain DOM (jsdom lacks matchMedia).
vi.mock('framer-motion', async () => {
  const React = await import('react')
  const MOTION_PROPS = new Set([
    'initial', 'animate', 'exit', 'transition', 'variants',
    'whileHover', 'whileTap', 'whileInView', 'whileFocus', 'whileDrag',
    'drag', 'dragConstraints', 'layout', 'layoutId',
  ])
  const make = (tag: string) => (props: Record<string, unknown>) => {
    const clean: Record<string, unknown> = {}
    for (const k in props) if (!MOTION_PROPS.has(k)) clean[k] = props[k]
    return React.createElement(tag, clean)
  }
  return {
    useReducedMotion: () => false,
    m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }),
  }
})

// ResultDialog is a sibling presentational shell (framer-motion + overlay store +
// ornaments). Mock it to expose the props WeaponAttackModal feeds it (accent,
// pulse, title, subtitle, extraActions) and render its children verbatim, so the
// assertions target WeaponAttackModal's own logic, not the dialog chrome.
vi.mock('@/components/ui/ResultDialog', async () => {
  const React = await import('react')
  return {
    default: (p: {
      title?: ReactNode; subtitle?: ReactNode; extraActions?: ReactNode;
      children?: ReactNode; accent?: string; pulse?: boolean;
    }) =>
      React.createElement(
        'div',
        { 'data-testid': 'result-dialog', 'data-accent': p.accent, 'data-pulse': String(!!p.pulse) },
        React.createElement('div', { 'data-testid': 'rd-title' }, p.title),
        p.subtitle ? React.createElement('div', { 'data-testid': 'rd-subtitle' }, p.subtitle) : null,
        p.extraActions ? React.createElement('div', { 'data-testid': 'rd-extra' }, p.extraActions) : null,
        React.createElement('div', { 'data-testid': 'rd-body' }, p.children),
      ),
  }
})

vi.mock('@/components/InspirationRerollButton', async () => {
  const React = await import('react')
  return {
    default: (p: { available?: boolean; pending?: boolean; onClick: () => void }) =>
      p.available === false
        ? null
        : React.createElement(
            'button',
            { 'data-testid': 'inspiration-reroll', disabled: p.pending, onClick: p.onClick },
            'reroll',
          ),
  }
})

const baseResult: WeaponAttackResult = {
  weapon_name: 'Longsword',
  to_hit_die: 14,
  to_hit_bonus: 5,
  to_hit_total: 19,
  is_critical: false,
  is_fumble: false,
  damage_dice: '1d8',
  damage_rolls: [6],
  damage_bonus: 3,
  damage_total: 9,
}

describe('WeaponAttackModal', () => {
  it('renders weapon name, to-hit total and damage total on a normal hit (emerald)', () => {
    render(<WeaponAttackModal result={baseResult} onClose={() => {}} />)
    expect(screen.getByTestId('rd-title')).toHaveTextContent('Longsword')
    expect(screen.getByText('19')).toBeInTheDocument() // to_hit_total
    expect(screen.getByText('9')).toBeInTheDocument() // damage_total
    expect(screen.queryByText('Critico!')).not.toBeInTheDocument()
    expect(screen.queryByText('Fumble!')).not.toBeInTheDocument()
    const dialog = screen.getByTestId('result-dialog')
    expect(dialog).toHaveAttribute('data-accent', 'emerald')
    expect(dialog).toHaveAttribute('data-pulse', 'false')
  })

  it('shows the CRITICO banner, gold accent + pulse, and a "(critico)" damage label', () => {
    const crit: WeaponAttackResult = {
      ...baseResult,
      is_critical: true,
      damage_dice: '2d8',
      damage_rolls: [6, 7],
      damage_total: 16,
    }
    render(<WeaponAttackModal result={crit} onClose={() => {}} />)
    expect(screen.getByText('Critico!')).toBeInTheDocument()
    expect(screen.getByText(/\(critico\)/)).toBeInTheDocument() // doubled-dice damage label
    expect(screen.getByText('16')).toBeInTheDocument()
    const dialog = screen.getByTestId('result-dialog')
    expect(dialog).toHaveAttribute('data-accent', 'gold')
    expect(dialog).toHaveAttribute('data-pulse', 'true')
  })

  it('on a fumble: crimson accent, FUMBLE banner, and the damage block is hidden', () => {
    const fumble: WeaponAttackResult = { ...baseResult, is_fumble: true }
    render(<WeaponAttackModal result={fumble} onClose={() => {}} />)
    expect(screen.getByText('Fumble!')).toBeInTheDocument()
    expect(screen.getByTestId('result-dialog')).toHaveAttribute('data-accent', 'crimson')
    expect(screen.getByText('19')).toBeInTheDocument() // to-hit still shown
    expect(screen.queryByText('9')).not.toBeInTheDocument() // damage_total NOT rendered on fumble
  })

  it('renders the inspiration reroll button and fires onInspirationReroll on click', async () => {
    const onReroll = vi.fn()
    render(
      <WeaponAttackModal
        result={baseResult}
        onClose={() => {}}
        inspirationAvailable
        onInspirationReroll={onReroll}
      />,
    )
    const btn = screen.getByTestId('inspiration-reroll')
    await userEvent.click(btn)
    expect(onReroll).toHaveBeenCalledTimes(1)
  })

  it('hides the reroll button and shows the reroll subtitle once wasRerolled', () => {
    render(
      <WeaponAttackModal
        result={baseResult}
        onClose={() => {}}
        inspirationAvailable
        wasRerolled
        onInspirationReroll={() => {}}
      />,
    )
    expect(screen.queryByTestId('inspiration-reroll')).not.toBeInTheDocument()
    expect(screen.getByTestId('rd-subtitle')).toBeInTheDocument()
  })

  it('does not show the reroll button when no onInspirationReroll handler is given', () => {
    render(<WeaponAttackModal result={baseResult} onClose={() => {}} inspirationAvailable />)
    expect(screen.queryByTestId('inspiration-reroll')).not.toBeInTheDocument()
  })

  // Contract / documented 🟠 gap (lotto 4 finding): the FE WeaponAttackResult type
  // OMITS the optional `homebrew_notifications` array that the BE attack endpoints
  // return. The notifications are surfaced by the global MutationCache interceptor
  // (read dynamically, not from the static type), so the omission is non-functional
  // — passing the extra field at runtime must not break the render.
  it('declares exactly the 10 BE fields (no homebrew_notifications) yet renders when BE sends it', () => {
    const keys = Object.keys(baseResult).sort()
    expect(keys).toEqual([
      'damage_bonus', 'damage_dice', 'damage_rolls', 'damage_total',
      'is_critical', 'is_fumble', 'to_hit_bonus', 'to_hit_die', 'to_hit_total', 'weapon_name',
    ])
    expect(keys).not.toContain('homebrew_notifications')

    const withExtra = {
      ...baseResult,
      homebrew_notifications: [{ rule_name: 'Qualità & Usura' }],
    } as WeaponAttackResult
    render(<WeaponAttackModal result={withExtra} onClose={() => {}} />)
    expect(screen.getByText('19')).toBeInTheDocument()
    expect(screen.getByText('9')).toBeInTheDocument()
  })
})

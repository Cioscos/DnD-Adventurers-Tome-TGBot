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

// Le opzioni dopo il danno hanno il loro test: qui conta cosa riceve e come aggiorna l'esito.
vi.mock('@/components/rules/AfterDamageOptions', async () => {
  const React = await import('react')
  return {
    default: (p: { query: { roll: string }; dice: { value: number; sides: number }[]; onResult: (r: unknown) => void }) =>
      React.createElement('button', {
        'data-testid': 'after-damage',
        'data-roll': p.query.roll,
        'data-dice': p.dice.map((d) => `${d.value}/d${d.sides}`).join(','),
        onClick: () => p.onResult({ ...baseResult, damage_rolls: [8], damage_total: 11 }),
      }, 'reroll-damage'),
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

  it('names the damage type of an unarmed strike and says when it counts as magical (Ki-Empowered Strikes)', () => {
    const { rerender } = render(<WeaponAttackModal result={{ ...baseResult, damage_type: 'bludgeoning' }} onClose={() => {}} />)
    expect(screen.getByTestId('damage-type')).toHaveTextContent('Contundente')
    expect(screen.queryByText(/Colpo magico/)).not.toBeInTheDocument()
    rerender(<WeaponAttackModal result={{ ...baseResult, damage_type: 'fire', is_magic: true }} onClose={() => {}} />)
    expect(screen.getByTestId('damage-type')).toHaveTextContent('Fuoco')
    expect(screen.getByTestId('damage-type')).toHaveTextContent('Colpo magico')
  })

  it('says a weapon strike is magical even though the weapon has no damage type of its own (Sacred Weapon)', () => {
    render(<WeaponAttackModal result={{ ...baseResult, is_magic: true }} onClose={() => {}} />)
    expect(screen.getByTestId('damage-type')).toHaveTextContent('Colpo magico')
  })

  it('shows no damage type line for a weapon attack', () => {
    render(<WeaponAttackModal result={baseResult} onClose={() => {}} />)
    expect(screen.queryByTestId('damage-type')).not.toBeInTheDocument()
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

  it('shows remaining ammunition', () => {
    const r: WeaponAttackResult = { ...baseResult, ammo: { item_id: 3, name: 'Frecce', remaining: 17 } }
    render(<WeaponAttackModal result={r} onClose={() => {}} />)
    expect(screen.getByText('Frecce: 17')).toBeInTheDocument()
  })

  it('shows the missing ammunition warning', () => {
    render(<WeaponAttackModal result={{ ...baseResult, ammo_missing: true }} onClose={() => {}} />)
    expect(screen.getByText('Munizioni esaurite o non equipaggiate: scala tu le munizioni')).toBeInTheDocument()
  })

  it('says which low dice a privilege had rerolled (Great Weapon Fighting)', () => {
    render(<WeaponAttackModal result={{ ...baseResult, damage_rolls: [4, 6], rerolled: [[1, 4], [2, 6]] }} onClose={() => {}} />)
    expect(screen.getByTestId('rerolled-dice')).toHaveTextContent('1 → 4, 2 → 6')
  })

  it('shows no rerolled line when nothing was rerolled', () => {
    render(<WeaponAttackModal result={baseResult} onClose={() => {}} />)
    expect(screen.queryByTestId('rerolled-dice')).not.toBeInTheDocument()
  })

  it('shows neither line without ammo info', () => {
    render(<WeaponAttackModal result={baseResult} onClose={() => {}} />)
    expect(screen.queryByText(/munizion/i)).not.toBeInTheDocument()
  })

  it('grapple and shove show the DC, without to-hit or damage', () => {
    render(<WeaponAttackModal onClose={vi.fn()} inspirationAvailable onInspirationReroll={vi.fn()} result={{
      weapon_name: 'x', to_hit_die: 0, to_hit_bonus: 0, to_hit_total: 0, is_critical: false, is_fumble: false,
      damage_dice: '', damage_rolls: [], damage_bonus: 0, damage_total: 0, effect: 'grapple', save_dc: 13,
    }} />)
    expect(screen.getByTestId('unarmed-effect')).toBeInTheDocument()
    expect(screen.queryByText('character.attack.to_hit')).toBeNull()
    expect(screen.queryByTestId('inspiration-reroll')).toBeNull()
  })

  it('a grazed miss shows its damage even on a natural 1', () => {
    render(<WeaponAttackModal onClose={vi.fn()} result={{
      weapon_name: 'x', to_hit_die: 1, to_hit_bonus: 5, to_hit_total: 6, is_critical: false, is_fumble: true,
      damage_dice: '2d6', damage_rolls: [], damage_bonus: 3, damage_total: 3, grazed: true,
    }} />)
    expect(screen.getByTestId('grazed-damage')).toHaveTextContent('3')
  })

  it('a declared miss with no damage (Studied Attacks) says it was noted and shows no damage number', () => {
    render(<WeaponAttackModal onClose={vi.fn()} result={{
      weapon_name: 'x', to_hit_die: 5, to_hit_bonus: 5, to_hit_total: 10, is_critical: false, is_fumble: false,
      damage_dice: '1d6', damage_rolls: [], damage_bonus: 0, damage_total: 0, grazed: true,
    }} />)
    expect(screen.getByTestId('grazed-damage')).toHaveTextContent('Mancato: segnato, nessun danno')
    expect(screen.getByTestId('grazed-damage')).not.toHaveTextContent('Graze')
  })

  it('offers the damage reroll with the weapon dice and shows the rerolled damage', async () => {
    render(<WeaponAttackModal result={{ ...baseResult, damage_dice: '2d8', damage_rolls: [3, 4], damage_total: 10 }} charId={7} onClose={() => {}} />)
    const reroll = screen.getByTestId('after-damage')
    expect(reroll).toHaveAttribute('data-roll', 'weapon_damage')
    expect(reroll).toHaveAttribute('data-dice', '3/d8,4/d8')
    await userEvent.click(reroll)
    expect(screen.getByText('11')).toBeInTheDocument()  // il danno ritirato sostituisce quello del tiro
  })

  it('offers the damage reroll when the second step handed over the final damage, option dice included', () => {
    // Dopo POST /attack/{id}/damage il server non manda piu `attack_id` e dice i dadi con i loro lati.
    render(<WeaponAttackModal result={{
      ...baseResult, damage_dice: '1d8', damage_rolls: [3], damage_total: 12,
      reroll_dice: [[8, 3], [6, 5], [6, 1]],
    }} charId={7} onClose={() => {}} />)
    expect(screen.getByTestId('after-damage')).toHaveAttribute('data-dice', '3/d8,5/d6,1/d6')
  })

  it('offers the damage reroll on a flat base damage ("1") through the dice the server lists', () => {
    // Senza facce nel testo del danno (`dieSides` sarebbe NaN) i dadi ritirabili sono quelli di `reroll_dice`.
    render(<WeaponAttackModal result={{
      ...baseResult, damage_dice: '1', damage_rolls: [1], damage_total: 6, reroll_dice: [[6, 4]],
    }} charId={7} onClose={() => {}} />)
    expect(screen.getByTestId('after-damage')).toHaveAttribute('data-dice', '4/d6')
  })

  it('has no damage reroll without a character, on a miss, on a flat damage or while the damage is pending', () => {
    const { rerender } = render(<WeaponAttackModal result={baseResult} onClose={() => {}} />)
    expect(screen.queryByTestId('after-damage')).toBeNull()
    for (const over of [{ is_fumble: true }, { damage_dice: '1', damage_rolls: [1] }, { attack_id: 'a' }] as const) {
      rerender(<WeaponAttackModal result={{ ...baseResult, ...over }} charId={7} onClose={() => {}} />)
      expect(screen.queryByTestId('after-damage')).toBeNull()
    }
  })
})

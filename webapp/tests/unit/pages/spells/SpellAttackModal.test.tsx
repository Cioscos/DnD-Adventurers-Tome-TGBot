import { describe, it, expect, vi } from 'vitest'
import type { ReactNode } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SpellAttackModal from '@/pages/spells/SpellAttackModal'
import type { SpellAttackResult } from '@/types'

vi.mock('framer-motion', async () => {
  const React = await import('react')
  const MOTION = new Set(['initial', 'animate', 'exit', 'transition', 'variants', 'whileTap', 'whileHover', 'layout'])
  const make = (tag: string) => (props: Record<string, unknown>) => {
    const clean: Record<string, unknown> = {}
    for (const k in props) if (!MOTION.has(k)) clean[k] = props[k]
    return React.createElement(tag, clean)
  }
  return { m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }) }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  const t = (k: string, o?: Record<string, unknown>) =>
    o && !('defaultValue' in o) ? `${k}(${Object.entries(o).map(([a, b]) => `${a}=${String(b)}`).join(',')})` : k
  return { ...actual, useTranslation: () => ({ t, i18n: { language: 'it' } }) }
})
vi.mock('@/components/ui/ResultDialog', async () => {
  const React = await import('react')
  return {
    default: (p: { title?: ReactNode; subtitle?: ReactNode; extraActions?: ReactNode; children?: ReactNode; accent?: string }) =>
      React.createElement('div', { 'data-testid': 'result-dialog', 'data-accent': p.accent },
        React.createElement('div', null, p.title),
        p.subtitle ? React.createElement('div', null, p.subtitle) : null,
        React.createElement('div', null, p.children),
        p.extraActions ? React.createElement('div', null, p.extraActions) : null,
      ),
  }
})
vi.mock('@/components/InspirationRerollButton', async () => {
  const React = await import('react')
  return { default: (p: { onClick: () => void }) => React.createElement('button', { onClick: p.onClick }, 'insp-reroll') }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return { default: (p: { onClick?: () => void; children?: unknown }) => React.createElement('button', { onClick: p.onClick }, p.children) }
})

const base = {
  spell_name: 'Dardo di Fuoco', to_hit_die: 12, to_hit_bonus: 6, to_hit_total: 18,
  is_critical: false, is_fumble: false, caster_class: 'Wizard', character: {},
} as unknown as SpellAttackResult

function renderModal(over: Partial<SpellAttackResult> = {}, props: Record<string, unknown> = {}) {
  const onRollDamage = vi.fn()
  const onClose = vi.fn()
  const onInspirationReroll = vi.fn()
  render(
    <SpellAttackModal
      result={{ ...base, ...over }}
      canRollDamage
      onRollDamage={onRollDamage}
      onClose={onClose}
      inspirationAvailable
      onInspirationReroll={onInspirationReroll}
      {...props}
    />,
  )
  return { onRollDamage, onClose, onInspirationReroll }
}

describe('SpellAttackModal', () => {
  it('shows the total, the die breakdown and the caster', async () => {
    const { onRollDamage, onClose } = renderModal()
    expect(screen.getByText('18')).toBeInTheDocument()
    expect(screen.getByText('d20 (12) +6')).toBeInTheDocument()
    expect(screen.getByText('character.spells.attack_caster(class=dnd.classes.wizard,bonus=+6)')).toBeInTheDocument()
    expect(screen.getByTestId('result-dialog').dataset.accent).toBe('emerald')
    await userEvent.click(screen.getByText('character.spells.attack_roll_damage'))
    expect(onRollDamage).toHaveBeenCalled()
    await userEvent.click(screen.getByText('common.close'))
    expect(onClose).toHaveBeenCalled()
  })

  it('shows the critical banner on a natural 20', () => {
    renderModal({ to_hit_die: 20, to_hit_total: 26, is_critical: true })
    expect(screen.getByText('character.dice.critical_banner')).toBeInTheDocument()
    expect(screen.getByTestId('result-dialog').dataset.accent).toBe('gold')
  })

  it('offers no damage after a natural 1', () => {
    renderModal({ to_hit_die: 1, to_hit_total: 7, is_fumble: true })
    expect(screen.getByText('character.dice.fumble_banner')).toBeInTheDocument()
    expect(screen.queryByText('character.spells.attack_roll_damage')).toBeNull()
    expect(screen.getByText('common.close')).toBeInTheDocument()
  })

  it('offers no damage when the spell has no damage dice', () => {
    renderModal({}, { canRollDamage: false })
    expect(screen.queryByText('character.spells.attack_roll_damage')).toBeNull()
  })

  it('rerolls with inspiration once, then shows the badge', async () => {
    const { onInspirationReroll } = renderModal()
    await userEvent.click(screen.getByText('insp-reroll'))
    expect(onInspirationReroll).toHaveBeenCalled()
  })

  it('hides the reroll after a reroll and shows the badge', () => {
    renderModal({}, { wasRerolled: true })
    expect(screen.queryByText('insp-reroll')).toBeNull()
    expect(screen.getByText('character.inspiration.reroll_badge')).toBeInTheDocument()
  })
})

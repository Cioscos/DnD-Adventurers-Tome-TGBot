import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DamageTypePicker from '@/components/ui/DamageTypePicker'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('framer-motion', async () => {
  const React = await import('react')
  const MOTION = new Set(['initial', 'animate', 'exit', 'transition', 'variants', 'whileTap', 'whileHover', 'layout'])
  const make = (tag: string) => (props: Record<string, unknown>) => {
    const clean: Record<string, unknown> = {}
    for (const k in props) if (!MOTION.has(k)) clean[k] = props[k]
    return React.createElement(tag, clean)
  }
  // Cache per tag: identità stabile dei componenti, altrimenti ogni re-render
  // smonta/rimonta il sottoalbero (input che perdono focus a metà digitazione).
  const cache: Record<string, unknown> = {}
  return { m: new Proxy({}, { get: (_t: object, tag: string | symbol) => (cache[String(tag)] ??= make(String(tag))) }) }
})

const FIRE = 'character.inventory.damage_types.dmg_fire'

describe('DamageTypePicker', () => {
  it('item format: marks the prefixed slug and emits prefixed slugs', async () => {
    const onChange = vi.fn()
    render(<DamageTypePicker value="dmg_slashing" onChange={onChange} valueFormat="item" />)
    expect(screen.getByRole('radio', { name: 'character.inventory.damage_types.dmg_slashing' }))
      .toHaveAttribute('aria-checked', 'true')
    await userEvent.click(screen.getByRole('radio', { name: FIRE }))
    expect(onChange).toHaveBeenCalledWith('dmg_fire')
  })

  it('spell format: marks the bare slug and emits bare slugs', async () => {
    const onChange = vi.fn()
    render(<DamageTypePicker value="fire" onChange={onChange} valueFormat="spell" />)
    expect(screen.getByRole('radio', { name: FIRE })).toHaveAttribute('aria-checked', 'true')
    await userEvent.click(screen.getByRole('radio', { name: 'character.inventory.damage_types.dmg_cold' }))
    expect(onChange).toHaveBeenCalledWith('cold')
  })

  it('keeps an unmappable legacy value visible as a raw extra chip', () => {
    render(<DamageTypePicker value="fuoco" onChange={() => {}} valueFormat="spell" />)
    expect(screen.getByRole('radio', { name: 'fuoco' })).toHaveAttribute('aria-checked', 'true')
  })

  it('allowEmpty: re-tapping the active chip clears the value', async () => {
    const onChange = vi.fn()
    render(<DamageTypePicker value="fire" onChange={onChange} valueFormat="spell" allowEmpty />)
    await userEvent.click(screen.getByRole('radio', { name: FIRE }))
    expect(onChange).toHaveBeenCalledWith('')
  })

  it('without allowEmpty: re-tapping keeps the value selected', async () => {
    const onChange = vi.fn()
    render(<DamageTypePicker value="dmg_fire" onChange={onChange} valueFormat="item" />)
    await userEvent.click(screen.getByRole('radio', { name: FIRE }))
    expect(onChange).toHaveBeenCalledWith('dmg_fire')
  })
})

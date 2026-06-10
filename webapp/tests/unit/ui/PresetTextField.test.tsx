import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PresetTextField from '@/components/ui/PresetTextField'

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
  return {
    m: new Proxy({}, { get: (_t: object, tag: string | symbol) => (cache[String(tag)] ??= make(String(tag))) }),
    AnimatePresence: (p: { children?: unknown }) => React.createElement(React.Fragment, null, p.children),
  }
})

const PRESETS = ['1 azione', '1 azione bonus', '1 reazione'] as const

function setup(value: string, onChange = vi.fn()) {
  render(
    <PresetTextField
      label="Tempo di lancio"
      presets={PRESETS}
      value={value}
      onChange={onChange}
      customLabel="Altro…"
      placeholder="es. 1 ora"
    />,
  )
  return onChange
}

describe('PresetTextField', () => {
  it('highlights the chip matching the stored value (SRD byte-match)', () => {
    setup('1 azione')
    expect(screen.getByRole('radio', { name: '1 azione' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('radio', { name: 'Altro…' })).toHaveAttribute('aria-checked', 'false')
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('lands an out-of-preset value on the custom chip with the text editable', () => {
    setup('Cono 4,5 m')
    expect(screen.getByRole('radio', { name: 'Altro…' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('textbox')).toHaveValue('Cono 4,5 m')
  })

  it('selecting a preset emits its exact string', async () => {
    const onChange = setup('')
    await userEvent.click(screen.getByRole('radio', { name: '1 reazione' }))
    expect(onChange).toHaveBeenCalledWith('1 reazione')
  })

  it('re-tapping the selected preset clears the value (no pre-fill convention)', async () => {
    const onChange = setup('1 azione')
    await userEvent.click(screen.getByRole('radio', { name: '1 azione' }))
    expect(onChange).toHaveBeenCalledWith('')
  })

  it('tapping the custom chip from a preset clears the value and reveals the input', async () => {
    const onChange = setup('1 azione')
    await userEvent.click(screen.getByRole('radio', { name: 'Altro…' }))
    expect(onChange).toHaveBeenCalledWith('')
    expect(screen.getByRole('textbox')).toBeInTheDocument()
  })

  it('typing in the custom input forwards the free text', async () => {
    const onChange = setup('Cono 4,5 m')
    await userEvent.type(screen.getByRole('textbox'), '!')
    expect(onChange).toHaveBeenCalledWith('Cono 4,5 m!')
  })
})

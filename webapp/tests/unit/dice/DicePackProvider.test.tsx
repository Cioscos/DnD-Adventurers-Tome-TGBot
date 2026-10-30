import { describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import { useContext } from 'react'

const settings = vi.hoisted(() => ({ animate3d: true }))

vi.mock('@/store/diceSettings', () => ({
  useDiceSettings: (sel: (s: Record<string, unknown>) => unknown) =>
    sel({ packId: 'default', setPackId: () => {}, animate3d: settings.animate3d }),
}))
vi.mock('@/hooks/useReducedMotion', () => ({ useReducedMotion: () => false }))
const loadPackWithFallback = vi.hoisted(() => vi.fn(() => new Promise(() => {})))
vi.mock('@/dice/packs/loader', () => ({ loadPackWithFallback, disposePack: vi.fn() }))

import { DicePackProvider } from '@/dice/packs/DicePackProvider'
import { DicePackCtx } from '@/dice/packs/dicePackContext'

function Probe() {
  const { loading } = useContext(DicePackCtx)
  return <span>{loading ? 'loading' : 'idle'}</span>
}

describe('DicePackProvider', () => {
  it('stops showing the loading state when the 3D dice are turned off mid-download', async () => {
    const { rerender } = render(
      <DicePackProvider>
        <Probe />
      </DicePackProvider>,
    )
    expect(screen.getByText('loading')).toBeInTheDocument()
    settings.animate3d = false
    rerender(
      <DicePackProvider>
        <Probe />
      </DicePackProvider>,
    )
    await act(async () => {})
    expect(screen.getByText('idle')).toBeInTheDocument()
    expect(loadPackWithFallback).not.toHaveBeenCalled()
    settings.animate3d = true
  })
})

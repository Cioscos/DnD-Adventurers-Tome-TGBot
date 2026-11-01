import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import RoundRibbon from '@/components/session/RoundRibbon'
import type { CombatantLive } from '@/types'

const mk = (id: number, over: Partial<CombatantLive> = {}): CombatantLive => ({
  id, kind: 'monster', name: `C${id}`, initiative: 20 - id, initiative_die: null,
  initiative_mod: 0, sort_order: id, is_dead: false, conditions: {},
  current_hp: null, max_hp: null, ac: null, hp_bucket: null, ...over,
})

const segs = () => screen.getAllByTestId('ribbon-seg')

describe('RoundRibbon', () => {
  it('marks the active combatant and the ones before it as done', () => {
    render(<RoundRibbon combatants={[mk(1), mk(2), mk(3), mk(4)]} activeId={3} myUserId={9} />)
    expect(segs().map((s) => s.dataset.state)).toEqual(['done', 'done', 'active', 'upcoming'])
  })

  it('marks dead combatants as dead regardless of position', () => {
    render(<RoundRibbon combatants={[mk(1), mk(2), mk(3, { is_dead: true })]} activeId={2} myUserId={9} />)
    expect(segs().map((s) => s.dataset.state)).toEqual(['done', 'active', 'dead'])
  })

  it('flags my own PC', () => {
    render(
      <RoundRibbon
        combatants={[mk(1, { kind: 'pc', owner_user_id: 9 }), mk(2, { kind: 'pc', owner_user_id: 7 })]}
        activeId={null}
        myUserId={9}
      />,
    )
    expect(segs()[0].dataset.me).toBe('true')
    expect(segs()[1].dataset.me).toBeUndefined()
    expect(segs().map((s) => s.dataset.state)).toEqual(['upcoming', 'upcoming'])
  })

  it('scrolls horizontally', () => {
    render(<RoundRibbon combatants={[mk(1)]} activeId={1} myUserId={9} />)
    expect(screen.getByTestId('round-ribbon').className).toContain('overflow-x-auto')
  })

  it('scrolls the active segment into view when the turn changes', () => {
    const spy = vi.fn()
    Element.prototype.scrollIntoView = spy
    const list = [mk(1), mk(2), mk(3)]
    const { rerender } = render(<RoundRibbon combatants={list} activeId={1} myUserId={9} />)
    rerender(<RoundRibbon combatants={list} activeId={3} myUserId={9} />)
    expect(spy).toHaveBeenLastCalledWith(expect.objectContaining({ inline: 'center' }))
    expect(spy.mock.contexts.at(-1)).toBe(segs()[2])
  })
})

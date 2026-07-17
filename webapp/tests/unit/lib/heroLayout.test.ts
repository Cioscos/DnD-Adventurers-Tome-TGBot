import { describe, it, expect } from 'vitest'
import { readHeroLayout, HERO_SECTIONS } from '@/lib/heroLayout'

describe('readHeroLayout', () => {
  it('senza settings restituisce il default', () => {
    expect(readHeroLayout(undefined)).toEqual({
      order: ['slots', 'stats', 'quick_actions'],
      hidden: [],
    })
  })

  it('rispetta ordine e hidden salvati', () => {
    const layout = readHeroLayout({
      hero_layout: { order: ['quick_actions', 'slots', 'stats'], hidden: ['slots'] },
    })
    expect(layout.order).toEqual(['quick_actions', 'slots', 'stats'])
    expect(layout.hidden).toEqual(['slots'])
  })

  it('scarta chiavi ignote, accoda le mancanti, deduplica', () => {
    const layout = readHeroLayout({
      hero_layout: { order: ['banana', 'stats', 'stats'], hidden: ['banana', 'stats'] },
    })
    expect(layout.order).toEqual(['stats', 'slots', 'quick_actions'])
    expect(layout.hidden).toEqual(['stats'])
  })

  it('settings malformati (non-oggetto) → default', () => {
    expect(readHeroLayout({ hero_layout: 'x' }).order).toEqual([...HERO_SECTIONS])
  })
})

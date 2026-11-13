import { describe, it, expect } from 'vitest'
import { proficientTools, toolLabel, TOOLS } from '@/lib/tools'

describe('tools catalog', () => {
  it('etichette per lingua e chiave sconosciuta invariata', () => {
    expect(toolLabel('lute', 'it')).toBe('Liuto')
    expect(toolLabel('lute', 'en')).toBe('Lute')
    expect(toolLabel('nope', 'it')).toBe('nope')
  })

  it('competenze in ordine di catalogo, chiavi sconosciute scartate', () => {
    const out = proficientTools({ lute: true, nope: true, alchemists_supplies: 'expert' })
    expect(out.map((x) => [x.tool.key, x.level])).toEqual([['alchemists_supplies', 'expert'], ['lute', true]])
    expect(proficientTools(undefined)).toEqual([])
    expect(TOOLS.length).toBe(39)
  })
})

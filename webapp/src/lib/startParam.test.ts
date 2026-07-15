import { describe, expect, it } from 'vitest'
import { parseStartParam } from './startParam'

describe('parseStartParam', () => {
  it('riconosce i codici join (case-insensitive, uppercased)', () => {
    expect(parseStartParam('join_abc123')).toEqual({ kind: 'join', code: 'ABC123' })
  })

  it('riconosce i token share preservando il case', () => {
    expect(parseStartParam('shr_Ab1-_x9Zq2w')).toEqual({ kind: 'share', token: 'Ab1-_x9Zq2w' })
  })

  it('scarta i valori malformati', () => {
    expect(parseStartParam(undefined)).toBeNull()
    expect(parseStartParam('')).toBeNull()
    expect(parseStartParam('shr_')).toBeNull()
    expect(parseStartParam('shr_ab')).toBeNull() // troppo corto
    expect(parseStartParam('shr_bad!token')).toBeNull() // charset invalido
    expect(parseStartParam('join_toolong1')).toBeNull()
  })
})

import { describe, it, expect } from 'vitest'
import { parseStartParam } from '@/lib/startParam'

describe('parseStartParam', () => {
  it('parses join_<CODE> into a join action with uppercase code', () => {
    expect(parseStartParam('join_ABC123')).toEqual({ kind: 'join', code: 'ABC123' })
    expect(parseStartParam('join_abc123')).toEqual({ kind: 'join', code: 'ABC123' })
    expect(parseStartParam('  join_XY12Z9  ')).toEqual({ kind: 'join', code: 'XY12Z9' })
  })

  it('parses shr_<token> into a share action preserving case', () => {
    expect(parseStartParam('shr_Ab1-_x9Zq2w')).toEqual({ kind: 'share', token: 'Ab1-_x9Zq2w' })
    expect(parseStartParam('  shr_abcdefgh  ')).toEqual({ kind: 'share', token: 'abcdefgh' })
  })

  it('rejects malformed shr_ values', () => {
    expect(parseStartParam('shr_')).toBeNull()
    expect(parseStartParam('shr_ab')).toBeNull() // too short (< 8 chars)
    expect(parseStartParam('shr_bad!token')).toBeNull() // invalid charset
    expect(parseStartParam(`shr_${'a'.repeat(65)}`)).toBeNull() // too long (> 64 chars)
  })

  it('rejects everything else', () => {
    expect(parseStartParam(null)).toBeNull()
    expect(parseStartParam(undefined)).toBeNull()
    expect(parseStartParam('')).toBeNull()
    expect(parseStartParam('join_TOOLONG1')).toBeNull()
    expect(parseStartParam('join_AB12')).toBeNull()
    expect(parseStartParam('join_ABC-12')).toBeNull()
    expect(parseStartParam('share_ABC123')).toBeNull()
  })
})

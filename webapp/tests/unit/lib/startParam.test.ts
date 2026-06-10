import { describe, it, expect } from 'vitest'
import { parseStartParam } from '@/lib/startParam'

describe('parseStartParam', () => {
  it('parses join_<CODE> into a join action with uppercase code', () => {
    expect(parseStartParam('join_ABC123')).toEqual({ kind: 'join', code: 'ABC123' })
    expect(parseStartParam('join_abc123')).toEqual({ kind: 'join', code: 'ABC123' })
    expect(parseStartParam('  join_XY12Z9  ')).toEqual({ kind: 'join', code: 'XY12Z9' })
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

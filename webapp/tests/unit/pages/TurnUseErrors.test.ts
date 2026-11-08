import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import it_ from '@/locales/it.json'
import en from '@/locales/en.json'

describe('Turn: codici d\'errore dei privilegi', () => {
  const src = readFileSync('src/pages/Turn.tsx', 'utf8')
  const codes = [...(/ABILITY_USE_ERRORS = \[([^\]]*)\]/.exec(src)?.[1] ?? '').matchAll(/'(\w+)'/g)].map((m) => m[1])

  it.each([['it', it_], ['en', en]] as const)('ogni codice ha il testo in %s', (_l, loc) => {
    const have = Object.keys((loc as { character: { turn: { use_errors: object } } }).character.turn.use_errors)
    expect(codes.length).toBeGreaterThan(5)
    expect(codes.filter((c) => !have.includes(c))).toEqual([])
  })
})

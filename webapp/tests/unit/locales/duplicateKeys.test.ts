import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// Una chiave ripetuta nello stesso oggetto fa vincere l'ultima e perde le altre (caso: roll_notes, titolo e modifica grezzi).
// Il JSON è indentato dal formattatore: un oggetto si apre con `"k": {` e si chiude con `}`.
function duplicates(text: string): string[] {
  const stack: Set<string>[] = [new Set()]
  const names: string[] = []
  const out: string[] = []
  for (const line of text.split('\n')) {
    const m = /^\s*"((?:[^"\\]|\\.)*)":/.exec(line)
    if (m) {
      const seen = stack[stack.length - 1]
      if (seen.has(m[1])) out.push([...names, m[1]].join('.'))
      seen.add(m[1])
    }
    if (/[{[]\s*$/.test(line)) { stack.push(new Set()); names.push(m ? m[1] : '') }
    else if (/^\s*[}\]],?\s*$/.test(line) && stack.length > 1) { stack.pop(); names.pop() }
  }
  return out
}

describe('locali senza chiavi duplicate', () => {
  it.each(['it', 'en'])('%s.json', (l) => {
    expect(duplicates(readFileSync(resolve(__dirname, `../../../src/locales/${l}.json`), 'utf8'))).toEqual([])
  })
})

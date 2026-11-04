import { describe, it, expect } from 'vitest'
import { classKey } from '@/lib/classProgression'

describe('classKey', () => {
  it('ignora maiuscole e lingua', () => {
    for (const n of ['Mago', 'wizard', 'Wizard', 'MAGO']) expect(classKey(n)).toBe('wizard')
  })
  it('è null per una classe custom', () => {
    expect(classKey('Cacciatore di Taglie')).toBeNull()
  })
})

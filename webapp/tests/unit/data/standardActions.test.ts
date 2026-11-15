import { describe, it, expect } from 'vitest'
import { standardActionsFor } from '@/data/standardActions'

describe('standardActionsFor', () => {
  it('"Sfuggire a una lotta" esiste solo nel 2014, con Atletica e Acrobazia', () => {
    const a = standardActionsFor('2014').find((x) => x.id === 'escape_grapple')
    expect(a).toMatchObject({ bucket: 'action', skills: ['athletics', 'acrobatics'] })
    expect(standardActionsFor('2024').some((x) => x.id === 'escape_grapple')).toBe(false)
  })
})

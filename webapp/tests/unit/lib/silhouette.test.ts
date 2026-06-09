import { describe, it, expect, vi } from 'vitest'

// Mock the manifest so the resolution logic is tested against a known, small
// allow-list instead of the real (large, changing) silhouette set.
vi.mock('@/data/silhouette-manifest.json', () => ({
  default: ['wizard.png', 'wizard_elf.png', 'wizard_elf_male.png', 'fighter.png'],
}))

import { silhouetteUrl } from '@/lib/silhouette'

type Char = Parameters<typeof silhouetteUrl>[0]

function mkChar(partial: Partial<Char>): Char {
  return { classes: [], race: null, gender: null, ...partial } as Char
}

describe('silhouetteUrl resolution', () => {
  it('prefers the most specific class_race_gender match', () => {
    const url = silhouetteUrl(
      mkChar({ classes: [{ class_name: 'wizard', level: 3 }], race: 'elf', gender: 'male' }),
    )
    expect(url).not.toBeNull()
    expect(url!.endsWith('silhouettes/wizard_elf_male.png')).toBe(true)
  })

  it('falls back class_race → class when the gendered file is missing', () => {
    // wizard_elf.png exists but wizard_elf_female.png does not.
    const url = silhouetteUrl(
      mkChar({ classes: [{ class_name: 'wizard', level: 1 }], race: 'elf', gender: 'female' }),
    )
    expect(url!.endsWith('silhouettes/wizard_elf.png')).toBe(true)
  })

  it('falls all the way back to the bare class file', () => {
    // unknown race + no gendered file → only wizard.png remains.
    const url = silhouetteUrl(
      mkChar({ classes: [{ class_name: 'wizard', level: 1 }], race: 'dragonborn', gender: 'male' }),
    )
    expect(url!.endsWith('silhouettes/wizard.png')).toBe(true)
  })

  it('maps Italian class names to canonical English slugs', () => {
    const url = silhouetteUrl(mkChar({ classes: [{ class_name: 'Mago', level: 1 }] }))
    expect(url!.endsWith('silhouettes/wizard.png')).toBe(true)
  })

  it('picks the highest-level canonical class on multiclass', () => {
    // fighter outranks wizard by level → fighter.png.
    const url = silhouetteUrl(
      mkChar({
        classes: [
          { class_name: 'wizard', level: 1 },
          { class_name: 'fighter', level: 5 },
        ],
      }),
    )
    expect(url!.endsWith('silhouettes/fighter.png')).toBe(true)
  })

  it('returns null when there is no canonical class (caller renders the SVG fallback)', () => {
    expect(silhouetteUrl(mkChar({ classes: [] }))).toBeNull()
    expect(
      silhouetteUrl(mkChar({ classes: [{ class_name: 'artificer-homebrew', level: 1 }] })),
    ).toBeNull()
  })

  it('returns null when the class has no manifest entry at all', () => {
    // bard is canonical but absent from the mocked manifest.
    expect(silhouetteUrl(mkChar({ classes: [{ class_name: 'bard', level: 1 }] }))).toBeNull()
  })
})

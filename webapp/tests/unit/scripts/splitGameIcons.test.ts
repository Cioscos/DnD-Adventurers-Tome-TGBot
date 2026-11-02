import { describe, it, expect } from 'vitest'
// @ts-expect-error -- plugin Vite in JS puro (scripts/), senza tipi
import { splitGameIcons } from '../../../scripts/split-game-icons.mjs'

const plugin = splitGameIcons()

describe('splitGameIcons', () => {
  it('rewrites named imports (multiline + alias) into one virtual module per icon', () => {
    const code = `import {\n  GiFist,\n  GiFlame as Fire,\n} from 'react-icons/gi'\nimport { X } from 'lucide-react'`
    const out = plugin.transform(code, '/src/a.tsx')
    expect(out).toContain(`import { GiFist as GiFist } from 'gi-icon:GiFist';`)
    expect(out).toContain(`import { GiFlame as Fire } from 'gi-icon:GiFlame';`)
    expect(out).toContain(`import { X } from 'lucide-react'`)
    expect(out).not.toContain('react-icons/gi')
  })

  it('ignores node_modules and files without gi imports', () => {
    expect(plugin.transform(`import { GiFist } from 'react-icons/gi'`, '/node_modules/x.js')).toBeUndefined()
    expect(plugin.transform(`const a = 1`, '/src/b.ts')).toBeUndefined()
  })

  it('loads exactly one icon function from react-icons', () => {
    const id = plugin.resolveId('gi-icon:GiFist')
    const src: string = plugin.load.call({ error: (m: string) => { throw new Error(m) } }, id)
    expect(src.startsWith(`import { GenIcon } from 'react-icons/lib';`)).toBe(true)
    expect(src.match(/export function/g)).toHaveLength(1)
    expect(src).toContain('export function GiFist (props) {')
    expect(src.trimEnd().endsWith('};')).toBe(true)
  })
})

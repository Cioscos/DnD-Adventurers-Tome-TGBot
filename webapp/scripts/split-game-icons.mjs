import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// react-icons/gi è UN solo modulo (4000 icone): Rollup divide i chunk per modulo,
// quindi tutte le icone usate nell'app finivano insieme nell'entry (~85 KB).
// Qui ogni `import { GiX } from 'react-icons/gi'` diventa un modulo virtuale per
// icona, che segue nel chunk della pagina che la usa. Solo in build: in dev e nei
// test il modulo reale va benissimo.
const PREFIX = 'gi-icon:'

export function splitGameIcons() {
  let root = process.cwd()
  let source
  return {
    name: 'split-game-icons',
    apply: 'build',
    enforce: 'pre',
    configResolved(config) {
      root = config.root
    },
    transform(code, id) {
      if (id.includes('node_modules') || !code.includes('react-icons/gi')) return
      return code.replace(/import\s*\{([^}]*)\}\s*from\s*['"]react-icons\/gi['"];?/g, (_, names) =>
        names
          .split(',')
          .map((n) => n.trim())
          .filter(Boolean)
          .map((n) => {
            const [name, alias = name] = n.split(/\s+as\s+/)
            return `import { ${name} as ${alias} } from '${PREFIX}${name}';`
          })
          .join('\n'),
      )
    },
    resolveId(id) {
      if (id.startsWith(PREFIX)) return '\0' + id
    },
    load(id) {
      if (!id.startsWith('\0' + PREFIX)) return
      const name = id.slice(PREFIX.length + 1)
      source ??= readFileSync(resolve(root, 'node_modules/react-icons/gi/index.mjs'), 'utf-8')
      // Formato generato da react-icons: `export function GiX (props) {` + corpo + `};`
      const start = source.indexOf(`export function ${name} (props) {`)
      if (start < 0) this.error(`react-icons/gi: icona ${name} non trovata`)
      const end = source.indexOf('\n};', start)
      return `import { GenIcon } from 'react-icons/lib';\n${source.slice(start, end + 3)}\n`
    },
  }
}

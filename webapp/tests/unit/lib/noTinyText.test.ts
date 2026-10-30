import { readdirSync, readFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import { describe, expect, it } from 'vitest'

const SRC_DIR = join(process.cwd(), 'src')
const EXCLUDED_DIRS = new Set(['graphify-out'])
const SOURCE_FILE = /\.(ts|tsx|css)$/
const TINY_TEXT = /text-\[\d(\.\d+)?px\]|text-\[1[01](\.\d+)?px\]/

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) return EXCLUDED_DIRS.has(entry.name) ? [] : sourceFiles(path)
    return SOURCE_FILE.test(entry.name) ? [path] : []
  })
}

describe('testo minimo 12 px', () => {
  it('nessun file di src usa classi di testo sotto i 12 px', () => {
    const offenders = sourceFiles(SRC_DIR)
      .filter((file) => TINY_TEXT.test(readFileSync(file, 'utf8')))
      .map((file) => relative(SRC_DIR, file).replaceAll('\\', '/'))

    expect(offenders).toEqual([])
  })
})

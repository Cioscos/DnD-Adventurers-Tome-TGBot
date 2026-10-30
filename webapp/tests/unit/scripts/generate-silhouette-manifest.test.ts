// @vitest-environment node
import { execFileSync } from 'node:child_process'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const webappRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..')

describe('generate-silhouette-manifest CLI', () => {
  // È il comando di `prebuild`: senza manifest `tsc` fallisce su una copia pulita del repo.
  it('writes the manifest when launched from the command line', () => {
    const output = execFileSync(process.execPath, ['scripts/generate-silhouette-manifest.mjs'], {
      cwd: webappRoot,
      encoding: 'utf8',
    })
    expect(output).toContain('silhouette-manifest.json')
  })
})

// Enumerates webapp/public/silhouettes/*.png and writes the list of
// filenames to webapp/src/data/silhouette-manifest.json.
//
// Run by the Vite plugin in webapp/vite.config.ts on every dev/build.

import { readdirSync, mkdirSync, writeFileSync, existsSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const WEBAPP_ROOT = resolve(__dirname, '..')
const SILHOUETTE_DIR = join(WEBAPP_ROOT, 'public', 'silhouettes')
const OUT_PATH = join(WEBAPP_ROOT, 'src', 'data', 'silhouette-manifest.json')

export function generateSilhouetteManifest() {
  let files = []
  if (existsSync(SILHOUETTE_DIR)) {
    files = readdirSync(SILHOUETTE_DIR)
      .filter((f) => f.toLowerCase().endsWith('.png'))
      .sort()
  }

  mkdirSync(dirname(OUT_PATH), { recursive: true })
  writeFileSync(OUT_PATH, JSON.stringify(files, null, 2) + '\n', 'utf8')

  return files
}

// CLI: node scripts/generate-silhouette-manifest.mjs
if (import.meta.url === `file://${process.argv[1]}`) {
  const files = generateSilhouetteManifest()
  console.log(`Wrote ${files.length} entries to ${OUT_PATH}`)
}

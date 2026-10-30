import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'
import { generateSilhouetteManifest } from './scripts/generate-silhouette-manifest.mjs'

function silhouetteManifestPlugin() {
  return {
    name: 'silhouette-manifest',
    buildStart() {
      const files = generateSilhouetteManifest()
      this.info(`silhouette-manifest: ${files.length} entries`)
    },
  }
}

// https://vitejs.dev/config/
// Versione dell'app per la home: dal package.json (la CI garantisce che combaci
// con la voce in testa al changelog), così la landing non importa i ~80 KB del
// changelog.json solo per mostrare "v2.x.y".
const pkg = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf-8'))

export default defineConfig(({ command }) => ({
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  base: command === 'build' ? '/DnD-Adventurers-Tome-TGBot/app/' : '/',
  build: {
    outDir: '../docs/app',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          // React in un chunk suo (vendor stabile fra i deploy, cache del
          // WebView); id con / o \ a seconda della piattaforma di build.
          if (/node_modules[\\/](react|react-dom|scheduler)[\\/]/.test(id)) {
            return 'react-vendor'
          }
          // three / @react-three / cannon-es NON vanno in un chunk manuale: Rollup
          // ci spostava anche helper condivisi (preload, interop CJS) e l'entry
          // finiva per importare l'intero chunk 3D all'avvio. Raggiungibili solo
          // via import() dinamico (DiceScene, packs/loader), restano fuori
          // dall'entry da soli.
        },
      },
    },
  },
  plugins: [react(), silhouetteManifestPlugin()],
  resolve: {
    alias: {
      '@': '/src',
    },
  },
}))

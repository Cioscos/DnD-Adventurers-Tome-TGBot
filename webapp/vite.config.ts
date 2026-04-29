import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
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
export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/DnD-Adventurers-Tome-TGBot/app/' : '/',
  build: {
    outDir: '../docs/app',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (
            id.includes('node_modules/three/') ||
            id.includes('node_modules/@react-three/') ||
            id.includes('node_modules/cannon-es/')
          ) {
            return 'dice-scene'
          }
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

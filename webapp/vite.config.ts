import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/DnD-Adventurers-Tome-TGBot/app/' : '/',
  build: {
    outDir: '../docs/app',
    emptyOutDir: true,
  },
  plugins: [react()],
  resolve: {
    alias: {
      '@': '/src',
    },
  },
}))

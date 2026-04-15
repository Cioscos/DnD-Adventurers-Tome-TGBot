/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        tg: {
          bg: 'var(--tg-theme-bg-color)',
          text: 'var(--tg-theme-text-color)',
          hint: 'var(--tg-theme-hint-color)',
          link: 'var(--tg-theme-link-color)',
          button: 'var(--tg-theme-button-color)',
          'button-text': 'var(--tg-theme-button-text-color)',
          'secondary-bg': 'var(--tg-theme-secondary-bg-color)',
        },
        dnd: {
          bg: 'var(--dnd-bg)',
          surface: 'var(--dnd-surface)',
          'surface-elevated': 'var(--dnd-surface-elevated)',
          gold: 'var(--dnd-gold)',
          'gold-dim': 'var(--dnd-gold-dim)',
          parchment: 'var(--dnd-parchment)',
          text: 'var(--dnd-text)',
          'text-secondary': 'var(--dnd-text-secondary)',
          danger: 'var(--dnd-danger)',
          success: 'var(--dnd-success)',
          arcane: 'var(--dnd-arcane)',
          info: 'var(--dnd-info)',
        },
      },
      fontFamily: {
        cinzel: ['Cinzel', 'serif'],
      },
      boxShadow: {
        'dnd-glow': '0 0 20px var(--dnd-gold-glow)',
      },
    },
  },
  plugins: [],
}

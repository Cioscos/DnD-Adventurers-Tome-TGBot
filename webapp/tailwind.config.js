/**
 * I token colore vivono in CSS vars (tema dark/light in index.css). Una var()
 * "opaca" non permette a Tailwind di iniettare l'alpha del modificatore
 * (`bg-dnd-gold/15`): senza questo wrapper quelle utility venivano scartate
 * in silenzio e ~300 tinte previste dal design non sono mai esistite.
 * color-mix(<alpha-value>) le rende reali mantenendo il flip di tema via var.
 * Supporto: Chrome/WebView 111+, Safari 16.2+ (il target Telegram è oltre).
 */
const alpha = (cssVar) =>
  `color-mix(in srgb, var(${cssVar}) calc(<alpha-value> * 100%), transparent)`

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      screens: {
        xs: '375px',
      },
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
          ink: alpha('--dnd-ink'),
          bg: alpha('--dnd-bg'),
          surface: alpha('--dnd-surface'),
          'surface-raised': alpha('--dnd-surface-raised'),
          'surface-lifted': alpha('--dnd-surface-lifted'),
          'surface-elevated': alpha('--dnd-surface-raised'), // alias legacy
          border: alpha('--dnd-border'),
          'border-strong': alpha('--dnd-border-strong'),
          gold: alpha('--dnd-gold'),
          'gold-bright': alpha('--dnd-gold-bright'),
          'gold-dim': alpha('--dnd-gold-dim'),
          'gold-deep': alpha('--dnd-gold-deep'),
          parchment: alpha('--dnd-parchment'),
          text: alpha('--dnd-text'),
          'text-muted': alpha('--dnd-text-muted'),
          'text-faint': alpha('--dnd-text-faint'),
          'text-secondary': alpha('--dnd-text-muted'), // alias legacy
          danger: alpha('--dnd-crimson'),
          crimson: alpha('--dnd-crimson'),
          'crimson-bright': alpha('--dnd-crimson-bright'),
          'crimson-deep': alpha('--dnd-crimson-deep'),
          success: alpha('--dnd-emerald'),
          emerald: alpha('--dnd-emerald'),
          'emerald-bright': alpha('--dnd-emerald-bright'),
          'emerald-deep': alpha('--dnd-emerald-deep'),
          arcane: alpha('--dnd-arcane'),
          'arcane-bright': alpha('--dnd-arcane-bright'),
          'arcane-deep': alpha('--dnd-arcane-deep'),
          info: alpha('--dnd-cobalt'),
          cobalt: alpha('--dnd-cobalt'),
          'cobalt-bright': alpha('--dnd-cobalt-bright'),
          'cobalt-deep': alpha('--dnd-cobalt-deep'),
          amber: alpha('--dnd-amber'),
          highlight: alpha('--dnd-amber'),
          'highlight-muted': alpha('--dnd-amber'),
          'success-text': alpha('--dnd-emerald-bright'),
          'arcane-text': alpha('--dnd-arcane-bright'),
          'info-text': alpha('--dnd-cobalt-bright'),
          'chip-bg': alpha('--dnd-chip-bg'),
          'chip-border': alpha('--dnd-chip-border'),
          overlay: 'var(--dnd-overlay)',
        },
      },
      fontFamily: {
        cinzel: ['Cinzel', 'Georgia', 'serif'],
        display: ['"Cormorant Unicase"', 'Cinzel', 'Georgia', 'serif'],
        body: ['Fraunces', 'Georgia', 'serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        'dnd-glow': '0 0 20px var(--dnd-gold-glow)',
        'parchment-sm': 'var(--shadow-1)',
        'parchment-md': 'var(--shadow-2)',
        'parchment-lg': 'var(--shadow-3)',
        'parchment-xl': 'var(--shadow-4)',
        'parchment-2xl': 'var(--shadow-5)',
        'illumination': 'var(--halo-gold)',
        'halo-gold': 'var(--halo-gold)',
        'halo-arcane': 'var(--halo-arcane)',
        'halo-danger': 'var(--halo-danger)',
        engrave: 'var(--shadow-engrave)',
      },
      backgroundImage: {
        'gradient-parchment': 'var(--gradient-parchment)',
        'gradient-gold': 'var(--gradient-gold)',
        'gradient-hero-halo': 'var(--gradient-hero-halo)',
        'gradient-arcane-mist': 'var(--gradient-arcane-mist)',
        'gradient-ember': 'var(--gradient-ember)',
        'gradient-flourish': 'var(--gradient-flourish)',
        'grain-overlay': 'var(--grain-overlay)',
      },
      transitionTimingFunction: {
        'ease-parchment': 'cubic-bezier(0.22, 1, 0.36, 1)',
        'ease-ink': 'cubic-bezier(0.22, 0.61, 0.36, 1)',
      },
      keyframes: {
        shake: {
          '0%, 100%': { transform: 'translateX(0)' },
          '20%': { transform: 'translateX(-4px)' },
          '40%': { transform: 'translateX(4px)' },
          '60%': { transform: 'translateX(-2px)' },
          '80%': { transform: 'translateX(2px)' },
        },
        bob: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-4px)' },
        },
        'ink-spread': {
          '0%': { transform: 'scale(0)', opacity: '0.4' },
          '100%': { transform: 'scale(2)', opacity: '0' },
        },
        'sigil-rotate': {
          '0%, 100%': { transform: 'rotate(-3deg)' },
          '50%': { transform: 'rotate(3deg)' },
        },
        'glow-pulse': {
          '0%, 100%': { boxShadow: '0 0 6px var(--dnd-gold-glow), 0 0 0 0 var(--dnd-gold-glow)' },
          '50%':       { boxShadow: '0 0 18px var(--dnd-gold-glow), 0 0 4px 1px var(--dnd-gold-glow)' },
        },
      },
      animation: {
        shake: 'shake 250ms ease-out',
        bob: 'bob 1.8s ease-in-out infinite',
        'ink-spread': 'ink-spread 320ms ease-out forwards',
        'sigil-rotate': 'sigil-rotate 5s ease-in-out infinite',
        'glow-pulse': 'glow-pulse 1.6s ease-in-out infinite',
      },
    },
  },
  plugins: [require('@tailwindcss/container-queries')],
}

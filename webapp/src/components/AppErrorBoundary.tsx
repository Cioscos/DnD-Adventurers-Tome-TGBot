import { Component, type ReactNode } from 'react'
import i18n from '@/i18n'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
}

/** Boundary di ultima istanza attorno all'intera app: senza di esso un errore
 *  di render smonta tutto il root e la Mini App resta su uno schermo bianco
 *  irrecuperabile (si può solo chiudere). Il fallback è volutamente HTML puro —
 *  niente framer-motion, query o router, che potrebbero essere la causa stessa
 *  del crash. */
export default class AppErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[AppErrorBoundary] render crash:', error, info.componentStack)
  }

  render() {
    if (!this.state.hasError) return this.props.children
    return (
      <div
        className="flex flex-col items-center justify-center gap-4 px-8 text-center bg-dnd-bg"
        style={{ minHeight: 'var(--tg-vh, 100vh)' }}
      >
        <span className="text-4xl" aria-hidden>
          💀
        </span>
        <h1 className="font-cinzel text-lg text-dnd-gold">
          {i18n.t('common.error_boundary.title')}
        </h1>
        <p className="font-body text-sm text-dnd-text-muted max-w-xs">
          {i18n.t('common.error_boundary.message')}
        </p>
        {/* eslint-disable-next-line no-restricted-syntax -- crash fallback: deve rendere anche se framer-motion è rotto, il kit UI (m.button) non è affidabile qui */}
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="min-h-[48px] px-6 py-3 rounded-xl bg-gradient-gold text-dnd-ink
                     font-cinzel text-sm shadow-engrave"
        >
          {i18n.t('common.error_boundary.reload')}
        </button>
      </div>
    )
  }
}

import { useState } from 'react'
import { m, AnimatePresence } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { ChevronDown, Settings as SettingsIcon } from 'lucide-react'
import { GiSparkles as Sparkles } from 'react-icons/gi'
import Surface from '@/components/ui/Surface'
import { haptic } from '@/auth/telegram'
import { ease, spring } from '@/styles/motion'

// Stato del banner Auto-mode condiviso fra tutti i personaggi (chiave globale):
// aperto al primissimo accesso (chiave assente), poi ricorda l'ultima scelta.
const STORAGE_KEY = 'dnd:slots-auto-banner'

interface AutoModeBannerProps {
  onGoToSettings: () => void
}

function readInitialOpen(): boolean {
  try {
    // assente o qualsiasi valore != 'closed' => aperto (primo accesso incluso)
    return localStorage.getItem(STORAGE_KEY) !== 'closed'
  } catch {
    return true
  }
}

export default function AutoModeBanner({ onGoToSettings }: AutoModeBannerProps) {
  const { t } = useTranslation()
  const [open, setOpen] = useState<boolean>(readInitialOpen)

  const toggle = () => {
    haptic.light()
    setOpen((prev) => {
      const next = !prev
      try {
        localStorage.setItem(STORAGE_KEY, next ? 'open' : 'closed')
      } catch {
        /* webview senza storage: ignora */
      }
      return next
    })
  }

  return (
    <Surface
      variant="arcane"
      className={`transition-colors duration-300 ${open ? '!border-dnd-arcane' : ''}`}
    >
      {/* Pill toggle row — sempre visibile (target tocco >= 44px) */}
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        className="flex w-full items-center gap-2.5 min-h-[44px] text-left"
      >
        <Sparkles size={16} className="text-dnd-arcane-bright shrink-0" />
        <span className="flex-1 min-w-0 truncate font-cinzel uppercase tracking-wider text-xs text-dnd-arcane-bright">
          {t('character.slots.auto_label')}
        </span>
        <m.span
          aria-hidden
          className="shrink-0 text-dnd-arcane-bright"
          animate={{ rotate: open ? 180 : 0 }}
          transition={spring.snappy}
        >
          <ChevronDown size={16} />
        </m.span>
      </button>

      {/* Corpo collassabile — frase completa + scorciatoia Impostazioni */}
      <AnimatePresence initial={false}>
        {open && (
          <m.div
            key="auto-banner-body"
            className="overflow-hidden"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: ease.inkSpread }}
          >
            <p className="pt-2.5 text-xs text-dnd-text font-body">
              {t('character.slots.auto_hint')}
            </p>
            <button
              type="button"
              onClick={onGoToSettings}
              className="mt-3 inline-flex items-center gap-1 min-h-[44px] px-3 rounded-lg bg-dnd-surface border border-dnd-arcane/40 text-dnd-arcane-bright font-cinzel text-[10px] uppercase tracking-widest"
            >
              <SettingsIcon size={11} />
              {t('character.slots.go_to_settings')}
            </button>
          </m.div>
        )}
      </AnimatePresence>
    </Surface>
  )
}

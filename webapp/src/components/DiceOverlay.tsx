import { useMemo } from 'react'
import { useLocation, matchPath } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Dices } from 'lucide-react'
import { useCharacterStore } from '@/store/characterStore'

function useOverlayVisibility(): { visible: boolean; charId: number | null } {
  const location = useLocation()
  const activeCharId = useCharacterStore((s) => s.activeCharId)

  return useMemo(() => {
    const path = location.pathname

    // Char pages: /char/:id/* EXCEPT /char/:id/dice
    const charDice = matchPath('/char/:id/dice', path)
    if (charDice) return { visible: false, charId: null }

    const charAny = matchPath('/char/:id/*', path) ?? matchPath('/char/:id', path)
    if (charAny) {
      const id = Number(charAny.params.id)
      return { visible: Number.isFinite(id), charId: Number.isFinite(id) ? id : null }
    }

    // Session room: /session/:id uses activeCharId
    const session = matchPath('/session/:id', path)
    if (session && activeCharId != null) {
      return { visible: true, charId: activeCharId }
    }

    return { visible: false, charId: null }
  }, [location.pathname, activeCharId])
}

export default function DiceOverlay() {
  const { t } = useTranslation()
  const { visible } = useOverlayVisibility()

  if (!visible) return null

  return (
    <m.button
      type="button"
      aria-label={t('character.dice_overlay.open')}
      className="fixed bottom-4 right-4 z-[55] w-14 h-14 rounded-full
                 bg-gradient-to-br from-dnd-gold-deep to-dnd-gold-bright
                 border border-dnd-gold-dim shadow-halo-gold
                 flex items-center justify-center text-dnd-ink"
      whileTap={{ scale: 0.9 }}
      whileHover={{ scale: 1.05 }}
      initial={{ opacity: 0, scale: 0.6 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ type: 'spring', stiffness: 260, damping: 22 }}
    >
      <Dices size={26} />
    </m.button>
  )
}

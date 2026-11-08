import { useTranslation } from 'react-i18next'
import { GiNightSleep, GiCampfire } from 'react-icons/gi'
import Sheet from '@/components/ui/Sheet'
import Pressable from '@/components/ui/Pressable'
import RestDialogs from '@/components/character/RestDialogs'
import { useRest } from '@/hooks/useRest'
import { haptic } from '@/auth/telegram'
import type { CharacterFull } from '@/types'

interface Props {
  char: CharacterFull
  open: boolean
  onClose: () => void
}

/** Riposo dal menu: breve (dadi vita) o lungo (con conferma). Le domande sono quelle di `useRest`, uguali ad azioni rapide e PF. */
export default function RestSheet({ char, open, onClose }: Props) {
  const { t } = useTranslation()
  const rest = useRest(char.id, char, onClose)

  const rowClass = `w-full min-h-[44px] flex items-center gap-3 px-4 py-3 rounded-2xl
                    bg-dnd-surface border border-dnd-border text-left
                    hover:border-dnd-gold/60 transition-[border-color] duration-200`

  return (
    <>
      <Sheet open={open} onClose={onClose} title={t('character.menu.rest')}>
        <div className="p-5 space-y-2">
          <Pressable
            onClick={() => { haptic.light(); rest.openShort() }}
            className={rowClass}
          >
            <GiNightSleep size={22} className="text-dnd-cobalt-bright" />
            <span className="text-sm text-dnd-text font-body">{t('character.quick_actions.rest_short')}</span>
          </Pressable>
          <Pressable
            onClick={() => { haptic.light(); rest.openLong() }}
            className={rowClass}
          >
            <GiCampfire size={22} className="text-dnd-amber" />
            <span className="text-sm text-dnd-text font-body">{t('character.quick_actions.rest_long')}</span>
          </Pressable>
        </div>
      </Sheet>

      <RestDialogs char={char} rest={rest} />
    </>
  )
}

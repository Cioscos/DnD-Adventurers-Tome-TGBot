import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { GiPolarStar } from 'react-icons/gi'
import Pressable from '@/components/ui/Pressable'
import ResolveChoiceSheet from '@/components/character/ResolveChoiceSheet'
import type { CharacterFull } from '@/types'

/** Badge "scelte di livello in sospeso": apre la risoluzione della prima scelta. */
export default function PendingChoicesBadge({ char }: { char: CharacterFull }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const choices = char.pending_choices ?? []
  if (choices.length === 0) return null
  return (
    <>
      <Pressable
        onClick={() => setOpen(true)}
        className="w-full min-h-[44px] flex items-center justify-center gap-2 px-3 rounded-xl
                   bg-dnd-gold/15 border border-dnd-gold text-dnd-gold-bright"
      >
        <GiPolarStar size={14} aria-hidden />
        <span className="text-xs font-cinzel uppercase tracking-widest">
          {t('character.level_choice.badge', { count: choices.length })}
        </span>
      </Pressable>
      <ResolveChoiceSheet key={choices[0].id} char={char} choice={choices[0]} open={open} onClose={() => setOpen(false)} />
    </>
  )
}

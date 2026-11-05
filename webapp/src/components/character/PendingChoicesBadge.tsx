import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { GiPolarStar } from 'react-icons/gi'
import Pressable from '@/components/ui/Pressable'
import ResolveChoiceSheet from '@/components/character/ResolveChoiceSheet'
import ClassOptionSheet from '@/components/rules/ClassOptionSheet'
import type { CharacterFull } from '@/types'

/** Badge "scelte di livello in sospeso": apre la risoluzione della prima scelta. */
export default function PendingChoicesBadge({ char }: { char: CharacterFull }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const choices = char.pending_choices ?? []
  if (choices.length === 0) return null
  // Incantesimi a scelta (Segreti Magici): non c'è un elenco da mostrare, si scelgono dalla pagina degli incantesimi.
  const picking = choices[0].kind === 'class_option' && choices[0].spell_pick
  return (
    <>
      <Pressable
        onClick={() => (picking ? navigate(`/char/${char.id}/spells?pick=${choices[0].id}`) : setOpen(true))}
        className="w-full min-h-[44px] flex items-center justify-center gap-2 px-3 rounded-xl
                   bg-dnd-gold/15 border border-dnd-gold text-dnd-gold-bright"
      >
        <GiPolarStar size={14} aria-hidden />
        <span className="text-xs font-cinzel uppercase tracking-widest">
          {t('character.level_choice.badge', { count: choices.length })}
        </span>
      </Pressable>
      {choices[0].kind === 'class_option'
        ? <ClassOptionSheet key={choices[0].id} char={char} choice={choices[0]} open={open} onClose={() => setOpen(false)} />
        : <ResolveChoiceSheet key={choices[0].id} char={char} choice={choices[0]} open={open} onClose={() => setOpen(false)} />}
    </>
  )
}

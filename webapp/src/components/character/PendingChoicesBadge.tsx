import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { GiPolarStar } from 'react-icons/gi'
import Pressable from '@/components/ui/Pressable'
import Sheet from '@/components/ui/Sheet'
import ResolveChoiceSheet from '@/components/character/ResolveChoiceSheet'
import ClassOptionSheet from '@/components/rules/ClassOptionSheet'
import { uiLang } from '@/lib/lang'
import { choiceTitle } from '@/lib/levelChoice'
import type { CharacterFull, PendingChoice } from '@/types'

/** Badge "scelte di livello in sospeso": una sola scelta si apre subito, più scelte si elencano tutte (U3). */
export default function PendingChoicesBadge({ char }: { char: CharacterFull }) {
  const { t, i18n } = useTranslation()
  const lang = uiLang(i18n.language)
  const [listOpen, setListOpen] = useState(false)
  const [currentId, setCurrentId] = useState<string | null>(null)
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const choices = char.pending_choices ?? []
  if (choices.length === 0) return null
  const current = choices.find((c) => c.id === currentId) ?? null

  const openChoice = (c: PendingChoice) => {
    setListOpen(false)
    // Incantesimi a scelta (Segreti Magici, trucchetti di classe): si scelgono dalla pagina degli incantesimi.
    if (c.kind === 'class_option' && c.spell_pick) return navigate(`/char/${char.id}/spells?pick=${c.id}`)
    setCurrentId(c.id)
    setOpen(true)
  }

  return (
    <>
      <Pressable
        onClick={() => (choices.length === 1 ? openChoice(choices[0]) : setListOpen(true))}
        className="w-full min-h-[44px] flex items-center justify-center gap-2 px-3 rounded-xl
                   bg-dnd-gold/15 border border-dnd-gold text-dnd-gold-bright"
      >
        <GiPolarStar size={14} aria-hidden />
        <span className="text-xs font-cinzel uppercase tracking-widest">
          {t('character.level_choice.badge', { count: choices.length })}
        </span>
      </Pressable>
      <Sheet open={listOpen} onClose={() => setListOpen(false)} title={t('character.level_choice.list_title')}>
        <div className="p-5 space-y-2">
          {choices.map((c) => (
            <Pressable
              key={c.id}
              onClick={() => openChoice(c)}
              className="w-full min-h-[44px] px-3 py-2 rounded-xl border border-dnd-border text-left"
            >
              <span className="block text-sm font-body text-dnd-text">{choiceTitle(t, lang, c)}</span>
              {c.resolvable === false && (
                <span className="block text-xs font-body text-dnd-text-muted">{t('character.level_choice.waiting_short')}</span>
              )}
            </Pressable>
          ))}
        </div>
      </Sheet>
      {current && (current.kind === 'class_option'
        ? <ClassOptionSheet key={current.id} char={char} choice={current} open={open} onClose={() => setOpen(false)} />
        : <ResolveChoiceSheet key={current.id} char={char} choice={current} open={open} onClose={() => setOpen(false)} />)}
    </>
  )
}

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Pressable from '@/components/ui/Pressable'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { notifyMutationError } from '@/lib/mutationError'
import { CLASS_NAME_TO_PROGRESSION_KEY } from '@/lib/classProgression'
import type { CharacterFull, ClassOptionEntry, PendingChoice } from '@/types'

interface Props {
  char: CharacterFull
  choice: PendingChoice
  open: boolean
  onClose: () => void
}

/** Scelta di opzioni di classe (Metamagia, Invocazioni, ...): esattamente `choice.count` fra quelle offerte. */
export default function ClassOptionSheet({ char, choice, open, onClose }: Props) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language?.startsWith('en') ? 'en' : 'it'
  const qc = useQueryClient()
  const [picked, setPicked] = useState<string[]>([])
  const total = choice.count ?? 1
  // Con meno opzioni del dovuto se ne prendono quante ne offre la scheda, il resto aspetta (R39).
  const count = choice.pick_count ?? total
  const options = choice.options ?? []
  const classEn = Object.entries(CLASS_NAME_TO_PROGRESSION_KEY).find(([, v]) => v === choice.class_key)?.[0]
  const classLabel = classEn ? t(`dnd.classes.${classEn}`, { defaultValue: choice.class_key }) : choice.class_key

  const mutation = useMutation({
    mutationFn: () => api.choices.resolve(char.id, choice.id, { kind: 'class_option', options: picked }),
    onSuccess: (updated) => {
      qc.setQueryData(['character', char.id], updated)
      haptic.success()
      onClose()
    },
    onError: () => haptic.error(),
  })

  const toggle = (key: string) => {
    haptic.light()
    setPicked((cur) => (cur.includes(key) ? cur.filter((k) => k !== key) : cur.length < count ? [...cur, key] : cur))
  }

  return (
    <Sheet open={open} onClose={onClose} title={`${t('character.level_choice.class_option_title')} · ${classLabel} ${choice.level}`}>
      <div className="p-5 space-y-3">
        {count === 0 ? (
          <p className="text-sm font-body text-dnd-text">{t('character.level_choice.waiting_for_skills', { n: total })}</p>
        ) : (
          <p className="text-xs font-body text-dnd-text-muted">
            {t('character.level_choice.options_left', { n: count - picked.length })}
          </p>
        )}
        {count > 0 && count < total && (
          <p className="text-xs font-body text-dnd-text-muted">{t('character.level_choice.partial', { n: total - count })}</p>
        )}
        {options.map((o) => {
          const on = picked.includes(o.key)
          return (
            <Pressable
              key={o.key}
              onClick={() => toggle(o.key)}
              disabled={!on && picked.length >= count}
              className={`w-full disabled:opacity-40 min-h-[44px] px-3 py-2 rounded-xl border text-left ${
                on ? 'bg-dnd-gold/15 border-dnd-gold' : 'border-dnd-border'
              }`}
            >
              <span className="block text-sm font-body text-dnd-text">{o.name[lang]}</span>
              {o.summary[lang] && <span className="block text-xs font-body text-dnd-text-muted">{o.summary[lang]}</span>}
              {o.owned && <span className="block text-xs font-body text-dnd-gold-bright">{t('character.level_choice.already_on_sheet')}</span>}
            </Pressable>
          )
        })}
        {mutation.isError && (
          <p className="text-xs font-body text-dnd-crimson-bright">{t('character.level_choice.error')}</p>
        )}
        {count > 0 && (
          <Pressable
            onClick={() => mutation.mutate()}
            disabled={picked.length !== count}
            pending={mutation.isPending}
            className="w-full min-h-[44px] rounded-xl bg-dnd-gold/15 border border-dnd-gold text-sm font-body text-dnd-gold-bright disabled:opacity-40"
          >
            {t('character.level_choice.confirm')}
          </Pressable>
        )}
      </div>
    </Sheet>
  )
}

interface ReplaceProps {
  char: CharacterFull
  classId: number
  group: string
  open: boolean
  onClose: () => void
}

/** Sostituisce un'opzione già scelta con un'altra (solo gruppi `replaceable`, deciso dal catalogo). */
export function ReplaceOptionSheet({ char, classId, group, open, onClose }: ReplaceProps) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language?.startsWith('en') ? 'en' : 'it'
  const qc = useQueryClient()
  const [oldKey, setOldKey] = useState('')
  const [newKey, setNewKey] = useState('')
  const state = useQuery({
    queryKey: ['class-options', char.id, classId, group],
    queryFn: () => api.choices.classOptions(char.id, classId, group),
    enabled: open,
  })
  const mutation = useMutation({
    mutationFn: () => api.choices.replaceOption(char.id, classId, { group, old_key: oldKey, new_key: newKey }),
    onSuccess: (updated) => {
      qc.setQueryData(['character', char.id], updated)
      qc.invalidateQueries({ queryKey: ['class-options', char.id, classId, group] })
      haptic.success()
      onClose()
    },
    onError: (err) => notifyMutationError(err),
  })
  const list = (entries: ClassOptionEntry[], current: string, set: (k: string) => void) => entries.map((o) => (
    <Pressable
      key={o.key}
      onClick={() => set(o.key)}
      className={`w-full min-h-[44px] px-3 py-2 rounded-xl border text-left ${
        current === o.key ? 'bg-dnd-gold/15 border-dnd-gold' : 'border-dnd-border'
      }`}
    >
      <span className="block text-sm font-body text-dnd-text">{o.name[lang]}</span>
    </Pressable>
  ))
  return (
    <Sheet open={open} onClose={onClose} title={t('character.level_choice.replace_title')}>
      <div className="p-5 space-y-3">
        <p className="text-xs font-body text-dnd-text-muted">{t('character.level_choice.replace_old')}</p>
        {list(state.data?.chosen ?? [], oldKey, setOldKey)}
        <p className="text-xs font-body text-dnd-text-muted">{t('character.level_choice.replace_new')}</p>
        {list(state.data?.available ?? [], newKey, setNewKey)}
        {mutation.isError && (
          <p className="text-xs font-body text-dnd-crimson-bright">{t('character.level_choice.error')}</p>
        )}
        <Pressable
          onClick={() => mutation.mutate()}
          disabled={!oldKey || !newKey || !state.data?.replaceable}
          pending={mutation.isPending}
          className="w-full min-h-[44px] rounded-xl bg-dnd-gold/15 border border-dnd-gold text-sm font-body text-dnd-gold-bright disabled:opacity-40"
        >
          {t('character.level_choice.confirm')}
        </Pressable>
      </div>
    </Sheet>
  )
}

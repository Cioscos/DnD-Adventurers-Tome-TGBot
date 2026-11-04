import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Pressable from '@/components/ui/Pressable'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { CLASS_NAME_TO_PROGRESSION_KEY } from '@/lib/classProgression'
import type { CharacterFull, PendingChoice } from '@/types'

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
  const count = choice.count ?? 1
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
        <p className="text-xs font-body text-dnd-text-muted">
          {t('character.level_choice.options_left', { n: count - picked.length })}
        </p>
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
            </Pressable>
          )
        })}
        {mutation.isError && (
          <p className="text-xs font-body text-dnd-crimson-bright">{t('character.level_choice.error')}</p>
        )}
        <Pressable
          onClick={() => mutation.mutate()}
          disabled={picked.length !== count}
          pending={mutation.isPending}
          className="w-full min-h-[44px] rounded-xl bg-dnd-gold/15 border border-dnd-gold text-sm font-body text-dnd-gold-bright disabled:opacity-40"
        >
          {t('character.level_choice.confirm')}
        </Pressable>
      </div>
    </Sheet>
  )
}

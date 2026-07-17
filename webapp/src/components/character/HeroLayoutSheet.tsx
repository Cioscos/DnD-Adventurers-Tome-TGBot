import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { ChevronUp, ChevronDown, Eye, EyeOff } from 'lucide-react'
import { api } from '@/api/client'
import Sheet from '@/components/ui/Sheet'
import IconButton from '@/components/ui/IconButton'
import { haptic } from '@/auth/telegram'
import { readHeroLayout, type HeroLayout, type HeroSectionKey } from '@/lib/heroLayout'
import type { CharacterFull } from '@/types'

interface HeroLayoutSheetProps {
  char: CharacterFull
  open: boolean
  onClose: () => void
}

/** Sheet di personalizzazione della home: frecce su/giù per l'ordine delle
 *  sezioni sotto la hero card, occhio per nasconderle. Persistenza immediata
 *  in settings.hero_layout (stesso pattern di quick_actions). */
export default function HeroLayoutSheet({ char, open, onClose }: HeroLayoutSheetProps) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const settings = (char.settings as Record<string, unknown>) ?? {}
  const layout = readHeroLayout(settings)

  const mutation = useMutation({
    mutationFn: (next: HeroLayout) =>
      api.characters.update(char.id, { settings: { ...settings, hero_layout: next } }),
    onSuccess: (updated) => {
      qc.setQueryData(['character', char.id], updated)
      haptic.light()
    },
    onError: () => haptic.error(),
  })

  const move = (key: HeroSectionKey, dir: -1 | 1) => {
    const order = [...layout.order]
    const i = order.indexOf(key)
    const j = i + dir
    if (i < 0 || j < 0 || j >= order.length) return
    ;[order[i], order[j]] = [order[j], order[i]]
    mutation.mutate({ ...layout, order })
  }

  const toggleHidden = (key: HeroSectionKey) => {
    const hidden = layout.hidden.includes(key)
      ? layout.hidden.filter((k) => k !== key)
      : [...layout.hidden, key]
    mutation.mutate({ ...layout, hidden })
  }

  return (
    <Sheet open={open} onClose={onClose} title={t('character.hero.layout_title')}>
      <div className="p-5 space-y-2">
        {layout.order.map((key, i) => {
          const isHidden = layout.hidden.includes(key)
          return (
            <div
              key={key}
              className={`flex items-center gap-2 px-3 py-2 rounded-xl border bg-dnd-surface border-dnd-border
                          ${isHidden ? 'opacity-50' : ''}`}
            >
              <span className="flex-1 min-w-0 truncate text-sm font-body text-dnd-text">
                {t(`character.hero.section_${key}`)}
              </span>
              <IconButton
                icon={<ChevronUp size={14} />}
                onClick={() => move(key, -1)}
                disabled={i === 0}
                loading={mutation.isPending}
                haptic="none"
                aria-label={t('character.hero.move_up')}
                className="w-9 h-9 rounded-lg bg-dnd-surface-raised border border-dnd-border disabled:opacity-30"
              />
              <IconButton
                icon={<ChevronDown size={14} />}
                onClick={() => move(key, 1)}
                disabled={i === layout.order.length - 1}
                loading={mutation.isPending}
                haptic="none"
                aria-label={t('character.hero.move_down')}
                className="w-9 h-9 rounded-lg bg-dnd-surface-raised border border-dnd-border disabled:opacity-30"
              />
              <IconButton
                icon={isHidden ? <EyeOff size={14} /> : <Eye size={14} />}
                onClick={() => toggleHidden(key)}
                loading={mutation.isPending}
                haptic="light"
                aria-label={t('character.hero.toggle_visibility')}
                className={`w-9 h-9 rounded-lg border ${isHidden
                  ? 'bg-dnd-surface-raised border-dnd-border text-dnd-text-faint'
                  : 'bg-dnd-gold/15 border-dnd-gold text-dnd-gold-bright'}`}
              />
            </div>
          )
        })}
      </div>
    </Sheet>
  )
}

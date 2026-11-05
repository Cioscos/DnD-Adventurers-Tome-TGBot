import { useTranslation } from 'react-i18next'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, ApiError } from '@/api/client'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import { useToast } from '@/hooks/useToast'
import { haptic } from '@/auth/telegram'
import { notifyMutationError } from '@/lib/mutationError'
import type { Companion } from '@/types'

export interface HealSlot { level: number; left: number }

interface Props {
  charId: number
  comp: Companion
  slots: HealSlot[]
  onClose: () => void
}

/** Forma Selvatica da Combattimento (Circolo della Luna): azione bonus e uno slot curano la forma di 1d8 per livello dello
 *  slot. Il server tira i dadi e prende lo slot; qui si sceglie solo il livello. */
export default function WildHealSheet({ charId, comp, slots, onClose }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()

  const heal = useMutation({
    mutationFn: (level: number) => api.companions.wildHeal(charId, comp.id, level),
    onSuccess: (r) => {
      haptic.success()
      toast.info(t('character.extras.wild_heal_done', { n: r.healed, dice: `${r.rolls.length}d8` }), { description: r.rolls.join(' + ') })
      qc.invalidateQueries({ queryKey: ['companions', charId] })
      qc.invalidateQueries({ queryKey: ['character', charId] })
      qc.invalidateQueries({ queryKey: ['turn-state', charId] })
      onClose()
    },
    onError: (err) => {
      const code = err instanceof ApiError ? (err.detail as { code?: string } | null)?.code : undefined
      if (code === 'turn_slot_used') toast.error(t('character.attack.bonus_used'))
      else if (code === 'no_slot') toast.error(t('character.extras.wild_heal_no_slot'))
      else if (code === 'form_full_hp') toast.error(t('character.extras.wild_heal_full'))
      else notifyMutationError()
      qc.invalidateQueries({ queryKey: ['character', charId] })
    },
  })

  return (
    <Sheet open onClose={onClose} title={t('character.extras.wild_heal_title')} zClassName="z-[60]">
      <div className="flex flex-col gap-3 px-4 pb-4">
        <p className="text-sm font-body text-dnd-text">{t('character.extras.wild_heal_hint', { name: comp.name })}</p>
        {slots.length === 0 && <p className="text-sm font-body text-dnd-text-muted">{t('character.extras.wild_heal_no_slot')}</p>}
        {slots.map((s) => (
          <Button key={s.level} variant="secondary" className="min-h-11" loading={heal.isPending && heal.variables === s.level}
            disabled={heal.isPending} onClick={() => heal.mutate(s.level)}>
            {t('character.extras.wild_heal_slot', { level: s.level, left: s.left, dice: `${s.level}d8` })}
          </Button>
        ))}
      </div>
    </Sheet>
  )
}

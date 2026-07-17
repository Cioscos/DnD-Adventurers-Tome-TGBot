import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Minus, Plus } from 'lucide-react'
import { GiNightSleep as Moon, GiDiceSixFacesOne as Dice1 } from 'react-icons/gi'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import { hitDiceRemaining } from '@/lib/quickActions'
import type { CharacterClass } from '@/types'

interface HitDiceModalProps {
  classes: CharacterClass[]
  onSpend: (classId: number, count: number) => void
  onConfirmRest: () => void
  onClose: () => void
  isPending: boolean
  /** classId currently in flight on the shared hitDiceMutation (P4 scoping), undefined when none. */
  pendingClassId?: number
  /** True while the short-rest mutation itself is in flight (onConfirmRest). */
  restPending?: boolean
}

export default function HitDiceModal({
  classes,
  onSpend,
  onConfirmRest,
  onClose,
  isPending,
  pendingClassId,
  restPending,
}: HitDiceModalProps) {
  const { t } = useTranslation()
  const [hitDiceCounts, setHitDiceCounts] = useState<Record<number, number>>({})

  return (
    <Sheet open onClose={onClose} title={t('character.hp.short_rest')}>
      <div className="p-5 space-y-4">
        <div className="flex items-center gap-2 text-dnd-cobalt-bright">
          <Moon size={18} />
          <p className="text-sm text-dnd-text-muted font-body italic">
            {t('character.hp.hit_dice_spend_hint')}
          </p>
        </div>

        {classes.length === 0 && (
          <p className="text-sm text-dnd-text-muted text-center py-4 font-body italic">{t('common.none')}</p>
        )}

        <div className="space-y-3">
          {classes.map((cls) => {
            const remaining = hitDiceRemaining(cls)
            // Clamp at read-time: dopo una spesa il pool scende mentre lo sheet
            // resta montato — il count salvato non deve mai superare i residui.
            const count = Math.min(remaining, hitDiceCounts[cls.id] ?? 0)
            const thisPending = isPending && pendingClassId === cls.id
            return (
              <div key={cls.id} className="flex items-center gap-3 p-2 rounded-xl bg-dnd-surface border border-dnd-border">
                <div className="flex-1 min-w-0">
                  <p className="font-display font-bold text-sm text-dnd-gold-bright truncate">{cls.class_name}</p>
                  <p className="text-[11px] text-dnd-text-faint font-mono">
                    d{cls.hit_die ?? 8} · <span className="tabular-nums">{remaining}/{cls.level}</span>{' '}
                    {t('character.hp.hit_dice_remaining_label')}
                  </p>
                </div>
                <div className="flex items-center gap-1.5">
                  <Pressable
                    onClick={() => setHitDiceCounts((c) => ({ ...c, [cls.id]: Math.max(0, (c[cls.id] ?? 0) - 1) }))}
                    className="w-11 h-11 rounded-lg bg-dnd-surface-raised border border-dnd-border flex items-center justify-center text-dnd-gold"
                    whileTap={{ scale: 0.9 }}
                  >
                    <Minus size={14} />
                  </Pressable>
                  <span className="w-6 text-center font-mono font-bold text-dnd-gold-bright">{count}</span>
                  <Pressable
                    onClick={() => setHitDiceCounts((c) => ({ ...c, [cls.id]: Math.min(remaining, (c[cls.id] ?? 0) + 1) }))}
                    className="w-11 h-11 rounded-lg bg-dnd-surface-raised border border-dnd-border flex items-center justify-center text-dnd-gold"
                    whileTap={{ scale: 0.9 }}
                  >
                    <Plus size={14} />
                  </Pressable>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => { if (count > 0) onSpend(cls.id, count) }}
                    disabled={!count || remaining === 0}
                    loading={thisPending}
                    icon={<Dice1 size={14} />}
                    haptic="success"
                  >
                    <span className="sr-only">Roll</span>
                  </Button>
                </div>
              </div>
            )
          })}
        </div>

        {/* Annulla a sinistra, conferma a destra (convenzione ConfirmSheet). */}
        <div className="flex gap-2 pt-1">
          <Button variant="secondary" fullWidth onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button
            variant="primary"
            fullWidth
            onClick={onConfirmRest}
            disabled={isPending}
            loading={restPending}
            icon={<Moon size={16} />}
          >
            {t('character.hp.confirm_rest')}
          </Button>
        </div>
      </div>
    </Sheet>
  )
}

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import Card from '@/components/Card'
import type { CharacterClass } from '@/types'

interface HitDiceModalProps {
  classes: CharacterClass[]
  onSpend: (classId: number, count: number) => void
  onConfirmRest: () => void
  onClose: () => void
  isPending: boolean
}

export default function HitDiceModal({
  classes,
  onSpend,
  onConfirmRest,
  onClose,
  isPending,
}: HitDiceModalProps) {
  const { t } = useTranslation()
  const [hitDiceCounts, setHitDiceCounts] = useState<Record<number, number>>({})

  return (
    <div className="fixed inset-0 bg-black/60 flex items-end z-50 p-4">
      <Card className="w-full space-y-3">
        <h3 className="font-semibold">{'\uD83C\uDF19'} {t('character.hp.short_rest')}</h3>
        <p className="text-sm text-dnd-text-secondary">
          {t('character.hp.hit_dice_spend_hint')}
        </p>

        {classes.length === 0 && (
          <p className="text-sm text-dnd-text-secondary">{t('common.none')}</p>
        )}

        {classes.map((cls) => (
          <div key={cls.id} className="flex items-center gap-3">
            <span className="flex-1 text-sm">
              {cls.class_name} (d{cls.hit_die ?? 8})
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setHitDiceCounts((c) => ({ ...c, [cls.id]: Math.max(0, (c[cls.id] ?? 0) - 1) }))}
                className="w-7 h-7 rounded-lg bg-dnd-surface font-bold active:opacity-70"
              >{'\u2212'}</button>
              <span className="w-6 text-center font-bold">{hitDiceCounts[cls.id] ?? 0}</span>
              <button
                onClick={() => setHitDiceCounts((c) => ({ ...c, [cls.id]: (c[cls.id] ?? 0) + 1 }))}
                className="w-7 h-7 rounded-lg bg-dnd-surface font-bold active:opacity-70"
              >+</button>
              <button
                onClick={() => {
                  const count = hitDiceCounts[cls.id] ?? 0
                  if (count > 0) onSpend(cls.id, count)
                }}
                disabled={!hitDiceCounts[cls.id] || isPending}
                className="px-3 py-1 rounded-lg bg-dnd-success/30 text-dnd-success-text text-sm font-medium
                           disabled:opacity-30 active:opacity-70"
              >
                {'\uD83C\uDFB2'}
              </button>
            </div>
          </div>
        ))}

        <div className="flex gap-2 pt-1">
          <button
            onClick={() => {
              onConfirmRest()
            }}
            disabled={isPending}
            className="flex-1 py-2.5 rounded-xl bg-dnd-info/30 text-dnd-info-text font-medium disabled:opacity-40"
          >
            {t('character.hp.confirm_rest')}
          </button>
          <button
            onClick={onClose}
            className="flex-1 py-2.5 rounded-xl bg-dnd-surface"
          >
            {t('common.cancel')}
          </button>
        </div>
      </Card>
    </div>
  )
}

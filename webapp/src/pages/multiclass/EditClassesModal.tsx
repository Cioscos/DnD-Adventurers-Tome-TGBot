import { useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Check } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '@/api/client'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import { haptic } from '@/auth/telegram'
import type { CharacterFull, CharacterClass } from '@/types'

interface EditClassesModalProps {
  char: CharacterFull
  targetLevel: number
  onClose: () => void
}

export default function EditClassesModal({ char, targetLevel, onClose }: EditClassesModalProps) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const classes: CharacterClass[] = char.classes ?? []

  const [draft, setDraft] = useState<Record<number, number>>(
    Object.fromEntries(classes.map((c) => [c.id, c.level])),
  )

  const currentSum = useMemo(
    () => Object.values(draft).reduce((s, v) => s + (Number.isFinite(v) ? v : 0), 0),
    [draft],
  )
  const isValid = currentSum === targetLevel && Object.values(draft).every((v) => v >= 1 && v <= 20)

  const distribute = useMutation({
    mutationFn: () => {
      const payload = Object.entries(draft).map(([id, lv]) => ({
        class_id: Number(id),
        level: lv,
      }))
      return api.classes.distribute(char.id, payload)
    },
    onSuccess: (updated) => {
      qc.setQueryData(['character', char.id], updated)
      haptic.success()
      onClose()
    },
    onError: () => {
      haptic.error()
      toast.error(t('character.multiclass.edit.error_server'))
    },
  })

  const setLevel = (classId: number, level: number) => {
    const clamped = Math.max(1, Math.min(20, Math.round(level)))
    setDraft((d) => ({ ...d, [classId]: clamped }))
  }

  return (
    <div
      className="fixed inset-0 bg-black/70 z-50 flex items-end sm:items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <m.div
        initial={{ y: 40, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="w-full max-w-lg max-h-[90vh] overflow-y-auto"
      >
        <Surface variant="tome" ornamented className="space-y-4">
          <div className="text-center">
            <h2 className="font-display text-2xl font-black text-dnd-gold-bright uppercase tracking-widest">
              {t('character.multiclass.edit.title')}
            </h2>
            <p className="text-xs text-dnd-text-muted mt-1 font-body italic">
              {t('character.multiclass.edit.hint', { target: targetLevel })}
            </p>
          </div>

          {/* Sum indicator */}
          <div className={`text-center py-3 rounded-xl border transition-colors
              ${isValid
                ? 'bg-dnd-surface border-dnd-gold text-dnd-gold-bright'
                : 'bg-dnd-surface border-[var(--dnd-crimson)]/60 text-[var(--dnd-crimson-bright)]'}`}
          >
            <p className="text-[10px] font-cinzel uppercase tracking-[0.3em] opacity-80">
              {t('character.multiclass.edit.sum_label')}
            </p>
            <p className="font-display font-black text-3xl">
              {t('character.multiclass.edit.sum_display', { current: currentSum, target: targetLevel })}
            </p>
          </div>

          {/* Class rows */}
          <div className="space-y-2">
            {classes.map((cls) => (
              <Surface key={cls.id} variant="elevated" className="flex items-center gap-3 !py-2 !px-3">
                <div className="flex-1 min-w-0">
                  <p className="font-display font-bold text-dnd-gold-bright truncate">{cls.class_name}</p>
                  {cls.subclass && (
                    <p className="text-xs text-dnd-text-muted italic truncate">{cls.subclass}</p>
                  )}
                </div>
                <input
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={20}
                  value={draft[cls.id] ?? cls.level}
                  onChange={(e) => setLevel(cls.id, Number(e.target.value))}
                  className="w-20 min-h-[44px] rounded-lg bg-dnd-surface border border-dnd-border text-dnd-gold-bright font-mono text-center"
                  aria-label={`${cls.class_name} level`}
                />
              </Surface>
            ))}
          </div>

          {/* Footer */}
          <div className="grid grid-cols-2 gap-2">
            <Button variant="ghost" size="md" fullWidth onClick={onClose}>
              {t('character.multiclass.edit.cancel')}
            </Button>
            <Button
              variant="primary"
              size="md"
              fullWidth
              disabled={!isValid}
              loading={distribute.isPending}
              icon={<Check size={16} />}
              haptic="success"
              onClick={() => distribute.mutate()}
            >
              {t('character.multiclass.edit.confirm')}
            </Button>
          </div>
        </Surface>
      </m.div>
    </div>
  )
}

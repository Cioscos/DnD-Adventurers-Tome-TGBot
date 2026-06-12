import { useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { ChevronsUp } from 'lucide-react'
import { api } from '@/api/client'
import Surface from '@/components/ui/Surface'
import { CornerFlourishes } from '@/components/ui/Ornament'
import Button from '@/components/ui/Button'
import { toast } from 'sonner'
import { haptic } from '@/auth/telegram'
import { progressionRows, localizeFeatures } from '@/lib/classProgression'
import { useRegisterOverlay } from '@/store/overlayStore'
import { useOverlayDismiss } from '@/hooks/useOverlayDismiss'
import { fireLevelUpConfetti } from '@/lib/celebrate'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import type { CharacterFull, CharacterClass } from '@/types'

interface LevelUpModalProps {
  char: CharacterFull
  xpLevel: number
  onClose: () => void
}

export default function LevelUpModal({ char, xpLevel, onClose }: LevelUpModalProps) {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const reducedMotion = useReducedMotion()
  useRegisterOverlay(true)
  useOverlayDismiss(true, onClose)
  const classes = useMemo<CharacterClass[]>(() => char.classes ?? [], [char.classes])
  // For multiclass characters the single-class progression table's proficiency
  // bonus is NOT the character's real PB (which scales with total level), so we
  // hide that misleading row when more than one class is present.
  const isMulticlass = classes.length > 1
  const [selectedClassId, setSelectedClassId] = useState<number>(classes[0]?.id ?? 0)

  const selectedClass = useMemo(
    () => classes.find((c) => c.id === selectedClassId) ?? classes[0],
    [classes, selectedClassId],
  )
  const selectedAtMax = !!selectedClass && selectedClass.level >= 20

  const distribute = useMutation({
    mutationFn: () => {
      if (!selectedClass) return Promise.reject(new Error('no class selected'))
      const payload = classes.map((c) => ({
        class_id: c.id,
        level: c.id === selectedClass.id ? c.level + 1 : c.level,
      }))
      return api.classes.distribute(char.id, payload)
    },
    onSuccess: (updated) => {
      qc.setQueryData(['character', char.id], updated)
      haptic.success()
      // Celebratory beat for the class level-up. The modal closes on success,
      // so a panel pulse wouldn't be seen — fire the screen confetti + toast
      // (the same call-out as the XP page). Reduced-motion: toast + icon only.
      const newTotal = classes.reduce((sum, c) => sum + c.level, 0) + 1
      toast.success(t('character.xp.level_up_toast', { level: newTotal }), {
        duration: 3500,
        icon: '✨',
      })
      if (!reducedMotion) fireLevelUpConfetti()
      if (updated.hp_gained && updated.hp_gained > 0) {
        toast.success(t('character.xp.hp_gained_toast', { hp: updated.hp_gained }), {
          duration: 2000,
          icon: '❤',
        })
      }
      onClose()
    },
    onError: () => haptic.error(),
  })

  const nextLevels = useMemo(() => {
    if (!selectedClass) return []
    const out: number[] = []
    for (let i = 1; i <= 3; i++) {
      const target = selectedClass.level + i
      if (target <= 20) out.push(target)
    }
    return out
  }, [selectedClass])

  if (!selectedClass) return null

  const entriesForClass = progressionRows(selectedClass.class_name)

  return (
    <div
      className="fixed inset-0 bg-[var(--dnd-overlay)] backdrop-blur-[6px] z-50 flex items-end sm:items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <m.div
        initial={{ y: 40, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="w-full max-w-xl max-h-[90vh] overflow-y-auto"
      >
        <Surface variant="tome" ornamented className="space-y-6 p-6">
          <div className="text-dnd-gold-dim pointer-events-none"><CornerFlourishes /></div>
          {/* Header */}
          <div className="text-center">
            <h2 className="font-display text-2xl font-black text-dnd-gold-bright uppercase tracking-widest">
              {t('character.multiclass.level_up.title')}
            </h2>
            <p className="text-xs text-dnd-text-muted mt-1 font-body italic">
              {t('character.multiclass.level_up.subtitle', { level: xpLevel })}
            </p>
          </div>

          {/* Preview unlocks */}
          <Surface variant="flat" className="space-y-5 p-5">
            <p className="text-[10px] font-cinzel uppercase tracking-[0.3em] text-dnd-gold-dim text-center">
              {t('character.multiclass.level_up.preview_next_levels')}
            </p>
            {!entriesForClass ? (
              <p className="text-sm text-dnd-text-muted italic text-center">
                {t('character.multiclass.level_up.progression_missing')}
              </p>
            ) : (
              nextLevels.map((targetLevel, idx) => {
                const curr = entriesForClass[targetLevel - 1]
                const prev = entriesForClass[targetLevel - 2] ?? null
                const pbChanged = !isMulticlass && prev && curr.proficiency_bonus !== prev.proficiency_bonus
                const newSlotLevels: number[] = []
                if (curr.spell_slots && prev?.spell_slots) {
                  curr.spell_slots.forEach((count, i) => {
                    if (count > 0 && prev.spell_slots![i] === 0) newSlotLevels.push(i + 1)
                  })
                } else if (curr.spell_slots && !prev?.spell_slots) {
                  curr.spell_slots.forEach((count, i) => {
                    if (count > 0) newSlotLevels.push(i + 1)
                  })
                }
                return (
                  <div
                    key={targetLevel}
                    className={`flex gap-4 items-start ${idx > 0 ? 'pt-4 border-t border-dnd-border/50' : ''}`}
                  >
                    {/* Level badge */}
                    <div className="flex-shrink-0 w-14 h-14 rounded-xl bg-gradient-gold flex flex-col items-center justify-center shadow-engrave">
                      <span className="text-[11px] font-cinzel uppercase tracking-wider text-dnd-ink/70 leading-none">
                        {t('character.equipment.progression.level_header')}
                      </span>
                      <span className="font-display font-black text-2xl text-dnd-ink leading-none mt-0.5">
                        {targetLevel}
                      </span>
                    </div>

                    {/* Unlocks */}
                    <div className="flex-1 min-w-0 space-y-2 pt-1">
                      <p className="text-sm text-dnd-text font-body leading-relaxed break-words">
                        {curr.features ? localizeFeatures(curr.features, i18n.language) : '—'}
                      </p>
                      {pbChanged && (
                        <p className="text-xs text-dnd-gold font-mono">
                          {t('character.multiclass.level_up.proficiency_change', {
                            from: prev!.proficiency_bonus,
                            to: curr.proficiency_bonus,
                          })}
                        </p>
                      )}
                      {newSlotLevels.map((lvl) => (
                        <p key={lvl} className="text-xs text-dnd-arcane-bright font-mono">
                          {t('character.multiclass.level_up.new_spell_slot', { level: lvl })}
                        </p>
                      ))}
                    </div>
                  </div>
                )
              })
            )}
          </Surface>

          {/* Class selector */}
          <div className="space-y-3">
            <p className="text-[10px] font-cinzel uppercase tracking-[0.3em] text-dnd-gold-dim text-center">
              {t('character.multiclass.level_up.choose_class')}
            </p>
            <div className="flex gap-3 flex-wrap">
              {classes.map((cls) => {
                const active = cls.id === selectedClassId
                return (
                  <button
                    key={cls.id}
                    type="button"
                    onClick={() => setSelectedClassId(cls.id)}
                    className={`min-h-[52px] px-4 py-2 rounded-xl font-cinzel text-xs uppercase tracking-widest flex-1 min-w-[120px] transition-all
                      ${active
                        ? 'bg-gradient-gold text-dnd-ink shadow-engrave border-2 border-dnd-gold scale-[1.02]'
                        : 'bg-dnd-surface text-dnd-text border border-dnd-border hover:border-dnd-gold/60'}`}
                  >
                    <span className="block">{cls.class_name}</span>
                    <span className="block text-[10px] opacity-70 font-mono mt-0.5">
                      {t('character.equipment.progression.level_header')} {cls.level}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Confirm — visually separated footer */}
          <div className="pt-5 border-t border-dnd-border/50">
            <Button
              variant="primary"
              size="lg"
              fullWidth
              onClick={() => {
                if (selectedAtMax) {
                  toast.info(t('character.multiclass.level_up.at_max_toast'))
                  return
                }
                distribute.mutate()
              }}
              disabled={selectedAtMax}
              loading={distribute.isPending}
              icon={<ChevronsUp size={18} />}
              haptic="medium"
            >
              {t('character.multiclass.level_up.confirm')}
            </Button>
          </div>
        </Surface>
      </m.div>
    </div>
  )
}

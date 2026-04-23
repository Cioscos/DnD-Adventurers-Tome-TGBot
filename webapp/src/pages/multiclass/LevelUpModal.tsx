import { useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { ChevronsUp } from 'lucide-react'
import { api } from '@/api/client'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import { toast } from 'sonner'
import { haptic } from '@/auth/telegram'
import classProgression from '@/data/class-progression.json'
import type { CharacterFull, CharacterClass } from '@/types'

type ProgressionEntry = {
  features: string
  proficiency_bonus: number
  spell_slots: number[] | null
}

type ClassProgression = Record<string, ProgressionEntry[]>

const PROGRESSION = classProgression as ClassProgression

interface LevelUpModalProps {
  char: CharacterFull
  xpLevel: number
  onClose: () => void
}

export default function LevelUpModal({ char, xpLevel, onClose }: LevelUpModalProps) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const classes: CharacterClass[] = char.classes ?? []
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
      if ((updated as any).hp_gained && (updated as any).hp_gained > 0) {
        toast.success(t('character.xp.hp_gained_toast', { hp: (updated as any).hp_gained }), {
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

  const entriesForClass = PROGRESSION[selectedClass.class_name]

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
        className="w-full max-w-xl max-h-[90vh] overflow-y-auto"
      >
        <Surface variant="tome" ornamented className="space-y-6 p-6">
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
                const pbChanged = prev && curr.proficiency_bonus !== prev.proficiency_bonus
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
                      <span className="text-[9px] font-cinzel uppercase tracking-widest text-dnd-ink/70 leading-none">
                        Liv
                      </span>
                      <span className="font-display font-black text-2xl text-dnd-ink leading-none mt-0.5">
                        {targetLevel}
                      </span>
                    </div>

                    {/* Unlocks */}
                    <div className="flex-1 min-w-0 space-y-2 pt-1">
                      <p className="text-sm text-dnd-text font-body leading-relaxed break-words">
                        {curr.features || '—'}
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
                      Liv {cls.level}
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

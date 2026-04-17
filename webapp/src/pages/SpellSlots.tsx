import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Gem, Minus, Plus, RotateCcw, X, Sparkles } from 'lucide-react'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import Reveal from '@/components/ui/Reveal'
import { haptic } from '@/auth/telegram'
import { spring, stagger } from '@/styles/motion'
import type { SpellSlot } from '@/types'

export default function SpellSlots() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const updateSlot = useMutation({
    mutationFn: ({ slotId, used }: { slotId: number; used: number }) =>
      api.spellSlots.update(charId, slotId, { used }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['character', charId] }),
  })

  const updateTotal = useMutation({
    mutationFn: ({ slotId, total }: { slotId: number; total: number }) =>
      api.spellSlots.update(charId, slotId, { total }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['character', charId] }),
  })

  const addSlot = useMutation({
    mutationFn: (level: number) => api.spellSlots.add(charId, level, 1),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      haptic.success()
    },
  })

  const removeSlot = useMutation({
    mutationFn: (slotId: number) => api.spellSlots.remove(charId, slotId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['character', charId] }),
  })

  const resetAll = useMutation({
    mutationFn: () => api.spellSlots.resetAll(charId),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.success()
    },
  })

  if (!char) return null

  const slots: SpellSlot[] = [...(char.spell_slots ?? [])].sort((a, b) => a.level - b.level)
  const existingLevels = new Set(slots.map((s) => s.level))
  const missingLevels = [1, 2, 3, 4, 5, 6, 7, 8, 9].filter((l) => !existingLevels.has(l))

  return (
    <Layout title={t('character.slots.title')} backTo={`/char/${charId}`} group="magic" page="slots">
      {slots.length > 0 && (
        <Button
          variant="arcane"
          fullWidth
          onClick={() => resetAll.mutate()}
          loading={resetAll.isPending}
          icon={<RotateCcw size={16} />}
          haptic="success"
        >
          {t('character.slots.reset_all')}
        </Button>
      )}

      {slots.length === 0 && (
        <Surface variant="flat" className="text-center py-8">
          <Gem className="mx-auto text-dnd-text-faint mb-2" size={32} />
          <p className="text-dnd-text-muted font-body italic">{t('common.none')}</p>
        </Surface>
      )}

      <Reveal.Stagger stagger={stagger.list} className="space-y-2">
        {slots.map((slot) => (
          <Reveal.Item key={slot.id}>
            <Surface variant="elevated" ornamented>
              {/* Level banner + meta */}
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-full bg-gradient-arcane-mist border border-dnd-arcane-bright flex items-center justify-center text-dnd-arcane-bright font-cinzel font-black text-sm">
                    {slot.level}
                  </div>
                  <span className="font-display font-bold text-dnd-gold-bright">
                    {t('character.slots.level', { level: slot.level })}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-sm font-mono font-bold ${slot.available > 0 ? 'text-[var(--dnd-emerald-bright)]' : 'text-dnd-text-faint'}`}>
                    {slot.available}/{slot.total}
                  </span>
                  <m.button
                    onClick={() => removeSlot.mutate(slot.id)}
                    className="w-7 h-7 rounded-lg text-[var(--dnd-crimson-bright)] flex items-center justify-center hover:bg-[var(--dnd-crimson)]/10"
                    whileTap={{ scale: 0.9 }}
                    aria-label="Remove"
                  >
                    <X size={14} />
                  </m.button>
                </div>
              </div>

              {/* Slot gems */}
              <div className="flex gap-2 flex-wrap mb-3">
                {Array.from({ length: slot.total }).map((_, i) => {
                  const isUsed = i < slot.used
                  return (
                    <m.button
                      key={i}
                      onClick={() => {
                        const newUsed = i < slot.used ? i : i + 1
                        updateSlot.mutate({ slotId: slot.id, used: newUsed > slot.total ? slot.total : newUsed })
                        haptic.light()
                      }}
                      className={`w-10 h-10 rounded-full flex items-center justify-center
                        ${isUsed
                          ? 'bg-dnd-surface border-2 border-dashed border-dnd-gold-dim/50'
                          : 'bg-gradient-to-br from-dnd-arcane-bright to-dnd-arcane-deep border-2 border-dnd-arcane-bright shadow-[0_0_12px_rgba(197,137,232,0.6)]'}`}
                      animate={isUsed ? { scale: 1 } : { scale: [1.15, 1] }}
                      transition={spring.elastic}
                      whileTap={{ scale: 0.85 }}
                      aria-label={`Slot ${i + 1} ${isUsed ? 'used' : 'available'}`}
                    >
                      {!isUsed && <Gem size={16} className="text-white drop-shadow" />}
                    </m.button>
                  )
                })}
              </div>

              {/* Total editor */}
              <div className="flex items-center gap-2 pt-2 border-t border-dnd-border/40">
                <span className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim flex-1">
                  {t('character.slots.total')}
                </span>
                <m.button
                  onClick={() => updateTotal.mutate({ slotId: slot.id, total: Math.max(1, slot.total - 1) })}
                  className="w-8 h-8 rounded-lg bg-dnd-surface border border-dnd-border flex items-center justify-center text-dnd-gold"
                  whileTap={{ scale: 0.9 }}
                >
                  <Minus size={14} />
                </m.button>
                <span className="w-6 text-center font-mono font-bold text-dnd-gold-bright">{slot.total}</span>
                <m.button
                  onClick={() => updateTotal.mutate({ slotId: slot.id, total: slot.total + 1 })}
                  className="w-8 h-8 rounded-lg bg-dnd-surface border border-dnd-border flex items-center justify-center text-dnd-gold"
                  whileTap={{ scale: 0.9 }}
                >
                  <Plus size={14} />
                </m.button>
              </div>
            </Surface>
          </Reveal.Item>
        ))}
      </Reveal.Stagger>

      {missingLevels.length > 0 && (
        <Surface variant="flat" className="mt-3">
          <div className="flex items-center gap-2 mb-2">
            <Sparkles size={14} className="text-dnd-arcane-bright" />
            <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim">
              {t('character.slots.add_level')}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {missingLevels.map((level) => (
              <m.button
                key={level}
                onClick={() => addSlot.mutate(level)}
                className="px-3 py-1.5 rounded-lg bg-dnd-surface border border-dnd-arcane/60
                           text-dnd-arcane-bright font-cinzel text-xs uppercase tracking-wider
                           hover:border-dnd-arcane hover:shadow-halo-arcane transition-[border-color,box-shadow] duration-200"
                whileTap={{ scale: 0.92 }}
              >
                + {t('character.slots.level', { level })}
              </m.button>
            ))}
          </div>
        </Surface>
      )}
    </Layout>
  )
}

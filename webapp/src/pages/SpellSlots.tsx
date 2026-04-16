import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import DndButton from '@/components/DndButton'
import ScrollArea from '@/components/ScrollArea'
import { haptic } from '@/auth/telegram'
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
        <DndButton
          variant="secondary"
          onClick={() => resetAll.mutate()}
          loading={resetAll.isPending}
          className="w-full !bg-dnd-info/20 !text-dnd-info-text !border-dnd-info/30"
        >
          {t('character.slots.reset_all')}
        </DndButton>
      )}

      {slots.length === 0 && (
        <Card>
          <p className="text-center text-dnd-text-secondary">{t('common.none')}</p>
        </Card>
      )}

      <ScrollArea>
        <div className="space-y-2">
          {slots.map((slot) => (
            <Card key={slot.id}>
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold text-dnd-text">{t('character.slots.level', { level: slot.level })}</span>
                <div className="flex gap-2 items-center">
                  <span className={`text-sm font-bold ${slot.available > 0 ? 'text-dnd-success-text' : 'text-dnd-text-secondary'}`}>
                    {slot.available}/{slot.total}
                  </span>
                  <button
                    onClick={() => removeSlot.mutate(slot.id)}
                    className="text-xs text-[var(--dnd-danger)] ml-2"
                  >&#x2715;</button>
                </div>
              </div>

              {/* Slot dots */}
              <div className="flex gap-2 flex-wrap mb-2">
                {Array.from({ length: slot.total }).map((_, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      const newUsed = i < slot.used ? i : i + 1
                      updateSlot.mutate({ slotId: slot.id, used: newUsed > slot.total ? slot.total : newUsed })
                      haptic.light()
                    }}
                    className={`w-8 h-8 rounded-full border-2 transition-all
                      ${i < slot.used
                        ? 'bg-dnd-arcane/40 border-dnd-arcane/60'
                        : 'border-dnd-arcane bg-transparent'}`}
                  />
                ))}
              </div>

              {/* Edit total */}
              <div className="flex items-center gap-2">
                <span className="text-xs text-dnd-text-secondary">{t('character.slots.total')}:</span>
                <button
                  onClick={() => updateTotal.mutate({ slotId: slot.id, total: Math.max(1, slot.total - 1) })}
                  className="w-8 h-8 rounded-lg bg-dnd-surface text-sm font-bold text-dnd-text flex items-center justify-center"
                >&#x2212;</button>
                <span className="text-sm font-bold w-4 text-center text-dnd-text">{slot.total}</span>
                <button
                  onClick={() => updateTotal.mutate({ slotId: slot.id, total: slot.total + 1 })}
                  className="w-8 h-8 rounded-lg bg-dnd-surface text-sm font-bold text-dnd-text flex items-center justify-center"
                >+</button>
              </div>
            </Card>
          ))}
        </div>

        {missingLevels.length > 0 && (
          <Card className="mt-3">
            <p className="text-xs text-dnd-text-secondary mb-2">{t('character.slots.add_level')}</p>
            <div className="flex flex-wrap gap-2">
              {missingLevels.map((level) => (
                <DndButton
                  key={level}
                  variant="secondary"
                  onClick={() => addSlot.mutate(level)}
                  className="!px-3 !py-1.5 !min-h-0 !text-sm !bg-dnd-arcane/20 !text-dnd-arcane-text !border-dnd-arcane/30"
                >
                  + Liv. {level}
                </DndButton>
              ))}
            </div>
          </Card>
        )}
      </ScrollArea>
    </Layout>
  )
}

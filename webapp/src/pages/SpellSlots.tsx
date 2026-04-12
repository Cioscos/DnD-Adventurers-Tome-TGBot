import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
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
    <Layout title={t('character.slots.title')} backTo={`/char/${charId}`}>
      {slots.length > 0 && (
        <button
          onClick={() => resetAll.mutate()}
          disabled={resetAll.isPending}
          className="w-full py-3 rounded-2xl bg-blue-500/20 text-blue-300 font-medium active:opacity-70"
        >
          🔄 {t('character.slots.reset_all')}
        </button>
      )}

      {slots.length === 0 && (
        <Card>
          <p className="text-center text-[var(--tg-theme-hint-color)]">{t('common.none')}</p>
        </Card>
      )}

      <div className="space-y-2">
        {slots.map((slot) => (
          <Card key={slot.id}>
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold">{t('character.slots.level', { level: slot.level })}</span>
              <div className="flex gap-2 items-center">
                <span className={`text-sm font-bold ${slot.available > 0 ? 'text-green-400' : 'text-[var(--tg-theme-hint-color)]'}`}>
                  {slot.available}/{slot.total}
                </span>
                <button
                  onClick={() => removeSlot.mutate(slot.id)}
                  className="text-xs text-red-400 ml-2"
                >✕</button>
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
                      ? 'bg-purple-500/40 border-purple-500/60'
                      : 'border-purple-400 bg-transparent'}`}
                />
              ))}
            </div>

            {/* Edit total */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-[var(--tg-theme-hint-color)]">{t('character.slots.total')}:</span>
              <button
                onClick={() => updateTotal.mutate({ slotId: slot.id, total: Math.max(1, slot.total - 1) })}
                className="w-6 h-6 rounded-lg bg-white/10 text-sm font-bold"
              >−</button>
              <span className="text-sm font-bold w-4 text-center">{slot.total}</span>
              <button
                onClick={() => updateTotal.mutate({ slotId: slot.id, total: slot.total + 1 })}
                className="w-6 h-6 rounded-lg bg-white/10 text-sm font-bold"
              >+</button>
            </div>
          </Card>
        ))}
      </div>

      {missingLevels.length > 0 && (
        <Card>
          <p className="text-xs text-[var(--tg-theme-hint-color)] mb-2">{t('character.slots.add_level')}</p>
          <div className="flex flex-wrap gap-2">
            {missingLevels.map((level) => (
              <button
                key={level}
                onClick={() => addSlot.mutate(level)}
                className="px-3 py-1.5 rounded-xl bg-purple-500/20 text-purple-300 text-sm font-medium"
              >
                + Liv. {level}
              </button>
            ))}
          </div>
        </Card>
      )}
    </Layout>
  )
}

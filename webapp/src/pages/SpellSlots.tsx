import { useState, useRef, useCallback, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Minus, Plus, RotateCcw, X } from 'lucide-react'
import { GiCutDiamond as Gem, GiSparkles as Sparkles } from 'react-icons/gi'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import Reveal from '@/components/ui/Reveal'
import EmptyState from '@/components/ui/EmptyState'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import { haptic } from '@/auth/telegram'
import { stagger } from '@/styles/motion'
import { toRoman } from '@/lib/roman'
import type { SpellSlot } from '@/types'
import SpellSlotsSkeleton from '@/components/skeletons/SpellSlotsSkeleton'
import AutoModeBanner from '@/components/character/AutoModeBanner'

// Editable Total — inline numeric input + hold-to-accelerate ± buttons.
// Lets users jump from 1 to 8 by typing or by holding the button instead of
// 7 individual taps.
interface TotalEditorProps {
  slotId: number
  total: number
  label: string
  decrementAria: string
  incrementAria: string
  onCommit: (next: number) => void
}

function TotalEditor({ total, label, decrementAria, incrementAria, onCommit }: TotalEditorProps) {
  const [draft, setDraft] = useState<string>(String(total))
  const [editing, setEditing] = useState(false)
  const repeatRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const valueRef = useRef(total)

  useEffect(() => {
    valueRef.current = total
    if (!editing) setDraft(String(total))
  }, [total, editing])

  useEffect(() => () => {
    if (repeatRef.current) clearTimeout(repeatRef.current)
  }, [])

  const stopRepeat = useCallback(() => {
    if (repeatRef.current) {
      clearTimeout(repeatRef.current)
      repeatRef.current = null
    }
  }, [])

  const startRepeat = useCallback((delta: 1 | -1) => {
    const apply = () => {
      const next = Math.max(1, valueRef.current + delta)
      if (next !== valueRef.current) {
        valueRef.current = next
        onCommit(next)
      }
    }
    apply()
    let delay = 380
    const tick = () => {
      apply()
      delay = Math.max(60, delay - 35)
      repeatRef.current = setTimeout(tick, delay)
    }
    repeatRef.current = setTimeout(tick, 380)
  }, [onCommit])

  const commitDraft = () => {
    const parsed = parseInt(draft, 10)
    if (Number.isFinite(parsed) && parsed >= 1 && parsed !== total) {
      onCommit(parsed)
    } else {
      setDraft(String(total))
    }
    setEditing(false)
  }

  return (
    <div className="flex items-center gap-2 pt-2 border-t border-dnd-border/40">
      <span className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim flex-1">
        {label}
      </span>
      <m.button
        onPointerDown={() => startRepeat(-1)}
        onPointerUp={stopRepeat}
        onPointerLeave={stopRepeat}
        onPointerCancel={stopRepeat}
        className="w-11 h-11 rounded-lg bg-dnd-surface border border-dnd-border flex items-center justify-center text-dnd-gold"
        whileTap={{ scale: 0.9 }}
        aria-label={decrementAria}
        type="button"
      >
        <Minus size={16} />
      </m.button>
      <input
        type="number"
        min={1}
        inputMode="numeric"
        value={draft}
        onFocus={() => setEditing(true)}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commitDraft}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault()
            ;(e.target as HTMLInputElement).blur()
          }
        }}
        className="w-14 h-9 text-center bg-dnd-surface border border-dnd-border rounded-lg
                   font-mono font-bold text-dnd-gold-bright tabular-nums
                   focus:border-dnd-gold/60 focus:outline-none"
      />
      <m.button
        onPointerDown={() => startRepeat(1)}
        onPointerUp={stopRepeat}
        onPointerLeave={stopRepeat}
        onPointerCancel={stopRepeat}
        className="w-11 h-11 rounded-lg bg-dnd-surface border border-dnd-border flex items-center justify-center text-dnd-gold"
        whileTap={{ scale: 0.9 }}
        aria-label={incrementAria}
        type="button"
      >
        <Plus size={16} />
      </m.button>
    </div>
  )
}

export default function SpellSlots() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [confirmResetOpen, setConfirmResetOpen] = useState(false)

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
      setConfirmResetOpen(false)
    },
  })

  if (!char) {
    return (
      <Layout title={t('character.slots.title')} backTo={`/char/${charId}`} group="magic" page="slots">
        <SpellSlotsSkeleton />
      </Layout>
    )
  }

  const slots: SpellSlot[] = [...(char.spell_slots ?? [])].sort(
    (a, b) => a.level - b.level || Number(a.is_pact) - Number(b.is_pact),
  )
  // Manual "add level" affordance targets the regular pool only.
  const existingLevels = new Set(slots.filter((s) => !s.is_pact).map((s) => s.level))
  const missingLevels = [1, 2, 3, 4, 5, 6, 7, 8, 9].filter((l) => !existingLevels.has(l))
  const slotsMode = ((char.settings as Record<string, unknown> | undefined)?.spell_slots_mode as string | undefined) ?? 'auto'

  return (
    <Layout title={t('character.slots.title')} backTo={`/char/${charId}`} group="magic" page="slots">
      {/* Banner Auto-mode — collassabile, ricorda lo stato (localStorage). */}
      {slotsMode === 'auto' && (
        <AutoModeBanner onGoToSettings={() => navigate(`/char/${charId}/settings`)} />
      )}

      {slots.length > 0 && (
        <Button
          variant="arcane"
          fullWidth
          onClick={() => setConfirmResetOpen(true)}
          loading={resetAll.isPending}
          icon={<RotateCcw size={16} />}
          haptic="success"
        >
          {t('character.slots.reset_all')}
        </Button>
      )}

      {slots.length === 0 && (
        <EmptyState
          icon={<Gem size={32} />}
          title={t('common.none')}
          hint={slotsMode === 'auto' ? t('character.slots.auto_hint') : t('character.slots.manual_empty_hint')}
        />
      )}

      <Reveal.Stagger stagger={stagger.list} className="space-y-2">
        {slots.map((slot) => (
          <Reveal.Item key={slot.id}>
            <Surface variant="elevated" ornamented>
              {/* Level banner + meta */}
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-full bg-gradient-arcane-mist border border-dnd-arcane-bright flex items-center justify-center text-dnd-arcane-bright font-cinzel font-black text-sm">
                    {toRoman(slot.level)}
                  </div>
                  <span className="font-display font-bold text-dnd-gold-bright">
                    {t('character.slots.level', { level: slot.level })}
                  </span>
                  {slot.is_pact && (
                    <span className="px-1.5 py-0.5 rounded-full border border-dnd-arcane/60 bg-dnd-arcane-mist/30 text-dnd-arcane-bright font-cinzel text-[9px] uppercase tracking-widest">
                      {t('character.slots.pact_badge')}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-sm font-mono font-bold tabular-nums ${slot.available > 0 ? 'text-[var(--dnd-emerald-bright)]' : 'text-dnd-text-faint'}`}>
                    {slot.available}/{slot.total}
                  </span>
                  {slotsMode !== 'auto' && (
                    <m.button
                      onClick={() => removeSlot.mutate(slot.id)}
                      className="w-11 h-11 rounded-lg text-[var(--dnd-crimson-bright)] flex items-center justify-center hover:bg-[var(--dnd-crimson)]/10"
                      whileTap={{ scale: 0.9 }}
                      aria-label="Remove"
                    >
                      <X size={16} />
                    </m.button>
                  )}
                </div>
              </div>

              {/* Slot gems */}
              <div className="flex gap-2 flex-wrap mb-3">
                {Array.from({ length: slot.total }).map((_, i) => (
                  <m.button
                    key={i}
                    type="button"
                    onClick={() => {
                      if (i < slot.used) {
                        haptic.light()
                        updateSlot.mutate({ slotId: slot.id, used: Math.max(0, slot.used - 1) })
                      } else {
                        haptic.medium()
                        updateSlot.mutate({ slotId: slot.id, used: Math.min(slot.total, slot.used + 1) })
                      }
                    }}
                    whileTap={{ scale: 0.9 }}
                    aria-label={t('character.slots.gem_aria', {
                      level: slot.level,
                      index: i + 1,
                      total: slot.total,
                      state: i < slot.used
                        ? t('character.slots.state_used')
                        : t('character.slots.state_available'),
                    })}
                    aria-pressed={i < slot.used}
                    className={`hit-44 w-7 h-7 rounded-full border-2 transition-all ${
                      i < slot.used
                        ? 'bg-gradient-to-br from-dnd-gold-deep to-dnd-gold-bright border-dnd-gold-bright shadow-[0_0_10px_rgba(244,208,111,0.5)]'
                        : 'bg-transparent border-dnd-gold-dim/60 hover:border-dnd-gold-bright'
                    }`}
                  />
                ))}
              </div>

              {/* Total editor — hidden in Auto mode (totals are class-derived). */}
              {slotsMode !== 'auto' && (
                <TotalEditor
                  slotId={slot.id}
                  total={slot.total}
                  label={t('character.slots.total')}
                  decrementAria={t('character.slots.decrement_total', { defaultValue: '-1' })}
                  incrementAria={t('character.slots.increment_total', { defaultValue: '+1' })}
                  onCommit={(next) => updateTotal.mutate({ slotId: slot.id, total: next })}
                />
              )}
            </Surface>
          </Reveal.Item>
        ))}
      </Reveal.Stagger>

      {/* Manual creation of slot levels — hidden in Auto mode. */}
      {slotsMode !== 'auto' && missingLevels.length > 0 && (
        <Surface variant="flat" className="mt-3">
          <div className="flex items-center gap-2 mb-2">
            <Sparkles size={14} className="text-dnd-arcane-bright" />
            <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim">
              {t('character.slots.add_new_level')}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {missingLevels.map((level) => (
              <m.button
                key={level}
                onClick={() => addSlot.mutate(level)}
                className="min-h-[44px] px-3 py-1.5 rounded-lg bg-dnd-surface border border-dnd-arcane/60
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

      <ConfirmSheet
        open={confirmResetOpen}
        onClose={() => setConfirmResetOpen(false)}
        title={t('character.slots.reset_all')}
        body={t('character.slots.reset_confirm')}
        confirmLabel={t('common.confirm')}
        cancelLabel={t('common.cancel')}
        confirmVariant="primary"
        loading={resetAll.isPending}
        onConfirm={() => resetAll.mutate()}
      />
    </Layout>
  )
}

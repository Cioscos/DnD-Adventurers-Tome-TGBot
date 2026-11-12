import { notifyMutationError } from '@/lib/mutationError'
import { useState, useRef, useCallback, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Minus, Plus, RotateCcw, X } from 'lucide-react'
import { GiCutDiamond as Gem } from 'react-icons/gi'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import Reveal from '@/components/ui/Reveal'
import EmptyState from '@/components/ui/EmptyState'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import { haptic } from '@/auth/telegram'
import { stagger } from '@/styles/motion'
import { LEDGER_LABEL, LEDGER_TITLE, gemClass } from '@/styles/ledger'
import type { CharacterFull, SpellSlot } from '@/types'
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
  /** BE mutation in flight for THIS slot's total — drives the ± buttons' spinner/disabled state. */
  pending: boolean
  onCommit: (next: number) => void
}

function TotalEditor({ total, label, decrementAria, incrementAria, pending, onCommit }: TotalEditorProps) {
  const [draft, setDraft] = useState<string>(String(total))
  const [editing, setEditing] = useState(false)
  const repeatRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Handler currently registered on `window` for pointerup/pointercancel — kept so
  // stopRepeat() can remove it even when the button itself never gets the event
  // (see stopRepeat below).
  const releaseRef = useRef<(() => void) | null>(null)
  const valueRef = useRef(total)

  useEffect(() => {
    valueRef.current = total
    if (!editing) setDraft(String(total))
  }, [total, editing])

  // Ends the repeat chain and detaches the window-level release listener.
  // Registered on `window` (not just the button's own onPointerUp/onPointerLeave/
  // onPointerCancel) because the ± button can get `disabled` mid-hold when
  // `pending` flips true (a previous release's PATCH still in flight): a disabled
  // <button> stops receiving pointer events, so relying solely on its own handlers
  // would leave the repeat firing forever after release. Window still sees the
  // pointerup/pointercancel (it bubbles from whatever element is now under the
  // pointer once the disabled button drops out of hit-testing), so the chain
  // always stops on release regardless of the button's disabled state.
  const stopRepeat = useCallback(() => {
    if (repeatRef.current) {
      clearTimeout(repeatRef.current)
      repeatRef.current = null
    }
    if (releaseRef.current) {
      window.removeEventListener('pointerup', releaseRef.current)
      window.removeEventListener('pointercancel', releaseRef.current)
      releaseRef.current = null
    }
  }, [])

  useEffect(() => stopRepeat, [stopRepeat])

  // Durante la pressione si aggiorna solo il draft locale; il valore finale va
  // al BE con UNA PATCH al rilascio (prima: una PATCH + invalidazione per tick,
  // con risposte che potevano arrivare fuori ordine).
  const startRepeat = useCallback((delta: 1 | -1) => {
    stopRepeat() // defensive: clear any stale chain/listener from a previous press
    const startValue = valueRef.current
    const apply = () => {
      const next = Math.max(1, valueRef.current + delta)
      if (next !== valueRef.current) {
        valueRef.current = next
        setDraft(String(next))
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

    const release = () => {
      stopRepeat()
      if (valueRef.current !== startValue) onCommit(valueRef.current)
    }
    releaseRef.current = release
    window.addEventListener('pointerup', release, { once: true })
    window.addEventListener('pointercancel', release, { once: true })
  }, [onCommit, stopRepeat])

  // Fine pressione dai gestori del bottone: rilascia (e committa) la catena
  // attiva. No-op se il listener su window l'ha già chiusa.
  const finishRepeat = useCallback(() => {
    releaseRef.current?.()
  }, [])

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
      <span className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim flex-1">
        {label}
      </span>
      <Pressable
        onPointerDown={() => startRepeat(-1)}
        onPointerUp={finishRepeat}
        onPointerLeave={finishRepeat}
        onPointerCancel={finishRepeat}
        pending={pending}
        spinnerSize={12}
        className="w-11 h-11 rounded-lg bg-dnd-surface border border-dnd-border flex items-center justify-center text-dnd-gold"
        whileTap={{ scale: 0.9 }}
        aria-label={decrementAria}
      >
        <Minus size={16} />
      </Pressable>
      <input
        type="number"
        min={1}
        inputMode="numeric"
        value={draft}
        onFocus={() => { setEditing(true); setDraft('') }}
        placeholder={String(total)}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commitDraft}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault()
            ;(e.target as HTMLInputElement).blur()
          }
        }}
        className="w-14 h-11 text-center bg-dnd-surface border border-dnd-border rounded-lg
                   font-mono font-bold text-dnd-gold-bright tabular-nums
                   focus:border-dnd-gold/60 focus:outline-none"
      />
      <Pressable
        onPointerDown={() => startRepeat(1)}
        onPointerUp={finishRepeat}
        onPointerLeave={finishRepeat}
        onPointerCancel={finishRepeat}
        pending={pending}
        spinnerSize={12}
        className="w-11 h-11 rounded-lg bg-dnd-surface border border-dnd-border flex items-center justify-center text-dnd-gold"
        whileTap={{ scale: 0.9 }}
        aria-label={incrementAria}
      >
        <Plus size={16} />
      </Pressable>
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
  const [confirmRemoveSlot, setConfirmRemoveSlot] = useState<SpellSlot | null>(null)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  // Gemme ottimistiche: il tap aggiorna subito la cache (prima: PATCH + GET
  // completo del personaggio via tunnel prima di vedere la gemma cambiare).
  // `scope` serializza i tap rapidi, così le PATCH arrivano in ordine.
  const updateSlot = useMutation({
    mutationFn: ({ slotId, used }: { slotId: number; used: number }) =>
      api.spellSlots.update(charId, slotId, { used }),
    scope: { id: `spell-slots-${charId}` },
    onMutate: async ({ slotId, used }) => {
      await qc.cancelQueries({ queryKey: ['character', charId] })
      const prev = qc.getQueryData<CharacterFull>(['character', charId])
      if (prev) {
        qc.setQueryData<CharacterFull>(['character', charId], {
          ...prev,
          spell_slots: prev.spell_slots.map((s) =>
            s.id === slotId ? { ...s, used, available: s.total - used } : s,
          ),
        })
      }
      return { prev }
    },
    onError: (err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(['character', charId], ctx.prev)
      notifyMutationError(err)
    },
    onSettled: () => {
      // Riallinea col BE solo a coda vuota: niente refetch fra un tap e l'altro.
      // (isMutating conta anche questa mutation e quelle in coda nello scope.)
      if (qc.isMutating({ predicate: (m) => m.options.scope?.id === `spell-slots-${charId}` }) <= 1) {
        void qc.invalidateQueries({ queryKey: ['character', charId] })
      }
    },
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
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      setConfirmRemoveSlot(null)
    },
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
        <AutoModeBanner edition={char.rules_edition} onGoToSettings={() => navigate(`/char/${charId}/settings`)} />
      )}

      {slots.length > 0 && (
        <Button
          variant="secondary"
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
          hint={slotsMode === 'auto' ? t('character.slots.auto_hint', { edition: char.rules_edition }) : t('character.slots.manual_empty_hint')}
        />
      )}

      <Reveal.Stagger stagger={stagger.list} className="border-y border-dnd-border divide-y divide-dnd-border/60">
        {slots.map((slot) => (
          <Reveal.Item key={slot.id}>
            <div className="px-1 py-2.5">
              <div className="flex min-h-[28px] items-center justify-between mb-2.5">
                <div className="flex items-center gap-2">
                  <span className={LEDGER_LABEL}>
                    {t('character.slots.level', { level: slot.level })}
                  </span>
                  {slot.is_pact && (
                    <span className="px-1.5 py-0.5 rounded-lg border border-dnd-arcane/60 text-dnd-arcane-bright font-cinzel text-xs uppercase tracking-wider">
                      {t('character.slots.pact_badge')}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-base font-mono font-bold tabular-nums ${slot.available > 0 ? 'text-dnd-text' : 'text-dnd-text-faint'}`}>
                    {slot.available}/{slot.total}
                  </span>
                  {slotsMode !== 'auto' && (
                    <Pressable
                      onClick={() => setConfirmRemoveSlot(slot)}
                      className="w-11 h-11 rounded-lg text-dnd-crimson-bright flex items-center justify-center hover:bg-dnd-crimson/10"
                      whileTap={{ scale: 0.9 }}
                      aria-label={t('character.slots.remove_level_aria', { level: slot.level })}
                    >
                      <X size={16} />
                    </Pressable>
                  )}
                </div>
              </div>

              {/* Slot gems */}
              <div className="flex gap-2 flex-wrap">
                {Array.from({ length: slot.total }).map((_, i) => (
                  <Pressable
                    key={i}
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
                    className={gemClass(i < slot.used)}
                  />
                ))}
              </div>

              {/* Total editor — hidden in Auto mode (totals are class-derived). */}
              {slotsMode !== 'auto' && (
                <TotalEditor
                  slotId={slot.id}
                  total={slot.total}
                  label={t('character.slots.total')}
                  decrementAria={t('character.slots.decrement_total')}
                  incrementAria={t('character.slots.increment_total')}
                  pending={updateTotal.isPending && updateTotal.variables?.slotId === slot.id}
                  onCommit={(next) => updateTotal.mutate({ slotId: slot.id, total: next })}
                />
              )}
            </div>
          </Reveal.Item>
        ))}
      </Reveal.Stagger>

      {/* Manual creation of slot levels — hidden in Auto mode. */}
      {slotsMode !== 'auto' && missingLevels.length > 0 && (
        <section className="mt-3">
          <h2 className={`mb-2 pl-1 ${LEDGER_TITLE}`}>
            {t('character.slots.add_new_level')}
          </h2>
          <div className="grid grid-cols-2 xs:grid-cols-3 gap-2">
            {missingLevels.map((level) => (
              <Pressable
                key={level}
                pending={addSlot.isPending && addSlot.variables === level}
                spinnerSize={12}
                onClick={() => addSlot.mutate(level)}
                className="min-h-[44px] px-3 py-1.5 rounded-lg border border-dnd-border
                           text-dnd-text-muted font-cinzel text-xs uppercase tracking-wider
                           hover:border-dnd-gold-dim transition-colors"
                whileTap={{ scale: 0.92 }}
              >
                + {t('character.slots.level', { level })}
              </Pressable>
            ))}
          </div>
        </section>
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

      {/* Rimozione livello slot: distruttiva (perde totale e utilizzo), sempre confermata. */}
      <ConfirmSheet
        open={confirmRemoveSlot !== null}
        onClose={() => setConfirmRemoveSlot(null)}
        title={t('character.slots.remove_confirm_title')}
        body={confirmRemoveSlot
          ? t('character.slots.remove_confirm_body', { level: confirmRemoveSlot.level })
          : undefined}
        confirmLabel={t('common.delete')}
        loading={removeSlot.isPending}
        onConfirm={() => {
          if (confirmRemoveSlot) removeSlot.mutate(confirmRemoveSlot.id)
        }}
      />
    </Layout>
  )
}

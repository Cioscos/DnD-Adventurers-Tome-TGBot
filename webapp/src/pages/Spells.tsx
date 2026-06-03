import { useState, useCallback, useEffect, useRef } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { Ban, ChevronRight } from 'lucide-react'
import { GiPotionBall as FlaskConical, GiSparkles as Sparkles } from 'react-icons/gi'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import ScrollArea from '@/components/ScrollArea'
import EmptyState from '@/components/ui/EmptyState'
import { haptic } from '@/auth/telegram'
import { toast } from 'sonner'
import SpellFilter from '@/pages/spells/SpellFilter'
import SpellItem from '@/pages/spells/SpellItem'
import SpellForm, { type SpellFormData } from '@/pages/spells/SpellForm'
import CastSpellModal from '@/pages/spells/CastSpellModal'
import SpellDamageSheet from '@/pages/spells/SpellDamageSheet'
import type { Spell, SpellSlot } from '@/types'
import SpellsSkeleton from '@/components/skeletons/SpellsSkeleton'

export default function Spells() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()

  const [search, setSearch] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [editingSpell, setEditingSpell] = useState<Spell | null>(null)
  const [expanded, setExpanded] = useState<number | null>(null)
  const [castingSpell, setCastingSpell] = useState<Spell | null>(null)
  const [rollDamageSpell, setRollDamageSpell] = useState<Spell | null>(null)
  const [pendingSlotLevel, setPendingSlotLevel] = useState<number | null>(null)
  const [collapsedLevels, setCollapsedLevels] = useState<Set<number>>(new Set())
  const [concBannerExpanded, setConcBannerExpanded] = useState(false)
  const [searchParams, setSearchParams] = useSearchParams()
  const spellRefs = useRef<Map<number, HTMLDivElement | null>>(new Map())
  const focusHandled = useRef(false)

  const toggleLevel = (level: number) => {
    setCollapsedLevels((prev) => {
      const next = new Set(prev)
      if (next.has(level)) next.delete(level)
      else next.add(level)
      return next
    })
  }

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const addMutation = useMutation({
    mutationFn: (data: SpellFormData) =>
      api.spells.add(charId, {
        name: data.name.trim(),
        level: Number(data.level),
        description: data.description.trim() || undefined,
        casting_time: data.casting_time.trim() || undefined,
        range_area: data.range_area.trim() || undefined,
        components: data.components.trim() || undefined,
        duration: data.duration.trim() || undefined,
        is_concentration: data.is_concentration,
        is_ritual: data.is_ritual,
        damage_dice: data.damage_dice.trim() || undefined,
        damage_type: data.damage_type.trim() || undefined,
        is_pinned: false,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      setShowAdd(false)
      setEditingSpell(null)
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const updateMutation = useMutation({
    mutationFn: ({ spellId, data }: { spellId: number; data: SpellFormData }) =>
      api.spells.update(charId, spellId, {
        name: data.name.trim(),
        level: Number(data.level),
        description: data.description.trim() || undefined,
        casting_time: data.casting_time.trim() || undefined,
        range_area: data.range_area.trim() || undefined,
        components: data.components.trim() || undefined,
        duration: data.duration.trim() || undefined,
        is_concentration: data.is_concentration,
        is_ritual: data.is_ritual,
        damage_dice: data.damage_dice.trim() || undefined,
        damage_type: data.damage_type.trim() || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      setShowAdd(false)
      setEditingSpell(null)
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const removeMutation = useMutation({
    mutationFn: (spellId: number) => api.spells.remove(charId, spellId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['character', charId] }),
  })

  const concentrationMutation = useMutation({
    mutationFn: (spellId: number | null) => api.spells.updateConcentration(charId, spellId),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.success()
    },
  })

  const castMutation = useMutation({
    mutationFn: async ({ spell, slotLevel }: { spell: Spell; slotLevel: number }) => {
      const updated = await api.spells.use(charId, spell.id, slotLevel)
      if (spell.is_concentration) {
        const conc = await api.spells.updateConcentration(charId, spell.id)
        return { updated: conc, spell }
      }
      return { updated, spell }
    },
    onSuccess: ({ updated }) => {
      qc.setQueryData(['character', charId], updated)
      setCastingSpell(null)
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const useSlotMutation = useMutation({
    mutationFn: ({ slotId, newUsed }: { slotId: number; newUsed: number }) =>
      api.spellSlots.update(charId, slotId, { used: newUsed }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      haptic.success()
    },
  })

  // "Create slot" from the cast modal when no slot is available. In Auto mode the
  // page offers no slot controls, so we switch the character to Manual first (with a
  // notice) and then materialise the slot — turning the old dead-end into a working
  // flow. The cast modal stays open so the freshly-created slot becomes selectable.
  const createSlotMutation = useMutation({
    mutationFn: async (level: number) => {
      const mode = ((char?.settings as Record<string, unknown> | undefined)?.spell_slots_mode as string | undefined) ?? 'auto'
      if (mode === 'auto') {
        await api.characters.update(charId, {
          settings: { ...(char?.settings ?? {}), spell_slots_mode: 'manual' },
        })
      }
      const existing = (char?.spell_slots ?? []).find((s) => s.level === level)
      if (existing) {
        return api.spellSlots.update(charId, existing.id, { total: existing.total + 1 })
      }
      return api.spellSlots.add(charId, level, 1)
    },
    onSuccess: () => {
      const mode = ((char?.settings as Record<string, unknown> | undefined)?.spell_slots_mode as string | undefined) ?? 'auto'
      qc.invalidateQueries({ queryKey: ['character', charId] })
      if (mode === 'auto') toast.info(t('character.spells.create_slot_switches_manual'))
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const handleUseSpell = useCallback((spell: Spell) => {
    if (spell.level === 0) {
      // Cantrip — no slot consumed; defer concentration toggle to the damage sheet when present.
      if (spell.damage_dice) {
        setPendingSlotLevel(0)
        setRollDamageSpell(spell)
        return
      }
      if (spell.is_concentration) {
        concentrationMutation.mutate(spell.id)
      } else {
        haptic.success()
      }
      return
    }
    // Leveled spell — pick a slot first.
    setCastingSpell(spell)
  }, [concentrationMutation])

  const handleFormSubmit = useCallback((data: SpellFormData) => {
    if (editingSpell) {
      updateMutation.mutate({ spellId: editingSpell.id, data })
    } else {
      addMutation.mutate(data)
    }
  }, [editingSpell, updateMutation, addMutation])

  const handleFormCancel = useCallback(() => {
    setShowAdd(false)
    setEditingSpell(null)
  }, [])

  const handleEditSpell = useCallback((spell: Spell) => {
    setEditingSpell(spell)
    setShowAdd(true)
  }, [])

  const handleCastSlot = useCallback((slotLevel: number) => {
    if (!castingSpell) return
    if (castingSpell.damage_dice) {
      // Defer slot consumption to the damage sheet's Roll button.
      setPendingSlotLevel(slotLevel)
      setRollDamageSpell(castingSpell)
      setCastingSpell(null)
      return
    }
    // No damage to roll — consume slot immediately.
    castMutation.mutate({ spell: castingSpell, slotLevel })
  }, [castingSpell, castMutation])

  const focusParam = searchParams.get('focus')
  const focusId = focusParam ? Number(focusParam) : null

  useEffect(() => {
    if (!char || focusId === null || focusHandled.current) return
    const spell = (char.spells ?? []).find((s) => s.id === focusId)
    if (!spell) return
    focusHandled.current = true
    setExpanded(focusId)
    setCollapsedLevels((prev) => {
      if (!prev.has(spell.level)) return prev
      const next = new Set(prev)
      next.delete(spell.level)
      return next
    })
    requestAnimationFrame(() => {
      const el = spellRefs.current.get(focusId)
      el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      const params = new URLSearchParams(searchParams)
      params.delete('focus')
      setSearchParams(params, { replace: true })
    })
  }, [char, focusId, searchParams, setSearchParams])

  if (!char) {
    return (
      <Layout title={t('character.spells.title')} backTo={`/char/${charId}`} group="magic" page="spells">
        <SpellsSkeleton />
      </Layout>
    )
  }

  const spells: Spell[] = char.spells ?? []
  const spellSlots: SpellSlot[] = char.spell_slots ?? []
  const filtered = search
    ? spells.filter((s) => s.name.toLowerCase().includes(search.toLowerCase()))
    : spells

  const byLevel = filtered.reduce<Record<number, Spell[]>>((acc, s) => {
    if (!acc[s.level]) acc[s.level] = []
    acc[s.level].push(s)
    return acc
  }, {})

  const sortedLevels = Object.keys(byLevel).map(Number).sort((a, b) => a - b)
  const concentratingId = char.concentrating_spell_id
  const concentratingSpell = concentratingId ? spells.find(s => s.id === concentratingId) : null

  const availableSlotsFor = (spellLevel: number) =>
    spellSlots
      .filter((s) => s.level >= spellLevel && s.available > 0)
      .sort((a, b) => a.level - b.level)

  return (
    <Layout title={t('character.spells.title')} backTo={`/char/${charId}`} group="magic" page="spells">
      <SpellFilter
        search={search}
        onSearchChange={setSearch}
        onAddClick={() => setShowAdd(true)}
      />

      {/* Concentration panel — active spell + description. TS auto on /hp DAMAGE. */}
      {concentratingId && concentratingSpell && (
        <ConcentrationPanel
          name={concentratingSpell.name}
          description={concentratingSpell.description}
          concBannerExpanded={concBannerExpanded}
          setConcBannerExpanded={setConcBannerExpanded}
          onStop={() => concentrationMutation.mutate(null)}
          labels={{
            concentration: t('character.spells.concentration'),
            stop: t('character.spells.stop_concentration'),
            expand: t('character.spells.expand'),
            collapse: t('character.spells.collapse'),
          }}
        />
      )}

      {spells.length === 0 && !showAdd && (
        <EmptyState
          icon={<Sparkles size={32} />}
          title={t('common.none')}
          hint={t('character.spells.empty_hint')}
          action={{
            label: t('character.spells.add'),
            onClick: () => setShowAdd(true),
          }}
        />
      )}

      <ScrollArea>
        {sortedLevels.map((level) => {
          const slot = level > 0 ? spellSlots.find((s) => s.level === level) : undefined
          return (
            <div key={level} className="mb-4">
              <div className="sticky top-0 z-[5] -mx-4 w-[calc(100%+2rem)] px-5 py-2 flex items-center gap-2 bg-dnd-bg/95 backdrop-blur-sm border-b border-dnd-border/40">
                <m.button
                  type="button"
                  onClick={() => toggleLevel(level)}
                  className="flex items-center gap-2 flex-1 min-w-0 text-left"
                  aria-expanded={!collapsedLevels.has(level)}
                >
                  <ChevronRight
                    size={14}
                    className={`text-dnd-gold-bright transition-transform ${!collapsedLevels.has(level) ? 'rotate-90' : ''}`}
                  />
                  <span className="font-cinzel uppercase tracking-widest text-xs text-dnd-gold-bright truncate">
                    {level === 0 ? t('character.spells.cantrip_label') : t('character.spells.level_label', { level })}
                  </span>
                </m.button>
                {slot && slot.total > 0 && (
                  <div className="flex gap-1 items-center shrink-0">
                    {Array.from({ length: slot.total }).map((_, i) => (
                      <m.button
                        key={i}
                        type="button"
                        disabled={useSlotMutation.isPending}
                        onClick={() => {
                          if (i < slot.used) {
                            haptic.light()
                            useSlotMutation.mutate({ slotId: slot.id, newUsed: Math.max(0, slot.used - 1) })
                          } else {
                            haptic.medium()
                            useSlotMutation.mutate({ slotId: slot.id, newUsed: Math.min(slot.total, slot.used + 1) })
                          }
                        }}
                        className={`hit-44 w-7 h-7 rounded-full border-2 transition-all disabled:opacity-40 ${
                          i < slot.used
                            ? 'bg-gradient-to-br from-dnd-gold-deep to-dnd-gold-bright border-dnd-gold-bright shadow-[0_0_8px_rgba(244,208,111,0.5)]'
                            : 'bg-transparent border-dnd-gold-dim/60 hover:border-dnd-gold-bright'
                        }`}
                        whileTap={{ scale: 0.85 }}
                        aria-label={t('character.slots.gem_aria', {
                          level: slot.level,
                          index: i + 1,
                          total: slot.total,
                          state: i < slot.used
                            ? t('character.slots.state_used')
                            : t('character.slots.state_available'),
                        })}
                        aria-pressed={i < slot.used}
                      />
                    ))}
                  </div>
                )}
              </div>
              <AnimatePresence>
                {!collapsedLevels.has(level) && (
                  <m.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="space-y-1.5 mt-2">
                      {byLevel[level].map((spell) => (
                        <div
                          key={spell.id}
                          ref={(el) => {
                            if (el) spellRefs.current.set(spell.id, el)
                            else spellRefs.current.delete(spell.id)
                          }}
                        >
                          <SpellItem
                            spell={spell}
                            isExpanded={expanded === spell.id}
                            onToggle={() => setExpanded(expanded === spell.id ? null : spell.id)}
                            onUse={() => handleUseSpell(spell)}
                            onConcentrationToggle={() =>
                              concentrationMutation.mutate(concentratingId === spell.id ? null : spell.id)
                            }
                            onEdit={() => handleEditSpell(spell)}
                            onRemove={() => removeMutation.mutate(spell.id)}
                            concentratingSpellId={concentratingId ?? null}
                            usePending={castMutation.isPending || concentrationMutation.isPending}
                          />
                        </div>
                      ))}
                    </div>
                  </m.div>
                )}
              </AnimatePresence>
            </div>
          )
        })}
      </ScrollArea>

      {castingSpell && (
        <CastSpellModal
          spell={castingSpell}
          availableSlots={availableSlotsFor(castingSpell.level)}
          onCast={handleCastSlot}
          onCreateSlot={(level) => createSlotMutation.mutate(level)}
          onCancel={() => setCastingSpell(null)}
          isPending={castMutation.isPending}
          isCreatingSlot={createSlotMutation.isPending}
        />
      )}

      {showAdd && (
        <SpellForm
          initialData={editingSpell}
          onSubmit={handleFormSubmit}
          onCancel={handleFormCancel}
          isPending={addMutation.isPending || updateMutation.isPending}
        />
      )}

      <SpellDamageSheet
        charId={charId}
        spell={rollDamageSpell}
        slotLevel={pendingSlotLevel}
        onClose={() => {
          setRollDamageSpell(null)
          setPendingSlotLevel(null)
        }}
      />

    </Layout>
  )
}

interface ConcentrationPanelProps {
  name: string
  description: string | null | undefined
  concBannerExpanded: boolean
  setConcBannerExpanded: (updater: (v: boolean) => boolean) => void
  onStop: () => void
  labels: {
    concentration: string
    stop: string
    expand: string
    collapse: string
  }
}

function ConcentrationPanel({
  name,
  description,
  concBannerExpanded,
  setConcBannerExpanded,
  onStop,
  labels,
}: ConcentrationPanelProps) {
  return (
    <m.div
      className="relative rounded-2xl"
      animate={{
        boxShadow: [
          '0 0 0 2px rgba(155, 89, 182, 0.20), 0 0 14px rgba(155, 89, 182, 0.18)',
          '0 0 0 2px rgba(155, 89, 182, 0.42), 0 0 28px rgba(155, 89, 182, 0.42)',
          '0 0 0 2px rgba(155, 89, 182, 0.20), 0 0 14px rgba(155, 89, 182, 0.18)',
        ],
      }}
      transition={{
        duration: 2.8,
        repeat: Infinity,
        ease: 'easeInOut',
      }}
    >
      <Surface variant="arcane" ornamented className="space-y-3 @container shadow-none">
        <div className="flex flex-col gap-3 @[22rem]:flex-row @[22rem]:items-center @[22rem]:justify-between">
          <div className="flex items-center gap-2 min-w-0">
            <FlaskConical size={16} className="text-dnd-arcane-bright shrink-0" />
            <div className="min-w-0 flex-1">
              <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-arcane-bright">
                {labels.concentration}
              </p>
              <p className="text-base font-display font-bold text-dnd-gold-bright truncate">
                {name}
              </p>
            </div>
          </div>
          <Button
            variant="danger"
            size="sm"
            onClick={onStop}
            icon={<Ban size={12} />}
            haptic="warning"
            className="shrink-0 whitespace-nowrap self-end @[22rem]:self-auto"
          >
            {labels.stop}
          </Button>
        </div>
        {description && (
          <div>
            <p className={`text-sm text-dnd-text font-body leading-relaxed break-words ${concBannerExpanded ? '' : 'line-clamp-2'}`}>
              {description}
            </p>
            {description.length > 120 && (
              <button
                type="button"
                onClick={() => setConcBannerExpanded((v) => !v)}
                className="mt-1 text-[11px] font-cinzel uppercase tracking-widest text-dnd-arcane-bright hover:text-dnd-gold-bright"
              >
                {concBannerExpanded ? labels.collapse : labels.expand}
              </button>
            )}
          </div>
        )}
      </Surface>
    </m.div>
  )
}

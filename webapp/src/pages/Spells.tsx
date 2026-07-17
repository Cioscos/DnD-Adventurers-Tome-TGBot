import { useState, useCallback, useEffect, useRef } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { Ban, ChevronRight, FilterX } from 'lucide-react'
import { GiPotionBall as FlaskConical, GiSparkles as Sparkles } from 'react-icons/gi'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import ScrollArea from '@/components/ScrollArea'
import EmptyState from '@/components/ui/EmptyState'
import FilterChip from '@/components/ui/FilterChip'
import FilterRow from '@/components/ui/FilterRow'
import { haptic } from '@/auth/telegram'
import { toast } from 'sonner'
import SpellFilter from '@/pages/spells/SpellFilter'
import SpellItem from '@/pages/spells/SpellItem'
import SpellForm, { type SpellFormData } from '@/pages/spells/SpellForm'
import { useCastFlow } from '@/pages/spells/useCastFlow'
import type { Spell, SpellSlot } from '@/types'
import SpellsSkeleton from '@/components/skeletons/SpellsSkeleton'

type SpellProp = 'concentration' | 'ritual' | 'prepared'

export default function Spells() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()

  const [search, setSearch] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [editingSpell, setEditingSpell] = useState<Spell | null>(null)
  const [expanded, setExpanded] = useState<number | null>(null)
  const [confirmForget, setConfirmForget] = useState<Spell | null>(null)
  const [collapsedLevels, setCollapsedLevels] = useState<Set<number>>(new Set())
  const [concBannerExpanded, setConcBannerExpanded] = useState(false)
  const [searchParams, setSearchParams] = useSearchParams()
  const spellRefs = useRef<Map<number, HTMLDivElement | null>>(new Map())
  const focusHandled = useRef(false)

  // Filtri a chips (come nelle Abilità speciali): multi-selezione, unione fra
  // chip della stessa dimensione, intersezione fra dimensioni diverse.
  const [levelFilter, setLevelFilter] = useState<Set<number>>(() => new Set())
  const [propFilter, setPropFilter] = useState<Set<SpellProp>>(() => new Set())

  const toggleLevel = (level: number) => {
    setCollapsedLevels((prev) => {
      const next = new Set(prev)
      if (next.has(level)) next.delete(level)
      else next.add(level)
      return next
    })
  }
  const toggleLevelFilter = (level: number) =>
    setLevelFilter((prev) => {
      const next = new Set(prev)
      if (next.has(level)) next.delete(level)
      else next.add(level)
      return next
    })
  const toggleProp = (key: SpellProp) =>
    setPropFilter((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  const clearSpellFilters = () => {
    setLevelFilter(new Set())
    setPropFilter(new Set())
  }

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const castFlow = useCastFlow(charId, char)

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
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      setConfirmForget(null)
    },
  })

  const concentrationMutation = useMutation({
    mutationFn: (spellId: number | null) => api.spells.updateConcentration(charId, spellId),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.success()
    },
  })

  const spellcasting = char?.spellcasting ?? null

  const preparedMutation = useMutation({
    mutationFn: ({ spellId, prepared }: { spellId: number; prepared: boolean }) =>
      api.spells.update(charId, spellId, { is_prepared: prepared }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      haptic.light()
    },
    onError: (e) => {
      haptic.error()
      toast.error(e instanceof Error ? e.message : String(e))
    },
  })

  const handlePreparedToggle = useCallback((spell: Spell) => {
    const sc = spellcasting
    if (!spell.is_prepared && sc?.has_preparing_class
        && sc.prepared_count >= (sc.prepared_cap ?? 0)) {
      haptic.warning()
      toast.warning(t('character.spells.prepared_cap_reached', {
        n: sc.prepared_count, cap: sc.prepared_cap ?? 0,
      }))
      return
    }
    preparedMutation.mutate({ spellId: spell.id, prepared: !spell.is_prepared })
  }, [spellcasting, preparedMutation, t])

  const useSlotMutation = useMutation({
    mutationFn: ({ slotId, newUsed }: { slotId: number; newUsed: number }) =>
      api.spellSlots.update(charId, slotId, { used: newUsed }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      haptic.success()
    },
  })

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
    // Lo scroll va riprovato: al primo frame la riga può non essere ancora
    // montata (livello appena de-collassato) e l'animazione di espansione
    // della card (~350ms) sposta il layout dopo il primo scrollIntoView.
    const scrollToSpell = (behavior: ScrollBehavior) =>
      spellRefs.current.get(focusId)?.scrollIntoView({ behavior, block: 'center' })
    let attempts = 0
    const tryScroll = () => {
      const el = spellRefs.current.get(focusId)
      if (el) {
        scrollToSpell('smooth')
      } else if (attempts++ < 10) {
        requestAnimationFrame(tryScroll)
      }
    }
    requestAnimationFrame(tryScroll)
    // Secondo passaggio a layout assestato (fine animazione di espansione).
    // Niente cleanup: il setSearchParams qui sotto rilancia subito l'effetto
    // e una cleanup cancellerebbe il timer prima che scatti.
    setTimeout(() => scrollToSpell('smooth'), 450)
    const params = new URLSearchParams(searchParams)
    params.delete('focus')
    setSearchParams(params, { replace: true })
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

  // Opzioni di filtro derivate dall'intero set di incantesimi (indipendenti dalla
  // ricerca, così le chip restano stabili). Una dimensione si mostra solo se utile.
  const levelOptions = Array.from(
    spells.reduce((acc, s) => acc.set(s.level, (acc.get(s.level) ?? 0) + 1), new Map<number, number>()),
  )
    .map(([level, count]) => ({ level, count }))
    .sort((a, b) => a.level - b.level)

  const propKeys: SpellProp[] = ['concentration', 'ritual']
  if (spellcasting?.has_preparing_class) propKeys.push('prepared')
  const propOptions = propKeys
    .map((key) => ({
      key,
      count: spells.filter((s) =>
        key === 'concentration' ? s.is_concentration
        : key === 'ritual' ? s.is_ritual
        : s.is_prepared && s.level >= 1,
      ).length,
    }))
    // una proprietà si mostra solo se discrimina davvero (presente ma non in tutti)
    .filter((o) => o.count > 0 && o.count < spells.length)

  const showLevelRow = levelOptions.length >= 2
  const showPropRow = propOptions.length >= 1
  const showFilterBar = showLevelRow || showPropRow
  const hasActiveChipFilter = levelFilter.size > 0 || propFilter.size > 0

  const matchesChips = (s: Spell): boolean => {
    if (levelFilter.size > 0 && !levelFilter.has(s.level)) return false
    if (propFilter.size > 0) {
      const matchesProp =
        (propFilter.has('concentration') && s.is_concentration) ||
        (propFilter.has('ritual') && s.is_ritual) ||
        (propFilter.has('prepared') && s.is_prepared && s.level >= 1)
      if (!matchesProp) return false
    }
    return true
  }

  const filtered = spells
    .filter((s) => (search ? s.name.toLowerCase().includes(search.toLowerCase()) : true))
    .filter(matchesChips)

  const byLevel = filtered.reduce<Record<number, Spell[]>>((acc, s) => {
    if (!acc[s.level]) acc[s.level] = []
    acc[s.level].push(s)
    return acc
  }, {})

  const sortedLevels = Object.keys(byLevel).map(Number).sort((a, b) => a - b)
  const noResults = spells.length > 0 && filtered.length === 0
  const concentratingId = char.concentrating_spell_id
  const concentratingSpell = concentratingId ? spells.find(s => s.id === concentratingId) : null

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
          stopPending={concentrationMutation.isPending && concentrationMutation.variables === null}
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

      {/* Contatore di preparazione: etichetta in Cinzel, numeri mono tabulari
          (Tabular Numerics). Rosso solo oltre il tetto (legacy grandfathered). */}
      {spellcasting?.has_preparing_class && spells.length > 0 && (
        <div className="flex items-center justify-end gap-1.5 px-1">
          <span className="font-cinzel text-[11px] uppercase tracking-widest text-dnd-gold-dim">
            {t('character.spells.prepared_counter')}
          </span>
          <span className={`font-mono text-xs tabular-nums ${
            spellcasting.prepared_count > (spellcasting.prepared_cap ?? 0)
              ? 'text-dnd-crimson-bright'
              : 'text-dnd-text'
          }`}>
            {spellcasting.prepared_count}/{spellcasting.prepared_cap ?? 0}
          </span>
        </div>
      )}

      {showFilterBar && (
        <div className="space-y-2">
          {showLevelRow && (
            <FilterRow label={t('character.spells.filters.level')}>
              {levelOptions.map((o) => (
                <FilterChip
                  key={o.level}
                  tone="gold"
                  label={o.level === 0 ? t('character.spells.cantrip') : t('character.spells.filters.level_n', { level: o.level })}
                  count={o.count}
                  selected={levelFilter.has(o.level)}
                  onToggle={() => toggleLevelFilter(o.level)}
                />
              ))}
            </FilterRow>
          )}
          {showPropRow && (
            <FilterRow label={t('character.spells.filters.property')}>
              {propOptions.map((o) => (
                <FilterChip
                  key={o.key}
                  tone={o.key === 'prepared' ? 'gold' : 'arcane'}
                  label={t(`character.spells.${o.key}`)}
                  count={o.count}
                  selected={propFilter.has(o.key)}
                  onToggle={() => toggleProp(o.key)}
                />
              ))}
            </FilterRow>
          )}
          {hasActiveChipFilter && (
            <div className="flex justify-end">
              <Button
                variant="ghost"
                size="sm"
                icon={<FilterX size={12} />}
                haptic="light"
                onClick={clearSpellFilters}
              >
                {t('character.spells.filters.clear')}
              </Button>
            </div>
          )}
        </div>
      )}

      <ScrollArea>
        {noResults && (
          <EmptyState
            icon={<Sparkles size={32} />}
            title={t('character.spells.filters.no_results')}
            action={
              hasActiveChipFilter
                ? { label: t('character.spells.filters.clear'), onClick: clearSpellFilters, icon: <FilterX size={14} /> }
                : undefined
            }
          />
        )}
        {sortedLevels.map((level) => {
          const slot = level > 0 ? spellSlots.find((s) => s.level === level) : undefined
          return (
            <div key={level} className="mb-4">
              {/* -top-4 compensa il p-4 del contenitore di scroll del Layout
                  (stesso pattern di Inventory): con top-0 l'header si fermava
                  16px sotto il bordo visivo della pagina. */}
              <div className="sticky -top-4 z-[5] -mx-4 w-[calc(100%+2rem)] px-5 py-2 flex items-center gap-2 bg-dnd-bg/95 backdrop-blur-sm border-b border-dnd-border/40">
                <Pressable
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
                </Pressable>
                {slot && slot.total > 0 && (
                  <div className="flex gap-1 items-center shrink-0">
                    {Array.from({ length: slot.total }).map((_, i) => (
                      <Pressable
                        key={i}
                        pending={useSlotMutation.isPending && useSlotMutation.variables?.slotId === slot.id}
                        spinnerSize={12}
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
                            onUse={() => castFlow.beginCast(spell)}
                            onConcentrationToggle={() =>
                              concentrationMutation.mutate(concentratingId === spell.id ? null : spell.id)
                            }
                            onEdit={() => handleEditSpell(spell)}
                            onRemove={() => setConfirmForget(spell)}
                            concentratingSpellId={concentratingId ?? null}
                            usePending={castFlow.isSpellPending(spell.id)}
                            showPreparedToggle={!!spellcasting?.has_preparing_class && spell.level >= 1}
                            onPreparedToggle={() => handlePreparedToggle(spell)}
                            preparedPending={preparedMutation.isPending && preparedMutation.variables?.spellId === spell.id}
                            concentrationPending={
                              concentrationMutation.isPending &&
                              (concentrationMutation.variables === spell.id ||
                                (concentrationMutation.variables === null && concentratingId === spell.id))
                            }
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

      {/* Dimentica: eliminazione definitiva, sempre confermata (audit #9). */}
      <ConfirmSheet
        open={confirmForget !== null}
        onClose={() => setConfirmForget(null)}
        title={t('character.spells.forget_confirm_title')}
        body={confirmForget
          ? t('character.spells.forget_confirm_body', { name: confirmForget.name })
          : undefined}
        confirmLabel={t('character.spells.forget')}
        loading={removeMutation.isPending}
        onConfirm={() => {
          if (confirmForget) removeMutation.mutate(confirmForget.id)
        }}
      />

      {showAdd && (
        <SpellForm
          initialData={editingSpell}
          onSubmit={handleFormSubmit}
          onCancel={handleFormCancel}
          isPending={addMutation.isPending || updateMutation.isPending}
        />
      )}

      {castFlow.elements}

    </Layout>
  )
}

interface ConcentrationPanelProps {
  name: string
  description: string | null | undefined
  concBannerExpanded: boolean
  setConcBannerExpanded: (updater: (v: boolean) => boolean) => void
  onStop: () => void
  stopPending: boolean
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
  stopPending,
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
            loading={stopPending}
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
              <Pressable
                onClick={() => setConcBannerExpanded((v) => !v)}
                className="mt-1 text-[11px] font-cinzel uppercase tracking-widest text-dnd-arcane-bright hover:text-dnd-gold-bright"
              >
                {concBannerExpanded ? labels.collapse : labels.expand}
              </Pressable>
            )}
          </div>
        )}
      </Surface>
    </m.div>
  )
}

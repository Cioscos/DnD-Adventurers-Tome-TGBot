import CasterStats from '@/pages/spells/CasterStats'
import SpellLimits from '@/pages/spells/SpellLimits'
import { useState, useCallback, useEffect, useRef } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { Ban, ChevronRight, FilterX } from 'lucide-react'
import { GiPotionBall as FlaskConical, GiSparkles as Sparkles } from 'react-icons/gi'
import { api, ApiError } from '@/api/client'
import { notifyMutationError, apiErrorCode } from '@/lib/mutationError'
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
import OwnedSecrets from '@/pages/spells/OwnedSecrets'
import SpellFilter from '@/pages/spells/SpellFilter'
import SpellItem from '@/pages/spells/SpellItem'
import SpellbookSheet from '@/pages/spells/SpellbookSheet'
import SpellForm, { type SpellFormData } from '@/pages/spells/SpellForm'
import { totalLevelOf } from '@/lib/dnd'
import { itemSpellConcentration } from '@/lib/concentration'
import { useCastFlow } from '@/pages/spells/useCastFlow'
import type { Spell, SpellSlot } from '@/types'
import SpellsSkeleton from '@/components/skeletons/SpellsSkeleton'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import { LEDGER_TITLE, gemClass } from '@/styles/ledger'

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
  const [schoolFilter, setSchoolFilter] = useState<Set<string>>(() => new Set())

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
  const toggleSchool = (key: string) =>
    setSchoolFilter((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  const clearSpellFilters = () => {
    setSchoolFilter(new Set())
    setLevelFilter(new Set())
    setPropFilter(new Set())
  }

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const castFlow = useCastFlow(charId, char)
  const [bookSpell, setBookSpell] = useState<Spell | null>(null)  // Libro del Mago: l'incantesimo da copiare
  const [confirmLost, setConfirmLost] = useState(false)
  const loseBook = useMutation({
    mutationFn: () => api.spells.loseSpellbook(charId),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setConfirmLost(false)
      toast.info(t('character.spells.book.lost_done'))
    },
  })

  const onPrepareError = (e: unknown) => {
    const detail = e instanceof ApiError ? e.detail as { code?: string; n?: number; cap?: number; per_class?: boolean } : null
    if (detail?.code === 'not_in_spellbook' || detail?.code === 'spell_above_slots') {
      haptic.warning()
      toast.warning(t(`character.spells.${detail.code}`))
      return
    }
    if (detail?.code !== 'prepared_cap') {
      notifyMutationError(e)
      return
    }
    haptic.warning()
    toast.warning(t(`character.spells.${detail.per_class ? 'prepared_cap_class_reached' : 'prepared_cap_reached'}`, {
      n: detail.n, cap: detail.cap,
    }))
  }

  // Segreti Magici: la scelta in sospeso a cui l'incantesimo che si sta aggiungendo risponde (`?pick=<id>` dalla scheda).
  const pickId = searchParams.get('pick')
  const pick = char?.pending_choices?.find((c) => c.id === pickId && c.spell_pick) ?? null

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
        attack_save: data.attack_save || undefined,
        higher_level: data.higher_level.trim() || undefined,
        school: data.school || undefined,
        srd_index: data.srd_index || undefined,
        higher_levels_dice: data.higher_levels_dice || undefined,
        is_pinned: false,
        // Una scelta di incantesimi va sempre alla classe che la dà: la sceglie il server.
        class_id: pick ? null : data.class_id ? Number(data.class_id) : null,
        always_prepared: data.always_prepared,
        ...(pick ? { pick_id: pick.id } : {}),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      setShowAdd(false)
      setEditingSpell(null)
      haptic.success()
    },
    onError: (e) => {
      const code = apiErrorCode(e)
      if (code === 'spell_pick_level' || code === 'spell_already_known') {
        haptic.warning()
        toast.warning(t(`character.spells.${code}`))
        return
      }
      onPrepareError(e)
    },
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
        // null (not undefined) so editing back to "Nessuno" actually clears it.
        attack_save: data.attack_save || null,
        higher_level: data.higher_level.trim() || undefined,
        school: data.school || undefined,
        srd_index: data.srd_index || undefined,
        higher_levels_dice: data.higher_levels_dice || null,
        class_id: data.class_id ? Number(data.class_id) : null,
        always_prepared: data.always_prepared,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      setShowAdd(false)
      setEditingSpell(null)
      haptic.success()
    },
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
    onError: onPrepareError,
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

  const schoolOptions = Array.from(
    spells.reduce((acc, s) => (s.school ? acc.set(s.school, (acc.get(s.school) ?? 0) + 1) : acc), new Map<string, number>()),
  )
    .map(([key, count]) => ({ key, count }))
    .sort((a, b) => a.key.localeCompare(b.key))

  const showSchoolRow = schoolOptions.length >= 2
  const showLevelRow = levelOptions.length >= 2
  const showPropRow = propOptions.length >= 1
  const showFilterBar = showLevelRow || showPropRow || showSchoolRow
  const hasActiveChipFilter = levelFilter.size > 0 || propFilter.size > 0 || schoolFilter.size > 0

  const matchesChips = (s: Spell): boolean => {
    if (levelFilter.size > 0 && !levelFilter.has(s.level)) return false
    if (schoolFilter.size > 0 && !(s.school && schoolFilter.has(s.school))) return false
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
  const itemConcentration = concentratingSpell ? null : itemSpellConcentration(char)

  return (
    <Layout title={t('character.spells.title')} backTo={`/char/${charId}`} group="magic" page="spells">
      <CasterStats casters={spellcasting?.casters ?? []} />
      <SpellLimits limits={spellcasting?.limits ?? []} />

      {pick?.spell_pick && (
        <Surface variant="arcane">
          <div data-testid="spell-pick-banner" className="space-y-1">
            <p className="font-body text-sm text-dnd-text">
              {pick.spell_pick.book
                ? t('character.spells.pick_book_banner', { count: pick.count ?? 0, max: pick.spell_pick.max_level })
                : pick.spell_pick.ritual
                ? t('character.spells.pick_ritual_banner', { count: pick.count ?? 0, level: pick.spell_pick.max_level })
                : pick.spell_pick.exact
                  ? t('character.spells.pick_exact_banner', { count: pick.count ?? 0, level: pick.spell_pick.max_level })
                  : pick.spell_pick.max_level === 0
                    ? t(pick.spell_pick.list ? 'character.spells.pick_cantrip_banner' : 'character.spells.pick_cantrip_any_banner', { count: pick.count ?? 0, list: t(`dnd.classes.${pick.spell_pick.list}`) })
                    : t('character.spells.pick_banner', { count: pick.count ?? 0, max: pick.spell_pick.max_level })}
            </p>
            {pick.spell_pick.free && (
              <p className="font-body text-xs text-dnd-text-muted">{t('character.spells.pick_free')}</p>
            )}
          </div>
          {pick.retrofit && (pick.spell_pick.owned?.length ?? 0) > 0 && (
            <OwnedSecrets charId={charId} pick={pick} />
          )}
        </Surface>
      )}

      <SpellFilter
        search={search}
        onSearchChange={setSearch}
        onAddClick={() => setShowAdd(true)}
      />

      {/* Concentration panel — active spell + description. TS auto on /hp DAMAGE. */}
      {(concentratingSpell || itemConcentration) && (
        <ConcentrationPanel
          name={concentratingSpell?.name ?? itemConcentration?.name ?? ''}
          description={concentratingSpell?.description}
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
      {spellcasting?.has_preparing_class && spells.length > 0
        && (spellcasting.limits?.length !== 1 || spellcasting.cap_mode === 'manual') && (
        <div className="flex items-center justify-end gap-1.5 px-1">
          <span className="font-cinzel text-xs uppercase tracking-widest text-dnd-gold-dim">
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

      {spellcasting?.has_wizard && spells.some((s) => s.has_book) && (
        <div className="flex justify-end px-1">
          <Button variant="secondary" size="sm" className="min-h-11" onClick={() => setConfirmLost(true)}>
            {t('character.spells.book.lost_button')}
          </Button>
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
          {showSchoolRow && (
            <FilterRow label={t('character.spells.filters.school')}>
              {schoolOptions.map((o) => (
                <FilterChip
                  key={o.key}
                  tone="arcane"
                  label={t(`character.spells.schools.${o.key}`, { defaultValue: o.key })}
                  count={o.count}
                  selected={schoolFilter.has(o.key)}
                  onToggle={() => toggleSchool(o.key)}
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
          const slots = level > 0 ? spellSlots.filter((s) => s.level === level && s.total > 0) : []
          return (
            <div key={level} className="mb-4">
              {/* -top-4 compensa il p-4 del contenitore di scroll del Layout
                  (stesso pattern di Inventory): con top-0 l'header si fermava
                  16px sotto il bordo visivo della pagina. */}
              <div className="sticky top-[calc(var(--crumb-offset,0px)-1rem)] z-[5] -mx-4 w-[calc(100%+2rem)] px-5 py-0.5 flex items-center gap-2 bg-dnd-bg border-b border-dnd-border">
                <Pressable
                  onClick={() => toggleLevel(level)}
                  className="flex items-center gap-2 flex-1 min-w-0 min-h-[44px] text-left"
                  aria-expanded={!collapsedLevels.has(level)}
                >
                  <ChevronRight
                    size={14}
                    className={`text-dnd-gold-bright transition-transform ${!collapsedLevels.has(level) ? 'rotate-90' : ''}`}
                  />
                  <span className={`truncate ${LEDGER_TITLE}`}>
                    {level === 0 ? t('character.spells.cantrip_label') : t('character.spells.level_label', { level })}
                  </span>
                </Pressable>
                {slots.map((slot) => (
                  <div key={slot.id} className="flex gap-1 items-center shrink-0">
                    {slot.is_pact && slots.length > 1 && (
                      <span className="font-cinzel text-xs uppercase tracking-widest text-dnd-gold-dim">{t('character.slots.pact_badge')}</span>
                    )}
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
                        className={`${gemClass(i < slot.used)} disabled:opacity-40`}
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
                ))}
              </div>
              <AnimatePresence>
                {!collapsedLevels.has(level) && (
                  <m.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="overflow-hidden"
                  >
                    <div>
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
                            onUse={(mode) => castFlow.beginCast(spell, mode)}
                            totalLevel={totalLevelOf(char?.classes)}
                            onConcentrationToggle={() =>
                              concentrationMutation.mutate(concentratingId === spell.id ? null : spell.id)
                            }
                            onEdit={() => handleEditSpell(spell)}
                            onRemove={() => setConfirmForget(spell)}
                            concentratingSpellId={concentratingId ?? null}
                            usePending={castFlow.isSpellPending(spell.id)}
                            showPreparedToggle={!!spellcasting?.has_preparing_class && spell.level >= 1 && !spell.always_prepared}
                            onPreparedToggle={() => handlePreparedToggle(spell)}
                            preparedPending={preparedMutation.isPending && preparedMutation.variables?.spellId === spell.id}
                            onBook={() => setBookSpell(spell)}
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

      {spellcasting?.has_wizard && (
        <SpellbookSheet
          charId={charId}
          spell={bookSpell ?? ({ id: 0, name: '', level: 1, is_concentration: false, is_ritual: false, is_pinned: false, is_prepared: false } as Spell)}
          open={bookSpell !== null}
          onClose={() => setBookSpell(null)}
        />
      )}

      <ConfirmSheet
        open={confirmLost}
        onClose={() => setConfirmLost(false)}
        title={t('character.spells.book.lost_title')}
        body={t('character.spells.book.lost_body')}
        confirmLabel={t('character.spells.book.lost_button')}
        loading={loseBook.isPending}
        onConfirm={() => loseBook.mutate()}
      />

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
          casters={spellcasting?.casters ?? []}
          pickFilter={pick?.spell_pick ? { max_level: pick.spell_pick.max_level, list: pick.spell_pick.list, exact: pick.spell_pick.exact, ritual: pick.spell_pick.ritual, school: pick.spell_pick.school } : undefined}
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
  const reducedMotion = useReducedMotion()
  return (
    <div className="relative rounded-2xl">
      {/* Respiro della concentrazione: l'halo è un layer statico di cui si anima
          solo l'opacity (compositor), non il box-shadow (repaint a ogni frame).
          Con "riduci movimento" resta fermo a piena intensità. */}
      <m.div
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-2xl shadow-halo-arcane"
        initial={{ opacity: reducedMotion ? 1 : 0.45 }}
        animate={reducedMotion ? { opacity: 1 } : { opacity: [0.45, 1, 0.45] }}
        transition={{ duration: 2.8, repeat: Infinity, ease: 'easeInOut' }}
      />
      <Surface variant="arcane" ornamented className="space-y-3 @container shadow-none">
        <div className="flex flex-col gap-3 @[22rem]:flex-row @[22rem]:items-center @[22rem]:justify-between">
          <div className="flex items-center gap-2 min-w-0">
            <FlaskConical size={16} className="text-dnd-arcane-bright shrink-0" />
            <div className="min-w-0 flex-1">
              <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-arcane-bright">
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
                className="mt-1 text-xs font-cinzel uppercase tracking-widest text-dnd-arcane-bright hover:text-dnd-gold-bright"
              >
                {concBannerExpanded ? labels.collapse : labels.expand}
              </Pressable>
            )}
          </div>
        )}
      </Surface>
    </div>
  )
}

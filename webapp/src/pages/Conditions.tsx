import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Clock, Info, Plus, RotateCcw } from 'lucide-react'
import { api } from '@/api/client'
import type { Effect, HomebrewRule } from '@/lib/homebrew/types'
import Layout from '@/components/Layout'
import { LEDGER_LABEL, LEDGER_TITLE } from '@/styles/ledger'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import FilterChip from '@/components/ui/FilterChip'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import { haptic } from '@/auth/telegram'
import { spring, stagger } from '@/styles/motion'
import ConditionDetailModal from '@/pages/conditions/ConditionDetailModal'
import { CONDITION_ICONS, conditionLabel, refusedConditions } from '@/lib/conditions'
import CustomConditionCard from '@/components/homebrew/CustomConditionCard'
import {
  showHomebrewNotifications,
  type NotificationLike,
} from '@/components/homebrew/HomebrewNotification'
import { useToast } from '@/hooks/useToast'
import ConditionsSkeleton from '@/components/skeletons/ConditionsSkeleton'
import { notifyMutationError } from '@/lib/mutationError'
import DurationInput from '@/components/character/DurationInput'
import { useTickRound } from '@/hooks/useTickRound'
import { useTurnState } from '@/hooks/useTurnState'
import { formatExpiry, formatSave } from '@/lib/conditionEffects'

const CONDITION_KEYS = [
  'blinded', 'charmed', 'deafened', 'frightened', 'grappled',
  'incapacitated', 'invisible', 'paralyzed', 'petrified', 'poisoned',
  'prone', 'restrained', 'stunned', 'unconscious',
] as const

// A custom condition that an *enabled* homebrew rule knows how to apply via an
// `apply_condition` effect. `key` is the full `custom:<slug>` string the action
// writes into `char.conditions`; `slug` is the bare suffix for fallback labels.
interface AppliableCustom {
  key: string
  slug: string
  ruleId: number
  ruleName: string
}

// `apply_condition` effects can be buried inside `if`/`match` control-flow
// effects, so walk every branch recursively. We only need the *static* set of
// condition keys a rule could ever apply, so we visit all branches regardless
// of the runtime condition/case that would actually fire.
function collectApplyConditionKeys(effects: Effect[] | undefined, out: Set<string>): void {
  for (const eff of effects ?? []) {
    if (eff.action === 'apply_condition') {
      out.add(eff.key)
    } else if (eff.action === 'if') {
      collectApplyConditionKeys(eff.then, out)
      collectApplyConditionKeys(eff.else, out)
    } else if (eff.action === 'match') {
      for (const branch of Object.values(eff.cases)) {
        collectApplyConditionKeys(branch, out)
      }
    }
  }
}

// Derive the deduplicated list of custom conditions that the character's
// *enabled* rules can apply. First rule that references a given `custom:<slug>`
// key wins as the label source.
function deriveAppliableCustoms(rules: HomebrewRule[] | undefined): AppliableCustom[] {
  const byKey = new Map<string, AppliableCustom>()
  for (const rule of rules ?? []) {
    if (!rule.enabled) continue
    const keys = new Set<string>()
    for (const trigger of rule.dsl?.triggers ?? []) {
      collectApplyConditionKeys(trigger.effects, keys)
    }
    for (const key of keys) {
      if (!key.startsWith('custom:') || byKey.has(key)) continue
      byKey.set(key, {
        key,
        slug: key.slice('custom:'.length),
        ruleId: rule.id,
        ruleName: rule.name,
      })
    }
  }
  return [...byKey.values()]
}

export default function Conditions() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const [pendingExhaustion, setPendingExhaustion] = useState<number | null>(null)
  // Key of the condition (or custom:<slug>) whose mutation.mutate() call is in
  // flight — the shared `mutation` object also serves setExhaustion/removeCustom/
  // resetAll, so a variables-diff would be ambiguous; tracking the key explicitly
  // (set right before mutate, cleared on settle) mirrors pendingExhaustion above.
  const [pendingConditionKey, setPendingConditionKey] = useState<string | null>(null)
  // Ultima condizione ATTIVATA dall'utente: lo shake è il beat della transizione
  // inattiva→attiva, non deve ripartire al mount per quelle già attive.
  const [justActivated, setJustActivated] = useState<string | null>(null)
  const [detailKey, setDetailKey] = useState<string | null>(null)
  const [showExhaustionDetails, setShowExhaustionDetails] = useState(false)
  const [filterActive, setFilterActive] = useState(false)
  const [confirmResetOpen, setConfirmResetOpen] = useState(false)
  const [confirmLethalOpen, setConfirmLethalOpen] = useState(false)
  // Interdizione della Natura: affascinato o spaventato che chiede da dove viene (elementale o folletto = immune).
  const [wardAsk, setWardAsk] = useState<'charmed' | 'frightened' | null>(null)
  // Durata in round assegnata alle prossime condizioni attivate (null = fino a fine).
  const [nextDuration, setNextDuration] = useState<number | null>(null)
  const tick = useTickRound(charId)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  // Active homebrew rules — used to resolve a friendly name for each
  // `custom:<slug>` condition entry written by the `apply_condition` action.
  // Shared cache key keeps invalidation in lock-step with Inventory.tsx and
  // Homebrew.tsx.
  const { data: rules } = useQuery({
    queryKey: ['homebrew-rules', charId],
    queryFn: () => api.homebrew.listRules(charId),
  })

  const { data: session } = useQuery({ queryKey: ['session-me'], queryFn: () => api.sessions.me() })
  const { data: turn } = useTurnState(charId, session?.status === 'active')
  const inEncounter = !!turn?.in_encounter

  const mutation = useMutation({
    mutationFn: ({ conditions, durations }: { conditions: Record<string, unknown>; durations?: Record<string, number | null> }) =>
      durations
        ? api.characters.updateConditions(charId, conditions, durations)
        : api.characters.updateConditions(charId, conditions),
    onSuccess: (updated, { conditions: requested }) => {
      qc.setQueryData(['character', charId], updated)
      for (const key of refusedConditions(requested, updated.conditions)) {
        toast.info(t('character.conditions.immune_blocked', { name: conditionLabel(key, t) }))
      }
      setPendingExhaustion(null)
      setPendingConditionKey(null)
      haptic.light()
    },
    onError: (err) => {
      setPendingExhaustion(null)
      setPendingConditionKey(null)
      notifyMutationError(err)
    },
  })

  // Manual "start of turn" signal — fires every enabled homebrew rule whose
  // trigger matches `turn_started` (e.g. Bleeding ticks damage each turn).
  // The response shape here is `{notifications: [...]}`, NOT
  // `{homebrew_notifications: [...]}`, so the global MutationCache handler
  // in main.tsx ignores it; we surface the array manually via
  // `showHomebrewNotifications`. Empty list → neutral info toast so the
  // tap is always acknowledged.
  const turnStartMutation = useMutation({
    mutationFn: () => api.homebrew.turnStart(charId),
    onSuccess: (resp) => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      qc.invalidateQueries({ queryKey: ['homebrew-resources', charId] })

      const list = resp?.notifications
      if (Array.isArray(list) && list.length > 0) {
        showHomebrewNotifications(list as NotificationLike[])
      } else {
        toast.info(t('character.conditions.turn_start.no_effect'))
      }
      haptic.success()
    },
    onError: () => {
      haptic.error()
      toast.error(t('character.conditions.turn_start.error'), { hapticFeedback: false })
    },
  })

  if (!char) {
    return (
      <Layout title={t('character.conditions.title')} backTo={`/char/${charId}`} group="combat" page="conditions">
        <ConditionsSkeleton />
      </Layout>
    )
  }

  const conditions: Record<string, unknown> = (char.conditions as Record<string, unknown>) ?? {}
  const currentExhaustion = typeof conditions['exhaustion'] === 'number'
    ? (conditions['exhaustion'] as number)
    : 0

  // `custom:<slug>` entries are written by the homebrew `apply_condition`
  // action as `{rule_id, params}` objects. We surface only the truthy object
  // entries; a `false` shadow value (left behind after manual removal) is
  // filtered out so the section disappears once the user clears it.
  const customEntries = Object.entries(conditions).filter(
    ([k, v]) => k.startsWith('custom:') && v && typeof v === 'object',
  )

  const ruleNameById = new Map<number, string>()
  for (const r of rules ?? []) ruleNameById.set(r.id, r.name)

  // Custom conditions an enabled rule could apply but that aren't active yet.
  // These get an "apply" affordance; once applied they migrate into
  // `customEntries` above and render as a removable CustomConditionCard.
  const appliableCustoms = deriveAppliableCustoms(rules).filter(
    (c) => !conditions[c.key] || typeof conditions[c.key] !== 'object',
  )

  const hasWard = (char.abilities ?? []).some((a) => a.feature_key === 'druid.natures_ward')

  const toggle = (key: string) => {
    const current = conditions[key] ?? false
    if (!current && hasWard) {
      if (key === 'poisoned') {  // il server la rifiuterebbe: lo diciamo prima
        toast.info(t('character.conditions.ward.poisoned'))
        return
      }
      if (key === 'charmed' || key === 'frightened') {
        setWardAsk(key)
        return
      }
    }
    apply(key, current)
  }

  const apply = (key: string, current: unknown) => {
    setPendingConditionKey(key)
    setJustActivated(current ? null : key)
    mutation.mutate({
      conditions: { ...conditions, [key]: !current },
      durations: !current && nextDuration != null ? { [key]: nextDuration } : undefined,
    })
  }

  const setExhaustion = (level: number) => {
    // Il livello 6 uccide: un tocco sbagliato non deve costare il personaggio.
    if (level === 6 && currentExhaustion < 6 && !confirmLethalOpen) {
      setConfirmLethalOpen(true)
      return
    }
    setConfirmLethalOpen(false)
    setPendingExhaustion(level)
    mutation.mutate({ conditions: { ...conditions, exhaustion: level } })
  }

  // PATCH /conditions merges, it cannot pop a key. Sending `false` marks the
  // custom condition inactive; the card filters by truthy so the entry stops
  // rendering. The leftover `false` shadow is cleaned up next time the source
  // rule's `remove_condition` action runs (which does a proper pop()).
  const removeCustom = (key: string) => {
    setPendingConditionKey(key)
    mutation.mutate({ conditions: { [key]: false } })
  }

  // Manually apply a custom condition known to an enabled rule. Mirrors the
  // backend `execute_apply_condition` write shape ({rule_id, params}) so the
  // resulting entry is indistinguishable from one the rule applied itself —
  // CustomConditionCard renders it and the "start of turn" CTA can tick it.
  const applyCustom = (c: AppliableCustom) => {
    setPendingConditionKey(c.key)
    mutation.mutate({
      conditions: { ...conditions, [c.key]: { rule_id: c.ruleId, params: {} } },
    })
  }

  const durations = Object.fromEntries((char.condition_effects ?? [])
    .filter((e) => e.expiry_count != null).map((e) => [e.slug, e.expiry_count as number]))
  const hasDurations = Object.keys(durations).length > 0 || char.settings?.concentration_rounds_left != null

  const effectRows = (char.condition_effects ?? [])
    .filter((e) => conditions[e.slug])
    .map((e) => ({ e, expiry: formatExpiry(e, t), save: formatSave(e, t) }))
    .filter((r) => r.expiry || r.save || r.e.applied_by_gm)

  const activeCount =
    CONDITION_KEYS.filter((k) => conditions[k]).length +
    (currentExhaustion > 0 ? 1 : 0) +
    customEntries.length
  const visibleConditions = filterActive
    ? CONDITION_KEYS.filter((k) => conditions[k])
    : CONDITION_KEYS

  // Reset-All only clears the 14 standard conditions + exhaustion. Custom
  // `custom:*` entries are intentionally left untouched here because their
  // lifecycle is governed by the homebrew rule that applied them — only the
  // rule (via `remove_condition`) or the per-card trash button should clear
  // them.
  const resetAll = () => {
    const cleared: Record<string, unknown> = { exhaustion: 0 }
    for (const k of CONDITION_KEYS) cleared[k] = false
    mutation.mutate({ conditions: cleared })
    setConfirmResetOpen(false)
  }

  return (
    <Layout title={t('character.conditions.title')} backTo={`/char/${charId}`} group="combat" page="conditions">
      {/* Turn-start CTA — only visible when at least one homebrew-applied
          `custom:*` condition is active, because that's the only situation
          where a `turn_started` trigger can have an effect the player
          notices on this page (e.g. Bleeding ticks damage each turn). */}
      {customEntries.length > 0 && (
        <Button
          variant="primary"
          size="lg"
          fullWidth
          onClick={() => turnStartMutation.mutate()}
          icon={<Clock size={18} />}
          loading={turnStartMutation.isPending}
          haptic="medium"
        >
          {t('character.conditions.turn_start.label')}
        </Button>
      )}

      <section>
        <DurationInput value={nextDuration} onChange={setNextDuration} />
        {inEncounter && (
          <p className="mt-2 text-xs text-dnd-text-muted font-body">
            {t('character.conditions.duration.in_encounter')}
          </p>
        )}
        {hasDurations && !inEncounter && (
          <Button
            variant="secondary"
            size="sm"
            className="mt-2"
            icon={<Clock size={14} />}
            loading={tick.isPending}
            onClick={() => tick.mutate()}
          >
            {t('character.conditions.duration.tick')}
          </Button>
        )}
      </section>

      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <FilterChip
            label={t('character.conditions.filter_all')}
            selected={!filterActive}
            onToggle={() => setFilterActive(false)}
          />
          <FilterChip
            label={t('character.conditions.filter_active')}
            selected={filterActive}
            onToggle={() => setFilterActive(true)}
            count={activeCount}
          />
        </div>
        {activeCount > 0 && (
          <Button
            variant="ghost"
            size="sm"
            icon={<RotateCcw size={12} />}
            haptic="warning"
            onClick={() => setConfirmResetOpen(true)}
            disabled={mutation.isPending}
          >
            {t('character.conditions.reset_all')}
          </Button>
        )}
      </div>

      {activeCount === 0 && !filterActive && (
        <p className="px-1 text-sm text-dnd-text-muted font-body italic">
          {t('character.conditions.none_active')}
        </p>
      )}

      {/* Exhaustion tracker — separated because levels are cumulative, not toggle. */}
      <section className="border-y border-dnd-border px-1 py-2.5">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className={LEDGER_LABEL}>
              {t('character.conditions.exhaustion_condition', { context: char.rules_edition })}
            </span>
            <Pressable
              aria-label={t('character.conditions.detail_aria')}
              aria-expanded={showExhaustionDetails}
              onClick={() => setShowExhaustionDetails((v) => !v)}
              className={`relative hit-44 transition-colors ${
                showExhaustionDetails
                  ? 'text-dnd-gold-bright'
                  : 'text-dnd-text-muted hover:text-dnd-gold-bright'
              }`}
            >
              <Info size={14} />
            </Pressable>
          </div>
          <span className={`font-mono text-lg font-bold tabular-nums
            ${currentExhaustion > 0 ? 'text-dnd-amber' : 'text-dnd-text-faint'}`}>
            {currentExhaustion}<span className="text-sm text-dnd-text-muted">/6</span>
          </span>
        </div>
        {/* 7 livelli in una riga a tutta larghezza: sotto i 412px sono larghi ~35px, ma alti 44 e senza vuoti tra loro. */}
        <div className="flex gap-1.5" data-layout-ok="scala di spossatezza">
          {[0, 1, 2, 3, 4, 5, 6].map((level) => {
            const displayLevel = pendingExhaustion ?? currentExhaustion
            const isActive = displayLevel === level
            const isFilled = level <= displayLevel
            return (
              <Pressable
                key={level}
                onClick={() => setExhaustion(level)}
                pending={mutation.isPending && pendingExhaustion === level}
                disabled={mutation.isPending && pendingExhaustion !== level}
                spinnerSize={12}
                className={`flex-1 min-h-[44px] rounded-lg font-cinzel font-black text-sm
                  ${isActive
                    ? 'bg-gradient-ember text-dnd-parchment shadow-parchment-md'
                    : isFilled
                      ? 'bg-dnd-amber/40 text-dnd-text'
                      : 'bg-dnd-surface border border-dnd-border text-dnd-text-faint'}`}
                whileTap={{ scale: 0.92 }}
                transition={spring.press}
              >
                {level}
              </Pressable>
            )
          })}
        </div>
        {/* Exhaustion details — intro + 6 level descriptions, toggled by Info button */}
        {showExhaustionDetails && (() => {
          const intro = t('character.conditions.desc.exhaustion', { context: char.rules_edition }) as string
          const levels = t('character.conditions.desc.exhaustion_levels', {
            returnObjects: true,
            context: char.rules_edition,
          }) as string[]
          return (
            <div className="mt-4 space-y-2">
              <p className="text-sm text-dnd-text font-body leading-relaxed">
                {intro}
              </p>
              <div className="space-y-1 text-sm">
                {levels.map((desc, idx) => {
                  const lvl = idx + 1
                  const isCurrent = lvl === currentExhaustion
                  return (
                    <div
                      key={lvl}
                      className={
                        isCurrent
                          ? 'px-3 py-2 rounded-md border border-dnd-gold/50 bg-dnd-gold/10 text-dnd-gold-bright'
                          : 'px-3 py-1.5 text-dnd-text-faint'
                      }
                    >
                      {desc}
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })()}
        <p className="mt-2 text-xs font-body text-dnd-text-muted">
          {t('character.conditions.exhaustion_caption', { defaultValue: 'Livelli (cumulativi)' })}
        </p>
      </section>

      {effectRows.length > 0 && (
        <section className="px-1">
          <h3 className={`mb-2 ${LEDGER_TITLE}`}>
            {t('character.conditions.effect.active_title')}
          </h3>
          <ul className="space-y-2">
            {effectRows.map(({ e, expiry, save }) => (
              <li key={e.slug} className="text-sm font-body">
                <span className="font-semibold text-dnd-text">
                  {(CONDITION_KEYS as readonly string[]).includes(e.slug) ? t(`character.conditions.${e.slug}`) : conditionLabel(e.slug, t)}
                </span>
                {e.applied_by_gm && (
                  <span className="ml-2 text-xs uppercase tracking-wider text-dnd-amber">
                    {t('character.conditions.effect.by_gm')}
                  </span>
                )}
                {expiry && <p className="text-xs text-dnd-text-muted">{expiry}</p>}
                {save && <p className="text-xs text-dnd-text-muted tabular-nums">{save}</p>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Condition grid */}
      <m.div
        className="grid grid-cols-2 max-[359px]:grid-cols-1 md:grid-cols-3 gap-x-4 border-t border-dnd-border"
        initial="initial"
        animate="animate"
        variants={{
          initial: {},
          animate: { transition: { staggerChildren: stagger.listTight } },
        }}
      >
        {visibleConditions.map((key) => {
          const Icon = CONDITION_ICONS[key]
          const active = !!conditions[key]
          return (
            <m.div
              key={key}
              variants={{
                initial: { opacity: 0, y: 8 },
                animate: { opacity: 1, y: 0 },
              }}
              className={`flex min-w-0 items-center border-b border-dnd-border/60 transition-colors
                ${active ? 'bg-dnd-crimson/10 text-dnd-text' : 'text-dnd-text'}`}
            >
              <Pressable
                onClick={() => toggle(key)}
                pending={mutation.isPending && pendingConditionKey === key}
                disabled={mutation.isPending && pendingConditionKey !== key}
                whileTap={{ scale: 0.95 }}
                animate={active && justActivated === key ? { x: [-2, 2, -1, 1, 0] } : { x: 0 }}
                transition={{ duration: 0.25 }}
                className="my-0.5 flex-1 min-w-0 min-h-[44px] flex items-center gap-2 pl-1 py-1 text-left"
              >
                <Icon size={16} className={`shrink-0 ${active ? 'text-dnd-crimson-bright' : 'text-dnd-gold'}`} />
                <span className={`min-w-0 truncate text-sm font-body leading-tight ${active ? 'font-semibold' : ''}`}>
                  {t(`character.conditions.${key}`)}
                </span>
                {active && durations[key] != null && (
                  <span className="ml-auto text-xs font-mono tabular-nums text-dnd-amber">
                    {t('character.conditions.duration.left', { n: durations[key] })}
                  </span>
                )}
              </Pressable>
              <Pressable
                aria-label={t('character.conditions.detail_aria')}
                onClick={() => setDetailKey(key)}
                className="shrink-0 hit-44 p-2 text-dnd-text-muted hover:text-dnd-gold-bright transition-colors"
              >
                <Info size={16} />
              </Pressable>
            </m.div>
          )
        })}
      </m.div>

      {/* Apply a custom condition that an enabled homebrew rule knows how to
          set (e.g. start "Bleeding"). Only rendered when at least one enabled
          rule has an `apply_condition` effect for a not-yet-active key — no
          dead UI otherwise. */}
      {appliableCustoms.length > 0 && (
        <section className="px-1">
          <h3 className={`mb-2 ${LEDGER_TITLE}`}>
            {t('character.conditions.apply_custom_title')}
          </h3>
          <div className="flex flex-wrap gap-2">
            {appliableCustoms.map((c) => (
              <Pressable
                key={c.key}
                onClick={() => applyCustom(c)}
                pending={mutation.isPending && pendingConditionKey === c.key}
                disabled={mutation.isPending && pendingConditionKey !== c.key}
                whileTap={{ scale: 0.95 }}
                transition={spring.press}
                aria-label={t('character.conditions.apply_custom_aria', { name: c.ruleName })}
                className="inline-flex items-center gap-2 min-h-[44px] px-3 rounded-xl
                           border border-dnd-crimson/40 bg-dnd-crimson/10
                           text-dnd-crimson-bright font-body text-sm font-semibold
                           hover:bg-dnd-crimson/15 transition-colors
                           disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Plus size={16} className="shrink-0" />
                <span className="truncate max-w-[12rem]">{c.ruleName}</span>
              </Pressable>
            ))}
          </div>
        </section>
      )}

      {/* Custom conditions applied by homebrew rules (`apply_condition`). */}
      {customEntries.length > 0 && (
        <section className="px-1">
          <h3 className={`mb-2 ${LEDGER_TITLE}`}>
            {t('character.conditions.custom_section_title')}
          </h3>
          <div className="space-y-2">
            {customEntries.map(([key, value]) => {
              const ruleId =
                value && typeof value === 'object' && 'rule_id' in value
                  ? (value as { rule_id?: number }).rule_id
                  : undefined
              const ruleName =
                ruleId !== undefined ? ruleNameById.get(ruleId) : undefined
              return (
                <CustomConditionCard
                  key={key}
                  conditionKey={key}
                  value={value}
                  ruleName={ruleName}
                  onRemove={() => removeCustom(key)}
                  isPending={mutation.isPending && pendingConditionKey === key}
                  disabled={mutation.isPending && pendingConditionKey !== key}
                />
              )
            })}
          </div>
        </section>
      )}

      {detailKey !== null && (
        <ConditionDetailModal
          condKey={detailKey}
          exhaustionLevel={currentExhaustion}
          edition={char.rules_edition}
          onClose={() => setDetailKey(null)}
        />
      )}

      <ConfirmSheet
        open={wardAsk !== null}
        onClose={() => { setWardAsk(null); toast.info(t('character.conditions.ward.immune_done')) }}
        title={t('character.conditions.ward.title')}
        body={t('character.conditions.ward.body')}
        confirmLabel={t('character.conditions.ward.apply')}
        cancelLabel={t('character.conditions.ward.immune')}
        confirmVariant="primary"
        onConfirm={() => { if (wardAsk) apply(wardAsk, false); setWardAsk(null) }}
      />

      <ConfirmSheet
        open={confirmLethalOpen}
        onClose={() => setConfirmLethalOpen(false)}
        title={t('character.conditions.exhaustion_condition', { context: char.rules_edition })}
        body={t('character.conditions.exhaustion_lethal_body')}
        confirmLabel={t('character.conditions.exhaustion_lethal_confirm')}
        cancelLabel={t('common.cancel')}
        onConfirm={() => setExhaustion(6)}
        loading={mutation.isPending}
      />

      <ConfirmSheet
        open={confirmResetOpen}
        onClose={() => setConfirmResetOpen(false)}
        title={t('character.conditions.reset_all')}
        body={t('character.conditions.reset_all_confirm')}
        confirmLabel={t('common.confirm')}
        cancelLabel={t('common.cancel')}
        confirmVariant="primary"
        onConfirm={resetAll}
        loading={mutation.isPending}
      />
    </Layout>
  )
}

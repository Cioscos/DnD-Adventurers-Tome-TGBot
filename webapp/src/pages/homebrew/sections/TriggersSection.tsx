import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'
import { Plus, Trash2, X } from 'lucide-react'
import Button from '@/components/ui/Button'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import Sheet from '@/components/ui/Sheet'
import { eventLabel, type Locale } from '@/lib/homebrew/i18n-dsl'
import type { EventType, Filter, Table, Trigger } from '@/lib/homebrew/types'
import EffectChainEditor from './EffectChainEditor'

export interface TriggersSectionProps {
  triggers: Trigger[] | undefined
  tables: Table[]
  onChange: (triggers: Trigger[]) => void
}

const ALL_EVENTS: readonly EventType[] = [
  'attack_rolled',
  'damage_taken',
  'dropped_to_zero',
  'hp_healed',
  'long_rest_taken',
  'short_rest_taken',
  'spell_cast',
  'ability_used',
  'item_equipped',
  'item_unequipped',
  'level_up',
  'resource_changed',
  'resource_depleted',
  'turn_started',
  'manual_trigger',
] as const

// ---------------------------------------------------------------------------
// Preset filters per event
// ---------------------------------------------------------------------------

const FUMBLE_FILTER: Filter = { path: '$event.is_fumble', op: 'eq', value: true }
const CRITICAL_FILTER: Filter = { path: '$event.is_critical', op: 'eq', value: true }
const WAS_CRIT_HIT_FILTER: Filter = {
  path: '$event.was_critical_hit',
  op: 'eq',
  value: true,
}

const PRESETS_BY_EVENT: Partial<Record<EventType, Filter[]>> = {
  attack_rolled: [FUMBLE_FILTER, CRITICAL_FILTER],
  damage_taken: [WAS_CRIT_HIT_FILTER],
}

/**
 * Plain-language label for a known preset filter. Returns null for ad-hoc
 * filters — the caller falls back to the raw `${path} ${op} ${value}` form.
 */
function presetLabel(filter: Filter, t: TFunction): string | null {
  if (filter.op !== 'eq') return null
  if (filter.path === '$event.is_fumble' && filter.value === true) {
    return t('homebrew.triggers.preset_filters.fumble')
  }
  if (filter.path === '$event.is_critical' && filter.value === true) {
    return t('homebrew.triggers.preset_filters.critical')
  }
  if (filter.path === '$event.was_critical_hit' && filter.value === true) {
    return t('homebrew.triggers.preset_filters.was_crit_hit')
  }
  if (filter.path === '$subject.is_equipped' && filter.value === true) {
    return t('homebrew.triggers.preset_filters.is_equipped')
  }
  return null
}

function filtersEqual(a: Filter, b: Filter): boolean {
  return a.path === b.path && a.op === b.op && a.value === b.value
}

function defaultTrigger(): Trigger {
  return { event: 'attack_rolled', filters: [], effects: [] }
}

// ---------------------------------------------------------------------------
// Section
// ---------------------------------------------------------------------------

/**
 * Task 4.10 — Trigger list editor.
 *
 * Each card has:
 *   1. Event dropdown (15 events, plain-language labels via `eventLabel`)
 *   2. Filter chips row (preset filters via `presetLabel`, ad-hoc fallback)
 *   3. EffectChainEditor for the trigger's effect chain
 *   4. Delete button (with ConfirmSheet)
 *
 * Filter presets are scoped per event (PRESETS_BY_EVENT). Duplicate filters
 * are prevented when adding from the preset picker.
 */
export default function TriggersSection({ triggers, tables, onChange }: TriggersSectionProps) {
  const { t, i18n } = useTranslation()
  const locale: Locale = i18n.language?.startsWith('en') ? 'en' : 'it'
  const list = triggers ?? []

  const [confirmDeleteIndex, setConfirmDeleteIndex] = useState<number | null>(null)
  const [filterPickerIndex, setFilterPickerIndex] = useState<number | null>(null)

  const updateTrigger = (index: number, next: Trigger) => {
    const copy = list.slice()
    copy[index] = next
    onChange(copy)
  }

  const handleAddTrigger = () => {
    onChange([...list, defaultTrigger()])
  }

  const handleDeleteTrigger = () => {
    if (confirmDeleteIndex === null) return
    const copy = list.slice()
    copy.splice(confirmDeleteIndex, 1)
    onChange(copy)
    setConfirmDeleteIndex(null)
  }

  const handleAddFilter = (triggerIndex: number, filter: Filter) => {
    const trig = list[triggerIndex]
    if (trig.filters.some((f) => filtersEqual(f, filter))) {
      setFilterPickerIndex(null)
      return
    }
    updateTrigger(triggerIndex, {
      ...trig,
      filters: [...trig.filters, filter],
    })
    setFilterPickerIndex(null)
  }

  const handleRemoveFilter = (triggerIndex: number, filterIndex: number) => {
    const trig = list[triggerIndex]
    const copy = trig.filters.slice()
    copy.splice(filterIndex, 1)
    updateTrigger(triggerIndex, { ...trig, filters: copy })
  }

  return (
    <div className="space-y-3">
      {list.length === 0 ? (
        <p className="px-2 py-4 text-center text-sm font-body italic text-dnd-text-muted">
          {t('homebrew.triggers.empty')}
        </p>
      ) : (
        <ul className="space-y-3">
          {list.map((trig, index) => (
            <li
              key={index}
              className="bg-dnd-surface-raised border border-dnd-border rounded-2xl p-4 space-y-3"
            >
              <div className="flex items-start gap-2">
                <div className="flex-1 min-w-0 space-y-1.5">
                  <label className="block text-[11px] uppercase tracking-wider font-cinzel font-bold text-dnd-gold-dim">
                    {t('homebrew.triggers.event_label')}
                  </label>
                  <select
                    value={trig.event}
                    onChange={(e) =>
                      updateTrigger(index, {
                        ...trig,
                        event: e.target.value as EventType,
                      })
                    }
                    className="w-full px-3 py-2.5 min-h-[48px] rounded-lg bg-dnd-surface text-dnd-text border-b-2 border-dnd-border outline-none font-body"
                  >
                    {ALL_EVENTS.map((ev) => (
                      <option key={ev} value={ev}>
                        {eventLabel(ev, [], locale)}
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  type="button"
                  onClick={() => setConfirmDeleteIndex(index)}
                  className="shrink-0 w-11 h-11 inline-flex items-center justify-center rounded-lg text-dnd-crimson hover:text-dnd-crimson-bright hover:bg-dnd-crimson/10 transition-colors mt-6"
                  aria-label="Delete trigger"
                >
                  <Trash2 size={16} />
                </button>
              </div>

              {/* Filters */}
              <div className="space-y-2">
                <div className="text-[11px] uppercase tracking-wider font-cinzel font-bold text-dnd-gold-dim">
                  {t('homebrew.triggers.filters_label')}
                </div>
                <div className="flex flex-wrap gap-2 items-center">
                  {trig.filters.map((f, fi) => {
                    const label = presetLabel(f, t)
                    return (
                      <span
                        key={fi}
                        className="inline-flex items-center gap-1.5 min-h-[36px] pl-3 pr-1 py-1 rounded-full bg-dnd-chip-bg border border-dnd-gold/60 text-dnd-gold-bright text-[11px] font-body"
                      >
                        {label ? (
                          <span>{label}</span>
                        ) : (
                          <span className="font-mono text-[10px] text-dnd-text">
                            {String(f.path)} {f.op} {String(f.value)}
                          </span>
                        )}
                        <button
                          type="button"
                          onClick={() => handleRemoveFilter(index, fi)}
                          className="w-7 h-7 inline-flex items-center justify-center rounded-full hover:bg-dnd-crimson/20 hover:text-dnd-crimson-bright text-dnd-gold-dim transition-colors"
                          aria-label="Remove filter"
                        >
                          <X size={12} />
                        </button>
                      </span>
                    )
                  })}
                  <button
                    type="button"
                    onClick={() => setFilterPickerIndex(index)}
                    className="inline-flex items-center gap-1 min-h-[36px] px-3 py-1 rounded-full bg-dnd-surface border border-dashed border-dnd-border text-dnd-text-muted hover:text-dnd-gold-bright hover:border-dnd-gold/60 text-[11px] font-body transition-colors"
                  >
                    <Plus size={12} />
                    <span>{t('homebrew.triggers.add_filter')}</span>
                  </button>
                </div>
              </div>

              {/* Effect chain */}
              <div className="pt-1">
                <EffectChainEditor
                  effects={trig.effects}
                  tables={tables}
                  onChange={(effects) => updateTrigger(index, { ...trig, effects })}
                />
              </div>
            </li>
          ))}
        </ul>
      )}

      <Button
        variant="secondary"
        size="sm"
        icon={<Plus size={16} />}
        onClick={handleAddTrigger}
      >
        {t('homebrew.triggers.add_button')}
      </Button>

      <FilterPicker
        open={filterPickerIndex !== null}
        event={filterPickerIndex !== null ? list[filterPickerIndex].event : null}
        existing={filterPickerIndex !== null ? list[filterPickerIndex].filters : []}
        onClose={() => setFilterPickerIndex(null)}
        onPick={(filter) => {
          if (filterPickerIndex !== null) handleAddFilter(filterPickerIndex, filter)
        }}
      />

      <ConfirmSheet
        open={confirmDeleteIndex !== null}
        onClose={() => setConfirmDeleteIndex(null)}
        onConfirm={handleDeleteTrigger}
        title={t('common.delete')}
        body={t('homebrew.triggers.delete_confirm')}
        confirmLabel={t('common.delete')}
        cancelLabel={t('common.cancel')}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Filter picker
// ---------------------------------------------------------------------------

function FilterPicker({
  open,
  event,
  existing,
  onClose,
  onPick,
}: {
  open: boolean
  event: EventType | null
  existing: Filter[]
  onClose: () => void
  onPick: (filter: Filter) => void
}) {
  const { t } = useTranslation()
  const presets = event ? PRESETS_BY_EVENT[event] ?? [] : []
  const available = presets.filter(
    (preset) => !existing.some((f) => filtersEqual(f, preset)),
  )

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title={t('homebrew.triggers.filter_picker_title')}
      centered
    >
      <div className="p-5 space-y-2">
        {available.length === 0 ? (
          <p className="px-2 py-3 text-center text-xs font-body italic text-dnd-text-muted">
            {t('homebrew.triggers.no_presets')}
          </p>
        ) : (
          <ul className="space-y-2">
            {available.map((preset, i) => {
              const label = presetLabel(preset, t) ?? preset.path
              return (
                <li key={i}>
                  <button
                    type="button"
                    onClick={() => onPick(preset)}
                    className="w-full min-h-[48px] px-3 py-2.5 rounded-xl bg-dnd-surface-raised border border-dnd-border hover:border-dnd-gold/70 text-left text-sm font-body text-dnd-text transition-colors"
                  >
                    {label}
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </Sheet>
  )
}

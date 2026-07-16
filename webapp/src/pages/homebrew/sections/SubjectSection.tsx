import { useTranslation } from 'react-i18next'
import Pressable from '@/components/ui/Pressable'
import FilterChip from '@/components/ui/FilterChip'
import Input from '@/components/ui/Input'
import type { Subject, SubjectType } from '@/lib/homebrew/types'

export interface SubjectSectionProps {
  subject: Subject
  onChange: (subject: Subject) => void
}

const SUBJECT_TYPES: readonly { value: SubjectType; emoji: string }[] = [
  { value: 'item', emoji: '⚔️' },
  { value: 'character', emoji: '👤' },
]

const ITEM_TYPES = [
  'weapon',
  'armor',
  'shield',
  'accessory',
  'gear',
  'consumable',
  'generic',
] as const

/**
 * Task 4.6 — subject picker. 3-card radio for the subject type
 * (item / character / ability). When 'item' is selected, exposes a
 * multi-select chip group for item_types plus an optional
 * name_contains substring filter.
 *
 * Switching the subject type resets `filter` to `undefined` so stale
 * item-only filters don't linger when the user picks character/ability.
 */
export default function SubjectSection({ subject, onChange }: SubjectSectionProps) {
  const { t } = useTranslation()

  const setType = (type: SubjectType) => {
    onChange({ type, filter: undefined })
  }

  const currentTypes = subject.filter?.item_types ?? []
  const currentNameContains = subject.filter?.name_contains ?? ''

  const emitItemFilter = (item_types: string[], nameContains: string) => {
    const next: Subject = { type: 'item' }
    const filter: NonNullable<Subject['filter']> = {}
    if (item_types.length) filter.item_types = item_types
    if (nameContains.trim()) filter.name_contains = nameContains.trim()
    if (Object.keys(filter).length) next.filter = filter
    onChange(next)
  }

  const toggleItemType = (key: string) => {
    const has = currentTypes.includes(key)
    const next = has ? currentTypes.filter((k) => k !== key) : [...currentTypes, key]
    emitItemFilter(next, currentNameContains)
  }

  const setNameContains = (value: string) => {
    emitItemFilter(currentTypes, value)
  }

  return (
    <div className="space-y-4">
      {/* Region 1 — Subject type radio cards */}
      <div className="grid grid-cols-3 gap-2">
        {SUBJECT_TYPES.map(({ value, emoji }) => {
          const selected = subject.type === value
          const styles = selected
            ? 'bg-dnd-chip-bg border-dnd-gold/70 text-dnd-gold-bright shadow-halo-gold'
            : 'bg-dnd-surface border-dnd-border text-dnd-text-muted hover:text-dnd-gold-bright/80'
          return (
            <Pressable
              key={value}
              onClick={() => setType(value)}
              whileTap={{ scale: 0.97 }}
              aria-pressed={selected}
              className={`flex flex-col items-center justify-center gap-1 min-h-[64px] px-2 py-2 rounded-xl border font-cinzel uppercase text-[11px] tracking-widest transition-colors ${styles}`}
            >
              <span className="text-xl leading-none" aria-hidden>
                {emoji}
              </span>
              <span className="text-center leading-tight">
                {t(`homebrew.subject.types.${value}`)}
              </span>
            </Pressable>
          )
        })}
      </div>

      {/* Region 2 + 3 — item filters */}
      {subject.type === 'item' && (
        <div className="space-y-3">
          <div>
            <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
              {t('homebrew.subject.item_types_label')}
            </label>
            <div className="flex flex-wrap gap-1.5">
              {ITEM_TYPES.map((key) => (
                <FilterChip
                  key={key}
                  label={t(`homebrew.subject.item_types.${key}`)}
                  selected={currentTypes.includes(key)}
                  onToggle={() => toggleItemType(key)}
                />
              ))}
            </div>
            <p className="mt-1.5 text-[11px] italic text-dnd-text-muted font-body">
              {t('homebrew.subject.item_types_helper')}
            </p>
          </div>

          <Input
            label={t('homebrew.subject.name_contains_label')}
            value={currentNameContains}
            onChange={setNameContains}
            placeholder={t('homebrew.subject.name_contains_placeholder')}
          />
        </div>
      )}
    </div>
  )
}

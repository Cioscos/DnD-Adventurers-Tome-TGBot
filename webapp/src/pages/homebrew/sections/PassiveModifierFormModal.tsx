import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import FilterChip from '@/components/ui/FilterChip'
import type { Filter, PassiveModifier } from '@/lib/homebrew/types'

// ---------------------------------------------------------------------------
// Canonical D&D 5e lists for the 2-tier sub-pickers.
// ---------------------------------------------------------------------------
export const SKILL_SLUGS = [
  'acrobatics',
  'animal_handling',
  'arcana',
  'athletics',
  'deception',
  'history',
  'insight',
  'intimidation',
  'investigation',
  'medicine',
  'nature',
  'perception',
  'performance',
  'persuasion',
  'religion',
  'sleight_of_hand',
  'stealth',
  'survival',
] as const

export const ABILITY_SLUGS = [
  'strength',
  'dexterity',
  'constitution',
  'intelligence',
  'wisdom',
  'charisma',
] as const

export type TargetCategory = 'ac' | 'hp_max' | 'speed' | 'skill' | 'save'

const TARGET_CATEGORIES: readonly TargetCategory[] = [
  'ac',
  'hp_max',
  'speed',
  'skill',
  'save',
] as const

// Backend regex sanity-check (mirrors api/services/homebrew/dsl.py:367).
const TARGET_REGEX =
  /^character\.(ac|hit_points_max|speed|skill\.[a-z_]+|saving_throw\.[a-z]+)$/

/**
 * Compose the final DSL target string from category + sub-key.
 * Returns null when a sub-key is required but missing.
 */
function composeTarget(category: TargetCategory, sub: string): string | null {
  switch (category) {
    case 'ac':
      return 'character.ac'
    case 'hp_max':
      return 'character.hit_points_max'
    case 'speed':
      return 'character.speed'
    case 'skill':
      return sub ? `character.skill.${sub}` : null
    case 'save':
      return sub ? `character.saving_throw.${sub}` : null
  }
}

/**
 * Reverse of composeTarget — split a DSL target back into category + sub.
 * Used to seed the modal draft when editing.
 */
function decomposeTarget(target: string): { category: TargetCategory; sub: string } {
  if (target === 'character.ac') return { category: 'ac', sub: '' }
  if (target === 'character.hit_points_max') return { category: 'hp_max', sub: '' }
  if (target === 'character.speed') return { category: 'speed', sub: '' }
  if (target.startsWith('character.skill.')) {
    return { category: 'skill', sub: target.slice('character.skill.'.length) }
  }
  if (target.startsWith('character.saving_throw.')) {
    return { category: 'save', sub: target.slice('character.saving_throw.'.length) }
  }
  // Unknown — default to AC so the modal doesn't crash on legacy data.
  return { category: 'ac', sub: '' }
}

/**
 * Sentinel "always true" filter used as the default `when` for MVP modifiers.
 * Matching algorithm: backend applies the rule's subject filter first, then
 * evaluates `when` as an additional constraint. A sentinel always-true means
 * "match the rule's subject scope, nothing more".
 */
function defaultWhenFilter(): Filter {
  return { path: '$character.id', op: 'gt', value: 0 }
}

interface DraftState {
  labelIt: string
  labelEn: string
  category: TargetCategory
  sub: string
  value: string // raw text input — coerced on save
}

function emptyDraft(): DraftState {
  return {
    labelIt: '',
    labelEn: '',
    category: 'ac',
    sub: '',
    value: '0',
  }
}

function draftFromMod(mod: PassiveModifier): DraftState {
  const { category, sub } = decomposeTarget(mod.target)
  return {
    labelIt: mod.label_i18n.it ?? '',
    labelEn: mod.label_i18n.en ?? '',
    category,
    sub,
    value: String(mod.value),
  }
}

interface PassiveModifierFormModalProps {
  open: boolean
  onClose: () => void
  initial: PassiveModifier | null
  onSave: (next: PassiveModifier) => void
}

/**
 * Sheet-hosted form to create or edit a PassiveModifier.
 *
 * The `when` filter is NOT user-editable in this MVP: new modifiers default
 * to a sentinel always-true filter, and existing modifiers keep their stored
 * `when` value across edits (preserved via `initial?.when ?? defaultWhenFilter()`).
 * Advanced conditional editing is deferred to a future task.
 */
export default function PassiveModifierFormModal({
  open,
  onClose,
  initial,
  onSave,
}: PassiveModifierFormModalProps) {
  const { t } = useTranslation()
  const [draft, setDraft] = useState<DraftState>(() =>
    initial ? draftFromMod(initial) : emptyDraft(),
  )
  const [errors, setErrors] = useState<{ labels?: string; target?: string; value?: string }>({})

  useEffect(() => {
    if (open) {
      setDraft(initial ? draftFromMod(initial) : emptyDraft())
      setErrors({})
    }
  }, [open, initial])

  const setCategory = (next: TargetCategory) => {
    setDraft((d) => {
      // Reset sub when category changes: pick first slug for skill/save,
      // empty for the targets that don't take a sub.
      let nextSub = ''
      if (next === 'skill') nextSub = SKILL_SLUGS[0]
      else if (next === 'save') nextSub = ABILITY_SLUGS[0]
      return { ...d, category: next, sub: nextSub }
    })
    setErrors((e) => ({ ...e, target: undefined }))
  }

  const setSub = (next: string) => {
    setDraft((d) => ({ ...d, sub: next }))
    setErrors((e) => ({ ...e, target: undefined }))
  }

  const setLabelIt = (v: string) => {
    setDraft((d) => ({ ...d, labelIt: v }))
    if (errors.labels) setErrors((e) => ({ ...e, labels: undefined }))
  }

  const setLabelEn = (v: string) => {
    setDraft((d) => ({ ...d, labelEn: v }))
    if (errors.labels) setErrors((e) => ({ ...e, labels: undefined }))
  }

  const setValue = (v: string) => {
    setDraft((d) => ({ ...d, value: v }))
    if (errors.value) setErrors((e) => ({ ...e, value: undefined }))
  }

  const handleSave = () => {
    const nextErrors: typeof errors = {}

    if (!draft.labelIt.trim() || !draft.labelEn.trim()) {
      nextErrors.labels = t('homebrew.passive.modal.label_required')
    }

    const composed = composeTarget(draft.category, draft.sub)
    if (!composed || !TARGET_REGEX.test(composed)) {
      nextErrors.target = t('homebrew.passive.modal.target_required')
    }

    const num = Number(draft.value)
    const isValidInt = draft.value.trim() !== '' && Number.isFinite(num) && Number.isInteger(num)
    if (!isValidInt) {
      nextErrors.value = t('homebrew.passive.modal.value_invalid')
    }

    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      return
    }

    const next: PassiveModifier = {
      when: initial?.when ?? defaultWhenFilter(),
      target: composed!,
      value: num,
      label_i18n: { it: draft.labelIt.trim(), en: draft.labelEn.trim() },
    }
    onSave(next)
  }

  const title = initial
    ? t('homebrew.passive.modal.title_edit')
    : t('homebrew.passive.modal.title_new')

  return (
    <Sheet open={open} onClose={onClose} title={title} centered>
      <div className="p-5 space-y-4">
        <Input
          label={t('homebrew.passive.modal.label_it')}
          value={draft.labelIt}
          onChange={setLabelIt}
          placeholder={t('homebrew.passive.modal.label_it_placeholder')}
          error={errors.labels && !draft.labelIt.trim() ? errors.labels : undefined}
        />
        <Input
          label={t('homebrew.passive.modal.label_en')}
          value={draft.labelEn}
          onChange={setLabelEn}
          placeholder={t('homebrew.passive.modal.label_en_placeholder')}
          error={errors.labels && !draft.labelEn.trim() ? errors.labels : undefined}
        />

        {/* Target category */}
        <div>
          <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
            {t('homebrew.passive.modal.target_label')}
          </label>
          <div className="flex flex-wrap gap-1.5">
            {TARGET_CATEGORIES.map((cat) => (
              <FilterChip
                key={cat}
                label={t(`homebrew.passive.target_labels.${cat}`)}
                selected={draft.category === cat}
                onToggle={() => setCategory(cat)}
              />
            ))}
          </div>
          {errors.target && (
            <p className="text-[var(--dnd-crimson-bright)] text-[11px] mt-1 font-body">
              {errors.target}
            </p>
          )}
        </div>

        {/* Sub-picker for skill / save */}
        {(draft.category === 'skill' || draft.category === 'save') && (
          <div>
            <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
              {draft.category === 'skill'
                ? t('homebrew.passive.modal.skill_sub_label')
                : t('homebrew.passive.modal.save_sub_label')}
            </label>
            <select
              value={draft.sub}
              onChange={(e) => setSub(e.target.value)}
              className="w-full px-3 py-2.5 min-h-[48px] rounded-lg bg-dnd-surface text-dnd-text border-b-2 border-dnd-border outline-none font-body"
            >
              {(draft.category === 'skill' ? SKILL_SLUGS : ABILITY_SLUGS).map((slug) => (
                <option key={slug} value={slug}>
                  {draft.category === 'skill'
                    ? t(`character.skills.${slug}`, { defaultValue: slug })
                    : t(`common.abilities.${slug}`, { defaultValue: slug })}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Numeric value */}
        <div>
          <Input
            label={t('homebrew.passive.modal.value_label')}
            type="number"
            inputMode="numeric"
            value={draft.value}
            onChange={setValue}
            placeholder="0"
            error={errors.value}
          />
          <p className="mt-1 text-[11px] italic text-dnd-text-muted font-body">
            {t('homebrew.passive.modal.value_helper')}
          </p>
        </div>

        <div className="flex gap-2 pt-2">
          <Button variant="secondary" fullWidth onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button variant="primary" fullWidth haptic="success" onClick={handleSave}>
            {t('common.save')}
          </Button>
        </div>
      </div>
    </Sheet>
  )
}

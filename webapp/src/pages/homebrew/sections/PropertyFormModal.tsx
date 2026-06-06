import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import FilterChip from '@/components/ui/FilterChip'
import type { Property, PropertyType } from '@/lib/homebrew/types'

const KEY_REGEX = /^[a-z][a-z0-9_]{0,59}$/

const PROPERTY_TYPES: readonly PropertyType[] = ['enum', 'number', 'boolean', 'text']

/**
 * Auto-derive a snake_case DSL key from a free-form label.
 * - NFD-normalises and strips combining diacritics so "à" -> "a".
 * - Drops everything that isn't an ASCII letter, digit, underscore or space.
 * - Collapses runs of whitespace into a single "_".
 * - Trims any leading non-letter so the regex `^[a-z][a-z0-9_]{0,59}$` holds.
 * - Truncates to 60 chars (backend max length).
 */
function deriveKey(label: string): string {
  return label
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9_\s]/g, '')
    .trim()
    .replace(/\s+/g, '_')
    .replace(/^[^a-z]+/, '')
    .slice(0, 60)
}

/** Default value sentinel for a given type when switching the type radio. */
function defaultForType(type: PropertyType, values: string[]): unknown {
  switch (type) {
    case 'enum':
      return values[0] ?? ''
    case 'number':
      return 0
    case 'boolean':
      return false
    case 'text':
      return ''
  }
}

interface DraftState {
  labelIt: string
  labelEn: string
  key: string
  keyOverridden: boolean
  type: PropertyType
  valuesText: string
  defaultValue: unknown
}

function emptyDraft(): DraftState {
  return {
    labelIt: '',
    labelEn: '',
    key: '',
    keyOverridden: false,
    type: 'enum',
    valuesText: '',
    defaultValue: '',
  }
}

function draftFromProperty(prop: Property): DraftState {
  const values = prop.values ?? []
  return {
    labelIt: prop.label_i18n.it ?? '',
    labelEn: prop.label_i18n.en ?? '',
    key: prop.key,
    keyOverridden: true,
    type: prop.type,
    valuesText: values.join(', '),
    defaultValue: prop.default,
  }
}

function parseValues(text: string): string[] {
  // Accept either commas or newlines as separators, trim, drop empties.
  return text
    .split(/[\n,]+/)
    .map((v) => v.trim())
    .filter((v) => v.length > 0)
}

interface PropertyFormModalProps {
  open: boolean
  onClose: () => void
  initial: Property | null
  onSave: (next: Property) => void
}

/**
 * Sheet-hosted form to create or edit a Property.
 * `initial` controls add (null) vs edit (object) mode. The draft state is
 * fully reset whenever `open` flips to true so leftover state from a
 * previously-cancelled edit cannot leak into a new "add" session.
 */
export default function PropertyFormModal({
  open,
  onClose,
  initial,
  onSave,
}: PropertyFormModalProps) {
  const { t } = useTranslation()
  const [draft, setDraft] = useState<DraftState>(() =>
    initial ? draftFromProperty(initial) : emptyDraft(),
  )
  const [errors, setErrors] = useState<{
    labels?: string
    key?: string
    values?: string
    default?: string
  }>({})

  // Re-seed when the modal opens with new initial data.
  useEffect(() => {
    if (open) {
      setDraft(initial ? draftFromProperty(initial) : emptyDraft())
      setErrors({})
    }
  }, [open, initial])

  const autoKey = useMemo(() => deriveKey(draft.labelIt), [draft.labelIt])
  const effectiveKey = draft.keyOverridden ? draft.key : autoKey

  const parsedValues = useMemo(() => parseValues(draft.valuesText), [draft.valuesText])

  const setLabelIt = (v: string) => {
    setDraft((d) => ({ ...d, labelIt: v }))
    if (errors.labels) setErrors((e) => ({ ...e, labels: undefined }))
  }
  const setLabelEn = (v: string) => {
    setDraft((d) => ({ ...d, labelEn: v }))
    if (errors.labels) setErrors((e) => ({ ...e, labels: undefined }))
  }

  const setType = (next: PropertyType) => {
    setDraft((d) => {
      // Reset default and clear values for non-enum since they are
      // semantically meaningless outside the enum branch.
      const values = next === 'enum' ? parseValues(d.valuesText) : []
      return {
        ...d,
        type: next,
        defaultValue: defaultForType(next, values),
      }
    })
    setErrors({})
  }

  const setValuesText = (v: string) => {
    setDraft((d) => {
      const newParsed = parseValues(v)
      // If the existing default isn't in the new list, reset to first or empty.
      const stillValid =
        typeof d.defaultValue === 'string' && newParsed.includes(d.defaultValue)
      return {
        ...d,
        valuesText: v,
        defaultValue: stillValid ? d.defaultValue : (newParsed[0] ?? ''),
      }
    })
    if (errors.values || errors.default) {
      setErrors((e) => ({ ...e, values: undefined, default: undefined }))
    }
  }

  const setDefaultValue = (v: unknown) => {
    setDraft((d) => ({ ...d, defaultValue: v }))
    if (errors.default) setErrors((e) => ({ ...e, default: undefined }))
  }

  const setKeyOverride = (raw: string) => {
    // Sanitize the user input lightly — drop disallowed chars on the fly.
    const cleaned = raw.toLowerCase().replace(/[^a-z0-9_]/g, '').slice(0, 60)
    setDraft((d) => ({ ...d, key: cleaned, keyOverridden: true }))
    if (errors.key) setErrors((e) => ({ ...e, key: undefined }))
  }

  const enableKeyOverride = () => {
    setDraft((d) => ({ ...d, key: autoKey, keyOverridden: true }))
  }

  const handleSave = () => {
    const nextErrors: typeof errors = {}

    if (!draft.labelIt.trim() || !draft.labelEn.trim()) {
      nextErrors.labels = t('homebrew.properties.modal.label_required')
    }

    if (!KEY_REGEX.test(effectiveKey)) {
      nextErrors.key = t('homebrew.properties.modal.key_invalid')
    }

    let resolvedDefault = draft.defaultValue

    if (draft.type === 'enum') {
      if (parsedValues.length === 0) {
        nextErrors.values = t('homebrew.properties.modal.values_empty')
      } else if (
        typeof resolvedDefault !== 'string' ||
        !parsedValues.includes(resolvedDefault)
      ) {
        nextErrors.default = t('homebrew.properties.modal.default_required')
      }
    } else if (draft.type === 'number') {
      const num = Number(resolvedDefault)
      resolvedDefault = Number.isFinite(num) ? num : 0
    }

    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      return
    }

    const next: Property = {
      key: effectiveKey,
      type: draft.type,
      default: resolvedDefault,
      label_i18n: {
        it: draft.labelIt.trim(),
        en: draft.labelEn.trim(),
      },
    }
    if (draft.type === 'enum') {
      next.values = parsedValues
    }
    onSave(next)
  }

  const title = initial
    ? t('homebrew.properties.modal.title_edit')
    : t('homebrew.properties.modal.title_new')

  return (
    <Sheet open={open} onClose={onClose} title={title} centered>
      <div className="p-5 space-y-4">
        <Input
          label={t('homebrew.properties.modal.label_it')}
          value={draft.labelIt}
          onChange={setLabelIt}
          placeholder={t('homebrew.properties.modal.label_it_placeholder')}
          error={errors.labels && !draft.labelIt.trim() ? errors.labels : undefined}
        />
        <Input
          label={t('homebrew.properties.modal.label_en')}
          value={draft.labelEn}
          onChange={setLabelEn}
          placeholder={t('homebrew.properties.modal.label_en_placeholder')}
          error={errors.labels && !draft.labelEn.trim() ? errors.labels : undefined}
        />

        {/* Key — auto-derived with optional override */}
        <div>
          <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
            {t('homebrew.properties.modal.key_label')}
          </label>
          {draft.keyOverridden ? (
            <Input
              value={draft.key}
              onChange={setKeyOverride}
              placeholder="my_key"
              error={errors.key}
            />
          ) : (
            <div className="flex items-center justify-between gap-2 px-3 py-2 rounded-lg bg-dnd-surface border border-dnd-border">
              <code className="font-mono text-sm text-dnd-text">
                {autoKey || '—'}
              </code>
              <button
                type="button"
                onClick={enableKeyOverride}
                className="text-[11px] font-cinzel uppercase tracking-wider text-dnd-gold-dim hover:text-dnd-gold-bright transition-colors"
              >
                {t('homebrew.properties.modal.key_override')}
              </button>
            </div>
          )}
          {!draft.keyOverridden && errors.key && (
            <p className="text-[var(--dnd-crimson-bright)] text-[11px] mt-1 font-body">
              {errors.key}
            </p>
          )}
        </div>

        {/* Type radio (chip row) */}
        <div>
          <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
            {t('homebrew.properties.modal.type_label')}
          </label>
          <div className="flex flex-wrap gap-1.5">
            {PROPERTY_TYPES.map((pt) => (
              <FilterChip
                key={pt}
                label={t(`homebrew.properties.type_badge.${pt}`)}
                selected={draft.type === pt}
                onToggle={() => setType(pt)}
              />
            ))}
          </div>
        </div>

        {/* Per-type editors */}
        {draft.type === 'enum' && (
          <>
            <Input
              variant="textarea"
              rows={3}
              label={t('homebrew.properties.values_label')}
              value={draft.valuesText}
              onChange={setValuesText}
              placeholder={t('homebrew.properties.modal.values_placeholder')}
              error={errors.values}
            />
            <p className="-mt-2 text-[11px] italic text-dnd-text-muted font-body">
              {t('homebrew.properties.modal.values_helper')}
            </p>
            <div>
              <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
                {t('homebrew.properties.default_label')}
              </label>
              <select
                value={typeof draft.defaultValue === 'string' ? draft.defaultValue : ''}
                onChange={(e) => setDefaultValue(e.target.value)}
                disabled={parsedValues.length === 0}
                className="w-full px-3 py-2.5 min-h-[48px] rounded-lg bg-dnd-surface text-dnd-text border-b-2 border-dnd-border outline-none font-body disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {parsedValues.length === 0 ? (
                  <option value="">
                    {t('homebrew.properties.modal.values_empty')}
                  </option>
                ) : (
                  parsedValues.map((v) => (
                    <option key={v} value={v}>
                      {v}
                    </option>
                  ))
                )}
              </select>
              {errors.default && (
                <p className="text-[var(--dnd-crimson-bright)] text-[11px] mt-1 font-body">
                  {errors.default}
                </p>
              )}
            </div>
          </>
        )}

        {draft.type === 'number' && (
          <Input
            label={t('homebrew.properties.default_label')}
            type="number"
            inputMode="numeric"
            value={String(draft.defaultValue ?? 0)}
            onChange={(v) => setDefaultValue(v === '' ? 0 : Number(v))}
            placeholder="0"
          />
        )}

        {draft.type === 'boolean' && (
          <div>
            <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
              {t('homebrew.properties.default_label')}
            </label>
            <div className="flex gap-1.5">
              <FilterChip
                label={t('common.yes')}
                selected={draft.defaultValue === true}
                onToggle={() => setDefaultValue(true)}
              />
              <FilterChip
                label={t('common.no')}
                selected={draft.defaultValue === false}
                onToggle={() => setDefaultValue(false)}
              />
            </div>
          </div>
        )}

        {draft.type === 'text' && (
          <Input
            label={t('homebrew.properties.default_label')}
            value={typeof draft.defaultValue === 'string' ? draft.defaultValue : ''}
            onChange={setDefaultValue}
            placeholder=""
          />
        )}

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

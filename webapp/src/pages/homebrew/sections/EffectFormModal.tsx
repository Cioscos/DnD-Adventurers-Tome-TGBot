import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Plus, Trash2 } from 'lucide-react'
import Sheet from '@/components/ui/Sheet'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import FilterChip from '@/components/ui/FilterChip'
import SwitchToggle from '@/components/ui/SwitchToggle'
import type {
  Effect,
  Filter,
  FilterOp,
  NotifySeverity,
  Table,
} from '@/lib/homebrew/types'

// ---------------------------------------------------------------------------
// Backend mirrors
// ---------------------------------------------------------------------------

const DICE_REGEX = /^(\d+)d(\d+)([+-]\d+)?$/
const VAR_REGEX = /^[a-zA-Z_][a-zA-Z0-9_]{0,59}$/
// Variable reference accepted by the backend `_resolve_amount`
// (api/services/homebrew/actions.py): `$name` or `$vars.name`. The bare form
// without `$` is intentionally rejected — the backend would read it as dice
// notation instead.
const VAR_PATH = /^\$(vars\.)?[A-Za-z_][A-Za-z0-9_]*$/
// Mirrors api/services/homebrew/dsl.py modifier target regex used in
// PassiveModifierFormModal.
const MODIFIER_TARGET_REGEX =
  /^character\.(ac|hit_points_max|speed|skill\.[a-z_]+|saving_throw\.[a-z]+)$/

const FILTER_OPS: readonly FilterOp[] = [
  'eq',
  'neq',
  'lt',
  'lte',
  'gt',
  'gte',
  'in',
  'has_property',
] as const

const SEVERITY_OPTIONS: readonly NotifySeverity[] = [
  'info',
  'warning',
  'error',
  'success',
] as const

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isAmountValid(raw: string, allowMax: boolean): boolean {
  const v = raw.trim()
  if (v === '') return false
  if (allowMax && v === 'max') return true
  if (VAR_PATH.test(v)) return true
  if (DICE_REGEX.test(v)) return true
  const n = Number(v)
  return Number.isFinite(n)
}

function coerceAmount(raw: string, allowMax: boolean): number | string {
  const v = raw.trim()
  if (allowMax && v === 'max') return 'max'
  // Variable references (`$name` / `$vars.name`) pass through verbatim — they
  // must NOT be funneled into Number().
  if (VAR_PATH.test(v)) return v
  if (DICE_REGEX.test(v)) return v
  const n = Number(v)
  return Number.isFinite(n) ? n : v
}

/**
 * Normalize a free-text condition name into the canonical `custom:<slug>` key
 * the backend writes into `char.conditions` and the Conditions page filters on
 * (`key.startsWith('custom:')`). Strips accents, lowercases, collapses any
 * run of non-alphanumerics into a single `-`, and trims leading/trailing `-`.
 * A `custom:` prefix already typed by the user is honored (no double prefix).
 * Returns `''` when the name slugs to nothing (caller treats as invalid).
 */
function conditionKey(rawName: string): string {
  let name = rawName.trim()
  if (name.toLowerCase().startsWith('custom:')) {
    name = name.slice('custom:'.length)
  }
  const slug = name
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return slug ? `custom:${slug}` : ''
}

/**
 * Strip the `custom:` prefix from a stored key so the editable name field
 * shows the friendly slug (e.g. `custom:veleno` -> `veleno`).
 */
function conditionDisplayName(key: string): string {
  return key.startsWith('custom:') ? key.slice('custom:'.length) : key
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface EffectFormModalProps {
  open: boolean
  onClose: () => void
  /** `null` while the picker is open; non-null once a type has been chosen. */
  effect: Effect | null
  /** True when adding a brand-new step (drives the modal title). */
  isNew?: boolean
  tables?: Table[]
  onSave: (effect: Effect) => void
}

/**
 * Per-action editor modal for a single Effect within an EffectChainEditor.
 *
 * The component is uncontrolled: when `open` flips to true, a local draft is
 * seeded from `effect`. The user's edits stay inside the modal until they
 * press Save, at which point `onSave` is called with the new Effect and the
 * parent advances. Nested branches (`if.then` / `if.else` / `match.cases`)
 * are NOT edited here — they are handled by sub-instances of EffectChainEditor.
 */
export default function EffectFormModal({
  open,
  onClose,
  effect,
  isNew = false,
  tables,
  onSave,
}: EffectFormModalProps) {
  const { t } = useTranslation()
  const [draft, setDraft] = useState<Effect | null>(effect)
  const [errors, setErrors] = useState<Record<string, string>>({})

  // Seed local state every time the modal re-opens with a different effect.
  useEffect(() => {
    if (open) {
      setDraft(effect)
      setErrors({})
    }
  }, [open, effect])

  const title = useMemo(() => {
    if (isNew) return t('homebrew.effects.modal_title_new')
    return t('homebrew.effects.modal_title_edit')
  }, [isNew, t])

  if (!draft) {
    return <Sheet open={open} onClose={onClose} title={title} centered><div /></Sheet>
  }

  const update = <T extends Effect>(patch: Partial<T>) => {
    setDraft((d) => (d ? ({ ...d, ...patch } as Effect) : d))
  }

  const validate = (e: Effect): Record<string, string> => {
    const errs: Record<string, string> = {}
    switch (e.action) {
      case 'roll_dice':
        if (!DICE_REGEX.test(e.notation.trim())) {
          errs.notation = t('homebrew.effects.fields.notation_invalid')
        }
        if (!VAR_REGEX.test(e.store_as.trim())) {
          errs.store_as = t('homebrew.effects.fields.store_as_invalid')
        }
        break
      case 'lookup_table':
        if (!e.table.trim()) errs.table = t('homebrew.effects.fields.table_required')
        if (!e.row.trim()) errs.row = t('homebrew.effects.fields.required')
        if (!e.col.trim()) errs.col = t('homebrew.effects.fields.required')
        if (!VAR_REGEX.test(e.store_as.trim())) {
          errs.store_as = t('homebrew.effects.fields.store_as_invalid')
        }
        break
      case 'match':
        if (!e.value.trim()) errs.value = t('homebrew.effects.fields.required')
        break
      case 'if':
        if (!e.cond.path.trim()) errs.cond_path = t('homebrew.effects.fields.required')
        break
      case 'set_property':
        if (!e.key.trim()) errs.key = t('homebrew.effects.fields.required')
        break
      case 'inc_property':
        if (!e.key.trim()) errs.key = t('homebrew.effects.fields.required')
        if (!isAmountValid(String(e.delta), false)) {
          errs.delta = t('homebrew.effects.fields.amount_invalid')
        }
        break
      case 'damage_character':
      case 'heal_character':
        if (!isAmountValid(String(e.amount), false)) {
          errs.amount = t('homebrew.effects.fields.amount_invalid')
        }
        break
      case 'change_resource':
        if (!e.key.trim()) errs.key = t('homebrew.effects.fields.required')
        if (!isAmountValid(String(e.delta), false)) {
          errs.delta = t('homebrew.effects.fields.amount_invalid')
        }
        break
      case 'restore_resource':
        if (!e.key.trim()) errs.key = t('homebrew.effects.fields.required')
        if (!isAmountValid(String(e.amount), true)) {
          errs.amount = t('homebrew.effects.fields.amount_invalid')
        }
        break
      case 'apply_condition':
      case 'remove_condition':
        // `e.key` is already normalized to `custom:<slug>` on input; an empty
        // result means the name slugged to nothing.
        if (!conditionKey(e.key)) errs.key = t('homebrew.effects.fields.required')
        break
      case 'apply_modifier_once':
        if (!MODIFIER_TARGET_REGEX.test(e.target.trim())) {
          errs.modifier_target = t('homebrew.effects.fields.modifier_target_invalid')
        }
        if (!isAmountValid(String(e.delta), false)) {
          errs.delta = t('homebrew.effects.fields.amount_invalid')
        }
        if (!e.label.trim()) errs.label = t('homebrew.effects.fields.required')
        break
      case 'notify':
        if (!e.message.trim()) errs.message = t('homebrew.effects.fields.required')
        break
      case 'add_history':
        if (!e.description.trim()) errs.description = t('homebrew.effects.fields.required')
        break
    }
    return errs
  }

  const handleSave = () => {
    if (!draft) return
    const errs = validate(draft)
    if (Object.keys(errs).length > 0) {
      setErrors(errs)
      return
    }
    onSave(draft)
  }

  return (
    <Sheet open={open} onClose={onClose} title={title} centered>
      <div className="p-5 space-y-4">
        <EffectFormBody
          draft={draft}
          update={update}
          tables={tables}
          errors={errors}
        />

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

// ---------------------------------------------------------------------------
// Per-action form body
// ---------------------------------------------------------------------------

interface BodyProps {
  draft: Effect
  update: <T extends Effect>(patch: Partial<T>) => void
  tables?: Table[]
  errors: Record<string, string>
}

function EffectFormBody({ draft, update, tables, errors }: BodyProps) {
  const { t } = useTranslation()

  switch (draft.action) {
    case 'roll_dice':
      return (
        <>
          <Input
            label={t('homebrew.effects.fields.notation')}
            value={draft.notation}
            onChange={(v) => update<typeof draft>({ notation: v })}
            placeholder="1d6"
            error={errors.notation}
          />
          <Input
            label={t('homebrew.effects.fields.store_as')}
            value={draft.store_as}
            onChange={(v) => update<typeof draft>({ store_as: v })}
            placeholder="result"
            error={errors.store_as}
          />
        </>
      )

    case 'lookup_table': {
      const tableIds = tables ?? []
      return (
        <>
          <div>
            <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
              {t('homebrew.effects.fields.table')}
            </label>
            <select
              value={draft.table}
              onChange={(e) => update<typeof draft>({ table: e.target.value })}
              className="w-full px-3 py-2.5 min-h-[48px] rounded-lg bg-dnd-surface text-dnd-text border-b-2 border-dnd-border outline-none font-body"
            >
              <option value="">—</option>
              {tableIds.map((tb) => (
                <option key={tb.id} value={tb.id}>{tb.id}</option>
              ))}
            </select>
            {errors.table && (
              <p className="text-dnd-crimson-bright text-[11px] mt-1 font-body">
                {errors.table}
              </p>
            )}
          </div>
          <Input
            label={t('homebrew.effects.fields.row')}
            value={draft.row}
            onChange={(v) => update<typeof draft>({ row: v })}
            placeholder="$qualita"
            error={errors.row}
          />
          <Input
            label={t('homebrew.effects.fields.col')}
            value={draft.col}
            onChange={(v) => update<typeof draft>({ col: v })}
            placeholder="$damage_total"
            error={errors.col}
          />
          <Input
            label={t('homebrew.effects.fields.store_as')}
            value={draft.store_as}
            onChange={(v) => update<typeof draft>({ store_as: v })}
            placeholder="mapped"
            error={errors.store_as}
          />
        </>
      )
    }

    case 'match':
      return (
        <>
          <Input
            label={t('homebrew.effects.fields.match_value')}
            value={draft.value}
            onChange={(v) => update<typeof draft>({ value: v })}
            placeholder="$result"
            error={errors.value}
          />
          <CasesEditor
            cases={draft.cases}
            onChange={(cases) => update<typeof draft>({ cases })}
          />
        </>
      )

    case 'if':
      return <FilterEditor
        cond={draft.cond}
        onChange={(cond) => update<typeof draft>({ cond })}
        pathError={errors.cond_path}
      />

    case 'set_property':
      return (
        <>
          <TargetRadio
            value={draft.target}
            onChange={(target) => update<typeof draft>({ target })}
          />
          <Input
            label={t('homebrew.effects.fields.property_key')}
            value={draft.key}
            onChange={(v) => update<typeof draft>({ key: v })}
            placeholder="quality"
            error={errors.key}
          />
          <Input
            label={t('homebrew.effects.fields.set_value')}
            value={String(draft.value ?? '')}
            onChange={(v) => update<typeof draft>({ value: v })}
            placeholder="normale"
          />
        </>
      )

    case 'inc_property':
      return (
        <>
          <TargetRadio
            value={draft.target}
            onChange={(target) => update<typeof draft>({ target })}
          />
          <Input
            label={t('homebrew.effects.fields.property_key')}
            value={draft.key}
            onChange={(v) => update<typeof draft>({ key: v })}
            placeholder="quality"
            error={errors.key}
          />
          <Input
            label={t('homebrew.effects.fields.delta')}
            value={String(draft.delta)}
            onChange={(v) => update<typeof draft>({ delta: coerceAmount(v, false) })}
            placeholder="1 oppure 1d4"
            error={errors.delta}
          />
        </>
      )

    case 'unequip':
      return (
        <p className="px-2 py-4 text-center text-sm font-body italic text-dnd-text-muted">
          {/* No editable fields; target is always 'subject'. */}
          —
        </p>
      )

    case 'damage_character':
      return (
        <>
          <Input
            label={t('homebrew.effects.fields.amount_simple')}
            value={String(draft.amount)}
            onChange={(v) => update<typeof draft>({ amount: coerceAmount(v, false) })}
            placeholder="1d4"
            error={errors.amount}
          />
          <Input
            label={t('homebrew.effects.fields.damage_type')}
            value={draft.type ?? ''}
            onChange={(v) => update<typeof draft>({ type: v || undefined })}
            placeholder={t('homebrew.effects.fields.damage_type_placeholder')}
          />
          <div className="flex items-center justify-between gap-2 min-h-[44px]">
            <span className="text-sm font-body text-dnd-text">
              {t('homebrew.effects.fields.was_critical')}
            </span>
            <SwitchToggle
              checked={!!draft.was_critical}
              onChange={(checked) => update<typeof draft>({ was_critical: checked || undefined })}
            />
          </div>
        </>
      )

    case 'heal_character':
      return (
        <Input
          label={t('homebrew.effects.fields.amount_simple')}
          value={String(draft.amount)}
          onChange={(v) => update<typeof draft>({ amount: coerceAmount(v, false) })}
          placeholder="1d4"
          error={errors.amount}
        />
      )

    case 'change_resource':
      return (
        <>
          <Input
            label={t('homebrew.effects.fields.resource_key')}
            value={draft.key}
            onChange={(v) => update<typeof draft>({ key: v })}
            placeholder="luck_points"
            error={errors.key}
          />
          <Input
            label={t('homebrew.effects.fields.delta')}
            value={String(draft.delta)}
            onChange={(v) => update<typeof draft>({ delta: coerceAmount(v, false) })}
            placeholder="-1"
            error={errors.delta}
          />
        </>
      )

    case 'restore_resource':
      return (
        <>
          <Input
            label={t('homebrew.effects.fields.resource_key')}
            value={draft.key}
            onChange={(v) => update<typeof draft>({ key: v })}
            placeholder="luck_points"
            error={errors.key}
          />
          <Input
            label={t('homebrew.effects.fields.amount')}
            value={String(draft.amount)}
            onChange={(v) => update<typeof draft>({ amount: coerceAmount(v, true) })}
            placeholder="max"
            error={errors.amount}
          />
        </>
      )

    case 'apply_condition':
      return (
        <>
          <ConditionNameInput
            value={draft.key}
            onChange={(key) => update<typeof draft>({ key })}
            error={errors.key}
          />
          <ParamsJsonInput
            value={draft.params}
            onChange={(p) => update<typeof draft>({ params: p })}
          />
        </>
      )

    case 'remove_condition':
      return (
        <ConditionNameInput
          value={draft.key}
          onChange={(key) => update<typeof draft>({ key })}
          error={errors.key}
        />
      )

    case 'apply_modifier_once':
      return (
        <>
          <Input
            label={t('homebrew.effects.fields.modifier_target')}
            value={draft.target}
            onChange={(v) => update<typeof draft>({ target: v })}
            placeholder="character.ac"
            error={errors.modifier_target}
          />
          <Input
            label={t('homebrew.effects.fields.delta')}
            value={String(draft.delta)}
            onChange={(v) => update<typeof draft>({ delta: coerceAmount(v, false) })}
            placeholder="1"
            error={errors.delta}
          />
          <Input
            label={t('homebrew.effects.fields.modifier_label')}
            value={draft.label}
            onChange={(v) => update<typeof draft>({ label: v })}
            placeholder="Bonus magico"
            error={errors.label}
          />
        </>
      )

    case 'notify':
      return (
        <>
          <div>
            <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
              {t('homebrew.effects.fields.severity')}
            </label>
            <div className="flex flex-wrap gap-1.5">
              {SEVERITY_OPTIONS.map((sev) => (
                <FilterChip
                  key={sev}
                  label={t(`homebrew.effects.fields.severity_options.${sev}`)}
                  selected={draft.severity === sev}
                  onToggle={() => update<typeof draft>({ severity: sev })}
                />
              ))}
            </div>
          </div>
          <Input
            label={t('homebrew.effects.fields.message')}
            value={draft.message}
            onChange={(v) => update<typeof draft>({ message: v })}
            placeholder="..."
            variant="textarea"
            error={errors.message}
          />
        </>
      )

    case 'add_history':
      return (
        <Input
          label={t('homebrew.effects.fields.description')}
          value={draft.description}
          onChange={(v) => update<typeof draft>({ description: v })}
          placeholder="..."
          variant="textarea"
          error={errors.description}
        />
      )
  }
}

// ---------------------------------------------------------------------------
// Sub-pieces
// ---------------------------------------------------------------------------

function TargetRadio({
  value,
  onChange,
}: {
  value: 'subject' | 'character'
  onChange: (v: 'subject' | 'character') => void
}) {
  const { t } = useTranslation()
  return (
    <div>
      <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
        {t('homebrew.effects.fields.target_subject_or_character')}
      </label>
      <div className="flex flex-wrap gap-1.5">
        <FilterChip
          label={t('homebrew.effects.fields.target_subject')}
          selected={value === 'subject'}
          onToggle={() => onChange('subject')}
        />
        <FilterChip
          label={t('homebrew.effects.fields.target_character')}
          selected={value === 'character'}
          onToggle={() => onChange('character')}
        />
      </div>
    </div>
  )
}

/**
 * Free-text "condition name" field that derives and stores a canonical
 * `custom:<slug>` key. The user types a friendly name (e.g. "Veleno"); the
 * normalized key is written upward via `onChange` and shown read-only as a
 * hint so the player sees exactly what lands in `char.conditions`.
 */
function ConditionNameInput({
  value,
  onChange,
  error,
}: {
  value: string
  onChange: (key: string) => void
  error?: string
}) {
  const { t } = useTranslation()
  // Local text mirrors the friendly name; seeded once from the stored key so
  // intermediate keystrokes (trailing spaces, accents) aren't clobbered by the
  // slugified round-trip.
  const [name, setName] = useState(() => conditionDisplayName(value))
  const derived = conditionKey(name)

  return (
    <div className="space-y-1.5">
      <Input
        label={t('homebrew.effects.fields.condition_name')}
        value={name}
        onChange={(v) => {
          setName(v)
          onChange(conditionKey(v))
        }}
        placeholder={t('homebrew.effects.fields.condition_name_placeholder')}
        error={error}
      />
      {derived && (
        <p className="text-[11px] font-body text-dnd-text-muted">
          {t('homebrew.effects.fields.condition_key_hint')}{' '}
          <span className="font-mono text-dnd-gold-dim">{derived}</span>
        </p>
      )}
    </div>
  )
}

/** Coerce a raw compare-value string to boolean / number / string for the DSL. */
function coerceCompareValue(raw: string): boolean | number | string {
  const trimmed = raw.trim()
  if (trimmed === 'true') return true
  if (trimmed === 'false') return false
  if (trimmed !== '' && Number.isFinite(Number(trimmed))) return Number(trimmed)
  return raw
}

function FilterEditor({
  cond,
  onChange,
  pathError,
}: {
  cond: Filter
  onChange: (next: Filter) => void
  pathError?: string
}) {
  const { t } = useTranslation()
  return (
    <>
      <Input
        label={t('homebrew.effects.fields.cond_path')}
        value={cond.path}
        onChange={(v) => onChange({ ...cond, path: v })}
        placeholder="$event.amount"
        error={pathError}
      />
      <div>
        <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
          {t('homebrew.effects.fields.cond_op')}
        </label>
        <select
          value={cond.op}
          onChange={(e) => onChange({ ...cond, op: e.target.value as FilterOp })}
          className="w-full px-3 py-2.5 min-h-[48px] rounded-lg bg-dnd-surface text-dnd-text border-b-2 border-dnd-border outline-none font-body"
        >
          {FILTER_OPS.map((op) => (
            <option key={op} value={op}>{op}</option>
          ))}
        </select>
      </div>
      <Input
        label={t('homebrew.effects.fields.cond_value')}
        value={String(cond.value ?? '')}
        onChange={(v) => onChange({ ...cond, value: coerceCompareValue(v) })}
        placeholder="..."
      />
    </>
  )
}

function CasesEditor({
  cases,
  onChange,
}: {
  cases: Record<string, Effect[]>
  onChange: (next: Record<string, Effect[]>) => void
}) {
  const { t } = useTranslation()
  const [newKey, setNewKey] = useState('')
  const [error, setError] = useState<string>('')
  const keys = Object.keys(cases)

  const addCase = () => {
    const k = newKey.trim()
    if (!k) {
      setError(t('homebrew.effects.fields.required'))
      return
    }
    if (k in cases) {
      setError(t('homebrew.effects.case_key_duplicate'))
      return
    }
    onChange({ ...cases, [k]: [] })
    setNewKey('')
    setError('')
  }

  const removeCase = (k: string) => {
    const copy = { ...cases }
    delete copy[k]
    onChange(copy)
  }

  return (
    <div>
      <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
        {t('homebrew.effects.fields.case_chip')}
      </label>
      {keys.length === 0 ? (
        <p className="text-xs italic text-dnd-text-muted font-body mb-2">
          {t('homebrew.effects.fields.no_cases_yet')}
        </p>
      ) : (
        <ul className="space-y-1 mb-2">
          {keys.map((k) => (
            <li
              key={k}
              className="flex items-center gap-2 px-2 py-1.5 bg-dnd-surface rounded-lg"
            >
              <span className="flex-1 font-mono text-xs text-dnd-text truncate">"{k}"</span>
              <button
                type="button"
                onClick={() => removeCase(k)}
                className="w-11 h-11 inline-flex items-center justify-center rounded-lg text-dnd-crimson hover:text-dnd-crimson-bright hover:bg-dnd-crimson/10"
                aria-label={t('common.delete')}
              >
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex gap-2 items-start">
        <div className="flex-1">
          <Input
            value={newKey}
            onChange={(v) => { setNewKey(v); if (error) setError('') }}
            placeholder={t('homebrew.effects.case_key_placeholder')}
            error={error || undefined}
          />
        </div>
        <Button
          variant="secondary"
          size="md"
          icon={<Plus size={16} />}
          onClick={addCase}
        >
          {t('homebrew.effects.add_case')}
        </Button>
      </div>
    </div>
  )
}

function ParamsJsonInput({
  value,
  onChange,
}: {
  value: Record<string, unknown> | undefined
  onChange: (next: Record<string, unknown> | undefined) => void
}) {
  const { t } = useTranslation()
  const [raw, setRaw] = useState<string>(() =>
    value ? JSON.stringify(value, null, 2) : '',
  )
  const [localError, setLocalError] = useState<string>('')

  const commit = (v: string) => {
    if (!v.trim()) {
      onChange(undefined)
      setLocalError('')
      return
    }
    try {
      const parsed = JSON.parse(v) as Record<string, unknown>
      if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
        setLocalError(t('homebrew.effects.fields.params_json_invalid'))
        return
      }
      onChange(parsed)
      setLocalError('')
    } catch {
      setLocalError(t('homebrew.effects.fields.params_json_invalid'))
    }
  }

  return (
    <Input
      label={t('homebrew.effects.fields.params_json')}
      value={raw}
      onChange={(v) => { setRaw(v); if (localError) setLocalError('') }}
      onCommit={commit}
      variant="textarea"
      placeholder='{ "stacks": 3 }'
      error={localError || undefined}
    />
  )
}

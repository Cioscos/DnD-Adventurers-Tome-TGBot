import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import ChipSelect from '@/components/ui/ChipSelect'
import type { ResourceDef, RestorationType } from '@/lib/homebrew/types'

const KEY_REGEX = /^[a-z][a-z0-9_]{0,59}$/

const RESTORATION_TYPES: readonly RestorationType[] = [
  'long_rest',
  'short_rest',
  'none',
  'manual',
]

/** Auto-derive a snake_case DSL key from a free-form name (same rules as PropertyFormModal). */
function deriveKey(name: string): string {
  return name
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9_\s]/g, '')
    .trim()
    .replace(/\s+/g, '_')
    .replace(/^[^a-z]+/, '')
    .slice(0, 60)
}

interface DraftState {
  name: string
  key: string
  keyOverridden: boolean
  max: string
  restoration_type: RestorationType
}

function emptyDraft(): DraftState {
  return { name: '', key: '', keyOverridden: false, max: '1', restoration_type: 'long_rest' }
}

function draftFromResource(res: ResourceDef): DraftState {
  return {
    name: res.name,
    key: res.key,
    keyOverridden: true,
    max: String(res.max),
    restoration_type: res.restoration_type,
  }
}

interface ResourceFormModalProps {
  open: boolean
  onClose: () => void
  initial: ResourceDef | null
  onSave: (next: ResourceDef) => void
}

/**
 * Sheet-hosted form to create or edit a ResourceDef (#5 / F3-9).
 * `initial` controls add (null) vs edit mode; the draft is fully re-seeded on
 * open so leftover state from a cancelled edit cannot leak into a new add.
 */
export default function ResourceFormModal({
  open,
  onClose,
  initial,
  onSave,
}: ResourceFormModalProps) {
  const { t } = useTranslation()
  const [draft, setDraft] = useState<DraftState>(() =>
    initial ? draftFromResource(initial) : emptyDraft(),
  )
  const [errors, setErrors] = useState<{ name?: string; key?: string; max?: string }>({})

  useEffect(() => {
    if (open) {
      setDraft(initial ? draftFromResource(initial) : emptyDraft())
      setErrors({})
    }
  }, [open, initial])

  const autoKey = useMemo(() => deriveKey(draft.name), [draft.name])
  const effectiveKey = draft.keyOverridden ? draft.key : autoKey

  const setName = (v: string) => {
    setDraft((d) => ({ ...d, name: v }))
    if (errors.name) setErrors((e) => ({ ...e, name: undefined }))
  }
  const setKeyOverride = (raw: string) => {
    const cleaned = raw.toLowerCase().replace(/[^a-z0-9_]/g, '').slice(0, 60)
    setDraft((d) => ({ ...d, key: cleaned, keyOverridden: true }))
    if (errors.key) setErrors((e) => ({ ...e, key: undefined }))
  }
  const enableKeyOverride = () => {
    setDraft((d) => ({ ...d, key: autoKey, keyOverridden: true }))
  }
  const setMax = (v: string) => {
    setDraft((d) => ({ ...d, max: v }))
    if (errors.max) setErrors((e) => ({ ...e, max: undefined }))
  }

  const handleSave = () => {
    const nextErrors: typeof errors = {}
    if (!draft.name.trim()) nextErrors.name = t('homebrew.resources.modal.name_required')
    if (!KEY_REGEX.test(effectiveKey)) nextErrors.key = t('homebrew.resources.modal.key_invalid')
    const maxNum = Number(draft.max)
    if (!Number.isInteger(maxNum) || maxNum < 0) {
      nextErrors.max = t('homebrew.resources.modal.max_invalid')
    }
    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      return
    }
    onSave({
      key: effectiveKey,
      name: draft.name.trim(),
      max: Number(draft.max),
      restoration_type: draft.restoration_type,
    })
  }

  const title = initial
    ? t('homebrew.resources.modal.title_edit')
    : t('homebrew.resources.modal.title_new')

  return (
    <Sheet open={open} onClose={onClose} title={title} centered>
      <div className="p-5 space-y-4">
        <Input
          label={t('homebrew.resources.modal.name_label')}
          value={draft.name}
          onChange={setName}
          placeholder={t('homebrew.resources.modal.name_placeholder')}
          error={errors.name}
        />

        {/* Key — auto-derived with optional override */}
        <div>
          <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
            {t('homebrew.resources.modal.key_label')}
          </label>
          {draft.keyOverridden ? (
            <Input
              value={draft.key}
              onChange={setKeyOverride}
              placeholder="punti_fortuna"
              error={errors.key}
            />
          ) : (
            <div className="flex items-center justify-between gap-2 px-3 py-2 rounded-lg bg-dnd-surface border border-dnd-border">
              <code className="font-mono text-sm text-dnd-text">{autoKey || '—'}</code>
              <Pressable
                onClick={enableKeyOverride}
                className="hit-44 text-[11px] font-cinzel uppercase tracking-wider text-dnd-gold-dim hover:text-dnd-gold-bright transition-colors"
              >
                {t('homebrew.resources.modal.key_override')}
              </Pressable>
            </div>
          )}
          {!draft.keyOverridden && errors.key && (
            <p className="text-dnd-crimson-bright text-[11px] mt-1 font-body">{errors.key}</p>
          )}
        </div>

        <Input
          label={t('homebrew.resources.modal.max_label')}
          type="number"
          inputMode="numeric"
          value={draft.max}
          onChange={setMax}
          placeholder="1"
          error={errors.max}
        />

        <ChipSelect
          label={t('homebrew.resources.modal.restoration_type_label')}
          columns={2}
          options={RESTORATION_TYPES.map((rt) => ({
            value: rt,
            label: t(`homebrew.resources.modal.restoration_${rt}`),
          }))}
          value={draft.restoration_type}
          onChange={(v) => setDraft((d) => ({ ...d, restoration_type: v as RestorationType }))}
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

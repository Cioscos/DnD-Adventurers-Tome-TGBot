import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Plus, X } from 'lucide-react'
import ChipSelect from '@/components/ui/ChipSelect'
import type { AbilityModifier, AbilityName, AbilityModifierKind } from '@/types'

const ABILITY_ORDER: AbilityName[] = [
  'strength', 'dexterity', 'constitution',
  'intelligence', 'wisdom', 'charisma',
]

const KINDS: AbilityModifierKind[] = ['relative', 'absolute']

interface AbilityModifiersEditorProps {
  modifiers: AbilityModifier[]
  onChange: (next: AbilityModifier[]) => void
}

export default function AbilityModifiersEditor({
  modifiers,
  onChange,
}: AbilityModifiersEditorProps) {
  const { t } = useTranslation()
  // Raw text per row while the user types: a controlled number would force a
  // "0" back into the field as soon as it's cleared (no pre-fill convention —
  // value 0 renders as an empty field with a "0" placeholder).
  const [drafts, setDrafts] = useState<Record<number, string>>({})

  const add = () => {
    onChange([
      ...modifiers,
      { ability: 'strength', kind: 'relative', value: 0 },
    ])
  }

  const update = (index: number, patch: Partial<AbilityModifier>) => {
    onChange(
      modifiers.map((m, i) => (i === index ? { ...m, ...patch } : m))
    )
  }

  const remove = (index: number) => {
    // Drafts are keyed by row index: drop them all so they can't shift onto
    // the wrong row after the removal.
    setDrafts({})
    onChange(modifiers.filter((_, i) => i !== index))
  }

  const displayValue = (index: number, value: number) =>
    drafts[index] ?? (value === 0 ? '' : String(value))

  const changeValue = (index: number, raw: string) => {
    setDrafts((d) => ({ ...d, [index]: raw }))
    const parsed = parseInt(raw, 10)
    update(index, { value: Number.isNaN(parsed) ? 0 : parsed })
  }

  const commitValue = (index: number) => {
    // On blur fall back to the canonical number (normalizes "05" → "5").
    setDrafts((d) => {
      const next = { ...d }
      delete next[index]
      return next
    })
  }

  return (
    <div className="space-y-2">
      <p className="font-cinzel text-xs uppercase tracking-widest text-dnd-gold-dim">
        {t('character.inventory.item.modifiers.title')}
      </p>
      {modifiers.length === 0 && (
        <p className="text-xs italic text-dnd-text-faint">
          {t('character.inventory.item.modifiers.empty')}
        </p>
      )}
      {modifiers.map((m, i) => (
        <div key={i} className="rounded-xl border border-dnd-border p-3 space-y-2.5">
          <ChipSelect
            label={t('character.inventory.item.modifiers.ability')}
            options={ABILITY_ORDER.map((ab) => ({
              value: ab,
              label: t(`character.ability.${ab}_short`),
            }))}
            value={m.ability}
            onChange={(v) => update(i, { ability: v as AbilityName })}
            columns={3}
          />
          <div className="flex items-end gap-2">
            <ChipSelect
              className="shrink-0"
              label={t('character.inventory.item.modifiers.kind_label')}
              options={KINDS.map((k) => ({
                value: k,
                label: t(`character.inventory.item.modifiers.kind.${k}`),
              }))}
              value={m.kind}
              onChange={(v) => update(i, { kind: v as AbilityModifierKind })}
            />
            <input
              type="number"
              value={displayValue(i, m.value)}
              onChange={(e) => changeValue(i, e.target.value)}
              onBlur={() => commitValue(i)}
              placeholder="0"
              className="flex-1 min-w-0 min-h-[44px] bg-dnd-surface border border-dnd-border rounded-md px-2 py-1 text-sm text-center font-mono placeholder:text-dnd-text-faint"
              aria-label={t('character.inventory.item.modifiers.value')}
            />
            <button
              type="button"
              onClick={() => remove(i)}
              className="shrink-0 min-h-[44px] min-w-[44px] flex items-center justify-center text-dnd-text-muted hover:text-[var(--dnd-crimson-bright)] transition-colors"
              aria-label={t('character.inventory.item.modifiers.remove')}
            >
              <X size={16} />
            </button>
          </div>
        </div>
      ))}
      <button
        type="button"
        onClick={add}
        className="inline-flex items-center gap-1 text-xs text-dnd-gold-bright hover:text-dnd-gold transition-colors px-2 py-1"
      >
        <Plus size={14} />
        {t('character.inventory.item.modifiers.add')}
      </button>
    </div>
  )
}

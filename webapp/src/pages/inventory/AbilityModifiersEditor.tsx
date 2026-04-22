import { useTranslation } from 'react-i18next'
import { Plus, X } from 'lucide-react'
import type { AbilityModifier, AbilityName, AbilityModifierKind } from '@/types'

const ABILITY_ORDER: AbilityName[] = [
  'strength', 'dexterity', 'constitution',
  'intelligence', 'wisdom', 'charisma',
]

interface AbilityModifiersEditorProps {
  modifiers: AbilityModifier[]
  onChange: (next: AbilityModifier[]) => void
}

export default function AbilityModifiersEditor({
  modifiers,
  onChange,
}: AbilityModifiersEditorProps) {
  const { t } = useTranslation()

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
    onChange(modifiers.filter((_, i) => i !== index))
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
        <div key={i} className="flex items-center gap-2">
          <select
            value={m.ability}
            onChange={(e) => update(i, { ability: e.target.value as AbilityName })}
            className="flex-1 bg-dnd-surface border border-dnd-border rounded-md px-2 py-1 text-sm"
            aria-label={t('character.inventory.item.modifiers.ability')}
          >
            {ABILITY_ORDER.map((ab) => (
              <option key={ab} value={ab}>
                {t(`character.ability.${ab}_short`)}
              </option>
            ))}
          </select>
          <select
            value={m.kind}
            onChange={(e) => update(i, { kind: e.target.value as AbilityModifierKind })}
            className="bg-dnd-surface border border-dnd-border rounded-md px-2 py-1 text-sm"
            aria-label={t('character.inventory.item.modifiers.kind_label')}
          >
            <option value="relative">{t('character.inventory.item.modifiers.kind.relative')}</option>
            <option value="absolute">{t('character.inventory.item.modifiers.kind.absolute')}</option>
          </select>
          <input
            type="number"
            value={m.value}
            onChange={(e) => update(i, { value: parseInt(e.target.value, 10) || 0 })}
            className="w-20 bg-dnd-surface border border-dnd-border rounded-md px-2 py-1 text-sm text-center font-mono"
            aria-label={t('character.inventory.item.modifiers.value')}
          />
          <button
            type="button"
            onClick={() => remove(i)}
            className="text-dnd-text-muted hover:text-[var(--dnd-crimson-bright)] transition-colors p-1"
            aria-label={t('character.inventory.item.modifiers.remove')}
          >
            <X size={16} />
          </button>
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

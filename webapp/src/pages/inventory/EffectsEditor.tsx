import { useTranslation } from 'react-i18next'
import { Plus, X } from 'lucide-react'
import ChipSelect from '@/components/ui/ChipSelect'
import SelectSheet from '@/components/ui/SelectSheet'
import {
  EFFECT_KINDS,
  CONDITION_SLUGS,
  type EffectKind,
  type ItemEffect,
} from './itemMetadata'

interface EffectsEditorProps {
  effects: ItemEffect[]
  onChange: (next: ItemEffect[]) => void
}

function defaultEffect(kind: EffectKind): ItemEffect {
  if (kind === 'heal') return { kind: 'heal', amount: '2d4+2' }
  return { kind, condition: 'poisoned' }
}

export default function EffectsEditor({ effects, onChange }: EffectsEditorProps) {
  const { t } = useTranslation()

  const add = () => onChange([...effects, defaultEffect('heal')])
  const update = (i: number, next: ItemEffect) =>
    onChange(effects.map((e, idx) => (idx === i ? next : e)))
  const remove = (i: number) => onChange(effects.filter((_, idx) => idx !== i))

  const changeKind = (i: number, kind: EffectKind) => update(i, defaultEffect(kind))

  const conditionOptions = CONDITION_SLUGS.map((c) => ({
    value: c,
    label: t(`character.conditions.${c}`, { defaultValue: c }),
  }))

  return (
    <div className="space-y-2">
      <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
        {t('character.inventory.effects.title')}
      </label>
      {effects.length === 0 && (
        <p className="text-xs italic text-dnd-text-faint">
          {t('character.inventory.effects.empty')}
        </p>
      )}
      {effects.map((e, i) => (
        <div key={i} className="rounded-xl border border-dnd-border p-3 space-y-2.5">
          <div className="flex items-start gap-2">
            <ChipSelect
              className="flex-1 min-w-0"
              label={t('character.inventory.effects.kind_label')}
              options={EFFECT_KINDS.map((k) => ({
                value: k,
                label: t(`character.inventory.effects.kinds.${k}`),
              }))}
              value={e.kind}
              onChange={(v) => changeKind(i, v as EffectKind)}
            />
            <button
              type="button"
              onClick={() => remove(i)}
              className="shrink-0 min-h-[44px] min-w-[44px] flex items-center justify-center text-dnd-text-muted hover:text-[var(--dnd-crimson-bright)] transition-colors"
              aria-label={t('common.remove', { defaultValue: 'Rimuovi' })}
            >
              <X size={16} />
            </button>
          </div>

          {e.kind === 'heal' ? (
            <input
              type="text"
              value={e.amount}
              onChange={(ev) => update(i, { kind: 'heal', amount: ev.target.value })}
              placeholder="2d4+2"
              className="w-28 min-h-[44px] bg-dnd-surface border border-dnd-border rounded-md px-2 py-1 text-sm text-center font-mono"
              aria-label={t('character.inventory.effects.amount_label')}
            />
          ) : (
            <SelectSheet
              label={t('character.inventory.effects.condition_label')}
              options={conditionOptions}
              value={e.condition}
              onChange={(v) => update(i, { kind: e.kind, condition: v })}
              placeholder={t('common.select')}
            />
          )}
        </div>
      ))}
      <button
        type="button"
        onClick={add}
        className="inline-flex items-center gap-1 text-xs text-dnd-gold-bright hover:text-dnd-gold transition-colors px-2 py-1"
      >
        <Plus size={14} />
        {t('character.inventory.effects.add')}
      </button>
    </div>
  )
}

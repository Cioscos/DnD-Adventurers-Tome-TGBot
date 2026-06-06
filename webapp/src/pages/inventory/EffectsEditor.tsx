import { useTranslation } from 'react-i18next'
import { Plus, X } from 'lucide-react'
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

const FIELD_CLS =
  'bg-dnd-surface border border-dnd-border rounded-md px-2 py-1 text-sm'

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
        <div key={i} className="flex items-center gap-2">
          <select
            value={e.kind}
            onChange={(ev) => changeKind(i, ev.target.value as EffectKind)}
            className={`${FIELD_CLS} flex-1`}
            aria-label={t('character.inventory.effects.kind_label')}
          >
            {EFFECT_KINDS.map((k) => (
              <option key={k} value={k}>{t(`character.inventory.effects.kinds.${k}`)}</option>
            ))}
          </select>

          {e.kind === 'heal' ? (
            <input
              type="text"
              value={e.amount}
              onChange={(ev) => update(i, { kind: 'heal', amount: ev.target.value })}
              placeholder="2d4+2"
              className={`${FIELD_CLS} w-28 text-center font-mono`}
              aria-label={t('character.inventory.effects.amount_label')}
            />
          ) : (
            <select
              value={e.condition}
              onChange={(ev) => update(i, { kind: e.kind, condition: ev.target.value })}
              className={`${FIELD_CLS} flex-1`}
              aria-label={t('character.inventory.effects.condition_label')}
            >
              {CONDITION_SLUGS.map((c) => (
                <option key={c} value={c}>{t(`character.conditions.${c}`, { defaultValue: c })}</option>
              ))}
            </select>
          )}

          <button
            type="button"
            onClick={() => remove(i)}
            className="shrink-0 min-h-[44px] min-w-[44px] -my-2 flex items-center justify-center text-dnd-text-muted hover:text-[var(--dnd-crimson-bright)] transition-colors"
            aria-label={t('common.remove', { defaultValue: 'Rimuovi' })}
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
        {t('character.inventory.effects.add')}
      </button>
    </div>
  )
}

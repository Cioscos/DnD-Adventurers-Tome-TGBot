import { useTranslation } from 'react-i18next'
import Pressable from '@/components/ui/Pressable'
import type { FeatItem } from '@/lib/feats'

const FIELD = 'w-full min-h-[44px] px-3 rounded-xl bg-dnd-surface border border-dnd-border text-sm font-body text-dnd-text'

interface Props {
  items: FeatItem[]
  value: string
  onPick: (key: string) => void
  /** feature_key delle righe già sulla scheda: un talento non ripetibile già preso è spento. */
  taken?: Set<string | null | undefined>
  /** Con un talento che dà +1: la caratteristica scelta e il punteggio attuale (per il massimo). */
  ability?: string
  onAbility?: (ability: string) => void
  score?: (ability: string) => number
}

/** Elenco dei talenti fra cui scegliere, con la caratteristica del +1 sotto il talento scelto. */
export default function FeatChoiceList({ items, value, onPick, taken, ability = '', onAbility, score }: Props) {
  const { t } = useTranslation()
  const picked = items.find((f) => f.key === value)
  const name = (f: FeatItem) => f.name
  const summary = (f: FeatItem) => f.summary
  const isTaken = (f: FeatItem) => !f.repeatable && !!taken?.has(`feat.${f.key}`)

  return (
    <div className="space-y-2">
      {items.map((f) => (
        <Pressable
          key={f.key}
          onClick={() => { onPick(f.key); onAbility?.('') }}
          disabled={isTaken(f) || f.unmet}
          className={`w-full disabled:opacity-40 min-h-[44px] px-3 py-2 rounded-xl border text-left ${
            value === f.key ? 'bg-dnd-gold/15 border-dnd-gold' : 'border-dnd-border'
          }`}
        >
          <span className="block text-sm font-body text-dnd-text">{name(f)}</span>
          <span className="block text-xs font-body text-dnd-text-muted">
            {isTaken(f)
              ? t('character.level_choice.already_taken')
              : f.unmet ? t('character.level_choice.prerequisites_unmet') : summary(f)}
          </span>
        </Pressable>
      ))}
      {picked?.abilities && onAbility && (
        <select
          value={ability}
          onChange={(e) => onAbility(e.target.value)}
          aria-label={t('character.level_choice.pick_ability')}
          className={FIELD}
        >
          <option value="">{t('character.level_choice.pick_ability')}</option>
          {picked.abilities.filter((a) => !score || score(a) < picked.cap).map((a) => (
            <option key={a} value={a}>{t(`common.abilities.${a}`)}</option>
          ))}
        </select>
      )}
    </div>
  )
}

import { Minus, Plus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import IconButton from '@/components/ui/IconButton'
import { classKey } from '@/lib/classProgression'
import type { CharacterFull } from '@/types'

const FEATURE = 'sorcerer.sorcerous_restoration'
const POINTS = 'sorcerer.sorcery_points'

interface Props { char: CharacterFull; value: number; onChange: (next: number) => void }

/** Ripristino Stregonesco (Stregone 2024, 5°) nel foglio del riposo breve: quanti punti stregoneria spesi riprendere, al massimo
 *  metà del livello da stregone. Il server ricontrolla tutto (tetto, punti spesi, un solo uso fra riposi lunghi). */
export default function SorcerousRestorationPicker({ char, value, onChange }: Props) {
  const { t } = useTranslation()
  const ability = (char.abilities ?? []).find((a) => a.feature_key === FEATURE)
  const pool = (char.abilities ?? []).find((a) => a.feature_key === POINTS)
  const level = (char.classes ?? []).filter((c) => classKey(c.class_name) === 'sorcerer').reduce((n, c) => n + c.level, 0)
  const missing = pool ? (pool.max_uses ?? 0) - (pool.uses ?? 0) : 0
  if (!ability || (ability.uses ?? 0) < 1 || missing < 1 || level < 2) return null

  const cap = Math.min(Math.floor(level / 2), missing)
  return (
    <section data-testid="sorcerous-restoration" className="space-y-2 text-left">
      <h3 className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim">{t('character.quick_actions.sorcerous_restoration')}</h3>
      <p className="text-sm font-body text-dnd-text">{t('character.quick_actions.sorcerous_restoration_hint', { max: cap })}</p>
      <div className="flex items-center gap-2">
        <span className="flex-1 text-sm font-body text-dnd-text">{t('character.quick_actions.sorcerous_restoration_points')}</span>
        <span data-testid="sr-minus">
          <IconButton variant="secondary" className="min-h-11 min-w-11" icon={<Minus size={16} />} disabled={value <= 0}
            aria-label={t('character.quick_actions.sorcerous_restoration_less')} onClick={() => onChange(value - 1)} />
        </span>
        <span data-testid="sr-count" className="w-6 text-center font-mono tabular-nums font-bold">{value}</span>
        <span data-testid="sr-plus">
          <IconButton variant="secondary" className="min-h-11 min-w-11" icon={<Plus size={16} />} disabled={value >= cap}
            aria-label={t('character.quick_actions.sorcerous_restoration_more')} onClick={() => onChange(value + 1)} />
        </span>
      </div>
    </section>
  )
}

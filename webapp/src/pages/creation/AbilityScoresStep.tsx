import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Dices, Minus, Plus } from 'lucide-react'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import { useDiceAnimation } from '@/dice/useDiceAnimation'
import {
  ABILITIES, POINT_BUY_BUDGET, STANDARD_ARRAY, arrayScores, assignFromArray, defaultScores, pointBuyCost,
  pointBuyTotal, roll4d6DropLowest, type Ability, type ScoreMode, type Scores,
} from '@/lib/pointBuy'

const ABBR: Record<string, Ability> = {
  str: 'strength', dex: 'dexterity', con: 'constitution', int: 'intelligence', wis: 'wisdom', cha: 'charisma',
}

interface Props {
  mode: ScoreMode
  scores: Scores
  pool: number[]
  bonuses: Record<string, number>
  onChange: (mode: ScoreMode, scores: Scores, pool: number[]) => void
}

export default function AbilityScoresStep({ mode, scores, pool, bonuses, onChange }: Props) {
  const { t } = useTranslation()
  const { playAndCollect } = useDiceAnimation()
  const [rolling, setRolling] = useState(false)
  const bonusOf = (a: Ability) =>
    Object.entries(bonuses).reduce((n, [k, v]) => n + ((ABBR[k] ?? k) === a ? v : 0), 0)

  const setMode = (m: ScoreMode) => {
    if (m === 'array') onChange(m, arrayScores(), STANDARD_ARRAY)
    else onChange(m, defaultScores(m === 'pointbuy' ? 8 : 10), [])
  }

  const roll = async () => {
    setRolling(true)
    try {
      const res = await playAndCollect(Array.from({ length: 6 }, () => ({ kind: 'd6' as const, count: 4 })))
      const rolled = Array.from({ length: 6 }, (_, g) =>
        roll4d6DropLowest(res.filter((r) => r.groupIndex === g).map((r) => r.value)))
      rolled.sort((a, b) => b - a)
      onChange('roll', arrayScores(rolled), rolled)
    } finally {
      setRolling(false)
    }
  }

  const spent = pointBuyTotal(Object.values(scores))
  const step = (a: Ability, d: number) => {
    const v = scores[a] + d
    if (mode === 'pointbuy' ? Number.isNaN(pointBuyCost(v)) : v < 3 || v > 20) return
    onChange(mode, { ...scores, [a]: v }, pool)
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2">
        {(['array', 'pointbuy', 'roll', 'manual'] as ScoreMode[]).map((m) => (
          <Pressable
            key={m}
            onClick={() => setMode(m)}
            className={`min-h-[44px] rounded-xl border text-[13px] font-display font-bold
              ${mode === m ? '!border-dnd-gold shadow-halo-gold text-dnd-gold-bright' : 'border-dnd-border text-dnd-text'}`}
          >
            {t(`character.create.scores_mode_${m}`)}
          </Pressable>
        ))}
      </div>

      {mode === 'pointbuy' && (
        <p className={`text-center font-mono tabular-nums text-sm ${spent > POINT_BUY_BUDGET ? 'text-dnd-crimson-bright' : 'text-dnd-gold-bright'}`}>
          {t('character.create.points_left', { left: POINT_BUY_BUDGET - spent, total: POINT_BUY_BUDGET })}
        </p>
      )}
      {mode === 'roll' && (
        <Button variant="secondary" fullWidth icon={<Dices size={16} />} loading={rolling} onClick={() => void roll()}>
          {t(pool.length ? 'character.create.reroll' : 'character.create.roll_4d6')}
        </Button>
      )}

      <ul className="space-y-2">
        {ABILITIES.map((a) => {
          const bonus = bonusOf(a)
          return (
            <li key={a} className="rounded-xl border border-dnd-border bg-dnd-surface p-2">
              <div className="flex items-center justify-between gap-2">
                <span className="font-display font-bold text-sm text-dnd-text truncate">{t(`common.abilities.${a}`)}</span>
                <span className="font-mono tabular-nums text-dnd-gold-bright shrink-0">
                  {scores[a] + bonus}
                  {bonus !== 0 && <span className="text-xs text-dnd-text-muted"> ({scores[a]}{bonus > 0 ? '+' : ''}{bonus})</span>}
                </span>
              </div>
              {(mode === 'pointbuy' || mode === 'manual') && (
                <div className="flex items-center gap-2 mt-1">
                  <Pressable onClick={() => step(a, -1)} className="min-w-[44px] min-h-[44px] rounded-lg border border-dnd-border flex items-center justify-center" aria-label="-1">
                    <Minus size={16} />
                  </Pressable>
                  <span className="flex-1 text-center font-mono tabular-nums">{scores[a]}</span>
                  <Pressable onClick={() => step(a, 1)} className="min-w-[44px] min-h-[44px] rounded-lg border border-dnd-border flex items-center justify-center" aria-label="+1">
                    <Plus size={16} />
                  </Pressable>
                </div>
              )}
              {(mode === 'array' || mode === 'roll') && (
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {pool.map((v, i) => (
                    <Pressable
                      key={i}
                      onClick={() => onChange(mode, assignFromArray(scores, a, v), pool)}
                      className={`min-w-[44px] min-h-[44px] rounded-lg border font-mono tabular-nums text-sm
                        ${scores[a] === v ? '!border-dnd-gold shadow-halo-gold text-dnd-gold-bright' : 'border-dnd-border text-dnd-text'}`}
                    >
                      {v}
                    </Pressable>
                  ))}
                </div>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

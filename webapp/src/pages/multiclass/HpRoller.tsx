import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import Button from '@/components/ui/Button'
import { useDiceAnimation } from '@/dice/useDiceAnimation'
import type { DiceKind } from '@/dice/types'

const DIE_KINDS: Record<number, DiceKind> = { 4: 'd4', 6: 'd6', 8: 'd8', 10: 'd10', 12: 'd12' }

/** Hit-die rolls for the gained level(s) (3D dice, local fallback). Rendered only in rolled-HP mode. */
export default function HpRoller({ die, count, conMod, rolls, onRoll }: {
  die: number
  count: number
  conMod: number
  rolls: number[] | null
  onRoll: (rolls: number[]) => void
}) {
  const { t } = useTranslation()
  const { playAndCollect } = useDiceAnimation()
  const [rolling, setRolling] = useState(false)
  const run = async () => {
    setRolling(true)
    const local = () => Array.from({ length: count }, () => 1 + Math.floor(Math.random() * die))
    let values = local()
    try {
      const kind = DIE_KINDS[die]
      const res = kind ? await playAndCollect([{ kind, count }]) : []
      if (res.length === count && res.every((r) => r.value >= 1 && r.value <= die)) {
        values = res.map((r) => r.value)
      }
    } catch {
      /* keep the local rolls */
    } finally {
      setRolling(false)
    }
    onRoll(values)
  }
  return (
    <div className="space-y-2 text-center">
      <Button variant="secondary" size="md" className="min-h-11" onClick={run} loading={rolling}>
        {t('character.multiclass.level_up.roll_hp', { die, count })}
      </Button>
      <p className="text-sm font-mono tabular-nums text-dnd-text-muted">
        {rolls === null
          ? t('character.multiclass.level_up.roll_hp_required')
          : t('character.multiclass.level_up.roll_hp_result', {
              roll: rolls.join(', '),
              con: conMod >= 0 ? `+${conMod}` : conMod,
              total: rolls.reduce((n, r) => n + Math.max(1, r + conMod), 0),
            })}
      </p>
    </div>
  )
}

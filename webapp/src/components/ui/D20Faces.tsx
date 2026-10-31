import { useTranslation } from 'react-i18next'
import type { RollMode } from '@/api/client'

/** "d20 (14)" or, with advantage/disadvantage, both faces with the discarded one dimmed. */
export default function D20Faces({ die, dice, mode }: { die: number; dice?: number[]; mode?: RollMode }) {
  const { t } = useTranslation()
  if (!dice || dice.length !== 2) return <>d20 ({die})</>
  const keptIdx = dice.indexOf(die)
  return (
    <>
      {mode === 'disadvantage' ? t('common.roll_mode.disadvantage') : t('common.roll_mode.advantage')} d20 (
      {dice.map((v, i) => (
        <span key={i} className={i === keptIdx ? 'font-bold text-dnd-text' : 'opacity-40 line-through'}>
          {i > 0 && ', '}{v}
        </span>
      ))}
      )
    </>
  )
}

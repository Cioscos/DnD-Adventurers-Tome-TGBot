import { useTranslation } from 'react-i18next'
import { useRollNoteLabels } from '@/hooks/useRollNoteLabels'
import type { OptionResult } from '@/api/client'

type Props = { notes?: string[]; autoFail?: boolean; className?: string; charId?: number; optionResult?: OptionResult }

/** Perché il tiro ha quel modo o quel bonus: condizioni, armatura, privilegi. */
export default function RollNotes({ notes = [], autoFail = false, className = '', charId, optionResult }: Props) {
  const extra = optionResult?.extra_rolls ?? []
  if (notes.length === 0 && !autoFail && extra.length === 0) return null
  return (
    <>
      {(notes.length > 0 || autoFail) && <Line notes={notes} autoFail={autoFail} className={className} charId={charId} />}
      {extra.length > 0 && <ExtraDice rolls={extra} total={optionResult!.extra_total} className={className} />}
    </>
  )
}

function ExtraDice({ rolls, total, className }: { rolls: number[]; total: number; className: string }) {
  const { t } = useTranslation()
  return (
    <span data-testid="roll-option-dice" className={`block text-xs font-mono tabular-nums text-dnd-text-muted ${className}`}>
      {t('character.roll_options.extra_dice')}: [{rolls.join(', ')}] = {total}
    </span>
  )
}

function Line({ notes, autoFail, className, charId }: Required<Omit<Props, 'charId' | 'optionResult'>> & Pick<Props, 'charId'>) {
  const { t } = useTranslation()
  const labels = useRollNoteLabels(charId)
  const parts = [...(autoFail ? [t('character.roll_notes.auto_fail')] : []), ...labels(notes)]
  return (
    <span data-testid="roll-notes" className={`block text-xs font-body text-dnd-amber ${className}`}>
      {parts.join(' · ')}
    </span>
  )
}

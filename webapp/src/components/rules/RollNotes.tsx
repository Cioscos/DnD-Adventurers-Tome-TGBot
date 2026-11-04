import { useTranslation } from 'react-i18next'
import { useRollNoteLabels } from '@/hooks/useRollNoteLabels'

type Props = { notes?: string[]; autoFail?: boolean; className?: string }

/** Perché il tiro ha quel modo o quel bonus: condizioni, armatura, privilegi. */
export default function RollNotes({ notes = [], autoFail = false, className = '' }: Props) {
  if (notes.length === 0 && !autoFail) return null
  return <Line notes={notes} autoFail={autoFail} className={className} />
}

function Line({ notes, autoFail, className }: Required<Props>) {
  const { t } = useTranslation()
  const labels = useRollNoteLabels()
  const parts = [...(autoFail ? [t('character.roll_notes.auto_fail')] : []), ...labels(notes)]
  return (
    <span data-testid="roll-notes" className={`block text-xs font-body text-dnd-amber ${className}`}>
      {parts.join(' · ')}
    </span>
  )
}

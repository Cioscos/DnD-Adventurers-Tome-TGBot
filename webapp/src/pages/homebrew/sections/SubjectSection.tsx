import { useTranslation } from 'react-i18next'
import Surface from '@/components/ui/Surface'
import type { Subject } from '@/lib/homebrew/types'

export interface SubjectSectionProps {
  subject: Subject
  onChange: (subject: Subject) => void
}

/**
 * STUB (Task 4.4). Task 4.6 will replace this with the subject-type picker
 * (item / character / ability) plus the optional filter editor.
 */
export default function SubjectSection(_props: SubjectSectionProps) {
  const { t } = useTranslation()
  return (
    <Surface variant="flat">
      <p className="text-sm font-body italic text-dnd-text-muted">
        {t('homebrew.editor.section_tbd')}
      </p>
    </Surface>
  )
}

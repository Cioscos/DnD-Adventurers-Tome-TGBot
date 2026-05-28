import { useTranslation } from 'react-i18next'
import Surface from '@/components/ui/Surface'

export interface IdentitySectionProps {
  name: string
  description: string
  onChange: (name: string, description: string) => void
}

/**
 * STUB (Task 4.4). Task 4.5 will replace this with the full name + description
 * + icon-picker form. The wrapping <details>/<summary> accordion lives in
 * RuleEditor.tsx — this component renders the inner panel only.
 */
export default function IdentitySection(_props: IdentitySectionProps) {
  const { t } = useTranslation()
  return (
    <Surface variant="flat">
      <p className="text-sm font-body italic text-dnd-text-muted">
        {t('homebrew.editor.section_tbd')}
      </p>
    </Surface>
  )
}

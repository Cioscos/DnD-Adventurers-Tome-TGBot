import { useTranslation } from 'react-i18next'
import Surface from '@/components/ui/Surface'
import type { PassiveModifier } from '@/lib/homebrew/types'

export interface PassiveModifiersSectionProps {
  mods: PassiveModifier[]
  onChange: (mods: PassiveModifier[]) => void
}

/**
 * STUB (Task 4.4). Task 4.9 will replace this with the passive-modifier list
 * editor (when-filter → target → value with i18n label).
 */
export default function PassiveModifiersSection(_props: PassiveModifiersSectionProps) {
  const { t } = useTranslation()
  return (
    <Surface variant="flat">
      <p className="text-sm font-body italic text-dnd-text-muted">
        {t('homebrew.editor.section_tbd')}
      </p>
    </Surface>
  )
}

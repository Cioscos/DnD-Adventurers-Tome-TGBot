import { useTranslation } from 'react-i18next'
import Surface from '@/components/ui/Surface'
import type { Property } from '@/lib/homebrew/types'

export interface PropertiesSectionProps {
  properties: Property[]
  onChange: (properties: Property[]) => void
}

/**
 * STUB (Task 4.4). Task 4.7 will replace this with the property-list editor
 * (add/remove/reorder properties with type-aware value editors).
 */
export default function PropertiesSection(_props: PropertiesSectionProps) {
  const { t } = useTranslation()
  return (
    <Surface variant="flat">
      <p className="text-sm font-body italic text-dnd-text-muted">
        {t('homebrew.editor.section_tbd')}
      </p>
    </Surface>
  )
}

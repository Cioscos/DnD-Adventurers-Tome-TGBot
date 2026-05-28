import { useTranslation } from 'react-i18next'
import Surface from '@/components/ui/Surface'
import type { Table } from '@/lib/homebrew/types'

export interface TablesSectionProps {
  tables: Table[]
  onChange: (tables: Table[]) => void
}

/**
 * STUB (Task 4.4). Task 4.8 will replace this with the (advanced) table-grid
 * editor: row axis × column bins → cell effects.
 */
export default function TablesSection(_props: TablesSectionProps) {
  const { t } = useTranslation()
  return (
    <Surface variant="flat">
      <p className="text-sm font-body italic text-dnd-text-muted">
        {t('homebrew.editor.section_tbd')}
      </p>
    </Surface>
  )
}

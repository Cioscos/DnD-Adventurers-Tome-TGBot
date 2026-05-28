import { useTranslation } from 'react-i18next'
import Surface from '@/components/ui/Surface'
import type { Table, Trigger } from '@/lib/homebrew/types'

export interface TriggersSectionProps {
  triggers: Trigger[] | undefined
  tables: Table[]
  onChange: (triggers: Trigger[]) => void
}

/**
 * STUB (Task 4.4). Task 4.10 will replace this with the trigger list editor
 * (event picker + filters + EffectChainEditor from Task 4.11). `tables` is
 * passed in so the eventual EffectChainEditor can offer lookup_table targets.
 */
export default function TriggersSection(_props: TriggersSectionProps) {
  const { t } = useTranslation()
  return (
    <Surface variant="flat">
      <p className="text-sm font-body italic text-dnd-text-muted">
        {t('homebrew.editor.section_tbd')}
      </p>
    </Surface>
  )
}

import { useTranslation } from 'react-i18next'
import Input from '@/components/ui/Input'

export interface IdentitySectionProps {
  name: string
  description: string
  onChange: (name: string, description: string) => void
}

/**
 * Task 4.5 — identity form. Two controlled inputs (name + description).
 * The wrapping <CollapsiblePanel> lives in RuleEditor.tsx; this component
 * renders only the inner form fields.
 *
 * Spec gap: the plan also asked for an icon picker, but HomebrewRule has no
 * `icon` field in the schema (only TemplateRead does). Omitted intentionally —
 * adding storage for it is out of scope for this task.
 */
export default function IdentitySection({ name, description, onChange }: IdentitySectionProps) {
  const { t } = useTranslation()

  const setName = (v: string) => onChange(v, description)
  const setDescription = (v: string) => onChange(name, v)

  return (
    <div className="space-y-3">
      <Input
        label={t('homebrew.identity.name_label')}
        value={name}
        onChange={setName}
        placeholder={t('homebrew.identity.name_placeholder')}
      />
      <Input
        variant="textarea"
        rows={3}
        label={t('homebrew.identity.description_label')}
        value={description}
        onChange={setDescription}
        placeholder={t('homebrew.identity.description_placeholder')}
      />
    </div>
  )
}

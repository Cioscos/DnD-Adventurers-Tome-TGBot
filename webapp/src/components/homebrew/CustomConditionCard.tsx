import { useTranslation } from 'react-i18next'
import { Sparkles, Trash2 } from 'lucide-react'
import IconButton from '@/components/ui/IconButton'

interface CustomConditionCardProps {
  conditionKey: string
  // The raw value stored under `char.conditions[conditionKey]`. Should always
  // be `{rule_id, params}` for active custom conditions, but we accept unknown
  // and narrow defensively so a malformed entry doesn't crash the page.
  value: { rule_id?: number; params?: Record<string, unknown> } | unknown
  // Resolved by the parent from the homebrew-rules query. May be undefined if
  // the source rule was deleted while the condition flag remained on the char.
  ruleName?: string
  onRemove: () => void
  isPending?: boolean
}

/**
 * Renders a single "custom:<slug>" condition currently flagged on the char.
 * Visual weight: softer crimson surface — lighter than the standard-condition
 * active-state gradient (DESIGN.md "Two Inks": crimson sparingly), since these
 * are attention-secondary alongside the 14 D&D 5e conditions above.
 */
export default function CustomConditionCard({
  conditionKey,
  value,
  ruleName,
  onRemove,
  isPending = false,
}: CustomConditionCardProps) {
  const { t } = useTranslation()

  const ruleId =
    value && typeof value === 'object' && 'rule_id' in value
      ? (value as { rule_id?: number }).rule_id
      : undefined

  const slug = conditionKey.startsWith('custom:')
    ? conditionKey.slice('custom:'.length)
    : conditionKey

  const title =
    ruleName ?? t('character.conditions.custom_fallback', { slug })

  const subtitle =
    ruleId !== undefined
      ? t('character.conditions.custom_subtitle_rule_id', { id: ruleId })
      : null

  return (
    <div
      className="flex items-center gap-3 rounded-xl border border-dnd-crimson/40
                 bg-dnd-crimson/10 px-3 py-2.5 shadow-parchment-md"
    >
      <span className="shrink-0 inline-flex w-9 h-9 items-center justify-center
                       rounded-lg bg-dnd-crimson/20 text-dnd-crimson-bright">
        <Sparkles size={18} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="font-body text-sm font-semibold text-dnd-text truncate">
          {title}
        </div>
        {subtitle && (
          <div className="text-[11px] font-cinzel uppercase tracking-[0.1em]
                          leading-tight text-dnd-text-faint">
            {subtitle}
          </div>
        )}
      </div>
      <IconButton
        icon={<Trash2 size={16} />}
        onClick={onRemove}
        loading={isPending}
        haptic="none"
        aria-label={t('character.conditions.custom_remove_aria', { name: title })}
        className="shrink-0 w-11 h-11 rounded-lg text-dnd-crimson hover:text-dnd-crimson-bright
                   hover:bg-dnd-crimson/15 disabled:opacity-50"
      />
    </div>
  )
}

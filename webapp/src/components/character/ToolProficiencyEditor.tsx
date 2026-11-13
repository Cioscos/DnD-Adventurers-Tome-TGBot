import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Plus, X } from 'lucide-react'
import Sheet from '@/components/ui/Sheet'
import Pressable from '@/components/ui/Pressable'
import IconButton from '@/components/ui/IconButton'
import { LEDGER_LABEL } from '@/styles/ledger'
import { TOOLS, TOOL_CATEGORIES, proficientTools, toolLabel, type ToolLevel } from '@/lib/tools'

/** Competenze negli strumenti scelte dal catalogo (niente testo libero); la Maestria si conserva. */
export default function ToolProficiencyEditor({
  values,
  onChange,
}: {
  values: Record<string, ToolLevel>
  onChange: (next: Record<string, ToolLevel>) => void
}) {
  const { t, i18n } = useTranslation()
  const [picking, setPicking] = useState(false)
  const owned = proficientTools(values)
  const remove = (key: string) => onChange(Object.fromEntries(Object.entries(values).filter(([k]) => k !== key)))

  return (
    <div className="space-y-2">
      <span className={LEDGER_LABEL}>{t('character.identity.proficiencies_tools')}</span>
      {owned.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {owned.map(({ tool, level }) => {
            const name = toolLabel(tool.key, i18n.language)
            return (
              <span key={tool.key}
                    className="inline-flex items-center gap-1 rounded-full border border-dnd-border bg-dnd-surface pl-3 text-sm font-body text-dnd-text">
                {name}
                {level === 'expert' && <span className="text-xs text-dnd-gold-bright">· {t('character.tools.expert')}</span>}
                <IconButton
                  icon={<X size={14} aria-hidden />}
                  aria-label={t('character.tools.remove', { name })}
                  onClick={() => remove(tool.key)}
                  className="text-dnd-text-muted"
                />
              </span>
            )
          })}
        </div>
      )}
      <Pressable
        type="button"
        onClick={() => setPicking(true)}
        className="min-h-[44px] inline-flex items-center gap-2 rounded-xl border border-dashed border-dnd-border px-3 text-sm font-body text-dnd-gold-bright"
      >
        <Plus size={16} aria-hidden />
        {t('character.tools.add')}
      </Pressable>

      <Sheet open={picking} onClose={() => setPicking(false)} title={t('character.tools.picker_title')}>
        <div className="p-5 space-y-4">
          {TOOL_CATEGORIES.map((cat) => {
            const free = TOOLS.filter((x) => x.category === cat && !values[x.key])
            if (free.length === 0) return null
            return (
              <div key={cat}>
                <p className={`mb-2 ${LEDGER_LABEL}`}>{t(`character.tools.category_${cat}`)}</p>
                <div className="flex flex-wrap gap-2">
                  {free.map((x) => (
                    <Pressable
                      key={x.key}
                      type="button"
                      onClick={() => {
                        onChange({ ...values, [x.key]: true })
                        setPicking(false)
                      }}
                      className="min-h-[44px] rounded-xl border border-dnd-border bg-dnd-surface px-3 text-sm font-body text-dnd-text"
                    >
                      {toolLabel(x.key, i18n.language)}
                    </Pressable>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      </Sheet>
    </div>
  )
}

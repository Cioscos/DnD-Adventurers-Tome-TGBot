import { useTranslation } from 'react-i18next'
import { useClassProficiencies } from '@/hooks/useClassProficiencies'
import Pressable from '@/components/ui/Pressable'

interface Props {
  edition: string
  /** Nome o chiave della classe; una classe custom non ha abilità da scegliere. */
  className: string | null
  asMulticlass: boolean
  value: string[]
  onChange: (skills: string[]) => void
}

/** Scelta delle abilità della classe: non mostra nulla se la classe non ne concede. */
export default function ClassSkillChoice({ edition, className, asMulticlass, value, onChange }: Props) {
  const { t } = useTranslation()
  const { data } = useClassProficiencies(edition, className, asMulticlass)
  if (!data || data.skills_count === 0) return null

  const full = value.length >= data.skills_count
  const toggle = (slug: string) =>
    onChange(value.includes(slug) ? value.filter((s) => s !== slug) : full ? value : [...value, slug])

  return (
    <div className="space-y-2">
      <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim">
        {t('character.multiclass.skill_choice_title', { count: data.skills_count })}
      </p>
      <p className="text-xs text-dnd-text-muted font-body tabular-nums">
        {t('character.multiclass.skill_choice_hint', { chosen: value.length, count: data.skills_count })}
      </p>
      <div className="grid grid-cols-2 gap-2">
        {data.skills_from.map((slug) => {
          const on = value.includes(slug)
          return (
            <Pressable
              key={slug}
              onClick={() => toggle(slug)}
              className={`min-h-[44px] px-2 rounded-xl border text-sm font-body text-center transition-colors
                ${on ? '!border-dnd-gold bg-dnd-gold/20 text-dnd-gold-bright' : 'border-dnd-border text-dnd-text'}
                ${!on && full ? 'opacity-50' : ''}`}
            >
              {t(`character.skills.${slug}`, { defaultValue: slug })}
            </Pressable>
          )
        })}
      </div>
    </div>
  )
}

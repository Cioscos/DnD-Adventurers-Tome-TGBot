import { useTranslation } from 'react-i18next'
import { useClassProficiencies } from '@/hooks/useClassProficiencies'
import Pressable from '@/components/ui/Pressable'
import { SKILL_KEYS } from '@/lib/species'

interface Props {
  edition: string
  /** Nome o chiave della classe; una classe custom non ha abilità da scegliere. */
  className: string | null
  asMulticlass: boolean
  value: string[]
  onChange: (skills: string[]) => void
  /** Abilità già date da background e specie: non si possono scegliere per la classe. */
  takenSkills?: string[]
}

/** Scelta delle abilità della classe: non mostra nulla se la classe non ne concede. */
export default function ClassSkillChoice({ edition, className, asMulticlass, value, onChange, takenSkills = [] }: Props) {
  const { t } = useTranslation()
  const { data } = useClassProficiencies(edition, className, asMulticlass)
  if (!data || data.skills_count === 0) return null

  const full = value.length >= data.skills_count
  // 2014 pag. 125: se l'elenco è esaurito dalle abilità già possedute, se ne sceglie un'altra qualsiasi (come il server)
  const exhausted = edition === '2014' && data.skills_from.filter((s) => !takenSkills.includes(s)).length < data.skills_count
  const offered = exhausted ? SKILL_KEYS : data.skills_from
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
        {offered.map((slug) => {
          const on = value.includes(slug)
          return (
            <Pressable
              key={slug}
              disabled={takenSkills.includes(slug)}
              onClick={() => toggle(slug)}
              className={`min-h-[44px] px-2 rounded-xl border text-sm font-body text-center transition-colors
                ${on ? '!border-dnd-gold bg-dnd-gold/20 text-dnd-gold-bright' : 'border-dnd-border text-dnd-text'}
                ${!on && full ? 'opacity-50' : ''} disabled:opacity-40`}
            >
              {t(`character.skills.${slug}`, { defaultValue: slug })}
            </Pressable>
          )
        })}
      </div>
    </div>
  )
}

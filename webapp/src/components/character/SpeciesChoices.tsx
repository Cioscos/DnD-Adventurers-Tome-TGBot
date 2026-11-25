import { useTranslation } from 'react-i18next'
import Pressable from '@/components/ui/Pressable'
import { uiLang } from '@/lib/lang'
import type { Species2024Entry } from '@/lib/species'

interface Props {
  species: Species2024Entry
  value: Record<string, string>
  onChange: (options: Record<string, string>) => void
  /** Abilità già date da altro (classe, background, scheda): non si possono scegliere per la specie. */
  takenSkills?: string[]
  /** Talenti d'Origine già dati dal background e non ripetibili: non sceglibili per Versatile (D-035). */
  takenFeats?: string[]
}

/** Scelte di una specie 2024 (lignaggio, taglia, abilità...): una riga di chip per scelta. */
export default function SpeciesChoices({ species, value, onChange, takenSkills = [], takenFeats = [] }: Props) {
  const { i18n } = useTranslation()
  const lang = uiLang(i18n.language)
  return (
    <div className="space-y-3">
      {species.choices.map((c) => (
        <div key={c.key} role="group" aria-label={c.label[lang]}>
          <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim mb-1.5">{c.label[lang]}</p>
          <div className="flex flex-wrap gap-2">
            {c.options.map((o) => (
              <Pressable
                key={o.key}
                aria-pressed={value[c.key] === o.key}
                disabled={(c.key === 'skill' && takenSkills.includes(o.key)) || (c.key === 'origin_feat' && takenFeats.includes(o.key))}
                onClick={() => onChange({ ...value, [c.key]: o.key })}
                className={`min-h-[44px] px-3 rounded-xl border text-sm font-body font-semibold
                  ${value[c.key] === o.key
                    ? '!border-dnd-gold bg-dnd-gold/20 text-dnd-gold-bright' : 'border-dnd-border text-dnd-text'} disabled:opacity-40`}
              >
                {o.label[lang]}
              </Pressable>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

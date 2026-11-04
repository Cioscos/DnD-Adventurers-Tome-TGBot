import { Check } from 'lucide-react'
import { GiPolarStar as Star } from 'react-icons/gi'

interface Props {
  level: boolean | 'expert'
  /** Mezza competenza (Factotum), mostrata solo senza competenza piena. */
  half?: boolean
}

/** Il pallino di competenza di Abilità e Tiri salvezza: vuoto, spunta, stella. */
export default function ProficiencyMark({ level, half = false }: Props) {
  if (level === 'expert') {
    return (
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-dnd-gold outline outline-1 outline-offset-2 outline-dnd-gold">
        <Star size={11} aria-hidden className="text-dnd-ink" />
      </span>
    )
  }
  if (level) {
    return (
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-dnd-gold">
        <Check size={12} aria-hidden className="text-dnd-ink" strokeWidth={3} />
      </span>
    )
  }
  return (
    <span className="flex h-5 w-5 items-center justify-center rounded-full border-2 border-dnd-border-strong text-xs leading-none text-dnd-gold-dim">
      {half ? '½' : null}
    </span>
  )
}

import type { CharacterFull } from '@/types'

/** In forma selvatica: PF del personaggio in piccolo, sotto quelli della forma. */
export default function CharacterHpSecondary({ char, className = '' }: { char: CharacterFull; className?: string }) {
  const max = char.hit_points + (char.hp_max_homebrew_modifier ?? 0)
  return (
    <p data-testid="character-hp-secondary" className={`text-xs font-body text-dnd-text-muted ${className}`}>
      <span>{char.name}</span>{' · '}
      <span className="font-mono tabular-nums text-dnd-text">{char.current_hit_points}/{max}</span>
      {char.temp_hp > 0 && <span className="ml-1 font-mono tabular-nums text-dnd-cobalt-bright">(+{char.temp_hp})</span>}
    </p>
  )
}

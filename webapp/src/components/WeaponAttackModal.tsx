export type WeaponAttackResult = {
  weapon_name: string
  to_hit_die: number
  to_hit_bonus: number
  to_hit_total: number
  is_critical: boolean
  is_fumble: boolean
  damage_dice: string
  damage_rolls: number[]
  damage_bonus: number
  damage_total: number
}

type Props = {
  result: WeaponAttackResult
  onClose: () => void
}

export default function WeaponAttackModal({ result, onClose }: Props) {
  const {
    weapon_name, to_hit_die, to_hit_bonus, to_hit_total,
    is_critical, is_fumble, damage_dice, damage_rolls, damage_bonus, damage_total,
  } = result

  const bonusStr = (n: number) => n >= 0 ? `+${n}` : `${n}`

  const borderColor = is_critical
    ? 'border-dnd-gold'
    : is_fumble
      ? 'border-dnd-danger'
      : 'border-dnd-success'

  const pulseClass = is_critical
    ? 'animate-pulse-gold'
    : is_fumble
      ? 'animate-pulse-danger'
      : ''

  return (
    <div
      className="fixed inset-0 bg-black/65 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className={`rounded-2xl p-5 w-full max-w-sm space-y-4
                     bg-dnd-surface-elevated border-2 ${borderColor} ${pulseClass}
                     animate-modal-enter`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="text-center">
          <p className="text-sm text-dnd-text-secondary">⚔️ {weapon_name}</p>
          {is_critical && <p className="text-[var(--dnd-gold)] font-bold">✦ CRITICO!</p>}
          {is_fumble && <p className="text-[var(--dnd-danger)] font-bold">💀 FUMBLE!</p>}
        </div>

        <div className="rounded-xl bg-dnd-surface p-3 text-center">
          <p className="text-xs text-dnd-text-secondary mb-1">Per colpire</p>
          <p className="text-sm text-dnd-text-secondary">
            d20 ({to_hit_die}) {bonusStr(to_hit_bonus)}
          </p>
          <p className={`text-3xl font-black ${is_critical ? 'text-[var(--dnd-gold)]' : is_fumble ? 'text-[var(--dnd-danger)]' : 'text-dnd-text'}`}>
            {to_hit_total}
          </p>
        </div>

        {!is_fumble && (
          <div className="rounded-xl bg-dnd-surface p-3 text-center">
            <p className="text-xs text-dnd-text-secondary mb-1">
              Danno{is_critical ? ' (critico)' : ''} — {damage_dice}
            </p>
            <p className="text-sm text-dnd-text-secondary">
              [{damage_rolls.join(', ')}] {bonusStr(damage_bonus)}
            </p>
            <p className="text-3xl font-black text-[var(--dnd-danger)]">{damage_total}</p>
          </div>
        )}

        <button
          onClick={onClose}
          className="w-full py-2.5 rounded-xl bg-dnd-gold text-dnd-bg font-semibold
                     min-h-[48px] active:scale-[0.97] active:opacity-70 transition-all duration-75"
        >
          OK
        </button>
      </div>
    </div>
  )
}

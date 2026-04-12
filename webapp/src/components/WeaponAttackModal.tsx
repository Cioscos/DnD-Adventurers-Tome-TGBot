/**
 * Modal that shows weapon attack + damage roll results.
 */

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

  const bgColor = is_critical
    ? 'bg-yellow-500/20 border border-yellow-500/50'
    : is_fumble
      ? 'bg-red-500/20 border border-red-500/50'
      : 'bg-[var(--tg-theme-secondary-bg-color)]'

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className={`rounded-2xl p-5 w-full max-w-sm space-y-4 ${bgColor}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="text-center">
          <p className="text-sm text-[var(--tg-theme-hint-color)]">⚔️ {weapon_name}</p>
          {is_critical && <p className="text-yellow-400 font-bold">✨ CRITICO!</p>}
          {is_fumble && <p className="text-red-400 font-bold">💀 FUMBLE!</p>}
        </div>

        {/* To-hit */}
        <div className="rounded-xl bg-white/10 p-3 text-center">
          <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">Per colpire</p>
          <p className="text-sm text-[var(--tg-theme-hint-color)]">
            d20 ({to_hit_die}) {bonusStr(to_hit_bonus)}
          </p>
          <p className={`text-3xl font-black ${is_critical ? 'text-yellow-400' : is_fumble ? 'text-red-400' : 'text-white'}`}>
            {to_hit_total}
          </p>
        </div>

        {/* Damage */}
        {!is_fumble && (
          <div className="rounded-xl bg-white/10 p-3 text-center">
            <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">
              Danno{is_critical ? ' (critico)' : ''} — {damage_dice}
            </p>
            <p className="text-sm text-[var(--tg-theme-hint-color)]">
              [{damage_rolls.join(', ')}] {bonusStr(damage_bonus)}
            </p>
            <p className="text-3xl font-black text-red-400">{damage_total}</p>
          </div>
        )}

        <button
          onClick={onClose}
          className="w-full py-2.5 rounded-xl bg-[var(--tg-theme-button-color)]
                     text-[var(--tg-theme-button-text-color)] font-semibold"
        >
          OK
        </button>
      </div>
    </div>
  )
}

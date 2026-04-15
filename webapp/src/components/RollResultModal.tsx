export type RollResult = {
  die: number
  bonus: number
  total: number
  is_critical: boolean
  is_fumble: boolean
  description?: string
}

type Props = {
  result: RollResult
  title: string
  onClose: () => void
}

export default function RollResultModal({ result, title, onClose }: Props) {
  const { die, bonus, total, is_critical, is_fumble } = result

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

  const dieColor = is_critical
    ? 'text-[var(--dnd-gold)]'
    : is_fumble
      ? 'text-[var(--dnd-danger)]'
      : 'text-dnd-text'

  const bonusStr = bonus >= 0 ? `+${bonus}` : `${bonus}`

  return (
    <div
      className="fixed inset-0 bg-black/65 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className={`rounded-2xl p-6 w-full max-w-xs text-center space-y-3
                     bg-dnd-surface-elevated border-2 ${borderColor} ${pulseClass}
                     animate-modal-enter`}
        onClick={(e) => e.stopPropagation()}
      >
        <p className="text-sm text-dnd-text-secondary font-medium">{title}</p>

        {is_critical && (
          <p className="text-[var(--dnd-gold)] font-bold text-sm">✦ CRITICO!</p>
        )}
        {is_fumble && (
          <p className="text-[var(--dnd-danger)] font-bold text-sm">💀 FUMBLE!</p>
        )}

        <div className={`text-6xl font-black ${dieColor}`}>{die}</div>

        <p className="text-dnd-text-secondary text-sm">
          d20 ({die}) {bonusStr} = <span className="text-dnd-text font-bold text-lg">{total}</span>
        </p>

        {result.description && (
          <p className="text-xs text-dnd-text-secondary">{result.description}</p>
        )}

        <button
          onClick={onClose}
          className="w-full py-2.5 rounded-xl bg-dnd-gold text-dnd-bg font-semibold mt-2
                     min-h-[48px] active:scale-[0.97] active:opacity-70 transition-all duration-75"
        >
          OK
        </button>
      </div>
    </div>
  )
}

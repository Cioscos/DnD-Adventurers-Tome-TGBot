/**
 * Generic dice roll result modal.
 * Shown after skill checks, saving throws, and weapon attacks.
 */

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

  const bgColor = is_critical
    ? 'bg-yellow-500/20 border border-yellow-500/50'
    : is_fumble
      ? 'bg-red-500/20 border border-red-500/50'
      : 'bg-[var(--tg-theme-secondary-bg-color)]'

  const dieColor = is_critical
    ? 'text-yellow-400'
    : is_fumble
      ? 'text-red-400'
      : 'text-white'

  const bonusStr = bonus >= 0 ? `+${bonus}` : `${bonus}`

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className={`rounded-2xl p-6 w-full max-w-xs text-center space-y-3 ${bgColor}`}
        onClick={(e) => e.stopPropagation()}
      >
        <p className="text-sm text-[var(--tg-theme-hint-color)] font-medium">{title}</p>

        {is_critical && (
          <p className="text-yellow-400 font-bold text-sm">✨ CRITICO!</p>
        )}
        {is_fumble && (
          <p className="text-red-400 font-bold text-sm">💀 FUMBLE!</p>
        )}

        {/* Die face */}
        <div className={`text-6xl font-black ${dieColor}`}>{die}</div>

        {/* Breakdown */}
        <p className="text-[var(--tg-theme-hint-color)] text-sm">
          d20 ({die}) {bonusStr} = <span className="text-white font-bold text-lg">{total}</span>
        </p>

        {result.description && (
          <p className="text-xs text-[var(--tg-theme-hint-color)]">{result.description}</p>
        )}

        <button
          onClick={onClose}
          className="w-full py-2.5 rounded-xl bg-[var(--tg-theme-button-color)]
                     text-[var(--tg-theme-button-text-color)] font-semibold mt-2"
        >
          OK
        </button>
      </div>
    </div>
  )
}

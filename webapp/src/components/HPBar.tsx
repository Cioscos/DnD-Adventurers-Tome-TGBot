interface HPBarProps {
  current: number
  max: number
  temp?: number
  size?: 'sm' | 'md'
}

export default function HPBar({ current, max, temp = 0, size = 'md' }: HPBarProps) {
  const pct = max > 0 ? Math.min(100, (current / max) * 100) : 0
  const color =
    pct > 50 ? '#30d158' : pct > 25 ? '#ffd60a' : '#ff453a'

  const height = size === 'sm' ? 'h-1.5' : 'h-2.5'

  return (
    <div className={`w-full ${height} rounded-full bg-white/10 overflow-hidden`}>
      <div
        className="h-full rounded-full transition-all duration-300"
        style={{ width: `${pct}%`, backgroundColor: color }}
      />
      {temp > 0 && (
        <div
          className="h-full rounded-full bg-blue-400 opacity-60"
          style={{ width: `${Math.min(100, (temp / max) * 100)}%` }}
        />
      )}
    </div>
  )
}

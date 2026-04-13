interface CardProps {
  children: React.ReactNode
  className?: string
  onClick?: (e: React.MouseEvent<HTMLDivElement>) => void
}

export default function Card({ children, className = '', onClick }: CardProps) {
  const base =
    'rounded-2xl p-4 transition-opacity active:opacity-70'
  const bg = 'bg-[var(--tg-theme-secondary-bg-color)]'
  const cursor = onClick ? 'cursor-pointer' : ''

  return (
    <div className={`${base} ${bg} ${cursor} ${className}`} onClick={onClick}>
      {children}
    </div>
  )
}

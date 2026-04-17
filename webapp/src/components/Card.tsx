import Surface, { type SurfaceVariant } from './ui/Surface'

interface CardProps {
  children: React.ReactNode
  className?: string
  variant?: 'default' | 'elevated'
  onClick?: (e: React.MouseEvent<HTMLDivElement>) => void
}

export default function Card({ variant = 'default', ...rest }: CardProps) {
  const mapped: SurfaceVariant = variant === 'elevated' ? 'elevated' : 'flat'
  return <Surface variant={mapped} {...rest} />
}

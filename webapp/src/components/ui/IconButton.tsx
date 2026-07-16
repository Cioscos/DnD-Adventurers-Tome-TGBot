import React from 'react'
import { m } from 'framer-motion'
import { spring } from '@/styles/motion'
import { fireHaptic, type HapticKind } from '@/lib/haptics'
import Spinner from './Spinner'

export type IconButtonVariant = 'ghost' | 'secondary' | 'danger'

interface IconButtonProps {
  icon: React.ReactNode
  variant?: IconButtonVariant
  loading?: boolean
  disabled?: boolean
  haptic?: HapticKind
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void
  className?: string
  type?: 'button' | 'submit'
  title?: string
  'aria-label'?: string
  'aria-pressed'?: boolean
}

function variantClasses(variant: IconButtonVariant): string {
  switch (variant) {
    case 'secondary':
      return 'bg-dnd-surface-raised text-dnd-text border border-dnd-gold-dim/30 hover:border-dnd-gold/70'
    case 'danger':
      return 'bg-dnd-crimson/15 text-dnd-crimson-bright border border-dnd-crimson/40 hover:bg-dnd-crimson/25 hover:border-dnd-crimson/60'
    case 'ghost':
    default:
      return 'bg-transparent text-dnd-gold hover:text-dnd-gold-bright'
  }
}

function IconButtonInner({
  icon,
  variant = 'ghost',
  loading = false,
  disabled = false,
  haptic: hapticKind = 'light',
  onClick,
  className = '',
  type = 'button',
  title,
  'aria-label': ariaLabel,
  'aria-pressed': ariaPressed,
}: IconButtonProps) {
  const isDisabled = disabled || loading

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    if (isDisabled) return
    fireHaptic(hapticKind)
    onClick?.(e)
  }

  return (
    <m.button
      type={type}
      onClick={handleClick}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      className={`min-w-[40px] min-h-[40px] rounded-xl flex items-center justify-center transition-colors duration-150 disabled:opacity-40 disabled:pointer-events-none ${variantClasses(variant)} ${className}`}
      title={title}
      aria-label={ariaLabel}
      aria-pressed={ariaPressed}
      whileTap={{ scale: 0.9 }}
      transition={spring.press}
    >
      {loading ? <Spinner /> : icon}
    </m.button>
  )
}

const IconButton = React.memo(IconButtonInner)
export default IconButton

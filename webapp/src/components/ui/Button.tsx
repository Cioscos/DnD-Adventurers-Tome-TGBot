import React, { useState, useRef } from 'react'
import { m } from 'framer-motion'
import { spring } from '@/styles/motion'
import { haptic } from '@/auth/telegram'

export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'arcane' | 'ghost'
export type ButtonSize = 'sm' | 'md' | 'lg'
export type HapticKind = 'light' | 'medium' | 'success' | 'error' | 'warning' | 'none'

interface ButtonProps {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
  disabled?: boolean
  icon?: React.ReactNode
  iconPosition?: 'left' | 'right'
  fullWidth?: boolean
  haptic?: HapticKind
  children?: React.ReactNode
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void
  className?: string
  type?: 'button' | 'submit'
  title?: string
  'aria-label'?: string
}

function variantClasses(variant: ButtonVariant): string {
  switch (variant) {
    case 'primary':
      return 'bg-gradient-gold text-dnd-ink shadow-engrave'
    case 'secondary':
      return 'bg-dnd-surface-raised text-dnd-text border border-dnd-gold-dim/30 hover:border-dnd-gold/70'
    case 'danger':
      return 'bg-[var(--dnd-crimson)]/15 text-[var(--dnd-crimson-bright)] border border-[var(--dnd-crimson)]/40'
    case 'arcane':
      return 'bg-gradient-to-r from-dnd-arcane-deep to-dnd-arcane text-white border border-dnd-arcane-bright/40 shadow-halo-arcane'
    case 'ghost':
      return 'bg-transparent text-dnd-gold hover:text-dnd-gold-bright border border-transparent'
  }
}

function sizeClasses(size: ButtonSize): string {
  switch (size) {
    case 'sm':
      return 'min-h-[40px] px-3 py-2 text-xs'
    case 'lg':
      return 'min-h-[56px] px-5 py-3.5 text-base'
    case 'md':
    default:
      return 'min-h-[48px] px-4 py-3 text-sm'
  }
}

interface Ripple { id: number; x: number; y: number }

function ButtonInner({
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  icon,
  iconPosition = 'left',
  fullWidth = false,
  haptic: hapticKind = 'light',
  children,
  onClick,
  className = '',
  type = 'button',
  title,
  'aria-label': ariaLabel,
}: ButtonProps) {
  const isDisabled = disabled || loading
  const [ripples, setRipples] = useState<Ripple[]>([])
  const btnRef = useRef<HTMLButtonElement>(null)

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    if (isDisabled) return
    // haptic
    if (hapticKind !== 'none') {
      if (hapticKind === 'success') haptic.success()
      else if (hapticKind === 'error') haptic.error()
      else if (hapticKind === 'warning') haptic.warning()
      else if (hapticKind === 'medium') haptic.medium()
      else haptic.light()
    }
    // ink-spread ripple on primary
    if (variant === 'primary' && btnRef.current) {
      const rect = btnRef.current.getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top
      const id = Date.now() + Math.random()
      setRipples((r) => [...r, { id, x, y }])
      setTimeout(() => setRipples((r) => r.filter((rp) => rp.id !== id)), 400)
    }
    onClick?.(e)
  }

  const base = 'relative overflow-hidden rounded-xl font-semibold flex items-center justify-center gap-2 transition-colors duration-150 disabled:opacity-40 disabled:pointer-events-none'
  const cls = `${base} ${sizeClasses(size)} ${variantClasses(variant)} ${fullWidth ? 'w-full' : ''} ${className}`

  return (
    <m.button
      ref={btnRef}
      type={type}
      onClick={handleClick}
      disabled={isDisabled}
      className={cls}
      title={title}
      aria-label={ariaLabel}
      whileTap={{ scale: 0.97 }}
      transition={spring.press}
    >
      {/* ink-spread ripples */}
      {ripples.map((r) => (
        <span
          key={r.id}
          className="absolute rounded-full bg-white/30 pointer-events-none"
          style={{
            left: r.x,
            top: r.y,
            width: 8,
            height: 8,
            marginLeft: -4,
            marginTop: -4,
            animation: 'ink-spread 320ms ease-out forwards',
          }}
        />
      ))}

      {loading ? (
        <>
          <span className="w-4 h-4 border-2 border-current/30 border-t-current rounded-full animate-spin" />
          {children}
        </>
      ) : (
        <>
          {icon && iconPosition === 'left' && icon}
          {children}
          {icon && iconPosition === 'right' && icon}
        </>
      )}
    </m.button>
  )
}

const Button = React.memo(ButtonInner)
export default Button

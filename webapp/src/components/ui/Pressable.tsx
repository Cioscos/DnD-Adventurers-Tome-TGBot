import React from 'react'
import { m, type TargetAndTransition, type Transition, type Variants } from 'framer-motion'
import { fireHaptic, type HapticKind } from '@/lib/haptics'
import Spinner from './Spinner'

interface PressableProps {
  /** Stato di attesa BE: disabilita, aria-busy e (di default) overlay spinner. */
  pending?: boolean
  /** false → nessun overlay: il chiamante posiziona <Spinner> dove preferisce. */
  spinner?: boolean
  spinnerSize?: number
  disabled?: boolean
  /** Default 'none': la conversione da <button> raw non cambia comportamento. */
  haptic?: HapticKind
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void
  className?: string
  children?: React.ReactNode
  type?: 'button' | 'submit'
  whileTap?: TargetAndTransition
  /** Escape hatch: hover gesture (es. Layout back button). */
  whileHover?: TargetAndTransition
  /** Escape hatch: animazione persistente non legata al gesture (es. halo su equip). */
  animate?: TargetAndTransition
  /** Escape hatch: transition custom per `animate`/`whileTap`/`whileHover`. */
  transition?: Transition
  /** Escape hatch: propagazione variants da un motion parent (stagger). */
  variants?: Variants
  title?: string
  style?: React.CSSProperties
  role?: string
  'aria-label'?: string
  'aria-pressed'?: boolean
  'aria-checked'?: boolean
  'aria-expanded'?: boolean
  'aria-selected'?: boolean
  'aria-current'?: React.AriaAttributes['aria-current']
}

function PressableInner({
  pending = false,
  spinner = true,
  spinnerSize = 14,
  disabled = false,
  haptic: hapticKind = 'none',
  onClick,
  className = '',
  children,
  type = 'button',
  whileTap,
  whileHover,
  animate,
  transition,
  variants,
  title,
  style,
  role,
  'aria-label': ariaLabel,
  'aria-pressed': ariaPressed,
  'aria-checked': ariaChecked,
  'aria-expanded': ariaExpanded,
  'aria-selected': ariaSelected,
  'aria-current': ariaCurrent,
}: PressableProps) {
  const isDisabled = disabled || pending

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    if (isDisabled) return
    fireHaptic(hapticKind)
    onClick?.(e)
  }

  // L'overlay inset-0 richiede un positioning context: aggiungiamo `relative`
  // solo se il chiamante non posiziona già il bottone (absolute/fixed/... in
  // className creano già il context e devono vincere).
  const positioned = /(?:^|\s)(?:relative|absolute|fixed|sticky)(?:\s|$)/.test(className)

  return (
    <m.button
      type={type}
      onClick={handleClick}
      disabled={isDisabled}
      aria-busy={pending || undefined}
      data-pending={pending || undefined}
      className={`${positioned ? '' : 'relative'} ${className}`}
      whileTap={isDisabled ? undefined : whileTap}
      whileHover={isDisabled ? undefined : whileHover}
      animate={animate}
      transition={transition}
      variants={variants}
      title={title}
      style={style}
      role={role}
      aria-label={ariaLabel}
      aria-pressed={ariaPressed}
      aria-checked={ariaChecked}
      aria-expanded={ariaExpanded}
      aria-selected={ariaSelected}
      aria-current={ariaCurrent}
    >
      {children}
      {pending && spinner && (
        <span className="absolute inset-0 flex items-center justify-center rounded-[inherit] bg-dnd-surface/60 pointer-events-none">
          <Spinner size={spinnerSize} />
        </span>
      )}
    </m.button>
  )
}

const Pressable = React.memo(PressableInner)
export default Pressable

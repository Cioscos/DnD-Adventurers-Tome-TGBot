import React from 'react'

interface DndButtonProps {
  variant?: 'primary' | 'secondary' | 'danger'
  loading?: boolean
  disabled?: boolean
  icon?: React.ReactNode
  children: React.ReactNode
  onClick?: () => void
  className?: string
  type?: 'button' | 'submit'
}

function DndButtonInner({
  variant = 'primary',
  loading = false,
  disabled = false,
  icon,
  children,
  onClick,
  className = '',
  type = 'button',
}: DndButtonProps) {
  const isDisabled = disabled || loading

  const base = 'min-h-[48px] px-4 py-3 rounded-xl font-semibold text-sm flex items-center justify-center gap-2 transition-all duration-75 active:scale-[0.97] active:opacity-70 disabled:opacity-40 disabled:pointer-events-none'

  const variants = {
    primary: 'bg-dnd-gold text-dnd-bg',
    secondary: 'bg-dnd-surface text-dnd-text border border-dnd-gold-dim/20',
    danger: 'bg-[var(--dnd-danger)]/15 text-[var(--dnd-danger)] border border-[var(--dnd-danger)]/30',
  }

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={isDisabled}
      className={`${base} ${variants[variant]} ${className}`}
    >
      {loading ? (
        <>
          <span className="w-4 h-4 border-2 border-current/30 border-t-current rounded-full animate-spin" />
          {children}
        </>
      ) : (
        <>
          {icon}
          {children}
        </>
      )}
    </button>
  )
}

const DndButton = React.memo(DndButtonInner)
export default DndButton

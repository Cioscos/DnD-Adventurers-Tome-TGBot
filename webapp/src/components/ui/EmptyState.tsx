import React from 'react'
import Surface from './Surface'
import Button from './Button'

interface EmptyStateAction {
  label: string
  onClick: () => void
  icon?: React.ReactNode
}

interface EmptyStateProps {
  icon?: React.ReactNode
  title: string
  hint?: string
  action?: EmptyStateAction
  className?: string
}

/** Centered empty placeholder with optional next-action CTA. */
export default function EmptyState({ icon, title, hint, action, className = '' }: EmptyStateProps) {
  return (
    <Surface variant="flat" className={`text-center py-8 ${className}`}>
      {icon && <div className="mx-auto mb-2 text-dnd-text-faint">{icon}</div>}
      <p className="text-dnd-text-muted font-body italic">{title}</p>
      {hint && (
        <p className="text-xs text-dnd-text-faint font-body mt-2 max-w-[28ch] mx-auto">{hint}</p>
      )}
      {action && (
        <div className="mt-4 flex justify-center">
          <Button size="sm" variant="secondary" icon={action.icon} onClick={action.onClick}>
            {action.label}
          </Button>
        </div>
      )}
    </Surface>
  )
}

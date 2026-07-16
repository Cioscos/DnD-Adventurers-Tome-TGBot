interface SpinnerProps {
  /** Diametro in px (default 16, come lo spinner storico di Button). */
  size?: number
  className?: string
}

/** Unica implementazione dello spinner in-app (DESIGN.md §Buttons/Loading):
 *  cerchio current-color, quarto pieno, animate-spin. */
export default function Spinner({ size = 16, className = '' }: SpinnerProps) {
  return (
    <span
      role="status"
      className={`inline-block shrink-0 border-2 border-current/30 border-t-current rounded-full animate-spin ${className}`}
      style={{ width: size, height: size }}
    />
  )
}

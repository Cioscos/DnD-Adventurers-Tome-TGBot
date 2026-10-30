import { useState, useCallback, useEffect, useRef } from 'react'
import { m, AnimatePresence } from 'framer-motion'

type InputVariant = 'default' | 'inline' | 'textarea'

interface InputProps {
  label?: string
  type?: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  error?: string
  min?: number
  max?: number
  disabled?: boolean
  inputMode?: 'text' | 'numeric' | 'decimal' | 'tel' | 'search' | 'email' | 'url'
  className?: string
  variant?: InputVariant
  leadingIcon?: React.ReactNode
  trailingAction?: React.ReactNode
  floatingLabel?: boolean
  rows?: number
  autoFocus?: boolean
  onCommit?: (value: string) => void
  /** false → onCommit SOLO con Invio, mai al blur. Per i form dove il blur nasce
   *  dal tap su un ALTRO controllo (es. cambio operazione HP): committare lì
   *  applicherebbe il valore con l'operazione sbagliata. */
  commitOnBlur?: boolean
  /** Etichetta del tasto Invio della tastiera mobile. */
  enterKeyHint?: 'done' | 'go' | 'next' | 'search' | 'send' | 'enter'
  inputRef?: React.Ref<HTMLInputElement | HTMLTextAreaElement>
}

export default function Input({
  label,
  type = 'text',
  value,
  onChange,
  placeholder,
  error,
  min,
  max,
  disabled = false,
  inputMode,
  className = '',
  variant = 'default',
  leadingIcon,
  trailingAction,
  floatingLabel = false,
  rows = 3,
  autoFocus,
  onCommit,
  commitOnBlur = true,
  enterKeyHint,
  inputRef,
}: InputProps) {
  const [focused, setFocused] = useState(false)
  const [localError, setLocalError] = useState('')
  const [shake, setShake] = useState(0)
  const ref = useRef<HTMLInputElement | HTMLTextAreaElement | null>(null)

  // Merge the internal ref with an optional forwarded ref so callers can
  // scroll/focus the field (e.g. RuleEditor scrolling to the name field on a
  // failed save).
  const setRefs = useCallback(
    (node: HTMLInputElement | HTMLTextAreaElement | null) => {
      ref.current = node
      if (typeof inputRef === 'function') inputRef(node)
      else if (inputRef) (inputRef as React.MutableRefObject<typeof node>).current = node
    },
    [inputRef],
  )

  // Shake once when an externally-controlled error transitions to truthy —
  // matches the DESIGN error pattern (crimson + one shake) for validation
  // surfaced on submit, not just on numeric blur.
  const prevErrorRef = useRef(error)
  useEffect(() => {
    if (error && !prevErrorRef.current) setShake((s) => s + 1)
    prevErrorRef.current = error
  }, [error])

  const displayError = error || localError

  // Validazione numerica: restituisce false (e segnala) se il valore è fuori range.
  const validate = useCallback((): boolean => {
    if (inputMode === 'numeric' || type === 'number') {
      const num = Number(value)
      if (value !== '' && isNaN(num)) {
        setLocalError('Valore non valido')
        setShake((s) => s + 1)
        return false
      }
      if (min !== undefined && num < min) {
        setLocalError(`Minimo: ${min}`)
        setShake((s) => s + 1)
        return false
      }
      if (max !== undefined && num > max) {
        setLocalError(`Massimo: ${max}`)
        setShake((s) => s + 1)
        return false
      }
    }
    setLocalError('')
    return true
  }, [value, min, max, inputMode, type])

  const handleBlur = useCallback(() => {
    setFocused(false)
    if (validate() && commitOnBlur) onCommit?.(value)
  }, [validate, commitOnBlur, onCommit, value])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    if (localError) setLocalError('')
    onChange(e.target.value)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && variant !== 'textarea') {
      // blur() will trigger handleBlur, which calls onCommit exactly once.
      // Calling onCommit here as well caused duplicate submissions (e.g. heal applied twice).
      // Con commitOnBlur=false il blur non committa: l'Invio lo fa qui, una volta.
      if (!commitOnBlur && validate()) onCommit?.(value)
      ;(e.target as HTMLElement).blur()
    }
  }

  const isTextarea = variant === 'textarea'

  const labelColor = displayError
    ? 'text-dnd-crimson-bright'
    : focused
      ? 'text-dnd-gold-bright'
      : 'text-dnd-gold-dim'

  const underlineColor = displayError
    ? 'border-dnd-crimson'
    : focused
      ? 'border-dnd-gold shadow-[0_2px_0_0_var(--dnd-gold-glow)]'
      : 'border-dnd-border'

  return (
    <m.div
      className={className}
      animate={shake ? { x: [-4, 4, -2, 2, 0] } : undefined}
      transition={{ duration: 0.25 }}
    >
      {label && !floatingLabel && (
        <label className={`block text-xs uppercase tracking-wider mb-1.5 font-cinzel font-bold transition-colors ${labelColor}`}>
          {label}
        </label>
      )}

      <div className="relative flex items-stretch">
        {leadingIcon && (
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-dnd-gold-dim pointer-events-none">
            {leadingIcon}
          </span>
        )}

        {isTextarea ? (
          <textarea
            ref={setRefs as React.Ref<HTMLTextAreaElement>}
            value={value}
            onChange={handleChange}
            onFocus={() => setFocused(true)}
            onBlur={handleBlur}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            rows={rows}
            autoFocus={autoFocus}
            className={`w-full px-3 py-2.5 min-h-[96px] rounded-lg bg-dnd-surface text-dnd-text
                        border-b-2 ${underlineColor} outline-none transition-all duration-200
                        placeholder:text-dnd-text-faint font-body
                        disabled:opacity-40 disabled:cursor-not-allowed resize-y`}
          />
        ) : (
          <input
            ref={setRefs as React.Ref<HTMLInputElement>}
            type={inputMode === 'numeric' ? 'text' : type}
            inputMode={inputMode}
            enterKeyHint={enterKeyHint}
            value={value}
            onChange={handleChange}
            onFocus={() => setFocused(true)}
            onBlur={handleBlur}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            autoFocus={autoFocus}
            className={`w-full px-3 py-2.5 min-h-[48px] rounded-lg bg-dnd-surface text-dnd-text
                        border-b-2 ${underlineColor} outline-none transition-all duration-200
                        placeholder:text-dnd-text-faint font-body
                        disabled:opacity-40 disabled:cursor-not-allowed
                        ${leadingIcon ? 'pl-10' : ''}
                        ${trailingAction ? 'pr-12' : ''}`}
          />
        )}

        {trailingAction && (
          <span className="absolute right-2 top-1/2 -translate-y-1/2">{trailingAction}</span>
        )}
      </div>

      <AnimatePresence>
        {displayError && (
          <m.p
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="text-dnd-crimson-bright text-xs mt-1 font-body"
          >
            {displayError}
          </m.p>
        )}
      </AnimatePresence>
    </m.div>
  )
}

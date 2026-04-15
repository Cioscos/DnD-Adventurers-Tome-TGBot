import { useState, useCallback } from 'react'

interface DndInputProps {
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
}

export default function DndInput({
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
}: DndInputProps) {
  const [focused, setFocused] = useState(false)
  const [localError, setLocalError] = useState('')

  const displayError = error || localError

  const handleBlur = useCallback(() => {
    setFocused(false)
    if (inputMode === 'numeric' || type === 'number') {
      const num = Number(value)
      if (value !== '' && isNaN(num)) {
        setLocalError('Valore non valido')
        return
      }
      if (min !== undefined && num < min) {
        setLocalError(`Minimo: ${min}`)
        return
      }
      if (max !== undefined && num > max) {
        setLocalError(`Massimo: ${max}`)
        return
      }
    }
    setLocalError('')
  }, [value, min, max, inputMode, type])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (localError) setLocalError('')
    onChange(e.target.value)
  }

  const labelColor = displayError
    ? 'text-[var(--dnd-danger)]'
    : focused
      ? 'text-dnd-gold'
      : 'text-dnd-gold-dim'

  const borderColor = displayError
    ? 'border-[var(--dnd-danger)]'
    : focused
      ? 'border-dnd-gold-dim shadow-[0_0_0_2px_var(--dnd-gold-glow)]'
      : 'border-transparent'

  return (
    <div className={className}>
      {label && (
        <label className={`block text-[11px] uppercase tracking-wider mb-1 font-medium transition-colors ${labelColor}`}>
          {label}
        </label>
      )}
      <input
        type={inputMode === 'numeric' ? 'text' : type}
        inputMode={inputMode}
        value={value}
        onChange={handleChange}
        onFocus={() => setFocused(true)}
        onBlur={handleBlur}
        placeholder={placeholder}
        disabled={disabled}
        className={`w-full px-3 py-3 min-h-[48px] rounded-xl bg-dnd-surface text-dnd-text
                    border ${borderColor} outline-none transition-all duration-150
                    placeholder:text-dnd-text-secondary/50
                    disabled:opacity-40 disabled:cursor-not-allowed`}
      />
      {displayError && (
        <p className="text-[var(--dnd-danger)] text-[11px] mt-1">{displayError}</p>
      )}
    </div>
  )
}

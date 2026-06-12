import React, { useState, useRef, useMemo, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { X } from 'lucide-react'
import { m } from 'framer-motion'

interface ChipInputProps {
  values: string[]
  onChange: (next: string[]) => void
  placeholder?: string
  /** Return null on valid, or an error message string. */
  validate?: (candidate: string, current: string[]) => string | null
  /** Lowercase + trim before storing. */
  normalize?: (raw: string) => string
  /** Tokens of comma-pasted input → separate chips. */
  splitOnComma?: boolean
  /** Optional dropdown of canonical values (e.g. SRD languages). Filtered by current input. */
  suggestions?: string[]
  label?: React.ReactNode
  hint?: React.ReactNode
  className?: string
}

const defaultNormalize = (raw: string) => raw.trim()

export default function ChipInput({
  values,
  onChange,
  placeholder,
  validate,
  normalize = defaultNormalize,
  splitOnComma = true,
  suggestions,
  label,
  hint,
  className = '',
}: ChipInputProps) {
  const { t } = useTranslation()
  const [input, setInput] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [showSuggestions, setShowSuggestions] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const filteredSuggestions = useMemo(() => {
    if (!suggestions || suggestions.length === 0) return []
    const lc = values.map((v) => v.toLowerCase())
    const inputLc = input.trim().toLowerCase()
    const remaining = suggestions.filter((s) => !lc.includes(s.toLowerCase()))
    if (!inputLc) return remaining.slice(0, 8)
    return remaining
      .filter((s) => s.toLowerCase().includes(inputLc))
      .slice(0, 8)
  }, [suggestions, values, input])

  const commit = (raw: string) => {
    const tokens = splitOnComma
      ? raw.split(',').map(normalize).filter(Boolean)
      : [normalize(raw)].filter(Boolean)

    if (tokens.length === 0) return
    let working = values.slice()
    let lastError: string | null = null
    for (const tok of tokens) {
      if (working.includes(tok)) {
        lastError = `"${tok}" già presente`
        continue
      }
      if (validate) {
        const e = validate(tok, working)
        if (e) {
          lastError = e
          continue
        }
      }
      working = [...working, tok]
    }
    setError(lastError)
    if (working.length !== values.length) {
      onChange(working)
      setInput('')
    }
  }

  const handleKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',' || e.key === 'Tab') {
      if (input.trim()) {
        e.preventDefault()
        commit(input)
      }
    } else if (e.key === 'Backspace' && !input && values.length > 0) {
      onChange(values.slice(0, -1))
    }
  }

  const remove = (idx: number) => {
    const next = values.filter((_, i) => i !== idx)
    onChange(next)
  }

  return (
    <div className={className}>
      {label && (
        <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim mb-1.5">
          {label}
        </p>
      )}
      <div
        className="min-h-[44px] flex flex-wrap items-center gap-1.5 px-2 py-1.5 rounded-xl bg-dnd-surface border border-dnd-border focus-within:border-dnd-gold/60"
        onClick={() => inputRef.current?.focus()}
      >
        {values.map((v, idx) => (
          <m.span
            key={`${v}-${idx}`}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
            className="inline-flex items-center gap-1 pl-2 pr-1 py-0.5 rounded-full bg-dnd-chip-bg border border-dnd-gold-dim/40 text-xs font-body text-dnd-text"
          >
            <span>{v}</span>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation()
                remove(idx)
              }}
              className="hit-44 inline-flex items-center justify-center text-dnd-gold-dim hover:text-dnd-gold-bright"
              aria-label={`${t('common.remove')} ${v}`}
            >
              <X size={12} />
            </button>
          </m.span>
        ))}
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => {
            setInput(e.target.value)
            if (error) setError(null)
            if (suggestions) setShowSuggestions(true)
          }}
          onKeyDown={handleKey}
          onFocus={() => suggestions && setShowSuggestions(true)}
          onBlur={() => {
            // Delay so suggestion clicks register before the dropdown closes.
            setTimeout(() => setShowSuggestions(false), 120)
            if (input.trim()) commit(input)
          }}
          placeholder={values.length === 0 ? placeholder : ''}
          className="flex-1 min-w-[80px] bg-transparent outline-none text-sm font-body text-dnd-text placeholder:text-dnd-text-faint py-1"
        />
      </div>
      {showSuggestions && filteredSuggestions.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-1.5">
          {filteredSuggestions.map((s) => (
            <button
              key={s}
              type="button"
              onMouseDown={(e) => {
                // mousedown fires before blur, so the input keeps focus and the suggestion commits.
                e.preventDefault()
                commit(s)
                inputRef.current?.focus()
              }}
              className="px-2 py-1 rounded-full text-[11px] font-body
                         bg-dnd-chip-bg border border-dnd-gold-dim/30
                         text-dnd-text-muted hover:text-dnd-gold-bright hover:border-dnd-gold/60"
            >
              {s}
            </button>
          ))}
        </div>
      )}
      {error && (
        <p className="text-[11px] text-dnd-crimson-bright mt-1 font-body italic">{error}</p>
      )}
      {hint && !error && (
        <p className="text-[11px] text-dnd-text-faint mt-1 font-body italic">{hint}</p>
      )}
    </div>
  )
}

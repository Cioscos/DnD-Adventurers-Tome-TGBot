/** Inline SVG flags for IT/EN — Telegram emoji rendering varies across platforms. */

interface FlagProps {
  size?: number
  className?: string
}

export function FlagIT({ size = 14, className = '' }: FlagProps) {
  return (
    <svg width={size} height={size * 0.667} viewBox="0 0 3 2" className={`inline-block rounded-sm overflow-hidden ${className}`} aria-hidden>
      <rect x="0" y="0" width="1" height="2" fill="#009246" />
      <rect x="1" y="0" width="1" height="2" fill="#f1f2f1" />
      <rect x="2" y="0" width="1" height="2" fill="#ce2b37" />
    </svg>
  )
}

export function FlagEN({ size = 14, className = '' }: FlagProps) {
  // Union Jack — simplified
  return (
    <svg width={size} height={size * 0.5} viewBox="0 0 60 30" className={`inline-block rounded-sm overflow-hidden ${className}`} aria-hidden>
      <clipPath id="t">
        <path d="M30,15 h30 v15 z v15 h-30 z h-30 v-15 z v-15 h30 z" />
      </clipPath>
      <path d="M0,0 v30 h60 v-30 z" fill="#012169" />
      <path d="M0,0 L60,30 M60,0 L0,30" stroke="#fff" strokeWidth="6" />
      <path d="M0,0 L60,30 M60,0 L0,30" clipPath="url(#t)" stroke="#C8102E" strokeWidth="4" />
      <path d="M30,0 v30 M0,15 h60" stroke="#fff" strokeWidth="10" />
      <path d="M30,0 v30 M0,15 h60" stroke="#C8102E" strokeWidth="6" />
    </svg>
  )
}

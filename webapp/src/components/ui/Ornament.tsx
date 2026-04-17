/**
 * Corner flourish SVG — placed absolutely in corners of elevated Surface.
 * Rotation prop controls which corner (0=TL, 90=TR, 180=BR, 270=BL).
 */
export function CornerFlourish({
  rotation = 0,
  size = 18,
  className = '',
}: {
  rotation?: 0 | 90 | 180 | 270
  size?: number
  className?: string
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      className={`pointer-events-none ${className}`}
      style={{ transform: `rotate(${rotation}deg)` }}
      aria-hidden
    >
      <path
        d="M2 2 L10 2 M2 2 L2 10 M10 2 Q8 6 4 8 M2 10 Q6 8 8 4"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        fill="none"
        opacity="0.85"
      />
      <circle cx="3" cy="3" r="1.2" fill="currentColor" opacity="0.9" />
    </svg>
  )
}

/** Four-corner flourishes wrapper — adds trefoil ornaments at card corners. */
export function CornerFlourishes({ color = 'text-dnd-gold-dim' }: { color?: string }) {
  return (
    <div className={`absolute inset-0 ${color} pointer-events-none`}>
      <div className="absolute top-1.5 left-1.5"><CornerFlourish rotation={0} /></div>
      <div className="absolute top-1.5 right-1.5"><CornerFlourish rotation={90} /></div>
      <div className="absolute bottom-1.5 right-1.5"><CornerFlourish rotation={180} /></div>
      <div className="absolute bottom-1.5 left-1.5"><CornerFlourish rotation={270} /></div>
    </div>
  )
}

/** Section divider — flourish SVG with center diamond, used by SectionDivider. */
export function FlourishDivider({ className = '' }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 240 12"
      preserveAspectRatio="none"
      className={`w-full h-3 ${className}`}
      aria-hidden
    >
      <line x1="0" y1="6" x2="105" y2="6" stroke="currentColor" strokeWidth="0.6" opacity="0.4" />
      <line x1="135" y1="6" x2="240" y2="6" stroke="currentColor" strokeWidth="0.6" opacity="0.4" />
      <path d="M120 2 L125 6 L120 10 L115 6 Z" fill="currentColor" opacity="0.9" />
      <circle cx="105" cy="6" r="1" fill="currentColor" opacity="0.7" />
      <circle cx="135" cy="6" r="1" fill="currentColor" opacity="0.7" />
    </svg>
  )
}

/** Wax seal — decorative empty-state emblem. */
export function WaxSeal({ size = 80 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      aria-hidden
      className="drop-shadow-[0_4px_12px_rgba(179,58,58,0.4)]"
    >
      <defs>
        <radialGradient id="wax-seal-gradient" cx="40%" cy="40%" r="60%">
          <stop offset="0%" stopColor="var(--dnd-crimson-bright)" />
          <stop offset="60%" stopColor="var(--dnd-crimson)" />
          <stop offset="100%" stopColor="var(--dnd-crimson-deep)" />
        </radialGradient>
      </defs>
      <circle cx="50" cy="50" r="42" fill="url(#wax-seal-gradient)" stroke="var(--dnd-gold-deep)" strokeWidth="1.5" />
      <path
        d="M50 22 L58 44 L80 44 L62 58 L70 80 L50 68 L30 80 L38 58 L20 44 L42 44 Z"
        fill="var(--dnd-gold-bright)"
        opacity="0.9"
      />
    </svg>
  )
}

/** Dice runic watermark — decorative background for Dice page. */
export function DiceRunicWatermark({ size = 240 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      aria-hidden
      className="pointer-events-none opacity-[0.06] text-dnd-gold"
    >
      <polygon
        points="50,6 92,28 92,72 50,94 8,72 8,28"
        stroke="currentColor"
        strokeWidth="1"
        fill="none"
      />
      <polygon
        points="50,20 78,34 78,66 50,80 22,66 22,34"
        stroke="currentColor"
        strokeWidth="0.8"
        fill="none"
      />
      <text x="50" y="56" textAnchor="middle" fontSize="22" fill="currentColor" fontFamily="Cinzel, serif" fontWeight="900">20</text>
    </svg>
  )
}

/** Scroll edge — torn-paper bar for modal sheet header. */
export function ScrollEdge({ className = '' }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 300 8"
      preserveAspectRatio="none"
      className={`w-full h-2 ${className}`}
      aria-hidden
    >
      <path
        d="M0 4 Q15 1 30 4 T60 4 T90 4 T120 4 T150 4 T180 4 T210 4 T240 4 T270 4 T300 4 V8 H0 Z"
        fill="currentColor"
      />
    </svg>
  )
}

/** Shield SVG — behind AC number. */
export function ShieldEmblem({ size = 140, className = '' }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      className={className}
      aria-hidden
    >
      <defs>
        <linearGradient id="shield-gold" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="var(--dnd-gold-bright)" />
          <stop offset="50%" stopColor="var(--dnd-gold)" />
          <stop offset="100%" stopColor="var(--dnd-gold-deep)" />
        </linearGradient>
      </defs>
      <path
        d="M50 8 L88 20 V52 Q88 80 50 94 Q12 80 12 52 V20 Z"
        fill="var(--dnd-surface-raised)"
        stroke="url(#shield-gold)"
        strokeWidth="2.5"
      />
      <path
        d="M50 16 L80 26 V52 Q80 74 50 86 Q20 74 20 52 V26 Z"
        fill="none"
        stroke="var(--dnd-gold-dim)"
        strokeWidth="0.8"
        opacity="0.5"
      />
    </svg>
  )
}

export default CornerFlourishes

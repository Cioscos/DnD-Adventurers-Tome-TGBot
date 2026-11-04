// Silhouette di ripiego: un viandante incappucciato, perché senza razza, classe e
// sesso il personaggio è ancora uno sconosciuto. Tratto inciso come i PNG di classe.

const r1 = (n: number) => Math.round(n * 10) / 10

/** Tratteggio sul lato in ombra del mantello: segue il bordo esterno destro. */
const CLOAK_HATCH = Array.from({ length: 30 }, (_, i) => {
  const y = 112 + i * 6.6
  const x = y < 240 ? 149 + ((y - 100) / 140) * 16 : 165 + (y - 240) * 0.02
  const len = 6 + (i % 2) * 3
  return `M${r1(x)} ${r1(y)}q${r1(-len / 2)} 1.5 ${r1(-len)} 5`
}).join('')

/** Ombra dentro il cappuccio: archi fitti che seguono l'apertura e si diradano verso il basso. */
const FACE_HATCH = Array.from({ length: 21 }, (_, i) => {
  const t = (i - 10) / 10 // -1..1 da sinistra a destra
  const x = 100 + t * 19
  const top = 37.5 + t * t * 15
  const len = 26 - Math.abs(t) * 12 - (i % 2) * 6
  return `M${r1(x)} ${r1(top)}q${r1(-t * 0.5)} ${r1(len / 2)} ${r1(-t * 1.5)} ${r1(len)}`
}).join('')

export default function WandererSilhouette() {
  return (
    <svg
      viewBox="0 0 200 350"
      width="100%"
      height="320"
      className="text-dnd-gold-dim"
      style={{ filter: 'drop-shadow(0 2px 6px rgba(var(--dnd-shadow-color), 0.45))' }}
      aria-hidden="true"
      data-testid="wanderer-silhouette"
    >
      <defs>
        <linearGradient id="wanderer-cloth" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="var(--dnd-surface-raised)" />
          <stop offset="100%" stopColor="var(--dnd-surface)" />
        </linearGradient>
      </defs>

      <g fill="url(#wanderer-cloth)" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" strokeLinecap="round">
        {/* Stivali: l'unica parte del corpo che spunta dal mantello */}
        <path d="M84 300 L98 300 L98 325 Q98 336 90 337 L70 337 Q65 330 75 325 Q82 321 84 312 Z" />
        <path d="M116 300 L102 300 L102 325 Q102 336 110 337 L130 337 Q135 330 125 325 Q118 321 116 312 Z" />

        {/* Tunica e cintura, nello spiraglio fra i lembi */}
        <path d="M92 92 L108 92 L113 316 Q100 322 87 316 Z" />
        <path d="M89 170 Q100 175 111 170 L111.5 180 Q100 185 88.5 180 Z" />
        <rect x="95.5" y="172" width="9" height="10" rx="1.5" />

        {/* Mantello: due lembi quasi chiusi */}
        <path d="M92 86 C78 78 60 82 50 100 C42 130 36 190 32 240 C30 265 30 288 36 312 C44 320 50 309 58 316 C66 323 74 312 88 320 C89 270 90 200 95 130 C96 112 96 98 92 86 Z" />
        <path d="M108 86 C122 78 140 82 150 100 C158 130 164 190 168 240 C170 265 170 288 164 312 C156 320 150 309 142 316 C134 323 126 312 112 320 C111 270 110 200 105 130 C104 112 104 98 108 86 Z" />

        {/* Cappuccio, con la cappa che ricade sulle spalle */}
        <path d="M100 12 C84 16 64 32 62 58 C61 76 66 92 76 104 C86 114 114 114 124 104 C134 92 139 76 138 58 C136 32 116 16 100 12 Z" />
        <path d="M100 34 C86 36 78 50 78 64 C78 78 88 90 100 96 C112 90 122 78 122 64 C122 50 114 36 100 34 Z" fill="var(--dnd-bg)" />
      </g>

      {/* Pieghe: le braccia si indovinano sotto il tessuto */}
      <g fill="none" stroke="currentColor" strokeWidth="0.8" strokeLinecap="round" opacity="0.8">
        <path d="M58 106 C50 140 58 172 86 190" />
        <path d="M142 106 C150 140 142 172 114 190" />
        <path d="M64 180 C58 220 54 270 52 312" />
        <path d="M78 192 C74 230 72 280 72 316" />
        <path d="M136 180 C142 220 146 270 148 312" />
        <path d="M122 192 C126 230 128 280 128 316" />
        <path d="M48 196 C44 226 42 260 42 296" />
        <path d="M97 188 C96 230 96 270 95 316" />
        <path d="M104 188 C105 240 106 280 106 316" />
        {/* Curve del cappuccio: il lato destro è in ombra */}
        <path d="M71 96 C66 80 68 60 77 44" />
        <path d="M112 19 C124 26 133 42 133 60 C133 74 128 88 120 98" />
        <path d="M108 24 C118 30 128 44 128 60 C128 72 124 84 117 94" />
      </g>

      {/* Ombre a tratteggio: la luce arriva da sinistra */}
      <g fill="none" stroke="currentColor" strokeLinecap="round">
        <path d={CLOAK_HATCH} strokeWidth="0.7" opacity="0.6" />
        <path d={FACE_HATCH} strokeWidth="0.9" opacity="0.8" />
      </g>

      {/* Il fermaglio è l'unico punto d'oro pieno */}
      <path d="M100 103 L108 112 L100 121 L92 112 Z" fill="var(--dnd-gold)" stroke="var(--dnd-gold-bright)" strokeWidth="0.8" strokeLinejoin="round" />
    </svg>
  )
}

import Pressable from '@/components/ui/Pressable'

interface HpQuickChipsProps {
  /** Segno mostrato davanti al valore: − danno, + cura, vuoto per i valori da impostare. */
  sign: '−' | '+' | ''
  onPick: (n: number) => void
  /** Valore in corso di applicazione, per lo spinner sul chip premuto. */
  pendingVal?: number
}

/** Valori rapidi di PF: pagina HP e foglio rapido dell'hub. */
export default function HpQuickChips({ sign, onPick, pendingVal }: HpQuickChipsProps) {
  return (
    <div className="grid grid-cols-4 gap-2">
      {[1, 5, 10, 20].map((n) => (
        <Pressable
          key={n}
          onClick={() => onPick(n)}
          pending={pendingVal === n}
          spinnerSize={16}
          className="min-h-[52px] rounded-2xl bg-dnd-surface border border-dnd-border
                     text-dnd-gold-bright font-mono font-bold text-base
                     hover:border-dnd-gold/70 transition-colors"
          whileTap={{ scale: 0.94 }}
        >
          {`${sign}${n}`}
        </Pressable>
      ))}
    </div>
  )
}

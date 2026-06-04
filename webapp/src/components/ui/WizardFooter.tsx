import Button, { type HapticKind } from '@/components/ui/Button'

interface WizardFooterProps {
  /** Slot secondario (sinistra): "Annulla" al 1º step, "Indietro" dopo. */
  secondaryLabel: string
  onSecondary: () => void
  /** Slot primario (destra, riempie): "Avanti →" / "Crea" / "Aggiungi" / "Salva". */
  primaryLabel: string
  onPrimary: () => void
  primaryDisabled?: boolean
  primaryLoading?: boolean
  primaryHaptic?: HapticKind
  secondaryDisabled?: boolean
  /** Spaziatura del contenitore (es. "mt-4" / "pt-2"); nessun default. */
  className?: string
}

/**
 * Footer unico per tutti i wizard: layout FISSO (secondario compatto a
 * sinistra, primario che riempie a destra). Resta a riga anche a 300px.
 * Compone i Button esistenti → conforme a DESIGN.md.
 */
export default function WizardFooter({
  secondaryLabel,
  onSecondary,
  primaryLabel,
  onPrimary,
  primaryDisabled = false,
  primaryLoading = false,
  primaryHaptic = 'medium',
  secondaryDisabled = false,
  className = '',
}: WizardFooterProps) {
  return (
    <div className={`flex gap-2 ${className}`}>
      <Button
        variant="secondary"
        onClick={onSecondary}
        disabled={secondaryDisabled}
        className="px-5 shrink-0"
      >
        {secondaryLabel}
      </Button>
      <Button
        variant="primary"
        onClick={onPrimary}
        disabled={primaryDisabled}
        loading={primaryLoading}
        haptic={primaryHaptic}
        className="flex-1"
      >
        {primaryLabel}
      </Button>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import { parseCounterInput } from '@/lib/counterInput'
import { haptic } from '@/auth/telegram'

interface UsesEditSheetProps {
  open: boolean
  /** Titolo dello sheet, già tradotto (es. "Imposta usi · Sanità"). */
  title: string
  value: number
  /** null = nessun tetto (es. munizioni). */
  max: number | null
  onSave: (n: number) => void
  onClose: () => void
  isPending: boolean
}

/** Editor numerico manuale per usi/quantità: sostituisce N tap su −/+.
 *  Il valore è clampato a [0, max] da parseCounterInput; Salva è disabilitato
 *  su input invalido. */
export default function UsesEditSheet({
  open, title, value, max, onSave, onClose, isPending,
}: UsesEditSheetProps) {
  const { t } = useTranslation()
  const [draft, setDraft] = useState(String(value))

  useEffect(() => {
    if (open) setDraft(String(value))
  }, [open, value])

  const parsed = parseCounterInput(draft, max)

  return (
    <Sheet open={open} onClose={onClose} title={title}>
      <div className="p-5 space-y-3">
        <Input
          label={max != null
            ? t('character.abilities.set_uses_hint', { max })
            : t('character.abilities.set_uses_hint_unbounded')}
          value={draft}
          onChange={setDraft}
          type="number"
          min={0}
          inputMode="numeric"
          autoFocus
        />
        <div className="flex gap-2 pt-2">
          <Button variant="secondary" onClick={onClose} className="px-4">
            {t('common.cancel')}
          </Button>
          <Button
            variant="primary"
            fullWidth
            disabled={parsed === null}
            loading={isPending}
            haptic="success"
            onClick={() => {
              if (parsed === null) { haptic.error(); return }
              onSave(parsed)
            }}
          >
            {t('common.save')}
          </Button>
        </div>
      </div>
    </Sheet>
  )
}

import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Minus, Plus } from 'lucide-react'
import Sheet from '@/components/ui/Sheet'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'

const MIN = 1
const MAX = 30

interface Props {
  open: boolean
  /** Localized ability label, e.g. "Destrezza". */
  label: string
  /** Current stored value. */
  currentValue: number
  saving?: boolean
  onClose: () => void
  onSave: (value: number) => void
}

export default function AbilityScoreEditModal({
  open, label, currentValue, saving = false, onClose, onSave,
}: Props) {
  const { t } = useTranslation()
  const [value, setValue] = useState<number>(currentValue)

  // Re-seed whenever the modal (re)opens for a (possibly different) ability.
  useEffect(() => {
    if (open) setValue(currentValue)
  }, [open, currentValue])

  const clamp = (n: number) => Math.max(MIN, Math.min(MAX, n))
  const mod = Math.floor((value - 10) / 2)
  const inRange = Number.isFinite(value) && value >= MIN && value <= MAX
  const canSave = inRange && value !== currentValue && !saving

  return (
    <Sheet open={open} onClose={onClose} title={t('character.stats.edit_title', { ability: label })} centered>
      <div className="px-5 py-5 space-y-5">
        <div className="flex items-center justify-center gap-4">
          <m.button
            onClick={() => setValue((v) => clamp((Number.isFinite(v) ? v : currentValue) - 1))}
            disabled={value <= MIN}
            whileTap={{ scale: 0.9 }}
            aria-label={t('character.stats.decrease')}
            className="w-14 h-14 rounded-xl bg-[var(--dnd-crimson)]/15 text-[var(--dnd-crimson-bright)] border border-[var(--dnd-crimson)]/40 flex items-center justify-center disabled:opacity-30"
          >
            <Minus size={24} />
          </m.button>

          <div className="flex flex-col items-center min-w-[96px]">
            <span className="text-5xl font-mono font-bold tabular-nums text-dnd-text leading-none">
              {Number.isFinite(value) ? value : currentValue}
            </span>
            <span className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim mt-1">
              {t('character.ability.mod_label')} {mod >= 0 ? `+${mod}` : mod}
            </span>
          </div>

          <m.button
            onClick={() => setValue((v) => clamp((Number.isFinite(v) ? v : currentValue) + 1))}
            disabled={value >= MAX}
            whileTap={{ scale: 0.9 }}
            aria-label={t('character.stats.increase')}
            className="w-14 h-14 rounded-xl bg-[var(--dnd-emerald)]/20 text-[var(--dnd-emerald-bright)] border border-dnd-emerald/40 flex items-center justify-center disabled:opacity-30"
          >
            <Plus size={24} />
          </m.button>
        </div>

        <Input
          value={String(Number.isFinite(value) ? value : '')}
          onChange={(v) => setValue(v === '' ? NaN : clamp(parseInt(v, 10)))}
          type="number"
          min={MIN}
          max={MAX}
          inputMode="numeric"
          className="[&_input]:text-2xl [&_input]:font-mono [&_input]:font-bold [&_input]:tabular-nums [&_input]:text-center [&_input]:min-h-[56px]"
        />

        <div className="flex gap-2">
          <Button variant="secondary" className="flex-1" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button
            className="flex-1"
            disabled={!canSave}
            loading={saving}
            onClick={() => { if (canSave) onSave(value) }}
          >
            {t('common.save')}
          </Button>
        </div>
      </div>
    </Sheet>
  )
}

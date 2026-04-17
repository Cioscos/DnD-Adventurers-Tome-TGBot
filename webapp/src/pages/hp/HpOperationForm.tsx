import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Minus, Plus, Target, Maximize2, Sparkles, Check } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import { haptic } from '@/auth/telegram'

type HPOp = 'damage' | 'heal' | 'set_max' | 'set_current' | 'set_temp'

interface HpOperationFormProps {
  activeOp: HPOp
  setActiveOp: (op: HPOp) => void
  value: string
  setValue: (v: string) => void
  onApply: () => void
  isPending: boolean
  hpMutate: (args: { op: HPOp; val: number }) => void
}

const ops: { key: HPOp; label_key: string; icon: LucideIcon; toneClass: string }[] = [
  { key: 'damage',      label_key: 'character.hp.damage',      icon: Minus,      toneClass: '!bg-gradient-ember !text-white !border-transparent shadow-halo-danger' },
  { key: 'heal',        label_key: 'character.hp.heal',        icon: Plus,       toneClass: '!bg-[var(--dnd-emerald)]/25 !text-[var(--dnd-emerald-bright)] !border-dnd-emerald/60' },
  { key: 'set_current', label_key: 'character.hp.set_current', icon: Target,     toneClass: '!bg-[var(--dnd-cobalt)]/20 !text-[var(--dnd-cobalt-bright)] !border-dnd-cobalt/60' },
  { key: 'set_max',     label_key: 'character.hp.set_max',     icon: Maximize2,  toneClass: '!bg-[var(--dnd-amber)]/20 !text-[var(--dnd-amber)] !border-dnd-amber/60' },
  { key: 'set_temp',    label_key: 'character.hp.set_temp',    icon: Sparkles,   toneClass: '!bg-[var(--dnd-arcane)]/20 !text-dnd-arcane-bright !border-dnd-arcane/60' },
]

export default function HpOperationForm({
  activeOp,
  setActiveOp,
  value,
  setValue,
  onApply,
  isPending,
  hpMutate,
}: HpOperationFormProps) {
  const { t } = useTranslation()

  return (
    <>
      {/* Op selector — segmented control */}
      <Surface variant="flat" className="!p-1.5">
        <div className="grid grid-cols-5 gap-1">
          {ops.map((op) => {
            const Icon = op.icon
            const isActive = activeOp === op.key
            return (
              <m.button
                key={op.key}
                onClick={() => { setActiveOp(op.key); haptic.selection() }}
                className={`flex flex-col items-center gap-0.5 py-2 px-1 rounded-xl font-cinzel text-[9px] uppercase tracking-wider border
                  ${isActive
                    ? op.toneClass
                    : 'bg-transparent text-dnd-text-muted border-transparent'}`}
                whileTap={{ scale: 0.95 }}
              >
                <Icon size={16} strokeWidth={2.2} />
                <span className="leading-tight">{t(op.label_key)}</span>
              </m.button>
            )
          })}
        </div>
      </Surface>

      {/* Number input + apply */}
      <Surface variant="elevated">
        <div className="flex flex-col gap-3">
          <Input
            type="number"
            min={0}
            value={value}
            onChange={setValue}
            placeholder="0"
            inputMode="numeric"
            onCommit={onApply}
            className="[&_input]:text-3xl [&_input]:font-display [&_input]:font-bold [&_input]:text-center [&_input]:min-h-[60px]"
          />
          <Button
            variant="primary"
            size="lg"
            fullWidth
            onClick={onApply}
            disabled={!value || isPending}
            loading={isPending}
            icon={<Check size={20} />}
            haptic="medium"
          >
            {t('common.confirm')}
          </Button>
        </div>
      </Surface>

      {/* Quick shortcuts — at least 52px min-height */}
      <div className="grid grid-cols-4 gap-2">
        {[1, 5, 10, 20].map((n) => (
          <m.button
            key={n}
            onClick={() => {
              hpMutate({ op: activeOp, val: n })
              haptic.light()
            }}
            className="min-h-[52px] rounded-2xl bg-dnd-surface border border-dnd-border
                       text-dnd-gold-bright font-mono font-bold text-base
                       hover:border-dnd-gold/70 transition-colors"
            whileTap={{ scale: 0.94 }}
          >
            {activeOp === 'damage' ? `−${n}` : activeOp === 'heal' ? `+${n}` : `${n}`}
          </m.button>
        ))}
      </div>
    </>
  )
}

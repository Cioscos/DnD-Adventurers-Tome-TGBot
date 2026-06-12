import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Minus, Plus, Heart, HeartPulse, Check } from 'lucide-react'
import { GiSkullCrossedBones as Skull } from 'react-icons/gi'
import { GiSparkles as Sparkles } from 'react-icons/gi'
import type { ComponentType, SVGAttributes } from 'react'
type IconCmp = ComponentType<SVGAttributes<SVGElement> & { size?: number | string }>
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
  atZero: boolean
  crit: boolean
  setCrit: (c: boolean) => void
}

// Short labels fit the 5-column segmented control at 390px viewport.
const ops: { key: HPOp; label_key: string; full_key: string; icon: IconCmp; toneClass: string }[] = [
  { key: 'damage',      label_key: 'character.hp.damage_short',  full_key: 'character.hp.damage',      icon: Minus,       toneClass: '!bg-gradient-ember !text-dnd-parchment !border-transparent shadow-halo-danger' },
  { key: 'heal',        label_key: 'character.hp.heal_short',    full_key: 'character.hp.heal',        icon: Plus,        toneClass: '!bg-dnd-emerald/25 !text-dnd-emerald-bright !border-dnd-emerald/60' },
  { key: 'set_current', label_key: 'character.hp.current_short', full_key: 'character.hp.set_current', icon: Heart,       toneClass: '!bg-dnd-cobalt/20 !text-dnd-cobalt-bright !border-dnd-cobalt/60' },
  { key: 'set_max',     label_key: 'character.hp.max_short',     full_key: 'character.hp.set_max',     icon: HeartPulse,  toneClass: '!bg-dnd-amber/20 !text-dnd-amber !border-dnd-amber/60' },
  { key: 'set_temp',    label_key: 'character.hp.temp_short',    full_key: 'character.hp.set_temp',    icon: Sparkles,    toneClass: '!bg-dnd-arcane/20 !text-dnd-arcane-bright !border-dnd-arcane/60' },
]

export default function HpOperationForm({
  activeOp,
  setActiveOp,
  value,
  setValue,
  onApply,
  isPending,
  hpMutate,
  atZero,
  crit,
  setCrit,
}: HpOperationFormProps) {
  const { t } = useTranslation()

  return (
    <>
      {/* Op selector — segmented control, 2-row (3+2) so labels stay readable at 390px */}
      <Surface variant="flat" className="!p-1.5 space-y-1">
        <div className="grid grid-cols-3 gap-1">
          {ops.slice(0, 3).map((op) => {
            const Icon = op.icon
            const isActive = activeOp === op.key
            return (
              <m.button
                key={op.key}
                onClick={() => { setActiveOp(op.key); haptic.selection() }}
                title={t(op.full_key)}
                className={`flex flex-col items-center gap-0.5 py-2 px-1 rounded-xl font-cinzel text-[11px] uppercase tracking-tight border min-h-[52px]
                  ${isActive
                    ? op.toneClass
                    : 'bg-transparent text-dnd-text-muted border-transparent'}`}
                whileTap={{ scale: 0.95 }}
              >
                <Icon size={18} strokeWidth={2.2} />
                <span className="leading-tight">{t(op.label_key)}</span>
              </m.button>
            )
          })}
        </div>
        <div className="grid grid-cols-2 gap-1">
          {ops.slice(3).map((op) => {
            const Icon = op.icon
            const isActive = activeOp === op.key
            return (
              <m.button
                key={op.key}
                onClick={() => { setActiveOp(op.key); haptic.selection() }}
                title={t(op.full_key)}
                className={`flex flex-col items-center gap-0.5 py-2 px-1 rounded-xl font-cinzel text-[11px] uppercase tracking-tight border min-h-[52px]
                  ${isActive
                    ? op.toneClass
                    : 'bg-transparent text-dnd-text-muted border-transparent'}`}
                whileTap={{ scale: 0.95 }}
              >
                <Icon size={18} strokeWidth={2.2} />
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
          {activeOp === 'damage' && atZero && (
            <button
              type="button"
              onClick={() => { setCrit(!crit); haptic.selection() }}
              aria-pressed={crit}
              className={`flex items-center justify-center gap-2 min-h-[44px] rounded-xl border font-cinzel text-xs uppercase tracking-wider transition-colors
                ${crit
                  ? '!bg-gradient-ember !text-dnd-parchment !border-transparent'
                  : 'bg-transparent text-dnd-text-muted border-dnd-border'}`}
            >
              <Skull size={16} />
              {t('character.hp.critical_hit')}
            </button>
          )}
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

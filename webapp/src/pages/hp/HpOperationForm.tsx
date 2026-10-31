import { useTranslation } from 'react-i18next'
import { Minus, Plus, Heart, HeartPulse, Check } from 'lucide-react'
import { GiSkullCrossedBones as Skull } from 'react-icons/gi'
import { GiSparkles as Sparkles } from 'react-icons/gi'
import type { ComponentType, SVGAttributes } from 'react'
type IconCmp = ComponentType<SVGAttributes<SVGElement> & { size?: number | string }>
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import Pressable from '@/components/ui/Pressable'
import { haptic } from '@/auth/telegram'
import DamageTypeControls from '@/components/ui/DamageTypeControls'
import { applyDamageModifier, damagePreviewText, type DamageModifier, type DamageMultiplier } from '@/lib/damageModifier'

type HPOp = 'damage' | 'heal' | 'set_max' | 'set_current' | 'set_temp'

interface HpOperationFormProps {
  activeOp: HPOp
  setActiveOp: (op: HPOp) => void
  value: string
  setValue: (v: string) => void
  onApply: () => void
  isPending: boolean
  hpMutate: (args: { op: HPOp; val: number }) => void
  /** Val of the quick-shortcut currently in flight on the shared hpMutation (P4 scoping), undefined when none. */
  pendingQuickVal?: number
  atZero: boolean
  crit: boolean
  setCrit: (c: boolean) => void
  damageModifier: DamageModifier
  setDamageModifier: (m: DamageModifier) => void
  /** Tipo di danno opzionale ('' = nessuno); senza `setDamageType` il picker non compare. */
  damageType?: string
  setDamageType?: (type: string) => void
  /** Moltiplicatore proposto dalle resistenze del personaggio per `damageType`. */
  proposedModifier?: DamageMultiplier
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
  pendingQuickVal,
  atZero,
  crit,
  setCrit,
  damageModifier,
  setDamageModifier,
  damageType = '',
  setDamageType,
  proposedModifier,
}: HpOperationFormProps) {
  const { t } = useTranslation()
  const rawTyped = parseInt(value, 10)
  // Override dell'utente, altrimenti la proposta del tipo di danno.
  const effective: DamageModifier = damageModifier ?? (damageType ? proposedModifier ?? null : null)
  const showPreview = activeOp === 'damage' && !!effective && effective !== 'none' && !isNaN(rawTyped) && rawTyped > 0

  return (
    <>
      {/* Op selector — segmented control, 2-row (3+2) so labels stay readable at 390px */}
      <Surface variant="flat" className="!p-1.5 space-y-1">
        <div className="grid grid-cols-3 gap-1">
          {ops.slice(0, 3).map((op) => {
            const Icon = op.icon
            const isActive = activeOp === op.key
            return (
              <Pressable
                key={op.key}
                onClick={() => { setActiveOp(op.key); haptic.selection() }}
                title={t(op.full_key)}
                className={`flex flex-col items-center gap-0.5 py-2 px-1 rounded-xl font-cinzel text-xs uppercase tracking-tight border min-h-[52px]
                  ${isActive
                    ? op.toneClass
                    : 'bg-transparent text-dnd-text-muted border-transparent'}`}
                whileTap={{ scale: 0.95 }}
              >
                <Icon size={18} strokeWidth={2.2} />
                <span className="leading-tight">{t(op.label_key)}</span>
              </Pressable>
            )
          })}
        </div>
        <div className="grid grid-cols-2 gap-1">
          {ops.slice(3).map((op) => {
            const Icon = op.icon
            const isActive = activeOp === op.key
            return (
              <Pressable
                key={op.key}
                onClick={() => { setActiveOp(op.key); haptic.selection() }}
                title={t(op.full_key)}
                className={`flex flex-col items-center gap-0.5 py-2 px-1 rounded-xl font-cinzel text-xs uppercase tracking-tight border min-h-[52px]
                  ${isActive
                    ? op.toneClass
                    : 'bg-transparent text-dnd-text-muted border-transparent'}`}
                whileTap={{ scale: 0.95 }}
              >
                <Icon size={18} strokeWidth={2.2} />
                <span className="leading-tight">{t(op.label_key)}</span>
              </Pressable>
            )
          })}
        </div>
      </Surface>

      {/* Number input + apply */}
      <Surface variant="elevated">
        <div className="flex flex-col gap-3">
          {activeOp === 'damage' && (
            <DamageTypeControls
              damageType={damageType}
              setDamageType={setDamageType}
              damageModifier={damageModifier}
              setDamageModifier={setDamageModifier}
              proposedModifier={proposedModifier}
            />
          )}
          <Input
            type="number"
            min={0}
            value={value}
            onChange={setValue}
            placeholder="0"
            inputMode="numeric"
            enterKeyHint="done"
            // Solo Invio/Conferma applicano: al blur (tap su "Cura", su uno
            // shortcut, su Indietro) il valore veniva applicato con l'op attiva.
            commitOnBlur={false}
            onCommit={onApply}
            className="[&_input]:text-3xl [&_input]:font-display [&_input]:font-bold [&_input]:text-center [&_input]:min-h-[60px]"
          />
          {showPreview && (
            <p className="text-center font-mono text-sm tabular-nums text-dnd-cobalt-bright">
              {damagePreviewText(
                damageType && effective ? t(`character.hp.preview_${effective}`) : null,
                rawTyped,
                applyDamageModifier(rawTyped, effective),
              )}
            </p>
          )}
          {activeOp === 'damage' && atZero && (
            <Pressable
              onClick={() => { setCrit(!crit); haptic.selection() }}
              aria-pressed={crit}
              className={`flex items-center justify-center gap-2 min-h-[44px] rounded-xl border font-cinzel text-xs uppercase tracking-wider transition-colors
                ${crit
                  ? '!bg-gradient-ember !text-dnd-parchment !border-transparent'
                  : 'bg-transparent text-dnd-text-muted border-dnd-border'}`}
            >
              <Skull size={16} />
              {t('character.hp.critical_hit')}
            </Pressable>
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

      {/* Quick shortcuts — at least 52px min-height. Applicano al volo solo le
          op incrementali (danno/cura/temp); per "Imposta attuali/max" riempiono
          il campo: un tap su "5" non deve fissare i PF massimi a 5. */}
      <div className="grid grid-cols-4 gap-2">
        {[1, 5, 10, 20].map((n) => (
          <Pressable
            key={n}
            onClick={() => {
              if (activeOp === 'set_max' || activeOp === 'set_current') {
                setValue(String(n))
                haptic.selection()
                return
              }
              hpMutate({ op: activeOp, val: n })
              haptic.light()
            }}
            pending={pendingQuickVal === n}
            spinnerSize={16}
            className="min-h-[52px] rounded-2xl bg-dnd-surface border border-dnd-border
                       text-dnd-gold-bright font-mono font-bold text-base
                       hover:border-dnd-gold/70 transition-colors"
            whileTap={{ scale: 0.94 }}
          >
            {activeOp === 'damage' ? `−${n}` : activeOp === 'heal' ? `+${n}` : `${n}`}
          </Pressable>
        ))}
      </div>
    </>
  )
}

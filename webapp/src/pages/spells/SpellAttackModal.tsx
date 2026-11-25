import type React from 'react'
import RollNotes from '@/components/rules/RollNotes'
import { m } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import {
  GiPolarStar as Star, GiSkullCrossedBones as Skull,
  GiMagicSwirl as Swirl,
} from 'react-icons/gi'
import ResultDialog from '@/components/ui/ResultDialog'
import InspirationRerollButton from '@/components/InspirationRerollButton'
import Button from '@/components/ui/Button'
import RollButton from '@/components/ui/RollButton'
import D20Faces from '@/components/ui/D20Faces'
import { classLabel } from '@/lib/classLabel'
import type { RollMode } from '@/api/client'
import type { SpellAttackResult } from '@/types'

type Props = {
  /** Serve al bersaglio delle opzioni del lancio. */
  charId?: number
  result: SpellAttackResult
  /** L'incantesimo ha un dado del danno: mostra "Tira danni" (mai su un 1 naturale). */
  canRollDamage: boolean
  onRollDamage: () => void
  onClose: () => void
  inspirationAvailable?: boolean
  isRerolling?: boolean
  wasRerolled?: boolean
  onInspirationReroll?: () => void | Promise<void>
  /** Riga dei privilegi usati dopo aver visto il d20. */
  afterRollRow?: React.ReactNode
  /** Il danno di questo raggio è tirato, o è dichiarato mancato: resta solo il raggio seguente. */
  rayDone?: boolean
  /** C'è un altro raggio dello stesso lancio (Deflagrazione Occulta): ognuno ha il suo tiro per colpire. */
  onNextRay?: (mode: RollMode) => void
  isRollingRay?: boolean
}

/** Esito del tiro per colpire di un incantesimo d'attacco (modellato su WeaponAttackModal). */
export default function SpellAttackModal({
  charId,
  result,
  canRollDamage,
  onRollDamage,
  onClose,
  inspirationAvailable = false,
  isRerolling = false,
  wasRerolled = false,
  onInspirationReroll,
  afterRollRow,
  rayDone = false,
  onNextRay,
  isRollingRay = false,
}: Props) {
  const { t } = useTranslation()
  const { spell_name, to_hit_die, dice, mode, to_hit_bonus, to_hit_total, is_critical, is_fumble, caster_class } = result

  const bonusStr = `${to_hit_bonus >= 0 ? '+' : '-'}${Math.abs(to_hit_bonus)}`
  const accent = is_critical ? 'gold' : is_fumble ? 'crimson' : 'emerald'
  // Raddoppiato: il 1 naturale di un bersaglio non toglie il tiro dei danni all'altro.
  const showDamage = !rayDone && canRollDamage && (!is_fumble || (!!result.twinned_attack && !result.twinned_attack.is_fumble))
  const showInspirationButton = inspirationAvailable && !wasRerolled && onInspirationReroll != null
  const toHitColor = is_critical
    ? 'text-dnd-gold-bright'
    : is_fumble
      ? 'text-dnd-crimson-bright'
      : 'text-dnd-text'
  const casterLabel = caster_class
    ? t('character.spells.attack_caster', {
        class: classLabel(t, caster_class),
        bonus: bonusStr,
      })
    : null

  const ray = result.ray && result.rays ? { n: result.ray, total: result.rays } : null
  const nextRayLabel = ray && t(rayDone || is_fumble ? 'character.spells.next_ray' : 'character.spells.next_ray_missed', { n: ray.n + 1, total: ray.total })

  return (
    <ResultDialog
      open
      onClose={onClose}
      accent={accent}
      pulse={is_critical || is_fumble}
      size="md"
      hideOkButton
      title={
        <span className="inline-flex items-center justify-center gap-1.5">
          <Swirl size={14} className="text-dnd-gold-bright" />
          {spell_name}
        </span>
      }
      subtitle={[ray && t('character.spells.ray_of', ray), wasRerolled && t('character.inspiration.reroll_badge')].filter(Boolean).join(' · ') || undefined}
      extraActions={
        <div className="space-y-2">
          {afterRollRow}
          {showInspirationButton && (
            <InspirationRerollButton available pending={isRerolling} onClick={onInspirationReroll} />
          )}
          {showDamage && (
            <Button variant="primary" fullWidth onClick={onRollDamage} haptic="medium">
              {t('character.spells.attack_roll_damage')}
            </Button>
          )}
          {onNextRay && nextRayLabel && (
            <RollButton
              onRoll={onNextRay}
              pending={isRollingRay}
              ariaLabel={nextRayLabel}
              className="w-full min-h-12 px-4 rounded-xl text-sm font-medium bg-dnd-crimson/20 text-dnd-crimson-bright border border-dnd-crimson/30 active:opacity-60"
            >
              {nextRayLabel}
            </RollButton>
          )}
          <Button variant={showDamage || onNextRay ? 'secondary' : 'primary'} fullWidth onClick={onClose}>
            {t('common.close')}
          </Button>
        </div>
      }
    >
      {casterLabel && (
        <p className="text-sm text-dnd-text-muted font-body tabular-nums">{casterLabel}</p>
      )}
      {is_critical && (
        <p className="text-dnd-gold-bright font-bold font-cinzel uppercase tracking-wider flex items-center justify-center gap-1.5">
          <Star size={14} fill="currentColor" /> {t('character.dice.critical_banner')}
        </p>
      )}
      {is_fumble && (
        <p className="text-dnd-crimson-bright font-bold font-cinzel uppercase tracking-wider flex items-center justify-center gap-1.5">
          <Skull size={14} /> {t('character.dice.fumble_banner')}
        </p>
      )}

      {result.forced_hit && (
        <p className="text-dnd-emerald-bright font-bold font-cinzel uppercase tracking-wider">
          {t('character.roll_options.forced_hit')}
        </p>
      )}
      <RollNotes notes={result.notes} charId={charId} optionResult={result.cast_option_result} />
      <m.div
        className="rounded-2xl bg-dnd-surface/80 border border-dnd-border p-3"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <p className="text-xs text-dnd-text-faint mb-1 font-cinzel uppercase tracking-wider">
          {t('character.spells.to_hit')}
        </p>
        <p className="text-xs text-dnd-text-muted font-body tabular-nums">
          <D20Faces die={to_hit_die} dice={dice} mode={mode} /> {bonusStr}
        </p>
        <p className={`text-4xl font-black font-display mt-1 tabular-nums ${toHitColor}`}>
          {to_hit_total}
        </p>
      </m.div>
      {result.twinned_attack && (
        <div className="rounded-2xl bg-dnd-surface/80 border border-dnd-border p-3">
          <p className="text-xs text-dnd-text-faint mb-1 font-cinzel uppercase tracking-wider">
            {t('character.spells.twinned_attack')}
          </p>
          <p className="text-xs text-dnd-text-muted font-body tabular-nums">
            <D20Faces die={result.twinned_attack.die} dice={result.twinned_attack.dice} mode={(result.twinned_attack.mode ?? 'normal') as typeof mode} /> {bonusStr}
          </p>
          <p className={`text-2xl font-black font-display mt-1 tabular-nums ${result.twinned_attack.is_critical ? 'text-dnd-gold-bright' : result.twinned_attack.is_fumble ? 'text-dnd-crimson-bright' : 'text-dnd-text'}`}>
            {result.twinned_attack.total}
          </p>
          {result.twinned_attack.is_critical && (
            <p className="text-xs font-bold font-cinzel uppercase tracking-wider text-dnd-gold-bright">{t('character.dice.critical_banner')}</p>
          )}
          {result.twinned_attack.is_fumble && (
            <p className="text-xs font-bold font-cinzel uppercase tracking-wider text-dnd-crimson-bright">{t('character.dice.fumble_banner')}</p>
          )}
        </div>
      )}
    </ResultDialog>
  )
}

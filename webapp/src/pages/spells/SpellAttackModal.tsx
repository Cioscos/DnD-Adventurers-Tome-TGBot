import { m } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import {
  GiPolarStar as Star, GiSkullCrossedBones as Skull,
  GiMagicSwirl as Swirl,
} from 'react-icons/gi'
import ResultDialog from '@/components/ui/ResultDialog'
import InspirationRerollButton from '@/components/InspirationRerollButton'
import Button from '@/components/ui/Button'
import type { SpellAttackResult } from '@/types'

type Props = {
  result: SpellAttackResult
  /** L'incantesimo ha un dado del danno: mostra "Tira danni" (mai su un 1 naturale). */
  canRollDamage: boolean
  onRollDamage: () => void
  onClose: () => void
  inspirationAvailable?: boolean
  isRerolling?: boolean
  wasRerolled?: boolean
  onInspirationReroll?: () => void | Promise<void>
}

/** Esito del tiro per colpire di un incantesimo d'attacco (modellato su WeaponAttackModal). */
export default function SpellAttackModal({
  result,
  canRollDamage,
  onRollDamage,
  onClose,
  inspirationAvailable = false,
  isRerolling = false,
  wasRerolled = false,
  onInspirationReroll,
}: Props) {
  const { t } = useTranslation()
  const { spell_name, to_hit_die, to_hit_bonus, to_hit_total, is_critical, is_fumble, caster_class } = result

  const bonusStr = `${to_hit_bonus >= 0 ? '+' : '-'}${Math.abs(to_hit_bonus)}`
  const accent = is_critical ? 'gold' : is_fumble ? 'crimson' : 'emerald'
  const showDamage = canRollDamage && !is_fumble
  const showInspirationButton = inspirationAvailable && !wasRerolled && onInspirationReroll != null
  const toHitColor = is_critical
    ? 'text-dnd-gold-bright'
    : is_fumble
      ? 'text-dnd-crimson-bright'
      : 'text-dnd-text'
  const casterLabel = caster_class
    ? t('character.spells.attack_caster', {
        class: t(`dnd.classes.${caster_class.toLowerCase()}`, { defaultValue: caster_class }),
        bonus: bonusStr,
      })
    : null

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
      subtitle={wasRerolled ? t('character.inspiration.reroll_badge') : undefined}
      extraActions={
        <div className="space-y-2">
          {showInspirationButton && (
            <InspirationRerollButton available pending={isRerolling} onClick={onInspirationReroll} />
          )}
          {showDamage && (
            <Button variant="primary" fullWidth onClick={onRollDamage} haptic="medium">
              {t('character.spells.attack_roll_damage')}
            </Button>
          )}
          <Button variant={showDamage ? 'secondary' : 'primary'} fullWidth onClick={onClose}>
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
          d20 ({to_hit_die}) {bonusStr}
        </p>
        <p className={`text-4xl font-black font-display mt-1 tabular-nums ${toHitColor}`}>
          {to_hit_total}
        </p>
      </m.div>
    </ResultDialog>
  )
}

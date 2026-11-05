import RollNotes from '@/components/rules/RollNotes'
import AfterDamageOptions from '@/components/rules/AfterDamageOptions'
import { useState } from 'react'
import { m } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import {
  GiPolarStar as Star, GiSkullCrossedBones as Skull,
  GiCrossedSwords as Swords,
} from 'react-icons/gi'
import ResultDialog from './ui/ResultDialog'
import InspirationRerollButton from './InspirationRerollButton'
import D20Faces from './ui/D20Faces'
import type { WeaponAttackResult } from '@/api/client'

export type { WeaponAttackResult }

type Props = {
  result: WeaponAttackResult
  /** Con il personaggio, l'esito offre di applicare gli effetti ai combattenti. */
  charId?: number
  onClose: () => void
  inspirationAvailable?: boolean
  isRerolling?: boolean
  wasRerolled?: boolean
  onInspirationReroll?: () => void | Promise<void>
}

export default function WeaponAttackModal({
  result: attack,
  charId,
  onClose,
  inspirationAvailable = false,
  isRerolling = false,
  wasRerolled = false,
  onInspirationReroll,
}: Props) {
  const { t } = useTranslation()
  // Il danno ritirato con l'Ispirazione sostituisce quello del tiro, finché il tiro è lo stesso.
  const [rerolled, setRerolled] = useState<{ base: WeaponAttackResult; value: WeaponAttackResult } | null>(null)
  const result = rerolled?.base === attack ? rerolled.value : attack
  const dieSides = Number(/\d+d(\d+)/.exec(result.damage_dice ?? '')?.[1])
  const canRerollDamage = !!charId && !!dieSides && !result.attack_id && !result.is_fumble && !result.grazed && !result.effect
  const {
    weapon_name, to_hit_die, dice, mode, magic_bonus, proficiency_warning, to_hit_bonus, to_hit_total,
    is_critical, is_fumble, damage_dice, damage_rolls, damage_bonus, damage_total,
    ammo, ammo_missing,
  } = result

  const bonusStr = (n: number) => n >= 0 ? `+${n}` : `${n}`

  const accent = is_critical ? 'gold' : is_fumble ? 'crimson' : 'emerald'
  const showInspirationButton =
    inspirationAvailable && !wasRerolled && onInspirationReroll != null && !result.attack_id
    && !result.effect && !result.grazed

  const toHitColor = is_critical
    ? 'text-dnd-gold-bright'
    : is_fumble
      ? 'text-dnd-crimson-bright'
      : 'text-dnd-text'

  return (
    <ResultDialog
      open
      onClose={onClose}
      accent={accent}
      pulse={is_critical || is_fumble}
      size="md"
      title={
        <span className="inline-flex items-center justify-center gap-1.5">
          <Swords size={14} className="text-dnd-gold-bright" />
          {weapon_name}
        </span>
      }
      subtitle={wasRerolled ? t('character.inspiration.reroll_badge') : undefined}
      extraActions={
        showInspirationButton ? (
          <InspirationRerollButton
            available
            pending={isRerolling}
            onClick={onInspirationReroll}
          />
        ) : undefined
      }
    >
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
      <RollNotes notes={result.notes} optionResult={result.option_result} charId={charId} />
      {result.effect && (
        <p data-testid="unarmed-effect" className="rounded-2xl bg-dnd-surface/80 border border-dnd-border p-3 text-sm font-body text-dnd-text">
          {t(`character.attack.effect_${result.effect}`, { dc: result.save_dc })}
        </p>
      )}
      {!result.effect && <m.div
        className="rounded-2xl bg-dnd-surface/80 border border-dnd-border p-3"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <p className="text-xs text-dnd-text-faint mb-1 font-cinzel uppercase tracking-wider">
          {t('character.attack.to_hit')}
        </p>
        <p className="text-xs text-dnd-text-muted font-body">
          <D20Faces die={to_hit_die} dice={dice} mode={mode} /> {bonusStr(to_hit_bonus)}
          {!!magic_bonus && ` · ${t('character.attack.magic_bonus', { n: magic_bonus })}`}
        </p>
        <p className={`text-4xl font-black font-display mt-1 ${toHitColor}`}>
          {to_hit_total}
        </p>
      </m.div>}

      {result.grazed && (
        <m.div
          data-testid="grazed-damage"
          className="rounded-2xl bg-dnd-surface/80 border border-dnd-border p-3"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <p className="text-xs text-dnd-text-faint mb-1 font-cinzel uppercase tracking-wider">{t('character.attack.grazed')}</p>
          <p className="text-4xl font-black font-display mt-1 text-dnd-crimson-bright">{damage_total}</p>
        </m.div>
      )}

      {!is_fumble && !result.effect && !result.grazed && (
        <m.div
          className="rounded-2xl bg-dnd-surface/80 border border-dnd-border p-3"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <p className="text-xs text-dnd-text-faint mb-1 font-cinzel uppercase tracking-wider">
            {is_critical ? t('character.attack.damage_critical') : t('character.attack.damage')}: {damage_dice}
          </p>
          <p className="text-xs text-dnd-text-muted font-body font-mono">
            [{damage_rolls.join(', ')}] {bonusStr(damage_bonus)}
          </p>
          <p className="text-4xl font-black font-display mt-1 text-dnd-crimson-bright">
            {damage_total}
          </p>
        </m.div>
      )}
      {canRerollDamage && (
        <AfterDamageOptions
          charId={charId}
          query={{ roll: 'weapon_damage' }}
          dice={damage_rolls.map((value, index) => ({ value, index, sides: dieSides }))}
          onResult={(r) => setRerolled({ base: attack, value: r as WeaponAttackResult })}
        />
      )}

      {proficiency_warning && (
        <p className="text-sm text-dnd-gold-bright font-body">
          {t('character.attack.proficiency_warning')}
        </p>
      )}
      {ammo && (
        <p className="text-sm text-dnd-text-muted font-body tabular-nums">
          {ammo.name}: {ammo.remaining}
        </p>
      )}
      {ammo_missing && (
        <p className="text-sm text-dnd-crimson-bright font-body">
          {t('character.attack.ammo_missing')}
        </p>
      )}
    </ResultDialog>
  )
}

import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation } from '@tanstack/react-query'
import { m } from 'framer-motion'
import { Minus, Plus } from 'lucide-react'
import {
  GiPerspectiveDiceSixFacesRandom as Dices, GiCrossedSwords as Swords,
  GiCheckedShield as Shield,
} from 'react-icons/gi'
import { api } from '@/api/client'
import type { Spell, RollDamageRequest, RollDamageResult } from '@/types'
import Sheet from '@/components/ui/Sheet'
import { haptic } from '@/auth/telegram'
import { useDiceAnimation } from '@/dice/useDiceAnimation'
import type { DiceKind } from '@/dice/types'

const ALLOWED_DICE_KINDS: DiceKind[] = ['d4', 'd6', 'd8', 'd10', 'd12', 'd20', 'd100']
const isAllowedDiceKind = (k: string | null | undefined): k is DiceKind =>
  typeof k === 'string' && (ALLOWED_DICE_KINDS as string[]).includes(k)

interface SpellDamageSheetProps {
  charId: number
  spell: Spell | null
  onClose: () => void
}

export default function SpellDamageSheet({
  charId,
  spell,
  onClose,
}: SpellDamageSheetProps) {
  const { t } = useTranslation()
  const [castingLevel, setCastingLevel] = useState(spell?.level ?? 1)
  const [extraDice, setExtraDice] = useState('')
  const [isCritical, setIsCritical] = useState(false)
  const [result, setResult] = useState<RollDamageResult | null>(null)

  useEffect(() => {
    if (spell) {
      setCastingLevel(spell.level)
      setExtraDice('')
      setIsCritical(false)
      setResult(null)
    }
  }, [spell?.id])

  const dice = useDiceAnimation()

  const mutation = useMutation({
    mutationFn: (body: RollDamageRequest) => {
      if (!spell) throw new Error('no spell')
      return api.spells.rollDamage(charId, spell.id, body)
    },
    onSuccess: async (data) => {
      if (isAllowedDiceKind(data.main_kind)) {
        const groups = [{ kind: data.main_kind, results: data.main_rolls }]
        if (isAllowedDiceKind(data.extra_kind) && data.extra_rolls.length > 0) {
          groups.push({ kind: data.extra_kind, results: data.extra_rolls })
        }
        await dice.play({ groups, interGroupMs: 150 })
      }
      haptic.success()
      setResult(data)
    },
    onError: () => haptic.error(),
  })

  if (!spell) return null

  const isAttack =
    spell.attack_save === 'ATK' ||
    spell.attack_save === null ||
    spell.attack_save === undefined ||
    spell.attack_save === ''
  const maxLevel = 9
  const minLevel = spell.level

  const handleRoll = () => {
    mutation.mutate({
      casting_level: castingLevel,
      extra_dice: extraDice || undefined,
      is_critical: isCritical,
    })
  }

  const reset = () => {
    setResult(null)
    setExtraDice('')
    setIsCritical(false)
    setCastingLevel(spell.level)
  }

  const handleClose = () => {
    reset()
    onClose()
  }

  return (
    <Sheet
      open={!!spell}
      onClose={handleClose}
      title={t('character.spells.roll_damage.title', { name: spell.name })}
    >
      {!result ? (
        <div className="space-y-4 p-1">
          <div>
            <label className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim">
              {t('character.spells.roll_damage.casting_level')}
            </label>
            <div className="mt-1 flex items-center gap-2">
              <button
                type="button"
                onClick={() => setCastingLevel((v) => Math.max(minLevel, v - 1))}
                className="w-8 h-8 rounded-md bg-dnd-surface border border-dnd-border"
                aria-label={t('character.spells.roll_damage.decrease_level')}
              >
                <Minus size={14} className="mx-auto" />
              </button>
              <div className="flex-1 text-center font-display text-xl font-bold">
                {castingLevel}
              </div>
              <button
                type="button"
                onClick={() => setCastingLevel((v) => Math.min(maxLevel, v + 1))}
                className="w-8 h-8 rounded-md bg-dnd-surface border border-dnd-border"
                aria-label={t('character.spells.roll_damage.increase_level')}
              >
                <Plus size={14} className="mx-auto" />
              </button>
            </div>
          </div>

          <div>
            <label className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim">
              {t('character.spells.roll_damage.extra_dice')}
            </label>
            <input
              type="text"
              value={extraDice}
              onChange={(e) => setExtraDice(e.target.value)}
              placeholder={t('character.spells.roll_damage.extra_dice_placeholder')}
              className="mt-1 w-full bg-dnd-surface border border-dnd-border rounded-md px-3 py-2 text-sm font-mono"
            />
          </div>

          {isAttack && (
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={isCritical}
                onChange={(e) => setIsCritical(e.target.checked)}
                className="w-4 h-4"
              />
              <span>{t('character.spells.roll_damage.critical')}</span>
            </label>
          )}

          <m.button
            type="button"
            onClick={handleRoll}
            disabled={mutation.isPending}
            whileTap={{ scale: 0.97 }}
            className="w-full inline-flex items-center justify-center gap-2 bg-gradient-to-r from-dnd-gold-deep to-dnd-gold-bright text-black px-4 py-3 rounded-md font-cinzel font-bold uppercase tracking-widest disabled:opacity-60"
          >
            <Dices size={18} />
            {t('character.spells.roll_damage.roll_button')}
          </m.button>
        </div>
      ) : (
        <div className="space-y-4 p-1">
          <div className="text-center">
            <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim mb-2">
              {result.breakdown}
            </p>
            {result.damage_type && (
              <p className="text-sm italic text-dnd-text-muted mb-3">
                {t(`character.inventory.damage_types.dmg_${result.damage_type}`, { defaultValue: result.damage_type })}
              </p>
            )}
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-dnd-surface border border-dnd-crimson/40 rounded-md p-3 text-center">
              <Swords size={16} className="mx-auto text-[var(--dnd-crimson-bright)]" />
              <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim mt-1">
                {t('character.spells.roll_damage.full_damage')}
              </p>
              <p className="text-2xl font-display font-black text-dnd-text mt-0.5">
                {result.total}
              </p>
            </div>
            {!isAttack && (
              <div className="bg-dnd-surface border border-dnd-cobalt/40 rounded-md p-3 text-center">
                <Shield size={16} className="mx-auto text-[var(--dnd-cobalt-bright)]" />
                <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim mt-1">
                  {t('character.spells.roll_damage.half_damage')}
                </p>
                <p className="text-2xl font-display font-black text-dnd-text mt-0.5">
                  {result.half_damage}
                </p>
              </div>
            )}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={reset}
              className="flex-1 px-3 py-2 rounded-md bg-dnd-surface border border-dnd-border text-sm"
            >
              {t('character.spells.roll_damage.reroll')}
            </button>
            <button
              type="button"
              onClick={handleClose}
              className="flex-1 px-3 py-2 rounded-md bg-dnd-surface border border-dnd-border text-sm"
            >
              {t('character.spells.roll_damage.close')}
            </button>
          </div>
        </div>
      )}
    </Sheet>
  )
}

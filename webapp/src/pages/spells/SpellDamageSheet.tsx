import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { m } from 'framer-motion'
import {
  GiPerspectiveDiceSixFacesRandom as Dices, GiCrossedSwords as Swords,
  GiCheckedShield as Shield,
} from 'react-icons/gi'
import { api } from '@/api/client'
import type { Spell, RollDamageRequest, RollDamageResult, CharacterFull } from '@/types'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import { haptic } from '@/auth/telegram'
import { useDiceAnimation } from '@/dice/useDiceAnimation'
import { useDiceSettings } from '@/store/diceSettings'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import type { DiceKind } from '@/dice/types'

const ALLOWED_DICE_KINDS: DiceKind[] = ['d4', 'd6', 'd8', 'd10', 'd12', 'd20', 'd100']
const isAllowedDiceKind = (k: string | null | undefined): k is DiceKind =>
  typeof k === 'string' && (ALLOWED_DICE_KINDS as string[]).includes(k)

const DICE_RE = /^(\d+)d(\d+)([+-]\d+)?$/i

function parseDice(notation: string | null | undefined): { count: number; sides: number } | null {
  if (!notation) return null
  const m = DICE_RE.exec(notation.trim())
  if (!m) return null
  return { count: parseInt(m[1], 10), sides: parseInt(m[2], 10) }
}

interface SpellDamageSheetProps {
  charId: number
  spell: Spell | null
  slotLevel: number | null
  /** Lancio rituale: nessuno slot consumato al Roll (spec 2026-06-10). */
  asRitual?: boolean
  onClose: () => void
}

export default function SpellDamageSheet({
  charId,
  spell,
  slotLevel,
  asRitual = false,
  onClose,
}: SpellDamageSheetProps) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [extraDice, setExtraDice] = useState('')
  const [isCritical, setIsCritical] = useState(false)
  const [result, setResult] = useState<RollDamageResult | null>(null)
  const [slotConsumed, setSlotConsumed] = useState(false)
  const [showNoSlotWarning, setShowNoSlotWarning] = useState(false)

  // Reset the form whenever a different spell is opened (identity tracked by id).
  const spellId = spell?.id
  useEffect(() => {
    if (spellId != null) {
      setExtraDice('')
      setIsCritical(false)
      setResult(null)
      setSlotConsumed(false)
      setShowNoSlotWarning(false)
    }
  }, [spellId])

  const dice = useDiceAnimation()
  const animate3d = useDiceSettings((s) => s.animate3d)
  const reducedMotion = useReducedMotion()

  const effectiveCastingLevel = (slotLevel && slotLevel > 0) ? slotLevel : (spell?.level ?? 0)

  const mutation = useMutation({
    mutationFn: async (body: RollDamageRequest) => {
      if (!spell) throw new Error('no spell')

      if (asRitual && !slotConsumed) {
        // Rituale: nessuno slot, il BE registra il lancio e attiva la concentrazione.
        const updated = await api.spells.use(charId, spell.id, null, true)
        qc.setQueryData(['character', charId], updated)
        setSlotConsumed(true)
      } else if (slotLevel != null && slotLevel >= 1 && !slotConsumed) {
        // Consume the spell slot only on the first successful roll for leveled spells.
        let updated: CharacterFull = await api.spells.use(charId, spell.id, slotLevel)
        if (spell.is_concentration) {
          updated = await api.spells.updateConcentration(charId, spell.id)
        }
        qc.setQueryData(['character', charId], updated)
        setSlotConsumed(true)
      } else if (slotLevel === 0 && spell.level === 0 && spell.is_concentration && !slotConsumed) {
        // Cantrip with concentration: still flip concentration on first roll, no slot consumed.
        const updated = await api.spells.updateConcentration(charId, spell.id)
        qc.setQueryData(['character', charId], updated)
        setSlotConsumed(true)
      }

      const useAnimation = animate3d && !reducedMotion
      let main_rolls: number[] | undefined
      let extra_rolls: number[] | undefined

      if (useAnimation) {
        const main = parseDice(spell.damage_dice)
        const extra = parseDice(body.extra_dice ?? null)
        if (main && isAllowedDiceKind(`d${main.sides}`)) {
          const mainCount = body.is_critical ? main.count * 2 : main.count
          const groups: { kind: DiceKind; count: number }[] = [
            { kind: `d${main.sides}` as DiceKind, count: mainCount },
          ]
          let extraCount = 0
          if (extra && isAllowedDiceKind(`d${extra.sides}`)) {
            extraCount = body.is_critical ? extra.count * 2 : extra.count
            groups.push({ kind: `d${extra.sides}` as DiceKind, count: extraCount })
          }
          const detected = await dice.playAndCollect(groups)
          main_rolls = detected.filter((d) => d.groupIndex === 0).map((d) => d.value)
          if (extraCount > 0) {
            extra_rolls = detected.filter((d) => d.groupIndex === 1).map((d) => d.value)
          }
          if (main_rolls.length !== mainCount) main_rolls = undefined
          if (extra_rolls && extra_rolls.length !== extraCount) extra_rolls = undefined
        }
      }

      return api.spells.rollDamage(charId, spell.id, {
        ...body,
        main_rolls,
        extra_rolls,
      })
    },
    onSuccess: (data) => {
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
  const isCantrip = spell.level === 0

  const handleRoll = () => {
    mutation.mutate({
      casting_level: effectiveCastingLevel,
      extra_dice: extraDice || undefined,
      is_critical: isCritical,
    })
  }

  const reset = () => {
    setResult(null)
    setExtraDice('')
    setIsCritical(false)
  }

  const handleReroll = () => {
    if (asRitual || slotLevel == null || slotLevel === 0) {
      // Rituale o trucchetto: nessuno slot coinvolto.
      reset()
      return
    }
    const character = qc.getQueryData<CharacterFull>(['character', charId])
    const slot = character?.spell_slots?.find((s) => s.level === slotLevel)
    const hasSlot = !!slot && slot.available > 0
    if (hasSlot) {
      // Allow the next roll to consume a fresh slot.
      setSlotConsumed(false)
      reset()
    } else {
      setShowNoSlotWarning(true)
    }
  }

  const handleCloseNoSlotWarning = () => {
    setShowNoSlotWarning(false)
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
          {!isCantrip && (
            <div>
              <label className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim">
                {t('character.spells.roll_damage.casting_level')}
              </label>
              <div className="mt-1 text-center font-display text-xl font-bold">
                {t('character.slots.level', { level: effectiveCastingLevel })}
              </div>
            </div>
          )}

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
          {showNoSlotWarning && slotLevel != null && slotLevel >= 1 && (
            <div className="rounded-xl border border-dnd-crimson/40 bg-dnd-crimson/10 p-3 space-y-1.5">
              <p className="font-cinzel text-xs uppercase tracking-widest text-dnd-crimson-bright">
                {t('character.spells.roll_damage.no_slots_warning_title')}
              </p>
              <p className="text-sm text-dnd-text-muted font-body">
                {t('character.spells.roll_damage.no_slots_warning_body', { level: slotLevel })}
              </p>
              <Button
                variant="ghost"
                size="sm"
                fullWidth
                onClick={handleCloseNoSlotWarning}
              >
                {t('character.spells.roll_damage.close')}
              </Button>
            </div>
          )}
          <div className="flex gap-2">
            <Button variant="secondary" fullWidth onClick={handleReroll}>
              {t('character.spells.roll_damage.reroll')}
            </Button>
            <Button variant="secondary" fullWidth onClick={handleClose}>
              {t('character.spells.roll_damage.close')}
            </Button>
          </div>
        </div>
      )}
    </Sheet>
  )
}

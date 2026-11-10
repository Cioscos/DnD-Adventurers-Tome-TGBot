import { askRollOptions, castSpell, CastCancelled, refreshAfterOptions, useEffectPickStore } from '@/lib/rollOptions'
import { notifyCastError } from '@/lib/mutationError'
import AfterDamageOptions from '@/components/rules/AfterDamageOptions'
import { rerollDiceOf, sidesOf } from '@/lib/rollOptions'
import RollNotes from '@/components/rules/RollNotes'
import type { OptionResult } from '@/api/client'
import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  GiPerspectiveDiceSixFacesRandom as Dices, GiCrossedSwords as Swords,
  GiCheckedShield as Shield,
} from 'react-icons/gi'
import { api, ApiError } from '@/api/client'
import type { Spell, RollDamageRequest, RollDamageResult, CharacterFull } from '@/types'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import { isAttackSpell } from '@/lib/spellType'
import { haptic } from '@/auth/telegram'
import { rollValues } from '@/dice/d100'
import { useDiceAnimation } from '@/dice/useDiceAnimation'
import { useDiceSettings } from '@/store/diceSettings'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import type { DiceKind } from '@/dice/types'
import { upcastExtraDice } from '@/lib/srd/catalog'
import { cantripMultiplier, totalLevelOf } from '@/lib/dnd'

const ALLOWED_DICE_KINDS: DiceKind[] = ['d4', 'd6', 'd8', 'd10', 'd12', 'd20', 'd100']
const isAllowedDiceKind = (k: string | null | undefined): k is DiceKind =>
  typeof k === 'string' && (ALLOWED_DICE_KINDS as string[]).includes(k)

const DICE_RE = /^(\d+)d(\d+)([+-]\d+)?$/i

/** Il lancio è andato, ma i dadi di danno dell'incantesimo non sono tirabili dal server. */
class DamageUnrollable extends Error {}

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
  /** Il pool scelto: patto e normali possono avere lo stesso livello. */
  slotId?: number
  /** Lancio coi punti ki: i ki in più scelti. Il primo tiro spende i ki, non uno slot; `slotLevel` è il livello raggiunto. */
  kiExtra?: number | null
  /** Lancio senza slot (Arcanum Mistico, a volontà): il primo tiro fa il lancio gratuito e spende ciò che il privilegio richiede. */
  freeCast?: boolean
  /** Lancio rituale: nessuno slot consumato al Roll (spec 2026-06-10). */
  asRitual?: boolean
  /** Slot/rituale/concentrazione già consumati dal tiro per colpire: il Roll non li tocca. */
  slotAlreadyConsumed?: boolean
  /** 20 naturale al tiro per colpire: i dadi raddoppiano. Il critico viene solo da lì (regole 5e). */
  initialCritical?: boolean
  onClose: () => void
  /** Torna alla scelta dello slot; assente se non c'è un passo precedente. */
  onBack?: () => void
}

export default function SpellDamageSheet({
  charId,
  spell,
  slotLevel,
  slotId,
  kiExtra = null,
  freeCast = false,
  asRitual = false,
  slotAlreadyConsumed = false,
  initialCritical = false,
  onClose,
  onBack,
}: SpellDamageSheetProps) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [extraDice, setExtraDice] = useState('')
  // Seconda parte del danno dell'incantesimo (Colpo infuocato: fuoco e radioso); se ha più tipi, sceglie il giocatore.
  const secondTypes = (spell?.extra_damage_type ?? '').split('|').filter(Boolean)
  const [secondType, setSecondType] = useState('')
  const [unrollable, setUnrollable] = useState(false)
  // Il tipo scelto al lancio, mostrato solo a lancio confermato dal server (un lancio rifiutato non ne ha salvato nessuno).
  const [slotConsumed, setSlotConsumed] = useState(false)
  const pickedType = useEffectPickStore((s) => (spell && (slotConsumed || slotAlreadyConsumed) ? s.picked[spell.id]?.choices?.damage_type : undefined))
  const isCritical = initialCritical
  const [result, setResult] = useState<RollDamageResult | null>(null)
  const [castNotes, setCastNotes] = useState<OptionResult | undefined>(undefined)
  const [showNoSlotWarning, setShowNoSlotWarning] = useState(false)

  // Reset the form whenever a different spell is opened (identity tracked by id).
  const spellId = spell?.id
  useEffect(() => {
    if (spellId != null) {
      setExtraDice('')
      setSecondType('')
      setUnrollable(false)
      setResult(null)
      setSlotConsumed(slotAlreadyConsumed)
      setCastNotes(undefined)
      setShowNoSlotWarning(false)
    }
  }, [spellId, slotAlreadyConsumed])

  const dice = useDiceAnimation()
  const animate3d = useDiceSettings((s) => s.animate3d)
  const reducedMotion = useReducedMotion()

  const effectiveCastingLevel = (slotLevel && slotLevel > 0) ? slotLevel : (spell?.level ?? 0)

  const castRefused = useRef(false)
  const mutation = useMutation({
    mutationFn: async (body: RollDamageRequest) => {
      if (!spell) throw new Error('no spell')

      // Il tiro per colpire (/attack) ha già fatto il lancio; altrimenti lo fa il primo tiro, una volta sola.
      // Slot, rituale o trucchetto: il server consuma il dovuto e avvia la concentrazione col suo contatore.
      let cast = slotAlreadyConsumed || slotConsumed
      if (!cast && (asRitual || spell.level === 0 || kiExtra != null || freeCast || (slotLevel != null && slotLevel >= 1))) {
        // Se il lancio fallisce (409...) nessun tipo è stato salvato: la scelta non resta nello store.
        const updated = await castSpell(charId, spell.id, kiExtra != null
          ? { ki: true, ki_extra: kiExtra, slot_level: null, as_ritual: false }
          : freeCast
            ? { free_cast: true, slot_level: null, as_ritual: false }
          : asRitual
            ? { as_ritual: true, slot_level: null }
            : { slot_id: slotId, slot_level: spell.level === 0 ? null : slotLevel, as_ritual: false }).catch((err) => {
          useEffectPickStore.setState(({ picked }) => ({ picked: Object.fromEntries(Object.entries(picked).filter(([id]) => Number(id) !== spell.id)) }))
          castRefused.current = true
          throw err
        })
        cast = true
        qc.setQueryData(['character', charId], updated)
        if (updated.damage_unrollable) throw new DamageUnrollable()  // lanciato, ma questi dadi il server non li sa tirare
        qc.invalidateQueries({ queryKey: ['turn-state', charId] })
        refreshAfterOptions(qc, charId, updated.option_result)
        setCastNotes(updated.option_result ?? undefined)
        setSlotConsumed(true)
      }

      // Il tipo scelto al lancio (Sfera Cromatica...): il server lo riconvalida e i privilegi che lo leggono lo vedono.
      const chosenType = cast ? useEffectPickStore.getState().picked[spell.id]?.choices?.damage_type : undefined
      const choice = await askRollOptions(charId, { roll: 'spell_damage', spell_id: spell.id, casting_level: effectiveCastingLevel, ...(chosenType ? { damage_type: chosenType } : {}) })
      const useAnimation = animate3d && !reducedMotion
      let main_rolls: number[] | undefined
      let extra_rolls: number[] | undefined

      if (useAnimation) {
        const main = parseDice(spell.damage_dice)
        const second = parseDice(spell.extra_damage_dice)
        const manual = parseDice(body.extra_dice ?? null)
        if (main && isAllowedDiceKind(`d${main.sides}`)) {
          const cached = qc.getQueryData<CharacterFull>(['character', charId])
          const scaled = (spell.level === 0 ? main.count * cantripMultiplier(totalLevelOf(cached?.classes)) : main.count)
            + upcastExtraDice(spell, effectiveCastingLevel, main.sides)
          const mainCount = body.is_critical ? scaled * 2 : scaled
          const groups: { kind: DiceKind; count: number }[] = [
            { kind: `d${main.sides}` as DiceKind, count: mainCount },
          ]
          // Dopo i dadi principali: prima la seconda parte dell'incantesimo, poi i dadi scritti a mano (stesso ordine del server).
          let extraCount = 0
          let extraOk = true
          for (const part of [second, manual]) {
            if (!part) continue
            if (!isAllowedDiceKind(`d${part.sides}`)) { extraOk = false; continue }
            const count = body.is_critical ? part.count * 2 : part.count
            extraCount += count
            groups.push({ kind: `d${part.sides}` as DiceKind, count: count })
          }
          // I dadi 3D sono sopra gli sheet (z-[90]): lo sheet resta aperto sotto.
          const detected = await dice.playAndCollect(groups)
          const valuesOf = (groupIndex: number) =>
            rollValues(
              groups[groupIndex].kind,
              detected.filter((d) => d.groupIndex === groupIndex).map((d) => d.value),
            )
          main_rolls = valuesOf(0)
          if (extraCount > 0 && extraOk) {
            extra_rolls = []
            for (let g = 1; g < groups.length; g++) extra_rolls.push(...valuesOf(g))
          }
          if (main_rolls.length !== mainCount) main_rolls = undefined
          if (extra_rolls && extra_rolls.length !== extraCount) extra_rolls = undefined
        }
      }

      return api.spells.rollDamage(charId, spell.id, {
        ...body,
        ...(chosenType ? { damage_type: chosenType } : {}),
        main_rolls,
        extra_rolls,
        ...(choice.options.length > 0 ? choice : {}),
      })
    },
    onSuccess: (data) => {
      haptic.success()
      refreshAfterOptions(qc, charId, data.option_result)
      setResult(data)
    },
    onError: (err) => {
      const code = err instanceof ApiError ? (err.detail as { code?: string } | null)?.code : undefined
      if (err instanceof DamageUnrollable || code === 'bad_damage_dice') setUnrollable(true)  // un testo suo, non «controlla la connessione»
      else if (!(err instanceof CastCancelled)) notifyCastError(err)
      // Un lancio rifiutato ha perso le scelte (tipo, bersagli): riprovare da qui darebbe un altro errore, si riparte dal lancio.
      if (castRefused.current) { castRefused.current = false; handleClose() }
    },
  })

  if (!spell) return null

  const isAttack = isAttackSpell(spell) || !spell.attack_save?.trim()
  const isCantrip = spell.level === 0
  const autoUpcast = parseDice(spell.higher_levels_dice)
  const autoExtra = autoUpcast ? upcastExtraDice(spell, effectiveCastingLevel, autoUpcast.sides) : 0

  const handleRoll = () => {
    mutation.mutate({
      casting_level: effectiveCastingLevel,
      // i dadi scritti a mano si sommano alla seconda parte dell'incantesimo, che il server tira da sé
      extra_dice: extraDice || undefined,
      ...(secondTypes.length > 1 ? { extra_damage_type: secondType || secondTypes[0] } : {}),
      is_critical: isCritical,
    })
  }

  const reset = () => {
    setResult(null)
    setExtraDice('')
  }

  const handleReroll = () => {
    if (kiExtra != null && !slotAlreadyConsumed) {
      // Un nuovo lancio spende altri ki: serve che ne restino (il server li ricontrolla comunque).
      const info = qc.getQueryData<CharacterFull>(['character', charId])?.spells?.find((s) => s.id === spell?.id)?.ki_cast
      if (info && info.ki_left >= info.cost + kiExtra) {
        setSlotConsumed(false)
        reset()
      } else {
        setShowNoSlotWarning(true)
      }
      return
    }
    if (freeCast && !slotAlreadyConsumed) {
      // Un nuovo tiro sarebbe un nuovo lancio gratuito: l'uso del privilegio è già speso.
      setShowNoSlotWarning(true)
      return
    }
    if (slotAlreadyConsumed || asRitual || slotLevel == null || slotLevel === 0) {
      // Dopo un tiro per colpire, rituale o trucchetto: nessuno slot coinvolto.
      reset()
      return
    }
    const character = qc.getQueryData<CharacterFull>(['character', charId])
    const slot = character?.spell_slots?.find((s) => (slotId != null ? s.id === slotId : s.level === slotLevel))
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

  // Corpo del passo "danni" dello sheet di lancio (lo sheet lo monta useCastFlow).
  return (
    <>
      {unrollable ? (
        <div className="space-y-4 p-5">
          <p className="text-sm text-center font-body text-dnd-text">{t('character.spells.roll_damage.unrollable')}</p>
          <Button variant="secondary" fullWidth onClick={handleClose}>{t('character.spells.roll_damage.close')}</Button>
        </div>
      ) : !result ? (
        <div className="space-y-4 p-5">
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

          {pickedType && (
            <p className="text-sm text-center font-body text-dnd-text">
              {t('character.spells.roll_damage.chosen_type', { type: t(`character.inventory.damage_types.dmg_${pickedType}`, { defaultValue: pickedType }) })}
            </p>
          )}

          {autoExtra > 0 && (
            <p className="text-sm text-dnd-text-muted font-body italic text-center">
              {t('character.spells.upcast_auto', { dice: spell.higher_levels_dice })}
            </p>
          )}

          {spell.extra_damage_dice && (
            <div className="space-y-2">
              <p className="text-sm text-center font-body text-dnd-text">
                {t('character.spells.roll_damage.second_part', {
                  dice: spell.extra_damage_dice,
                  type: secondTypes.map((x) => t(`character.inventory.damage_types.dmg_${x}`, { defaultValue: x })).join(' / '),
                })}
              </p>
              {secondTypes.length > 1 && (
                <div className="flex gap-2">
                  {secondTypes.map((x) => (
                    <Button key={x} variant={(secondType || secondTypes[0]) === x ? 'primary' : 'secondary'} fullWidth onClick={() => setSecondType(x)}>
                      {t(`character.inventory.damage_types.dmg_${x}`, { defaultValue: x })}
                    </Button>
                  ))}
                </div>
              )}
            </div>
          )}

          <Input
            label={t('character.spells.roll_damage.extra_dice')}
            value={extraDice}
            onChange={setExtraDice}
            placeholder={t('character.spells.roll_damage.extra_dice_placeholder')}
          />

          {isCritical && (
            <p className="text-sm text-center font-semibold text-dnd-crimson-bright">
              {t('character.spells.roll_damage.critical')}
            </p>
          )}

          <Button
            variant="primary"
            fullWidth
            icon={<Dices size={18} />}
            onClick={handleRoll}
            loading={mutation.isPending}
            haptic="medium"
          >
            {t('character.spells.roll_damage.roll_button')}
          </Button>
          {onBack && (
            <Button variant="ghost" fullWidth onClick={onBack} disabled={mutation.isPending}>
              {t('common.back')}
            </Button>
          )}
        </div>
      ) : (
        <div className="space-y-4 p-5">
          <div className="text-center">
            <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim mb-2">
              {result.breakdown}
            </p>
            {(result.parts?.length ?? 0) > 1 ? (
              <ul className="mb-3 space-y-0.5 text-sm italic text-dnd-text-muted">
                {result.parts!.map((p) => (
                  <li key={p.label}>
                    {p.type ? t(`character.inventory.damage_types.dmg_${p.type}`, { defaultValue: p.type }) : t('character.spells.roll_damage.extra_dice')}
                    {' '}({p.rolls.join(' + ')})
                  </li>
                ))}
              </ul>
            ) : result.damage_type && (
              <p className="text-sm italic text-dnd-text-muted mb-3">
                {t(`character.inventory.damage_types.dmg_${result.damage_type}`, { defaultValue: result.damage_type })}
              </p>
            )}
          </div>
          <div className="grid grid-cols-2 gap-2">
            {/* «Pieno/Metà» ha senso solo per le spell con TS: per gli attacchi
                la card è una sola, a tutta larghezza, con label «Danno». */}
            <div className={`bg-dnd-surface border border-dnd-crimson/40 rounded-md p-3 text-center ${isAttack ? 'col-span-2' : ''}`}>
              <Swords size={16} className="mx-auto text-dnd-crimson-bright" />
              <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim mt-1">
                {isAttack
                  ? t('character.spells.roll_damage.damage')
                  : t('character.spells.roll_damage.full_damage')}
              </p>
              <p className="text-2xl font-display font-black text-dnd-text mt-0.5">
                {result.total}
              </p>
            </div>
            {!isAttack && (
              <div className="bg-dnd-surface border border-dnd-cobalt/40 rounded-md p-3 text-center">
                <Shield size={16} className="mx-auto text-dnd-cobalt-bright" />
                <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim mt-1">
                  {t('character.spells.roll_damage.half_damage')}
                </p>
                <p className="text-2xl font-display font-black text-dnd-text mt-0.5">
                  {result.half_damage}
                </p>
              </div>
            )}
            {result.save_success_damage != null && (
              <p data-testid="potent-cantrip" className="text-xs text-dnd-text-muted font-body text-center">
                {t('character.spells.roll_damage.potent_cantrip', { n: result.save_success_damage })}
              </p>
            )}
          </div>
          {result.twinned_damage && (
            <div className="bg-dnd-surface border border-dnd-border rounded-md p-3 text-center">
              <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim">{t('character.spells.twinned_damage')}</p>
              <p className="text-sm text-dnd-text-muted font-body tabular-nums">{result.twinned_damage.rolls.join(' + ')}</p>
              <p className="text-2xl font-display font-black text-dnd-text mt-0.5 tabular-nums">{result.twinned_damage.total}</p>
            </div>
          )}
          <RollNotes charId={charId} optionResult={castNotes} />
          <RollNotes charId={charId} optionResult={result.option_result} />  {/* ciò che è avvenuto col danno (Saturazione Magica: i necrotici a sé) */}
          <AfterDamageOptions
            charId={charId}
            query={{ roll: 'spell_damage', spell_id: spell.id, ...(result.damage_type ? { damage_type: result.damage_type } : {}) }}
            dice={result.reroll_dice ? rerollDiceOf(result.reroll_dice) : [
              ...(result.main_rolls ?? []).map((value, index) => ({ value, index, sides: sidesOf(result.main_kind) })),
              ...(result.extra_rolls ?? []).map((value, i) => ({ value, index: (result.main_rolls ?? []).length + i, sides: sidesOf(result.extra_kind) })),
            ]}
            onResult={(r) => setResult(r as RollDamageResult)}
          />
          {showNoSlotWarning && slotLevel != null && slotLevel >= 1 && (
            <div className="rounded-xl border border-dnd-crimson/40 bg-dnd-crimson/10 p-3 space-y-1.5">
              <p className="font-cinzel text-xs uppercase tracking-widest text-dnd-crimson-bright">
                {t('character.spells.roll_damage.no_slots_warning_title')}
              </p>
              <p className="text-sm text-dnd-text-muted font-body">
                {kiExtra != null
                  ? t('character.spells.roll_damage.no_ki_warning_body')
                  : t('character.spells.roll_damage.no_slots_warning_body', { level: slotLevel })}
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
    </>
  )
}

import { notifyMutationError } from '@/lib/mutationError'
import { canRerollInspiration, askRollOptions, castSpell, CastCancelled, prepareCast, refreshAfterOptions } from '@/lib/rollOptions'
import { useState, useCallback, type ReactNode } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { api, ApiError } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { isAttackSpell } from '@/lib/spellType'
import { m, AnimatePresence } from 'framer-motion'
import Button from '@/components/ui/Button'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import Sheet from '@/components/ui/Sheet'
import RollNotes from '@/components/rules/RollNotes'
import type { OptionResult } from '@/api/client'
import { useAnimatedRoll } from '@/dice/useAnimatedRoll'
import { useD20Roll, d20Arg, type RollMode } from '@/hooks/useD20Roll'
import CastSpellModal from '@/pages/spells/CastSpellModal'
import AfterRollOptions from '@/components/rules/AfterRollOptions'
import SpellAttackModal from '@/pages/spells/SpellAttackModal'
import SpellDamageSheet from '@/pages/spells/SpellDamageSheet'
import SpellHealingSheet from '@/pages/spells/SpellHealingSheet'
import { isHealingSpell } from '@/lib/spellHealing'
import type { CharacterFull, Spell, SpellAttackResult, SpellSlot } from '@/types'

// Avanti (slot → danni) il pannello entra da destra; indietro da sinistra.
const STEP_VARIANTS = {
  enter: (dir: number) => ({ opacity: 0, x: 32 * dir }),
  center: { opacity: 1, x: 0 },
  exit: (dir: number) => ({ opacity: 0, x: -32 * dir }),
}

type AttackCast = { spell: Spell; slot: SpellSlot | null; ritual: boolean; mode: RollMode }
type AttackState = AttackCast & { result: SpellAttackResult; wasRerolled: boolean }

export interface CastFlow {
  /** Avvia il flusso di lancio per un incantesimo (identico a "Usa" nella pagina Spells). */
  beginCast: (spell: Spell, mode?: RollMode) => void
  /** Pending dei percorsi senza sheet intermedio: trucchetto con concentrazione senza danno, tiro per colpire. */
  isSpellPending: (spellId: number) => boolean
  /** Sheet/modal del flusso: il chiamante li monta una volta nel proprio JSX. */
  elements: ReactNode
}

/** Flusso di cast condiviso fra la pagina Spells e le Azioni rapide della home
 *  (spec 2026-07-17): cantrip vs livellato, scelta slot (incluso "crea slot" con
 *  switch a modalità manuale), avviso non preparato (eccezione Mago sui rituali),
 *  rituale, sheet danni con consumo slot differito, concentrazione.
 *  Incantesimi d'attacco (spec 2026-10-30): d20 dopo la scelta dello slot, poi
 *  esito e danno con slot già consumato. Lanci senza danno: toast di conferma. */
export function useCastFlow(charId: number, char: CharacterFull | undefined): CastFlow {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const rollDice = useAnimatedRoll()
  const rollD20 = useD20Roll()
  // Modalità d20 scelta alla pressione di "Usa": resta valida durante la scelta dello slot.
  const [castMode, setCastMode] = useState<RollMode>('normal')

  const [castingSpell, setCastingSpell] = useState<Spell | null>(null)
  const [rollDamageSpell, setRollDamageSpell] = useState<Spell | null>(null)
  const [pendingSlotLevel, setPendingSlotLevel] = useState<number | null>(null)
  const [pendingSlotId, setPendingSlotId] = useState<number | undefined>(undefined)
  // Lancio coi punti ki: i ki in più scelti (uno per livello dell'incantesimo in più), al posto di slot e rituale.
  const [pendingKi, setPendingKi] = useState<number | null>(null)
  // Esito delle opzioni di un lancio senza danno: effetti e bersaglio da mostrare.
  const [castNotes, setCastNotes] = useState<OptionResult | null>(null)
  const [pendingRitual, setPendingRitual] = useState(false)
  const [confirmCast, setConfirmCast] = useState<
    { spell: Spell; slot: SpellSlot } | null
  >(null)
  const [attackState, setAttackState] = useState<AttackState | null>(null)
  // Danno dopo il tiro per colpire: slot già consumato, critico preimpostato.
  const [damageAfterAttack, setDamageAfterAttack] = useState<{ critical: boolean } | null>(null)

  const spellcasting = char?.spellcasting ?? null
  /** Uno stato attivo autorizza questo incantesimo senza slot (Lettura del Pensiero): il server lo ricontrolla. */
  const freeCastFor = (spell: Spell) =>
    !!spell.at_will || (!!spell.srd_index && (char?.active_states ?? []).some((s) => (s.data as { free_cast?: string } | undefined)?.free_cast === spell.srd_index))
  const spellSlots: SpellSlot[] = char?.spell_slots ?? []

  // Conferma dei lanci senza danno: nome + slot/rituale + concentrazione.
  const confirmCastDone = useCallback((spell: Spell, slotLevel: number | null, ritual: boolean, ki: number | null = null) => {
    let msg = t('character.spells.cast_done', { name: spell.name })
    if (slotLevel != null && slotLevel >= 1) msg += t('character.spells.cast_done_slot', { level: slotLevel })
    if (ki != null && spell.ki_cast) msg += t('character.spells.cast_done_ki', { n: spell.ki_cast.cost + ki })
    if (ritual) msg += t('character.spells.cast_done_ritual')
    if (spell.is_concentration) msg += t('character.spells.cast_done_concentration')
    toast.success(msg)
  }, [t])

  // Lancio senza dadi: slot, rituale o trucchetto. Il server avvia anche la concentrazione col suo contatore.
  const castMutation = useMutation({
    mutationFn: ({ spell, slot, ritual = false, free = false, ki = null }: { spell: Spell; slot?: SpellSlot; ritual?: boolean; free?: boolean; ki?: number | null }) =>
      castSpell(charId, spell.id, ki != null
        ? { slot_level: null, as_ritual: false, ki: true, ki_extra: ki }
        : free
          ? { slot_level: null, as_ritual: false, free_cast: true }
          : { slot_id: slot?.id, slot_level: slot?.level ?? null, as_ritual: ritual }),
    onSuccess: (updated, { spell, slot, ritual = false, ki = null }) => {
      qc.setQueryData(['character', charId], updated)
      qc.invalidateQueries({ queryKey: ['turn-state', charId] })
      setCastingSpell(null)
      haptic.success()
      confirmCastDone(spell, slot?.level ?? null, ritual, ki)
      refreshAfterOptions(qc, charId, updated.option_result)
      if (updated.option_result?.effects?.length || updated.option_result?.targets?.length) setCastNotes(updated.option_result)
    },
    onError: (err) => {
      if (!(err instanceof CastCancelled)) notifyMutationError()
    },
  })

  // Tiro per colpire: il BE consuma slot/rituale e attiva la concentrazione come /use.
  const attackMutation = useMutation({
    mutationFn: async (cast: AttackCast) => {
      const prepared = await prepareCast(charId, cast.spell.id, cast.ritual, cast.slot?.level)
      const choice = await askRollOptions(charId, { roll: 'attack', spell_id: cast.spell.id })
      const roll = d20Arg(cast.mode, await rollD20(cast.mode), choice)
      const result = await api.spells.attack(charId, cast.spell.id, {
        slot_id: cast.slot?.id, slot_level: cast.slot?.level ?? null, ritual: cast.ritual, confirm: prepared.confirm,
        cast_options: prepared.options, cast_option_inputs: prepared.option_inputs,
        ...(typeof roll === 'object' ? roll : { die: roll }),
      })
      return { cast, result }
    },
    onSuccess: ({ cast, result }) => {
      qc.setQueryData(['character', charId], result.character)
      qc.invalidateQueries({ queryKey: ['turn-state', charId] })
      setAttackState({ ...cast, result, wasRerolled: false })
      haptic.success()
    },
    onError: (err) => {
      if (err instanceof CastCancelled) return
      if (err instanceof ApiError && (err.detail as { code?: string } | null)?.code === 'incapacitated') {
        toast.error(t('character.attack.incapacitated'))
      } else {
        notifyMutationError()
      }
    },
  })

  // Reroll con ispirazione: nessuno slot, il BE consuma solo l'ispirazione.
  const attackRerollMutation = useMutation({
    mutationFn: async (spell: Spell) => {
      const die = (await rollDice('d20', 1))?.[0]
      return api.spells.attack(charId, spell.id, {
        slot_level: null, ritual: false, die, with_inspiration: true,
      })
    },
    onSuccess: (result) => {
      qc.setQueryData(['character', charId], result.character)
      setAttackState((prev) => prev && { ...prev, result, wasRerolled: true })
      haptic.success()
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) {
        toast.error(t('character.inspiration.unavailable_error'))
        qc.invalidateQueries({ queryKey: ['character', charId] })
      } else {
        haptic.error()
      }
    },
  })

  // "Crea slot" dal modal di cast quando non ce ne sono: in Auto mode si passa
  // prima a Manual (con avviso), poi si materializza lo slot. Il modal resta
  // aperto così lo slot appena creato diventa selezionabile.
  const createSlotMutation = useMutation({
    mutationFn: async (level: number) => {
      const mode = ((char?.settings as Record<string, unknown> | undefined)?.spell_slots_mode as string | undefined) ?? 'auto'
      if (mode === 'auto') {
        await api.characters.update(charId, {
          settings: { ...(char?.settings ?? {}), spell_slots_mode: 'manual' },
        })
      }
      const existing = (char?.spell_slots ?? []).find((s) => s.level === level && !s.is_pact)
      if (existing) {
        return api.spellSlots.update(charId, existing.id, { total: existing.total + 1 })
      }
      return api.spellSlots.add(charId, level, 1)
    },
    onSuccess: () => {
      const mode = ((char?.settings as Record<string, unknown> | undefined)?.spell_slots_mode as string | undefined) ?? 'auto'
      qc.invalidateQueries({ queryKey: ['character', charId] })
      if (mode === 'auto') toast.info(t('character.spells.create_slot_switches_manual'))
      haptic.success()
    },
  })

  const beginAttack = useCallback((cast: AttackCast) => {
    // Il modal di cast si chiude subito: i dadi 3D non devono finirci dietro.
    setCastingSpell(null)
    attackMutation.mutate(cast)
  }, [attackMutation])

  const beginCast = useCallback((spell: Spell, mode: RollMode = 'normal') => {
    setCastMode(mode)
    if (spell.level === 0) {
      // Trucchetto — nessuno slot; la concentrazione si gestisce nello sheet danni se presente.
      if (isAttackSpell(spell)) {
        beginAttack({ spell, slot: null, ritual: false, mode })
        return
      }
      if (spell.damage_dice || isHealingSpell(spell)) {
        setPendingRitual(false)
        setPendingSlotLevel(0)
        setPendingSlotId(undefined)
        setRollDamageSpell(spell)
        return
      }
      castMutation.mutate({ spell })
      return
    }
    // A volontà (Mille Forme): nessuno slot da scegliere. Solo per i lanci senza tiri: nessun incantesimo a volontà del catalogo li ha.
    if (spell.at_will && !isAttackSpell(spell) && !spell.damage_dice && !isHealingSpell(spell)) {
      castMutation.mutate({ spell, free: true })
      return
    }
    // Livellato — prima si sceglie lo slot.
    setCastingSpell(spell)
  }, [beginAttack, castMutation])

  const needsUnpreparedWarn = useCallback((spell: Spell) =>
    !!spellcasting?.has_preparing_class && spell.level >= 1 && !spell.is_prepared,
  [spellcasting])

  const proceedSlotCast = useCallback((spell: Spell, slot: SpellSlot) => {
    if (isAttackSpell(spell)) {
      beginAttack({ spell, slot, ritual: false, mode: castMode })
      return
    }
    if (spell.damage_dice || isHealingSpell(spell)) {
      // Consumo slot differito al bottone Roll dello sheet danni.
      setPendingRitual(false)
      setPendingSlotLevel(slot.level)
      setPendingSlotId(slot.id)
      setRollDamageSpell(spell)
      return
    }
    castMutation.mutate({ spell, slot })
  }, [beginAttack, castMutation, castMode])

  const proceedRitualCast = useCallback((spell: Spell) => {
    if (isAttackSpell(spell)) {
      beginAttack({ spell, slot: null, ritual: true, mode: castMode })
      return
    }
    if (spell.damage_dice || isHealingSpell(spell)) {
      setPendingRitual(true)
      setPendingSlotLevel(null)
      setPendingSlotId(undefined)
      setRollDamageSpell(spell)
      return
    }
    castMutation.mutate({ spell, ritual: true })
  }, [beginAttack, castMutation, castMode])

  // Coi punti ki: il costo è del privilegio, il server lo ricontrolla. Con i dadi, il lancio avviene al primo tiro (come uno slot).
  const proceedKiCast = useCallback((spell: Spell, extra: number) => {
    if (spell.damage_dice) {
      setPendingRitual(false)
      setPendingSlotLevel(spell.level + extra)
      setPendingSlotId(undefined)
      setPendingKi(extra)
      setRollDamageSpell(spell)
      return
    }
    castMutation.mutate({ spell, ki: extra })
  }, [castMutation])

  const handleCastSlot = useCallback((slot: SpellSlot) => {
    if (!castingSpell) return
    if (needsUnpreparedWarn(castingSpell)) {
      setConfirmCast({ spell: castingSpell, slot })
      return
    }
    proceedSlotCast(castingSpell, slot)
  }, [castingSpell, needsUnpreparedWarn, proceedSlotCast])

  // La preparazione di un rituale la giudica il server, per edizione e classe (`prepareCast`).
  const handleCastRitual = useCallback(() => {
    if (castingSpell) proceedRitualCast(castingSpell)
  }, [castingSpell, proceedRitualCast])

  const availableSlotsFor = (spellLevel: number) =>
    spellSlots
      .filter((s) => s.level >= spellLevel && s.available > 0)
      .sort((a, b) => a.level - b.level)

  const isSpellPending = useCallback((spellId: number) =>
    (castMutation.isPending && castMutation.variables?.spell.id === spellId)
    || (attackMutation.isPending && attackMutation.variables?.spell.id === spellId),
  [castMutation.isPending, castMutation.variables,
    attackMutation.isPending, attackMutation.variables])

  const openDamageAfterAttack = () => {
    if (!attackState) return
    setPendingRitual(attackState.ritual)
    setPendingSlotLevel(attackState.slot?.level ?? 0)
    setPendingSlotId(attackState.slot?.id)
    setDamageAfterAttack({ critical: attackState.result.is_critical })
    setRollDamageSpell(attackState.spell)
    setAttackState(null)
  }

  const closeDamage = () => {
    setRollDamageSpell(null)
    setPendingSlotLevel(null)
    setPendingSlotId(undefined)
    setPendingKi(null)
    setPendingRitual(false)
    setDamageAfterAttack(null)
  }
  const closeCastSheet = () => {
    closeDamage()
    setCastingSpell(null)
  }

  // Slot e danni sono due passi dello stesso sheet: il contenuto scorre, lo sheet resta.
  const step = rollDamageSpell ? 'damage' : castingSpell ? 'slot' : null
  const stepDir = step === 'damage' ? 1 : -1
  const elements = (
    <>
      <Sheet
        open={step !== null}
        onClose={closeCastSheet}
        title={rollDamageSpell
          ? t(isHealingSpell(rollDamageSpell) ? 'character.spells.roll_healing.title' : 'character.spells.roll_damage.title', { name: rollDamageSpell.name })
          : t('character.spells.cast_slot_title')}
      >
        {/* custom: il pannello che esce legge la direzione nuova, non quella del suo ultimo render. */}
        <AnimatePresence mode="wait" initial={false} custom={stepDir}>
          <m.div
            key={step ?? 'none'}
            custom={stepDir}
            variants={STEP_VARIANTS}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: 0.16, ease: 'easeOut' }}
          >
            {step === 'slot' && castingSpell && (
              <CastSpellModal
                spell={castingSpell}
                availableSlots={availableSlotsFor(castingSpell.level)}
                canRitual={!!castingSpell.is_ritual && (!!spellcasting?.has_ritual_caster || !!spellcasting?.ritual_only_spell_ids?.includes(castingSpell.id))}
                onCast={handleCastSlot}
                onCastRitual={handleCastRitual}
                canFreeCast={freeCastFor(castingSpell)}
                onCastFree={() => castMutation.mutate({ spell: castingSpell, free: true })}
                kiCast={castingSpell.ki_cast}
                onCastKi={(extra) => proceedKiCast(castingSpell, extra)}
                onCreateSlot={(level) => createSlotMutation.mutate(level)}
                onCancel={closeCastSheet}
                isPending={castMutation.isPending}
                isCreatingSlot={createSlotMutation.isPending}
              />
            )}
            {step === 'damage' && isHealingSpell(rollDamageSpell) && (
              <SpellHealingSheet
                charId={charId}
                spell={rollDamageSpell}
                slotLevel={pendingSlotLevel}
                slotId={pendingSlotId}
                asRitual={pendingRitual}
                onClose={closeCastSheet}
                onBack={castingSpell ? closeDamage : undefined}
              />
            )}
            {step === 'damage' && !isHealingSpell(rollDamageSpell) && (
              <SpellDamageSheet
                charId={charId}
                spell={rollDamageSpell}
                slotLevel={pendingSlotLevel}
                slotId={pendingSlotId}
                kiExtra={pendingKi}
                asRitual={pendingRitual}
                slotAlreadyConsumed={damageAfterAttack !== null}
                initialCritical={damageAfterAttack?.critical ?? false}
                onClose={closeCastSheet}
                onBack={castingSpell ? closeDamage : undefined}
              />
            )}
          </m.div>
        </AnimatePresence>
      </Sheet>

      <ConfirmSheet
        open={confirmCast !== null}
        onClose={() => setConfirmCast(null)}
        title={t('character.spells.unprepared_cast_title')}
        body={confirmCast
          ? t('character.spells.unprepared_cast_body', { name: confirmCast.spell.name })
          : undefined}
        confirmLabel={t('character.spells.cast_anyway')}
        cancelLabel={t('common.cancel')}
        loading={castMutation.isPending}
        onConfirm={() => {
          if (!confirmCast) return
          proceedSlotCast(confirmCast.spell, confirmCast.slot)
          setConfirmCast(null)
        }}
      />

      <Sheet open={castNotes !== null} onClose={() => setCastNotes(null)} title={t('character.roll_options.title_cast')}>
        <div className="p-5 space-y-3">
          <RollNotes charId={charId} optionResult={castNotes ?? undefined} />
          <Button variant="secondary" fullWidth onClick={() => setCastNotes(null)}>{t('common.close')}</Button>
        </div>
      </Sheet>

      {attackState && (
        <SpellAttackModal
          charId={charId}
          result={attackState.result}
          canRollDamage={!!attackState.spell.damage_dice && !attackState.result.is_fumble}
          onRollDamage={openDamageAfterAttack}
          onClose={() => setAttackState(null)}
          inspirationAvailable={canRerollInspiration(char)}
          isRerolling={attackRerollMutation.isPending}
          wasRerolled={attackState.wasRerolled}
          onInspirationReroll={() => attackRerollMutation.mutate(attackState.spell)}
          afterRollRow={(
            <AfterRollOptions
              charId={charId}
              query={{ roll: 'attack', spell_id: attackState.spell.id }}
              rollToken={`${attackMutation.submittedAt}:${attackRerollMutation.submittedAt}`}
              onResult={(roll) => setAttackState((prev) => prev && {
                ...prev,
                result: {
                  ...prev.result, to_hit_die: roll.die, dice: roll.dice, mode: roll.mode, notes: roll.notes,
                  to_hit_bonus: roll.total - roll.die, to_hit_total: roll.total, is_critical: roll.is_critical,
                  is_fumble: roll.is_fumble, forced_hit: roll.forced_hit,
                },
              })}
            />
          )}
        />
      )}

    </>
  )

  return { beginCast, isSpellPending, elements }
}

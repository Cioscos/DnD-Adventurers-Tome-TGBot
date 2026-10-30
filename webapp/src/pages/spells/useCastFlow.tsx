import { useState, useCallback, type ReactNode } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { api, ApiError } from '@/api/client'
import { haptic } from '@/auth/telegram'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import { useAnimatedRoll } from '@/dice/useAnimatedRoll'
import CastSpellModal from '@/pages/spells/CastSpellModal'
import SpellAttackModal from '@/pages/spells/SpellAttackModal'
import SpellDamageSheet from '@/pages/spells/SpellDamageSheet'
import type { CharacterFull, Spell, SpellAttackResult, SpellSlot } from '@/types'

/** Incantesimo con tiro per colpire: il d20 precede il danno (spec 2026-10-30). */
const isAttackSpell = (spell: Spell) => spell.attack_save?.trim().toUpperCase() === 'ATK'

type AttackCast = { spell: Spell; slotLevel: number | null; ritual: boolean }
type AttackState = AttackCast & { result: SpellAttackResult; wasRerolled: boolean }

export interface CastFlow {
  /** Avvia il flusso di lancio per un incantesimo (identico a "Usa" nella pagina Spells). */
  beginCast: (spell: Spell) => void
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

  const [castingSpell, setCastingSpell] = useState<Spell | null>(null)
  const [rollDamageSpell, setRollDamageSpell] = useState<Spell | null>(null)
  const [pendingSlotLevel, setPendingSlotLevel] = useState<number | null>(null)
  const [pendingRitual, setPendingRitual] = useState(false)
  const [confirmCast, setConfirmCast] = useState<
    { spell: Spell; slotLevel: number | null; ritual: boolean } | null
  >(null)
  const [attackState, setAttackState] = useState<AttackState | null>(null)
  // Danno dopo il tiro per colpire: slot già consumato, critico preimpostato.
  const [damageAfterAttack, setDamageAfterAttack] = useState<{ critical: boolean } | null>(null)

  const spellcasting = char?.spellcasting ?? null
  const spellSlots: SpellSlot[] = char?.spell_slots ?? []

  // Conferma dei lanci senza danno: nome + slot/rituale + concentrazione.
  const confirmCastDone = useCallback((spell: Spell, slotLevel: number | null, ritual: boolean) => {
    let msg = t('character.spells.cast_done', { name: spell.name })
    if (slotLevel != null && slotLevel >= 1) msg += t('character.spells.cast_done_slot', { level: slotLevel })
    if (ritual) msg += t('character.spells.cast_done_ritual')
    if (spell.is_concentration) msg += t('character.spells.cast_done_concentration')
    toast.success(msg)
  }, [t])

  const concentrationMutation = useMutation({
    mutationFn: (spell: Spell) => api.spells.updateConcentration(charId, spell.id),
    onSuccess: (updated, spell) => {
      qc.setQueryData(['character', charId], updated)
      haptic.success()
      confirmCastDone(spell, null, false)
    },
  })

  const castMutation = useMutation({
    mutationFn: async ({ spell, slotLevel }: { spell: Spell; slotLevel: number }) => {
      const updated = await api.spells.use(charId, spell.id, slotLevel)
      if (spell.is_concentration) {
        const conc = await api.spells.updateConcentration(charId, spell.id)
        return { updated: conc, spell }
      }
      return { updated, spell }
    },
    onSuccess: ({ updated, spell }, { slotLevel }) => {
      qc.setQueryData(['character', charId], updated)
      setCastingSpell(null)
      haptic.success()
      confirmCastDone(spell, slotLevel, false)
    },
  })

  const castRitualMutation = useMutation({
    mutationFn: (spell: Spell) => api.spells.use(charId, spell.id, null, true),
    onSuccess: (updated, spell) => {
      qc.setQueryData(['character', charId], updated)
      setCastingSpell(null)
      haptic.success()
      confirmCastDone(spell, null, true)
    },
  })

  // Tiro per colpire: il BE consuma slot/rituale e attiva la concentrazione come /use.
  const attackMutation = useMutation({
    mutationFn: async (cast: AttackCast) => {
      const die = (await rollDice('d20', 1))?.[0]
      const result = await api.spells.attack(charId, cast.spell.id, {
        slot_level: cast.slotLevel, ritual: cast.ritual, die,
      })
      return { cast, result }
    },
    onSuccess: ({ cast, result }) => {
      qc.setQueryData(['character', charId], result.character)
      setAttackState({ ...cast, result, wasRerolled: false })
      haptic.success()
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
      const existing = (char?.spell_slots ?? []).find((s) => s.level === level)
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

  const beginCast = useCallback((spell: Spell) => {
    if (spell.level === 0) {
      // Trucchetto — nessuno slot; la concentrazione si gestisce nello sheet danni se presente.
      if (isAttackSpell(spell)) {
        beginAttack({ spell, slotLevel: null, ritual: false })
        return
      }
      if (spell.damage_dice) {
        setPendingRitual(false)
        setPendingSlotLevel(0)
        setRollDamageSpell(spell)
        return
      }
      if (spell.is_concentration) {
        concentrationMutation.mutate(spell)
      } else {
        haptic.success()
        confirmCastDone(spell, null, false)
      }
      return
    }
    // Livellato — prima si sceglie lo slot.
    setCastingSpell(spell)
  }, [beginAttack, concentrationMutation, confirmCastDone])

  const needsUnpreparedWarn = useCallback((spell: Spell) =>
    !!spellcasting?.has_preparing_class && spell.level >= 1 && !spell.is_prepared,
  [spellcasting])

  const proceedSlotCast = useCallback((spell: Spell, slotLevel: number) => {
    if (isAttackSpell(spell)) {
      beginAttack({ spell, slotLevel, ritual: false })
      return
    }
    if (spell.damage_dice) {
      // Consumo slot differito al bottone Roll dello sheet danni.
      setPendingRitual(false)
      setPendingSlotLevel(slotLevel)
      setRollDamageSpell(spell)
      setCastingSpell(null)
      return
    }
    castMutation.mutate({ spell, slotLevel })
  }, [beginAttack, castMutation])

  const proceedRitualCast = useCallback((spell: Spell) => {
    if (isAttackSpell(spell)) {
      beginAttack({ spell, slotLevel: null, ritual: true })
      return
    }
    if (spell.damage_dice) {
      setPendingRitual(true)
      setPendingSlotLevel(null)
      setRollDamageSpell(spell)
      setCastingSpell(null)
      return
    }
    castRitualMutation.mutate(spell)
  }, [beginAttack, castRitualMutation])

  const handleCastSlot = useCallback((slotLevel: number) => {
    if (!castingSpell) return
    if (needsUnpreparedWarn(castingSpell)) {
      setConfirmCast({ spell: castingSpell, slotLevel, ritual: false })
      return
    }
    proceedSlotCast(castingSpell, slotLevel)
  }, [castingSpell, needsUnpreparedWarn, proceedSlotCast])

  const handleCastRitual = useCallback(() => {
    if (!castingSpell) return
    // RAW: il Mago rituala dal libro anche se non preparato, niente avviso.
    if (needsUnpreparedWarn(castingSpell) && !spellcasting?.has_wizard) {
      setConfirmCast({ spell: castingSpell, slotLevel: null, ritual: true })
      return
    }
    proceedRitualCast(castingSpell)
  }, [castingSpell, needsUnpreparedWarn, spellcasting, proceedRitualCast])

  const availableSlotsFor = (spellLevel: number) =>
    spellSlots
      .filter((s) => s.level >= spellLevel && s.available > 0)
      .sort((a, b) => a.level - b.level)

  const isSpellPending = useCallback((spellId: number) =>
    (concentrationMutation.isPending && concentrationMutation.variables?.id === spellId)
    || (attackMutation.isPending && attackMutation.variables?.spell.id === spellId),
  [concentrationMutation.isPending, concentrationMutation.variables,
    attackMutation.isPending, attackMutation.variables])

  const openDamageAfterAttack = () => {
    if (!attackState) return
    setPendingRitual(attackState.ritual)
    setPendingSlotLevel(attackState.slotLevel ?? 0)
    setDamageAfterAttack({ critical: attackState.result.is_critical })
    setRollDamageSpell(attackState.spell)
    setAttackState(null)
  }

  const elements = (
    <>
      {castingSpell && (
        <CastSpellModal
          spell={castingSpell}
          availableSlots={availableSlotsFor(castingSpell.level)}
          canRitual={!!castingSpell.is_ritual && !!spellcasting?.has_ritual_caster}
          onCast={handleCastSlot}
          onCastRitual={handleCastRitual}
          onCreateSlot={(level) => createSlotMutation.mutate(level)}
          onCancel={() => setCastingSpell(null)}
          isPending={castMutation.isPending || castRitualMutation.isPending}
          isCreatingSlot={createSlotMutation.isPending}
        />
      )}

      <ConfirmSheet
        open={confirmCast !== null}
        onClose={() => setConfirmCast(null)}
        title={t('character.spells.unprepared_cast_title')}
        body={confirmCast
          ? t('character.spells.unprepared_cast_body', { name: confirmCast.spell.name })
          : undefined}
        confirmLabel={t('character.spells.cast_anyway')}
        cancelLabel={t('common.cancel')}
        loading={castMutation.isPending || castRitualMutation.isPending}
        onConfirm={() => {
          if (!confirmCast) return
          if (confirmCast.ritual) proceedRitualCast(confirmCast.spell)
          else if (confirmCast.slotLevel !== null) proceedSlotCast(confirmCast.spell, confirmCast.slotLevel)
          setConfirmCast(null)
        }}
      />

      {attackState && (
        <SpellAttackModal
          result={attackState.result}
          canRollDamage={!!attackState.spell.damage_dice && !attackState.result.is_fumble}
          onRollDamage={openDamageAfterAttack}
          onClose={() => setAttackState(null)}
          inspirationAvailable={!!char?.heroic_inspiration}
          isRerolling={attackRerollMutation.isPending}
          wasRerolled={attackState.wasRerolled}
          onInspirationReroll={() => attackRerollMutation.mutate(attackState.spell)}
        />
      )}

      <SpellDamageSheet
        charId={charId}
        spell={rollDamageSpell}
        slotLevel={pendingSlotLevel}
        asRitual={pendingRitual}
        slotAlreadyConsumed={damageAfterAttack !== null}
        initialCritical={damageAfterAttack?.critical ?? false}
        onClose={() => {
          setRollDamageSpell(null)
          setPendingSlotLevel(null)
          setPendingRitual(false)
          setDamageAfterAttack(null)
        }}
      />
    </>
  )

  return { beginCast, isSpellPending, elements }
}

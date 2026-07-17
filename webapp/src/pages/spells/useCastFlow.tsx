import { useState, useCallback, type ReactNode } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import CastSpellModal from '@/pages/spells/CastSpellModal'
import SpellDamageSheet from '@/pages/spells/SpellDamageSheet'
import type { CharacterFull, Spell, SpellSlot } from '@/types'

export interface CastFlow {
  /** Avvia il flusso di lancio per un incantesimo (identico a "Usa" nella pagina Spells). */
  beginCast: (spell: Spell) => void
  /** Pending del solo percorso senza sheet intermedio (trucchetto con concentrazione, senza danno). */
  isSpellPending: (spellId: number) => boolean
  /** Sheet/modal del flusso: il chiamante li monta una volta nel proprio JSX. */
  elements: ReactNode
}

/** Flusso di cast condiviso fra la pagina Spells e le Azioni rapide della home
 *  (spec 2026-07-17): cantrip vs livellato, scelta slot (incluso "crea slot" con
 *  switch a modalità manuale), avviso non preparato (eccezione Mago sui rituali),
 *  rituale, sheet danni con consumo slot differito, concentrazione. */
export function useCastFlow(charId: number, char: CharacterFull | undefined): CastFlow {
  const { t } = useTranslation()
  const qc = useQueryClient()

  const [castingSpell, setCastingSpell] = useState<Spell | null>(null)
  const [rollDamageSpell, setRollDamageSpell] = useState<Spell | null>(null)
  const [pendingSlotLevel, setPendingSlotLevel] = useState<number | null>(null)
  const [pendingRitual, setPendingRitual] = useState(false)
  const [confirmCast, setConfirmCast] = useState<
    { spell: Spell; slotLevel: number | null; ritual: boolean } | null
  >(null)

  const spellcasting = char?.spellcasting ?? null
  const spellSlots: SpellSlot[] = char?.spell_slots ?? []

  const concentrationMutation = useMutation({
    mutationFn: (spellId: number | null) => api.spells.updateConcentration(charId, spellId),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.success()
    },
    onError: () => haptic.error(),
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
    onSuccess: ({ updated }) => {
      qc.setQueryData(['character', charId], updated)
      setCastingSpell(null)
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const castRitualMutation = useMutation({
    mutationFn: (spell: Spell) => api.spells.use(charId, spell.id, null, true),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setCastingSpell(null)
      haptic.success()
    },
    onError: () => haptic.error(),
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
    onError: () => haptic.error(),
  })

  const beginCast = useCallback((spell: Spell) => {
    if (spell.level === 0) {
      // Trucchetto — nessuno slot; la concentrazione si gestisce nello sheet danni se presente.
      if (spell.damage_dice) {
        setPendingRitual(false)
        setPendingSlotLevel(0)
        setRollDamageSpell(spell)
        return
      }
      if (spell.is_concentration) {
        concentrationMutation.mutate(spell.id)
      } else {
        haptic.success()
      }
      return
    }
    // Livellato — prima si sceglie lo slot.
    setCastingSpell(spell)
  }, [concentrationMutation])

  const needsUnpreparedWarn = useCallback((spell: Spell) =>
    !!spellcasting?.has_preparing_class && spell.level >= 1 && !spell.is_prepared,
  [spellcasting])

  const proceedSlotCast = useCallback((spell: Spell, slotLevel: number) => {
    if (spell.damage_dice) {
      // Consumo slot differito al bottone Roll dello sheet danni.
      setPendingRitual(false)
      setPendingSlotLevel(slotLevel)
      setRollDamageSpell(spell)
      setCastingSpell(null)
      return
    }
    castMutation.mutate({ spell, slotLevel })
  }, [castMutation])

  const proceedRitualCast = useCallback((spell: Spell) => {
    if (spell.damage_dice) {
      setPendingRitual(true)
      setPendingSlotLevel(null)
      setRollDamageSpell(spell)
      setCastingSpell(null)
      return
    }
    castRitualMutation.mutate(spell)
  }, [castRitualMutation])

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

  const isSpellPending = useCallback((spellId: number) => {
    const spell = char?.spells?.find((s) => s.id === spellId)
    return !!spell && spell.level === 0 && !spell.damage_dice && !!spell.is_concentration
      && concentrationMutation.isPending && concentrationMutation.variables === spellId
  }, [char, concentrationMutation.isPending, concentrationMutation.variables])

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

      <SpellDamageSheet
        charId={charId}
        spell={rollDamageSpell}
        slotLevel={pendingSlotLevel}
        asRitual={pendingRitual}
        onClose={() => {
          setRollDamageSpell(null)
          setPendingSlotLevel(null)
          setPendingRitual(false)
        }}
      />
    </>
  )

  return { beginCast, isSpellPending, elements }
}

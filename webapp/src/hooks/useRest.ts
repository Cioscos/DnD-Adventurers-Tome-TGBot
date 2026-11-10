import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api, ApiError } from '@/api/client'
import type { HitDiceSpendResult } from '@/api/client'
import { useAnimatedRoll } from '@/dice/useAnimatedRoll'
import { haptic } from '@/auth/telegram'
import { useToast } from '@/hooks/useToast'
import { notifyMutationError } from '@/lib/mutationError'
import type { MemorizeChoice } from '@/components/character/MemorizeSpellPicker'
import type { CharacterFull } from '@/types'

/** Stato e domande del riposo, uguali per le tre porte (menu, azioni rapide, pagina PF):
 *  interrotto, ha mangiato e bevuto, conferma «troppo presto» e le scelte dei privilegi (`<RestDialogs>`). */
export function useRest(charId: number, char: CharacterFull | undefined, onDone?: () => void) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const rollDice = useAnimatedRoll()
  const [shortRestOpen, setShortRestOpen] = useState(false)
  const [confirmLongRest, setConfirmLongRest] = useState(false)
  const [hitDieResult, setHitDieResult] = useState<HitDiceSpendResult | null>(null)
  const [interrupted, setInterrupted] = useState(false)
  const [ateAndDrank, setAteAndDrank] = useState(true)
  const [tooSoon, setTooSoon] = useState(false)
  const [recovery, setRecovery] = useState<Record<number, number>>({})  // Recupero Naturale: livello -> slot
  const [arcane, setArcane] = useState<Record<number, number>>({})  // Recupero Arcano: livello -> slot
  const [memorize, setMemorize] = useState<MemorizeChoice | null>(null)  // Memorizzare Incantesimo (Mago 2024)
  const [restoration, setRestoration] = useState(0)  // Ripristino Stregonesco: punti stregoneria
  const [reopenTome, setReopenTome] = useState(false)  // Patto del Tomo: le scelte del Libro tornano da fare
  const [tempAllies, setTempAllies] = useState<number[]>([])  // Resilienza Celestiale: PG della serata che ricevono i PF temporanei

  const hitDieMutation = useMutation({
    mutationFn: async ({ classId, count }: { classId: number; count: number }) => {
      const hitDie = char?.classes.find((c) => c.id === classId)?.hit_die
      const rolls = await rollDice(`d${hitDie ?? 8}`, count)
      return api.characters.spendHitDice(charId, classId, count, rolls)
    },
    onSuccess: (result) => {
      setHitDieResult(result)
      qc.invalidateQueries({ queryKey: ['character', charId] })
      haptic.success()
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) {
        toast.error(t('character.quick_actions.hit_die_exhausted'))
        qc.invalidateQueries({ queryKey: ['character', charId] })
      } else {
        notifyMutationError(err)
      }
    },
  })

  const restMutation = useMutation({
    mutationFn: ({ restType, confirmEarly }: { restType: 'long' | 'short'; confirmEarly?: boolean }) =>
      api.characters.rest(charId, restType, {
        interrupted,
        ate_and_drank: ateAndDrank,
        confirm_early: confirmEarly,
        ...(restType === 'short' && Object.keys(recovery).length > 0 ? { natural_recovery: recovery } : {}),
        ...(restType === 'short' && Object.keys(arcane).length > 0 ? { arcane_recovery: arcane } : {}),
        ...(restType === 'short' && restoration > 0 ? { sorcerous_restoration: restoration } : {}),
        ...(restType === 'short' && memorize ? { memorize_spell: memorize } : {}),
        ...(restType === 'long' && reopenTome ? { reopen_tome: true } : {}),
        ...(tempAllies.length > 0 ? { temp_hp_allies: tempAllies } : {}),
      }),
    onError: (err) => {
      const detail = err instanceof ApiError ? err.detail : null
      const code = (detail as { code?: string } | null)?.code
      if (detail === 'long_rest_too_soon') {
        setConfirmLongRest(false)
        setTooSoon(true)
      } else if (detail === 'rest_needs_hp') {
        toast.error(t('character.quick_actions.rest_needs_hp'))
      } else if (code === 'target_dead') {
        toast.error(t('character.quick_actions.rest_target_dead'))
      } else if (code === 'invalid_target') {
        toast.error(t('character.turn.use_errors.invalid_target'))
      } else {
        notifyMutationError(err)
      }
    },
    onSuccess: (updated) => {
      setTooSoon(false)
      setInterrupted(false)
      setAteAndDrank(true)
      setRecovery({})
      setArcane({})
      setRestoration(0)
      setMemorize(null)
      setReopenTome(false)
      setTempAllies([])
      qc.setQueryData(['character', charId], updated)
      qc.invalidateQueries({ queryKey: ['homebrew-resources', charId] })
      setConfirmLongRest(false)
      setShortRestOpen(false)
      onDone?.()
      toast.success(t('character.quick_actions.rest_done'))
      for (const r of updated.temp_received ?? []) {  // il server dice se i PF temporanei sono saliti o se l'altro ne aveva di più
        toast.info(t(r.applied ? 'character.turn.use_temp_received' : 'character.quick_actions.rest_temp_kept', { name: r.name, n: r.given, have: r.temp_hp }))
      }
      haptic.success()
    },
  })

  // Annullare la conferma del riposo lungo azzera anche le domande: la volta dopo non resta «interrotto» a metà.
  const cancelLongRest = () => {
    setConfirmLongRest(false)
    setInterrupted(false)
    setAteAndDrank(true)
  }

  return {
    openShort: () => setShortRestOpen(true),
    openLong: () => setConfirmLongRest(true),
    pending: restMutation.isPending,
    shortRestOpen, setShortRestOpen, confirmLongRest, setConfirmLongRest, cancelLongRest, tooSoon, setTooSoon,
    hitDieResult, setHitDieResult, interrupted, setInterrupted, ateAndDrank, setAteAndDrank,
    recovery, setRecovery, arcane, setArcane, memorize, setMemorize, restoration, setRestoration,
    reopenTome, setReopenTome, tempAllies, setTempAllies, hitDieMutation, restMutation,
  }
}

export type RestState = ReturnType<typeof useRest>

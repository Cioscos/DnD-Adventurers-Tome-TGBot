import { useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api, ApiError } from '@/api/client'
import type { HitDiceSpendResult } from '@/api/client'
import { useAnimatedRoll } from '@/dice/useAnimatedRoll'
import { haptic } from '@/auth/telegram'
import { useToast } from '@/hooks/useToast'
import { notifyMutationError } from '@/lib/mutationError'
import { hitDiceRemaining } from '@/lib/quickActions'
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
  const [resistance, setResistance] = useState('')  // Resilienza Immonda: il tipo di danno scelto finendo il riposo
  const [tempAllies, setTempAllies] = useState<number[]>([])  // Resilienza Celestiale: PG della serata che ricevono i PF temporanei

  // Dadi vita tirati nel modale: si spendono solo con «Riposa»; Annulla li lascia dove sono.
  const [pendingDice, setPendingDice] = useState<Record<number, number[]>>({})
  const hitDieMutation = useMutation({
    mutationFn: async ({ classId, count }: { classId: number; count: number }) => {
      const faces = char?.classes.find((c) => c.id === classId)?.hit_die ?? 8
      // Senza animazione 3D il tiro si fa qui: il valore va mostrato prima di «Riposa», non scelto dal server dopo.
      const rolls = await rollDice(`d${faces}`, count) ?? Array.from({ length: count }, () => 1 + Math.floor(Math.random() * faces))
      return { classId, rolls }
    },
    onSuccess: ({ classId, rolls }) => {
      setPendingDice((p) => ({ ...p, [classId]: [...(p[classId] ?? []), ...rolls] }))
      haptic.light()
    },
    onError: (err) => notifyMutationError(err),
  })

  const spendPendingDice = async (): Promise<HitDiceSpendResult[]> => {
    const spent: HitDiceSpendResult[] = []
    for (const [classId, rolls] of Object.entries(pendingDice)) {
      if (rolls.length === 0) continue
      spent.push(await api.characters.spendHitDice(charId, Number(classId), rolls.length, rolls))
      // speso: un nuovo tentativo dopo un riposo rifiutato non lo spende due volte
      setPendingDice((p) => { const next = { ...p }; delete next[Number(classId)]; return next })
    }
    return spent
  }

  const closeShort = () => {
    setShortRestOpen(false)
    setPendingDice({})
  }

  const restInFlight = useRef(false)  // guardia sincrona: un doppio tocco prima del rerender non invia due POST
  const restMutation = useMutation({
    mutationFn: async ({ restType, confirmEarly }: { restType: 'long' | 'short'; confirmEarly?: boolean }) => {
      const spent = restType === 'short' ? await spendPendingDice() : []
      const updated = await api.characters.rest(charId, restType, {
        interrupted,
        ate_and_drank: ateAndDrank,
        confirm_early: confirmEarly,
        ...(restType === 'short' && Object.keys(recovery).length > 0 ? { natural_recovery: recovery } : {}),
        ...(restType === 'short' && Object.keys(arcane).length > 0 ? { arcane_recovery: arcane } : {}),
        ...(restType === 'short' && restoration > 0 ? { sorcerous_restoration: restoration } : {}),
        ...(restType === 'short' && memorize ? { memorize_spell: memorize } : {}),
        ...(restType === 'long' && reopenTome ? { reopen_tome: true } : {}),
        ...(resistance ? { fiendish_resilience: resistance } : {}),
        ...(tempAllies.length > 0 ? { temp_hp_allies: tempAllies } : {}),
      })
      return { updated, spent }
    },
    onSettled: () => { restInFlight.current = false },
    onError: (err) => {
      qc.invalidateQueries({ queryKey: ['character', charId] })  // i dadi vita spesi prima del rifiuto restano spesi
      const detail = err instanceof ApiError ? err.detail : null
      const code = (detail as { code?: string } | null)?.code
      if (detail === 'long_rest_too_soon') {
        setConfirmLongRest(false)
        setTooSoon(true)
      } else if (detail === 'hit_dice_exhausted') {
        toast.error(t('character.quick_actions.hit_die_exhausted'))
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
    onSuccess: ({ updated, spent }) => {
      setTooSoon(false)
      setPendingDice({})
      setInterrupted(false)
      setAteAndDrank(true)
      setRecovery({})
      setArcane({})
      setRestoration(0)
      setMemorize(null)
      setReopenTome(false)
      setResistance('')
      setTempAllies([])
      qc.setQueryData(['character', charId], updated)
      qc.invalidateQueries({ queryKey: ['homebrew-resources', charId] })
      setConfirmLongRest(false)
      setShortRestOpen(false)
      onDone?.()
      if (spent.length > 0) setHitDieResult(mergeSpent(spent, updated.current_hit_points))
      // L'esito dice sempre i dadi vita rimasti: fuori dai modali non si leggono altrove che nella pagina PF.
      const dice = (updated.classes ?? []).map((c) => `d${c.hit_die ?? 8} ${hitDiceRemaining(c)}/${c.level}`).join(', ')
      toast.success(dice ? t('character.quick_actions.rest_done_dice', { dice }) : t('character.quick_actions.rest_done'))
      for (const r of updated.temp_received ?? []) {  // il server dice se i PF temporanei sono saliti o se l'altro ne aveva di più
        toast.info(t(r.applied ? 'character.turn.use_temp_received' : 'character.quick_actions.rest_temp_kept', { name: r.name, n: r.given, have: r.temp_hp }))
      }
      haptic.success()
    },
  })

  const startRest = (vars: Parameters<typeof restMutation.mutate>[0]) => {
    if (restInFlight.current) return
    restInFlight.current = true
    restMutation.mutate(vars)
  }

  // Annullare la conferma del riposo lungo azzera anche le domande: la volta dopo non resta «interrotto» a metà.
  const cancelLongRest = () => {
    setConfirmLongRest(false)
    setInterrupted(false)
    setAteAndDrank(true)
    setReopenTome(false)  // l'interruttore del Libro non resta acceso per il riposo dopo
  }

  return {
    openShort: () => setShortRestOpen(true),
    closeShort, pendingDice,
    openLong: () => setConfirmLongRest(true),
    pending: restMutation.isPending,
    shortRestOpen, setShortRestOpen, confirmLongRest, setConfirmLongRest, cancelLongRest, tooSoon, setTooSoon,
    hitDieResult, setHitDieResult, interrupted, setInterrupted, ateAndDrank, setAteAndDrank,
    recovery, setRecovery, arcane, setArcane, memorize, setMemorize, restoration, setRestoration,
    reopenTome, setReopenTome, resistance, setResistance, tempAllies, setTempAllies, hitDieMutation, restMutation, startRest,
  }
}

export type RestState = ReturnType<typeof useRest>

/** I dadi vita spesi con «Riposa» (una chiamata per classe) in un solo esito, coi PF dopo il riposo. */
export function mergeSpent(spent: HitDiceSpendResult[], newHp: number): HitDiceSpendResult {
  return {
    rolls: spent.flatMap((s) => s.rolls),
    con_bonus: spent[0].con_bonus,
    healed: spent.reduce((n, s) => n + s.healed, 0),
    new_current_hp: newHp,
    song_die: spent.find((s) => s.song_die)?.song_die ?? null,
    song_rolls: spent.flatMap((s) => s.song_rolls ?? []),
  }
}

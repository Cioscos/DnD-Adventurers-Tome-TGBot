import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useLocation, useMatch } from 'react-router-dom'
import { api, type LastRollResult, type RollOption, type RollOptionsQuery } from '@/api/client'
import { useD20Roll } from '@/hooks/useD20Roll'
import { useToast } from '@/hooks/useToast'
import { applyAfterRoll, optionHints, usePromptStore, useRefundStore } from '@/lib/rollOptions'
import Button from '@/components/ui/Button'
import Sheet from '@/components/ui/Sheet'
import type { TurnState } from '@/types'

/** Un privilegio da usare dopo aver visto il d20: etichetta e costo. */
export function AfterRollButton({ option, loading, onClick }: { option: RollOption; loading?: boolean; onClick: () => void }) {
  const { t } = useTranslation()
  const hints = optionHints(option, t)
  return (
    <Button variant="secondary" fullWidth loading={loading} onClick={onClick}>
      <span className="flex flex-col items-center">
        <span>{option.label}</span>
        {hints.length > 0 && <span className="text-xs font-normal text-dnd-text-muted tabular-nums">{hints.join(' · ')}</span>}
      </span>
    </Button>
  )
}

function useRefreshAfterRoll(charId: number) {
  const qc = useQueryClient()
  return () => {
    qc.invalidateQueries({ queryKey: ['roll-options', charId] })
    qc.invalidateQueries({ queryKey: ['character', charId] })
    qc.invalidateQueries({ queryKey: ['turn-state', charId] })
  }
}

/** «Il tiro è riuscito?» per ciò che si paga solo se riesce. Un 409 vuol dire che il tiro non è più l'ultimo. */
function RefundQuestion({ charId, onDone }: { charId: number; onDone: () => void }) {
  const { t } = useTranslation()
  const toast = useToast()
  const qc = useQueryClient()
  const refresh = useRefreshAfterRoll(charId)
  const answer = useMutation({
    mutationFn: (succeeded: boolean) => api.characters.lastRollRefund(charId, succeeded),
    onSuccess: (turn) => {
      // Prima di chiudere: con la cache vecchia l'host riaprirebbe la domanda fino alla rilettura.
      qc.setQueryData(['turn-state', charId], (old: TurnState | undefined) => old && { ...old, turn })
      onDone()
      refresh()
    },
    onError: (err) => {
      if ((err as { status?: number }).status === 409) {
        onDone()
        refresh()
      } else {
        toast.warning(t('character.roll_options.refund_failed'))
      }
    },
  })
  return (
    <div className="space-y-2" data-testid="after-roll-refund">
      <p className="text-sm text-dnd-text font-body">{t('character.roll_options.succeeded_question')}</p>
      <div className="flex gap-2">
        <Button variant="secondary" fullWidth loading={answer.isPending && answer.variables === false} onClick={() => answer.mutate(false)}>{t('common.no')}</Button>
        <Button variant="secondary" fullWidth loading={answer.isPending && answer.variables === true} onClick={() => answer.mutate(true)}>{t('common.yes')}</Button>
      </div>
    </div>
  )
}

/** Riga non bloccante dell'esito: nulla si spende finché non si tocca.
 *  `rollToken` cambia solo con un tiro nuovo: le opzioni usate e la domanda valgono per quel tiro. */
export default function AfterRollOptions({ charId, query, rollToken, onResult }: {
  charId: number
  query: RollOptionsQuery
  rollToken: unknown
  onResult: (result: LastRollResult) => void
}) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const rollD20 = useD20Roll()
  const refresh = useRefreshAfterRoll(charId)
  const [state, setState] = useState({ token: rollToken, used: [] as string[], asking: false })
  const current = state.token === rollToken ? state : { token: rollToken, used: [] as string[], asking: false }
  const { data } = useQuery({
    queryKey: ['roll-options', charId, query],
    queryFn: () => api.characters.rollOptions(charId, query),
    gcTime: 0,
  })
  const options = (data ?? []).filter((o) => o.phase === 'after_roll' && !o.needs && !current.used.includes(o.key))

  // Un tiro nuovo sostituisce l'ultimo sul server: la domanda rimasta in cache non vale più.
  useEffect(() => {
    qc.invalidateQueries({ queryKey: ['turn-state', charId] })
  }, [rollToken, charId, qc])

  // Mentre la domanda è qui, l'host non la ripete; se il modale si chiude senza risposta, la riprende lui.
  useEffect(() => {
    if (!current.asking) return
    useRefundStore.setState((s) => ({ inline: s.inline + 1 }))
    return () => useRefundStore.setState((s) => ({ inline: s.inline - 1 }))
  }, [current.asking])

  const apply = useMutation({
    mutationFn: (option: RollOption) => applyAfterRoll(charId, option, rollD20),
    onSuccess: (result, option) => {
      onResult(result)
      setState({ token: rollToken, used: [...current.used, option.key], asking: !!result.refundable?.length })
      refresh()
    },
    onError: () => {
      toast.warning(t('character.roll_options.after_roll_failed'))
      refresh()
    },
  })

  if (current.asking) {
    return <RefundQuestion charId={charId} onDone={() => setState({ ...current, asking: false })} />
  }
  if (options.length === 0) return null
  return (
    // Il dialogo scorre solo se serve: la riga scorre per sé, così la chiusura resta in vista.
    <div className="space-y-2 max-h-[30dvh] [@media(min-height:700px)]:max-h-[38dvh] overflow-y-auto" data-testid="after-roll-options">
      {options.map((option) => (
        <AfterRollButton
          key={option.key}
          option={option}
          loading={apply.isPending && apply.variables?.key === option.key}
          onClick={() => apply.mutate(option)}
        />
      ))}
    </div>
  )
}

/** Da montare una volta sola: la domanda rimasta senza risposta torna finché il tiro resta l'ultimo. */
export function RefundQuestionHost() {
  const match = useMatch('/char/:id/*')
  const charId = Number(match?.params.id)
  return Number.isInteger(charId) && charId > 0 ? <PendingRefund charId={charId} /> : null
}

function PendingRefund({ charId }: { charId: number }) {
  const { t } = useTranslation()
  const { pathname } = useLocation()
  const inline = useRefundStore((s) => s.inline)
  const promptOpen = usePromptStore((s) => !!s.request)
  const [hiddenFor, setHiddenFor] = useState<string | null>(null)
  const { data } = useQuery({ queryKey: ['turn-state', charId], queryFn: () => api.characters.turnState(charId) })
  const last = data?.turn.last_roll
  const pending = Object.keys(last?.refundable ?? {}).length > 0
  // Chiusa senza risposta torna al cambio di pagina: nessun uso si perde, nessun assillo a ogni aggiornamento.
  const token = `${last?.roll_id}:${pathname}`
  if (!pending || inline > 0 || promptOpen || hiddenFor === token) return null
  return (
    <Sheet open onClose={() => setHiddenFor(token)} zClassName="z-[70]" title={t('character.roll_options.refund_title', { total: last?.total })}>
      <div className="p-5">
        <RefundQuestion charId={charId} onDone={() => setHiddenFor(token)} />
      </div>
    </Sheet>
  )
}

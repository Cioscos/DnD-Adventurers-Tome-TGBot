import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api, type LastRollResult, type RollOption, type RollOptionsQuery } from '@/api/client'
import { useD20Roll } from '@/hooks/useD20Roll'
import { useToast } from '@/hooks/useToast'
import { applyAfterRoll, optionHints } from '@/lib/rollOptions'
import Button from '@/components/ui/Button'

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

/** Riga non bloccante del modale di esito: nulla si spende finché non si tocca. */
export default function AfterRollOptions({ charId, query, onResult }: {
  charId: number
  query: RollOptionsQuery
  onResult: (result: LastRollResult) => void
}) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const rollD20 = useD20Roll()
  const [askRefund, setAskRefund] = useState(false)
  const listKey = ['roll-options', charId, query]
  const { data } = useQuery({ queryKey: listKey, queryFn: () => api.characters.rollOptions(charId, query), gcTime: 0 })
  const options = (data ?? []).filter((o) => o.phase === 'after_roll' && !o.needs)

  const refresh = () => {
    qc.invalidateQueries({ queryKey: listKey })
    qc.invalidateQueries({ queryKey: ['character', charId] })
    qc.invalidateQueries({ queryKey: ['turn-state', charId] })
  }

  const apply = useMutation({
    mutationFn: (option: RollOption) => applyAfterRoll(charId, option, rollD20),
    onSuccess: (result) => {
      onResult(result)
      setAskRefund(!!result.refundable?.length)
      refresh()
    },
    onError: () => {
      toast.warning(t('character.roll_options.after_roll_failed'))
      refresh()
    },
  })
  const refund = useMutation({
    mutationFn: () => api.characters.lastRollRefund(charId),
    onSuccess: () => {
      setAskRefund(false)
      refresh()
    },
    onError: () => toast.warning(t('character.roll_options.refund_failed')),
  })

  if (askRefund) {
    return (
      <div className="space-y-2" data-testid="after-roll-refund">
        <p className="text-sm text-dnd-text font-body">{t('character.roll_options.succeeded_question')}</p>
        <div className="flex gap-2">
          <Button variant="secondary" fullWidth loading={refund.isPending} onClick={() => refund.mutate()}>{t('common.no')}</Button>
          <Button variant="secondary" fullWidth onClick={() => setAskRefund(false)}>{t('common.yes')}</Button>
        </div>
      </div>
    )
  }
  if (options.length === 0) return null
  return (
    // Il dialogo è centrato e non scorre: con molte opzioni scorre la riga.
    <div className="space-y-2 max-h-[38dvh] overflow-y-auto" data-testid="after-roll-options">
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

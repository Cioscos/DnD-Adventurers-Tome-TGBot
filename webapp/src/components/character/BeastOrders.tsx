import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ApiError } from '@/api/client'
import Button from '@/components/ui/Button'
import { haptic } from '@/auth/telegram'
import { useToast } from '@/hooks/useToast'
import { notifyMutationError } from '@/lib/mutationError'
import { LEDGER_LABEL, LEDGER_TITLE } from '@/styles/ledger'
import type { BeastCommand, CharacterFull, TurnBlock } from '@/types'

export const BEAST_FEATURE = 'ranger.rangers_companion'
const ORDERS: BeastCommand[] = ['attack', 'help', 'disengage', 'dash', 'dodge']
const BONUS_ORDERS = ORDERS.filter((c) => c !== 'attack')
const ERRORS = ['turn_slot_used', 'beast_attacked', 'beast_not_attacking', 'companion_down', 'incapacitated', 'feature_unavailable']

/** Gli ordini del Signore delle Bestie alla sua bestia compagna (Compagno del Ranger 2014): un'azione per un ordine, o
 *  l'azione bonus dal 7° livello per tutti tranne l'Attacco. L'attacco della bestia si tira poi dalla pagina Extra. */
export default function BeastOrders({ char, turn }: { char: CharacterFull; turn?: TurnBlock }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const present = (char.abilities ?? []).some((a) => a.feature_key === BEAST_FEATURE)
  const training = (char.abilities ?? []).some((a) => a.feature_key === 'ranger.exceptional_training')
  const { data: companions } = useQuery({
    queryKey: ['companions', char.id], queryFn: () => api.companions.list(char.id), enabled: present,
  })
  const order = useMutation({
    mutationFn: ({ id, command, bonus }: { id: number; command: BeastCommand; bonus: boolean }) =>
      api.companions.command(char.id, id, command, bonus),
    onSuccess: () => {
      haptic.success()
      qc.invalidateQueries({ queryKey: ['turn-state', char.id] })
      qc.invalidateQueries({ queryKey: ['companions', char.id] })
    },
    onError: (err) => {
      const code = err instanceof ApiError ? (err.detail as { code?: string } | null)?.code : undefined
      if (code && ERRORS.includes(code)) toast.error(t(`character.extras.beast.errors.${code}`))
      else notifyMutationError()
    },
  })
  if (!present) return null
  const beast = (companions ?? []).find((c) => c.feature_key === BEAST_FEATURE && c.current_hp > 0)
  const left = turn?.beast?.attacks_left ?? 0
  return (
    <section data-testid="beast-orders" className="space-y-2">
      <h2 className={`flex min-h-11 items-center border-b border-dnd-border pl-1 ${LEDGER_TITLE}`}>{t('character.extras.beast.title')}</h2>
      {!beast ? (
        <p className="px-1 text-sm font-body text-dnd-text-muted">{t('character.extras.beast.none')}</p>
      ) : (
        <>
          <p className="px-1 text-sm font-body text-dnd-text">
            {beast.name} <span className="font-mono tabular-nums text-dnd-text-muted">{beast.current_hp}/{beast.max_hp}</span>
            {left > 0 && <span role="status" className="ml-3 text-dnd-gold-bright">{t('character.extras.beast.attacks_left', { n: left })}</span>}
          </p>
          <p className={`px-1 ${LEDGER_LABEL}`}>{t('character.extras.beast.action_orders')}</p>
          <div className="flex flex-wrap gap-2 px-1">
            {ORDERS.map((c) => (
              <Button key={c} size="sm" variant="secondary" className="min-h-11"
                loading={order.isPending && order.variables?.command === c && !order.variables.bonus}
                onClick={() => order.mutate({ id: beast.id, command: c, bonus: false })}>
                {t(`character.extras.beast.orders.${c}`)}
              </Button>
            ))}
          </div>
          {training && (
            <>
              <p className={`px-1 ${LEDGER_LABEL}`}>{t('character.extras.beast.bonus_orders')}</p>
              <div className="flex flex-wrap gap-2 px-1">
                {BONUS_ORDERS.map((c) => (
                  <Button key={c} size="sm" variant="secondary" className="min-h-11"
                    loading={order.isPending && order.variables?.command === c && order.variables.bonus}
                    onClick={() => order.mutate({ id: beast.id, command: c, bonus: true })}>
                    {t(`character.extras.beast.orders.${c}`)}
                  </Button>
                ))}
              </div>
            </>
          )}
          <p className="px-1 text-xs font-body text-dnd-text-muted">{t('character.extras.beast.hint')}</p>
        </>
      )}
    </section>
  )
}

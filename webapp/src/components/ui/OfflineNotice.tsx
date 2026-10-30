import type { UseQueryResult } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { WifiOff } from 'lucide-react'
import { isNetworkError } from '@/lib/queryPersist'

export type OfflineNoticeQuery = Pick<
  UseQueryResult<unknown, unknown>,
  'data' | 'dataUpdatedAt' | 'error' | 'failureReason' | 'isFetching' | 'isRefetchError'
>

interface OfflineNoticeProps {
  query: OfflineNoticeQuery
  className?: string
}

// La cache dura giorni: un orario nudo farebbe sembrare di oggi i dati di ieri.
function formatDataTime(timestamp: number, locale: string): string {
  const date = new Date(timestamp)
  const isToday = date.toDateString() === new Date().toDateString()
  return date.toLocaleString(locale, {
    ...(isToday ? {} : { day: '2-digit', month: '2-digit' }),
    hour: '2-digit',
    minute: '2-digit',
    // Sempre HH:mm, anche con le lingue che userebbero AM/PM.
    hourCycle: 'h23',
  })
}

/** Avvisa che i dati a schermo non sono aggiornati perché l'ultimo aggiornamento è
 *  fallito: "offline" se non ha raggiunto il server, testo neutro se il server ha
 *  risposto con un errore. `failureReason` copre i tentativi in corso: con la rete giù
 *  durano secondi e intanto la query non è ancora in `error`. Fuori da un fetch non
 *  conta: `setQueryData` non lo azzera e resterebbe anche su dati appena salvati. */
export default function OfflineNotice({ query, className = '' }: OfflineNoticeProps) {
  const { t, i18n } = useTranslation()
  const failure = query.isRefetchError ? query.error : query.isFetching ? query.failureReason : null
  if (query.data === undefined || !failure) return null
  const textKey = isNetworkError(failure) ? 'common.offline_data_from' : 'common.stale_data_from'

  return (
    <p
      role="status"
      className={`flex items-center gap-1.5 rounded-lg border border-dnd-amber/40 bg-dnd-amber/10 px-3 py-1.5 text-xs font-body tabular-nums text-dnd-text ${className}`}
    >
      <WifiOff size={14} className="shrink-0 text-dnd-amber" />
      <span className="min-w-0">
        {t(textKey, { time: formatDataTime(query.dataUpdatedAt, i18n.language) })}
      </span>
    </p>
  )
}

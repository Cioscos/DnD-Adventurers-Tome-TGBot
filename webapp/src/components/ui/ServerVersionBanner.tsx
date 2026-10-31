import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { AlertTriangle, X } from 'lucide-react'
import { api } from '@/api/client'
import { currentVersion } from '@/lib/version'
import { isServerBehind } from '@/lib/semver'

const DISMISS_KEY = 'serverVersionBannerDismissed'

/** Avvisa se il server (Raspberry) gira una versione più vecchia della webapp. */
export default function ServerVersionBanner() {
  const { t } = useTranslation()
  const [dismissed, setDismissed] = useState(() => sessionStorage.getItem(DISMISS_KEY) === '1')
  const { data } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.health(),
    staleTime: Infinity,
    refetchOnReconnect: true,
  })
  if (dismissed || !isServerBehind(currentVersion(), data?.version ?? null)) return null

  return (
    <div
      role="status"
      className="shrink-0 flex items-center gap-2 border-b border-dnd-amber/40 bg-dnd-amber/10 px-4 py-1.5 text-xs font-body text-dnd-text"
    >
      <AlertTriangle size={14} className="shrink-0 text-dnd-amber" />
      <span className="min-w-0 flex-1">{t('layout.server_outdated')}</span>
      <button
        type="button"
        aria-label={t('common.close')}
        onClick={() => {
          sessionStorage.setItem(DISMISS_KEY, '1')
          setDismissed(true)
        }}
        className="shrink-0 w-11 h-11 -my-2 -mr-3 flex items-center justify-center"
      >
        <X size={16} />
      </button>
    </div>
  )
}

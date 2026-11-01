import { useEffect, useRef } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { WifiOff } from 'lucide-react'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import EmptyState from '@/components/ui/EmptyState'
import Skeleton from '@/components/ui/Skeleton'
import { api, ApiError } from '@/api/client'
import { useSessionLive } from '@/hooks/useSessionLive'
import CombatPanel from '@/pages/session/CombatPanel'

export default function Combat() {
  const { id } = useParams<{ id: string }>()
  const sessionId = Number(id)
  const navigate = useNavigate()
  const { t } = useTranslation()

  const { data: meInfo } = useQuery({
    queryKey: ['auth-me'],
    queryFn: () => api.me(),
    staleTime: Infinity,
  })
  const myUserId = meInfo?.user_id ?? 0

  const { data: live, isLoading, isFetching, isError, error, refetch } = useSessionLive(sessionId)
  const open = !!live && live.status === 'active' && !!live.encounter

  // Incontro finito (o mai esistito, o sessione chiusa): si torna alla sessione.
  const hadEncounterRef = useRef(false)
  useEffect(() => {
    if (!live) return
    if (open) {
      hadEncounterRef.current = true
      return
    }
    // La cache può essere di prima che l'incontro iniziasse: decide solo un dato fresco.
    if (isFetching) return
    if (hadEncounterRef.current) toast.info(t('session.combat.ended_toast'))
    navigate(`/session/${sessionId}`, { replace: true })
  }, [live, open, isFetching, navigate, sessionId, t])

  const layout = (children: React.ReactNode) => (
    <Layout
      help="combat"
      title={t('session.combat.page_title')}
      backTo={`/session/${sessionId}`}
    >
      {children}
    </Layout>
  )

  if (isLoading || (live && !open)) {
    return layout(
      <>
        <Skeleton.Rect height="56px" />
        <Skeleton.Rect height="140px" delay={100} />
        <Skeleton.Rect height="220px" delay={200} />
      </>,
    )
  }

  const notFound = error instanceof ApiError && (error.status === 404 || error.status === 403)
  if (!live && isError && !notFound) {
    return layout(
      <EmptyState
        icon={<WifiOff size={32} />}
        title={t('common.offline_unavailable')}
        action={{ label: t('common.retry'), onClick: () => refetch() }}
      />,
    )
  }

  if (!live) {
    return layout(
      <Surface variant="elevated">
        <p className="text-center text-dnd-text-muted font-body py-6">{t('session.not_found')}</p>
      </Surface>,
    )
  }

  return layout(
    <CombatPanel
      live={live}
      sessionId={sessionId}
      amGm={live.gm_user_id === myUserId}
      myUserId={myUserId}
    />,
  )
}

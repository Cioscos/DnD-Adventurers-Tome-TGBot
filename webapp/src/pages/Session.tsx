import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Crown, UserPlus, Swords } from 'lucide-react'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import FancyHeader from '@/components/ui/FancyHeader'
import Reveal from '@/components/ui/Reveal'
import Skeleton from '@/components/ui/Skeleton'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'

export default function Session() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const qc = useQueryClient()

  const { data: active, isLoading } = useQuery({
    queryKey: ['session-me'],
    queryFn: () => api.sessions.me(),
  })

  const { data: characters = [] } = useQuery({
    queryKey: ['characters'],
    queryFn: () => api.characters.list(),
  })

  const createMutation = useMutation({
    mutationFn: () => api.sessions.create(),
    onSuccess: (session) => {
      qc.setQueryData(['session-me'], session)
      haptic.success()
      navigate(`/session/${session.id}`)
    },
    onError: () => haptic.error(),
  })

  if (isLoading) {
    return (
      <Layout title={t('session.title')} backTo="/">
        <Skeleton.Rect height="120px" />
        <Skeleton.Rect height="120px" delay={100} />
      </Layout>
    )
  }

  if (active) {
    return (
      <Layout title={t('session.title')} backTo="/">
        <Surface variant="sigil" ornamented>
          <FancyHeader
            title={t('session.active_session_banner')}
            subtitle={active.code}
          />
          <div className="mt-4 space-y-2">
            <p className="text-sm text-dnd-text-muted font-body text-center">
              {t(`session.role_${active.gm_user_id === active.participants.find(p => p.role === 'game_master')?.user_id ? 'game_master' : 'player'}`)}
            </p>
            <Button
              variant="primary"
              size="lg"
              fullWidth
              onClick={() => navigate(`/session/${active.id}`)}
              icon={<Swords size={18} />}
            >
              {t('session.resume')}
            </Button>
          </div>
        </Surface>
      </Layout>
    )
  }

  const hasCharacters = characters.length > 0

  return (
    <Layout title={t('session.title')} backTo="/">
      <FancyHeader title={t('session.title')} subtitle={t('session.landing_subtitle')} />

      <Reveal.Stagger className="space-y-3">
        <Surface variant="elevated">
          <div className="flex items-start gap-3">
            <div className="shrink-0 w-11 h-11 rounded-xl bg-gradient-gold flex items-center justify-center">
              <Crown size={20} className="text-dnd-ink" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-display font-bold text-dnd-gold-bright">
                {t('session.create_gm')}
              </p>
              <p className="text-xs text-dnd-text-muted font-body italic mt-1">
                {t('session.create_gm_hint')}
              </p>
              <div className="mt-3">
                <Button
                  variant="primary"
                  size="md"
                  fullWidth
                  loading={createMutation.isPending}
                  onClick={() => createMutation.mutate()}
                >
                  {t('session.create_button')}
                </Button>
              </div>
            </div>
          </div>
        </Surface>

        <Surface variant="elevated">
          <div className="flex items-start gap-3">
            <div className="shrink-0 w-11 h-11 rounded-xl bg-dnd-arcane/20 border border-dnd-arcane/50 flex items-center justify-center">
              <UserPlus size={20} className="text-dnd-arcane-bright" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-display font-bold text-dnd-gold-bright">
                {t('session.join_player')}
              </p>
              <p className="text-xs text-dnd-text-muted font-body italic mt-1">
                {hasCharacters
                  ? t('session.join_player_hint')
                  : t('session.no_characters_hint')}
              </p>
              <div className="mt-3">
                <Button
                  variant="secondary"
                  size="md"
                  fullWidth
                  disabled={!hasCharacters}
                  onClick={() => navigate('/session/join')}
                >
                  {t('session.join_button')}
                </Button>
              </div>
            </div>
          </div>
        </Surface>
      </Reveal.Stagger>
    </Layout>
  )
}

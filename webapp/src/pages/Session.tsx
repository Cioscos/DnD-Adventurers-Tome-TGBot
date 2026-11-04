import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { UserPlus } from 'lucide-react'
import { GiCrown as Crown, GiCrossedSwords as Swords } from 'react-icons/gi'
import Layout from '@/components/Layout'
import Button from '@/components/ui/Button'
import Reveal from '@/components/ui/Reveal'
import Skeleton from '@/components/ui/Skeleton'
import Pressable from '@/components/ui/Pressable'
import SectionDivider from '@/components/ui/SectionDivider'
import StartSessionSheet from '@/pages/session/StartSessionSheet'
import { api } from '@/api/client'
import { getMyRole } from '@/lib/sessionHelpers'

export default function Session() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [startOpen, setStartOpen] = useState(false)

  const { data: active, isLoading } = useQuery({
    queryKey: ['session-me'],
    queryFn: () => api.sessions.me(),
  })

  const { data: meInfo } = useQuery({
    queryKey: ['auth-me'],
    queryFn: () => api.me(),
    staleTime: Infinity,
  })

  const charactersQuery = useQuery({
    queryKey: ['characters'],
    queryFn: () => api.characters.list(),
  })
  const characters = charactersQuery.data ?? []
  // Un fetch fallito non è "nessun personaggio": il bottone diventa un riprova.
  const charactersUnavailable = charactersQuery.isError && charactersQuery.data === undefined

  const campaigns = useQuery({ queryKey: ['campaigns'], queryFn: () => api.campaigns.list() }).data ?? []

  // Le campagne restano raggiungibili anche a sessione aperta (pagina, diario, lore, calendario).
  const campaignList = campaigns.length > 0 && (
    <>
      <SectionDivider>{t('campaign.mine')}</SectionDivider>
      <div className="divide-y divide-dnd-border/60 border-b border-dnd-border/60">
        {campaigns.map((c) => (
          <Pressable
            key={c.id}
            onClick={() => navigate(`/campaign/${c.id}`)}
            className="my-0.5 w-full min-h-[48px] px-1 py-1.5 text-left hover:bg-dnd-surface/60 transition-colors"
          >
            <span className="block font-body font-semibold text-sm text-dnd-text break-words">{c.name}</span>
            <span className="block text-xs font-body text-dnd-text-muted">
              {t('campaign.members_count', { count: c.member_count })}
              {c.active_session_id != null && ` · ${t('campaign.night_active')}`}
            </span>
          </Pressable>
        ))}
      </div>
    </>
  )

  if (isLoading) {
    return (
      <Layout help="session" title={t('session.title')} backTo="/">
        <Skeleton.Rect height="120px" />
        <Skeleton.Rect height="120px" delay={100} />
      </Layout>
    )
  }

  if (active) {
    const sessionName =
      active.gm_display_name?.trim() || active.title?.trim() || `#${active.gm_user_id}`
    // participants può mancare su payload parziali: getMyRole è null-safe e
    // deriva il ruolo del viewer dal proprio user_id, non dalla lista GM.
    const myRole = getMyRole(active, meInfo?.user_id)
    return (
      <Layout help="session" title={t('session.title')} backTo="/">
        <section className="px-1">
          <h2 className="font-display text-xl font-bold text-dnd-text break-words">{sessionName}</h2>
          <p className="text-sm font-body text-dnd-text-muted">{t('session.active_session_banner')}</p>
          <div className="mt-3 space-y-2">
            <p className="text-xs uppercase tracking-widest font-cinzel text-dnd-gold-dim">
              {t('session.code_label')}: <span className="text-dnd-gold-bright">{active.code}</span>
            </p>
            {myRole !== 'none' && (
              <p className="text-sm text-dnd-text-muted font-body">
                {t(`session.role_${myRole === 'gm' ? 'game_master' : 'player'}`)}
              </p>
            )}
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
        </section>
        {campaignList}
      </Layout>
    )
  }

  const hasCharacters = characters.length > 0

  return (
    <Layout help="session" title={t('session.title')} backTo="/">
      <p className="px-1 text-sm font-body text-dnd-text-muted">{t('session.landing_subtitle')}</p>

      <Reveal.Stagger className="border-y border-dnd-border divide-y divide-dnd-border/60">
        <div className="px-1 py-4">
          <div className="flex items-start gap-3">
            <Crown size={22} aria-hidden className="mt-0.5 shrink-0 text-dnd-gold" />
            <div className="flex-1 min-w-0">
              <p className="font-display font-bold text-dnd-text">
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
                  onClick={() => setStartOpen(true)}
                >
                  {t('session.create_button')}
                </Button>
              </div>
            </div>
          </div>
        </div>

        <div className="px-1 py-4">
          <div className="flex items-start gap-3">
            <UserPlus size={22} aria-hidden className="mt-0.5 shrink-0 text-dnd-gold" />
            <div className="flex-1 min-w-0">
              <p className="font-display font-bold text-dnd-text">
                {t('session.join_player')}
              </p>
              <p className="text-xs text-dnd-text-muted font-body italic mt-1">
                {charactersUnavailable
                  ? t('common.offline_unavailable')
                  : hasCharacters
                    ? t('session.join_player_hint')
                    : t('session.no_characters_hint')}
              </p>
              <div className="mt-3">
                <Button
                  variant="secondary"
                  size="md"
                  fullWidth
                  disabled={!hasCharacters && !charactersUnavailable}
                  onClick={() => (charactersUnavailable ? charactersQuery.refetch() : navigate('/session/join'))}
                >
                  {charactersUnavailable ? t('common.retry') : t('session.join_button')}
                </Button>
              </div>
            </div>
          </div>
        </div>
      </Reveal.Stagger>

      {campaignList}
      <StartSessionSheet open={startOpen} onClose={() => setStartOpen(false)} />
    </Layout>
  )
}

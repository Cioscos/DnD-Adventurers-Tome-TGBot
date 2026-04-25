import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'
import { LogOut, User } from 'lucide-react'
import {
  GiCrown as Crown, GiHeartPlus as Heart, GiCheckedShield as Shield,
  GiSparkles as Sparkles, GiSkullCrossedBones as XOctagon,
  GiPerspectiveDiceSixFacesRandom as Dices,
} from 'react-icons/gi'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import Skeleton from '@/components/ui/Skeleton'
import SectionDivider from '@/components/ui/SectionDivider'
import ConditionBadge from '@/components/ui/ConditionBadge'
import { api } from '@/api/client'
import type { CharacterLiveSnapshot, SessionParticipant } from '@/types'
import { haptic, telegramConfirm } from '@/auth/telegram'
import ParticipantIdentitySheet from '@/pages/session/ParticipantIdentitySheet'
import SessionFeed from '@/pages/session/SessionFeed'

function conditionEntries(
  conditions: Record<string, unknown> | null | undefined,
): Array<[string, unknown]> {
  if (!conditions) return []
  return Object.entries(conditions).filter(([, v]) => Boolean(v))
}

function ParticipantRow({
  participant,
  snapshot,
  isGm,
  isMe,
  isOwn,
  onOwnClick,
  onOtherClick,
  t,
}: {
  participant: SessionParticipant
  snapshot?: CharacterLiveSnapshot
  isGm: boolean
  isMe: boolean
  isOwn: boolean
  onOwnClick: (charId: number) => void
  onOtherClick: (participant: SessionParticipant) => void
  t: TFunction
}) {
  const roleIcon = isGm
    ? <Crown size={14} className="text-dnd-gold-bright" />
    : <User size={14} className="text-dnd-text-muted" />

  const redacted = !!snapshot && snapshot.hit_points === null
  const hpPct = snapshot && !redacted && (snapshot.hit_points ?? 0) > 0
    ? Math.max(0, Math.min(100, Math.round(
        ((snapshot.current_hit_points ?? 0) / (snapshot.hit_points ?? 1)) * 100
      )))
    : 0
  const conds = conditionEntries(snapshot?.conditions)

  const bucketColorClass: Record<string, string> = {
    healthy:          'bg-[var(--dnd-emerald-bright)]',
    lightly_wounded:  'bg-dnd-gold-bright',
    badly_wounded:    'bg-[var(--dnd-amber)]',
    dying:            'bg-[var(--dnd-crimson-bright)]',
    dead:             'bg-black',
  }

  const handleClick = () => {
    if (isOwn && snapshot) {
      onOwnClick(snapshot.id)
    } else if (!isGm && !isMe && participant.character_id) {
      onOtherClick(participant)
    }
  }

  const isClickable = isOwn || (!isGm && !isMe && !!participant.character_id)
  const wrapperProps = isClickable
    ? {
        role: 'button' as const,
        tabIndex: 0,
        onClick: handleClick,
        onKeyDown: (e: React.KeyboardEvent) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            handleClick()
          }
        },
        className: 'w-full text-left cursor-pointer',
      }
    : {}

  return (
    <div {...wrapperProps}>
      <div className={`rounded-lg border p-3 transition-colors
        ${isMe ? 'border-dnd-gold bg-dnd-surface-raised' : 'border-dnd-border bg-dnd-surface'}
        ${isClickable ? 'hover:border-dnd-gold-bright' : ''}`}>

        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            {roleIcon}
            <p className="font-display font-bold text-dnd-gold-bright truncate">
              {isGm ? t('session.game_master') : (snapshot?.name ?? participant.display_name ?? `#${participant.user_id}`)}
            </p>
            {isMe && (
              <span className="text-[10px] uppercase tracking-wider text-dnd-text-muted font-cinzel">
                {t('session.you')}
              </span>
            )}
          </div>
          {snapshot?.heroic_inspiration && (
            <Sparkles size={14} className="text-dnd-amber animate-shimmer shrink-0" />
          )}
        </div>

        {snapshot && (
          <>
            <p className="text-xs text-dnd-text-muted font-body italic mt-0.5">
              {snapshot.class_summary || '—'}
            </p>

            {redacted ? (
              <>
                <div className="mt-2 flex items-center justify-between text-xs font-cinzel">
                  <div className="flex items-center gap-1.5">
                    <Heart size={12} className="text-[var(--dnd-crimson-bright)]" />
                    <span className="uppercase tracking-wider">
                      {snapshot.hp_bucket
                        ? t(`session.hp_bucket.${snapshot.hp_bucket}`)
                        : t('session.hp_bucket.healthy')}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Shield size={12} className="text-dnd-gold-bright" />
                    <span className="uppercase tracking-wider">
                      {t(`session.armor_category.${snapshot.armor_category ?? 'unarmored'}`)}
                    </span>
                  </div>
                </div>
                <div className="mt-1.5 h-1.5 w-full rounded-full bg-dnd-surface overflow-hidden">
                  <div className={`h-full ${bucketColorClass[snapshot.hp_bucket ?? 'healthy']}`} style={{ width: '100%' }} />
                </div>
              </>
            ) : (
              <>
                <div className="mt-2 grid grid-cols-2 gap-2 text-xs font-mono">
                  <div className="flex items-center gap-1.5">
                    <Heart size={12} className="text-[var(--dnd-crimson-bright)]" />
                    <span>{snapshot.current_hit_points}/{snapshot.hit_points}</span>
                    {(snapshot.temp_hp ?? 0) > 0 && <span className="text-dnd-arcane-bright">+{snapshot.temp_hp}</span>}
                  </div>
                  <div className="flex items-center gap-1.5 justify-end">
                    <Shield size={12} className="text-dnd-gold-bright" />
                    <span>{snapshot.ac}</span>
                  </div>
                </div>
                <div className="mt-1.5 h-1.5 w-full rounded-full bg-dnd-surface overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-[var(--dnd-crimson)] via-[var(--dnd-amber)] to-[var(--dnd-emerald-bright)]"
                    style={{ width: `${hpPct}%` }}
                  />
                </div>
              </>
            )}

            {conds.length > 0 && (
              <div
                className="mt-2 flex flex-wrap gap-1.5"
                onClick={(e) => e.stopPropagation()}
              >
                {conds.map(([key, val]) => (
                  <ConditionBadge key={key} conditionKey={key} value={val} />
                ))}
              </div>
            )}
            {snapshot.last_roll && (
              <div className="mt-1 text-[11px] text-dnd-text-muted flex items-center gap-1">
                <Dices size={11} />
                <span>{snapshot.last_roll.notation} → {snapshot.last_roll.total}</span>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default function SessionRoom() {
  const { id } = useParams<{ id: string }>()
  const sessionId = Number(id)
  const navigate = useNavigate()
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [identityTarget, setIdentityTarget] = useState<SessionParticipant | null>(null)

  const { data: meInfo } = useQuery({
    queryKey: ['auth-me'],
    queryFn: () => api.me(),
    staleTime: Infinity,
  })
  const myUserId = meInfo?.user_id ?? 0

  const { data: live, isLoading } = useQuery({
    queryKey: ['session-live', sessionId],
    queryFn: () => api.sessions.live(sessionId),
    refetchInterval: (query) => {
      const d = query.state.data
      return d && d.status === 'active' ? 2500 : false
    },
    enabled: Number.isFinite(sessionId),
  })

  const leaveMutation = useMutation({
    mutationFn: () => api.sessions.leave(sessionId),
    onSuccess: () => {
      qc.setQueryData(['session-me'], null)
      qc.invalidateQueries({ queryKey: ['session-me'] })
      haptic.success()
      navigate('/session')
    },
    onError: (err) => {
      console.error('leave session failed', err)
      haptic.error()
    },
  })

  const closeMutation = useMutation({
    mutationFn: () => api.sessions.close(sessionId),
    onSuccess: () => {
      qc.setQueryData(['session-me'], null)
      qc.invalidateQueries({ queryKey: ['session-me'] })
      haptic.warning()
      navigate('/session')
    },
    onError: (err) => {
      console.error('close session failed', err)
      haptic.error()
    },
  })

  const snapshotsById = useMemo(() => {
    const map = new Map<number, CharacterLiveSnapshot>()
    live?.live_characters.forEach((c) => map.set(c.id, c))
    return map
  }, [live])

  const gmUserId = live?.gm_user_id ?? null

  const amGm = !!live && live.gm_user_id === myUserId

  if (isLoading) {
    return (
      <Layout title={t('session.title')} backTo="/session">
        <Skeleton.Rect height="120px" />
        <Skeleton.Rect height="180px" delay={100} />
      </Layout>
    )
  }

  if (!live) {
    return (
      <Layout title={t('session.title')} backTo="/session">
        <Surface variant="elevated">
          <p className="text-center text-dnd-text-muted font-body py-6">
            {t('session.not_found')}
          </p>
        </Surface>
      </Layout>
    )
  }

  if (live.status !== 'active') {
    return (
      <Layout title={t('session.title')} backTo="/session">
        <Surface variant="ember">
          <p className="text-center font-display font-bold text-[var(--dnd-crimson-bright)] py-6">
            {t('session.closed_notice')}
          </p>
          <Button variant="secondary" fullWidth onClick={() => navigate('/session')}>
            {t('common.back')}
          </Button>
        </Surface>
      </Layout>
    )
  }

  const confirmLeave = () => {
    const msg = amGm ? t('session.confirm_close') : t('session.confirm_leave')
    telegramConfirm(msg, (ok) => {
      if (!ok) return
      if (amGm) closeMutation.mutate()
      else leaveMutation.mutate()
    })
  }

  return (
    <Layout title={t('session.room_title', { code: live.code })} backTo="/session">
      {amGm ? (
        <Surface variant="sigil" ornamented>
          <div className="text-center">
            <p className="text-xs uppercase tracking-widest text-dnd-gold-dim font-cinzel">
              {t('session.code_label')}
            </p>
            <p className="font-display font-bold text-3xl text-dnd-gold-bright tracking-[0.3em] mt-1">
              {live.code}
            </p>
            {live.title && (
              <p className="text-sm text-dnd-text-muted font-body italic mt-1">
                {live.title}
              </p>
            )}
          </div>
        </Surface>
      ) : (
        <Surface variant="sigil" ornamented>
          <div className="text-center">
            <p className="text-xs uppercase tracking-widest text-dnd-gold-dim font-cinzel">
              {t('session.role_player')}
            </p>
            <p className="font-display font-bold text-xl text-dnd-gold-bright mt-1">
              {live.title || t('session.active_session_banner')}
            </p>
          </div>
        </Surface>
      )}

      <SectionDivider>
        {t('session.players')}
      </SectionDivider>

      <div className="space-y-2">
        {live.participants.map((p) => {
          const isMe = p.user_id === myUserId
          const snap = p.character_id ? snapshotsById.get(p.character_id) : undefined
          const isOwn = isMe && !!snap && snap.hit_points !== null
          return (
            <ParticipantRow
              key={`${p.user_id}-${p.joined_at}`}
              participant={p}
              snapshot={snap}
              isGm={p.role === 'game_master'}
              isMe={isMe}
              isOwn={isOwn}
              onOwnClick={(cid) => navigate(`/char/${cid}`)}
              onOtherClick={(target) => setIdentityTarget(target)}
              t={t}
            />
          )
        })}
      </div>

      <SectionDivider>
        {t('session.chat_and_history')}
      </SectionDivider>

      <SessionFeed
        code={live.code}
        sessionId={live.id}
        amGm={amGm}
        gmUserId={gmUserId}
        myUserId={myUserId}
        participants={live.participants}
      />

      <Button
        variant="danger"
        size="md"
        fullWidth
        icon={amGm ? <XOctagon size={16} /> : <LogOut size={16} />}
        onClick={confirmLeave}
      >
        {amGm ? t('session.close') : t('session.leave')}
      </Button>

      <ParticipantIdentitySheet
        code={live.code}
        target={identityTarget}
        onClose={() => setIdentityTarget(null)}
      />
    </Layout>
  )
}

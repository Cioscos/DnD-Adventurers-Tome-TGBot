import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'
import { LogOut, User, Gift, Copy, Share2, WifiOff, Package, BookOpen, Map as MapIcon } from 'lucide-react'
import { toast } from 'sonner'
import {
  GiCrown as Crown, GiHeartPlus as Heart, GiCheckedShield as Shield,
  GiPolarStar as Sparkles, GiSkullCrossedBones as XOctagon,
  GiPerspectiveDiceSixFacesRandom as Dices,
} from 'react-icons/gi'
import PendingSavesBanner from '@/components/PendingSavesBanner'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import EmptyState from '@/components/ui/EmptyState'
import Button from '@/components/ui/Button'
import Skeleton from '@/components/ui/Skeleton'
import Pressable from '@/components/ui/Pressable'
import SectionDivider from '@/components/ui/SectionDivider'
import HPGauge from '@/components/ui/HPGauge'
import { LEDGER_INDEX_ROW } from '@/styles/ledger'
import ConditionBadge from '@/components/ui/ConditionBadge'
import PublicStates from '@/components/session/PublicStates'
import { api, ApiError } from '@/api/client'
import type { CharacterLiveSnapshot, SessionParticipant } from '@/types'
import { canShareMessage, haptic, telegramConfirm } from '@/auth/telegram'
import { useShareMessage } from '@/hooks/useShareMessage'
import { useSessionLive } from '@/hooks/useSessionLive'
import { useYourTurnToast } from '@/hooks/useYourTurnToast'
import ParticipantIdentitySheet from '@/pages/session/ParticipantIdentitySheet'
import SessionFeed from '@/pages/session/SessionFeed'
import GrantItemModal from '@/pages/session/GrantItemModal'
import StashSheet from '@/pages/session/StashSheet'
import CombatEntryCard from '@/components/session/CombatEntryCard'
import { dequeue, peek, pruneOlderThan, type Reward } from '@/lib/rewardQueue'
import RewardPopup from '@/components/session/RewardPopup'
import { notifyMutationError } from '@/lib/mutationError'

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
  const conds = conditionEntries(snapshot?.conditions)

  const bucketColorClass: Record<string, string> = {
    healthy:          'bg-dnd-emerald-bright',
    lightly_wounded:  'bg-dnd-gold-bright',
    badly_wounded:    'bg-dnd-amber',
    dying:            'bg-dnd-crimson-bright',
    dead:             'bg-dnd-ink',
  }

  const handleClick = () => {
    if (isOwn && snapshot) {
      onOwnClick(snapshot.id)
    } else if (!isMe) {
      onOtherClick(participant)
    }
  }

  const isClickable = isOwn || !isMe
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
      <div className={`px-1 py-2.5 transition-colors
        ${isMe ? 'bg-dnd-gold/10' : ''}
        ${isClickable ? 'hover:bg-dnd-surface/60' : ''}`}>

        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            {roleIcon}
            <p className="font-display font-bold text-dnd-text truncate">
              {isGm ? t('session.game_master') : (snapshot?.name ?? participant.display_name ?? `#${participant.user_id}`)}
            </p>
            {isMe && (
              <span className="text-xs uppercase tracking-wider text-dnd-text-muted font-cinzel">
                {t('session.you')}
              </span>
            )}
          </div>
          {snapshot?.heroic_inspiration && (
            <Sparkles size={14} aria-hidden className="text-dnd-amber shrink-0" />
          )}
        </div>

        {snapshot && (
          <>
            <p className="text-xs text-dnd-text-muted font-body italic mt-0.5">
              {snapshot.class_summary || '—'}
            </p>

            {redacted ? (
              <>
                <div className="mt-2 flex items-center text-xs font-cinzel">
                  <div className="flex items-center gap-1.5">
                    <Heart size={12} className="text-dnd-crimson-bright" />
                    <span className="uppercase tracking-wider">
                      {snapshot.hp_bucket
                        ? t(`session.hp_bucket.${snapshot.hp_bucket}`)
                        : t('session.hp_bucket.healthy')}
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
                    <Heart size={12} className="text-dnd-crimson-bright" />
                    <span>{snapshot.current_hit_points}/{snapshot.hit_points}</span>
                    {(snapshot.temp_hp ?? 0) > 0 && <span className="text-dnd-arcane-bright">+{snapshot.temp_hp}</span>}
                  </div>
                  <div className="flex items-center gap-1.5 justify-end">
                    <Shield size={12} className="text-dnd-gold-bright" />
                    <span>{snapshot.ac}</span>
                  </div>
                </div>
                <div className="mt-1.5">
                  <HPGauge current={snapshot.current_hit_points ?? 0} max={snapshot.hit_points ?? 0} temp={snapshot.temp_hp ?? 0} size="md" />
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
            <PublicStates states={snapshot.active_states} />
            {snapshot.last_roll && (
              <div className="mt-1 text-xs text-dnd-text-muted flex items-center gap-1">
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
  const [whisperTarget, setWhisperTarget] = useState<SessionParticipant | null>(null)
  const [showGrantItem, setShowGrantItem] = useState(false)
  const [showStash, setShowStash] = useState(false)
  const [currentReward, setCurrentReward] = useState<Reward | null>(null)

  useEffect(() => {
    pruneOlderThan(24 * 60 * 60 * 1000)
    setCurrentReward(peek())
  }, [])

  const handleRewardEnqueued = () => {
    setCurrentReward((cur) => cur ?? peek())
  }

  const { data: meInfo } = useQuery({
    queryKey: ['auth-me'],
    queryFn: () => api.me(),
    staleTime: Infinity,
  })
  const myUserId = meInfo?.user_id ?? 0

  const { data: live, isLoading, isError, error, refetch } = useSessionLive(sessionId)
  useYourTurnToast(live?.encounter, myUserId)

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
      notifyMutationError(err)
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
      notifyMutationError(err)
    },
  })

  const snapshotsById = useMemo(() => {
    const map = new Map<number, CharacterLiveSnapshot>()
    live?.live_characters.forEach((c) => map.set(c.id, c))
    return map
  }, [live])

  const gmUserId = live?.gm_user_id ?? null

  const amGm = !!live && live.gm_user_id === myUserId

  const shareInvite = useShareMessage(() => api.share.invite(sessionId))

  const myCharId =
    live?.participants?.find((p) => p.user_id === myUserId)?.character_id ?? null

  if (isLoading) {
    return (
      <Layout help="session_room" title={t('session.title')} backTo="/session">
        <Skeleton.Rect height="120px" />
        <Skeleton.Rect height="180px" delay={100} />
      </Layout>
    )
  }

  // Un errore di rete non dice che la sessione non esiste: "non trovata" solo se
  // lo ha risposto il server. Tornata la rete la query riparte da sola.
  const notFound = error instanceof ApiError && (error.status === 404 || error.status === 403)
  if (!live && isError && !notFound) {
    return (
      <Layout help="session_room" title={t('session.title')} backTo="/session">
        <EmptyState
          icon={<WifiOff size={32} />}
          title={t('common.offline_unavailable')}
          action={{ label: t('common.retry'), onClick: () => refetch() }}
        />
      </Layout>
    )
  }

  if (!live) {
    return (
      <Layout help="session_room" title={t('session.title')} backTo="/session">
        <p className="text-center text-dnd-text-muted font-body py-6">
          {t('session.not_found')}
        </p>
      </Layout>
    )
  }

  if (live.status !== 'active') {
    return (
      <Layout help="session_room" title={t('session.title')} backTo="/session">
        <Surface variant="ember">
          <p className="text-center font-display font-bold text-dnd-crimson-bright py-6">
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

  const inCampaign = live.campaign_id != null
  const sessionName =
    live.gm_display_name?.trim() ||
    live.title?.trim() ||
    t('session.active_session_banner')

  return (
    <Layout help="session_room" title={inCampaign ? (live.campaign_name || sessionName) : t('session.room_title', { code: live.code })} backTo="/session">
      {!amGm && myCharId && <PendingSavesBanner charId={myCharId} />}
      {/* Sessione di campagna: l'accesso è per iscrizione, il codice non c'è. */}
      {amGm && !inCampaign ? (
        <section>
          <div className="text-center">
            <p className="text-xs uppercase tracking-widest text-dnd-gold-dim font-cinzel">
              {t('session.code_label')}
            </p>
            <div className="flex items-center justify-center gap-2 mt-1">
              <p className="font-display font-bold text-3xl text-dnd-gold-bright tracking-[0.3em]">
                {live.code}
              </p>
              <Pressable
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(live.code)
                    haptic.light()
                    toast.success(t('session.code_copied'), { duration: 1500 })
                  } catch {
                    haptic.error()
                  }
                }}
                className="w-11 h-11 inline-flex items-center justify-center rounded-full bg-dnd-chip-bg border border-dnd-gold-dim/40 text-dnd-gold-bright hover:border-dnd-gold/70"
                aria-label={t('common.copy')}
              >
                <Copy size={16} />
              </Pressable>
              {canShareMessage() && (
                <Pressable
                  onClick={() => { haptic.light(); shareInvite.mutate() }}
                  pending={shareInvite.isPending}
                  className="w-11 h-11 inline-flex items-center justify-center rounded-full bg-dnd-chip-bg border border-dnd-gold-dim/40 text-dnd-gold-bright hover:border-dnd-gold/70 disabled:opacity-50"
                  aria-label={t('share.invite')}
                >
                  <Share2 size={16} />
                </Pressable>
              )}
            </div>
            <p className="text-sm text-dnd-text-muted font-body italic mt-1">
              {sessionName}
            </p>
          </div>
        </section>
      ) : (
        <section className="px-1">
          <p className="text-xs uppercase tracking-widest text-dnd-gold-dim font-cinzel">
            {t(amGm ? 'session.role_game_master' : 'session.role_player')}
          </p>
          <p className="font-display font-bold text-xl text-dnd-text mt-0.5">
            {sessionName}
          </p>
        </section>
      )}

      <CombatEntryCard live={live} sessionId={live.id} amGm={amGm} />

      <SectionDivider>
        {t('session.players')}
      </SectionDivider>

      <div className="divide-y divide-dnd-border/60 border-b border-dnd-border/60">
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

      {/* Indice della serata: stesse righe del menu del personaggio. */}
      {(amGm || live.campaign_id != null) && (
        <ul className="grid grid-cols-2 gap-x-4 border-t border-dnd-border">
          {[
            ...(amGm ? [{ key: 'grant', Icon: Gift, label: t('session.grant_item.button'), run: () => setShowGrantItem(true) }] : []),
            ...(live.campaign_id != null ? [
              { key: 'stash', Icon: Package, label: t('campaign.stash'), run: () => setShowStash(true) },
              // Lore, calendario e diario stanno nella pagina campagna: raggiungibile anche a serata in corso.
              { key: 'page', Icon: BookOpen, label: t('campaign.open_page'), run: () => navigate(`/campaign/${live.campaign_id}`) },
              { key: 'atlas', Icon: MapIcon, label: t('atlas.title'), run: () => navigate(`/campaign/${live.campaign_id}`, { state: { scrollTo: 'atlas' } }) },
            ] : []),
          ].map(({ key, Icon, label, run }) => (
            <li key={key} className="min-w-0 border-b border-dnd-border/60">
              <Pressable onClick={run} className={`${LEDGER_INDEX_ROW} text-dnd-text hover:text-dnd-gold-bright transition-colors`}>
                <Icon size={18} aria-hidden className="shrink-0 text-dnd-gold" />
                <span className="min-w-0 break-words font-body text-sm leading-tight">{label}</span>
              </Pressable>
            </li>
          ))}
        </ul>
      )}

      <SectionDivider>
        {t('session.chat_and_history')}
      </SectionDivider>

      <SessionFeed
        code={live.code}
        sessionId={live.id}
        campaignId={live.campaign_id ?? null}
        gmUserId={gmUserId}
        myUserId={myUserId}
        myCharId={myCharId}
        participants={live.participants}
        whisperTarget={whisperTarget}
        onClearWhisperTarget={() => setWhisperTarget(null)}
        onRewardEnqueued={handleRewardEnqueued}
      />

      <Button
        variant="danger"
        size="md"
        fullWidth
        icon={amGm ? <XOctagon size={16} /> : <LogOut size={16} />}
        loading={amGm ? closeMutation.isPending : leaveMutation.isPending}
        onClick={confirmLeave}
      >
        {amGm ? t('session.close') : t('session.leave')}
      </Button>

      <ParticipantIdentitySheet
        code={live.code}
        target={identityTarget}
        snapshot={
          identityTarget?.character_id
            ? snapshotsById.get(identityTarget.character_id)
            : undefined
        }
        myUserId={myUserId}
        onClose={() => setIdentityTarget(null)}
        onStartWhisper={(target) => setWhisperTarget(target)}
      />

      {showGrantItem && amGm && (
        <GrantItemModal
          sessionId={live.id}
          participants={live.participants}
          gmUserId={gmUserId}
          onClose={() => setShowGrantItem(false)}
        />
      )}

      {showStash && live.campaign_id != null && (
        <StashSheet
          sessionId={live.id}
          isGm={amGm}
          myCharId={myCharId}
          participants={live.participants}
          gmUserId={gmUserId}
          onClose={() => setShowStash(false)}
        />
      )}

      {currentReward && (
        <RewardPopup
          reward={currentReward}
          description={null}
          onDismiss={() => {
            dequeue()
            setCurrentReward(peek())
          }}
          onGoToInventory={() => {
            const r = currentReward
            dequeue()
            setCurrentReward(peek())
            navigate(`/char/${r.char_id}/inventory`, {
              state: { highlightItemId: r.item_id },
            })
          }}
        />
      )}
    </Layout>
  )
}

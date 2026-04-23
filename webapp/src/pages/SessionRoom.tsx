import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'
import { Crown, Heart, LogOut, Lock, Send, Shield, Sparkles, User, XOctagon, Dices } from 'lucide-react'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import Skeleton from '@/components/ui/Skeleton'
import SectionDivider from '@/components/ui/SectionDivider'
import { api } from '@/api/client'
import type { CharacterLiveSnapshot, SessionMessage, SessionParticipant } from '@/types'
import { haptic, telegramConfirm } from '@/auth/telegram'
import { formatCondition } from '@/lib/conditions'
import ParticipantIdentitySheet from '@/pages/session/ParticipantIdentitySheet'

function conditionLabels(
  conditions: Record<string, unknown> | null | undefined,
  t: TFunction,
): string[] {
  if (!conditions) return []
  return Object.entries(conditions)
    .filter(([, v]) => Boolean(v))
    .map(([key, val]) => formatCondition(key, val, t))
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
  const conds = conditionLabels(snapshot?.conditions, t)

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
  const Wrapper: any = isClickable ? 'button' : 'div'
  const wrapperProps = isClickable
    ? { type: 'button', onClick: handleClick, className: 'w-full text-left cursor-pointer' }
    : {}

  return (
    <Wrapper {...wrapperProps}>
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
              <p className="mt-2 text-[11px] text-[var(--dnd-amber)] font-body">
                ⚠ {conds.join(', ')}
              </p>
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
    </Wrapper>
  )
}

export default function SessionRoom() {
  const { id } = useParams<{ id: string }>()
  const sessionId = Number(id)
  const navigate = useNavigate()
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [chatInput, setChatInput] = useState('')
  const [whisperTo, setWhisperTo] = useState<number | null>(null)
  const [identityTarget, setIdentityTarget] = useState<SessionParticipant | null>(null)
  const [lastSeenMsgId, setLastSeenMsgId] = useState(0)
  const [chatCache, setChatCache] = useState<SessionMessage[]>([])
  const scrollerRef = useRef<HTMLDivElement | null>(null)

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

  const { data: msgDelta } = useQuery({
    queryKey: ['session-messages', sessionId, lastSeenMsgId],
    queryFn: () => api.sessions.messages(sessionId, lastSeenMsgId),
    refetchInterval: live?.status === 'active' ? 2000 : false,
    enabled: Number.isFinite(sessionId),
  })

  useEffect(() => {
    if (msgDelta && msgDelta.length > 0) {
      setChatCache((prev) => [...prev, ...msgDelta])
      const last = msgDelta[msgDelta.length - 1]
      setLastSeenMsgId(last.id)
    }
  }, [msgDelta])

  useEffect(() => {
    scrollerRef.current?.scrollTo({ top: scrollerRef.current.scrollHeight, behavior: 'smooth' })
  }, [chatCache.length])

  useEffect(() => {
    if (whisperTo === null) return
    const stillPresent = live?.participants.some((p) => p.user_id === whisperTo)
    if (!stillPresent) setWhisperTo(null)
  }, [live, whisperTo])

  const sendMutation = useMutation({
    mutationFn: (body: string) => api.sessions.sendMessage(sessionId, body, whisperTo),
    onSuccess: (msg) => {
      setChatCache((prev) => [...prev, msg])
      setLastSeenMsgId(msg.id)
      setChatInput('')
      haptic.light()
    },
    onError: () => haptic.error(),
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

  const senderLabel = (m: SessionMessage): string => {
    if (m.sender_display_name === '__GM__' || (m.role === 'game_master' && !m.sender_display_name))
      return t('session.game_master')
    return m.sender_display_name ?? t('session.unknown_sender')
  }

  const playerParticipants = useMemo(
    () => live?.participants.filter((p) => p.role !== 'game_master') ?? [],
    [live],
  )
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
        {t('session.chat')}
      </SectionDivider>

      <Surface variant="elevated">
        <div
          ref={scrollerRef}
          className="space-y-2 max-h-[260px] overflow-y-auto pr-1"
        >
          {chatCache.length === 0 ? (
            <p className="text-xs text-dnd-text-faint font-body italic text-center py-4">
              {t('session.chat_empty')}
            </p>
          ) : (
            chatCache.map((m) => {
              const mine = m.user_id === myUserId
              const isWhisper = !!m.recipient_user_id
              const recipientName = isWhisper
                ? (live.participants.find((p) => p.user_id === m.recipient_user_id)?.display_name
                   ?? (m.recipient_user_id === live.gm_user_id ? t('session.game_master') : `#${m.recipient_user_id}`))
                : null
              return (
                <div
                  key={m.id}
                  className={`max-w-[80%] rounded-lg px-3 py-2 text-sm font-body
                    ${isWhisper
                      ? 'bg-[var(--dnd-amber)]/15 border border-[var(--dnd-amber)]/40 italic'
                      : mine
                        ? 'ml-auto bg-gradient-gold text-dnd-ink'
                        : 'bg-dnd-surface border border-dnd-border text-dnd-text'}
                    ${mine && isWhisper ? 'ml-auto' : ''}`}
                >
                  {(!mine || isWhisper) && (
                    <p className="text-[10px] uppercase tracking-wider opacity-70 mb-0.5 font-cinzel flex items-center gap-1">
                      {isWhisper && <Lock size={10} />}
                      {mine ? t('session.you') : senderLabel(m)}
                      {isWhisper && recipientName && (
                        <span className="text-[var(--dnd-amber)]">
                          {' '}{t('session.whisper.recipient_prefix', { name: recipientName })}
                        </span>
                      )}
                    </p>
                  )}
                  <p className="whitespace-pre-wrap break-words">{m.body}</p>
                </div>
              )
            })
          )}
        </div>

        {amGm ? (
          <div className="flex items-center gap-2 mb-2">
            <Lock size={12} className="text-dnd-gold-dim shrink-0" />
            <select
              value={whisperTo ?? ''}
              onChange={(e) => setWhisperTo(e.target.value === '' ? null : Number(e.target.value))}
              className="flex-1 px-2 py-1 rounded bg-dnd-surface border border-dnd-border text-dnd-text font-body text-sm"
            >
              <option value="">{t('session.whisper.broadcast')}</option>
              {playerParticipants.map((p) => (
                <option key={p.user_id} value={p.user_id}>
                  {p.display_name ?? `#${p.user_id}`}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <div className="mb-2">
            <button
              type="button"
              onClick={() => setWhisperTo(whisperTo === null ? gmUserId : null)}
              disabled={gmUserId === null}
              className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-cinzel uppercase tracking-wider transition-colors
                ${whisperTo !== null
                  ? 'bg-[var(--dnd-amber)]/30 text-[var(--dnd-amber)] border border-[var(--dnd-amber)]/60'
                  : 'bg-dnd-surface text-dnd-text-muted border border-dnd-border hover:text-dnd-gold-bright'}`}
            >
              <Lock size={12} />
              {t('session.whisper.to_gm')}
            </button>
          </div>
        )}
        <div className="mt-3 flex items-center gap-2">
          <input
            type="text"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && chatInput.trim().length > 0) {
                sendMutation.mutate(chatInput.trim())
              }
            }}
            placeholder={t('session.message_placeholder')}
            maxLength={1000}
            className="flex-1 px-3 py-2 min-h-[44px] rounded-lg bg-dnd-surface border border-dnd-border
                       text-dnd-text outline-none focus:border-dnd-gold transition-colors font-body"
          />
          <Button
            size="sm"
            onClick={() => chatInput.trim() && sendMutation.mutate(chatInput.trim())}
            disabled={chatInput.trim().length === 0 || sendMutation.isPending}
            icon={<Send size={14} />}
            aria-label={t('session.send')}
          >
            <span className="sr-only">{t('session.send')}</span>
          </Button>
        </div>
      </Surface>

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

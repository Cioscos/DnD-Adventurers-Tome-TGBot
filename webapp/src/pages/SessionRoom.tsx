import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Crown, Heart, LogOut, Send, Shield, Sparkles, User, XOctagon, Dices } from 'lucide-react'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import Skeleton from '@/components/ui/Skeleton'
import SectionDivider from '@/components/ui/SectionDivider'
import { api } from '@/api/client'
import type { CharacterLiveSnapshot, SessionMessage, SessionParticipant } from '@/types'
import { haptic, telegramConfirm } from '@/auth/telegram'

function conditionLabels(conditions?: Record<string, unknown>): string[] {
  if (!conditions) return []
  return Object.entries(conditions)
    .filter(([, v]) => Boolean(v))
    .map(([k, v]) => {
      if (typeof v === 'number' && v > 0) return `${k} ${v}`
      return k
    })
}

function ParticipantRow({
  participant,
  snapshot,
  isGm,
  isMe,
}: {
  participant: SessionParticipant
  snapshot?: CharacterLiveSnapshot
  isGm: boolean
  isMe: boolean
}) {
  const { t } = useTranslation()
  const roleIcon = isGm ? <Crown size={14} className="text-dnd-gold-bright" /> : <User size={14} className="text-dnd-text-muted" />
  const hpPct = snapshot && snapshot.hit_points > 0
    ? Math.max(0, Math.min(100, Math.round((snapshot.current_hit_points / snapshot.hit_points) * 100)))
    : 0
  const conds = conditionLabels(snapshot?.conditions)

  return (
    <div className={`rounded-lg border p-3 ${isMe ? 'border-dnd-gold bg-dnd-surface-raised' : 'border-dnd-border bg-dnd-surface'}`}>
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
          <div className="mt-2 grid grid-cols-2 gap-2 text-xs font-mono">
            <div className="flex items-center gap-1.5">
              <Heart size={12} className="text-[var(--dnd-crimson-bright)]" />
              <span>{snapshot.current_hit_points}/{snapshot.hit_points}</span>
              {snapshot.temp_hp > 0 && <span className="text-dnd-arcane-bright">+{snapshot.temp_hp}</span>}
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
  )
}

export default function SessionRoom() {
  const { id } = useParams<{ id: string }>()
  const sessionId = Number(id)
  const navigate = useNavigate()
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [chatInput, setChatInput] = useState('')
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

  const sendMutation = useMutation({
    mutationFn: (body: string) => api.sessions.sendMessage(sessionId, body),
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
  })

  const closeMutation = useMutation({
    mutationFn: () => api.sessions.close(sessionId),
    onSuccess: () => {
      qc.setQueryData(['session-me'], null)
      qc.invalidateQueries({ queryKey: ['session-me'] })
      haptic.warning()
      navigate('/session')
    },
  })

  const snapshotsById = useMemo(() => {
    const map = new Map<number, CharacterLiveSnapshot>()
    live?.live_characters.forEach((c) => map.set(c.id, c))
    return map
  }, [live])

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

      <SectionDivider>
        {t('session.players')}
      </SectionDivider>

      <div className="space-y-2">
        {live.participants.map((p) => (
          <ParticipantRow
            key={`${p.user_id}-${p.joined_at}`}
            participant={p}
            snapshot={p.character_id ? snapshotsById.get(p.character_id) : undefined}
            isGm={p.role === 'game_master'}
            isMe={p.user_id === myUserId}
          />
        ))}
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
              return (
                <div
                  key={m.id}
                  className={`max-w-[80%] rounded-lg px-3 py-2 text-sm font-body
                    ${mine
                      ? 'ml-auto bg-gradient-gold text-dnd-ink'
                      : 'bg-dnd-surface border border-dnd-border text-dnd-text'}`}
                >
                  {!mine && (
                    <p className="text-[10px] uppercase tracking-wider opacity-70 mb-0.5 font-cinzel">
                      {m.role === 'game_master' ? t('session.game_master') : `#${m.user_id}`}
                    </p>
                  )}
                  <p className="whitespace-pre-wrap break-words">{m.body}</p>
                </div>
              )
            })
          )}
        </div>

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
    </Layout>
  )
}

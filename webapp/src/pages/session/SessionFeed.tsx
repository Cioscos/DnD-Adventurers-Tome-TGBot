import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Lock, Send, Crown, User as UserIcon } from 'lucide-react'
import { api } from '@/api/client'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import type { SessionFeedItem, SessionFeedResponse, SessionParticipant } from '@/types'
import { haptic } from '@/auth/telegram'
import { EVENT_META } from '@/lib/eventMeta'

interface Props {
  code: string
  sessionId: number
  amGm: boolean
  gmUserId: number | null
  myUserId: number
  participants: SessionParticipant[]
}

const POLL_MS = 3000

function formatTime(iso: string) {
  const d = new Date(iso)
  return d.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })
}

function itemKey(it: SessionFeedItem): string {
  return it.type === 'message' ? `m:${it.message_id ?? ''}` : `e:${it.event_id ?? ''}`
}

export default function SessionFeed({
  code,
  sessionId,
  amGm,
  gmUserId,
  myUserId,
  participants,
}: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()

  const [items, setItems] = useState<SessionFeedItem[]>([])
  const [hasMoreBefore, setHasMoreBefore] = useState(false)
  const [loadingPrev, setLoadingPrev] = useState(false)
  const [chatInput, setChatInput] = useState('')
  const [whisperTo, setWhisperTo] = useState<number | null>(null)

  const scrollerRef = useRef<HTMLDivElement | null>(null)
  const initialisedRef = useRef(false)
  const latestTsRef = useRef<string | null>(null)

  const oldestTs = items.length > 0 ? items[0].timestamp : null

  const mergeIncoming = (incoming: SessionFeedItem[]) => {
    if (incoming.length === 0) return
    setItems((prev) => {
      const seen = new Set<string>(prev.map(itemKey))
      const fresh = incoming.filter((it) => !seen.has(itemKey(it)))
      if (fresh.length === 0) return prev
      const next = [...prev, ...fresh]
      latestTsRef.current = next[next.length - 1].timestamp
      requestAnimationFrame(() => {
        scrollerRef.current?.scrollTo({ top: scrollerRef.current.scrollHeight, behavior: 'smooth' })
      })
      return next
    })
  }

  // Initial fetch + incremental polling via since cursor
  useEffect(() => {
    let cancelled = false

    async function initial() {
      try {
        const res = await api.sessions.getFeed(code, { limit: 100 })
        if (cancelled) return
        setItems(res.items)
        setHasMoreBefore(res.has_more)
        initialisedRef.current = true
        if (res.items.length > 0) {
          latestTsRef.current = res.items[res.items.length - 1].timestamp
        }
        requestAnimationFrame(() => {
          scrollerRef.current?.scrollTo({ top: scrollerRef.current?.scrollHeight ?? 0 })
        })
      } catch {
        /* empty state acceptable */
      }
    }

    initial()

    const tick = async () => {
      if (cancelled || !initialisedRef.current) return
      try {
        const since = latestTsRef.current ?? undefined
        const res: SessionFeedResponse = await api.sessions.getFeed(
          code,
          since ? { since, limit: 100 } : { limit: 100 },
        )
        if (cancelled) return
        mergeIncoming(res.items)
      } catch {
        /* next tick retries */
      }
    }

    const id = window.setInterval(tick, POLL_MS)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [code])

  const sendMutation = useMutation({
    mutationFn: (body: string) =>
      api.sessions.sendMessage(sessionId, body, whisperTo ?? undefined),
    onSuccess: () => {
      setChatInput('')
      haptic.success()
      qc.invalidateQueries({ queryKey: ['session-feed', code] })
      // Force immediate refetch so our message shows up without waiting.
      void (async () => {
        try {
          const since = latestTsRef.current ?? undefined
          const res: SessionFeedResponse = await api.sessions.getFeed(
            code,
            since ? { since, limit: 100 } : { limit: 100 },
          )
          mergeIncoming(res.items)
        } catch { /* noop */ }
      })()
    },
    onError: () => haptic.error(),
  })

  const loadPrevious = async () => {
    if (!oldestTs || loadingPrev) return
    setLoadingPrev(true)
    try {
      const res: SessionFeedResponse = await api.sessions.getFeed(code, { before: oldestTs, limit: 50 })
      setItems((prev) => [...res.items, ...prev])
      setHasMoreBefore(res.has_more)
    } catch {
      /* noop */
    } finally {
      setLoadingPrev(false)
    }
  }

  const playerParticipants = useMemo(
    () => participants.filter((p) => p.role !== 'game_master'),
    [participants],
  )

  const senderLabel = (it: SessionFeedItem): string => {
    if (it.role === 'game_master') return t('session.game_master')
    return it.display_name ?? `#${it.user_id ?? ''}`
  }

  const recipientName = (rid: number | null | undefined): string | null => {
    if (rid == null) return null
    if (rid === gmUserId) return t('session.game_master')
    const p = participants.find((pp) => pp.user_id === rid)
    return p?.display_name ?? `#${rid}`
  }

  return (
    <Surface variant="elevated">
      {hasMoreBefore && (
        <div className="flex justify-center mb-2">
          <button
            type="button"
            onClick={loadPrevious}
            disabled={loadingPrev}
            className="text-xs font-cinzel uppercase tracking-wider text-dnd-gold-dim hover:text-dnd-gold-bright disabled:opacity-50 px-3 py-1 rounded border border-dnd-border"
          >
            {loadingPrev ? t('session.loading_previous') : t('session.load_previous')}
          </button>
        </div>
      )}

      <div
        ref={scrollerRef}
        className="space-y-2 max-h-[320px] overflow-y-auto pr-1"
      >
        {items.length === 0 ? (
          <p className="text-xs text-dnd-text-faint font-body italic text-center py-4">
            {t('session.feed_empty')}
          </p>
        ) : (
          items.map((it) => {
            if (it.type === 'event') {
              const meta = EVENT_META[it.event_type ?? 'other'] ?? EVENT_META.other
              const Icon = meta.icon
              const iconColorClass = meta.tone.split(' ').find((c) => c.startsWith('text-')) ?? 'text-dnd-text-muted'
              return (
                <div
                  key={itemKey(it)}
                  className="flex items-center justify-center gap-2 text-xs italic opacity-80 px-3 py-1.5"
                >
                  <Icon size={12} className={iconColorClass} />
                  <span className="font-body text-dnd-text-muted">{it.description}</span>
                  <span className="font-mono text-[10px] text-dnd-text-faint">
                    {formatTime(it.timestamp)}
                  </span>
                </div>
              )
            }

            const mine = it.user_id === myUserId
            const isWhisper = !!it.recipient_user_id
            const recName = isWhisper ? recipientName(it.recipient_user_id ?? null) : null
            return (
              <div
                key={itemKey(it)}
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
                    {it.role === 'game_master' && !isWhisper && <Crown size={10} />}
                    {it.role === 'player' && !isWhisper && <UserIcon size={10} />}
                    {mine ? t('session.you') : senderLabel(it)}
                    {isWhisper && recName && (
                      <span className="text-[var(--dnd-amber)]">
                        {' '}{t('session.whisper.recipient_prefix', { name: recName })}
                      </span>
                    )}
                  </p>
                )}
                <p className="whitespace-pre-wrap break-words">{it.body}</p>
              </div>
            )
          })
        )}
      </div>

      {amGm ? (
        <div className="flex items-center gap-2 mt-3 mb-2">
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
        <div className="mt-3 mb-2">
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

      <div className="flex items-center gap-2">
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
          className="flex-1 px-3 py-2 rounded bg-dnd-surface border border-dnd-border text-dnd-text font-body text-sm"
        />
        <Button
          variant="primary"
          size="sm"
          onClick={() => chatInput.trim() && sendMutation.mutate(chatInput.trim())}
          disabled={!chatInput.trim() || sendMutation.isPending}
          icon={<Send size={14} />}
        >
          {t('session.send')}
        </Button>
      </div>
    </Surface>
  )
}

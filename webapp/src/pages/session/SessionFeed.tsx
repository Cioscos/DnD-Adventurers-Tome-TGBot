import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Gift, Lock, Maximize2, Send, User as UserIcon, X } from 'lucide-react'
import { GiCrown as Crown } from 'react-icons/gi'
import { toast } from 'sonner'
import { useNavigate } from 'react-router-dom'
import { api, ApiError } from '@/api/client'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import type { CharacterFull, SessionFeedItem, SessionFeedResponse, SessionParticipant } from '@/types'
import { haptic } from '@/auth/telegram'
import { useOverlayDismiss } from '@/hooks/useOverlayDismiss'
import { EVENT_META } from '@/lib/eventMeta'
import { enqueue, type Reward } from '@/lib/rewardQueue'
import { formatTime24 } from '@/lib/format'

const SLOW_MODE_MS = 3000

function extractRetryAfterMs(detail: unknown): number | null {
  if (detail && typeof detail === 'object' && 'retry_after' in detail) {
    const ra = (detail as { retry_after?: unknown }).retry_after
    if (typeof ra === 'number' && ra > 0) return Math.ceil(ra * 1000)
  }
  return null
}

interface Props {
  code: string
  sessionId: number
  gmUserId: number | null
  myUserId: number
  myCharId: number | null
  participants: SessionParticipant[]
  whisperTarget: SessionParticipant | null
  onClearWhisperTarget: () => void
  onRewardEnqueued?: () => void
}

const POLL_MS = 3000


function itemKey(it: SessionFeedItem): string {
  return it.type === 'message' ? `m:${it.message_id ?? ''}` : `e:${it.event_id ?? ''}`
}

export default function SessionFeed({
  code,
  sessionId,
  gmUserId,
  myUserId,
  myCharId,
  participants,
  whisperTarget,
  onClearWhisperTarget,
  onRewardEnqueued,
}: Props) {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const navigate = useNavigate()

  const [items, setItems] = useState<SessionFeedItem[]>([])
  const [hasMoreBefore, setHasMoreBefore] = useState(false)
  const [loadingPrev, setLoadingPrev] = useState(false)
  const [chatInput, setChatInput] = useState('')
  const [cooldownUntil, setCooldownUntil] = useState<number | null>(null)
  const [, setNowTick] = useState(0)
  const [fullscreen, setFullscreen] = useState(false)
  const whisperTo = whisperTarget?.user_id ?? null

  const scrollerRef = useRef<HTMLDivElement | null>(null)
  const initialisedRef = useRef(false)
  const latestTsRef = useRef<string | null>(null)

  const oldestTs = items.length > 0 ? items[0].timestamp : null

  const mergeIncoming = (incoming: SessionFeedItem[], opts: { skipReward?: boolean } = {}) => {
    if (incoming.length === 0) return
    setItems((prev) => {
      const seen = new Set<string>(prev.map(itemKey))
      const fresh = incoming.filter((it) => !seen.has(itemKey(it)))
      if (fresh.length === 0) return prev

      if (!opts.skipReward && myCharId !== null) {
        let enqueuedAny = false
        for (const it of fresh) {
          if (
            it.type === 'message' &&
            it.message_id != null &&
            it.item_id != null &&
            it.item_name &&
            it.recipient_user_id === myUserId
          ) {
            const r: Reward = {
              message_id: it.message_id,
              item_id: it.item_id,
              item_name: it.item_name,
              item_quantity: it.item_quantity ?? 1,
              char_id: myCharId,
              granted_at: it.timestamp,
            }
            enqueue(r)
            enqueuedAny = true
          }
        }
        if (enqueuedAny) onRewardEnqueued?.()
      }

      const next = [...prev, ...fresh]
      latestTsRef.current = next[next.length - 1].timestamp
      requestAnimationFrame(() => {
        scrollerRef.current?.scrollTo({ top: scrollerRef.current.scrollHeight, behavior: 'smooth' })
      })
      return next
    })
  }

  // Keep the polling effect (keyed only on `code`) decoupled from the
  // ever-recreated mergeIncoming closure: read the latest via ref.
  const mergeIncomingRef = useRef(mergeIncoming)
  mergeIncomingRef.current = mergeIncoming

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
        mergeIncomingRef.current(res.items)
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
      setCooldownUntil(Date.now() + SLOW_MODE_MS)
      onClearWhisperTarget()
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
    onError: (err) => {
      haptic.error()
      if (err instanceof ApiError && err.status === 429) {
        const retryMs = extractRetryAfterMs(err.detail) ?? SLOW_MODE_MS
        setCooldownUntil(Date.now() + retryMs)
        toast.warning(t('session.slow_mode.toast', { seconds: Math.ceil(retryMs / 1000) }))
      }
    },
  })

  // Countdown ticker: re-render once per second while cooldown active.
  useEffect(() => {
    if (cooldownUntil === null) return
    const remaining = cooldownUntil - Date.now()
    if (remaining <= 0) {
      setCooldownUntil(null)
      return
    }
    const id = window.setInterval(() => {
      if (Date.now() >= cooldownUntil) {
        setCooldownUntil(null)
      } else {
        setNowTick((n) => n + 1)
      }
    }, 250)
    return () => window.clearInterval(id)
  }, [cooldownUntil])

  const cooldownRemaining =
    cooldownUntil !== null ? Math.max(0, Math.ceil((cooldownUntil - Date.now()) / 1000)) : 0
  const onCooldown = cooldownRemaining > 0

  // ESC/back chiudono il fullscreen (stack overlay condiviso); qui restano
  // scroll lock, expand Telegram e lo scroll in fondo dopo lo swap di layout.
  useOverlayDismiss(fullscreen, () => setFullscreen(false))
  useEffect(() => {
    if (!fullscreen) return
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const tg = (window as { Telegram?: { WebApp?: { expand?: () => void } } }).Telegram?.WebApp
    tg?.expand?.()
    requestAnimationFrame(() => {
      scrollerRef.current?.scrollTo({ top: scrollerRef.current.scrollHeight })
    })
    return () => {
      document.body.style.overflow = prevOverflow
    }
  }, [fullscreen])

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

  const handleGrantClick = (it: SessionFeedItem) => {
    if (myCharId === null || it.item_id == null) return
    const cached = qc.getQueryData<CharacterFull>(['character', myCharId])
    // Only fail-fast when we have authoritative cached data showing the item is gone.
    // If the character query has never been fetched (cold cache, e.g. user landed
    // directly in SessionRoom), navigate optimistically — Inventory will silently
    // clear highlight state if the item turns out to be missing.
    if (cached?.items && !cached.items.some((x) => x.id === it.item_id)) {
      toast.warning(t('session.reward.item_not_found_toast'))
      haptic.error()
      return
    }
    navigate(`/char/${myCharId}/inventory`, { state: { highlightItemId: it.item_id } })
  }

  const scrollerClass = fullscreen
    ? 'space-y-2 flex-1 min-h-0 overflow-y-auto pr-1'
    : 'space-y-2 max-h-[320px] overflow-y-auto pr-1'

  const chatBody = (
    <>
      {hasMoreBefore && (
        <div className="flex justify-center mb-2">
          <button
            type="button"
            onClick={loadPrevious}
            disabled={loadingPrev}
            className="min-h-[40px] text-xs font-cinzel uppercase tracking-wider text-dnd-gold-dim hover:text-dnd-gold-bright disabled:opacity-50 px-3 py-1 rounded-lg border border-dnd-border"
          >
            {loadingPrev ? t('session.loading_previous') : t('session.load_previous')}
          </button>
        </div>
      )}

      <div
        ref={scrollerRef}
        className={scrollerClass}
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
                  <span className="font-body text-dnd-text-muted">
                    {it.character_name ? (
                      <>
                        <span className="font-cinzel text-dnd-gold-dim not-italic">
                          {it.character_name}
                        </span>
                        {' · '}
                        {it.description}
                      </>
                    ) : (
                      it.description
                    )}
                  </span>
                  <span className="font-mono text-[10px] text-dnd-text-faint">
                    {formatTime24(it.timestamp, i18n.language)}
                  </span>
                </div>
              )
            }

            const mine = it.user_id === myUserId
            const isWhisper = !!it.recipient_user_id
            const recName = isWhisper ? recipientName(it.recipient_user_id ?? null) : null
            // Legacy grant messages (pre-2.14.0) lack item_name and fall back to raw body.
            const isGrant = it.item_id != null && !!it.item_name
            const isGrantToMe =
              !!it.item_id && it.recipient_user_id === myUserId && myCharId !== null
            const grantBody = isGrant
              ? it.recipient_user_id === myUserId
                ? t('session.feed.grant_received', {
                    name: it.item_name,
                    qty: it.item_quantity ?? 1,
                  })
                : t('session.feed.grant_sent', {
                    recipient: recipientName(it.recipient_user_id ?? null) ?? '',
                    name: it.item_name,
                    qty: it.item_quantity ?? 1,
                  })
              : null

            const bubbleContent = (
              <>
                {(!mine || isWhisper) && (
                  <p className="text-[10px] uppercase tracking-wider opacity-70 mb-0.5 font-cinzel flex items-center gap-1">
                    {isWhisper && <Lock size={10} />}
                    {it.role === 'game_master' && !isWhisper && <Crown size={10} />}
                    {it.role === 'player' && !isWhisper && <UserIcon size={10} />}
                    {mine ? t('session.you') : senderLabel(it)}
                    {isWhisper && recName && (
                      <span className="text-dnd-amber">
                        {' '}{t('session.whisper.recipient_prefix', { name: recName })}
                      </span>
                    )}
                  </p>
                )}
                <p className="whitespace-pre-wrap break-words">
                  {isGrant && <Gift size={12} className="inline -mt-0.5 mr-1 text-dnd-gold-bright" />}
                  {grantBody ?? it.body}
                </p>
                {isGrantToMe && (
                  <p className="text-[10px] uppercase tracking-wider mt-1 text-dnd-amber/80 font-cinzel">
                    {t('session.feed.grant_chip')}
                  </p>
                )}
              </>
            )

            const baseClass = `max-w-[80%] rounded-lg px-3 py-2 text-sm font-body text-left
              ${isWhisper
                ? 'bg-dnd-amber/15 border border-dnd-amber/40 italic'
                : mine
                  ? 'ml-auto bg-gradient-gold text-dnd-ink'
                  : 'bg-dnd-surface border border-dnd-border text-dnd-text'}
              ${mine && isWhisper ? 'ml-auto' : ''}`

            if (isGrantToMe) {
              return (
                <button
                  key={itemKey(it)}
                  type="button"
                  onClick={() => handleGrantClick(it)}
                  className={`${baseClass} cursor-pointer hover:bg-dnd-amber/25 transition-colors`}
                >
                  {bubbleContent}
                </button>
              )
            }
            return (
              <div key={itemKey(it)} className={baseClass}>
                {bubbleContent}
              </div>
            )
          })
        )}
      </div>

      {whisperTarget && (
        <div className="mt-3 mb-2 flex items-center justify-between gap-2 rounded-full px-3 py-1.5 bg-dnd-amber/20 border border-dnd-amber/60">
          <div className="flex items-center gap-2 min-w-0">
            <Lock size={12} className="text-dnd-amber shrink-0" />
            <span className="text-xs font-cinzel uppercase tracking-wider text-dnd-amber truncate">
              {t('session.whisper.target_chip', {
                name:
                  whisperTarget.user_id === gmUserId
                    ? t('session.game_master')
                    : whisperTarget.display_name ?? `#${whisperTarget.user_id}`,
              })}
            </span>
          </div>
          <button
            type="button"
            onClick={onClearWhisperTarget}
            aria-label={t('session.whisper.cancel')}
            className="hit-44 w-7 h-7 inline-flex items-center justify-center rounded-full text-dnd-amber hover:text-dnd-gold-bright"
          >
            <X size={14} />
          </button>
        </div>
      )}

      <div className="mt-4 flex items-center gap-2">
        <input
          type="text"
          value={chatInput}
          onChange={(e) => setChatInput(e.target.value)}
          onKeyDown={(e) => {
            if (
              e.key === 'Enter' &&
              chatInput.trim().length > 0 &&
              !onCooldown &&
              !sendMutation.isPending
            ) {
              sendMutation.mutate(chatInput.trim())
            }
          }}
          placeholder={
            onCooldown
              ? t('session.slow_mode.cooldown', { seconds: cooldownRemaining })
              : t('session.message_placeholder')
          }
          disabled={onCooldown || sendMutation.isPending}
          className="flex-1 min-h-[44px] px-3 py-2 rounded-lg bg-dnd-surface border border-dnd-border focus:border-dnd-gold/70 outline-none text-dnd-text font-body text-sm disabled:opacity-50"
        />
        <Button
          variant="primary"
          size="sm"
          onClick={() =>
            chatInput.trim() &&
            !onCooldown &&
            !sendMutation.isPending &&
            sendMutation.mutate(chatInput.trim())
          }
          disabled={!chatInput.trim() || sendMutation.isPending || onCooldown}
          icon={<Send size={14} />}
        >
          {onCooldown ? `${cooldownRemaining}s` : t('session.send')}
        </Button>
      </div>
    </>
  )

  if (fullscreen) {
    return createPortal(
      <div className="fixed inset-0 z-[60] flex flex-col bg-dnd-bg">
        <header className="flex items-center justify-between px-4 py-3 pt-safe border-b border-dnd-border bg-dnd-surface-raised shrink-0">
          <h2 className="font-display font-bold text-dnd-gold-bright text-base">
            {t('session.chat_and_history')}
          </h2>
          <button
            type="button"
            onClick={() => setFullscreen(false)}
            aria-label={t('session.chat_fullscreen_close')}
            title={t('session.chat_fullscreen_close')}
            className="w-10 h-10 inline-flex items-center justify-center rounded-full text-dnd-gold-dim hover:text-dnd-gold-bright hover:bg-dnd-surface transition-colors"
          >
            <X size={18} />
          </button>
        </header>
        <div className="flex-1 min-h-0 flex flex-col p-3 pb-safe gap-2">
          {chatBody}
        </div>
      </div>,
      document.body,
    )
  }

  return (
    <Surface variant="elevated" className="relative">
      <div className="flex items-center justify-end mb-1">
        <button
          type="button"
          onClick={() => setFullscreen(true)}
          aria-label={t('session.chat_fullscreen_open')}
          title={t('session.chat_fullscreen_open')}
          className="w-10 h-10 inline-flex items-center justify-center rounded-lg text-dnd-gold-dim hover:text-dnd-gold-bright hover:bg-dnd-surface-raised transition-colors"
        >
          <Maximize2 size={14} />
        </button>
      </div>
      {chatBody}
    </Surface>
  )
}

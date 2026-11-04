import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Trash2, Search, X, WifiOff } from 'lucide-react'
import { GiOpenBook as BookOpen } from 'react-icons/gi'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import Input from '@/components/ui/Input'
import ScrollArea from '@/components/ScrollArea'
import Skeleton from '@/components/ui/Skeleton'
import EmptyState from '@/components/ui/EmptyState'
import { haptic } from '@/auth/telegram'
import { EVENT_META } from '@/lib/eventMeta'
import { LEDGER_TITLE } from '@/styles/ledger'
import { formatRelative, formatAbsolute } from '@/lib/relativeTime'

export default function History() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const [confirmClear, setConfirmClear] = useState(false)

  const historyQuery = useQuery({
    queryKey: ['history', charId],
    queryFn: () => api.history.get(charId),
  })
  const { isLoading } = historyQuery
  const entries = useMemo(() => historyQuery.data ?? [], [historyQuery.data])

  const [search, setSearch] = useState('')
  const filteredEntries = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return entries
    return entries.filter((e) => e.description.toLowerCase().includes(q))
  }, [entries, search])

  const clearMutation = useMutation({
    mutationFn: () => api.history.clear(charId),
    onSuccess: () => {
      qc.setQueryData(['history', charId], [])
      setConfirmClear(false)
      haptic.success()
    },
  })

  const locale = (i18n.language?.startsWith('en') ? 'en' : 'it') as 'it' | 'en'
  const formatDate = (iso: string) => formatRelative(iso, {
    locale,
    todayLabel: t('common.date.today'),
    yesterdayLabel: t('common.date.yesterday'),
  })

  return (
    <Layout title={t('character.history.title')} backTo={`/char/${charId}`} group="tools" page="history" hideScrollbar offlineQuery={historyQuery}>
      {isLoading ? (
        <div>
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex gap-3 px-1 py-3 border-b border-dnd-border/60">
              <Skeleton.Circle width="32px" delay={i * 80} />
              <div className="flex-1 space-y-2">
                <Skeleton.Line width="80%" height="14px" delay={i * 80} />
                <Skeleton.Line width="40%" height="10px" delay={i * 80 + 50} />
              </div>
            </div>
          ))}
        </div>
      ) : historyQuery.isError && historyQuery.data === undefined ? (
        // Un fetch fallito non è "cronologia vuota".
        <EmptyState
          icon={<WifiOff size={32} />}
          title={t('common.offline_unavailable')}
          action={{ label: t('common.retry'), onClick: () => historyQuery.refetch() }}
        />
      ) : entries.length === 0 ? (
        <EmptyState
          icon={<BookOpen size={32} />}
          title={t('character.history.empty')}
          hint={t('character.history.empty_hint')}
        />
      ) : (
        <>
          {/* Top-of-page action bar — clear button always reachable without scrolling. */}
          <div className="flex items-center justify-between gap-2">
            <span className={LEDGER_TITLE}>
              {t('character.history.entries_count', {
                count: search ? filteredEntries.length : entries.length,
              })}
            </span>
            <Button
              variant="danger"
              size="sm"
              onClick={() => setConfirmClear(true)}
              icon={<Trash2 size={12} />}
              haptic="warning"
            >
              {t('character.history.clear')}
            </Button>
          </div>

          {/* Search filter — client-side substring match on description. */}
          <Input
            type="search"
            value={search}
            onChange={setSearch}
            placeholder={t('character.history.search_placeholder')}
            leadingIcon={<Search size={14} />}
            trailingAction={
              search ? (
                <Pressable
                  onClick={() => setSearch('')}
                  className="w-11 h-11 rounded-full flex items-center justify-center text-dnd-text-faint hover:text-dnd-gold-bright"
                  aria-label={t('common.cancel')}
                >
                  <X size={14} />
                </Pressable>
              ) : undefined
            }
          />

          <ScrollArea>
            <div>
              <div className="border-y border-dnd-border divide-y divide-dnd-border/60">
                {filteredEntries.length === 0 && search && (
                  <p className="px-1 text-sm italic text-dnd-text-muted font-body py-4">
                    {t('character.history.no_match')}
                  </p>
                )}
                {filteredEntries.map((entry, idx) => {
                  const meta = EVENT_META[entry.event_type] ?? EVENT_META.other
                  const Icon = meta.icon
                  const absoluteTime = formatAbsolute(entry.timestamp, locale)
                  return (
                    <m.div
                      key={entry.id}
                      className="flex gap-3 items-start px-1 py-2.5"
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.03 }}
                    >
                      {/* Il colore dice il tipo di evento: l'icona basta, senza cerchio. */}
                      <span className={`mt-0.5 shrink-0 ${meta.tone} !bg-transparent`}>
                        <Icon size={18} aria-hidden />
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm leading-snug font-body text-dnd-text [overflow-wrap:anywhere]">
                          {entry.description}
                        </p>
                        <p
                          className="text-xs text-dnd-text-faint font-mono mt-0.5 cursor-help"
                          title={absoluteTime}
                        >
                          {formatDate(entry.timestamp)}
                        </p>
                      </div>
                    </m.div>
                  )
                })}
              </div>
            </div>
          </ScrollArea>
        </>
      )}

      <ConfirmSheet
        open={confirmClear}
        onClose={() => setConfirmClear(false)}
        onConfirm={() => clearMutation.mutate()}
        title={t('character.history.clear')}
        body={t('character.history.clear_confirm')}
        confirmLabel={t('common.confirm')}
        loading={clearMutation.isPending}
      />
    </Layout>
  )
}

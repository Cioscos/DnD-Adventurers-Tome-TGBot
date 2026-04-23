import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Trash2, BookOpen } from 'lucide-react'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import Sheet from '@/components/ui/Sheet'
import ScrollArea from '@/components/ScrollArea'
import Skeleton from '@/components/ui/Skeleton'
import { haptic } from '@/auth/telegram'
import { EVENT_META } from '@/lib/eventMeta'

export default function History() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [confirmClear, setConfirmClear] = useState(false)

  const { data: entries = [], isLoading } = useQuery({
    queryKey: ['history', charId],
    queryFn: () => api.history.get(charId),
  })

  const clearMutation = useMutation({
    mutationFn: () => api.history.clear(charId),
    onSuccess: () => {
      qc.setQueryData(['history', charId], [])
      setConfirmClear(false)
      haptic.success()
    },
  })

  const formatDate = (iso: string) => {
    const d = new Date(iso)
    return d.toLocaleDateString('it-IT', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
  }

  return (
    <Layout title={t('character.history.title')} backTo={`/char/${charId}`} group="tools" page="history">
      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex gap-3 px-4 py-3 rounded-xl bg-dnd-surface border border-dnd-border">
              <Skeleton.Circle width="32px" delay={i * 80} />
              <div className="flex-1 space-y-2">
                <Skeleton.Line width="80%" height="14px" delay={i * 80} />
                <Skeleton.Line width="40%" height="10px" delay={i * 80 + 50} />
              </div>
            </div>
          ))}
        </div>
      ) : entries.length === 0 ? (
        <Surface variant="flat" className="text-center py-8">
          <BookOpen className="mx-auto text-dnd-text-faint mb-2" size={32} />
          <p className="text-dnd-text-muted font-body italic">{t('character.history.empty')}</p>
        </Surface>
      ) : (
        <>
          <ScrollArea>
            <div className="relative">
              {/* Vertical timeline line — gold gradient + glow + inner highlight */}
              <div
                className="absolute left-[23px] top-2 bottom-2 w-1 rounded-full"
                style={{
                  background:
                    'linear-gradient(to bottom, transparent 0%, var(--dnd-gold-deep) 6%, var(--dnd-gold) 25%, var(--dnd-gold-bright) 50%, var(--dnd-gold) 75%, var(--dnd-gold-deep) 94%, transparent 100%)',
                  boxShadow: '0 0 6px var(--dnd-gold-glow), 0 0 12px rgba(212,175,55,0.35)',
                }}
              />
              <div
                className="absolute left-[24.5px] top-2 bottom-2 w-px opacity-80"
                style={{
                  background:
                    'linear-gradient(to bottom, transparent 0%, rgba(255,240,200,0.7) 30%, rgba(255,240,200,0.9) 50%, rgba(255,240,200,0.7) 70%, transparent 100%)',
                }}
              />
              <div className="space-y-3">
                {[...entries].reverse().map((entry, idx) => {
                  const meta = EVENT_META[entry.event_type] ?? EVENT_META.other
                  const Icon = meta.icon
                  return (
                    <m.div
                      key={entry.id}
                      className="relative flex gap-3 items-start"
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.03 }}
                    >
                      {/* Icon pill (on the timeline) */}
                      <div className={`w-12 h-12 rounded-full flex items-center justify-center border-2 ${meta.tone} shadow-parchment-md shrink-0 z-10 relative`}>
                        <Icon size={18} />
                      </div>
                      {/* Content */}
                      <div className="flex-1 min-w-0 pt-1">
                        <p className="text-sm leading-snug font-body text-dnd-text">
                          {entry.description}
                        </p>
                        <p className="text-[10px] text-dnd-text-faint font-mono mt-0.5">
                          {formatDate(entry.timestamp)}
                        </p>
                      </div>
                    </m.div>
                  )
                })}
              </div>
            </div>
          </ScrollArea>

          <Button
            variant="danger"
            size="md"
            fullWidth
            onClick={() => setConfirmClear(true)}
            icon={<Trash2 size={14} />}
          >
            {t('character.history.clear')}
          </Button>
        </>
      )}

      <Sheet
        open={confirmClear}
        onClose={() => setConfirmClear(false)}
        centered
        title={t('character.history.clear')}
      >
        <div className="p-5 space-y-3">
          <p className="text-sm text-center text-dnd-text font-body">
            {t('character.history.clear_confirm')}
          </p>
          <div className="flex gap-2">
            <Button
              variant="danger"
              fullWidth
              onClick={() => clearMutation.mutate()}
              loading={clearMutation.isPending}
              haptic="error"
            >
              {t('common.confirm')}
            </Button>
            <Button variant="secondary" fullWidth onClick={() => setConfirmClear(false)}>
              {t('common.cancel')}
            </Button>
          </div>
        </div>
      </Sheet>
    </Layout>
  )
}

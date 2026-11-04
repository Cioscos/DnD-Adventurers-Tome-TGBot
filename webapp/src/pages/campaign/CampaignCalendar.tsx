import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Check, CalendarClock, Ban, ChevronLeft, ChevronRight, Plus } from 'lucide-react'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import SectionDivider from '@/components/ui/SectionDivider'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import ScheduleSheet from '@/pages/campaign/ScheduleSheet'
import { dateKey, fromServer } from '@/lib/calendarDates'
import { api } from '@/api/client'
import { notifyMutationError } from '@/lib/mutationError'
import type { CampaignSessionEntry, ScheduleRead } from '@/types'

type Mark = 'done' | 'planned' | 'skipped'
// Oro = giocata, cobalto (info) = programmata, spenta = saltata: sempre icona + colore.
const MARK_STYLE: Record<Mark, string> = {
  done: 'text-dnd-gold-bright',
  planned: 'text-dnd-info-text',
  skipped: 'text-dnd-text-muted',
}
const MARK_ICON = { done: Check, planned: CalendarClock, skipped: Ban }

/** Calendario mensile delle serate: passate (da `sessions`) e programmate (dal master). */
export default function CampaignCalendar({ campaignId, isGm, sessions }: { campaignId: number; isGm: boolean; sessions: CampaignSessionEntry[] }) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const tag = i18n.language === 'en' ? 'en-US' : 'it-IT'
  const today = new Date()
  const [cursor, setCursor] = useState({ y: today.getFullYear(), m: today.getMonth() })
  const [selected, setSelected] = useState<string | null>(null)
  const [editing, setEditing] = useState<ScheduleRead | 'new' | null>(null)
  const [cancelling, setCancelling] = useState<ScheduleRead | null>(null)

  const { data: schedule } = useQuery({ queryKey: ['schedule', campaignId], queryFn: () => api.campaigns.schedule.list(campaignId) })
  const del = useMutation({
    mutationFn: (r: ScheduleRead) => api.campaigns.schedule.remove(campaignId, r.id),
    onSuccess: () => { setCancelling(null); qc.invalidateQueries({ queryKey: ['schedule', campaignId] }) },
    onError: () => { setCancelling(null); notifyMutationError() },
  })

  // Giorno locale → serate. Le righe `done` sono già nelle sessioni: non si contano due volte.
  const byDay = useMemo(() => {
    const map = new Map<string, { sessions: CampaignSessionEntry[]; rows: ScheduleRead[] }>()
    const slot = (k: string) => {
      if (!map.has(k)) map.set(k, { sessions: [], rows: [] })
      return map.get(k)!
    }
    sessions.forEach((s) => slot(dateKey(fromServer(s.created_at))).sessions.push(s))
    ;(schedule ?? []).filter((r) => r.status !== 'done').forEach((r) => slot(dateKey(fromServer(r.starts_at))).rows.push(r))
    return map
  }, [sessions, schedule])

  const first = new Date(cursor.y, cursor.m, 1)
  const daysInMonth = new Date(cursor.y, cursor.m + 1, 0).getDate()
  const weekStart = i18n.language === 'en' ? 0 : 1
  const lead = (first.getDay() - weekStart + 7) % 7
  const fmt = (o: Intl.DateTimeFormatOptions, d: Date) => new Intl.DateTimeFormat(tag, o).format(d)
  // 4 gennaio 2026 è domenica: base per i nomi dei giorni.
  const heads = Array.from({ length: 7 }, (_, i) => fmt({ weekday: 'short' }, new Date(2026, 0, 4 + weekStart + i)))
  const move = (delta: number) => {
    setCursor(({ y, m }) => { const d = new Date(y, m + delta, 1); return { y: d.getFullYear(), m: d.getMonth() } })
    setSelected(null)
  }
  const markOf = (k: string): Mark | undefined => {
    const e = byDay.get(k)
    if (!e) return undefined
    if (e.rows.some((r) => r.status === 'planned')) return 'planned'
    if (e.sessions.length) return 'done'
    return e.rows.length ? 'skipped' : undefined
  }
  const sel = selected ? byDay.get(selected) : undefined
  const todayKey = dateKey(today)

  return (
    <>
      <SectionDivider>{t('campaign.calendar.title')}</SectionDivider>
      <section>
        <div className="flex items-center justify-between gap-2">
          <Button variant="secondary" size="sm" className="min-w-11" aria-label={t('campaign.calendar.prev')} icon={<ChevronLeft size={16} />} onClick={() => move(-1)} />
          <p className="font-display font-bold text-dnd-gold-bright capitalize text-center">{fmt({ month: 'long', year: 'numeric' }, first)}</p>
          <Button variant="secondary" size="sm" className="min-w-11" aria-label={t('campaign.calendar.next')} icon={<ChevronRight size={16} />} onClick={() => move(1)} />
        </div>
        <div className="-mx-3 mt-2 grid grid-cols-7 gap-0.5 text-center">
          {heads.map((h) => (
            <span key={h} data-testid="weekday" className="text-xs font-cinzel uppercase text-dnd-text-muted">{h}</span>
          ))}
        </div>
        <div className="-mx-3 mt-1 grid grid-cols-7 gap-0.5" data-testid="grid">
          {Array.from({ length: daysInMonth }, (_, i) => {
            const d = new Date(cursor.y, cursor.m, i + 1)
            const k = dateKey(d)
            const mark = markOf(k)
            const Icon = mark && MARK_ICON[mark]
            return (
              <Pressable
                key={k}
                style={i === 0 ? { gridColumnStart: lead + 1 } : undefined}
                aria-label={`${i + 1} ${fmt({ weekday: 'long', month: 'long', year: 'numeric' }, d)}`}
                aria-pressed={selected === k}
                onClick={() => setSelected(selected === k ? null : k)}
                className={`flex min-h-11 min-w-0 flex-col items-center justify-center rounded-lg border text-sm font-mono tabular-nums ${
                  selected === k ? 'border-dnd-gold bg-dnd-gold/20 text-dnd-gold-bright' : k === todayKey ? 'border-dnd-gold-dim text-dnd-text' : 'border-transparent text-dnd-text'
                }`}
              >
                <span>{i + 1}</span>
                {Icon && mark ? <span data-mark={mark} className={MARK_STYLE[mark]}><Icon size={12} /></span> : <span className="h-3" />}
              </Pressable>
            )
          })}
        </div>

        {selected && (
          <div className="mt-3 space-y-2 border-t border-dnd-border pt-3" data-testid="day-detail">
            {!sel && <p className="text-sm text-dnd-text-muted italic">{t('campaign.calendar.none')}</p>}
            {sel?.sessions.map((s) =>
              s.has_recap ? (
                <Pressable key={s.id} className="flex min-h-11 w-full items-center gap-2 text-left text-sm font-body" onClick={() => navigate(`/campaign/${campaignId}/recap/${s.id}`)}>
                  <Check size={14} className={MARK_STYLE.done} />
                  <span className="min-w-0 break-words">{t('campaign.night_n', { n: s.number })}</span>
                </Pressable>
              ) : (
                <p key={s.id} className="flex items-center gap-2 text-sm font-body">
                  <Check size={14} className={MARK_STYLE.done} />
                  <span className="min-w-0 break-words">{t('campaign.night_n', { n: s.number })}</span>
                </p>
              ),
            )}
            {sel?.rows.map((r) => {
              const Icon = MARK_ICON[r.status as Mark]
              return (
                <div key={r.id} className="text-sm font-body">
                  <p className="flex items-center gap-2">
                    <Icon size={14} className={MARK_STYLE[r.status as Mark]} />
                    <span className="font-mono tabular-nums">{fmt({ hour: '2-digit', minute: '2-digit' }, fromServer(r.starts_at))}</span>
                    <span className="text-dnd-text-muted">{t(r.status === 'skipped' ? 'campaign.calendar.skipped' : 'campaign.calendar.planned')}</span>
                  </p>
                  {r.note && <p className="mt-1 break-words text-dnd-text-muted">{r.note}</p>}
                  {isGm && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {r.status === 'planned' && <Button variant="secondary" size="sm" onClick={() => setEditing(r)}>{t('campaign.calendar.move')}</Button>}
                      <Button variant="danger" size="sm" onClick={() => setCancelling(r)}>{t('campaign.calendar.cancel')}</Button>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {isGm && (
          <div className="mt-3">
            <Button variant="secondary" size="sm" icon={<Plus size={14} />} onClick={() => setEditing('new')}>
              {t('campaign.calendar.schedule')}
            </Button>
          </div>
        )}
      </section>

      <ScheduleSheet
        open={editing !== null}
        campaignId={campaignId}
        row={editing === 'new' ? null : editing}
        defaultDate={selected && selected >= todayKey ? selected : ''}
        onClose={() => setEditing(null)}
      />
      <ConfirmSheet
        open={cancelling !== null}
        onClose={() => setCancelling(null)}
        onConfirm={() => cancelling && del.mutate(cancelling)}
        loading={del.isPending}
        title={t('campaign.calendar.cancel_title')}
        body={t('campaign.calendar.cancel_body')}
        confirmLabel={t('campaign.calendar.cancel_confirm')}
      />
    </>
  )
}

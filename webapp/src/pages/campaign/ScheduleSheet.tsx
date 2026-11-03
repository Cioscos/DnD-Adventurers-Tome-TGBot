import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import { api, ApiError } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { pad, dateKey, fromServer } from '@/lib/calendarDates'
import type { ScheduleRead } from '@/types'


interface Props {
  open: boolean
  campaignId: number
  /** null = nuova programmazione; con una riga la sheet sposta quella serata. */
  row: ScheduleRead | null
  /** Giorno suggerito (YYYY-MM-DD) per una nuova serata. */
  defaultDate?: string
  onClose: () => void
}

/** Programma o sposta una serata: data e ora locali, inviate come ISO con offset (toISOString → Z). */
export default function ScheduleSheet({ open, campaignId, row, defaultDate = '', onClose }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [date, setDate] = useState('')
  const [time, setTime] = useState('21:00')
  const [note, setNote] = useState('')
  const [err, setErr] = useState('')

  useEffect(() => {
    if (!open) return
    setErr('')
    if (row) {
      const d = fromServer(row.starts_at)
      setDate(dateKey(d))
      setTime(`${pad(d.getHours())}:${pad(d.getMinutes())}`)
      setNote(row.note ?? '')
    } else {
      setDate(defaultDate)
      setTime('21:00')
      setNote('')
    }
  }, [open, row, defaultDate])

  const save = useMutation({
    mutationFn: () => {
      const starts_at = new Date(`${date}T${time}`).toISOString()
      const n = note.trim() || null
      return row
        ? api.campaigns.schedule.update(campaignId, row.id, { starts_at, note: n })
        : api.campaigns.schedule.create(campaignId, { starts_at, ...(n ? { note: n } : {}) })
    },
    onSuccess: () => {
      haptic.success()
      qc.invalidateQueries({ queryKey: ['schedule', campaignId] })
      onClose()
    },
    onError: (e) => setErr(t(e instanceof ApiError && e.status === 422 ? 'campaign.calendar.err_past' : 'campaign.calendar.err_generic')),
  })

  return (
    <Sheet open={open} onClose={onClose} title={t(row ? 'campaign.calendar.sheet_edit' : 'campaign.calendar.sheet_new')}>
      <div className="p-5 space-y-3">
        <Input type="date" label={t('campaign.calendar.date')} value={date} onChange={setDate} />
        <Input type="time" label={t('campaign.calendar.time')} value={time} onChange={setTime} />
        <Input label={t('campaign.calendar.note')} value={note} onChange={setNote} />
        {err && <p className="text-sm text-dnd-crimson-bright">{err}</p>}
        <div className="flex gap-2 pt-1">
          <Button variant="secondary" fullWidth onClick={onClose}>{t('common.cancel')}</Button>
          <Button variant="primary" fullWidth disabled={!date || !time} loading={save.isPending} onClick={() => save.mutate()}>
            {t('common.save')}
          </Button>
        </div>
      </div>
    </Sheet>
  )
}

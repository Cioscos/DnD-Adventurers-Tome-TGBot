import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import Pressable from '@/components/ui/Pressable'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { useToast } from '@/hooks/useToast'
import { dayHeader } from '@/lib/relativeTime'

type Choice = number | 'none' | 'new'

function Option({ selected, onClick, children }: { selected: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <Pressable
      aria-pressed={selected}
      onClick={onClick}
      className={`w-full min-h-[44px] px-3 py-2 rounded-xl border text-left font-cinzel text-sm ${selected ? 'bg-dnd-gold/20 border-dnd-gold' : 'bg-dnd-surface border-dnd-border'}`}
    >
      {children}
    </Pressable>
  )
}

/** «Per quale campagna?»: l'ultima campagna del master è già selezionata, quindi due tocchi. */
export default function StartSessionSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [choice, setChoice] = useState<Choice | null>(null)
  const [name, setName] = useState('')

  const { data } = useQuery({ queryKey: ['campaigns'], queryFn: () => api.campaigns.list(), enabled: open })
  const mine = (data ?? []).filter((c) => c.is_gm)
  // L'elenco arriva già con l'ultima usata in testa; finché l'utente non sceglie, vale quella.
  const selected: Choice | null = choice ?? (data ? (mine[0]?.id ?? 'none') : null)

  useEffect(() => { if (!open) { setChoice(null); setName('') } }, [open])

  const start = useMutation({
    mutationFn: async () => {
      if (selected === 'none') return api.sessions.create()
      if (selected === 'new') {
        const camp = await api.campaigns.create(name.trim())
        qc.invalidateQueries({ queryKey: ['campaigns'] })
        return api.sessions.create(undefined, camp.id)
      }
      return api.sessions.create(undefined, selected as number)
    },
    onSuccess: (session) => {
      qc.setQueryData(['session-me'], session)
      haptic.success()
      onClose()
      navigate(`/session/${session.id}`)
    },
    onError: () => toast.error(t('campaign.start_error')),
  })

  const canStart = selected !== null && (selected !== 'new' || name.trim().length > 0)

  return (
    <Sheet open={open} onClose={onClose} title={t('campaign.start_title')}>
      <div className="p-4 space-y-2">
        {mine.map((c) => (
          <Option key={c.id} selected={selected === c.id} onClick={() => setChoice(c.id)}>
            <span className="block break-words">{c.name}</span>
            <span className="block text-xs font-body text-dnd-text-muted">
              {t('campaign.members_count', { count: c.member_count })} ·{' '}
              {c.last_session_at
                ? t('campaign.last_night', { date: dayHeader(c.last_session_at, i18n.language as 'it' | 'en') })
                : t('campaign.no_nights')}
            </span>
          </Option>
        ))}
        <Option selected={selected === 'none'} onClick={() => setChoice('none')}>
          <span className="block">{t('campaign.none')}</span>
          <span className="block text-xs font-body text-dnd-text-muted">{t('campaign.none_hint')}</span>
        </Option>
        <Option selected={selected === 'new'} onClick={() => setChoice('new')}>{t('campaign.new')}</Option>
        {selected === 'new' && (
          <Input value={name} onChange={(v) => setName(v.slice(0, 120))} placeholder={t('campaign.new_name_placeholder')} autoFocus />
        )}
        <div className="pt-2">
          <Button variant="primary" size="lg" fullWidth disabled={!canStart} loading={start.isPending} onClick={() => start.mutate()}>
            {t('campaign.start_go')}
          </Button>
        </div>
      </div>
    </Sheet>
  )
}

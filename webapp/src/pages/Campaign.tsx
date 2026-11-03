import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Copy, Share2, RefreshCw, Play, Trash2, UserMinus, Pencil, BookOpen } from 'lucide-react'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import EmptyState from '@/components/ui/EmptyState'
import Skeleton from '@/components/ui/Skeleton'
import SectionDivider from '@/components/ui/SectionDivider'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import Sheet from '@/components/ui/Sheet'
import Input from '@/components/ui/Input'
import JoinCampaignSessionSheet from '@/pages/campaign/JoinCampaignSessionSheet'
import StashTree from '@/pages/campaign/StashTree'
import LoreSection from '@/pages/campaign/LoreSection'
import CampaignCalendar from '@/pages/campaign/CampaignCalendar'
import { api, ApiError } from '@/api/client'
import { canShareMessage, haptic } from '@/auth/telegram'
import { useShareMessage } from '@/hooks/useShareMessage'
import { useToast } from '@/hooks/useToast'
import { notifyMutationError } from '@/lib/mutationError'
import { dayHeader } from '@/lib/relativeTime'
import { fromServer } from '@/lib/calendarDates'
import { formatDuration } from '@/lib/duration'
import type { CampaignDetail, CampaignMember, CampaignMemberStatus } from '@/types'

const STATUSES: CampaignMemberStatus[] = ['active', 'reserve', 'dead']

type Confirm = { kind: 'regen' } | { kind: 'delete' } | { kind: 'member'; member: CampaignMember } | null

export default function Campaign() {
  const { id } = useParams()
  const campId = Number(id)
  const navigate = useNavigate()
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const [confirm, setConfirm] = useState<Confirm>(null)
  const [joining, setJoining] = useState(false)
  // un PG gestibile alla volta: di norma ne gioca uno, gli altri restano chiusi
  const [openMember, setOpenMember] = useState<number | null>(null)
  const [renaming, setRenaming] = useState<string | null>(null)
  const key = ['campaign', campId]

  const { data: camp, isLoading, isError, error, refetch } = useQuery({
    queryKey: key,
    queryFn: () => api.campaigns.get(campId),
    enabled: Number.isFinite(campId),
  })
  // Per il giocatore: sono già dentro la sessione aperta o devo entrarci?
  const { data: myLive } = useQuery({
    queryKey: ['session-me'],
    queryFn: () => api.sessions.me(),
    enabled: !!camp && !camp.is_gm && camp.active_session_id != null,
  })

  const setDetail = (d: CampaignDetail) => {
    qc.setQueryData(key, d)
    qc.invalidateQueries({ queryKey: ['campaigns'] })
  }

  const share = useShareMessage(() => api.share.campaignInvite(campId))
  const start = useMutation({
    mutationFn: () => api.sessions.create(undefined, campId),
    onSuccess: (s) => {
      qc.setQueryData(['session-me'], s)
      haptic.success()
      navigate(`/session/${s.id}`)
    },
    // Es. 409: la sessione esiste già, ricarica così il bottone diventa «Vai alla sessione».
    onError: (e) => {
      qc.invalidateQueries({ queryKey: key })
      if (e instanceof ApiError && e.status === 409 && e.detail === 'You already have an active session') toast.error(t('session.already_in_other'))
      else notifyMutationError()
    },
  })
  const renameMut = useMutation({
    mutationFn: (name: string) => api.campaigns.rename(campId, name),
    onSuccess: (r) => {
      setRenaming(null)
      qc.setQueryData<CampaignDetail>(key, (d) => (d ? { ...d, name: r.name } : d))
      qc.invalidateQueries({ queryKey: ['campaigns'] })
    },
  })
  const setStatus = useMutation({
    mutationFn: (v: { characterId: number; status: CampaignMemberStatus }) =>
      api.campaigns.setMemberStatus(campId, v.characterId, v.status),
    onSuccess: setDetail,
  })
  const removeMember = useMutation({
    mutationFn: (characterId: number) => api.campaigns.removeMember(campId, characterId),
    onSuccess: () => {
      setConfirm(null)
      qc.invalidateQueries({ queryKey: key })
      qc.invalidateQueries({ queryKey: ['campaigns'] })
    },
  })
  const regen = useMutation({
    mutationFn: () => api.campaigns.regenerateCode(campId),
    onSuccess: ({ invite_code }) => {
      setConfirm(null)
      qc.setQueryData<CampaignDetail>(key, (d) => (d ? { ...d, invite_code } : d))
    },
  })
  const del = useMutation({
    mutationFn: () => api.campaigns.remove(campId),
    onSuccess: () => {
      qc.removeQueries({ queryKey: key })
      qc.invalidateQueries({ queryKey: ['campaigns'] })
      navigate('/session', { replace: true })
    },
    onError: (e) => {
      setConfirm(null)
      if (e instanceof ApiError && e.status === 409) toast.error(t('campaign.delete_blocked'))
      else notifyMutationError()
    },
  })

  if (isLoading) {
    return (
      <Layout title={t('campaign.mine')} backTo="/session">
        <Skeleton.Rect height="120px" />
        <Skeleton.Rect height="120px" delay={100} />
      </Layout>
    )
  }
  if (isError || !camp) {
    const gone = error instanceof ApiError && (error.status === 404 || error.status === 403)
    return (
      <Layout title={t('campaign.mine')} backTo="/session">
        <EmptyState
          title={t(gone ? 'campaign.not_found' : 'campaign.load_error')}
          action={gone ? undefined : { label: t('common.retry'), onClick: () => refetch() }}
        />
      </Layout>
    )
  }

  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(camp.invite_code ?? '')
      haptic.light()
      toast.success(t('campaign.code_copied'), { duration: 1500 })
    } catch {
      haptic.error()
    }
  }
  const locale = i18n.language as 'it' | 'en'

  return (
    <Layout title={camp.name} backTo="/session">
      <Surface variant="sigil" ornamented>
        <h2 className="font-display font-bold text-xl text-dnd-gold-bright text-center break-words">{camp.name}</h2>
        {camp.is_gm && (
          <div className="mt-2 flex justify-center">
            <Button variant="secondary" size="sm" icon={<Pencil size={14} />} onClick={() => setRenaming(camp.name)}>
              {t('campaign.rename')}
            </Button>
          </div>
        )}
        {camp.is_gm && camp.invite_code && (
          <div className="mt-3 text-center">
            <p className="text-xs uppercase tracking-widest text-dnd-gold-dim font-cinzel">{t('campaign.code')}</p>
            <p className="font-display font-bold text-2xl text-dnd-gold-bright tracking-[0.2em] mt-1">{camp.invite_code}</p>
            <div className="mt-2 flex flex-wrap justify-center gap-2">
              <Button variant="secondary" size="sm" icon={<Copy size={14} />} onClick={copyCode}>{t('common.copy')}</Button>
              {canShareMessage() && (
                <Button variant="secondary" size="sm" icon={<Share2 size={14} />} loading={share.isPending} onClick={() => share.mutate()}>
                  {t('share.action')}
                </Button>
              )}
              <Button variant="secondary" size="sm" icon={<RefreshCw size={14} />} onClick={() => setConfirm({ kind: 'regen' })}>
                {t('campaign.regenerate')}
              </Button>
            </div>
          </div>
        )}
        {camp.is_gm && (
          <div className="mt-4">
            {camp.active_session_id != null ? (
              <Button variant="primary" size="lg" fullWidth icon={<Play size={18} />} onClick={() => navigate(`/session/${camp.active_session_id}`)}>
                {t('campaign.go_to_session')}
              </Button>
            ) : (
              <Button variant="primary" size="lg" fullWidth icon={<Play size={18} />} loading={start.isPending} onClick={() => start.mutate()}>
                {t('campaign.start_session')}
              </Button>
            )}
          </div>
        )}
        {!camp.is_gm && camp.active_session_id != null && (
          <div className="mt-4">
            {myLive?.id === camp.active_session_id ? (
              <Button variant="primary" size="lg" fullWidth icon={<Play size={18} />} onClick={() => navigate(`/session/${camp.active_session_id}`)}>
                {t('campaign.go_to_session')}
              </Button>
            ) : (
              <Button variant="primary" size="lg" fullWidth icon={<Play size={18} />} onClick={() => setJoining(true)}>
                {t('campaign.enter')}
              </Button>
            )}
          </div>
        )}
      </Surface>

      <SectionDivider>{t('campaign.group')}</SectionDivider>
      <div className="space-y-2" data-testid="members">
        {camp.members.length === 0 && <p className="text-sm text-dnd-text-muted italic">{t('campaign.no_members')}</p>}
        {camp.members.map((mem) => {
          const manage = camp.is_gm || mem.is_mine
          const open = openMember === mem.character_id
          return (
            <Surface key={mem.character_id} variant="elevated" className={mem.status === 'dead' ? 'opacity-70' : ''}>
              <div className="flex items-start gap-2">
                <div className="min-w-0 flex-1">
                  <p className="font-display font-bold text-dnd-gold-bright break-words">
                    {mem.character_name}
                    {mem.is_mine && (
                      <span className="ml-2 align-middle inline-block rounded-full border border-dnd-gold px-2 py-0.5 text-xs font-cinzel uppercase tracking-wider text-dnd-gold-bright">
                        {t('campaign.yours')}
                      </span>
                    )}
                  </p>
                  <p className="text-xs text-dnd-text-muted font-body break-words">
                    {[mem.player_name, mem.class_summary].filter(Boolean).join(' · ')}
                  </p>
                  <p className="mt-1 text-xs font-cinzel uppercase text-dnd-gold-dim">{t(`campaign.status_${mem.status}`)}</p>
                  {mem.is_mine && (
                    <Button
                      className="mt-2"
                      variant="secondary"
                      size="sm"
                      icon={<BookOpen size={14} />}
                      onClick={() => navigate(`/char/${mem.character_id}/notes?campaign=${camp.id}`, { state: { from: `/campaign/${camp.id}` } })}
                    >
                      {t('campaign.my_journal')}
                    </Button>
                  )}
                </div>
                {manage && (
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={<Pencil size={14} />}
                    onClick={() => setOpenMember(open ? null : mem.character_id)}
                  >
                    {t('campaign.manage')}
                  </Button>
                )}
              </div>
              {manage && open && (
                <>
                  <div className="mt-2 grid grid-cols-3 gap-1">
                    {STATUSES.map((s) => (
                      <Pressable
                        key={s}
                        aria-pressed={mem.status === s}
                        pending={setStatus.isPending && setStatus.variables?.characterId === mem.character_id && setStatus.variables.status === s}
                        disabled={setStatus.isPending}
                        onClick={() => mem.status !== s && setStatus.mutate({ characterId: mem.character_id, status: s })}
                        className={`min-h-[44px] rounded-lg border text-xs font-cinzel ${mem.status === s ? 'bg-dnd-gold/20 border-dnd-gold text-dnd-gold-bright' : 'bg-dnd-surface border-dnd-border text-dnd-text-muted'}`}
                      >
                        {t(`campaign.status_${s}`)}
                      </Pressable>
                    ))}
                  </div>
                  <div className="mt-2">
                    <Button variant="danger" size="sm" icon={<UserMinus size={14} />} onClick={() => setConfirm({ kind: 'member', member: mem })}>
                      {t('campaign.remove_member')}
                    </Button>
                  </div>
                </>
              )}
            </Surface>
          )
        })}
      </div>

      <SectionDivider>{t('campaign.stash')}</SectionDivider>
      <Surface variant="elevated">
        <StashTree items={camp.stash.items} currency={camp.stash.currency} />
      </Surface>

      <LoreSection campaignId={camp.id} isGm={camp.is_gm} />

      <CampaignCalendar campaignId={camp.id} isGm={camp.is_gm} sessions={camp.sessions} />

      <SectionDivider>{t('campaign.nights')}</SectionDivider>
      {camp.sessions.length === 0 ? (
        <p className="text-sm text-dnd-text-muted italic">{t('campaign.nights_empty')}</p>
      ) : (
        <ul className="space-y-1">
          {camp.sessions.map((s) => {
            const row = (
              <>
                <span className="min-w-0 break-words">
                  {t('campaign.night_n', { n: s.number })} · {dayHeader(fromServer(s.created_at), locale)}
                </span>
                <span className="shrink-0 font-mono tabular-nums text-dnd-text-muted">{formatDuration(s.duration_seconds)}</span>
              </>
            )
            const cls = 'flex w-full items-baseline justify-between gap-3 text-sm font-body'
            return (
              <li key={s.id}>
                {s.has_recap ? (
                  <Pressable className={`${cls} min-h-11 items-center text-left`} onClick={() => navigate(`/campaign/${camp.id}/recap/${s.id}`)}>
                    {row}
                  </Pressable>
                ) : (
                  <div className={cls}>{row}</div>
                )}
              </li>
            )
          })}
        </ul>
      )}

      {camp.is_gm && (
        <div className="mt-6">
          <Button variant="danger" fullWidth icon={<Trash2 size={16} />} onClick={() => setConfirm({ kind: 'delete' })}>
            {t('campaign.delete')}
          </Button>
        </div>
      )}

      {joining && camp.active_session_id != null && (
        <JoinCampaignSessionSheet
          open
          onClose={() => setJoining(false)}
          item={{ campaign_id: camp.id, campaign_name: camp.name, session_id: camp.active_session_id, my_last_character_id: camp.my_last_character_id }}
        />
      )}
      <Sheet open={renaming !== null} onClose={() => setRenaming(null)} title={t('campaign.rename_title')}>
        <div className="p-5 space-y-3">
          <Input label={t('campaign.new_name_placeholder')} value={renaming ?? ''} onChange={setRenaming} />
          <div className="flex gap-2 pt-1">
            <Button variant="secondary" fullWidth onClick={() => setRenaming(null)}>{t('common.cancel')}</Button>
            <Button
              variant="primary"
              fullWidth
              disabled={!renaming?.trim()}
              loading={renameMut.isPending}
              onClick={() => renameMut.mutate((renaming ?? '').trim())}
            >
              {t('common.save')}
            </Button>
          </div>
        </div>
      </Sheet>
      <ConfirmSheet
        open={confirm?.kind === 'regen'}
        onClose={() => setConfirm(null)}
        onConfirm={() => regen.mutate()}
        loading={regen.isPending}
        title={t('campaign.regenerate_title')}
        body={t('campaign.regenerate_body')}
        confirmLabel={t('campaign.regenerate_confirm')}
        confirmVariant="primary"
      />
      <ConfirmSheet
        open={confirm?.kind === 'delete'}
        onClose={() => setConfirm(null)}
        onConfirm={() => del.mutate()}
        loading={del.isPending}
        title={t('campaign.delete_title')}
        body={t('campaign.delete_body')}
        confirmLabel={t('campaign.delete_confirm')}
      />
      <ConfirmSheet
        open={confirm?.kind === 'member'}
        onClose={() => setConfirm(null)}
        onConfirm={() => confirm?.kind === 'member' && removeMember.mutate(confirm.member.character_id)}
        loading={removeMember.isPending}
        title={t('campaign.remove_member_title', { name: confirm?.kind === 'member' ? confirm.member.character_name : '' })}
        body={t('campaign.remove_member_body')}
        confirmLabel={t('campaign.remove_member_confirm')}
      />
    </Layout>
  )
}

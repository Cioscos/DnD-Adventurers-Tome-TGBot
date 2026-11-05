import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { conditionLabel } from '@/lib/conditions'
import { Share2 } from 'lucide-react'
import Layout from '@/components/Layout'
import Button from '@/components/ui/Button'
import EmptyState from '@/components/ui/EmptyState'
import Skeleton from '@/components/ui/Skeleton'
import SectionDivider from '@/components/ui/SectionDivider'
import { api, ApiError } from '@/api/client'
import { canShareMessage } from '@/auth/telegram'
import { useShareMessage } from '@/hooks/useShareMessage'
import { dayHeader } from '@/lib/relativeTime'
import { formatDuration } from '@/lib/duration'
import { fromServer } from '@/lib/calendarDates'
import type { SessionRecapCharacter } from '@/types'

const P = 'campaign.recap.'

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 text-sm font-body">
      <span className="min-w-0 break-words text-dnd-text-muted">{label}</span>
      <span className="shrink-0 font-mono tabular-nums text-dnd-text">{value}</span>
    </div>
  )
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <>
      <SectionDivider>{title}</SectionDivider>
      <div className="px-1">{children}</div>
    </>
  )
}

function CharacterCard({ c }: { c: SessionRecapCharacter }) {
  const { t } = useTranslation()
  const slots = Object.entries(c.slots_used).sort(([a], [b]) => Number(a) - Number(b))
  const info = [c.player_name, c.class_summary].filter(Boolean).join(' · ')
  return (
    <div className="px-1 py-3">
      <h3 className="font-display font-bold text-dnd-text break-words">{c.name}</h3>
      {info && <p className="text-xs text-dnd-text-muted break-words">{info}</p>}
      <div className="mt-2 space-y-1">
        <Stat label={t(`${P}rolls`)} value={c.dice.rolls} />
        <Stat label={t(`${P}nat20`)} value={c.dice.nat20} />
        <Stat label={t(`${P}nat1`)} value={c.dice.nat1} />
        {c.dice.highest != null && <Stat label={t(`${P}highest`)} value={c.dice.highest} />}
        <Stat label={t(`${P}damage`)} value={c.damage_taken} />
        <Stat label={t(`${P}healed`)} value={c.healed} />
        {c.downed > 0 && <Stat label={t(`${P}downed`)} value={c.downed} />}
        {(c.death_saves.successes > 0 || c.death_saves.failures > 0) && (
          <Stat label={t(`${P}ds`)} value={`${t(`${P}ds_s`, { count: c.death_saves.successes })} · ${t(`${P}ds_f`, { count: c.death_saves.failures })}`} />
        )}
        {(c.spells_cast > 0 || slots.length > 0) && <Stat label={t(`${P}spells`)} value={c.spells_cast} />}
        {slots.length > 0 && <Stat label={t(`${P}slots`)} value={slots.map(([l, n]) => `${l}°×${n}`).join(' ')} />}
        {(c.rests.short > 0 || c.rests.long > 0) && (
          <Stat label={t(`${P}rests`)} value={t(`${P}rests_v`, { s: c.rests.short, l: c.rests.long })} />
        )}
      </div>
      {c.conditions.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {c.conditions.map((slug) => (
            <span key={slug} className="rounded-full border border-dnd-border px-2 py-0.5 text-xs text-dnd-text-muted">
              {conditionLabel(slug, t)}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export default function CampaignRecap() {
  const { id, sessionId } = useParams()
  const campId = Number(id)
  const sid = Number(sessionId)
  const { t, i18n } = useTranslation()
  const locale = i18n.language as 'it' | 'en'
  const backTo = `/campaign/${campId}`

  const { data: recap, isLoading, error } = useQuery({
    queryKey: ['session-recap', sid],
    queryFn: () => api.sessions.recap(sid),
    enabled: Number.isFinite(sid),
    retry: (n, e) => !(e instanceof ApiError) && n < 2,
  })
  const { data: camp } = useQuery({
    queryKey: ['campaign', campId],
    queryFn: () => api.campaigns.get(campId),
    enabled: Number.isFinite(campId),
  })
  const share = useShareMessage(() => api.share.recap(sid))

  if (isLoading) {
    return (
      <Layout title={t('campaign.nights')} backTo={backTo}>
        <Skeleton.Rect height="120px" />
        <Skeleton.Rect height="120px" delay={100} />
      </Layout>
    )
  }
  if (error || !recap) {
    return (
      <Layout title={t('campaign.nights')} backTo={backTo}>
        <EmptyState title={t(`${P}unavailable`)} />
      </Layout>
    )
  }

  // timestamp naive in UTC: senza "Z" il browser li leggerebbe come ora locale
  const title = recap.number ? t(`${P}evening`, { n: recap.number }) : t('campaign.nights')
  const { items, combat } = recap
  const places = recap.places ?? [] // assente nei riepiloghi precedenti alla 2.35.0
  const itemLines = [
    ...items.gm_grants.map((g) => t(`${P}grant`, { to: g.to ?? '?', item: g.item, q: g.quantity })),
    ...items.trades.map((x) => t(`${P}trade`, { from: x.from, to: x.to, what: x.summary })),
    ...items.stash.map((x) => t(`${P}${x.kind}`, { who: x.who, what: x.summary })),
  ]

  return (
    <Layout title={title} backTo={backTo}>
      <section className="px-1">
        <h2 className="font-display text-xl font-bold text-dnd-text break-words">{title}</h2>
        {recap.campaign_name && <p className="text-sm text-dnd-text-muted break-words">{recap.campaign_name}</p>}
        <p className="mt-0.5 flex flex-wrap items-baseline gap-x-3 text-sm font-body">
          <span>{dayHeader(fromServer(recap.started_at), locale)}</span>
          <span className="font-mono tabular-nums text-dnd-text-muted">{formatDuration(recap.duration_seconds)}</span>
        </p>
        {camp?.is_gm && canShareMessage() && (
          <div className="mt-3">
            <Button variant="secondary" size="sm" icon={<Share2 size={14} />} loading={share.isPending} onClick={() => share.mutate()}>
              {t(`${P}share`)}
            </Button>
          </div>
        )}
      </section>

      {recap.characters.length > 0 && (
        <>
          <SectionDivider>{t(`${P}players`)}</SectionDivider>
          <div className="divide-y divide-dnd-border/60 border-b border-dnd-border/60">{recap.characters.map((c) => <CharacterCard key={c.character_id} c={c} />)}</div>
        </>
      )}

      {combat.encounters > 0 && (
        <Block title={t(`${P}combat`)}>
          <div className="space-y-1">
            <Stat label={t(`${P}encounters`)} value={combat.encounters} />
            <Stat label={t(`${P}rounds`)} value={combat.rounds} />
          </div>
          {combat.monsters.length > 0 && (
            <p className="mt-2 text-sm font-body break-words">
              <span className="text-dnd-text-muted">{t(`${P}foes`)}: </span>{combat.monsters.join(', ')}
            </p>
          )}
        </Block>
      )}

      {itemLines.length > 0 && (
        <Block title={t(`${P}items`)}>
          <ul className="space-y-1 text-sm font-body">
            {itemLines.map((l, i) => <li key={i} className="break-words">{l}</li>)}
          </ul>
        </Block>
      )}

      {recap.lore.length > 0 && (
        <Block title={t(`${P}lore`)}>
          <ul className="space-y-1 text-sm font-body">
            {recap.lore.map((l) => <li key={l.id} className="break-words">{l.title}</li>)}
          </ul>
        </Block>
      )}

      {places.length > 0 && (
        <Block title={t(`${P}places`)}>
          <ul className="space-y-1 text-sm font-body">
            {places.map((p) => <li key={`${p.map_id}-${p.marker_id}`} className="break-words">{p.title}</li>)}
          </ul>
        </Block>
      )}

      {recap.highlights.length > 0 && (
        <Block title={t(`${P}highlights`)}>
          <ul className="space-y-1 text-sm font-body">
            {recap.highlights.map((h) => (
              <li key={h.key} className="break-words">{t(`${P}hl_${h.key}`, { name: h.name, v: h.value })}</li>
            ))}
          </ul>
        </Block>
      )}
    </Layout>
  )
}

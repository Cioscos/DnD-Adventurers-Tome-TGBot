import { useTranslation } from 'react-i18next'
import { PawPrint, User } from 'lucide-react'
import {
  GiHeartPlus as Heart,
  GiCheckedShield as Shield,
  GiDeathSkull as Skull,
} from 'react-icons/gi'
import ConditionBadge from '@/components/ui/ConditionBadge'
import type {
  CharacterLiveSnapshot,
  CombatantLive,
  EncounterMode,
  HpBucket,
} from '@/types'

const BUCKET_BAR: Record<HpBucket, string> = {
  healthy: 'bg-[var(--dnd-emerald-bright)]',
  lightly_wounded: 'bg-dnd-gold-bright',
  badly_wounded: 'bg-[var(--dnd-amber)]',
  dying: 'bg-[var(--dnd-crimson-bright)]',
  dead: 'bg-black',
}

interface Props {
  combatant: CombatantLive
  snapshot?: CharacterLiveSnapshot
  isActive: boolean
  amGm: boolean
  mode: EncounterMode
  onTap?: () => void
}

function HpBar({ pct, bucket }: { pct: number | null; bucket: HpBucket | null }) {
  return (
    <div
      data-testid={bucket !== null ? 'hp-bucket-bar' : 'hp-bar'}
      className="mt-1.5 h-1.5 w-full rounded-full bg-dnd-surface overflow-hidden"
    >
      {bucket !== null ? (
        <div className={`h-full ${BUCKET_BAR[bucket]}`} style={{ width: '100%' }} />
      ) : (
        <div
          className="h-full bg-gradient-to-r from-[var(--dnd-crimson)] via-[var(--dnd-amber)] to-[var(--dnd-emerald-bright)]"
          style={{ width: `${pct ?? 0}%` }}
        />
      )}
    </div>
  )
}

export default function CombatantRow({
  combatant: c, snapshot, isActive, amGm, mode, onTap,
}: Props) {
  const { t } = useTranslation()
  const isPc = c.kind === 'pc'
  const conds = Object.entries(
    (isPc ? snapshot?.conditions : c.conditions) ?? {},
  ).filter(([, v]) => Boolean(v))

  // PG: snapshot live (già redatto server-side). Mostro full: campi del combattente.
  const showExactPc = isPc && !!snapshot && snapshot.hit_points !== null
  const showExactMonster = !isPc && mode === 'full' && amGm && c.max_hp !== null
  const monsterBucket = !isPc && mode === 'full' && !amGm ? c.hp_bucket : null
  const pcBucket = isPc && snapshot && snapshot.hit_points === null
    ? (snapshot.hp_bucket ?? 'healthy')
    : null

  const pct = (cur: number | null | undefined, max: number | null | undefined) =>
    max && max > 0 ? Math.max(0, Math.min(100, Math.round(((cur ?? 0) / max) * 100))) : 0

  const clickable = amGm && !!onTap
  const wrapperProps = clickable
    ? {
        role: 'button' as const,
        tabIndex: 0,
        onClick: onTap,
        onKeyDown: (e: React.KeyboardEvent) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onTap?.()
          }
        },
      }
    : {}

  return (
    <div
      data-testid="combatant-row"
      data-active={isActive ? 'true' : 'false'}
      data-dead={c.is_dead ? 'true' : 'false'}
      {...wrapperProps}
      className={`rounded-lg border p-3 transition-all min-h-[44px]
        ${c.is_dead ? 'opacity-50' : ''}
        ${isActive
          ? 'border-dnd-gold bg-dnd-surface-raised ring-2 ring-dnd-gold-bright/50 shadow-[0_0_12px_rgba(212,168,71,0.35)]'
          : 'border-dnd-border bg-dnd-surface'}
        ${isPc ? 'border-l-4 border-l-dnd-gold-dim/70' : 'border-l-4 border-l-[var(--dnd-crimson)]'}
        ${clickable ? 'cursor-pointer hover:border-dnd-gold-bright' : ''}`}
    >
      <div className="flex items-center gap-3">
        <div className="w-9 shrink-0 text-center">
          <p className="font-mono tabular-nums text-lg font-bold text-dnd-gold-bright">
            {c.initiative ?? '—'}
          </p>
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            {c.is_dead ? (
              <Skull size={13} className="text-dnd-text-muted shrink-0" />
            ) : isPc ? (
              <User size={13} className="shrink-0 text-dnd-gold-bright" />
            ) : (
              <PawPrint size={13} className="shrink-0 text-[var(--dnd-crimson-bright)]" />
            )}
            <p className="font-display font-bold text-dnd-text break-words">
              {c.name}
            </p>
            {c.is_dead && (
              <span className="text-[10px] uppercase tracking-wider text-dnd-text-muted font-cinzel">
                {t('session.combat.dead_label')}
              </span>
            )}
          </div>

          {showExactPc && snapshot && (
            <>
              <div className="mt-1 flex items-center gap-3 text-xs font-mono tabular-nums">
                <span className="flex items-center gap-1">
                  <Heart size={11} className="text-[var(--dnd-crimson-bright)]" />
                  {snapshot.current_hit_points}/{snapshot.hit_points}
                </span>
                <span className="flex items-center gap-1">
                  <Shield size={11} className="text-dnd-gold-bright" />
                  {snapshot.ac}
                </span>
              </div>
              <HpBar pct={pct(snapshot.current_hit_points, snapshot.hit_points)} bucket={null} />
            </>
          )}
          {pcBucket && <HpBar pct={null} bucket={pcBucket} />}

          {showExactMonster && (
            <>
              <div className="mt-1 flex items-center gap-3 text-xs font-mono tabular-nums">
                <span className="flex items-center gap-1">
                  <Heart size={11} className="text-[var(--dnd-crimson-bright)]" />
                  {c.current_hp}/{c.max_hp}
                </span>
                {c.ac !== null && (
                  <span className="flex items-center gap-1">
                    <Shield size={11} className="text-dnd-gold-bright" />
                    {c.ac}
                  </span>
                )}
              </div>
              <HpBar pct={pct(c.current_hp, c.max_hp)} bucket={null} />
            </>
          )}
          {monsterBucket && <HpBar pct={null} bucket={monsterBucket} />}

          {conds.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1.5" onClick={(e) => e.stopPropagation()}>
              {conds.map(([key, val]) => (
                <ConditionBadge key={key} conditionKey={key} value={val} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

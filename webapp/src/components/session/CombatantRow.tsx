import { useTranslation } from 'react-i18next'
import { PawPrint, User } from 'lucide-react'
import {
  GiHeartPlus as Heart,
  GiCheckedShield as Shield,
  GiDeathSkull as Skull,
} from 'react-icons/gi'
import ConditionBadge from '@/components/ui/ConditionBadge'
import Pressable from '@/components/ui/Pressable'
import { formatCondition } from '@/lib/conditions'
import type {
  CharacterLiveSnapshot,
  CombatantLive,
  EncounterMode,
  HpBucket,
} from '@/types'

const BUCKET_BAR: Record<HpBucket, string> = {
  healthy: 'bg-dnd-emerald-bright',
  lightly_wounded: 'bg-dnd-gold-bright',
  badly_wounded: 'bg-dnd-amber',
  dying: 'bg-dnd-crimson-bright',
  dead: 'bg-dnd-ink',
}

interface Props {
  combatant: CombatantLive
  snapshot?: CharacterLiveSnapshot
  isActive: boolean
  amGm: boolean
  mode: EncounterMode
  onTap?: () => void
  /** GM: esito di un TS pendente di un mostro (tirato al tavolo). */
  onResolveSave?: (saveId: number, passed: boolean) => void
  resolvingSaveId?: number | null
  /** Riga compatta del tracciato: PF in una riga, niente barra. */
  compact?: boolean
}

const BUCKET_TEXT: Record<HpBucket, string> = {
  healthy: 'text-dnd-emerald-bright',
  lightly_wounded: 'text-dnd-gold-bright',
  badly_wounded: 'text-dnd-amber',
  dying: 'text-dnd-crimson-bright',
  dead: 'text-dnd-text-muted',
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
          className="h-full bg-gradient-to-r from-dnd-crimson via-dnd-amber to-dnd-emerald-bright"
          style={{ width: `${pct ?? 0}%` }}
        />
      )}
    </div>
  )
}

export default function CombatantRow({
  combatant: c, snapshot, isActive, amGm, mode, onTap, onResolveSave, resolvingSaveId, compact = false,
}: Props) {
  const { t } = useTranslation()
  const isPc = c.kind === 'pc'
  const conds = Object.entries(
    (isPc ? snapshot?.conditions : c.conditions) ?? {},
  ).filter(([, v]) => Boolean(v))
  const monsterSaves = !isPc && onResolveSave
    ? (c.pending_saves ?? []).filter((p) => p.status === 'pending')
    : []

  // Etichetta del TS in sospeso: il primo effetto con un TS ripetuto.
  const pcSave = snapshot?.condition_effects?.find((e) => e.save_ability && e.save_dc != null)

  // PG: snapshot live (già redatto server-side). Mostro full: campi del combattente.
  const showExactPc = isPc && !!snapshot && snapshot.hit_points !== null
  const showExactMonster = !isPc && mode === 'full' && amGm && c.max_hp !== null
  const monsterBucket = !isPc && mode === 'full' && !amGm ? c.hp_bucket : null
  const pcBucket = isPc && snapshot && snapshot.hit_points === null
    ? (snapshot.hp_bucket ?? 'healthy')
    : null

  const pct = (cur: number | null | undefined, max: number | null | undefined) =>
    max && max > 0 ? Math.max(0, Math.min(100, Math.round(((cur ?? 0) / max) * 100))) : 0

  const collapsed = compact
  const bucket = pcBucket ?? monsterBucket
  const hpSummary = showExactPc && snapshot
    ? `${snapshot.current_hit_points}/${snapshot.hit_points}`
    : showExactMonster
      ? `${c.current_hp}/${c.max_hp}`
      : null

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
      className={`mb-1 border-b ${collapsed ? 'py-1.5' : 'py-2.5'} px-1 transition-colors min-h-[44px]
        ${c.is_dead ? 'opacity-60' : ''}
        ${isActive ? 'border-dnd-gold bg-dnd-gold/10' : 'border-dnd-border/60'}
        ${clickable ? 'cursor-pointer hover:bg-dnd-surface/60' : ''}`}
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
              <PawPrint size={13} className="shrink-0 text-dnd-crimson-bright" />
            )}
            <p className="font-display font-bold text-dnd-text break-words">
              {c.name}
            </p>
            {isPc && snapshot?.has_pending_save && (
              <span
                aria-label={t('session.combat.pending_save')}
                className="shrink-0 rounded-full border border-dnd-amber/60 bg-dnd-amber/15 px-2 py-0.5 text-xs font-body text-dnd-amber tabular-nums whitespace-nowrap"
              >
                {pcSave
                  ? t('character.conditions.effect.save_any', {
                      ability: t(`character.ability.${pcSave.save_ability}_short`), dc: pcSave.save_dc,
                    })
                  : t('session.combat.pending_save')}
              </span>
            )}
            {c.is_dead && (
              <span className="text-xs uppercase tracking-wider text-dnd-text-muted font-cinzel">
                {t('session.combat.dead_label')}
              </span>
            )}
          </div>

          {!collapsed && showExactPc && snapshot && (
            <>
              <div className="mt-1 flex items-center gap-3 text-xs font-mono tabular-nums">
                <span className="flex items-center gap-1">
                  <Heart size={11} className="text-dnd-crimson-bright" />
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
          {!collapsed && pcBucket && <HpBar pct={null} bucket={pcBucket} />}

          {!collapsed && showExactMonster && (
            <>
              <div className="mt-1 flex items-center gap-3 text-xs font-mono tabular-nums">
                <span className="flex items-center gap-1">
                  <Heart size={11} className="text-dnd-crimson-bright" />
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
          {!collapsed && monsterBucket && <HpBar pct={null} bucket={monsterBucket} />}

          {conds.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1.5" onClick={(e) => e.stopPropagation()}>
              {conds.map(([key, val]) => (
                <ConditionBadge key={key} conditionKey={key} value={val} />
              ))}
            </div>
          )}

          {monsterSaves.map((ps) => (
            <div
              key={ps.id}
              className="mt-2 flex items-center gap-2"
              onClick={(e) => e.stopPropagation()}
              onKeyDown={(e) => e.stopPropagation()}
            >
              <p className="flex-1 min-w-0 text-xs text-dnd-amber break-words">
                {t('character.conditions.effect.save_any', {
                  ability: t(`character.ability.${ps.ability}_short`), dc: ps.dc,
                })}
                {' — '}{formatCondition(ps.slug, true, t)}
              </p>
              {([true, false] as const).map((passed) => (
                <Pressable
                  key={String(passed)}
                  onClick={() => onResolveSave?.(ps.id, passed)}
                  disabled={resolvingSaveId != null}
                  pending={resolvingSaveId === ps.id}
                  spinnerSize={12}
                  className={`min-h-[44px] px-3 rounded-md border text-xs font-cinzel uppercase tracking-wider
                    active:opacity-70 disabled:opacity-40
                    ${passed
                      ? 'border-dnd-emerald-bright/60 text-dnd-emerald-bright'
                      : 'border-dnd-crimson-bright/60 text-dnd-crimson-bright'}`}
                >
                  {t(passed ? 'session.combat.save_passed' : 'session.combat.save_failed')}
                </Pressable>
              ))}
            </div>
          ))}
        </div>
        {collapsed && !c.is_dead && (hpSummary || bucket) && (
          <span
            className={`shrink-0 text-xs font-mono tabular-nums
              ${hpSummary ? 'text-dnd-text' : BUCKET_TEXT[bucket!]}`}
          >
            {hpSummary ?? t(`session.hp_bucket.${bucket}`)}
          </span>
        )}
      </div>
    </div>
  )
}

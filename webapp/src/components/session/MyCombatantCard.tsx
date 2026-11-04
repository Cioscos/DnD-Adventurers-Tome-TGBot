import HPGauge from '@/components/ui/HPGauge'
import { useTranslation } from 'react-i18next'
import { ChevronRight } from 'lucide-react'
import {
  GiHeartPlus as Heart,
  GiCheckedShield as Shield,
  GiDeathSkull as Skull,
} from 'react-icons/gi'
import Button from '@/components/ui/Button'
import ConditionBadge from '@/components/ui/ConditionBadge'
import { formatCondition } from '@/lib/conditions'
import type { CharacterLiveSnapshot, CombatantLive } from '@/types'

interface Props {
  combatant: CombatantLive
  snapshot?: CharacterLiveSnapshot
  isMyTurn: boolean
  /** Posizioni vive che mancano al mio turno (0 = è il mio turno). */
  turnsUntilMine: number | null
  onOpenTurn?: () => void
}

/** Card del giocatore nella pagina Combattimento: il suo PG in primo piano. */
export default function MyCombatantCard({ combatant: c, snapshot: s, isMyTurn, turnsUntilMine, onOpenTurn }: Props) {
  const { t } = useTranslation()
  const max = s?.hit_points ?? null
  const cur = s?.current_hit_points ?? null
  const down = c.is_dead || (max !== null && (cur ?? 0) <= 0)
  const endOfTurnSaves = (s?.condition_effects ?? []).filter(
    (e) => e.save_edge === 'end' && e.save_ability && e.save_dc != null,
  )
  const conds = Object.entries(s?.conditions ?? {}).filter(([, v]) => Boolean(v))

  return (
    <div
      data-testid="my-combatant-card"
      className={`rounded-xl border p-3.5 bg-dnd-surface-raised transition-all
        ${isMyTurn
          ? 'border-dnd-gold ring-2 ring-dnd-gold-bright/40 shadow-dnd-glow'
          : 'border-dnd-border'}`}
    >
      <div className="flex items-baseline justify-between gap-2">
        <p className="min-w-0 font-display font-bold text-lg text-dnd-text break-words">
          {c.name}{' '}
          <span className="font-body font-normal text-xs text-dnd-text-muted">({t('session.you')})</span>
        </p>
        {isMyTurn ? (
          <span className="shrink-0 font-cinzel uppercase tracking-wider text-xs text-dnd-gold-bright">
            {t('session.combat.your_turn')}
          </span>
        ) : turnsUntilMine !== null && turnsUntilMine > 0 ? (
          <span className="shrink-0 text-xs text-dnd-text-muted tabular-nums">
            {t('session.combat.turns_until_mine', { count: turnsUntilMine })}
          </span>
        ) : null}
      </div>

      {down ? (
        <p className="mt-1.5 flex items-center gap-1.5 text-sm text-dnd-crimson-bright font-cinzel uppercase tracking-wider">
          <Skull size={14} />
          {t(c.is_dead ? 'session.combat.dead_label' : 'session.hp_bucket.dying')}
        </p>
      ) : max !== null ? (
        <>
          <div className="mt-1.5 flex items-center gap-4 font-mono tabular-nums text-sm">
            <span className="flex items-center gap-1">
              <Heart size={13} className="text-dnd-crimson-bright" />
              {cur}/{max}
              {(s?.temp_hp ?? 0) > 0 && <span className="text-dnd-arcane-bright">+{s?.temp_hp}</span>}
            </span>
            {s?.ac != null && (
              <span className="flex items-center gap-1">
                <Shield size={13} className="text-dnd-gold-bright" />
                {s.ac}
              </span>
            )}
          </div>
          <div className="mt-1.5">
            <HPGauge current={cur ?? 0} max={max} temp={s?.temp_hp ?? 0} size="md" />
          </div>
        </>
      ) : null}

      {conds.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {conds.map(([key, val]) => (
            <ConditionBadge key={key} conditionKey={key} value={val} />
          ))}
        </div>
      )}

      {endOfTurnSaves.map((e) => (
        <p
          key={e.slug}
          data-testid="end-turn-save-hint"
          className="mt-2 rounded-lg border border-dnd-amber/60 bg-dnd-amber/10 px-2.5 py-1 text-xs text-dnd-amber font-body"
        >
          {t('session.combat.end_turn_save_hint', {
            save: t('character.conditions.effect.save_any', {
              ability: t(`character.ability.${e.save_ability}_short`), dc: e.save_dc,
            }),
            condition: formatCondition(e.slug, true, t),
          })}
        </p>
      ))}

      {onOpenTurn && (
        <Button
          variant="secondary"
          size="md"
          fullWidth
          className="mt-3"
          icon={<ChevronRight size={16} />}
          onClick={onOpenTurn}
        >
          {t('session.combat.open_my_turn')}
        </Button>
      )}
    </div>
  )
}

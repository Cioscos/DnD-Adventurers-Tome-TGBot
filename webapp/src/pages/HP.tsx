import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import {
  GiNightSleep as Moon, GiSparkles as Sparkles, GiPotionBall as FlaskConical,
  GiHeartPlus as Heart,
} from 'react-icons/gi'
import { toast } from 'sonner'
import { api, type DeathSaveRollResult, type ConcentrationSaveResult, type HitDiceSpendResult } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import HPGauge from '@/components/ui/HPGauge'
import Button from '@/components/ui/Button'
import StatPill from '@/components/ui/StatPill'
import { CornerFlourishes } from '@/components/ui/Ornament'
import { haptic } from '@/auth/telegram'
import { spring } from '@/styles/motion'
import HpOperationForm from '@/pages/hp/HpOperationForm'
import DeathSaves from '@/pages/hp/DeathSaves'
import HitDiceModal from '@/pages/hp/HitDiceModal'
import { useDiceAnimation } from '@/dice/useDiceAnimation'

type HPOp = 'damage' | 'heal' | 'set_max' | 'set_current' | 'set_temp'

export default function HP() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const dice = useDiceAnimation()
  const [value, setValue] = useState('')
  const [activeOp, setActiveOp] = useState<HPOp>('damage')

  const [showShortRest, setShowShortRest] = useState(false)
  const [hitDiceResult, setHitDiceResult] = useState<HitDiceSpendResult | null>(null)
  const [deathRollResult, setDeathRollResult] = useState<DeathSaveRollResult | null>(null)
  const [concSaveResult, setConcSaveResult] = useState<ConcentrationSaveResult | null>(null)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const hpMutation = useMutation({
    mutationFn: ({ op, val }: { op: HPOp; val: number }) =>
      api.characters.updateHp(charId, op, val),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setValue('')
      haptic.success()
      const conc = updated.concentration_save
      if (conc) {
        setConcSaveResult(conc)
        if (conc.lost_concentration) {
          toast.warning(t('character.hp.concentration_lost'), { duration: 4000 })
        }
      }
    },
    onError: () => haptic.error(),
  })

  const restMutation = useMutation({
    mutationFn: (restType: 'long' | 'short') =>
      api.characters.rest(charId, restType),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.success()
    },
  })

  const deathMutation = useMutation({
    mutationFn: (action: string) =>
      api.characters.updateDeathSaves(charId, action),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.success()
    },
  })

  const deathRollMutation = useMutation({
    mutationFn: () => api.characters.rollDeathSave(charId),
    onSuccess: async (result) => {
      await dice.play({ groups: [{ kind: 'd20', results: [result.die] }] })
      setDeathRollResult(result)
      qc.invalidateQueries({ queryKey: ['character', charId] })
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const hitDiceMutation = useMutation({
    mutationFn: ({ classId, count }: { classId: number; count: number }) =>
      api.characters.spendHitDice(charId, classId, count),
    onSuccess: (result) => {
      setHitDiceResult(result)
      qc.invalidateQueries({ queryKey: ['character', charId] })
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const handleApply = () => {
    const n = parseInt(value, 10)
    if (isNaN(n) || n <= 0) return
    hpMutation.mutate({ op: activeOp, val: n })
  }

  if (!char) return null

  const ds = char.death_saves ?? { successes: 0, failures: 0, stable: false }
  const isDying = char.current_hit_points === 0 && !ds.stable
  const isConcentrating = !!char.concentrating_spell_id
  const classes = char.classes ?? []
  const hpPct = char.hit_points > 0 ? (char.current_hit_points / char.hit_points) * 100 : 0

  // Color scale for HP number
  const hpColor = hpPct > 50
    ? 'text-dnd-emerald-bright'
    : hpPct > 25
      ? 'text-dnd-gold-bright'
      : 'text-[var(--dnd-crimson-bright)]'
  const hpGlow = hpPct > 50
    ? 'drop-shadow(0 0 18px rgba(111,209,149,0.35))'
    : hpPct > 25
      ? 'drop-shadow(0 0 18px rgba(240,201,112,0.5))'
      : 'drop-shadow(0 0 22px rgba(232,80,80,0.6))'

  return (
    <Layout title={t('character.hp.title')} backTo={`/char/${charId}`} group="combat" page="hp">
      {/* HP hero */}
      <Surface variant="tome" ornamented className="relative">
        <div className="flex items-end justify-between gap-4 mb-3">
          <div>
            <p className="text-[10px] font-cinzel uppercase tracking-[0.25em] text-dnd-gold-dim mb-1">
              <Heart size={10} className="inline mr-1 text-[var(--dnd-crimson-bright)]" />
              {t('character.hp.title')}
            </p>
            <m.p
              key={char.current_hit_points}
              initial={{ scale: 0.85, opacity: 0.4 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={spring.elastic}
              className={`font-display font-black leading-none ${hpColor}`}
              style={{ fontSize: '5.5rem', filter: hpGlow }}
            >
              {char.current_hit_points}
            </m.p>
            <p className="text-lg text-dnd-text-muted font-mono">
              / {char.hit_points}
            </p>
          </div>
          <div className="flex flex-col items-end gap-1.5 pb-2">
            {char.temp_hp > 0 && (
              <StatPill
                tone="cobalt"
                size="sm"
                value={`+${char.temp_hp}`}
                label={t('character.hp.temp')}
              />
            )}
            <span className="text-xs font-mono text-dnd-text-faint">
              {Math.round(hpPct)}%
            </span>
          </div>
        </div>
        <HPGauge current={char.current_hit_points} max={char.hit_points} temp={char.temp_hp} size="lg" segmented />
      </Surface>

      {/* Concentration banner — passive indicator (auto-TS triggered by DAMAGE) */}
      {isConcentrating && (
        <Surface variant="arcane">
          <div className="flex items-center gap-2">
            <FlaskConical size={16} className="text-dnd-arcane-bright" />
            <p className="text-sm font-cinzel uppercase tracking-wider text-dnd-arcane-bright">
              {t('character.hp.concentration_active')}
            </p>
          </div>
        </Surface>
      )}

      {/* Operation form */}
      <HpOperationForm
        activeOp={activeOp}
        setActiveOp={setActiveOp}
        value={value}
        setValue={setValue}
        onApply={handleApply}
        isPending={hpMutation.isPending}
        hpMutate={(args) => hpMutation.mutate(args)}
      />

      {/* Rest buttons */}
      <div className="grid grid-cols-2 gap-2">
        <Button
          variant="arcane"
          size="lg"
          fullWidth
          onClick={() => setShowShortRest(true)}
          disabled={restMutation.isPending}
          icon={<Moon size={18} />}
          className="!bg-gradient-to-br !from-[var(--dnd-cobalt-deep)]/40 !to-[var(--dnd-cobalt)]/30 !text-[var(--dnd-cobalt-bright)] !border-dnd-cobalt/50"
          haptic="medium"
        >
          {t('character.hp.short_rest')}
        </Button>
        <Button
          variant="arcane"
          size="lg"
          fullWidth
          onClick={() => restMutation.mutate('long')}
          disabled={restMutation.isPending}
          loading={restMutation.isPending}
          icon={<Sparkles size={18} />}
          haptic="success"
        >
          {t('character.hp.long_rest')}
        </Button>
      </div>

      {/* Death saves */}
      {isDying && (
        <DeathSaves
          deathSaves={ds}
          onRoll={() => deathRollMutation.mutate()}
          onAction={(action) => deathMutation.mutate(action)}
          isRolling={deathRollMutation.isPending}
        />
      )}

      {/* Hit dice modal */}
      {showShortRest && (
        <HitDiceModal
          classes={classes}
          onSpend={(classId, count) => hitDiceMutation.mutate({ classId, count })}
          onConfirmRest={() => {
            restMutation.mutate('short')
            setShowShortRest(false)
          }}
          onClose={() => setShowShortRest(false)}
          isPending={hitDiceMutation.isPending}
        />
      )}

      {/* Hit dice result */}
      <AnimatePresence>
        {hitDiceResult && (
          <m.div
            className="fixed inset-0 flex items-center justify-center z-50 p-4"
            style={{ background: 'var(--dnd-overlay)', backdropFilter: 'blur(6px)' }}
            onClick={() => setHitDiceResult(null)}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <m.div
              className="relative rounded-3xl p-6 pt-8 w-full max-w-xs text-center space-y-3
                         bg-gradient-parchment surface-parchment border-2 border-dnd-emerald shadow-parchment-2xl"
              initial={{ opacity: 0, scale: 0.85, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.92 }}
              transition={spring.elastic}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="text-dnd-gold-dim"><CornerFlourishes /></div>
              <p className="text-sm text-dnd-text-muted font-cinzel uppercase tracking-widest">
                {t('character.hp.hit_dice_result')}
              </p>
              <m.p
                initial={{ scale: 0.5 }}
                animate={{ scale: 1 }}
                transition={{ ...spring.elastic, delay: 0.1 }}
                className="text-6xl font-black font-display text-[var(--dnd-emerald-bright)]"
              >
                +{hitDiceResult.healed}
              </m.p>
              <p className="text-xs text-dnd-text-muted font-mono">
                [{hitDiceResult.rolls.join(', ')}] +{hitDiceResult.con_bonus} (COS)
              </p>
              <p className="text-sm font-body">
                {t('character.hp.new_hp')}: <span className="font-bold font-mono text-dnd-gold-bright">{hitDiceResult.new_current_hp}</span>
              </p>
              <Button variant="primary" fullWidth onClick={() => setHitDiceResult(null)}>
                OK
              </Button>
            </m.div>
          </m.div>
        )}
      </AnimatePresence>

      {/* Death save result */}
      <AnimatePresence>
        {deathRollResult && (
          <m.div
            className="fixed inset-0 flex items-center justify-center z-50 p-4"
            style={{ background: 'var(--dnd-overlay)', backdropFilter: 'blur(6px)' }}
            onClick={() => setDeathRollResult(null)}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <m.div
              className={`relative rounded-3xl p-6 pt-8 w-full max-w-xs text-center space-y-3
                         bg-gradient-parchment surface-parchment border-2 shadow-parchment-2xl
                         ${deathRollResult.outcome === 'nat20' ? 'border-dnd-gold animate-pulse-gold'
                           : deathRollResult.outcome === 'success' ? 'border-dnd-emerald'
                           : 'border-[var(--dnd-crimson)] animate-pulse-danger'}`}
              initial={{ opacity: 0, scale: 0.85 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.92 }}
              transition={spring.elastic}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="text-dnd-gold-dim"><CornerFlourishes /></div>
              <p className="text-sm text-dnd-text-muted font-cinzel uppercase tracking-widest">
                {t('character.death_saves.roll_result')}
              </p>
              {deathRollResult.outcome === 'nat20' && (
                <p className="text-dnd-gold-bright font-bold font-cinzel">✦ {t('character.death_saves.nat20')}</p>
              )}
              {deathRollResult.outcome === 'nat1' && (
                <p className="text-[var(--dnd-crimson-bright)] font-bold font-cinzel">💀 {t('character.death_saves.nat1')}</p>
              )}
              <m.p
                initial={{ scale: 0, rotate: -180 }}
                animate={{ scale: 1, rotate: 0 }}
                transition={{ ...spring.elastic, delay: 0.1 }}
                className={`text-7xl font-black font-display ${
                  deathRollResult.outcome === 'nat20' ? 'text-dnd-gold-bright'
                    : deathRollResult.outcome === 'success' ? 'text-[var(--dnd-emerald-bright)]'
                      : 'text-[var(--dnd-crimson-bright)]'
                }`}
              >
                {deathRollResult.die}
              </m.p>
              <p className={`font-bold font-cinzel uppercase tracking-wider ${
                deathRollResult.outcome === 'success' || deathRollResult.outcome === 'nat20'
                  ? 'text-[var(--dnd-emerald-bright)]' : 'text-[var(--dnd-crimson-bright)]'
              }`}>
                {deathRollResult.outcome === 'success' || deathRollResult.outcome === 'nat20'
                  ? t('character.death_saves.success') : t('character.death_saves.failure')}
              </p>
              {deathRollResult.revived && (
                <p className="text-dnd-gold-bright text-sm font-medium font-body italic">
                  {t('character.death_saves.revived')}
                </p>
              )}
              {deathRollResult.stable && !deathRollResult.revived && (
                <p className="text-[var(--dnd-emerald-bright)] text-sm font-medium font-body italic">
                  {t('character.death_saves.stable_3_successes')}
                </p>
              )}
              {deathRollResult.failures >= 3 && (
                <p className="text-[var(--dnd-crimson-bright)] text-sm font-medium font-body italic">
                  {t('character.death_saves.dead_3_failures')}
                </p>
              )}
              <p className="text-xs text-dnd-text-muted font-mono">
                ✓ {deathRollResult.successes}/3 · ✗ {deathRollResult.failures}/3
              </p>
              <Button variant="primary" fullWidth onClick={() => setDeathRollResult(null)}>OK</Button>
            </m.div>
          </m.div>
        )}
      </AnimatePresence>

      {/* Concentration save result */}
      <AnimatePresence>
        {concSaveResult && (
          <m.div
            className="fixed inset-0 flex items-center justify-center z-50 p-4"
            style={{ background: 'var(--dnd-overlay)', backdropFilter: 'blur(6px)' }}
            onClick={() => setConcSaveResult(null)}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <m.div
              className={`relative rounded-3xl p-6 pt-8 w-full max-w-xs text-center space-y-3
                         bg-gradient-parchment surface-parchment border-2 shadow-parchment-2xl
                         ${concSaveResult.success ? 'border-dnd-emerald' : 'border-[var(--dnd-crimson)]'}`}
              initial={{ opacity: 0, scale: 0.85 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.92 }}
              transition={spring.elastic}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="text-dnd-gold-dim"><CornerFlourishes /></div>
              <p className="text-sm text-dnd-text-muted font-cinzel uppercase tracking-widest">
                🔮 {t('character.spells.concentration')} — DC {concSaveResult.dc}
              </p>
              {concSaveResult.is_critical && <p className="text-dnd-gold-bright font-bold font-cinzel">✦ CRITICO!</p>}
              {concSaveResult.is_fumble && <p className="text-[var(--dnd-crimson-bright)] font-bold font-cinzel">💀 FUMBLE!</p>}
              <m.p
                initial={{ scale: 0.4 }}
                animate={{ scale: 1 }}
                transition={{ ...spring.elastic, delay: 0.1 }}
                className={`text-5xl font-black font-display ${concSaveResult.success ? 'text-[var(--dnd-emerald-bright)]' : 'text-[var(--dnd-crimson-bright)]'}`}
              >
                {concSaveResult.total}
              </m.p>
              <p className="text-xs text-dnd-text-muted font-mono">
                d20 ({concSaveResult.die}) {concSaveResult.bonus >= 0 ? '+' : ''}{concSaveResult.bonus}
              </p>
              <p className={`font-bold font-cinzel uppercase tracking-wider ${concSaveResult.success ? 'text-[var(--dnd-emerald-bright)]' : 'text-[var(--dnd-crimson-bright)]'}`}>
                {concSaveResult.success ? t('character.spells.conc_save_success') : t('character.spells.conc_save_fail')}
              </p>
              {concSaveResult.lost_concentration && (
                <p className="text-[10px] text-[var(--dnd-crimson-bright)] font-body italic">
                  {t('character.spells.conc_lost')}
                </p>
              )}
              <Button variant="primary" fullWidth onClick={() => setConcSaveResult(null)}>OK</Button>
            </m.div>
          </m.div>
        )}
      </AnimatePresence>
    </Layout>
  )
}

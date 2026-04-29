import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
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
import { haptic } from '@/auth/telegram'
import { spring } from '@/styles/motion'
import HpOperationForm from '@/pages/hp/HpOperationForm'
import DeathSaves from '@/pages/hp/DeathSaves'
import HitDiceModal from '@/pages/hp/HitDiceModal'
import HitDiceResultDialog from '@/pages/hp/HitDiceResultDialog'
import DeathSaveResultDialog from '@/pages/hp/DeathSaveResultDialog'
import ConcentrationSaveDialog from '@/pages/hp/ConcentrationSaveDialog'
import { useDiceAnimation } from '@/dice/useDiceAnimation'
import { useDiceSettings } from '@/store/diceSettings'
import { useReducedMotion } from '@/hooks/useReducedMotion'

type HPOp = 'damage' | 'heal' | 'set_max' | 'set_current' | 'set_temp'

export default function HP() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const dice = useDiceAnimation()
  const animate3d = useDiceSettings((s) => s.animate3d)
  const reducedMotion = useReducedMotion()
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
    mutationFn: async () => {
      const useAnimation = animate3d && !reducedMotion
      let die: number | undefined
      if (useAnimation) {
        const detected = await dice.playAndCollect([{ kind: 'd20', count: 1 }])
        die = detected[0]?.value
      }
      return api.characters.rollDeathSave(charId, die)
    },
    onSuccess: (result) => {
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
    if (hpMutation.isPending) return
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
      : 'text-dnd-crimson-bright'
  const hpGlowClass = hpPct > 50
    ? 'hp-glow-emerald'
    : hpPct > 25
      ? 'hp-glow-gold'
      : 'hp-glow-crimson'

  return (
    <Layout title={t('character.hp.title')} backTo={`/char/${charId}`} group="combat" page="hp">
      {/* HP hero */}
      <Surface variant="tome" ornamented className="relative">
        <div className="flex items-end justify-between gap-4 mb-3">
          <div>
            <p className="text-[10px] font-cinzel uppercase tracking-[0.25em] text-dnd-gold-dim mb-1">
              <Heart size={10} className="inline mr-1 text-dnd-crimson-bright" />
              {t('character.hp.title')}
            </p>
            <m.p
              key={char.current_hit_points}
              initial={{ scale: 0.85, opacity: 0.4 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={spring.elastic}
              className={`font-display font-black leading-none text-[5.5rem] ${hpColor} ${hpGlowClass}`}
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
          className="!bg-gradient-to-br !from-dnd-cobalt-deep/40 !to-dnd-cobalt/30 !text-dnd-cobalt-bright !border-dnd-cobalt/50"
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

      {hitDiceResult && (
        <HitDiceResultDialog
          result={hitDiceResult}
          onClose={() => setHitDiceResult(null)}
        />
      )}

      {deathRollResult && (
        <DeathSaveResultDialog
          result={deathRollResult}
          onClose={() => setDeathRollResult(null)}
        />
      )}

      {concSaveResult && (
        <ConcentrationSaveDialog
          result={concSaveResult}
          onClose={() => setConcSaveResult(null)}
        />
      )}
    </Layout>
  )
}

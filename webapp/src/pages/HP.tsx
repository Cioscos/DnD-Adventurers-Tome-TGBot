import { useState, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { AnimatePresence, m } from 'framer-motion'
import { HeartPulse } from 'lucide-react'
import {
  GiNightSleep as Moon, GiCampfire as Campfire, GiPotionBall as FlaskConical,
  GiHeartPlus as Heart,
} from 'react-icons/gi'
import { toast } from 'sonner'
import { api, ApiError, type DeathSaveRollResult, type ConcentrationSaveResult, type HitDiceSpendResult } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import HPGauge from '@/components/ui/HPGauge'
import Button from '@/components/ui/Button'
import StatPill from '@/components/ui/StatPill'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import { showUndoToast } from '@/components/ui/UndoToast'
import { haptic } from '@/auth/telegram'
import { spring } from '@/styles/motion'
import HpOperationForm from '@/pages/hp/HpOperationForm'
import DeathSaves from '@/pages/hp/DeathSaves'
import HitDiceModal from '@/pages/hp/HitDiceModal'
import HitDiceResultDialog from '@/pages/hp/HitDiceResultDialog'
import DeathSaveResultDialog from '@/pages/hp/DeathSaveResultDialog'
import DeadState from '@/pages/hp/DeadState'
import InstantDeathDialog from '@/pages/hp/InstantDeathDialog'
import type { CharacterFull } from '@/types'
import ConcentrationSaveDialog from '@/pages/hp/ConcentrationSaveDialog'
import { useAnimatedRoll } from '@/dice/useAnimatedRoll'
import { useD20Roll, d20Arg, type RollMode } from '@/hooks/useD20Roll'
import HomebrewBreakdownRow from '@/components/homebrew/HomebrewBreakdownRow'
import HPSkeleton from '@/components/skeletons/HPSkeleton'
import { useIsFirstValue } from '@/hooks/useIsFirstValue'
import { notifyMutationError } from '@/lib/mutationError'
import { applyDamageModifier, damageMultiplier, type DamageModifier } from '@/lib/damageModifier'

type HPOp = 'damage' | 'heal' | 'set_max' | 'set_current' | 'set_temp'

// Solo la chiave del messaggio: l'annullamento vero lo fa il server con lo snapshot.
const UNDO_MESSAGE_KEYS: Record<HPOp, string> = {
  damage:      'character.hp.quick_damage_undo',
  heal:        'character.hp.quick_heal_undo',
  set_current: 'character.hp.quick_heal_undo',
  set_max:     'character.hp.quick_heal_undo',
  set_temp:    'character.hp.quick_temp_undo',
}

export default function HP() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const rollD20 = useD20Roll()
  const rollDice = useAnimatedRoll()
  const [value, setValue] = useState('')
  const [activeOp, setActiveOp] = useState<HPOp>('damage')
  const [crit, setCrit] = useState(false)
  const [damageModifier, setDamageModifier] = useState<DamageModifier>(null)
  const [damageType, setDamageType] = useState('')
  const [instantDeathOpen, setInstantDeathOpen] = useState(false)
  // Synchronous guard against double-fire of handleApply (Input.onCommit on blur +
  // button.onClick both fire when the user taps Conferma — `hpMutation.isPending` isn't
  // yet true at the second call, so a ref that flips immediately is needed). Mirrors
  // AbilityScores.tsx. Without it every Conferma sent 2 identical PATCH /hp (finding #1).
  const savingRef = useRef(false)

  const [showShortRest, setShowShortRest] = useState(false)
  const [showLongRestConfirm, setShowLongRestConfirm] = useState(false)
  const [hitDiceResult, setHitDiceResult] = useState<HitDiceSpendResult | null>(null)
  const [deathRollResult, setDeathRollResult] = useState<DeathSaveRollResult | null>(null)
  const [concSaveResult, setConcSaveResult] = useState<ConcentrationSaveResult | null>(null)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })
  // Pop del valore solo quando CAMBIA, non all'ingresso nella pagina.
  const isFirstValue = useIsFirstValue(char)

  const reviveMutation = useMutation({
    mutationFn: () => api.characters.revive(charId),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.success()
    },
  })

  // Morte istantanea = morto per danno massiccio (failures < 3). Il caso
  // "3 fallimenti da danno a 0" mostra direttamente la schermata DeadState.
  const maybeShowInstantDeath = (updated: CharacterFull) => {
    if (updated.is_dead && (updated.death_saves?.failures ?? 0) < 3) {
      setInstantDeathOpen(true)
    }
  }

  const hpMutation = useMutation({
    mutationFn: ({ op, val, wasCritical, modifier }: {
      op: HPOp; val: number; wasCritical?: boolean
      modifier?: { damage_modifier?: 'half' | 'double' | 'none' | 'immune'; raw_value?: number; damage_type?: string }
    }) =>
      modifier
        ? api.characters.updateHp(charId, op, val, wasCritical ?? false, modifier)
        : api.characters.updateHp(charId, op, val, wasCritical ?? false),
    onSuccess: (updated, { op, val }) => {
      qc.setQueryData(['character', charId], updated)
      // HP events (damage/heal) can drive homebrew change_resource rules (#18).
      qc.invalidateQueries({ queryKey: ['homebrew-resources', charId] })
      setValue('')
      setCrit(false)
      setDamageModifier(null)
      setDamageType('')
      haptic.success()
      maybeShowInstantDeath(updated)
      const conc = updated.concentration_save
      if (conc) {
        setConcSaveResult(conc)
        if (conc.lost_concentration) {
          toast.warning(t('character.hp.concentration_lost'), { duration: 4000 })
        }
      }
      savingRef.current = false
      // Stesso annullamento per scorciatoie e valore scritto a mano.
      const undoId = updated.hp_undo_id
      if (!undoId) return
      const base = t(UNDO_MESSAGE_KEYS[op], { n: val })
      const hasHomebrew = (updated.homebrew_notifications?.length ?? 0) > 0
      showUndoToast({
        message: hasHomebrew ? `${base} · ${t('character.hp.undo_homebrew_note')}` : base,
        actionLabel: t('character.hp.quick_undo_action'),
        onUndo: () => undoMutation.mutate(undoId),
      })
    },
    onError: () => {
      notifyMutationError()
      savingRef.current = false
    },
  })

  // Annulla tramite lo snapshot del server; 409 = i PF sono cambiati nel frattempo.
  const undoMutation = useMutation({
    mutationFn: (opId: string) => api.characters.undoHp(charId, opId),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      qc.invalidateQueries({ queryKey: ['homebrew-resources', charId] })
      // I dialog raccontavano l'operazione appena annullata.
      setInstantDeathOpen(false)
      setConcSaveResult(null)
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) {
        toast.error(t('character.hp.undo_stale'))
        qc.invalidateQueries({ queryKey: ['character', charId] })
      } else {
        notifyMutationError()
      }
    },
  })

  const restMutation = useMutation({
    mutationFn: (restType: 'long' | 'short') =>
      api.characters.rest(charId, restType),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      // Rest auto-restores homebrew resources (D3) and fires rest events (#18).
      qc.invalidateQueries({ queryKey: ['homebrew-resources', charId] })
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
    mutationFn: async (mode: RollMode) =>
      api.characters.rollDeathSave(charId, d20Arg(mode, await rollD20(mode))),
    onSuccess: (result) => {
      setDeathRollResult(result)
      qc.invalidateQueries({ queryKey: ['character', charId] })
      haptic.success()
    },
  })

  const hitDiceMutation = useMutation({
    mutationFn: async ({ classId, count }: { classId: number; count: number }) => {
      const hitDie = char?.classes.find((c) => c.id === classId)?.hit_die
      const rolls = await rollDice(`d${hitDie ?? 8}`, count)
      return api.characters.spendHitDice(charId, classId, count, rolls)
    },
    onSuccess: (result) => {
      setHitDiceResult(result)
      qc.invalidateQueries({ queryKey: ['character', charId] })
      haptic.success()
    },
  })

  const handleApply = () => {
    if (savingRef.current || hpMutation.isPending) return
    const n = parseInt(value, 10)
    if (isNaN(n) || n <= 0) return
    savingRef.current = true
    const wasCritical = activeOp === 'damage' && char?.current_hit_points === 0 && crit
    runHpMutation(activeOp, n, wasCritical)
  }

  // Il modificatore vale solo per il danno: `val` è già il valore applicato, il grezzo
  // viaggia come annotazione.
  const runHpMutation = (op: HPOp, raw: number, wasCritical: boolean) => {
    const type = damageType ? { damage_type: damageType } : {}
    if (op === 'damage' && damageModifier) {
      // Override dell'utente: il client applica il moltiplicatore, il server annota (e azzera se immune).
      hpMutation.mutate({
        op, val: applyDamageModifier(raw, damageModifier), wasCritical,
        modifier: { damage_modifier: damageModifier, raw_value: raw, ...type },
      })
    } else if (op === 'damage' && damageType) {
      // Nessun override: il server applica le resistenze del personaggio al tipo.
      hpMutation.mutate({ op, val: raw, wasCritical, modifier: type })
    } else {
      hpMutation.mutate({ op, val: raw, wasCritical })
    }
  }

  const handleSetActiveOp = (op: HPOp) => {
    setActiveOp(op)
    setDamageModifier(null)
    setDamageType('')
  }

  const handleQuickApply = ({ op, val }: { op: HPOp; val: number }) => {
    if (!char || hpMutation.isPending) return
    const wasCritical = op === 'damage' && char.current_hit_points === 0 && crit
    runHpMutation(op, val, wasCritical)
  }

  if (!char) {
    return (
      <Layout title={t('character.hp.title')} backTo={`/char/${charId}`} group="combat" page="hp">
        <HPSkeleton />
      </Layout>
    )
  }

  const ds = char.death_saves ?? { successes: 0, failures: 0, stable: false }
  const isDead = char.is_dead ?? false
  const deathCause: 'death_saves' | 'massive_damage' = (ds.failures ?? 0) >= 3 ? 'death_saves' : 'massive_damage'
  const atZero = char.current_hit_points === 0
  const isDying = atZero && !ds.stable && !isDead
  const isConcentrating = !!char.concentrating_spell_id
  const classes = char.classes ?? []
  const hbHp = char.hp_max_homebrew_modifier ?? 0
  const hpMax = char.hit_points + hbHp
  const hpPct = hpMax > 0 ? (char.current_hit_points / hpMax) * 100 : 0

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
      {/* First section: alive → hero PF centrato | dying → tiri salvezza | dead → seam (futura epica) */}
      {(() => {
        const section: 'alive' | 'dying' | 'dead' = isDead ? 'dead' : isDying ? 'dying' : 'alive'
        return (
          <AnimatePresence mode="wait" initial={false}>
            {section === 'alive' && (
              <m.div
                key="hp-alive"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
              >
                <Surface variant="tome" ornamented className="relative text-center">
                  <p className="text-xs font-cinzel uppercase tracking-[0.25em] text-dnd-gold-dim mb-2">
                    <Heart size={10} className="inline mr-1 text-dnd-crimson-bright" />
                    {t('character.hp.title')}
                  </p>
                  <div className="flex items-end justify-center gap-1.5">
                    <m.span
                      key={char.current_hit_points}
                      initial={isFirstValue ? false : { scale: 0.85, opacity: 0.4 }}
                      animate={{ scale: 1, opacity: 1 }}
                      transition={spring.elastic}
                      className={`font-display font-black leading-none text-[5rem] ${hpColor} ${hpGlowClass}`}
                    >
                      {char.current_hit_points}
                    </m.span>
                    <span className="mb-3 text-xl font-mono text-dnd-text-muted">/{hpMax}</span>
                  </div>
                  <div className="mt-2 flex items-center justify-center gap-2">
                    {char.temp_hp > 0 && (
                      <StatPill
                        tone="cobalt"
                        size="sm"
                        value={`+${char.temp_hp}`}
                        label={t('character.hp.temp')}
                      />
                    )}
                    <span className="rounded-full bg-dnd-ink/25 px-2 py-0.5 text-xs font-mono text-dnd-text">
                      {Math.round(hpPct)}%
                    </span>
                  </div>
                  <div className="mt-3">
                    <HPGauge current={char.current_hit_points} max={hpMax} temp={char.temp_hp} size="lg" segmented />
                  </div>
                  {/* A 0 HP stabile la sezione resta "alive": senza questo badge lo
                      stato "privo di sensi ma stabile" sarebbe indistinguibile da
                      un'anomalia (audit FE #5). Cobalt = info, mai crimson. */}
                  {atZero && ds.stable && (
                    <p className="mt-3 inline-flex items-center justify-center gap-1.5 rounded-full px-3 py-1.5
                                  text-xs font-cinzel font-bold uppercase tracking-wider
                                  bg-dnd-cobalt/15 border border-dnd-cobalt/40 text-dnd-cobalt-bright">
                      <HeartPulse size={13} />
                      {t('character.death_saves.stabilized_badge')}
                    </p>
                  )}
                  <HomebrewBreakdownRow value={char.hp_max_homebrew_modifier ?? 0} label={t('character.hp.homebrew_max_bonus_label')} />
                </Surface>
              </m.div>
            )}

            {section === 'dying' && (
              <m.div
                key="hp-dying"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="space-y-2"
              >
                <p className="text-center text-sm font-mono text-dnd-crimson-bright">
                  0 / {hpMax}
                </p>
                <DeathSaves
                  deathSaves={ds}
                  onRoll={(mode) => deathRollMutation.mutate(mode)}
                  onAction={(action) => deathMutation.mutate(action)}
                  isRolling={deathRollMutation.isPending}
                  pendingAction={deathMutation.isPending ? deathMutation.variables : undefined}
                />
              </m.div>
            )}

            {section === 'dead' && (
              <m.div
                key="hp-dead"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
              >
                <DeadState
                  cause={deathCause}
                  onRevive={() => reviveMutation.mutate()}
                  reviving={reviveMutation.isPending}
                />
              </m.div>
            )}
          </AnimatePresence>
        )
      })()}

      {/* Concentration banner — passive indicator (auto-TS triggered by DAMAGE) */}
      {!isDead && isConcentrating && (
        <Surface variant="arcane">
          <div className="flex items-center gap-2">
            <FlaskConical size={16} className="text-dnd-arcane-bright" />
            <p className="text-sm font-cinzel uppercase tracking-wider text-dnd-arcane-bright">
              {t('character.hp.concentration_active')}
            </p>
          </div>
        </Surface>
      )}

      {/* Operation form — nascosto da morto (operazioni PF inerti) */}
      {!isDead && (
        <HpOperationForm
          activeOp={activeOp}
          setActiveOp={handleSetActiveOp}
          value={value}
          setValue={setValue}
          onApply={handleApply}
          isPending={hpMutation.isPending}
          hpMutate={handleQuickApply}
          pendingQuickVal={hpMutation.isPending ? hpMutation.variables?.val : undefined}
          atZero={atZero}
          crit={crit}
          setCrit={setCrit}
          damageModifier={damageModifier}
          setDamageModifier={setDamageModifier}
          damageType={damageType}
          setDamageType={setDamageType}
          proposedModifier={damageMultiplier(char.damage_modifiers, damageType)}
        />
      )}

      {/* Rest buttons — nascosti da morto */}
      {!isDead && (
      <div className="grid grid-cols-2 gap-2">
        <Button
          variant="secondary"
          size="lg"
          fullWidth
          onClick={() => setShowShortRest(true)}
          loading={restMutation.isPending}
          icon={<Campfire size={18} />}
          haptic="medium"
        >
          {t('character.hp.short_rest')}
        </Button>
        <Button
          variant="secondary"
          size="lg"
          fullWidth
          onClick={() => setShowLongRestConfirm(true)}
          loading={restMutation.isPending}
          icon={<Moon size={18} />}
          haptic="success"
        >
          {t('character.hp.long_rest')}
        </Button>
      </div>
      )}

      <ConfirmSheet
        open={showLongRestConfirm}
        onClose={() => setShowLongRestConfirm(false)}
        onConfirm={() => {
          setShowLongRestConfirm(false)
          restMutation.mutate('long')
        }}
        title={t('character.hp.long_rest_confirm_title')}
        body={t('character.hp.long_rest_confirm_body')}
        confirmLabel={t('character.hp.long_rest_confirm_action')}
        confirmVariant="primary"
        loading={restMutation.isPending}
      />

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
          pendingClassId={hitDiceMutation.isPending ? hitDiceMutation.variables?.classId : undefined}
          restPending={restMutation.isPending}
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
      <InstantDeathDialog open={instantDeathOpen} onClose={() => setInstantDeathOpen(false)} />
    </Layout>
  )
}

import { askRollOptions, refreshAfterOptions } from '@/lib/rollOptions'
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
import { api, ApiError, type DeathSaveRollResult, type ConcentrationSaveResult, type HitDiceSpendResult, type RollOption } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import HPGauge from '@/components/ui/HPGauge'
import CharacterHpSecondary from '@/components/character/CharacterHpSecondary'
import Button from '@/components/ui/Button'
import StatPill from '@/components/ui/StatPill'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import RestPreviewList from '@/components/character/RestPreviewList'
import SongOfRestToggle from '@/components/character/SongOfRestToggle'
import NaturalRecoveryPicker from '@/components/character/NaturalRecoveryPicker'
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
import { isConcentrating, concentrationLabel } from '@/lib/concentration'
import { zeroHpSaveMessage } from '@/lib/zeroHpSave'
import { useReactionOffers } from '@/components/character/ReactionOffers'
import UndyingSentinelOffer from '@/components/character/UndyingSentinelOffer'
import { hpNumeralTone } from '@/lib/hpTone'
import { applyDamageModifier, damageMultiplier, effectiveDamageMods, type DamageModifier } from '@/lib/damageModifier'

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
  const [knockOut, setKnockOut] = useState(false)
  const [damageModifier, setDamageModifier] = useState<DamageModifier>(null)
  const [damageType, setDamageType] = useState('')
  const [instantDeathOpen, setInstantDeathOpen] = useState(false)
  // Synchronous guard against double-fire of handleApply (Input.onCommit on blur +
  // button.onClick both fire when the user taps Conferma — `hpMutation.isPending` isn't
  // yet true at the second call, so a ref that flips immediately is needed). Mirrors
  // AbilityScores.tsx. Without it every Conferma sent 2 identical PATCH /hp (finding #1).
  const savingRef = useRef(false)

  const [showShortRest, setShowShortRest] = useState(false)
  const [recovery, setRecovery] = useState<Record<number, number>>({})  // Recupero Naturale: livello -> slot
  const [showLongRestConfirm, setShowLongRestConfirm] = useState(false)
  const [hitDiceResult, setHitDiceResult] = useState<HitDiceSpendResult | null>(null)
  const [deathRollResult, setDeathRollResult] = useState<DeathSaveRollResult | null>(null)
  const [concSaveResult, setConcSaveResult] = useState<ConcentrationSaveResult | null>(null)
  // Reazioni che l'ultimo danno ha aperto (Ritorsione): si propongono con l'attacco in un tocco.
  const [reactions, setReactions] = useState<RollOption[]>([])

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })
  const offers = useReactionOffers({
    charId, char, reactions, onSpent: (key) => setReactions((all) => all.filter((r) => r.key !== key)),
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
    mutationFn: async ({ op, val, wasCritical, modifier }: {
      op: HPOp; val: number; wasCritical?: boolean
      modifier?: { damage_modifier?: 'half' | 'double' | 'half_double' | 'none' | 'immune'; raw_value?: number; damage_type?: string; knock_out?: boolean }
    }) => {
      const choice = op === 'damage'
        ? await askRollOptions(charId, { roll: 'damage_taken', damage_type: modifier?.damage_type }, 'damage_in')
        : undefined
      const withOptions = choice?.options.length ? { ...modifier, ...choice } : modifier
      return withOptions
        ? api.characters.updateHp(charId, op, val, wasCritical ?? false, withOptions)
        : api.characters.updateHp(charId, op, val, wasCritical ?? false)
    },
    onSuccess: (updated, { op, val }) => {
      qc.setQueryData(['character', charId], updated)
      setReactions(op === 'damage' ? updated.reactions ?? [] : [])
      if (updated.option_result) {
        refreshAfterOptions(qc, charId, updated.option_result)
        toast.info(t('character.roll_options.damage_changed', {
          before: updated.option_result.damage_before, after: updated.option_result.damage_after,
        }))
      }
      // HP events (damage/heal) can drive homebrew change_resource rules (#18).
      qc.invalidateQueries({ queryKey: ['homebrew-resources', charId] })
      setValue('')
      setCrit(false)
      setKnockOut(false)
      setDamageModifier(null)
      setDamageType('')
      haptic.success()
      maybeShowInstantDeath(updated)
      const zeroSave = zeroHpSaveMessage(updated, t)
      if (zeroSave) (zeroSave.ok ? toast.success : toast.warning)(zeroSave.text, { duration: 5000 })
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
      setReactions([])  // la reazione era del danno annullato
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
      restType === 'short' && Object.keys(recovery).length > 0
        ? api.characters.rest(charId, restType, { natural_recovery: recovery })
        : api.characters.rest(charId, restType),
    onError: (err) => {
      const detail = err instanceof ApiError ? err.detail : null
      if (detail === 'rest_needs_hp') toast.error(t('character.quick_actions.rest_needs_hp'))
      else if (detail === 'long_rest_too_soon') toast.error(t('character.quick_actions.rest_too_soon_use_menu'))
      else notifyMutationError()
    },
    onSuccess: (updated) => {
      setRecovery({})
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
    mutationFn: async (mode: RollMode) => {
      const choice = await askRollOptions(charId, { roll: 'death_save' })
      return api.characters.rollDeathSave(charId, d20Arg(mode, await rollD20(mode), choice))
    },
    onSuccess: (result) => {
      setDeathRollResult(result)
      qc.invalidateQueries({ queryKey: ['character', charId] })
      refreshAfterOptions(qc, charId, result.option_result)
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
    // Tramortire vale per il solo danno che porta a 0 PF: il server lo ignora altrimenti.
    const type = {
      ...(damageType ? { damage_type: damageType } : {}),
      ...(op === 'damage' && knockOut ? { knock_out: true } : {}),
    }
    if (op === 'damage' && damageModifier) {
      // Override dell'utente: il client applica il moltiplicatore, il server annota (e azzera se immune).
      hpMutation.mutate({
        op, val: applyDamageModifier(raw, damageModifier), wasCritical,
        modifier: { damage_modifier: damageModifier, raw_value: raw, ...type },
      })
    } else if (op === 'damage' && (damageType || knockOut)) {
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
  const concentrating = isConcentrating(char)
  const concentrationName = concentrationLabel(char)
  const classes = char.classes ?? []
  const hbHp = char.hp_max_homebrew_modifier ?? 0
  const hpMax = char.computed?.hp_max_effective ?? char.hit_points + hbHp
  // In forma selvatica il numero grande e la barra sono quelli della forma (come in Eroe).
  const form = char.active_form?.own_hp === false ? null : char.active_form ?? null // 2024: i PF sono del druido
  const shownHp = form ? form.current_hp : char.current_hit_points
  const shownMax = form ? form.max_hp : hpMax
  const shownTemp = form ? form.temp_hp : char.temp_hp
  const hpPct = shownMax > 0 ? (shownHp / shownMax) * 100 : 0

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
                <div className="relative py-2 text-center">
                  <p className="text-xs font-cinzel uppercase tracking-[0.25em] text-dnd-gold-dim mb-2">
                    <Heart size={10} className="inline mr-1 text-dnd-crimson-bright" />
                    {form ? form.name : t('character.hp.title')}
                  </p>
                  {form && (
                    <p className="mb-2 text-sm font-body text-dnd-emerald-bright">
                      {t('character.extras.hp_goes_to_form', { name: form.name })}
                    </p>
                  )}
                  <div className="flex items-end justify-center gap-1.5">
                    <m.span
                      key={shownHp}
                      initial={isFirstValue ? false : { scale: 0.85, opacity: 0.4 }}
                      animate={{ scale: 1, opacity: 1 }}
                      transition={spring.elastic}
                      className={`font-display font-black leading-none text-[5rem] ${hpNumeralTone(hpPct)}`}
                    >
                      {shownHp}
                    </m.span>
                    <span className="mb-3 text-xl font-mono text-dnd-text-muted">/{shownMax}</span>
                  </div>
                  <div className="mt-2 flex items-center justify-center gap-2">
                    {shownTemp > 0 && (
                      <StatPill
                        tone="cobalt"
                        size="sm"
                        value={`+${shownTemp}`}
                        label={t('character.hp.temp')}
                      />
                    )}
                    <span className="rounded-full bg-dnd-ink/25 px-2 py-0.5 text-xs font-mono text-dnd-text">
                      {Math.round(hpPct)}%
                    </span>
                  </div>
                  <div className="mt-3">
                    <HPGauge current={shownHp} max={shownMax} temp={shownTemp} size="lg" segmented />
                  </div>
                  {form && <CharacterHpSecondary char={char} className="mt-2" />}
                  {/* A 0 HP stabile la sezione resta "alive": senza questo badge lo
                      stato "privo di sensi ma stabile" sarebbe indistinguibile da
                      un'anomalia (audit FE #5). Cobalt = info, mai crimson. */}
                  {atZero && ds.stable && (
                    <p className="mt-3 inline-flex items-center justify-center gap-1.5 rounded-full px-3 py-1.5
                                  text-xs font-cinzel font-bold uppercase tracking-wider
                                  bg-dnd-cobalt/10 border border-dnd-cobalt/40 text-dnd-cobalt-bright">
                      <HeartPulse size={13} />
                      {t('character.death_saves.stabilized_badge')}
                    </p>
                  )}
                  <HomebrewBreakdownRow value={char.hp_max_homebrew_modifier ?? 0} label={t('character.hp.homebrew_max_bonus_label')} />
                </div>
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
                <UndyingSentinelOffer charId={charId} char={char} />
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
      {!isDead && concentrating && (
        <Surface variant="arcane">
          <div className="flex items-center gap-2">
            <FlaskConical size={16} className="text-dnd-arcane-bright" />
            <p className="text-sm font-cinzel uppercase tracking-wider text-dnd-arcane-bright">
              {t('character.hp.concentration_active')}
            </p>
            {concentrationName && (
              <p className="text-sm font-body italic text-dnd-arcane-bright truncate">{concentrationName}</p>
            )}
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
          knockOut={knockOut}
          setKnockOut={setKnockOut}
          canKnockOut={char.current_hit_points > 0}
          damageModifier={damageModifier}
          setDamageModifier={setDamageModifier}
          damageType={damageType}
          setDamageType={setDamageType}
          proposedModifier={damageMultiplier(effectiveDamageMods(char), damageType)}
        />
      )}

      {offers.card}

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
        body={
          <div className="space-y-3">
            <p>{t('character.hp.long_rest_confirm_body')}</p>
            {showLongRestConfirm && <RestPreviewList charId={charId} restType="long" />}
          </div>
        }
        confirmLabel={t('character.hp.long_rest_confirm_action')}
        confirmVariant="primary"
        loading={restMutation.isPending}
      />

      {/* Hit dice modal */}
      {showShortRest && (
        <HitDiceModal
          classes={classes}
          preview={<><SongOfRestToggle char={char} /><NaturalRecoveryPicker char={char} value={recovery} onChange={setRecovery} /></>}
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
          afterRoll={{ charId }}
        />
      )}

      {concSaveResult && (
        <ConcentrationSaveDialog
          result={concSaveResult}
          onClose={() => setConcSaveResult(null)}
          afterRoll={{ charId }}
        />
      )}
      {offers.elements}
      <InstantDeathDialog open={instantDeathOpen} onClose={() => setInstantDeathOpen(false)} />
    </Layout>
  )
}

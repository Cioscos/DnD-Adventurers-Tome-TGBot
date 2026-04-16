import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api, type DeathSaveRollResult, type ConcentrationSaveResult, type HitDiceSpendResult } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import HPBar from '@/components/HPBar'
import DndInput from '@/components/DndInput'
import { haptic } from '@/auth/telegram'
import HpOperationForm from '@/pages/hp/HpOperationForm'
import DeathSaves from '@/pages/hp/DeathSaves'
import HitDiceModal from '@/pages/hp/HitDiceModal'

type HPOp = 'damage' | 'heal' | 'set_max' | 'set_current' | 'set_temp'

export default function HP() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [value, setValue] = useState('')
  const [activeOp, setActiveOp] = useState<HPOp>('damage')

  // Short rest hit dice modal
  const [showShortRest, setShowShortRest] = useState(false)
  const [hitDiceResult, setHitDiceResult] = useState<HitDiceSpendResult | null>(null)

  // Death save roll result
  const [deathRollResult, setDeathRollResult] = useState<DeathSaveRollResult | null>(null)

  // Concentration save (after taking damage)
  const [concDamageInput, setConcDamageInput] = useState('')
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

  const concSaveMutation = useMutation({
    mutationFn: (damage: number) => api.spells.concentrationSave(charId, damage),
    onSuccess: (result) => {
      setConcSaveResult(result)
      if (result.lost_concentration) {
        qc.invalidateQueries({ queryKey: ['character', charId] })
      }
      setConcDamageInput('')
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

  return (
    <Layout title={t('character.hp.title')} backTo={`/char/${charId}`} group="combat" page="hp">
      {/* HP display */}
      <Card variant="elevated">
        <div className="flex justify-between items-start mb-3">
          <div>
            <p className="text-4xl font-bold">
              {char.current_hit_points}
              <span className="text-xl text-dnd-text-secondary">/{char.hit_points}</span>
            </p>
            {char.temp_hp > 0 && (
              <p className="text-sm text-dnd-info">+{char.temp_hp} temporanei</p>
            )}
          </div>
          <div className="text-right text-sm text-dnd-text-secondary">
            <p>{t('character.hp.max')}: {char.hit_points}</p>
            {char.temp_hp > 0 && <p>{t('character.hp.temp')}: {char.temp_hp}</p>}
          </div>
        </div>
        <HPBar current={char.current_hit_points} max={char.hit_points} temp={char.temp_hp} />
      </Card>

      {/* Concentration save banner */}
      {isConcentrating && (
        <Card variant="elevated">
          <p className="text-sm text-dnd-arcane-text font-medium mb-2">
            {'\uD83D\uDD2E'} {t('character.hp.concentration_active')}
          </p>
          <div className="flex gap-2 items-center">
            <DndInput
              type="number"
              min={0}
              value={concDamageInput}
              onChange={setConcDamageInput}
              placeholder={t('character.spells.conc_save_damage_placeholder')}
              className="flex-1"
            />
            <button
              onClick={() => {
                const dmg = parseInt(concDamageInput, 10)
                if (!isNaN(dmg) && dmg >= 0) concSaveMutation.mutate(dmg)
              }}
              disabled={concSaveMutation.isPending || !concDamageInput}
              className="px-3 py-1.5 rounded-xl bg-dnd-arcane/20 text-dnd-arcane-text text-sm font-medium
                         disabled:opacity-30 active:opacity-70"
            >
              {concSaveMutation.isPending ? '...' : t('character.spells.conc_save_btn')}
            </button>
          </div>
        </Card>
      )}

      {/* HP operation form (op selector, input, quick buttons) */}
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
        <button
          onClick={() => setShowShortRest(true)}
          disabled={restMutation.isPending}
          className="py-3 rounded-2xl bg-dnd-info/20 text-dnd-info-text font-medium active:opacity-70"
        >
          {'\uD83C\uDF19'} {t('character.hp.short_rest')}
        </button>
        <button
          onClick={() => restMutation.mutate('long')}
          disabled={restMutation.isPending}
          className="py-3 rounded-2xl bg-dnd-arcane/20 text-dnd-arcane-text font-medium active:opacity-70"
        >
          {'\uD83D\uDCA4'} {t('character.hp.long_rest')}
        </button>
      </div>

      {/* Death saves (shown when HP = 0) */}
      {isDying && (
        <DeathSaves
          deathSaves={ds}
          onRoll={() => deathRollMutation.mutate()}
          onAction={(action) => deathMutation.mutate(action)}
          isRolling={deathRollMutation.isPending}
        />
      )}

      {/* Short rest modal: choose hit dice to spend */}
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

      {/* Hit dice result modal */}
      {hitDiceResult && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
          onClick={() => setHitDiceResult(null)}
        >
          <div
            className="rounded-2xl p-5 w-full max-w-xs text-center space-y-3
                       bg-dnd-surface-elevated border-2 border-dnd-success animate-modal-enter"
            onClick={(e) => e.stopPropagation()}
          >
            <p className="text-sm text-dnd-text-secondary">{t('character.hp.hit_dice_result')}</p>
            <p className="text-4xl font-black text-green-400">+{hitDiceResult.healed}</p>
            <p className="text-sm text-dnd-text-secondary">
              [{hitDiceResult.rolls.join(', ')}] +{hitDiceResult.con_bonus} (COS)
            </p>
            <p className="text-sm">
              {t('character.hp.new_hp')}: <span className="font-bold">{hitDiceResult.new_current_hp}</span>
            </p>
            <button
              onClick={() => setHitDiceResult(null)}
              className="w-full py-2.5 rounded-xl bg-dnd-gold text-dnd-bg font-semibold"
            >
              OK
            </button>
          </div>
        </div>
      )}

      {/* Death save roll result modal */}
      {deathRollResult && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
          onClick={() => setDeathRollResult(null)}
        >
          <div
            className={`rounded-2xl p-5 w-full max-w-xs text-center space-y-3
              bg-dnd-surface-elevated border-2 animate-modal-enter
              ${deathRollResult.outcome === 'nat20'
                ? 'border-dnd-gold'
                : deathRollResult.outcome === 'success'
                  ? 'border-dnd-success'
                  : 'border-[var(--dnd-danger)]'}`}
            onClick={(e) => e.stopPropagation()}
          >
            <p className="text-sm text-dnd-text-secondary">
              {'\uD83D\uDC80'} {t('character.death_saves.roll_result')}
            </p>
            {deathRollResult.outcome === 'nat20' && (
              <p className="text-dnd-highlight font-bold text-lg">{t('character.death_saves.nat20')}</p>
            )}
            {deathRollResult.outcome === 'nat1' && (
              <p className="text-red-400 font-bold text-lg">{t('character.death_saves.nat1')}</p>
            )}
            <p className={`text-5xl font-black ${
              deathRollResult.outcome === 'nat20' ? 'text-dnd-highlight'
                : deathRollResult.outcome === 'success' ? 'text-green-400'
                  : 'text-red-400'
            }`}>
              {deathRollResult.die}
            </p>
            <p className={`font-bold ${
              deathRollResult.outcome === 'success' || deathRollResult.outcome === 'nat20'
                ? 'text-green-400' : 'text-red-400'
            }`}>
              {deathRollResult.outcome === 'success' || deathRollResult.outcome === 'nat20'
                ? t('character.death_saves.success') : t('character.death_saves.failure')}
            </p>
            {deathRollResult.revived && (
              <p className="text-dnd-highlight text-sm font-medium">
                {t('character.death_saves.revived')}
              </p>
            )}
            {deathRollResult.stable && !deathRollResult.revived && (
              <p className="text-green-300 text-sm font-medium">
                {t('character.death_saves.stable_3_successes')}
              </p>
            )}
            {deathRollResult.failures >= 3 && (
              <p className="text-red-300 text-sm font-medium">
                {t('character.death_saves.dead_3_failures')}
              </p>
            )}
            <p className="text-xs text-dnd-text-secondary">
              {t('character.death_saves.successes')}: {deathRollResult.successes}/3 | {t('character.death_saves.failures')}: {deathRollResult.failures}/3
            </p>
            <button
              onClick={() => setDeathRollResult(null)}
              className="w-full py-2 rounded-xl bg-dnd-gold text-dnd-bg font-semibold"
            >
              OK
            </button>
          </div>
        </div>
      )}

      {/* Concentration save result modal */}
      {concSaveResult && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
          onClick={() => setConcSaveResult(null)}
        >
          <div
            className={`rounded-2xl p-5 w-full max-w-xs text-center space-y-3
              bg-dnd-surface-elevated border-2 animate-modal-enter
              ${concSaveResult.success ? 'border-dnd-success' : 'border-[var(--dnd-danger)]'}`}
            onClick={(e) => e.stopPropagation()}
          >
            <p className="text-sm text-dnd-text-secondary">
              {'\uD83D\uDD2E'} {t('character.spells.concentration')} — DC {concSaveResult.dc}
            </p>
            {concSaveResult.is_critical && <p className="text-dnd-highlight font-bold">{'\u2728'} CRITICO!</p>}
            {concSaveResult.is_fumble && <p className="text-red-400 font-bold">{'\uD83D\uDC80'} FUMBLE!</p>}
            <p className={`text-4xl font-black ${concSaveResult.success ? 'text-green-400' : 'text-red-400'}`}>
              {concSaveResult.total}
            </p>
            <p className="text-sm text-dnd-text-secondary">
              d20 ({concSaveResult.die}) {concSaveResult.bonus >= 0 ? '+' : ''}{concSaveResult.bonus}
            </p>
            <p className={`font-bold ${concSaveResult.success ? 'text-green-400' : 'text-red-400'}`}>
              {concSaveResult.success ? t('character.spells.conc_save_success') : t('character.spells.conc_save_fail')}
            </p>
            {concSaveResult.lost_concentration && (
              <p className="text-xs text-red-300">{t('character.spells.conc_lost')}</p>
            )}
            <button
              onClick={() => setConcSaveResult(null)}
              className="w-full py-2 rounded-xl bg-dnd-gold text-dnd-bg font-semibold"
            >
              OK
            </button>
          </div>
        </div>
      )}
    </Layout>
  )
}

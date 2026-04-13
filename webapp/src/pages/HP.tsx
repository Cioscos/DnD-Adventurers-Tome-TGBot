import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api, type DeathSaveRollResult } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import HPBar from '@/components/HPBar'
import { haptic } from '@/auth/telegram'

type HPOp = 'damage' | 'heal' | 'set_max' | 'set_current' | 'set_temp'

type HitDiceSpendResult = {
  rolls: number[]
  con_bonus: number
  healed: number
  new_current_hp: number
}

type ConcentrationSaveResult = {
  die: number
  bonus: number
  total: number
  dc: number
  success: boolean
  lost_concentration: boolean
  is_critical: boolean
  is_fumble: boolean
}

export default function HP() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [value, setValue] = useState('')
  const [activeOp, setActiveOp] = useState<HPOp>('damage')

  // Short rest hit dice modal
  const [showShortRest, setShowShortRest] = useState(false)
  const [hitDiceCounts, setHitDiceCounts] = useState<Record<number, number>>({})
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

  const ops: { key: HPOp; label: string; color: string }[] = [
    { key: 'damage',      label: t('character.hp.damage'),      color: 'bg-red-500/80' },
    { key: 'heal',        label: t('character.hp.heal'),         color: 'bg-green-500/80' },
    { key: 'set_current', label: t('character.hp.set_current'),  color: 'bg-blue-500/80' },
    { key: 'set_max',     label: t('character.hp.set_max'),      color: 'bg-orange-500/80' },
    { key: 'set_temp',    label: t('character.hp.set_temp'),     color: 'bg-cyan-500/80' },
  ]

  return (
    <Layout title={t('character.hp.title')} backTo={`/char/${charId}`}>
      {/* HP display */}
      <Card>
        <div className="flex justify-between items-start mb-3">
          <div>
            <p className="text-4xl font-bold">
              {char.current_hit_points}
              <span className="text-xl text-[var(--tg-theme-hint-color)]">/{char.hit_points}</span>
            </p>
            {char.temp_hp > 0 && (
              <p className="text-sm text-blue-400">+{char.temp_hp} temporanei</p>
            )}
          </div>
          <div className="text-right text-sm text-[var(--tg-theme-hint-color)]">
            <p>{t('character.hp.max')}: {char.hit_points}</p>
            {char.temp_hp > 0 && <p>{t('character.hp.temp')}: {char.temp_hp}</p>}
          </div>
        </div>
        <HPBar current={char.current_hit_points} max={char.hit_points} temp={char.temp_hp} />
      </Card>

      {/* Concentration save banner (shown when concentrating) */}
      {isConcentrating && (
        <Card>
          <p className="text-sm text-purple-300 font-medium mb-2">
            🔮 {t('character.hp.concentration_active')}
          </p>
          <div className="flex gap-2 items-center">
            <input
              type="number"
              min="0"
              value={concDamageInput}
              onChange={(e) => setConcDamageInput(e.target.value)}
              placeholder={t('character.spells.conc_save_damage_placeholder')}
              className="flex-1 bg-white/10 rounded-xl px-3 py-1.5 text-sm outline-none
                         focus:ring-2 focus:ring-purple-500"
            />
            <button
              onClick={() => {
                const dmg = parseInt(concDamageInput, 10)
                if (!isNaN(dmg) && dmg >= 0) concSaveMutation.mutate(dmg)
              }}
              disabled={concSaveMutation.isPending || !concDamageInput}
              className="px-3 py-1.5 rounded-xl bg-purple-500/30 text-purple-300 text-sm font-medium
                         disabled:opacity-30 active:opacity-70"
            >
              {concSaveMutation.isPending ? '...' : t('character.spells.conc_save_btn')}
            </button>
          </div>
        </Card>
      )}

      {/* Op selector */}
      <div className="w-full flex gap-1 overflow-x-auto pb-1 scrollbar-hide">
        {ops.map((op) => (
          <button
            key={op.key}
            onClick={() => setActiveOp(op.key)}
            className={`shrink-0 px-3 py-1.5 rounded-xl text-sm font-medium transition-all
              ${activeOp === op.key ? op.color + ' text-white' : 'bg-white/10'}`}
          >
            {op.label}
          </button>
        ))}
      </div>

      {/* Number input */}
      <Card>
        <div className="flex gap-3 items-center">
          <input
            type="number"
            min="0"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleApply()}
            placeholder="0"
            className="flex-1 bg-white/10 rounded-xl px-3 py-3 text-xl font-bold text-center
                       outline-none focus:ring-2 focus:ring-[var(--tg-theme-button-color)]"
          />
          <button
            onClick={handleApply}
            disabled={!value || hpMutation.isPending}
            className="px-5 py-3 rounded-xl bg-[var(--tg-theme-button-color)]
                       text-[var(--tg-theme-button-text-color)] font-semibold
                       disabled:opacity-40 active:opacity-80"
          >
            {hpMutation.isPending ? '...' : '✓'}
          </button>
        </div>
      </Card>

      {/* Quick heal / damage shortcuts */}
      <div className="grid grid-cols-4 gap-2">
        {[1, 5, 10, 20].map((n) => (
          <button
            key={n}
            onClick={() => {
              hpMutation.mutate({ op: activeOp, val: n })
              haptic.light()
            }}
            className="py-2 rounded-xl bg-white/10 text-sm font-medium active:opacity-70"
          >
            {activeOp === 'damage' ? `-${n}` : activeOp === 'heal' ? `+${n}` : String(n)}
          </button>
        ))}
      </div>

      {/* Rest buttons */}
      <div className="grid grid-cols-2 gap-2">
        <button
          onClick={() => setShowShortRest(true)}
          disabled={restMutation.isPending}
          className="py-3 rounded-2xl bg-blue-500/20 text-blue-300 font-medium active:opacity-70"
        >
          🌙 {t('character.hp.short_rest')}
        </button>
        <button
          onClick={() => restMutation.mutate('long')}
          disabled={restMutation.isPending}
          className="py-3 rounded-2xl bg-purple-500/20 text-purple-300 font-medium active:opacity-70"
        >
          💤 {t('character.hp.long_rest')}
        </button>
      </div>

      {/* Death saves (shown when HP = 0) */}
      {isDying && (
        <Card>
          <h3 className="font-semibold mb-3">💀 {t('character.death_saves.title')}</h3>
          <div className="grid grid-cols-2 gap-3 mb-4">
            <div className="text-center">
              <p className="text-sm text-[var(--tg-theme-hint-color)] mb-1">
                {t('character.death_saves.successes')}
              </p>
              <div className="flex justify-center gap-2">
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    className={`w-6 h-6 rounded-full border-2 ${
                      i < (ds.successes ?? 0)
                        ? 'bg-green-500 border-green-500'
                        : 'border-white/30'
                    }`}
                  />
                ))}
              </div>
            </div>
            <div className="text-center">
              <p className="text-sm text-[var(--tg-theme-hint-color)] mb-1">
                {t('character.death_saves.failures')}
              </p>
              <div className="flex justify-center gap-2">
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    className={`w-6 h-6 rounded-full border-2 ${
                      i < (ds.failures ?? 0)
                        ? 'bg-red-500 border-red-500'
                        : 'border-white/30'
                    }`}
                  />
                ))}
              </div>
            </div>
          </div>
          <button
            onClick={() => deathRollMutation.mutate()}
            disabled={deathRollMutation.isPending}
            className="w-full py-3 rounded-xl bg-yellow-500/20 text-yellow-300 font-bold text-base
                       active:opacity-70 disabled:opacity-40 mb-2"
          >
            🎲 {t('character.death_saves.roll')}
          </button>
          <div className="grid grid-cols-3 gap-2">
            <button
              onClick={() => deathMutation.mutate('success')}
              className="py-2 rounded-xl bg-green-500/20 text-green-300 text-sm font-medium"
            >
              ✓ {t('character.death_saves.success')}
            </button>
            <button
              onClick={() => deathMutation.mutate('failure')}
              className="py-2 rounded-xl bg-red-500/20 text-red-300 text-sm font-medium"
            >
              ✗ {t('character.death_saves.failure')}
            </button>
            <button
              onClick={() => deathMutation.mutate('stabilize')}
              className="py-2 rounded-xl bg-blue-500/20 text-blue-300 text-sm font-medium"
            >
              💊 {t('character.death_saves.stabilize')}
            </button>
          </div>
          <button
            onClick={() => deathMutation.mutate('reset')}
            className="w-full mt-2 py-2 rounded-xl bg-white/10 text-sm"
          >
            {t('character.death_saves.reset')}
          </button>
        </Card>
      )}

      {/* Short rest modal: choose hit dice to spend */}
      {showShortRest && (
        <div className="fixed inset-0 bg-black/60 flex items-end z-50 p-4">
          <Card className="w-full space-y-3">
            <h3 className="font-semibold">🌙 {t('character.hp.short_rest')}</h3>
            <p className="text-sm text-[var(--tg-theme-hint-color)]">
              {t('character.hp.hit_dice_spend_hint')}
            </p>

            {classes.length === 0 && (
              <p className="text-sm text-[var(--tg-theme-hint-color)]">{t('common.none')}</p>
            )}

            {classes.map((cls) => (
              <div key={cls.id} className="flex items-center gap-3">
                <span className="flex-1 text-sm">
                  {cls.class_name} (d{cls.hit_die ?? 8})
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setHitDiceCounts((c) => ({ ...c, [cls.id]: Math.max(0, (c[cls.id] ?? 0) - 1) }))}
                    className="w-7 h-7 rounded-lg bg-white/10 font-bold active:opacity-70"
                  >−</button>
                  <span className="w-6 text-center font-bold">{hitDiceCounts[cls.id] ?? 0}</span>
                  <button
                    onClick={() => setHitDiceCounts((c) => ({ ...c, [cls.id]: (c[cls.id] ?? 0) + 1 }))}
                    className="w-7 h-7 rounded-lg bg-white/10 font-bold active:opacity-70"
                  >+</button>
                  <button
                    onClick={() => {
                      const count = hitDiceCounts[cls.id] ?? 0
                      if (count > 0) hitDiceMutation.mutate({ classId: cls.id, count })
                    }}
                    disabled={!hitDiceCounts[cls.id] || hitDiceMutation.isPending}
                    className="px-3 py-1 rounded-lg bg-green-500/30 text-green-300 text-sm font-medium
                               disabled:opacity-30 active:opacity-70"
                  >
                    🎲
                  </button>
                </div>
              </div>
            ))}

            <div className="flex gap-2 pt-1">
              <button
                onClick={() => {
                  restMutation.mutate('short')
                  setShowShortRest(false)
                  setHitDiceCounts({})
                }}
                disabled={restMutation.isPending}
                className="flex-1 py-2.5 rounded-xl bg-blue-500/30 text-blue-300 font-medium disabled:opacity-40"
              >
                {t('character.hp.confirm_rest')}
              </button>
              <button
                onClick={() => { setShowShortRest(false); setHitDiceCounts({}) }}
                className="flex-1 py-2.5 rounded-xl bg-white/10"
              >
                {t('common.cancel')}
              </button>
            </div>
          </Card>
        </div>
      )}

      {/* Hit dice result modal */}
      {hitDiceResult && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
          onClick={() => setHitDiceResult(null)}
        >
          <div
            className="rounded-2xl p-5 w-full max-w-xs text-center space-y-3 bg-green-500/20 border border-green-500/40"
            onClick={(e) => e.stopPropagation()}
          >
            <p className="text-sm text-[var(--tg-theme-hint-color)]">{t('character.hp.hit_dice_result')}</p>
            <p className="text-4xl font-black text-green-400">+{hitDiceResult.healed}</p>
            <p className="text-sm text-[var(--tg-theme-hint-color)]">
              [{hitDiceResult.rolls.join(', ')}] +{hitDiceResult.con_bonus} (COS)
            </p>
            <p className="text-sm">
              {t('character.hp.new_hp')}: <span className="font-bold">{hitDiceResult.new_current_hp}</span>
            </p>
            <button
              onClick={() => setHitDiceResult(null)}
              className="w-full py-2.5 rounded-xl bg-[var(--tg-theme-button-color)]
                         text-[var(--tg-theme-button-text-color)] font-semibold"
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
              ${deathRollResult.outcome === 'nat20'
                ? 'bg-yellow-500/20 border border-yellow-500/40'
                : deathRollResult.outcome === 'success'
                  ? 'bg-green-500/20 border border-green-500/40'
                  : 'bg-red-500/20 border border-red-500/40'}`}
            onClick={(e) => e.stopPropagation()}
          >
            <p className="text-sm text-[var(--tg-theme-hint-color)]">
              💀 {t('character.death_saves.roll_result')}
            </p>
            {deathRollResult.outcome === 'nat20' && (
              <p className="text-yellow-400 font-bold text-lg">{t('character.death_saves.nat20')}</p>
            )}
            {deathRollResult.outcome === 'nat1' && (
              <p className="text-red-400 font-bold text-lg">{t('character.death_saves.nat1')}</p>
            )}
            <p className={`text-5xl font-black ${
              deathRollResult.outcome === 'nat20' ? 'text-yellow-400'
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
              <p className="text-yellow-300 text-sm font-medium">
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
            <p className="text-xs text-[var(--tg-theme-hint-color)]">
              {t('character.death_saves.successes')}: {deathRollResult.successes}/3 | {t('character.death_saves.failures')}: {deathRollResult.failures}/3
            </p>
            <button
              onClick={() => setDeathRollResult(null)}
              className="w-full py-2 rounded-xl bg-[var(--tg-theme-button-color)]
                         text-[var(--tg-theme-button-text-color)] font-semibold"
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
              ${concSaveResult.success ? 'bg-green-500/20 border border-green-500/40' : 'bg-red-500/20 border border-red-500/40'}`}
            onClick={(e) => e.stopPropagation()}
          >
            <p className="text-sm text-[var(--tg-theme-hint-color)]">
              🔮 {t('character.spells.concentration')} — DC {concSaveResult.dc}
            </p>
            {concSaveResult.is_critical && <p className="text-yellow-400 font-bold">✨ CRITICO!</p>}
            {concSaveResult.is_fumble && <p className="text-red-400 font-bold">💀 FUMBLE!</p>}
            <p className={`text-4xl font-black ${concSaveResult.success ? 'text-green-400' : 'text-red-400'}`}>
              {concSaveResult.total}
            </p>
            <p className="text-sm text-[var(--tg-theme-hint-color)]">
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
              className="w-full py-2 rounded-xl bg-[var(--tg-theme-button-color)]
                         text-[var(--tg-theme-button-text-color)] font-semibold"
            >
              OK
            </button>
          </div>
        </div>
      )}
    </Layout>
  )
}

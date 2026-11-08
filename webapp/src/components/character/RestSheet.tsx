import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { GiNightSleep, GiCampfire } from 'react-icons/gi'
import { api, ApiError } from '@/api/client'
import { useAnimatedRoll } from '@/dice/useAnimatedRoll'
import Sheet from '@/components/ui/Sheet'
import Pressable from '@/components/ui/Pressable'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import SwitchToggle from '@/components/ui/SwitchToggle'
import RestPreviewList from '@/components/character/RestPreviewList'
import SongOfRestToggle from '@/components/character/SongOfRestToggle'
import NaturalRecoveryPicker, { ArcaneRecoveryPicker } from '@/components/character/NaturalRecoveryPicker'
import MemorizeSpellPicker, { type MemorizeChoice } from '@/components/character/MemorizeSpellPicker'
import SorcerousRestorationPicker from '@/components/character/SorcerousRestorationPicker'
import TomeReopenToggle from '@/components/character/TomeReopenToggle'
import HitDiceModal from '@/pages/hp/HitDiceModal'
import HitDiceResultDialog from '@/pages/hp/HitDiceResultDialog'
import { haptic } from '@/auth/telegram'
import { useToast } from '@/hooks/useToast'
import { notifyMutationError } from '@/lib/mutationError'
import type { HitDiceSpendResult } from '@/api/client'
import type { CharacterFull } from '@/types'

interface Props {
  char: CharacterFull
  open: boolean
  onClose: () => void
}

/** Riposo dal menu: breve (dadi vita) o lungo (con conferma). Stesso flusso di QuickActions. */
export default function RestSheet({ char, open, onClose }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const [shortRestOpen, setShortRestOpen] = useState(false)
  const [confirmLongRest, setConfirmLongRest] = useState(false)
  const [hitDieResult, setHitDieResult] = useState<HitDiceSpendResult | null>(null)
  const [interrupted, setInterrupted] = useState(false)
  const [ateAndDrank, setAteAndDrank] = useState(true)
  const [tooSoon, setTooSoon] = useState(false)
  const [recovery, setRecovery] = useState<Record<number, number>>({})  // Recupero Naturale: livello -> slot
  const [arcane, setArcane] = useState<Record<number, number>>({})  // Recupero Arcano: livello -> slot
  const [memorize, setMemorize] = useState<MemorizeChoice | null>(null)  // Memorizzare Incantesimo (Mago 2024)
  const [restoration, setRestoration] = useState(0)  // Ripristino Stregonesco: punti stregoneria
  const [reopenTome, setReopenTome] = useState(false)  // Patto del Tomo: le scelte del Libro tornano da fare
  const is2024 = char.rules_edition === '2024'

  const rollDice = useAnimatedRoll()

  const hitDieMutation = useMutation({
    mutationFn: async ({ classId, count }: { classId: number; count: number }) => {
      const hitDie = char.classes.find((c) => c.id === classId)?.hit_die
      const rolls = await rollDice(`d${hitDie ?? 8}`, count)
      return api.characters.spendHitDice(char.id, classId, count, rolls)
    },
    onSuccess: (result) => {
      setHitDieResult(result)
      qc.invalidateQueries({ queryKey: ['character', char.id] })
      haptic.success()
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) {
        toast.error(t('character.quick_actions.hit_die_exhausted'))
        qc.invalidateQueries({ queryKey: ['character', char.id] })
      } else {
        notifyMutationError()
      }
    },
  })

  const restMutation = useMutation({
    mutationFn: ({ restType, confirmEarly }: { restType: 'long' | 'short'; confirmEarly?: boolean }) =>
      api.characters.rest(char.id, restType, {
        interrupted,
        ate_and_drank: ateAndDrank,
        confirm_early: confirmEarly,
        ...(restType === 'short' && Object.keys(recovery).length > 0 ? { natural_recovery: recovery } : {}),
        ...(restType === 'short' && Object.keys(arcane).length > 0 ? { arcane_recovery: arcane } : {}),
        ...(restType === 'short' && restoration > 0 ? { sorcerous_restoration: restoration } : {}),
        ...(restType === 'short' && memorize ? { memorize_spell: memorize } : {}),
        ...(restType === 'long' && reopenTome ? { reopen_tome: true } : {}),
      }),
    onError: (err) => {
      const detail = err instanceof ApiError ? err.detail : null
      if (detail === 'long_rest_too_soon') {
        setConfirmLongRest(false)
        setTooSoon(true)
      } else if (detail === 'rest_needs_hp') {
        toast.error(t('character.quick_actions.rest_needs_hp'))
      } else {
        notifyMutationError()
      }
    },
    onSuccess: (updated) => {
      setTooSoon(false)
      setInterrupted(false)
      setAteAndDrank(true)
      setRecovery({})
      setArcane({})
      setRestoration(0)
      setMemorize(null)
      setReopenTome(false)
      qc.setQueryData(['character', char.id], updated)
      qc.invalidateQueries({ queryKey: ['homebrew-resources', char.id] })
      setConfirmLongRest(false)
      setShortRestOpen(false)
      onClose()
      toast.success(t('character.quick_actions.rest_done'))
      haptic.success()
    },
  })

  const interruptedToggle = (hint: string) => (
    <div className="text-left">
      <SwitchToggle
        checked={interrupted}
        onChange={setInterrupted}
        label={t('character.quick_actions.rest_interrupted')}
        hint={hint}
      />
    </div>
  )

  const rowClass = `w-full min-h-[44px] flex items-center gap-3 px-4 py-3 rounded-2xl
                    bg-dnd-surface border border-dnd-border text-left
                    hover:border-dnd-gold/60 transition-[border-color] duration-200`

  return (
    <>
      <Sheet open={open} onClose={onClose} title={t('character.menu.rest')}>
        <div className="p-5 space-y-2">
          <Pressable
            onClick={() => { haptic.light(); setShortRestOpen(true) }}
            className={rowClass}
          >
            <GiNightSleep size={22} className="text-dnd-cobalt-bright" />
            <span className="text-sm text-dnd-text font-body">{t('character.quick_actions.rest_short')}</span>
          </Pressable>
          <Pressable
            onClick={() => { haptic.light(); setConfirmLongRest(true) }}
            className={rowClass}
          >
            <GiCampfire size={22} className="text-dnd-amber" />
            <span className="text-sm text-dnd-text font-body">{t('character.quick_actions.rest_long')}</span>
          </Pressable>
        </div>
      </Sheet>

      <ConfirmSheet
        open={confirmLongRest}
        onClose={() => setConfirmLongRest(false)}
        title={t('character.quick_actions.confirm_long_rest_title')}
        body={
          <div className="space-y-3">
            <p>{t('character.quick_actions.confirm_long_rest_body')}</p>
            {confirmLongRest && <RestPreviewList charId={char.id} restType="long" />}
            <TomeReopenToggle char={char} value={reopenTome} onChange={setReopenTome} />
            {interruptedToggle(t(is2024
              ? 'character.quick_actions.rest_interrupted_long_2024'
              : 'character.quick_actions.rest_interrupted_long_2014'))}
            {!is2024 && (
              <div className="text-left">
                <SwitchToggle
                  checked={ateAndDrank}
                  onChange={setAteAndDrank}
                  label={t('character.quick_actions.rest_ate_and_drank')}
                  hint={t('character.quick_actions.rest_ate_and_drank_hint')}
                />
              </div>
            )}
          </div>
        }
        confirmLabel={t('character.quick_actions.rest_long')}
        confirmVariant="primary"
        loading={restMutation.isPending}
        onConfirm={() => restMutation.mutate({ restType: 'long' })}
      />

      <ConfirmSheet
        open={tooSoon}
        onClose={() => setTooSoon(false)}
        title={t('character.quick_actions.rest_too_soon_title')}
        body={<p>{t('character.quick_actions.rest_too_soon_body', { hours: is2024 ? 16 : 24 })}</p>}
        confirmLabel={t('character.quick_actions.rest_long')}
        confirmVariant="primary"
        loading={restMutation.isPending}
        onConfirm={() => restMutation.mutate({ restType: 'long', confirmEarly: true })}
      />

      {shortRestOpen && (
        <HitDiceModal
          classes={char.classes ?? []}
          onSpend={(classId, count) => hitDieMutation.mutate({ classId, count })}
          onConfirmRest={() => restMutation.mutate({ restType: 'short' })}
          preview={
            <>
              <RestPreviewList charId={char.id} restType="short" />
              <SongOfRestToggle char={char} />
              <NaturalRecoveryPicker char={char} value={recovery} onChange={setRecovery} />
              <ArcaneRecoveryPicker char={char} value={arcane} onChange={setArcane} />
              <SorcerousRestorationPicker char={char} value={restoration} onChange={setRestoration} />
              <MemorizeSpellPicker char={char} onChange={setMemorize} />
              {is2024 && interruptedToggle(t('character.quick_actions.rest_interrupted_short_2024'))}
            </>
          }
          onClose={() => setShortRestOpen(false)}
          isPending={hitDieMutation.isPending}
          pendingClassId={hitDieMutation.isPending ? hitDieMutation.variables?.classId : undefined}
          restPending={restMutation.isPending}
        />
      )}

      {hitDieResult && (
        <HitDiceResultDialog result={hitDieResult} onClose={() => setHitDieResult(null)} />
      )}
    </>
  )
}

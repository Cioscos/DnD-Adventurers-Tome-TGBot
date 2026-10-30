import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { GiNightSleep, GiCampfire } from 'react-icons/gi'
import { api, ApiError } from '@/api/client'
import Sheet from '@/components/ui/Sheet'
import Pressable from '@/components/ui/Pressable'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import HitDiceModal from '@/pages/hp/HitDiceModal'
import HitDiceResultDialog from '@/pages/hp/HitDiceResultDialog'
import { haptic } from '@/auth/telegram'
import { useToast } from '@/hooks/useToast'
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

  const hitDieMutation = useMutation({
    mutationFn: ({ classId, count }: { classId: number; count: number }) =>
      api.characters.spendHitDice(char.id, classId, count),
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
        haptic.error()
      }
    },
  })

  const restMutation = useMutation({
    mutationFn: (restType: 'long' | 'short') => api.characters.rest(char.id, restType),
    onSuccess: (updated) => {
      qc.setQueryData(['character', char.id], updated)
      qc.invalidateQueries({ queryKey: ['homebrew-resources', char.id] })
      setConfirmLongRest(false)
      setShortRestOpen(false)
      onClose()
      toast.success(t('character.quick_actions.rest_done'))
      haptic.success()
    },
  })

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
        body={t('character.quick_actions.confirm_long_rest_body')}
        confirmLabel={t('character.quick_actions.rest_long')}
        confirmVariant="primary"
        loading={restMutation.isPending}
        onConfirm={() => restMutation.mutate('long')}
      />

      {shortRestOpen && (
        <HitDiceModal
          classes={char.classes ?? []}
          onSpend={(classId, count) => hitDieMutation.mutate({ classId, count })}
          onConfirmRest={() => restMutation.mutate('short')}
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

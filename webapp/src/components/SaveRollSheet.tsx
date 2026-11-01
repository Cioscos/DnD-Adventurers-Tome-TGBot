import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api, ApiError, type RollMode } from '@/api/client'
import { useD20Roll, d20Arg } from '@/hooks/useD20Roll'
import { useToast } from '@/hooks/useToast'
import { haptic } from '@/auth/telegram'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import InspirationRerollButton from '@/components/InspirationRerollButton'
import type { PendingSave, PendingSaveRollResult } from '@/types'

const MODES: RollMode[] = ['normal', 'advantage', 'disadvantage']

interface Props {
  charId: number
  /** Pending saves to resolve, shown one at a time. */
  saves: PendingSave[]
  onClose: () => void
}

export default function SaveRollSheet({ charId, saves: live, onClose }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const rollD20 = useD20Roll()
  const [mode, setMode] = useState<RollMode>('normal')
  const [done, setDone] = useState<number[]>([])
  // The save stays in `shown` after a pass, when the server drops it from the list.
  const [shown, setShown] = useState<{ save: PendingSave; res: PendingSaveRollResult } | null>(null)
  // Queue frozen at open: the live list shrinks as the server drops resolved saves.
  const [saves] = useState(live)
  const total = useRef(saves.length)
  const { data: char } = useQuery({ queryKey: ['character', charId], queryFn: () => api.characters.get(charId) })

  const current = saves.find((s) => !done.includes(s.id))
  // An already-failed save opens straight on its outcome (re-roll / OK).
  const view =
    shown ??
    (current?.status === 'failed'
      ? {
          save: current,
          res: {
            save: current,
            roll: { total: Number((current.last_roll as { total?: number } | null)?.total ?? 0) } as PendingSaveRollResult['roll'],
            passed: false,
            condition_removed: false,
          },
        }
      : null)
  const active = view?.save ?? current
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['character', charId] })
    qc.invalidateQueries({ queryKey: ['turn-state', charId] })
  }

  const roll = useMutation({
    mutationFn: async ({ save, reroll }: { save: PendingSave; reroll: boolean }) => {
      const m = reroll ? 'normal' : mode
      const res = await api.characters.pendingSaves.roll(charId, save.id, d20Arg(m, await rollD20(m)), reroll)
      return { save, res }
    },
    onSuccess: (r) => {
      setShown(r)
      refresh()
      if (r.res.passed) haptic.success()
      else haptic.warning()
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) {
        const code = (err.detail as { code?: string } | null)?.code
        toast.error(t(`pendingSaves.${code === 'condition_gone' ? 'gone' : code === 'inspiration_unavailable' ? 'inspiration_unavailable' : 'not_rerollable'}`))
        refresh()
        if (code === 'condition_gone') onClose()
      } else {
        toast.error(t('pendingSaves.error'))
      }
    },
  })

  const ok = async () => {
    if (!view) return
    const { save, res } = view
    try {
      if (!res.passed) await api.characters.pendingSaves.dismiss(charId, save.id)
    } catch {
      // Already closed elsewhere: nothing to dismiss.
    }
    refresh()
    setShown(null)
    const left = saves.filter((s) => s.id !== save.id && !done.includes(s.id))
    setDone((d) => [...d, save.id])
    if (left.length === 0) onClose()
  }

  if (!active) return null
  const cond = t(`character.conditions.${active.slug}`, { defaultValue: active.slug })
  const n = Math.min(done.length + 1, Math.max(total.current, done.length + 1))

  return (
    <Sheet
      open
      onClose={onClose}
      title={t('pendingSaves.title', { ability: t(`character.stats.${active.ability}`) })}
    >
      <div className="p-5 space-y-4">
        <div className="flex items-center justify-between gap-2 text-sm font-body text-dnd-text-muted">
          <span>{t('pendingSaves.line', { condition: cond, dc: active.dc })}</span>
          {total.current > 1 && (
            <span className="tabular-nums">{t('pendingSaves.progress', { n, total: total.current })}</span>
          )}
        </div>

        {!view ? (
          <>
            <div role="radiogroup" aria-label={t('common.roll_mode.title')} className="grid grid-cols-3 gap-2">
              {MODES.map((md) => (
                <Pressable
                  key={md}
                  role="radio"
                  aria-checked={mode === md}
                  haptic="light"
                  onClick={() => setMode(md)}
                  whileTap={{ scale: 0.95 }}
                  className={`min-h-[44px] rounded-xl border text-sm font-body ${
                    mode === md
                      ? 'border-dnd-gold bg-dnd-gold/20 text-dnd-gold-bright font-semibold'
                      : 'border-dnd-gold-dim/30 bg-dnd-surface text-dnd-text-muted'
                  }`}
                >
                  {t(`common.roll_mode.${md}`)}
                </Pressable>
              ))}
            </div>
            <Button
              size="lg"
              fullWidth
              loading={roll.isPending}
              onClick={() => roll.mutate({ save: active, reroll: false })}
            >
              {t('pendingSaves.roll')}
            </Button>
          </>
        ) : (
          <div className="space-y-3">
            <p className="text-center font-mono text-3xl font-bold tabular-nums text-dnd-gold-bright">
              {t('pendingSaves.total_vs_dc', { total: view.res.roll.total, dc: active.dc })}
            </p>
            <p
              className={`text-center font-display font-bold ${
                view.res.passed ? 'text-dnd-emerald-bright' : 'text-dnd-crimson-bright'
              }`}
            >
              {t(view.res.passed ? 'pendingSaves.passed' : 'pendingSaves.failed', { condition: cond })}
            </p>
            {!view.res.passed && (
              <InspirationRerollButton
                available={!!char?.heroic_inspiration}
                pending={roll.isPending}
                onClick={() => roll.mutate({ save: view.save, reroll: true })}
              />
            )}
            <Button size="lg" fullWidth variant="secondary" onClick={ok}>
              {t('pendingSaves.ok')}
            </Button>
          </div>
        )}
      </div>
    </Sheet>
  )
}

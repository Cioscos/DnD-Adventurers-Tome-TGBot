import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import type { EncounterMode } from '@/types'

interface Props {
  sessionId: number
  mode: EncounterMode
  onClose: () => void
}

export default function AddMonsterSheet({ sessionId, mode, onClose }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [count, setCount] = useState('')
  const [initMod, setInitMod] = useState('')
  const [maxHp, setMaxHp] = useState('')
  const [ac, setAc] = useState('')

  const addMutation = useMutation({
    mutationFn: () =>
      api.sessions.encounter.addCombatants(sessionId, {
        name: name.trim(),
        count: Math.max(1, Number(count) || 1),
        initiative_mod: Number(initMod) || 0,
        ...(mode === 'full' && Number(maxHp) > 0 ? { max_hp: Number(maxHp) } : {}),
        ...(mode === 'full' && Number(ac) > 0 ? { ac: Number(ac) } : {}),
      }),
    onSuccess: () => {
      haptic.success()
      qc.invalidateQueries({ queryKey: ['session-live', sessionId] })
      onClose()
    },
    onError: () => {
      haptic.error()
      toast.error(t('session.combat.action_failed'))
    },
  })

  const field = (
    label: string,
    value: string,
    set: (v: string) => void,
    opts: { placeholder: string; type?: string },
  ) => (
    <label className="block">
      <span className="text-xs uppercase tracking-wider text-dnd-gold-dim font-cinzel">
        {label}
      </span>
      <input
        type={opts.type ?? 'number'}
        inputMode={opts.type === 'text' ? undefined : 'numeric'}
        value={value}
        placeholder={opts.placeholder}
        onChange={(e) => set(e.target.value)}
        className="mt-1 w-full rounded-md bg-dnd-surface border border-dnd-border
                   px-3 py-2.5 text-sm text-dnd-text placeholder:text-dnd-text-muted/60"
      />
    </label>
  )

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-end z-50 p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="w-full rounded-2xl bg-dnd-surface-elevated p-4 space-y-3 max-h-[90vh] overflow-y-auto">
        <h3 className="font-semibold font-cinzel text-dnd-gold text-center">
          {t('session.combat.add_monster')}
        </h3>
        {field(t('session.combat.add_monster'), name, setName, {
          placeholder: t('session.combat.monster_name_placeholder'), type: 'text',
        })}
        <div className="grid grid-cols-2 gap-3">
          {field(t('session.combat.count_label'), count, setCount, { placeholder: '1' })}
          {field(t('session.combat.init_mod_label'), initMod, setInitMod, { placeholder: '0' })}
        </div>
        {mode === 'full' && (
          <div className="grid grid-cols-2 gap-3">
            {field(t('session.combat.max_hp_label'), maxHp, setMaxHp, { placeholder: '7' })}
            {field(t('session.combat.ac_label'), ac, setAc, { placeholder: '13' })}
          </div>
        )}
        <div className="flex gap-2 pt-2 border-t border-dnd-gold-dim/10">
          <button
            type="button"
            onClick={onClose}
            disabled={addMutation.isPending}
            className="flex-1 px-3 py-2 rounded-md bg-dnd-surface border border-dnd-border
                       text-sm active:opacity-60 disabled:opacity-40"
          >
            {t('common.cancel')}
          </button>
          <button
            type="button"
            onClick={() => addMutation.mutate()}
            disabled={!name.trim() || addMutation.isPending}
            className="flex-1 px-3 py-2 rounded-md bg-gradient-to-r from-dnd-gold-deep to-dnd-gold-bright
                       text-black font-cinzel font-bold uppercase tracking-widest text-xs
                       active:opacity-80 disabled:opacity-40"
          >
            {t('session.combat.add_confirm')}
          </button>
        </div>
      </div>
    </div>
  )
}

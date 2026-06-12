import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import Sheet from '@/components/ui/Sheet'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
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

  return (
    <Sheet open onClose={onClose} title={t('session.combat.add_monster')}>
      <div className="p-1 space-y-3">
        <Input
          label={t('session.combat.monster_name_label')}
          value={name}
          onChange={setName}
          placeholder={t('session.combat.monster_name_placeholder')}
        />
        <div className="grid grid-cols-2 gap-3">
          <Input
            label={t('session.combat.count_label')}
            type="number"
            inputMode="numeric"
            value={count}
            onChange={setCount}
            placeholder="1"
          />
          <Input
            label={t('session.combat.init_mod_label')}
            type="number"
            inputMode="numeric"
            value={initMod}
            onChange={setInitMod}
            placeholder="0"
          />
        </div>
        {mode === 'full' && (
          <div className="grid grid-cols-2 gap-3">
            <Input
              label={t('session.combat.max_hp_label')}
              type="number"
              inputMode="numeric"
              value={maxHp}
              onChange={setMaxHp}
              placeholder="7"
            />
            <Input
              label={t('session.combat.ac_label')}
              type="number"
              inputMode="numeric"
              value={ac}
              onChange={setAc}
              placeholder="13"
            />
          </div>
        )}
        <div className="flex gap-2 pt-2">
          <Button
            variant="secondary"
            fullWidth
            onClick={onClose}
            disabled={addMutation.isPending}
          >
            {t('common.cancel')}
          </Button>
          <Button
            variant="primary"
            fullWidth
            haptic="success"
            onClick={() => addMutation.mutate()}
            disabled={!name.trim()}
            loading={addMutation.isPending}
          >
            {t('session.combat.add_confirm')}
          </Button>
        </div>
      </div>
    </Sheet>
  )
}

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { GiHeartPlus, GiCrossedSwords } from 'react-icons/gi'
import { api } from '@/api/client'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import ChipSelect from '@/components/ui/ChipSelect'
import { showUndoToast } from '@/components/ui/UndoToast'
import { useToast } from '@/hooks/useToast'
import { haptic } from '@/auth/telegram'
import { parseCounterInput } from '@/lib/counterInput'
import type { CharacterFull } from '@/types'

interface HpQuickSheetProps {
  char: CharacterFull
  open: boolean
  onClose: () => void
}

/** Mini-sheet Danno/Cura dal tap sulla barra HP in home (spec 2026-07-17).
 *  Riusa PATCH /hp: PF temporanei, concentrazione e death saves restano
 *  governati dal server. La pagina HP completa resta il posto per temp HP,
 *  death saves e riposo. */
export default function HpQuickSheet({ char, open, onClose }: HpQuickSheetProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [op, setOp] = useState<'damage' | 'heal'>('damage')
  const [amount, setAmount] = useState('')

  const hpMutation = useMutation({
    mutationFn: ({ op, value }: { op: 'damage' | 'heal' | 'set_current'; value: number }) =>
      api.characters.updateHp(char.id, op, value),
    onError: () => haptic.error(),
  })

  // 0 is parsed successfully by parseCounterInput (it only rejects empty/non-numeric
  // input) but is a meaningless damage/heal amount — treat it as invalid here so the
  // Applica button disables consistently with the apply() guard below.
  const parsedAmount = parseCounterInput(amount, null)
  const isAmountInvalid = parsedAmount === null || parsedAmount === 0

  const apply = () => {
    const n = parsedAmount
    if (n === null || n === 0) { haptic.error(); return }
    const prevCurrent = char.current_hit_points
    hpMutation.mutate({ op, value: n }, {
      onSuccess: (updated) => {
        qc.setQueryData(['character', char.id], updated)
        qc.invalidateQueries({ queryKey: ['homebrew-resources', char.id] })
        haptic.success()
        const conc = updated.concentration_save
        if (conc?.lost_concentration) {
          toast.warning(t('character.hp.concentration_lost'), { duration: 4000 })
        }
        showUndoToast({
          message: t(op === 'damage' ? 'character.hp.quick_damage_undo' : 'character.hp.quick_heal_undo', { n }),
          actionLabel: t('character.hp.quick_undo_action'),
          onUndo: () => hpMutation.mutate({ op: 'set_current', value: prevCurrent }, {
            onSuccess: (u) => {
              qc.setQueryData(['character', char.id], u)
              qc.invalidateQueries({ queryKey: ['homebrew-resources', char.id] })
            },
          }),
        })
        setAmount('')
        onClose()
      },
    })
  }

  return (
    <Sheet open={open} onClose={onClose} title={t('character.hp.quick_sheet_title')}>
      <div className="p-5 space-y-3">
        <ChipSelect
          label=""
          options={[
            { value: 'damage', label: t('character.hp.quick_damage') },
            { value: 'heal', label: t('character.hp.quick_heal') },
          ]}
          value={op}
          onChange={(v) => setOp(v as 'damage' | 'heal')}
          columns={2}
        />
        <Input
          label={t('character.hp.quick_apply')}
          value={amount}
          onChange={setAmount}
          type="number"
          min={0}
          inputMode="numeric"
          autoFocus
          placeholder="0"
        />
        <Button
          variant={op === 'damage' ? 'danger' : 'primary'}
          fullWidth
          size="lg"
          icon={op === 'damage' ? <GiCrossedSwords size={16} /> : <GiHeartPlus size={16} />}
          loading={hpMutation.isPending}
          disabled={isAmountInvalid}
          onClick={apply}
          haptic="medium"
        >
          {t('character.hp.quick_apply')}
        </Button>
        <Button
          variant="ghost"
          fullWidth
          onClick={() => { onClose(); navigate(`/char/${char.id}/hp`) }}
        >
          {t('character.hp.go_full_page')}
        </Button>
      </div>
    </Sheet>
  )
}

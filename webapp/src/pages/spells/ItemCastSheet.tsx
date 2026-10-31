import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import ResultDialog from '@/components/ui/ResultDialog'
import RollButton from '@/components/ui/RollButton'
import RollResultModal, { type RollResult } from '@/components/RollResultModal'
import { useD20Roll, type RollMode } from '@/hooks/useD20Roll'
import type { ResolvedItemCast } from '@/lib/itemCast'

interface Props {
  charId: number
  resolved: ResolvedItemCast
  onClose: () => void
}

/** Esito del lancio da oggetto: cariche, CD/attacco risolti e tiro per colpire. */
export default function ItemCastSheet({ charId, resolved, onClose }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const rollD20 = useD20Roll()
  const [result, setResult] = useState<RollResult | null>(null)
  const { spell, saveDc, attackBonus, isAttack, saveAbility, spent, remaining, max } = resolved
  const bonus = attackBonus ?? 0

  const attackMutation = useMutation({
    mutationFn: async (mode: RollMode) => {
      const n = mode === 'normal' ? 1 : 2
      const faces = (await rollD20(mode)) ?? Array.from({ length: n }, () => 1 + Math.floor(Math.random() * 20))
      const value = mode === 'advantage' ? Math.max(...faces) : mode === 'disadvantage' ? Math.min(...faces) : faces[0]
      const keep = mode === 'advantage' ? 'kh1' : mode === 'disadvantage' ? 'kl1' : ''
      await api.dice.result(charId, {
        rolls: faces.map((v) => ({ kind: 'd20' as const, value: v })),
        modifier: bonus,
        notation: `${n}d20${keep}${bonus >= 0 ? '+' : ''}${bonus}`,
        label: spell.name,
        mode,
      })
      return { value, faces, mode }
    },
    onSuccess: ({ value, faces, mode }) => {
      qc.invalidateQueries({ queryKey: ['dice-history', charId] })
      qc.invalidateQueries({ queryKey: ['history', charId] })
      setResult({
        die: value, dice: faces, mode, bonus, total: value + bonus,
        is_critical: value === 20, is_fumble: value === 1,
      })
      haptic.success()
    },
  })

  if (result) {
    return <RollResultModal result={result} title={spell.name} onClose={() => setResult(null)} />
  }

  return (
    <ResultDialog open onClose={onClose} accent="arcane" size="sm" title={spell.name}
      subtitle={t('character.inventory.magic.cast_done', { name: spell.name })}>
      {spent > 0 && (
        <p className="text-sm text-dnd-text font-body">
          {t('character.inventory.magic.cast_spent', { n: spent })}
          {remaining != null && max != null && ` · ${t('character.inventory.magic.cast_remaining', { current: remaining, max })}`}
        </p>
      )}
      {saveDc != null && !isAttack && (
        <p className="text-lg font-mono font-bold tabular-nums text-dnd-gold-bright">
          {saveAbility
            ? t('character.inventory.magic.dc_save', { dc: saveDc, ability: saveAbility })
            : t('character.inventory.magic.dc_only', { dc: saveDc })}
        </p>
      )}
      {isAttack && (
        <>
          {attackBonus != null && (
            <p className="text-lg font-mono font-bold tabular-nums text-dnd-gold-bright">
              {t('character.inventory.magic.attack_bonus', { bonus: `${bonus >= 0 ? '+' : ''}${bonus}` })}
            </p>
          )}
          <RollButton
            onRoll={(mode) => attackMutation.mutate(mode)}
            pending={attackMutation.isPending}
            ariaLabel={t('character.inventory.magic.roll_attack')}
            className="min-h-11 px-4 rounded-lg text-sm font-medium bg-dnd-crimson/20 text-dnd-crimson-bright border border-dnd-crimson/30 active:opacity-60"
          >
            {t('character.inventory.magic.roll_attack')}
          </RollButton>
        </>
      )}
    </ResultDialog>
  )
}

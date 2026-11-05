import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api, type RollOption } from '@/api/client'
import { optionHints, refreshAfterOptions } from '@/lib/rollOptions'
import { AfterRollButton } from '@/components/rules/AfterRollOptions'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import type { RollDamageResult } from '@/types'

const sidesOf = (kind: string | null | undefined) => Number((kind ?? '').slice(1))

/** Privilegi usati dopo aver visto i dadi di danno: si scelgono i dadi, il server li ritira dal tiro che ha salvato. */
export default function AfterDamageOptions({ charId, spellId, result, onResult }: {
  charId: number
  spellId: number
  result: RollDamageResult
  onResult: (result: RollDamageResult) => void
}) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [option, setOption] = useState<RollOption | null>(null)
  const [picked, setPicked] = useState<number[]>([])
  const query = { roll: 'spell_damage', spell_id: spellId } as const
  const { data } = useQuery({
    queryKey: ['roll-options', charId, query],
    queryFn: () => api.characters.rollOptions(charId, query),
    gcTime: 0,
  })

  const apply = useMutation({
    mutationFn: () => api.characters.lastDamageOptions(charId, { options: [option!.key], option_inputs: {}, reroll: picked }),
    onSuccess: (updated) => {
      onResult(updated)
      refreshAfterOptions(qc, charId, updated.option_result)
      qc.invalidateQueries({ queryKey: ['roll-options', charId, query] })
      setOption(null)
      setPicked([])
    },
    onError: () => { toast.warning(t('character.roll_options.after_roll_failed')) },
  })

  const options = (data ?? []).filter((o) => o.phase === 'after_damage')
  if (options.length === 0) return null

  if (!option) {
    return (
      <div className="space-y-2" data-testid="after-damage-options">
        {options.map((o) => <AfterRollButton key={o.key} option={o} onClick={() => setOption(o)} />)}
      </div>
    )
  }

  const limit = option.reroll_limit ?? 0
  const dice = [
    ...result.main_rolls.map((value, index) => ({ value, index, sides: sidesOf(result.main_kind) })),
    ...result.extra_rolls.map((value, i) => ({ value, index: result.main_rolls.length + i, sides: sidesOf(result.extra_kind) })),
  ].filter((d) => !option.keep_rolled || d.value === d.sides)
  const toggle = (index: number) =>
    setPicked((p) => (p.includes(index) ? p.filter((i) => i !== index) : [...p, index]))

  return (
    <div className="space-y-2 rounded-xl border border-dnd-border bg-dnd-surface/80 p-3" data-testid="after-damage-options">
      <p className="text-sm font-body text-dnd-text">{option.label}</p>
      <p className="text-xs font-body text-dnd-text-muted">
        {[t('character.roll_options.after_damage_pick', { count: limit }), ...optionHints(option, t)].join(' · ')}
      </p>
      <div className="flex flex-wrap gap-2">
        {dice.map((d) => {
          const on = picked.includes(d.index)
          return (
            <Pressable
              key={d.index}
              type="button"
              aria-pressed={on}
              disabled={!on && picked.length >= limit}
              onClick={() => toggle(d.index)}
              className={`min-h-11 min-w-11 px-3 rounded-lg border font-mono tabular-nums text-sm disabled:opacity-40
                ${on ? 'border-dnd-gold/70 text-dnd-gold-bright shadow-halo-gold' : 'border-dnd-border text-dnd-text'}`}
            >
              {d.value}
            </Pressable>
          )
        })}
      </div>
      <div className="flex gap-2">
        <Button variant="secondary" fullWidth onClick={() => { setOption(null); setPicked([]) }}>{t('common.cancel')}</Button>
        <Button variant="primary" fullWidth disabled={picked.length === 0} loading={apply.isPending} onClick={() => apply.mutate()}>
          {t('character.roll_options.after_damage_confirm')}
        </Button>
      </div>
    </div>
  )
}

import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import SwitchToggle from '@/components/ui/SwitchToggle'
import { notifyMutationError } from '@/lib/mutationError'
import { useToast } from '@/hooks/useToast'
import type { CharacterFull } from '@/types'

type Row = { id: number; name: string; hp: number; hpMax: number }

/** Preservare Vita (R42): 5 × livello PF fra chi lo usa e gli altri partecipanti della serata. Il server impone riserva,
 *  tetto alla metà dei PF massimi e destinatari; qui si vede solo quanto resta. Chi non è nell'app: lo dice il giocatore al GM (D1). */
export default function PreserveLifeSheet({ char, pool, onClose }: { char: CharacterFull; pool: number; onClose: () => void }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const [amounts, setAmounts] = useState<Record<number, string>>({})
  const [living, setLiving] = useState(false)
  const allies = useQuery({ queryKey: ['session-allies', char.id], queryFn: () => api.characters.sessionAllies(char.id) })
  const rows: Row[] = useMemo(() => [
    { id: char.id, name: t('character.turn.preserve_self'), hp: char.current_hit_points, hpMax: char.hit_points },
    ...(allies.data ?? []).map((a) => ({ id: a.id, name: a.name, hp: a.hp ?? 0, hpMax: a.hp_max ?? 0 })),
  ], [char.id, char.current_hit_points, char.hit_points, allies.data, t])
  const cap = (r: Row) => Math.max(0, Math.floor(r.hpMax / 2) - r.hp)
  const value = (id: number) => Math.max(0, parseInt(amounts[id] ?? '0', 10) || 0)
  const total = rows.reduce((n, r) => n + value(r.id), 0)
  const over = total > pool || rows.some((r) => value(r.id) > cap(r))

  const go = useMutation({
    mutationFn: () => api.characters.preserveLife(char.id, {
      allocations: rows.filter((r) => value(r.id) > 0).map((r) => ({ character_id: r.id, amount: value(r.id) })),
      confirm_living: living,
    }),
    onSuccess: (res) => {
      toast.info(t('character.turn.preserve_done'), { description: res.healed.map((h) => `${h.name} +${h.healed}`).join(', ') })
      qc.invalidateQueries({ queryKey: ['character', char.id] })
      qc.invalidateQueries({ queryKey: ['turn-state', char.id] })
      onClose()
    },
    onError: () => notifyMutationError(),
  })

  return (
    <Sheet open onClose={onClose} title={t('character.turn.preserve_title')} zClassName="z-[60]">
      <div className="flex flex-col gap-3 px-4 pb-4">
        <p className="text-sm font-body text-dnd-text tabular-nums">{t('character.turn.preserve_pool', { left: Math.max(0, pool - total), pool })}</p>
        {rows.map((r) => (
          <div key={r.id} className="flex flex-col gap-1">
            <Input label={`${r.name} (${r.hp}/${r.hpMax})`} type="number" inputMode="numeric" min={0} max={cap(r)}
              value={amounts[r.id] ?? ''} placeholder="0" onChange={(v) => setAmounts((s) => ({ ...s, [r.id]: v }))}
              error={value(r.id) > cap(r) ? t('character.turn.preserve_cap', { max: cap(r) }) : undefined} />
          </div>
        ))}
        <p className="text-xs text-dnd-text-muted font-body">{t('character.turn.preserve_others', { n: Math.max(0, pool - total) })}</p>
        <SwitchToggle label={t('character.turn.preserve_living')} checked={living} onChange={setLiving} />
        <Button variant="primary" disabled={total < 1 || over || !living} loading={go.isPending} onClick={() => go.mutate()}>
          {t('character.turn.preserve_go')}
        </Button>
      </div>
    </Sheet>
  )
}

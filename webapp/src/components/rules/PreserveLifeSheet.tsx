import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ApiError } from '@/api/client'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import SwitchToggle from '@/components/ui/SwitchToggle'
import { useToast } from '@/hooks/useToast'
import type { CharacterFull } from '@/types'

const ERRORS = ['over_half', 'over_pool', 'no_uses', 'turn_slot_used', 'invalid_target', 'target_dead', 'confirm_required', 'bad_allocation', 'feature_not_usable']

/** Preservare Vita (R42): 5 × livello PF fra chi lo usa e gli altri partecipanti della serata. Il server impone riserva,
 *  tetto alla metà dei PF massimi e destinatari; qui si vede solo quanto resta. Chi non è nell'app: lo dice il giocatore al GM (D1). */
export default function PreserveLifeSheet({ char, onClose }: { char: CharacterFull; onClose: () => void }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const [amounts, setAmounts] = useState<Record<number, string>>({})
  const [living, setLiving] = useState(false)
  // Riserva e tetti li calcola il server: la pagina non vede i PF degli altri giocatori.
  const info = useQuery({ queryKey: ['preserve-life', char.id], queryFn: () => api.characters.preserveLifeInfo(char.id) })
  const pool = info.data?.pool ?? 0
  const rows = (info.data?.targets ?? []).map((x) => ({ ...x, name: x.self ? t('character.turn.preserve_self') : x.name }))
  const cap = (r: { cap: number }) => r.cap
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
    // Il server dice perché rifiuta (metà dei PF, riserva, azione già spesa...): si traduce, mai il messaggio tecnico.
    onError: (err) => {
      const code = err instanceof ApiError ? (err.detail as { code?: string } | null)?.code : undefined
      toast.error(t(`character.turn.preserve_errors.${code && ERRORS.includes(code) ? code : 'default'}`))
      qc.invalidateQueries({ queryKey: ['preserve-life', char.id] })
    },
  })

  return (
    <Sheet open onClose={onClose} title={t('character.turn.preserve_title')} zClassName="z-[60]">
      <div className="flex flex-col gap-3 px-4 pb-4">
        <p className="text-sm font-body text-dnd-text tabular-nums">{t('character.turn.preserve_pool', { left: Math.max(0, pool - total), pool })}</p>
        {rows.map((r) => (
          <div key={r.id} className="flex flex-col gap-1">
            <Input label={r.name} type="number" inputMode="numeric" min={0} max={cap(r)}
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

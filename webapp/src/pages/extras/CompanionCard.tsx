import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Swords, Trash2 } from 'lucide-react'
import { api, ApiError } from '@/api/client'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import HPGauge from '@/components/ui/HPGauge'
import Pressable from '@/components/ui/Pressable'
import ExpandChevron from '@/components/ui/ExpandChevron'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import RollButton from '@/components/ui/RollButton'
import { useD20Roll, type RollMode } from '@/hooks/useD20Roll'
import { useToast } from '@/hooks/useToast'
import { notifyMutationError } from '@/lib/mutationError'
import { haptic } from '@/auth/telegram'
import type { Companion, CompanionAction, CompanionAttackResult } from '@/types'

function EnBadge() {
  const { t } = useTranslation()
  return (
    <span className="ml-1 text-xs font-bold px-1.5 py-0.5 rounded bg-dnd-surface border border-dnd-border text-dnd-text-muted">
      {t('catalog.en_badge')}
    </span>
  )
}

interface Props {
  charId: number
  comp: Companion
  /** Remaining Wild Shape uses (null when the character has no such ability). */
  wildShapeUses: number | null
}

export default function CompanionCard({ charId, comp, wildShapeUses }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const rollD20 = useD20Roll()
  const [amount, setAmount] = useState('')
  const [open, setOpen] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [forceAsk, setForceAsk] = useState(false)
  const [result, setResult] = useState<{ name: string; r: CompanionAttackResult } | null>(null)

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['companions', charId] })
    qc.invalidateQueries({ queryKey: ['character', charId] })
  }

  const hp = useMutation({
    mutationFn: (op: 'damage' | 'heal') => api.companions.hp(charId, comp.id, op, Number(amount)),
    onSuccess: () => { setAmount(''); haptic.success(); refresh() },
    onError: () => notifyMutationError(),
  })

  const attack = useMutation({
    mutationFn: async ({ idx, mode }: { idx: number; mode: RollMode }) => {
      const dice = await rollD20(mode)
      return api.companions.attack(charId, comp.id, idx, mode, dice)
    },
    onSuccess: (r, { idx }) => {
      setResult({ name: comp.statblock.actions?.[idx]?.name ?? '', r })
      haptic.success()
      refresh()
    },
    onError: () => notifyMutationError(),
  })

  const activate = useMutation({
    mutationFn: (force: boolean) => api.companions.activate(charId, comp.id, force),
    onSuccess: () => { setForceAsk(false); haptic.success(); refresh() },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409 && err.detail === 'no_wild_shape_uses') setForceAsk(true)
      else if (err instanceof ApiError && err.status === 409 && err.detail === 'character_down') toast.error(t('character.extras.character_down'))
      else notifyMutationError()
    },
  })

  const deactivate = useMutation({
    mutationFn: () => api.companions.deactivate(charId, comp.id),
    onSuccess: refresh,
    onError: () => notifyMutationError(),
  })

  const remove = useMutation({
    mutationFn: () => api.companions.remove(charId, comp.id),
    onSuccess: () => { setConfirmDelete(false); refresh() },
    onError: () => notifyMutationError(),
  })

  const amountOk = Number(amount) > 0
  const sb = comp.statblock
  const attacks = (sb.actions ?? []).flatMap((a, idx) => (a.attack_bonus != null ? [{ a, idx }] : []))
  const text = (a: CompanionAction, i: number) => (
    <p key={`${a.name}-${i}`} className="text-sm font-body text-dnd-text">
      <span className="font-bold">{a.name}.</span> {a.desc}{a.en && <EnBadge />}
    </p>
  )

  return (
    <Surface variant={comp.is_active ? 'sigil' : 'elevated'} className="p-4 space-y-3">
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <p className="font-cinzel text-dnd-gold break-words">{comp.name}</p>
          {comp.is_active && (
            <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-emerald-bright">{t('character.extras.active')}</p>
          )}
          {comp.notes && <p className="text-xs text-dnd-text-muted font-body break-words">{comp.notes}</p>}
        </div>
        <div className="shrink-0 text-center">
          <p className="font-mono font-bold tabular-nums text-dnd-gold-bright leading-none">{comp.armor_class}</p>
          <p className="text-xs font-cinzel uppercase text-dnd-text-muted">{t('character.ac.short')}</p>
        </div>
      </div>

      <div>
        <div className="flex justify-between text-sm font-mono tabular-nums mb-1">
          <span className="text-dnd-text font-bold">{comp.current_hp}/{comp.max_hp}</span>
          {comp.temp_hp > 0 && <span className="text-dnd-cobalt-bright">+{comp.temp_hp} temp</span>}
        </div>
        <HPGauge current={comp.current_hp} max={comp.max_hp} temp={comp.temp_hp} size="md" segmented />
        {comp.current_hp === 0 && (
          <p className="mt-1 text-xs text-dnd-crimson-bright font-body">{t('character.extras.down')}</p>
        )}
      </div>

      <div className="flex items-end gap-2">
        <div className="flex-1 min-w-0">
          <Input type="number" inputMode="numeric" min={0} value={amount} onChange={setAmount} placeholder="0"
            label={t('character.extras.amount')} />
        </div>
        <Button variant="danger" className="min-h-11" disabled={!amountOk} loading={hp.isPending && hp.variables === 'damage'}
          onClick={() => hp.mutate('damage')}>{t('character.hp.quick_damage')}</Button>
        <Button variant="primary" className="min-h-11" disabled={!amountOk} loading={hp.isPending && hp.variables === 'heal'}
          onClick={() => hp.mutate('heal')}>{t('character.hp.quick_heal')}</Button>
      </div>

      {attacks.length > 0 && (
        <ul className="space-y-1.5">
          {attacks.map(({ a, idx }) => (
            <li key={idx} className="flex items-center gap-2">
              <span className="flex-1 min-w-0 text-sm font-body text-dnd-text break-words">
                {a.name}
                <span className="block text-xs font-mono text-dnd-text-muted tabular-nums">
                  {a.attack_bonus! >= 0 ? '+' : ''}{a.attack_bonus}{a.damage_dice ? ` · ${a.damage_dice}` : ''}
                </span>
              </span>
              <RollButton
                onRoll={(mode) => attack.mutate({ idx, mode })}
                pending={attack.isPending}
                ariaLabel={`${t('character.turn.attack')} ${a.name}`}
                className="flex items-center gap-1 text-sm font-medium px-4 min-h-11 rounded-lg border bg-dnd-crimson/20 text-dnd-crimson-bright border-dnd-crimson/30"
              >
                <Swords size={14} />{t('character.turn.attack')}
              </RollButton>
            </li>
          ))}
        </ul>
      )}
      {result && (
        <p role="status" className="text-sm font-mono tabular-nums text-dnd-text px-3 py-2 rounded-xl bg-dnd-surface-raised border border-dnd-border">
          {result.name}: {result.r.to_hit_die}{result.r.to_hit_bonus >= 0 ? '+' : ''}{result.r.to_hit_bonus} = {result.r.to_hit_total}
          {result.r.is_critical && ` · ${t('character.extras.critical')}`}
          {' · '}{result.r.damage_total} {result.r.damage_type ?? ''}
        </p>
      )}

      {comp.kind === 'wild_shape' && (
        comp.is_active ? (
          <Button variant="secondary" fullWidth className="min-h-11" loading={deactivate.isPending} onClick={() => deactivate.mutate()}>
            {t('character.extras.end_form')}
          </Button>
        ) : (
          <Button fullWidth className="min-h-11" loading={activate.isPending} onClick={() => activate.mutate(false)}>
            {t('character.extras.activate')}{wildShapeUses != null ? ` (${wildShapeUses})` : ''}
          </Button>
        )
      )}

      {((sb.traits?.length ?? 0) > 0 || (sb.actions?.length ?? 0) > 0) && (
        <div>
          <Pressable onClick={() => setOpen((o) => !o)} aria-expanded={open}
            className="w-full min-h-11 flex items-center justify-between text-sm font-cinzel uppercase tracking-widest text-dnd-text-muted">
            {t('character.extras.statblock')}<ExpandChevron open={open} />
          </Pressable>
          {open && (
            <div className="space-y-2">
              {sb.traits?.map(text)}
              {sb.actions?.map(text)}
            </div>
          )}
        </div>
      )}

      <Button variant="ghost" className="min-h-11" icon={<Trash2 size={14} />} onClick={() => setConfirmDelete(true)}>
        {t('common.delete')}
      </Button>

      <ConfirmSheet open={confirmDelete} onClose={() => setConfirmDelete(false)} onConfirm={() => remove.mutate()}
        title={t('character.extras.delete_title', { name: comp.name })} confirmLabel={t('common.delete')} loading={remove.isPending} />
      <ConfirmSheet open={forceAsk} onClose={() => setForceAsk(false)} onConfirm={() => activate.mutate(true)}
        title={t('character.extras.force_title')} body={t('character.extras.force_body')}
        confirmLabel={t('character.extras.force_confirm')} confirmVariant="primary" loading={activate.isPending} />
    </Surface>
  )
}

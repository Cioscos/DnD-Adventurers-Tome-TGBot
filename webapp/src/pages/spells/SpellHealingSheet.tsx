import { Fragment, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { GiHealthNormal as Heart, GiPerspectiveDiceSixFacesRandom as Dices } from 'react-icons/gi'
import { api } from '@/api/client'
import { askRollOptions, castSpell, CastCancelled, refreshAfterOptions } from '@/lib/rollOptions'
import { notifyCastError } from '@/lib/mutationError'
import { haptic } from '@/auth/telegram'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import SwitchToggle from '@/components/ui/SwitchToggle'
import RollNotes from '@/components/rules/RollNotes'
import type { OptionResult } from '@/api/client'
import type { RollHealingResult, Spell } from '@/types'

interface Props {
  charId: number
  spell: Spell | null
  slotLevel: number | null
  slotId?: number
  asRitual?: boolean
  onClose: () => void
  onBack?: () => void
}

// Cure che toccano più creature (chi lancia compreso); le altre una sola. Il server ricontrolla (HealingSpec.targets).
const MULTI_TARGET: Record<string, number> = { 'mass-cure-wounds': 6, 'mass-healing-word': 6, 'prayer-of-healing': 6, 'mass-heal': 20 }
// Cure che si dividono fra i bersagli, una quantità ciascuno (D-038): il totale.
const POOL: Record<string, number> = { 'mass-heal': 700 }

/** Passo «cura» dello sheet di lancio (R41): il server tira i dadi e somma modificatore e privilegi. La cura va a chi lancia
 *  e/o ai PG seduti alla stessa serata attiva (B8): il server verifica la serata e applica i PF. */
export default function SpellHealingSheet({ charId, spell, slotLevel, slotId, asRitual = false, onClose, onBack }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [result, setResult] = useState<RollHealingResult | null>(null)
  const [castNotes, setCastNotes] = useState<OptionResult | undefined>(undefined)
  const [consumed, setConsumed] = useState(false)
  // U22: di default la cura va a chi lancia, così non si perde; scegliere un alleato (bersaglio unico) la sposta
  const [onSelf, setOnSelf] = useState(true)
  const [allyIds, setAllyIds] = useState<number[]>([])
  const [amounts, setAmounts] = useState<Record<number, string>>({})
  const spellId = spell?.id
  useEffect(() => {
    if (spellId != null) { setResult(null); setCastNotes(undefined); setConsumed(false); setOnSelf(true); setAllyIds([]); setAmounts({}) }
  }, [spellId])
  const { data: everyone = [] } = useQuery({ queryKey: ['session-allies', charId], queryFn: () => api.characters.sessionAllies(charId), enabled: spellId != null })
  const allies = everyone.filter((a) => !a.dead)  // il server rifiuta un bersaglio morto
  const max = MULTI_TARGET[spell?.srd_index ?? ''] ?? 1
  // Con un solo bersaglio la scelta è esclusiva: accendere qualcuno spegne gli altri
  const pickSelf = (on: boolean) => { setOnSelf(on); if (on && max === 1) setAllyIds([]) }
  const pickAlly = (id: number, on: boolean) => {
    if (!on) { setAllyIds(allyIds.filter((x) => x !== id)); return }
    if (max === 1) { setOnSelf(false); setAllyIds([id]); return }
    if (allyIds.length + (onSelf ? 1 : 0) < max) setAllyIds([...allyIds, id])
  }

  const pool = POOL[spell?.srd_index ?? '']
  const chosen = [...(onSelf ? [charId] : []), ...allyIds]
  const amount = (id: number) => Math.max(0, parseInt(amounts[id] ?? '', 10) || 0)
  const left = (pool ?? 0) - chosen.reduce((n, id) => n + amount(id), 0)
  const unsplit = pool != null && (left < 0 || chosen.some((id) => amount(id) < 1))
  const amountInput = (id: number, label: string) => pool != null && chosen.includes(id) && (
    <Input label={label} type="number" inputMode="numeric" min={1} max={pool}
      value={amounts[id] ?? ''} placeholder="0" onChange={(v) => setAmounts((s) => ({ ...s, [id]: v }))} />
  )

  const level = slotLevel && slotLevel > 0 ? slotLevel : spell?.level ?? 0
  const mutation = useMutation({
    mutationFn: async () => {
      if (!spell) throw new Error('no spell')
      if (!consumed) {
        const updated = await castSpell(charId, spell.id, asRitual
          ? { as_ritual: true, slot_level: null }
          : { slot_id: slotId, slot_level: slotLevel })
        qc.setQueryData(['character', charId], updated)
        qc.invalidateQueries({ queryKey: ['turn-state', charId] })
        refreshAfterOptions(qc, charId, updated.option_result)
        setCastNotes(updated.option_result ?? undefined)
        setConsumed(true)
      }
      const choice = await askRollOptions(charId, { roll: 'spell_healing', spell_id: spell.id, casting_level: level }, 'before', { cancellable: true })
      return api.spells.rollHealing(charId, spell.id, {
        casting_level: level, apply_to_self: onSelf, target_character_ids: allyIds,
        ...(pool != null ? { amounts: Object.fromEntries(chosen.map((id) => [id, amount(id)])) } : {}), ...(choice.options.length > 0 ? choice : {}),
      })
    },
    onSuccess: (data) => {
      haptic.success()
      refreshAfterOptions(qc, charId, data.option_result)
      qc.invalidateQueries({ queryKey: ['character', charId] })
      setResult(data)
    },
    onError: (err) => { if (!(err instanceof CastCancelled)) notifyCastError(err) },
  })

  if (!spell) return null
  return (
    <div className="space-y-4 p-5">
      {!result ? (
        <>
          <div className="text-center">
            <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim">{t('character.spells.roll_healing.casting_level')}</p>
            <p className="mt-1 font-display text-xl font-bold">{t('character.slots.level', { level })}</p>
            {spell.healing_preview?.[level] && (
              <p className="mt-1 font-mono text-sm tabular-nums text-dnd-text-muted" data-testid="healing-formula">
                {t('character.spells.roll_healing.formula', { formula: spell.healing_preview[level] })}
              </p>
            )}
          </div>
          {allies.length > 0 && <h3 className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim">{t('character.spells.roll_healing.targets')}</h3>}
          <SwitchToggle label={t('character.spells.roll_healing.on_self')} checked={onSelf} onChange={pickSelf} />
          {amountInput(charId, t('character.spells.roll_healing.amount_self'))}
          {allies.map((a) => (
            <Fragment key={a.id}>
              <SwitchToggle label={a.name} aria-label={a.name} checked={allyIds.includes(a.id)} onChange={(on) => pickAlly(a.id, on)} />
              {amountInput(a.id, t('character.spells.roll_healing.amount', { name: a.name }))}
            </Fragment>
          ))}
          {pool != null && (
            <p className={`text-sm font-body tabular-nums ${left < 0 ? 'text-dnd-crimson-bright' : 'text-dnd-text'}`}>
              {left < 0 ? t('character.spells.roll_healing.pool_over', { n: -left, pool }) : t('character.spells.roll_healing.pool_left', { n: left, pool })}
            </p>
          )}
          <Button variant="primary" fullWidth disabled={unsplit} icon={<Dices size={18} />} onClick={() => mutation.mutate()} loading={mutation.isPending} haptic="medium">
            {t('character.spells.roll_healing.roll_button')}
          </Button>
          {onBack && <Button variant="ghost" fullWidth onClick={onBack} disabled={mutation.isPending}>{t('common.back')}</Button>}
        </>
      ) : (
        <>
          <p className="text-center text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim">{result.breakdown}</p>
          <div className="rounded-md border border-dnd-gold-dim/40 bg-dnd-surface p-3 text-center">
            <Heart size={16} className="mx-auto text-dnd-gold-bright" aria-hidden />
            <p className="mt-1 text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim">{t('character.spells.roll_healing.total')}</p>
            <p className="mt-0.5 text-2xl font-display font-black tabular-nums text-dnd-text">{result.total}</p>
          </div>
          {result.maximized && <p className="text-center text-sm text-dnd-text-muted">{t('character.spells.roll_healing.maximized')}</p>}
          {onSelf && <p className="text-center text-sm text-dnd-text-muted">{t('character.spells.roll_healing.healed_self', { n: result.healed })}</p>}
          {result.healed_allies?.map((a) => (
            <p key={a.id} className="text-center text-sm text-dnd-text-muted">{t('character.spells.roll_healing.healed_ally', { name: a.name, n: a.healed })}</p>
          ))}
          {result.self_healed > 0 && <p className="text-center text-sm text-dnd-text-muted">{t('character.spells.roll_healing.self_healed', { n: result.self_healed })}</p>}
          <RollNotes charId={charId} optionResult={castNotes} />
          <Button variant="secondary" fullWidth onClick={onClose}>{t('character.spells.roll_damage.close')}</Button>
        </>
      )}
    </div>
  )
}

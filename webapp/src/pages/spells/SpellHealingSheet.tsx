import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { GiHealthNormal as Heart, GiPerspectiveDiceSixFacesRandom as Dices } from 'react-icons/gi'
import { api } from '@/api/client'
import { askRollOptions, castSpell, CastCancelled, refreshAfterOptions } from '@/lib/rollOptions'
import { notifyCastError } from '@/lib/mutationError'
import { haptic } from '@/auth/telegram'
import Button from '@/components/ui/Button'
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

/** Passo «cura» dello sheet di lancio (R41): il server tira i dadi e somma modificatore e privilegi. */
export default function SpellHealingSheet({ charId, spell, slotLevel, slotId, asRitual = false, onClose, onBack }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [result, setResult] = useState<RollHealingResult | null>(null)
  const [castNotes, setCastNotes] = useState<OptionResult | undefined>(undefined)
  const [consumed, setConsumed] = useState(false)
  const [onSelf, setOnSelf] = useState(false)
  const spellId = spell?.id
  useEffect(() => {
    if (spellId != null) { setResult(null); setCastNotes(undefined); setConsumed(false); setOnSelf(false) }
  }, [spellId])

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
      const choice = await askRollOptions(charId, { roll: 'spell_healing', spell_id: spell.id, casting_level: level })
      return api.spells.rollHealing(charId, spell.id, {
        casting_level: level, apply_to_self: onSelf, ...(choice.options.length > 0 ? choice : {}),
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
          </div>
          <SwitchToggle label={t('character.spells.roll_healing.on_self')} checked={onSelf} onChange={setOnSelf} />
          <Button variant="primary" fullWidth icon={<Dices size={18} />} onClick={() => mutation.mutate()} loading={mutation.isPending} haptic="medium">
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
          {result.self_healed > 0 && <p className="text-center text-sm text-dnd-text-muted">{t('character.spells.roll_healing.self_healed', { n: result.self_healed })}</p>}
          <RollNotes charId={charId} optionResult={castNotes} />
          <Button variant="secondary" fullWidth onClick={onClose}>{t('character.spells.roll_damage.close')}</Button>
        </>
      )}
    </div>
  )
}

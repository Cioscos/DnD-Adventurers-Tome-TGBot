import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, ApiError } from '@/api/client'
import type { WildSurgeEntry, WildSurgeResult } from '@/api/client'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import SwitchToggle from '@/components/ui/SwitchToggle'
import { useToast } from '@/hooks/useToast'
import type { CharacterFull } from '@/types'

const ERRORS = ['once_per_turn', 'tides_not_spent', 'no_repeat', 'no_pending_surge', 'feature_not_usable', 'invalid_choice']
const TIDES = 'sorcerer.tides_of_chaos'

/** Impulso di Magia Selvaggia (Stregone 2014): il GM lo chiede dopo un incantesimo, il server tira il d20 (una volta per turno)
 *  e con 1 la tabella dei 50 impulsi, e applica PF, slot, punti, azione extra, CA e stati con timer. Dal 14° livello i risultati
 *  sono due e si sceglie (Caos Controllato). Qui si conferma la richiesta del GM e si leggono gli esiti. */
export default function WildMagicSheet({ char, onClose }: { char: CharacterFull; onClose: () => void }) {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const lang = i18n.language?.startsWith('en') ? 'en' : 'it'
  const [asked, setAsked] = useState(false)
  const [result, setResult] = useState<WildSurgeResult | null>(null)
  // Onde di Caos spesa: il GM può far tirare la tabella senza il d20 e l'uso torna.
  const tides = (char.abilities ?? []).find((a) => a.feature_key === TIDES)
  const tidesSpent = !!tides && tides.max_uses != null && (tides.uses ?? 0) < tides.max_uses
  // Impulso 01-02 in corso: a ogni turno si tira la tabella senza d20.
  const repeating = (char.active_states ?? []).some((s) => s.key === 'wild_repeat')

  const done = (res: WildSurgeResult) => {
    setResult(res)
    qc.invalidateQueries({ queryKey: ['character', char.id] })
    qc.invalidateQueries({ queryKey: ['turn-state', char.id] })
  }
  const fail = (err: unknown) => {
    const code = err instanceof ApiError ? (err.detail as { code?: string } | null)?.code : undefined
    toast.error(t(`character.turn.wild.errors.${code && ERRORS.includes(code) ? code : 'default'}`))
    qc.invalidateQueries({ queryKey: ['character', char.id] })
  }
  const surge = useMutation({
    mutationFn: (mode: 'd20' | 'tides' | 'repeat') =>
      api.characters.wildMagicSurge(char.id, mode === 'repeat' ? { repeat: true } : { tides: mode === 'tides' }),
    onSuccess: done, onError: fail,
  })
  const choose = useMutation({ mutationFn: (index: number) => api.characters.wildMagicChoose(char.id, index), onSuccess: done, onError: fail })

  const entryCard = (e: WildSurgeEntry, action?: ReactNode) => (
    <div key={`${e.roll}-${e.lo}`} className="flex flex-col gap-1 rounded-lg border border-dnd-border bg-dnd-surface p-3">
      <p className="font-heading text-sm text-dnd-gold tabular-nums">{t('character.turn.wild.table_roll', { n: e.roll, label: e.label })} · {e.name[lang]}</p>
      <p className="text-sm font-body text-dnd-text">{e.text[lang]}</p>
      {action}
    </div>
  )

  const applied = result?.applied
  const details = applied ? [
    applied.ignored && t('character.turn.wild.ignored'),
    applied.healed > 0 && t('character.turn.wild.healed', { n: applied.healed }),
    applied.slot_level != null && t('character.turn.wild.slot', { n: applied.slot_level }),
    applied.points && t('character.turn.wild.points'),
    applied.extra_action && t('character.turn.wild.action'),
    applied.damage && t('character.turn.wild.damage', { dice: applied.damage.dice, type: t(`character.inventory.damage_types.dmg_${applied.damage.type}`, { defaultValue: applied.damage.type }), rolls: applied.damage.rolls.join(' + '), total: applied.damage.total }),
    applied.extra_roll && t('character.turn.wild.extra_roll', { dice: applied.extra_roll.dice, rolls: applied.extra_roll.rolls.join(' + '), total: applied.extra_roll.total }),
    applied.dc != null && t('character.turn.wild.dc', { n: applied.dc }),
    applied.state?.rounds_left != null && t('character.turn.wild.timer', { n: applied.state.rounds_left }),
    result?.tides_restored && t('character.turn.wild.tides_back'),
  ].filter((x): x is string => !!x) : []

  return (
    <Sheet open onClose={onClose} title={t('character.turn.wild.title')} zClassName="z-[60]">
      <div className="flex flex-col gap-3 px-4 pb-4">
        {!result && (
          <>
            <p className="text-sm font-body text-dnd-text-muted">{t('character.turn.wild.intro')}</p>
            <SwitchToggle label={t('character.turn.wild.confirm')} checked={asked} onChange={setAsked} />
            <Button variant="primary" disabled={!asked} loading={surge.isPending} onClick={() => surge.mutate('d20')}>
              {t('character.turn.wild.roll')}
            </Button>
            {tidesSpent && (
              <Button variant="secondary" loading={surge.isPending} onClick={() => surge.mutate('tides')}>
                {t('character.turn.wild.tides')}
              </Button>
            )}
            {repeating && (
              <Button variant="secondary" loading={surge.isPending} onClick={() => surge.mutate('repeat')}>
                {t('character.turn.wild.repeat')}
              </Button>
            )}
          </>
        )}
        {result && !result.triggered && (
          <p className="text-sm font-body text-dnd-text tabular-nums">{t('character.turn.wild.no_surge', { n: result.die })}</p>
        )}
        {result?.pending && (
          <>
            <p className="text-sm font-body text-dnd-text">{t('character.turn.wild.choose_title')}</p>
            {result.options.map((e, index) => entryCard(e, (
              <Button variant="primary" loading={choose.isPending} onClick={() => choose.mutate(index)}>{t('character.turn.wild.choose')}</Button>
            )))}
          </>
        )}
        {applied && (
          <>
            {entryCard(applied)}
            {details.length > 0 && (
              <ul className="flex flex-col gap-1 text-sm font-body text-dnd-text tabular-nums">
                {details.map((d) => <li key={d}>{d}</li>)}
              </ul>
            )}
          </>
        )}
        {result && <Button variant="secondary" onClick={onClose}>{t('character.turn.wild.close')}</Button>}
      </div>
    </Sheet>
  )
}

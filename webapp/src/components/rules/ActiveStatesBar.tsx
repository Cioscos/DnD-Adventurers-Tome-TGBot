import { useTranslation } from 'react-i18next'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { GiLightningTrio } from 'react-icons/gi'
import { api } from '@/api/client'
import Button from '@/components/ui/Button'
import { notifyMutationError } from '@/lib/mutationError'
import type { CharacterFull } from '@/types'

/** Stati attivi dei privilegi (Ira...) con i round rimasti e la chiusura a mano. Niente se non ce n'è nessuno. */
export default function ActiveStatesBar({ char }: { char: CharacterFull }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const end = useMutation({
    mutationFn: (key: string) => api.characters.endActiveState(char.id, key),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['character', char.id] }),
    onError: () => notifyMutationError(),
  })
  const states = char.active_states ?? []
  if (states.length === 0) return null
  return (
    <ul className="mt-3 flex flex-col gap-2">
      {states.map((s) => {
        const name = char.abilities.find((a) => a.feature_key === s.feature_key)?.name ?? s.key
        return (
          <li key={s.key} className="flex items-center gap-2 px-3 py-2 rounded-xl border border-dnd-gold-dim/50 bg-dnd-gold/10">
            <GiLightningTrio size={16} aria-hidden className="shrink-0 text-dnd-gold-bright" />
            <p className="flex-1 min-w-0 text-sm font-body text-dnd-text break-words">
              {name}
              {s.rounds_left != null && (
                <span className="ml-2 text-dnd-text-muted tabular-nums">{t('character.turn.state_rounds_left', { n: s.rounds_left })}</span>
              )}
            </p>
            <Button size="sm" variant="secondary" className="min-h-11 shrink-0"
              loading={end.isPending && end.variables === s.key} onClick={() => end.mutate(s.key)}>
              {t('character.turn.end_state')}
            </Button>
          </li>
        )
      })}
    </ul>
  )
}

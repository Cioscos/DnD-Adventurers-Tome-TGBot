import { useTranslation } from 'react-i18next'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { GiLightningTrio } from 'react-icons/gi'
import { api } from '@/api/client'
import Button from '@/components/ui/Button'
import { notifyMutationError } from '@/lib/mutationError'
import { useToast } from '@/hooks/useToast'
import type { CharacterFull } from '@/types'

/** Stati attivi dei privilegi (Ira...) con i round rimasti e la chiusura a mano. Niente se non ce n'è nessuno. */
export default function ActiveStatesBar({ char }: { char: CharacterFull }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const end = useMutation({
    mutationFn: (key: string) => api.characters.endActiveState(char.id, key),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['character', char.id] }),
    onError: () => notifyMutationError(),
  })
  // Dado di Ispirazione in Combattimento alla CA: in reazione, il valore da sommare lo dice il server.
  const acBoost = useMutation({
    mutationFn: () => api.characters.bardicDieAc(char.id),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['character', char.id] })
      qc.invalidateQueries({ queryKey: ['turn-state', char.id] })
      toast.info(t('character.turn.bardic_die_ac_result'), { description: `+${res.roll}` })
    },
    onError: () => notifyMutationError(),
  })
  // I segni interni di un privilegio (il Canto di Riposo già ricevuto) non sono del giocatore: né si vedono né si chiudono.
  const states = (char.active_states ?? []).filter((s) => !s.data?.internal)
  if (states.length === 0) return null
  return (
    <ul className="mt-3 flex flex-col gap-2">
      {states.map((s) => {
        // Il dado ricevuto non ha una riga sulla scheda di chi lo riceve: il nome salvato è nella lingua del bardo, si traduce qui.
        const name = s.key === 'bardic_die' ? t('character.turn.bardic_die_name')
          : char.abilities.find((a) => a.feature_key === s.feature_key)?.name ?? s.name ?? t('character.turn.state_generic')
        // Privilegi che agiscono su altri (Lupo, Orso, Attacco Irruento): il testo sta sotto lo stato, il GM li applica (D1).
        const others = ((s.data?.others as string[] | undefined) ?? [])
          .map((k) => char.abilities.find((a) => a.feature_key === k))
          .filter((a): a is NonNullable<typeof a> => !!a)
        return (
          <li key={s.key} className="flex flex-wrap items-center gap-2 px-3 py-2 rounded-xl border border-dnd-gold-dim/50 bg-dnd-gold/10">
            <GiLightningTrio size={16} aria-hidden className="shrink-0 text-dnd-gold-bright" />
            <div className="flex-1 min-w-[9rem] text-sm font-body text-dnd-text break-words">
              <p>
                {name}
                {typeof s.data?.die === 'number' && (
                  <span className="ml-2 font-mono text-dnd-text-muted">d{s.data.die}</span>
                )}
                {s.rounds_left != null && (
                  <span className="ml-2 text-dnd-text-muted tabular-nums">{t('character.turn.state_rounds_left', { n: s.rounds_left })}</span>
                )}
              </p>
              {others.map((a) => (
                <p key={a.id} className="mt-0.5 text-xs text-dnd-text-muted">{a.name}: {a.description}</p>
              ))}
            </div>
            {s.key === 'bardic_die' && s.data?.combat === true && (
              <Button size="sm" variant="secondary" className="min-h-11 shrink-0"
                loading={acBoost.isPending} onClick={() => acBoost.mutate()}>
                {t('character.turn.bardic_die_ac')}
              </Button>
            )}
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

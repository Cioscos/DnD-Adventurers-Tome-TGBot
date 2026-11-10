import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import SwitchToggle from '@/components/ui/SwitchToggle'
import { notifyMutationError } from '@/lib/mutationError'
import type { CharacterFull } from '@/types'

/** Canto di Riposo (Bardo 2014) nel foglio del riposo breve: il bardo lo accende qui, dove decide di esibirsi. Lo stato dura
 *  oltre il suo riposo (chi spende Dadi Vita dopo di lui riceve il dado) fino al riposo lungo, a un nuovo turno o a mano. */
export default function SongOfRestToggle({ char }: { char: CharacterFull }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const mutation = useMutation({
    mutationFn: async (on: boolean) => {
      if (on) await api.characters.featureUse(char.id, 'bard.song_of_rest')
      else await api.characters.endActiveState(char.id, 'song_of_rest')
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['character', char.id] }); qc.invalidateQueries({ queryKey: ['turn-state', char.id] }) },
    onError: () => notifyMutationError(),
  })
  const available = char.rules_edition !== '2024'
    && (char.abilities ?? []).some((a) => a.feature_key === 'bard.song_of_rest' && a.has_on_use)
  if (!available) return null
  return (
    <div className="text-left">
      <SwitchToggle
        checked={(char.active_states ?? []).some((s) => s.key === 'song_of_rest')}
        onChange={(on) => mutation.mutate(on)}
        label={t('character.quick_actions.song_of_rest')}
        hint={t('character.quick_actions.song_of_rest_hint')}
      />
    </div>
  )
}

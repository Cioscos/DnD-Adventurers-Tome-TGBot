import type { QueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { create } from 'zustand'
import { api } from '@/api/client'
import i18n from '@/i18n'
import type { OptionResult, RollChoice, RollOption, RollOptionPhase, RollOptionsQuery } from '@/api/client'

export type PromptContext = {
  /** Esito del tiro per colpire, mostrato in alto dopo il d20. */
  summary?: string
  canReroll?: boolean
}

export type PromptRequest = {
  options: RollOption[]
  phase: RollOptionPhase
  context?: PromptContext
  answer: (answer: RollChoice) => void
}

export const usePromptStore = create<{ request: PromptRequest | null }>(() => ({ request: null }))

async function listOptions(charId: number, query: RollOptionsQuery): Promise<RollOption[]> {
  try {
    return (await api.characters.rollOptions(charId, query)) ?? []
  } catch (err) {
    // Il tiro resta possibile senza opzioni. Il 403 è il GM su un PG altrui: lì non c'è nulla da confermare.
    const status = (err as { status?: number }).status
    if (status !== undefined && status !== 403) toast.warning(i18n.t('character.roll_options.list_failed'))
    return []
  }
}

/** Serve al rilancio: sapere se il danno dovrà aspettare, senza aprire il prompt. */
export async function hasAfterHitOptions(charId: number, query: RollOptionsQuery): Promise<boolean> {
  return (await listOptions(charId, query)).some((o) => o.phase === 'after_hit')
}

/** Chiede al giocatore le opzioni del tiro. Senza opzioni per questa fase risponde subito, senza prompt. */
export async function askRollOptions(
  charId: number, query: RollOptionsQuery, phase: RollOptionPhase = 'before', context?: PromptContext,
): Promise<RollChoice> {
  const listed = await listOptions(charId, query)
  const defer = phase === 'before' && query.roll === 'attack' && query.spell_id === undefined
    && listed.some((o) => o.phase === 'after_hit')
  const base: RollChoice = { options: [], option_inputs: {}, ...(defer ? { defer_damage: true } : {}) }
  const inPhase = listed.filter((o) => o.phase === phase)
  // `needs` di un'altra fase: il server lo azzera se è già confermata, altrimenti l'opzione non si può scegliere.
  const options = inPhase.filter((o) => !o.needs || inPhase.some((p) => p.key === o.needs))
  if (options.length === 0) return base
  return new Promise((resolve) => {
    usePromptStore.setState({
      request: {
        options, phase, context,
        answer: (answer) => {
          usePromptStore.setState({ request: null })
          resolve({ ...answer, ...(defer ? { defer_damage: true } : {}) })
        },
      },
    })
  })
}

/** Dopo un tiro con opzioni: usi, slot e turno sono cambiati sul server. */
export function refreshAfterOptions(qc: QueryClient, charId: number, result?: OptionResult | null): void {
  if (!result) return
  qc.invalidateQueries({ queryKey: ['character', charId] })
  qc.invalidateQueries({ queryKey: ['turn-state', charId] })
}

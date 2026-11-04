import type { QueryClient } from '@tanstack/react-query'
import { create } from 'zustand'
import { api } from '@/api/client'
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

/** Chiede al giocatore le opzioni del tiro. Senza opzioni per questa fase risponde subito, senza prompt. */
export async function askRollOptions(
  charId: number, query: RollOptionsQuery, phase: RollOptionPhase = 'before', context?: PromptContext,
): Promise<RollChoice> {
  let listed: RollOption[] = []
  try {
    listed = (await api.characters.rollOptions(charId, query)) ?? []
  } catch {
    // Elenco non arrivato: il tiro resta possibile, senza opzioni da scegliere.
  }
  const defer = phase === 'before' && query.roll === 'attack' && query.spell_id === undefined
    && listed.some((o) => o.phase === 'after_hit')
  const base: RollChoice = { options: [], option_inputs: {}, ...(defer ? { defer_damage: true } : {}) }
  const options = listed.filter((o) => o.phase === phase)
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

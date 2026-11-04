import type { QueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { create } from 'zustand'
import { api } from '@/api/client'
import i18n from '@/i18n'
import type { TFunction } from 'i18next'
import type { LastRollResult, OptionResult, RollChoice, RollMode, RollOption, RollOptionPhase, RollOptionsQuery } from '@/api/client'

type PromptPhase = Exclude<RollOptionPhase, 'after_roll'>

export type PromptContext = {
  /** Esito del tiro per colpire, mostrato in alto dopo il d20. */
  summary?: string
  canReroll?: boolean
  /** 1 naturale: si offre solo ciò che può cambiarlo. */
  fumble?: boolean
}

export type PromptRequest = {
  options: RollOption[]
  /** Dopo il tiro per colpire: agiscono subito sul d20 già visto, prima del danno. */
  afterRoll: RollOption[]
  phase: PromptPhase
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

const defersDamage = (options: RollOption[]) => options.some((o) => o.phase === 'after_hit' || o.phase === 'after_roll')

/** Serve al rilancio: sapere se il danno dovrà aspettare, senza aprire il prompt. */
export async function hasDeferringOptions(charId: number, query: RollOptionsQuery): Promise<boolean> {
  return defersDamage(await listOptions(charId, query))
}

/** Costi ed effetti di un'opzione, per le righe e i pulsanti. */
export function optionHints(option: RollOption, t: TFunction): string[] {
  return [
    option.dice,
    option.bonus ? `${option.bonus > 0 ? '+' : ''}${option.bonus}` : null,
    option.mode ? t(`common.roll_mode.${option.mode}`) : null,
    option.auto_fail ? t('character.roll_notes.auto_fail') : null,
    option.multiplier !== null ? `×${option.multiplier}` : null,
    option.slot ? t(`character.roll_options.slot_${option.slot}`) : null,
    option.once_per_turn ? t('character.roll_options.once_per_turn') : null,
    option.cost?.feature_key ? t('character.roll_options.uses', { count: option.cost.amount }) : null,
    option.dice_cost ? t('character.roll_options.dice_cost', { count: option.dice_cost }) : null,
  ].filter((hint): hint is string => !!hint)
}

/** Usa un privilegio sul tiro già visto; un ritiro anima il nuovo d20. */
export async function applyAfterRoll(
  charId: number, option: RollOption, rollD20: (mode: RollMode) => Promise<number[] | undefined>,
): Promise<LastRollResult> {
  const mode = option.mode ?? 'normal'
  const dice = option.after === 'reroll' ? await rollD20(mode) : undefined
  return api.characters.lastRollOptions(charId, { options: [option.key], option_inputs: {}, mode, dice })
}

/** Chiede al giocatore le opzioni del tiro. Senza opzioni per questa fase risponde subito, senza prompt. */
export async function askRollOptions(
  charId: number, query: RollOptionsQuery, phase: PromptPhase = 'before', context?: PromptContext,
): Promise<RollChoice> {
  const listed = await listOptions(charId, query)
  const defer = phase === 'before' && query.roll === 'attack' && query.spell_id === undefined
    && defersDamage(listed)
  const base: RollChoice = { options: [], option_inputs: {}, ...(defer ? { defer_damage: true } : {}) }
  const inPhase = context?.fumble ? [] : listed.filter((o) => o.phase === phase)
  // `needs` di un'altra fase: il server lo azzera se è già confermata, altrimenti l'opzione non si può scegliere.
  const options = inPhase.filter((o) => !o.needs || inPhase.some((p) => p.key === o.needs))
  // Su un 1 naturale una somma non basta: resta mancato.
  const afterRoll = phase === 'after_hit'
    ? listed.filter((o) => o.phase === 'after_roll' && !o.needs && !(context?.fumble && o.after === 'add'))
    : []
  if (options.length === 0 && afterRoll.length === 0) return base
  return new Promise((resolve) => {
    usePromptStore.setState({
      request: {
        options, afterRoll, phase, context,
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

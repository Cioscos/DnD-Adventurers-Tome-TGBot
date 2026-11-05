import type { QueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { create } from 'zustand'
import { api } from '@/api/client'
import i18n from '@/i18n'
import type { TFunction } from 'i18next'
import type { LastRollResult, OptionResult, RollChoice, RollMode, RollOption, RollOptionPhase, RollOptionsQuery, SpellUseBody } from '@/api/client'
import type { CharacterFull } from '@/types'

type PromptPhase = Exclude<RollOptionPhase, 'after_roll' | 'after_damage'>

export type PromptContext = {
  /** Esito del tiro per colpire, mostrato in alto dopo il d20. */
  summary?: string
  canReroll?: boolean
  /** 1 naturale: si offre solo ciò che può cambiarlo. */
  fumble?: boolean
  /** Opzioni dopo il tiro già usate su questo tiro: non si offrono più. */
  used?: string[]
  /** Il prompt resta aperto anche senza opzioni: il giocatore deve poter dichiarare il mancato. */
  keepOpen?: boolean
  /** Opzioni del lancio, non di un tiro: cambiano titolo e pulsante. */
  cast?: boolean
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

export const useAttackLimitStore = create<{ request: { made: number; allowed: number; answer: (go: boolean) => void } | null }>(
  () => ({ request: null }),
)

/** Il limite dell'azione Attacco si supera solo confermando: chi ha privilegi in più non va impedito. */
export function askAttackLimit(made: number, allowed: number): Promise<boolean> {
  return new Promise((resolve) => {
    useAttackLimitStore.setState({
      request: { made, allowed, answer: (go) => { useAttackLimitStore.setState({ request: null }); resolve(go) } },
    })
  })
}

export const useCastConfirmStore = create<{ request: { code: string; answer: (go: boolean) => void } | null }>(
  () => ({ request: null }),
)

/** Il giocatore ha rifiutato una conferma: nessun lancio e nessun errore da mostrare. */
export class CastCancelled extends Error {}

function askCastConfirm(code: string): Promise<boolean> {
  return new Promise((resolve) => {
    useCastConfirmStore.setState({
      request: { code, answer: (go) => { useCastConfirmStore.setState({ request: null }); resolve(go) } },
    })
  })
}

async function castWarnings(charId: number, spellId: number, ritual: boolean): Promise<string[]> {
  try {
    return (await api.spells.castCheck(charId, spellId, ritual)) ?? []
  } catch {
    return []  // il lancio ricontrolla sul server
  }
}

/** Prima dei dadi: conferme delle regole violate, poi opzioni del lancio. `CastCancelled` se il giocatore rinuncia. */
export async function prepareCast(charId: number, spellId: number, ritual: boolean) {
  const confirm = await castWarnings(charId, spellId, ritual)
  for (const code of confirm) {
    if (!(await askCastConfirm(code))) throw new CastCancelled()
  }
  const choice = await askRollOptions(charId, { roll: 'cast', spell_id: spellId }, 'before', { cast: true })
  return { confirm, options: choice.options, option_inputs: choice.option_inputs }
}

/** Il lancio senza tiro per colpire: `/use`. */
export async function castSpell(charId: number, spellId: number, body: SpellUseBody): Promise<CharacterFull> {
  return api.spells.use(charId, spellId, { ...body, ...(await prepareCast(charId, spellId, !!body.as_ritual)) })
}

/** Il rilancio è del 2024: nel 2014 l'Ispirazione si spende prima del tiro, come opzione. */
export const canRerollInspiration = (char?: { heroic_inspiration?: boolean; rules_edition?: string } | null): boolean =>
  !!char?.heroic_inspiration && char.rules_edition === '2024'

/** Quante domande «Il tiro è riuscito?» sono aperte nei modali di esito. */
export const useRefundStore = create<{ inline: number }>(() => ({ inline: 0 }))

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
    ? listed.filter((o) => o.phase === 'after_roll' && !o.needs && !context?.used?.includes(o.key)
        && !(context?.fumble && o.after === 'add'))
    : []
  if (options.length === 0 && afterRoll.length === 0 && !context?.keepOpen) return base
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

/** Facce di un dado dal tipo `d8` -> 8 (`main_kind` del danno). */
export const sidesOf = (kind: string | null | undefined): number => Number((kind ?? '').slice(1))

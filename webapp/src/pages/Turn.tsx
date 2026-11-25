import { uiLang } from '@/lib/lang'
import { concentrationLabel } from '@/lib/concentration'
import { askRollOptions, refreshAfterOptions, rolledText } from '@/lib/rollOptions'
import { useState, type ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Check, ChevronRight, Clock, RotateCcw, Sparkles, Target } from 'lucide-react'
import { api, ApiError, type RollMode } from '@/api/client'
import { isUnlimitedFeature } from '@/lib/abilityUses'
import Layout from '@/components/Layout'
import Button from '@/components/ui/Button'
import { formatCondition, incapacitatedMessageKey } from '@/lib/conditions'
import ConditionBadge from '@/components/ui/ConditionBadge'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import { turnLeftovers } from '@/lib/turnLeftovers'
import Input from '@/components/ui/Input'
import ExpandChevron from '@/components/ui/ExpandChevron'
import Pressable from '@/components/ui/Pressable'
import RollButton from '@/components/ui/RollButton'
import ActiveStatesBar from '@/components/rules/ActiveStatesBar'
import TargetEffectSheet from '@/components/rules/TargetEffectSheet'
import AllyTargetSheet from '@/components/rules/AllyTargetSheet'
import PreserveLifeSheet from '@/components/rules/PreserveLifeSheet'
import WeaponBondSheet from '@/components/rules/WeaponBondSheet'
import WildMagicSheet from '@/components/rules/WildMagicSheet'
import AmountStepper from '@/components/rules/AmountStepper'
import SwitchToggle from '@/components/ui/SwitchToggle'
import SelectSheet from '@/components/ui/SelectSheet'
import GiveInspirationRow from '@/components/character/GiveInspirationRow'
import BeastOrders from '@/components/character/BeastOrders'
import WeaponChoiceRow from '@/components/WeaponChoiceRow'
import EquipItemPicker from '@/components/character/EquipItemPicker'
import WeaponPreviewLine from '@/components/character/WeaponPreviewLine'
import ActionsSkeleton from '@/components/skeletons/ActionsSkeleton'
import { useWeaponAttackFlow } from '@/hooks/useWeaponAttackFlow'
import { useTickRound } from '@/hooks/useTickRound'
import { useTurnState } from '@/hooks/useTurnState'
import { useToast } from '@/hooks/useToast'
import { useCastFlow } from '@/pages/spells/useCastFlow'
import { useWeaponChoices, choiceOf } from '@/store/weaponChoiceStore'
import { groupForTurn, type TurnEntry } from '@/lib/turnGrouping'
import { standardActionsFor } from '@/data/standardActions'
import RollResultModal, { type RollResult } from '@/components/RollResultModal'
import { useD20Roll, d20Arg } from '@/hooks/useD20Roll'
import type { Ability, TurnBlock, TurnSlot, TurnState } from '@/types'
import { LEDGER_TITLE } from '@/styles/ledger'
import type { CharacterFull } from '@/types'

type Bucket = 'action' | 'bonus_action' | 'reaction'
const BUCKETS: Bucket[] = ['action', 'bonus_action', 'reaction']
const SLOT_OF: Record<Bucket, TurnSlot> = { action: 'action', bonus_action: 'bonus', reaction: 'reaction' }
/** Codici con un testo proprio quando un privilegio non si può usare (`POST /features/{key}/use`). */
const ABILITY_USE_ERRORS = ['turn_slot_used', 'no_uses', 'feature_not_usable', 'amount_too_high', 'feature_unavailable', 'once_per_turn', 'no_attack_left', 'amount_too_low', 'amount_invalid', 'no_slot', 'insufficient_funds', 'invalid_text', 'identity_exists', 'already_moved', 'invalid_choice', 'already_chosen', 'no_benefit', 'already_used_this_rage', 'invalid_target', 'target_dead', 'target_not_down', 'nothing_to_remove', 'beast_alive']
/** Esiti di un privilegio che il server manda come chiavi (`FeatureUseResult.notes`) e la pagina traduce. */
const USE_NOTES = ['amount_capped', 'arcane_charge','quivering_palm', 'water_whip', 'fist_of_unbroken_air', 'lay_on_hands_other', 'lay_on_hands_cure_self', 'lay_on_hands_cure_other', 'lay_on_hands_other_2024', 'lay_on_hands_cure_self_2024', 'lay_on_hands_cure_other_2024', 'revivification_other', 'gift_of_the_protectors_other', 'primeval_awareness', 'vanish_hide',
  'cunning_dash', 'cunning_disengage', 'cunning_hide', 'cunning_sleight_of_hand', 'cunning_thieves_tools', 'cunning_use_object', 'steady_aim', 'steady_aim_keeps_speed', 'mage_hand_control', 'bend_luck_plus', 'bend_luck_minus', 'healer_other']
const BTN = 'flex items-center gap-1 text-sm font-medium px-4 h-11 rounded-lg border active:scale-95 transition-transform'

export default function Turn() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const [skillRoll, setSkillRoll] = useState<{ result: RollResult; skill: string } | null>(null)
  const [otherOpen, setOtherOpen] = useState(false)
  const [weaponPicker, setWeaponPicker] = useState(false)
  const [openStandard, setOpenStandard] = useState<Record<string, boolean>>({})
  // Influenzare 2024: CD scelta dal giocatore (15 di base) e totale dell'ultima prova, per mostrare l'esito.
  const [influenceDc, setInfluenceDc] = useState('15')
  const [influenceRolled, setInfluenceRolled] = useState(false)
  // Usi da spendere per i privilegi a pool (per id della riga); senza scelta si spende 1.
  const [amounts, setAmounts] = useState<Record<number, number>>({})
  // Scelte sì/no all'uso di un privilegio (Frenesia), per riga di privilegio.
  const [toggles, setToggles] = useState<Record<number, Record<string, boolean>>>({})
  const [panel, setPanel] = useState<Ability | null>(null)
  const [useChoices, setUseChoices] = useState<Record<number, Record<string, string>>>({})
  // Testi liberi all'uso di un privilegio (il nome di un'identità falsa, di un incantesimo rubato), per riga di privilegio.
  const [useTexts, setUseTexts] = useState<Record<number, Record<string, string>>>({})
  // Effetto su altri di un privilegio appena usato (Presenza Intimidatoria): il giocatore sceglie su chi applicarlo.
  const [targetKey, setTargetKey] = useState<string | null>(null)
  // Privilegio che dà lo stato a un alleato della serata (Ispirazione Bardica): prima si sceglie a chi (R38).
  // Privilegio che toglie condizioni (Task 48): lo stesso foglio degli incantesimi, aperto dall'uso
  const [removalPick, setRemovalPick] = useState<{ ability: Ability; uses: number; amount?: number; allies: { id: number; name: string }[] } | null>(null)
  const [allyPick, setAllyPick] = useState<{ ability: Ability; uses: number; amount?: number; allies: { id: number; name: string }[]; max: number } | null>(null)
  const choices = useWeaponChoices((s) => s.choices)
  const setChoice = useWeaponChoices((s) => s.setChoice)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })
  const { data: session } = useQuery({ queryKey: ['session-me'], queryFn: () => api.sessions.me() })
  const { data: turn } = useTurnState(charId, true, session?.status === 'active')

  // Lo stato del turno vive sul server: sopravvive a ricarica e cambio pagina.
  const block = turn?.turn
  // Un'azione in più (Azione Impetuosa) riapre la sezione dell'azione anche se quella normale è già spesa.
  const extraActions = block?.extra_actions ?? 0
  // LA4b: l'azione Attacco già iniziata è l'azione del turno (gli attacchi restano nella loro sezione)
  const used: Record<Bucket, boolean> = {
    action: (!!block?.action_used || (block?.action_attacks ?? 0) > 0) && extraActions === 0,
    bonus_action: !!block?.bonus_used, reaction: !!block?.reaction_used,
  }
  const setBlock = (b: TurnBlock) =>
    qc.setQueryData(['turn-state', charId], (old: TurnState | undefined) => old && { ...old, turn: b })
  const useSlot = useMutation({
    mutationFn: ({ slot, on = true }: { slot: TurnSlot; on?: boolean }) => api.characters.turnUse(charId, slot, on),
    onSuccess: (b) => { setBlock(b); qc.invalidateQueries({ queryKey: ['turn-state', charId] }) }, // spendere l'azione extra cambia il limite di attacchi
    onError: () => qc.invalidateQueries({ queryKey: ['turn-state', charId] }),
  })
  const newTurn = useMutation({
    mutationFn: () => api.characters.turnNew(charId),
    // L'inizio del turno può curare (Sopravvissuto) e dare un'azione extra (Velocità): PF e limite di attacchi si rileggono.
    onSuccess: (b) => { setBlock(b); qc.invalidateQueries({ queryKey: ['character', charId] }); qc.invalidateQueries({ queryKey: ['turn-state', charId] }) },
  })
  const setProne = useMutation({
    mutationFn: (prone: boolean) => api.characters.updateConditions(charId, { prone }),
    onSuccess: (updated) => qc.setQueryData(['character', charId], updated),
  })
  const hide = useMutation({
    mutationFn: () => api.characters.hide(charId),
    onSuccess: (updated) => { qc.setQueryData(['character', charId], updated); qc.invalidateQueries({ queryKey: ['turn-state', charId] }) },
  })
  const otherTurn = useMutation({ mutationFn: () => api.characters.turnOther(charId), onSuccess: setBlock })
  // MA2: «Termina turno» come nel Combattimento; i TS di fine turno li apre il banner della pagina
  const [leftover, setLeftover] = useState<string | null>(null)
  const endTurn = useMutation({
    mutationFn: (sessionId: number) => api.sessions.encounter.nextTurn(sessionId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['turn-state', charId] })  // porta anche i TS nati a fine turno (banner)
      qc.invalidateQueries({ queryKey: ['session-live'] })
    },
    onError: (err) => {
      qc.invalidateQueries({ queryKey: ['turn-state', charId] })
      if (err instanceof ApiError && err.status === 403) toast.info(t('session.combat.turn_already_advanced'))
      else toast.error(t('session.combat.action_failed'))
    },
  })
  const rollD20 = useD20Roll()
  const skillMutation = useMutation({
    mutationFn: async ({ skill, mode }: { skill: string; mode: RollMode; spendsAttack?: boolean; influence?: boolean }) => {
      const choice = await askRollOptions(charId, { roll: 'skill', skill })
      return { result: await api.characters.rollSkill(charId, skill, d20Arg(mode, await rollD20(mode, choice), choice)), skill }
    },
    onSuccess: ({ result, skill }, { spendsAttack, influence }) => {
      if (spendsAttack) useSlot.mutate({ slot: 'attack' })
      setInfluenceRolled(!!influence)  // un'altra prova non lascia l'esito di Influenzare sul tiro nuovo
      // Nascondersi legge il totale dal tiro salvato dal server: il turno lo riporta.
      qc.invalidateQueries({ queryKey: ['turn-state', charId] })
      refreshAfterOptions(qc, charId, result.option_result)
      setSkillRoll({ result: { ...result, description: undefined }, skill })
    },
  })

  const weaponFlow = useWeaponAttackFlow(charId, char)
  const castFlow = useCastFlow(charId, char)
  const tick = useTickRound(charId)

  // Un privilegio con effetto reale passa dal server (usi, slot di turno, cura, stato); gli altri scalano solo il contatore.
  const abilityUse = useMutation({
    mutationFn: async ({ ability, uses, amount, allyId, allyIds, removal }: { ability: Ability; uses: number; amount?: number; allyId?: number; allyIds?: number[]; removal?: { targets: (number | string)[]; conditions?: string[] } }) => {
      if (ability.has_on_use && ability.feature_key) {
        const chosen = toggles[ability.id]
        const picked = useChoices[ability.id]
        const typed = useTexts[ability.id]
        const choices = ability.use_toggles?.length || ability.use_choices?.length || ability.use_texts?.length ? {
          ...Object.fromEntries((ability.use_toggles ?? []).map((x) => [x.key, !!chosen?.[x.key]])),
          ...Object.fromEntries((ability.use_choices ?? []).map((x) => [x.key, picked?.[x.key]]).filter(([, v]) => v)),
          ...Object.fromEntries((ability.use_texts ?? []).map((x) => [x.key, typed?.[x.key]?.trim()]).filter(([, v]) => v)),
        } : undefined
        // Il bersaglio scelto viaggia con le scelte già fatte (Imposizione delle Mani: la modalità decide cosa farne).
        const chosenTarget = allyIds !== undefined ? { ...choices, target_character_ids: allyIds }
          : allyId !== undefined ? { ...choices, target_character_id: allyId } : choices
        // Togliere condizioni: lo stesso corpo `removal` degli incantesimi (il server ricava costo e bersaglio dei PF)
        const params = removal ? { ...chosenTarget, removal } : chosenTarget
        if (params) return api.characters.featureUse(charId, ability.feature_key, amount ?? 1, params)
        if (amount) return api.characters.featureUse(charId, ability.feature_key, amount)
        return api.characters.featureUse(charId, ability.feature_key)
      }
      await api.abilities.update(charId, ability.id, { uses })
      return null
    },
    onSuccess: (res, { ability }) => {
      // Le scelte valgono per un uso solo: il prossimo riparte vuoto, senza riproporre una condizione già curata.
      setUseChoices((s) => Object.fromEntries(Object.entries(s).filter(([id]) => Number(id) !== ability.id)))
      setUseTexts((s) => Object.fromEntries(Object.entries(s).filter(([id]) => Number(id) !== ability.id)))
      if (res?.targets?.length) setTargetKey(res.targets[0])
      // All'alleato solo quanto ha recuperato (i suoi PF restano privati); su di sé anche i PF risultanti.
      if (res?.received) toast.info(t('character.turn.use_received', { name: res.received.name, n: res.received.healed }))
      if (res?.healed && char) {
        const max = char.computed?.hp_max_effective ?? char.hit_points + (char.hp_max_homebrew_modifier ?? 0)
        toast.info(t('character.turn.use_healed_self', { n: res.healed, hp: Math.min(max, char.current_hit_points + res.healed), max }))
      }
      // Il dado tirato dal privilegio (Parole Taglienti: il valore da sottrarre al tiro dell'altro) si dice subito.
      if (res?.rolls?.length) toast.info(t('character.turn.use_rolled'), { description: rolledText(res.rolls, res.flat ?? 0) })
      // Un valore per un altro (PF temporanei di Incoraggiamento, dado del Colpo del Comandante) e gli esiti in chiave.
      if (res?.given != null) toast.info(t('character.turn.use_given', { n: res.given }))
      for (const r of res?.temp_received ?? []) {  // PF temporanei consegnati: il server dice se sono saliti o se l'altro ne aveva già di più
        toast.info(t(r.applied ? 'character.turn.use_temp_received' : 'character.turn.use_temp_kept', { name: r.name, n: r.given, have: r.temp_hp }))
      }
      if (res?.temp_hp != null) toast.info(t('character.turn.use_temp_hp', { n: res.temp_hp }))
      if (res?.attack) toast.info(t('character.turn.use_attack', { die: res.attack.die, bonus: `${res.attack.bonus >= 0 ? '+' : ''}${res.attack.bonus}`, total: res.attack.total }), { description: res.attack.is_fumble ? t('character.dice.fumble_banner') : res.attack.is_critical ? t('character.dice.critical_banner') : undefined })
      if (res?.message) toast.info(res.message[uiLang(i18n.language)])
      for (const line of res?.removal ?? []) toast.info(line[uiLang(i18n.language)])
      for (const note of res?.notes ?? []) if (USE_NOTES.includes(note)) toast.info(t(`character.turn.use_notes.${note}`))
      // U39: Nascondersi con l'Azione Scaltra tira subito Furtività; l'esito (2024: Invisibile) si conferma da «Nascondersi»
      if (res?.notes?.includes('cunning_hide')) skillMutation.mutate({ skill: 'stealth', mode: 'normal' })
    },
    // Il server rifiuta ciò che la pagina non aveva ancora visto (slot già speso, usi finiti): si dice, mai il messaggio tecnico.
    onError: (err) => {
      // Il codice sta in `detail.code`; l'oro che manca arriva come testo semplice (`insufficient_funds`).
      const detail = err instanceof ApiError ? err.detail : undefined
      const code = typeof detail === 'string' ? detail : (detail as { code?: string } | null)?.code
      toast.error(t(`character.turn.use_errors.${code && ABILITY_USE_ERRORS.includes(code) ? code : 'default'}`))
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      qc.invalidateQueries({ queryKey: ['turn-state', charId] })
      qc.invalidateQueries({ queryKey: ['companions', charId] })  // Compagno Primordiale crea o rialza la bestia
      setAllyPick(null)
      setRemovalPick(null)
    },
  })
  /** La modalità scelta è rivolta a un altro: il pulsante dice «Usa su…», il passo dopo è la scelta del bersaglio. */
  const usesOnAlly = (ab: Ability) => {
    const mode = useChoices[ab.id]?.mode
    return !!ab.gives_to_ally || !!(mode && ab.ally_modes?.includes(mode))
  }
  /** «Usa» di un privilegio: se dà lo stato a un alleato e alla serata siede qualcun altro, prima chiede a chi. */
  const triggerAbility = async (args: { ability: Ability; uses: number; amount?: number }) => {
    if (args.ability.use_panel === 'preserve_life' || args.ability.use_panel === 'weapon_bond' || args.ability.use_panel === 'wild_magic') {
      setPanel(args.ability)
      return
    }
    // Un privilegio che dà un effetto a un alleato, o una cui modalità scelta è rivolta a un altro (Imposizione delle Mani).
    const mode = useChoices[args.ability.id]?.mode
    const rm = args.ability.removal
    // La cura può anche togliere condizioni (Imposizione delle Mani 2024): su di sé si chiede solo se c'è qualcosa da togliere.
    const also = !!rm?.also_modes?.includes(mode ?? '') && (mode !== 'self' || rm.conditions.some((c) => char?.conditions?.[c.key]))
    if (rm && (!rm.modes || also || (mode && rm.modes.includes(mode)))) {
      const allies = rm.ally && !((rm.bound || also) && mode === 'self') ? await api.characters.sessionAllies(charId).catch(() => []) : []
      setRemovalPick({ ...args, allies })
      return
    }
    if (args.ability.gives_to_ally || (mode && args.ability.ally_modes?.includes(mode))) {
      const allies = await api.characters.sessionAllies(charId).catch(() => [])
      if (allies.length > 0) {
        setAllyPick({ ...args, allies, max: args.ability.ally_max ?? 1 })
        return
      }
    }
    abilityUse.mutate(args)
  }

  const removalAlso = !!removalPick?.ability.removal?.also_modes?.includes(useChoices[removalPick.ability.id]?.mode ?? '')

  if (!char) {
    return (
      <Layout title={t('character.turn.title')} backTo={`/char/${charId}`} group="combat" page="turn">
        <ActionsSkeleton />
      </Layout>
    )
  }

  const groups = groupForTurn(char)
  // Da sorpreso (2014) tutto è spento tranne ciò che permette di agire (Ira per l'Istinto Ferino): sta fuori dal `fieldset`.
  const exitKeys = char.computed?.incapacitated ? char.computed.surprise_exit_features ?? [] : []
  const exitIds = new Set((char.abilities ?? []).filter((a) => a.feature_key && exitKeys.includes(a.feature_key)).map((a) => String(a.id)))
  const exitEntries: TurnEntry[] = Object.values(groups).flat().filter((e) => e.kind === 'ability' && exitIds.has(e.id))
  const withoutExit = (entries: TurnEntry[]) => entries.filter((e) => !(e.kind === 'ability' && exitIds.has(e.id)))
  // Ultima prova di Furtività, salvata dal server (anche dopo un ritiro o un dado in più).
  const lastRoll = block?.last_roll
  const hideTotal = lastRoll?.roll === 'skill' && lastRoll.skill === 'stealth' ? lastRoll.total : null
  // Stesso tiro per Influenzare: il totale è quello del server, che segue le opzioni scelte dopo il tiro.
  const influenceSkills = standardActionsFor(char.rules_edition).find((s) => s.id === 'influence')?.skills ?? []
  const influenceTotal = influenceRolled && lastRoll?.roll === 'skill' && influenceSkills.includes(lastRoll.skill ?? '') ? lastRoll.total : null
  const lang = uiLang(i18n.language)
  const concSpell = char.concentrating_spell_id ? char.spells.find((s) => s.id === char.concentrating_spell_id) : undefined
  const concName = concentrationLabel(char) // anche da un oggetto, fuori dalla lista
  // Un incantesimo del catalogo ha già la sua riga (l'orologio legato alla concentrazione): niente doppione
  const concClocked = (char.active_states ?? []).some((s) => s.key.startsWith('spell_cast:') && s.ends_on?.includes('concentration_end'))
  const concRounds = char.settings?.concentration_rounds_left as number | null | undefined
  // Lama Assetata: con l'arma del patto in mano gli attacchi sono quelli del privilegio
  const pactInHand = char.items?.some((i) => i.is_equipped && i.item_metadata?.pact_weapon)
  const attacks = (pactInHand ? turn?.attacks_allowed_pact : undefined) ?? turn?.attacks_allowed ?? char.attacks_per_action ?? 1
  const stdActions = standardActionsFor(char.rules_edition)
  const hasRoundDurations = (char.condition_effects ?? []).some((e) => e.expiry_count != null) || char.settings?.concentration_rounds_left != null
  // Il turno di questo PG in uno scontro attivo: si chiude anche da qui (stesso avviso del Combattimento su ciò che resta)
  const sessionId = turn?.in_encounter && turn.is_my_turn ? turn.session_id : null
  const endMyTurn = () => {
    if (sessionId == null) return
    const { attacksLeft, actionUnused } = char.current_hit_points === 0 ? { attacksLeft: 0, actionUnused: false } : turnLeftovers(turn)
    const parts = [
      attacksLeft > 0 && t('session.combat.leftover_attacks', { count: attacksLeft }),
      actionUnused && t('session.combat.leftover_action'),
    ].filter(Boolean)
    if (parts.length > 0) setLeftover(parts.join(' · '))
    else endTurn.mutate(sessionId)
  }
  const activeConditions = Object.entries(char.conditions ?? {}).filter(([, v]) => Boolean(v))
  const endOfTurnSaves = (char.condition_effects ?? []).filter((e) => e.save_edge === 'end' && e.save_ability && e.save_dc != null)
  // Richieste in serie dallo stesso dispositivo: il server fa read-modify-write sul JSON.
  const busy = useSlot.isPending || newTurn.isPending

  /** Interruttori e scelte fatti all'uso (Frenesia, abilità di Conoscenze Secolari): il server li legge in `params`. */
  const renderToggles = (ab: Ability) => (ab.use_toggles?.length || ab.use_choices?.length || ab.use_texts?.length ? (
    <div className="pt-1 text-sm">
      {ab.use_toggles?.map((x) => (
        <SwitchToggle key={x.key} label={x.label[lang]} checked={!!toggles[ab.id]?.[x.key]}
          onChange={(on) => setToggles((s) => ({ ...s, [ab.id]: { ...s[ab.id], [x.key]: on } }))} />
      ))}
      {ab.use_choices?.map((x) => (
        <SelectSheet key={x.key} label={x.label[lang]} placeholder={t('character.turn.choose')} value={useChoices[ab.id]?.[x.key] ?? ''}
          options={[...(x.optional ? [{ value: '', label: t('character.turn.choice_none') }] : []),
            ...x.options.map((o) => ({ value: o.key, label: o.label[lang] }))]}
          onChange={(v) => setUseChoices((s) => ({ ...s, [ab.id]: { ...s[ab.id], [x.key]: v } }))} />
      ))}
      {ab.use_texts?.map((x) => (
        <Input key={x.key} label={x.label[lang]} value={useTexts[ab.id]?.[x.key] ?? ''} className="mt-2"
          onChange={(v) => setUseTexts((s) => ({ ...s, [ab.id]: { ...s[ab.id], [x.key]: v.slice(0, x.max_len) } }))} />
      ))}
    </div>
  ) : null)
  /** Il «Usa» resta spento finché non è fatta ogni scelta obbligatoria. */
  const missingChoice = (ab: Ability) => (ab.use_choices ?? []).some((x) => !x.optional && !useChoices[ab.id]?.[x.key])
    || (ab.use_texts ?? []).some((x) => !x.optional && !useTexts[ab.id]?.[x.key]?.trim())

  const renderEntry = (e: TurnEntry, c: CharacterFull) => {
    const key = `${e.kind}:${e.id}`
    if (e.kind === 'standard') {
      const std = stdActions.find((s) => s.id === e.id)
      return (
        <li key={key} className="px-1 py-2">
          <p className="font-cinzel text-sm text-dnd-text">{std?.[lang].name ?? e.label}</p>
          <p className="text-xs text-dnd-text-muted">{std?.[lang].desc}</p>
          {(std?.skills?.length ?? 0) > 0 && (
            <div className="flex flex-wrap gap-2 pt-2">
              {std?.skills?.map((sk) => (
                <RollButton key={sk} onRoll={(mode) => skillMutation.mutate({ skill: sk, mode, spendsAttack: std.spends_attack, influence: std.id === 'influence' })}
                  pending={skillMutation.isPending && skillMutation.variables?.skill === sk}
                  ariaLabel={t(`character.skills.${sk}`)}
                  className={`${BTN} border-dnd-border text-dnd-text`}>
                  {t(`character.skills.${sk}`)}
                </RollButton>
              ))}
            </div>
          )}
          {e.id === 'influence' && (
            <div className="pt-2 space-y-1">
              <Input label={t('character.turn.influence_dc')} type="number" inputMode="numeric" min={1} max={40}
                value={influenceDc} onChange={setInfluenceDc} className="w-28 text-center font-mono" />
              {influenceTotal !== null && Number(influenceDc) > 0 && (
                <p role="status" className="text-sm font-body text-dnd-text">
                  {t(influenceTotal >= Number(influenceDc) ? 'character.turn.influence_success' : 'character.turn.influence_failure',
                    { total: influenceTotal, dc: Number(influenceDc) })}
                </p>
              )}
            </div>
          )}
          {e.id === 'hide' && c.rules_edition === '2024' && hideTotal !== null && (
            c.hiding_dc != null ? (
              <p className="mt-2 text-xs text-dnd-text-muted">{t('character.turn.hiding', { dc: c.hiding_dc })}</p>
            ) : 
            hideTotal >= (turn?.hide_min_total ?? Infinity) ? (
              <Button size="sm" variant="secondary" className="mt-2" loading={hide.isPending} onClick={() => hide.mutate()}>
                {t('character.turn.hide_confirm', { total: hideTotal })}
              </Button>
            ) : (
              <p className="mt-2 text-xs text-dnd-text-muted">{t('character.turn.hide_failed', { total: hideTotal })}</p>
            )
          )}
          {(e.id === 'stand_up' || e.id === 'drop_prone') && (
            <Button size="sm" variant="secondary" className="mt-2" loading={setProne.isPending}
              disabled={e.id === 'stand_up' ? !c.conditions?.prone || c.computed?.speed === 0 : !!c.conditions?.prone}
              onClick={() => setProne.mutate(e.id === 'drop_prone')}>
              {t(e.id === 'stand_up' ? 'character.turn.stand_up' : 'character.turn.drop_prone')}
            </Button>
          )}
          {(e.id === 'use_object') && (
            <Button size="sm" variant="secondary" className="mt-2" disabled={busy || !!block?.free_interaction_used}
              onClick={() => useSlot.mutate({ slot: 'free_interaction' })}>
              {block?.free_interaction_used ? t('character.turn.free_interaction_used') : t('character.turn.free_interaction')}
            </Button>
          )}
        </li>
      )
    }
    let control: ReactNode = null
    let extra: ReactNode = null
    let preview: string | undefined
    let label = e.label
    if (e.kind === 'weapon') {
      const crimson = `${BTN} bg-dnd-crimson/10 text-dnd-crimson-bright border-dnd-crimson/30`
      if (e.id === 'unarmed') {
        label = t('character.turn.unarmed')
        extra = (
          <>
            <p className="text-xs text-dnd-text-muted">{t('character.turn.unarmed_desc', { damage: c.unarmed_damage_dice ?? '1' })}</p>
            {c.rules_edition === '2024' && (
              <div className="flex flex-wrap gap-2 pt-2">
                {(['grapple', 'shove'] as const).map((effect) => (
                  <Button key={effect} size="sm" variant="secondary" onClick={() => weaponFlow.attackUnarmedEffect(effect)}>
                    {t(`character.attack.${effect}`)}
                  </Button>
                ))}
              </div>
            )}
          </>
        )
        control = (
          <RollButton onRoll={weaponFlow.attackUnarmed} pending={weaponFlow.isUnarmedPending}
            ariaLabel={`${t('character.turn.attack')} ${label}`} className={crimson}>
            <Target size={14} />{t('character.turn.attack')}
          </RollButton>
        )
      } else {
        const item = c.items.find((i) => String(i.id) === e.id)
        const itemId = Number(e.id)
        control = (
          <RollButton onRoll={(mode) => weaponFlow.attackWeapon(itemId, mode)} pending={weaponFlow.isWeaponPending(itemId)}
            ariaLabel={`${t('character.turn.attack')} ${label}`} className={crimson}>
            <Target size={14} />{t('character.turn.attack')}
          </RollButton>
        )
        if (item) extra = (
          <>
            <WeaponPreviewLine item={item} />
            <WeaponChoiceRow item={item} char={c} choice={choiceOf(choices, itemId)} onChange={(ch) => setChoice(itemId, ch)} />
          </>
        )
      }
    } else if (e.kind === 'spell') {
      const spell = c.spells.find((s) => String(s.id) === e.id)
      if (spell) {
        control = castFlow.canRollActiveDamage(spell) ? (
          // Già attivo (Guardiani spirituali): i danni dei turni dopo si tirano senza un nuovo lancio
          <Pressable onClick={() => castFlow.rollActiveDamage(spell)}
            className={`${BTN} bg-dnd-arcane/10 text-dnd-arcane-bright border-dnd-arcane/30`}>
            <Sparkles size={14} />{t('character.spells.roll_active_damage')}
          </Pressable>
        ) : (
          <RollButton onRoll={(mode) => castFlow.beginCast(spell, mode)} pending={castFlow.isSpellPending(spell.id)}
            ariaLabel={`${t('character.turn.cast')} ${label}`}
            className={`${BTN} bg-dnd-arcane/10 text-dnd-arcane-bright border-dnd-arcane/30`}>
            <Sparkles size={14} />{t('character.turn.cast')}
          </RollButton>
        )
      }
    } else {
      const ab = c.abilities.find((a) => String(a.id) === e.id)
      preview = ab?.use_preview?.[lang]
      // Reazione passiva (U24): niente «Usa» qui, la propone l'app nel momento in cui serve (es. i danni dalla pagina PF)
      if (ab?.is_passive) preview = `${ab.description ? `${ab.description} ` : ''}${t('character.turn.reaction_offered')}`
      if (ab && (ab.max_uses ?? 0) > 0) {
        // Un uso che non costa nulla (prolungare l'Ira 2024) resta possibile a 0 usi: lo dice il server.
        const running = !!ab.free_use
        // Un uso finito si ripristina spendendo un uso di un'altra risorsa (Presenza Intimidatoria): l'interruttore c'è solo allora.
        const restorable = !!ab.use_toggles?.some((x) => x.key === 'restore')
        const usable = running || restorable
        // Un uso che spende un'altra riserva e l'ha finita (Magia Ammaliante senza Ispirazione): il server lo rifiuterebbe
        const poolEmpty = ab.spends_left === 0
        const left = ab.uses ?? 0
        const pickable = !!(ab.has_on_use && ab.choose_amount)
        const floor = ab.min_amount ?? 1
        const cap = Math.max(floor, Math.min(left, ab.max_amount ?? left))
        const amount = Math.min(Math.max(amounts[ab.id] ?? floor, floor), cap)
        label = `${e.label} (${left}/${ab.max_uses})`
        // Il costo di una cura di condizioni lo decide il server (cinque punti per voce): niente contatore da regolare.
        const serverPriced = !!ab.removal?.cost_each && !!ab.removal.modes?.includes(useChoices[ab.id]?.mode ?? '')
        if (pickable && left > 0 && !serverPriced) extra = (
          <>
            {renderToggles(ab)}
            <div className="pt-2"><AmountStepper value={amount} min={floor} max={cap} onChange={(n) => setAmounts((a) => ({ ...a, [ab.id]: n }))} /></div>
          </>
        )
        else if (left > 0 || usable) extra = renderToggles(ab)
        // Una riserva a catalogo (`is_pool`, dal server: Incanalare Divinità) mostra solo il contatore, l'uso passa dai privilegi
        // che la spendono. Le righe automatiche di classe (Secondo Vento...) e quelle a mano conservano il «Usa».
        if (!ab.is_pool || ab.has_on_use) control = (
          <Button size="sm" variant="secondary" disabled={(left < (ab.min_amount ?? 1) && !usable) || missingChoice(ab) || poolEmpty}
            loading={abilityUse.isPending && abilityUse.variables?.ability.id === ab.id}
            onClick={() => triggerAbility({ ability: ab, uses: Math.max(0, left - 1), amount: pickable ? amount : undefined })}>
            {(left < (ab.min_amount ?? 1) && !usable) || poolEmpty ? t('character.turn.no_uses') : t(usesOnAlly(ab) ? 'character.turn.use_on' : 'character.turn.use')}
          </Button>
        )
      } else if (ab && (isUnlimitedFeature(ab) || ab.has_on_use)) {
        // Senza contatore (Presenza Intimidatoria) o illimitato (Ira al 20°): il «Usa» c'è se il privilegio ha un effetto.
        if (isUnlimitedFeature(ab)) label = `${e.label} (${t('character.abilities.unlimited')})`
        if (ab.has_on_use) {
          // Quanti punti della riserva spendere (Frusta d'Acqua: 2 ki più extra): il tetto sono i punti rimasti a quella riserva.
          const floor = ab.min_amount ?? 1
          const pickable = !!ab.choose_amount
          const poolLeft = ab.spends_left ?? Number.MAX_SAFE_INTEGER
          const cap = Math.max(floor, Math.min(poolLeft, ab.max_amount ?? Number.MAX_SAFE_INTEGER))
          const amount = Math.min(Math.max(amounts[ab.id] ?? floor, floor), cap)
          const short = ab.spends_left != null && (ab.spends_left === 0 || (pickable && ab.spends_left < floor))
          extra = (
            <>
              {renderToggles(ab)}
              {pickable && !short && <div className="pt-2"><AmountStepper value={amount} min={floor} max={cap} onChange={(n) => setAmounts((a) => ({ ...a, [ab.id]: n }))} /></div>}
            </>
          )
          control = (
            <Button size="sm" variant="secondary" disabled={missingChoice(ab) || short || !!ab.use_blocked}
              loading={abilityUse.isPending && abilityUse.variables?.ability.id === ab.id}
              onClick={() => triggerAbility({ ability: ab, uses: 0, amount: pickable ? amount : undefined })}>
              {short ? t('character.turn.no_uses') : t(usesOnAlly(ab) ? 'character.turn.use_on' : 'character.turn.use')}
            </Button>
          )
        }
      }
    }
    return (
      <li key={key} className="px-1 py-2">
        <div className="flex items-center gap-3">
          <span className="flex-1 min-w-0 truncate font-body text-sm text-dnd-text">{label}</span>
          {control}
        </div>
        {preview && <p className="pt-1 text-sm font-body text-dnd-text-muted" data-testid="use-preview">{preview}</p>}
        {extra}
      </li>
    )
  }

  const sectionBody = (title: string, entries: TurnEntry[]) => {
    const playable = entries.filter((e) => e.kind !== 'standard')
    const standard = entries.filter((e) => e.kind === 'standard')
    const standardOpen = openStandard[title]
    return (
      <div className="divide-y divide-dnd-border/60 border-b border-dnd-border/60">
        {entries.length === 0 && <p className="text-sm text-dnd-text-muted px-1 py-2">{t('character.turn.empty')}</p>}
        {playable.length > 0 && <ul className="divide-y divide-dnd-border/60">{playable.map((e) => renderEntry(e, char))}</ul>}
        {standard.length > 0 && (
          <Pressable
            aria-expanded={!!standardOpen}
            onClick={() => setOpenStandard((o) => ({ ...o, [title]: !o[title] }))}
            className="flex w-full min-h-[48px] items-center justify-between gap-2 px-1 text-left text-sm font-body text-dnd-text-muted"
          >
            {t('character.turn.standard_actions', { n: standard.length })}
            <ExpandChevron open={!!standardOpen} className="text-dnd-text-muted" />
          </Pressable>
        )}
        {standard.length > 0 && standardOpen && (
          <ul className="divide-y divide-dnd-border/60">{standard.map((e) => renderEntry(e, char))}</ul>
        )}
      </div>
    )
  }

  const section = (title: string, entries: TurnEntry[], bucket: Bucket) => {
    const isUsed = used[bucket]
    // T13: i danni di un incantesimo attivo (Guardiani spirituali) si tirano anche a azione spesa, nei turni dei nemici
    const freeNow = isUsed ? entries.filter((e) => e.kind === 'ability'
      ? char?.abilities.some((a) => String(a.id) === e.id && a.free_use)
      : e.kind === 'spell' && char?.spells.some((s) => String(s.id) === e.id && castFlow.canRollActiveDamage(s))) : []
    return (
      <section>
        <div className="flex items-center justify-between gap-2 border-b border-dnd-border pb-1 pl-1">
          <h2 className={LEDGER_TITLE}>{title}</h2>
          <Pressable
            aria-pressed={isUsed}
            disabled={busy}
            aria-label={`${t('character.turn.mark_used')}: ${title}`}
            onClick={() => useSlot.mutate({ slot: SLOT_OF[bucket], on: !isUsed })}
            className={`inline-flex items-center gap-1 min-h-11 px-3 rounded-lg border text-xs font-medium ${
              isUsed
                ? 'border-dnd-gold-dim text-dnd-gold-bright'
                : 'border-dnd-border text-dnd-text-muted'}`}
          >
            {isUsed && <Check size={14} aria-hidden />}
            {isUsed ? t('character.turn.used') : t('character.turn.mark_used')}
          </Pressable>
        </div>
        {/* Una sezione usata si richiude: in vista resta solo ciò che si può ancora fare, anche un uso gratuito (Arciere). */}
        {!isUsed && sectionBody(title, entries)}
        {isUsed && freeNow.length > 0 && sectionBody(title, freeNow)}
      </section>
    )
  }

  return (
    <Layout title={t('character.turn.title')} backTo={`/char/${charId}`} group="combat" page="turn">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <p className="text-sm text-dnd-text font-body tabular-nums">
          {t('character.turn.attacks_made', { made: block?.action_attacks ?? 0, n: attacks })}
          {extraActions > 0 && (
            <span data-testid="extra-actions" className="ml-3 text-dnd-gold-bright">{t('character.turn.extra_actions', { n: extraActions })}</span>
          )}
          {turn?.in_encounter && turn.round != null && (
            <span className="ml-3 text-dnd-text-muted">{t('character.turn.round', { n: turn.round })}</span>
          )}
        </p>
        <div className="flex flex-wrap justify-end gap-2">
          {!turn?.in_encounter && !!block?.once_per_turn?.length && (
            <Button size="sm" variant="ghost" loading={otherTurn.isPending} onClick={() => otherTurn.mutate()}>
              {t('character.turn.other_turn')}
            </Button>
          )}
          {turn?.in_encounter ? (
            <p className="self-center text-xs text-dnd-text-muted font-body">{t('character.conditions.duration.in_encounter')}</p>
          ) : hasRoundDurations && (  // come Condizioni: senza durate a round non c'è niente da scalare
            <Button size="sm" variant="ghost" icon={<Clock size={14} />} loading={tick.isPending} onClick={() => tick.mutate()}>
              {t('character.turn.end_round')}
            </Button>
          )}
          <Button size="sm" variant="secondary" icon={<RotateCcw size={14} />} loading={newTurn.isPending} disabled={busy} onClick={() => newTurn.mutate()}>
            {t('character.turn.new_turn')}
          </Button>
        </div>
      </div>

      {sessionId != null && (
        <Button variant="primary" size="md" fullWidth icon={<ChevronRight size={16} />} loading={endTurn.isPending} onClick={endMyTurn}>
          {t('session.combat.end_my_turn')}
        </Button>
      )}

      {(block?.start_heal ?? []).map((n) => (
        <p key={n.feature_key} role="status" data-testid="start-heal" className="px-1 text-sm font-body text-dnd-gold-bright">
          {n.message ? n.message[lang] : t('character.turn.start_heal', { name: n.name[lang], amount: n.amount })}
        </p>
      ))}

      <ActiveStatesBar char={char} />

      {/* MA8: condizioni attive e TS di fine turno, come nella card del Combattimento */}
      {activeConditions.length > 0 && (
        <div data-testid="turn-conditions" className="flex flex-wrap gap-1.5 px-1">
          {activeConditions.map(([key, val]) => <ConditionBadge key={key} conditionKey={key} value={val} showLabel />)}
        </div>
      )}
      {endOfTurnSaves.map((e, i) => (
        <p key={`${e.slug}-${i}`} data-testid="turn-end-save" className="rounded-lg border border-dnd-amber/60 bg-dnd-amber/10 px-2.5 py-1 text-xs text-dnd-amber font-body">
          {t('session.combat.end_turn_save_hint', {
            save: t('character.conditions.effect.save_any', { ability: t(`character.ability.${e.save_ability}_short`), dc: e.save_dc }),
            condition: formatCondition(e.slug, true, t),
          })}
        </p>
      ))}

      {/* U15: l'incantesimo in concentrazione senza stato proprio (Ragnatela, Guardiani spirituali) resta visibile nel turno */}
      {concName && !concClocked && (
        <p data-testid="turn-concentration" className="flex flex-wrap items-center gap-x-2 px-3 py-2 rounded-xl border border-dnd-arcane/40 bg-dnd-arcane/10 text-sm font-body text-dnd-text">
          <Sparkles size={16} aria-hidden className="shrink-0 text-dnd-arcane-bright" />
          <span>{t('character.spells.concentration')}: {concName}</span>
          {concRounds != null && <span className="text-dnd-text-muted tabular-nums">{t('character.turn.state_rounds_left', { n: concRounds })}</span>}
          {concSpell?.save_dc != null && !!concSpell.attack_save?.trim() && concSpell.attack_save.trim().toUpperCase() !== 'ATK' && (
            <span className="text-dnd-text-muted tabular-nums">{t('character.turn.concentration_spell_dc', { dc: concSpell.save_dc })}</span>
          )}
        </p>
      )}

      {char.computed?.incapacitated && (
        <p role="status" className="px-1 text-sm font-body text-dnd-crimson-bright">
          {t(incapacitatedMessageKey(char))}
        </p>
      )}

      {exitEntries.length > 0 && (
        <section data-testid="turn-surprise-exit">
          <h2 className={`flex min-h-11 items-center border-b border-dnd-border pl-1 ${LEDGER_TITLE}`}>{t(char.computed?.surprised ? 'character.turn.surprised_exit' : 'character.turn.down_exit')}</h2>
          <ul className="divide-y divide-dnd-border/60 border-b border-dnd-border/60">
            {exitEntries.map((e) => renderEntry(e, char))}
          </ul>
        </section>
      )}

      {/* `fieldset disabled` spegne ogni pulsante delle azioni. */}
      <fieldset disabled={!!char.computed?.incapacitated}
        className={`min-w-0 space-y-3 ${char.computed?.incapacitated ? '[&_button]:opacity-50' : ''}`}>
      {/* Sempre aperta: un attacco può servire anche fuori dall'azione (opportunità, altra mano).
          Da incapacitato (anche a 0 PF) non si attacca affatto: la sezione sparisce (U41). */}
      {!char.computed?.incapacitated && <section>
        <div className="flex min-h-11 items-center justify-between gap-2 border-b border-dnd-border pl-1">
          <h2 className={LEDGER_TITLE}>{t('character.turn.section_attacks')}</h2>
          {/* U12: si cambia arma da qui, senza passare dall'inventario a metà turno */}
          <Pressable onClick={() => setWeaponPicker(true)}
            className="min-h-11 px-2 text-xs font-medium text-dnd-gold-bright active:opacity-70">
            {t('character.turn.change_weapon')}
          </Pressable>
        </div>
        <ul className="divide-y divide-dnd-border/60 border-b border-dnd-border/60">
          {withoutExit(groups.attacks).map((e) => renderEntry(e, char))}
        </ul>
      </section>}

      {BUCKETS.map((b) => (
        <div key={b}>{section(t(`character.turn.section_${b}`), withoutExit(groups[b]), b)}</div>
      ))}
      </fieldset>

      <section>
        <Pressable
          aria-expanded={otherOpen}
          onClick={() => setOtherOpen((o) => !o)}
          className="flex w-full min-h-11 items-center justify-between gap-2 border-b border-dnd-border pl-1 pr-1 text-left"
        >
          <span className={LEDGER_TITLE}>{t('character.turn.section_other')}</span>
          <ExpandChevron open={otherOpen} className="text-dnd-text-muted" />
        </Pressable>
        {otherOpen && (
          <fieldset data-testid="turn-other" disabled={!!char.computed?.incapacitated}
            className={`min-w-0 pt-2 ${char.computed?.incapacitated ? '[&_button]:opacity-50' : ''}`}>
            {sectionBody(t('character.turn.section_other'), withoutExit(groups.other))}
          </fieldset>
        )}
      </section>

      <BeastOrders char={char} turn={block} />

      <GiveInspirationRow char={char} />

      {skillRoll && (
        <RollResultModal result={skillRoll.result} title={t(`character.skills.${skillRoll.skill}`)}
          afterRoll={{ charId, query: { roll: 'skill', skill: skillRoll.skill } }}
          onClose={() => setSkillRoll(null)} />
      )}
      {weaponFlow.elements}
      {weaponPicker && (
        <EquipItemPicker charId={charId} slot="main_hand" items={char.items ?? []} onClose={() => setWeaponPicker(false)} />
      )}
      {castFlow.elements}
      {panel && char && (panel.use_panel === 'weapon_bond'
        ? <WeaponBondSheet char={char} onClose={() => setPanel(null)} />
        : panel.use_panel === 'wild_magic'
          ? <WildMagicSheet char={char} onClose={() => setPanel(null)} />
          : <PreserveLifeSheet char={char} onClose={() => setPanel(null)} />)}
      {removalPick?.ability.removal && (
        <AllyTargetSheet
          title={removalPick.ability.name} allies={removalPick.allies} pending={abilityUse.isPending} onPick={() => {}} onClose={() => setRemovalPick(null)}
          removal={{
            ...removalPick.ability.removal, maxTargets: removalPick.ability.removal.max_targets, optional: removalPick.ability.removal.optional || removalAlso,
            costEach: removalPick.ability.removal.cost_each, confirmKey: 'removal_confirm_use',
            scope: !removalPick.ability.removal.ally ? 'self' : removalPick.ability.removal.bound || removalAlso ? (useChoices[removalPick.ability.id]?.mode === 'self' ? 'self' : 'others') : 'any',
            onConfirm: (removal) => abilityUse.mutate({ ability: removalPick.ability, uses: removalPick.uses, amount: removalPick.amount, removal }),
          }} />
      )}
      {allyPick && (
        <AllyTargetSheet title={allyPick.ability.name} die={allyPick.ability.feature_key === 'bard.bardic_inspiration'} allies={allyPick.allies} max={allyPick.max} pending={abilityUse.isPending} onClose={() => setAllyPick(null)}
          onPickMany={(allyIds) => abilityUse.mutate({ ability: allyPick.ability, uses: allyPick.uses, amount: allyPick.amount, allyIds })}
          onPick={(allyId) => abilityUse.mutate({ ability: allyPick.ability, uses: allyPick.uses, amount: allyPick.amount, ...(allyId === null ? {} : { allyId }) })} />
      )}
      {targetKey && <TargetEffectSheet charId={charId} effectKey={targetKey} onClose={() => setTargetKey(null)} />}
      <ConfirmSheet
        open={leftover !== null}
        onClose={() => setLeftover(null)}
        onConfirm={() => {
          if (sessionId != null) endTurn.mutate(sessionId)
          setLeftover(null)
        }}
        title={t('session.combat.leftover_title')}
        body={leftover ?? undefined}
        confirmLabel={t('session.combat.leftover_cta')}
        confirmVariant="primary"
      />
    </Layout>
  )
}

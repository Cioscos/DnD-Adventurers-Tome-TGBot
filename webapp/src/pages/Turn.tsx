import { askRollOptions, refreshAfterOptions } from '@/lib/rollOptions'
import { useState, type ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Check, Clock, RotateCcw, Sparkles, Target } from 'lucide-react'
import { api, ApiError, type RollMode } from '@/api/client'
import { isUnlimitedFeature } from '@/lib/abilityUses'
import Layout from '@/components/Layout'
import Button from '@/components/ui/Button'
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
import ActionsSkeleton from '@/components/skeletons/ActionsSkeleton'
import { useWeaponAttackFlow } from '@/hooks/useWeaponAttackFlow'
import { useTickRound } from '@/hooks/useTickRound'
import { useTurnState } from '@/hooks/useTurnState'
import { useToast } from '@/hooks/useToast'
import { useCastFlow } from '@/pages/spells/useCastFlow'
import { useWeaponChoices, choiceOf } from '@/store/weaponChoiceStore'
import { groupForTurn, type TurnEntry } from '@/lib/turnGrouping'
import { unarmedDamageDice } from '@/lib/unarmedStrike'
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
const ABILITY_USE_ERRORS = ['turn_slot_used', 'no_uses', 'feature_not_usable', 'amount_too_high', 'feature_unavailable', 'once_per_turn', 'no_attack_left', 'amount_too_low', 'amount_invalid', 'no_slot', 'insufficient_funds', 'invalid_text', 'identity_exists', 'invalid_choice', 'already_chosen', 'no_benefit']
/** Esiti di un privilegio che il server manda come chiavi (`FeatureUseResult.notes`) e la pagina traduce. */
const USE_NOTES = ['arcane_charge', 'quivering_palm', 'water_whip', 'fist_of_unbroken_air', 'lay_on_hands_other', 'lay_on_hands_cure_self', 'lay_on_hands_cure_other', 'primeval_awareness', 'vanish_hide',
  'cunning_dash', 'cunning_disengage', 'cunning_hide', 'cunning_sleight_of_hand', 'cunning_thieves_tools', 'cunning_use_object', 'mage_hand_control', 'bend_luck_plus', 'bend_luck_minus']
const BTN = 'flex items-center gap-1 text-sm font-medium px-4 h-11 rounded-lg border active:scale-95 transition-transform'

export default function Turn() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const [skillRoll, setSkillRoll] = useState<{ result: RollResult; skill: string } | null>(null)
  const [otherOpen, setOtherOpen] = useState(false)
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
  const [allyPick, setAllyPick] = useState<{ ability: Ability; uses: number; amount?: number; allies: { id: number; name: string }[] } | null>(null)
  const choices = useWeaponChoices((s) => s.choices)
  const setChoice = useWeaponChoices((s) => s.setChoice)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })
  const { data: turn } = useTurnState(charId, true)

  // Lo stato del turno vive sul server: sopravvive a ricarica e cambio pagina.
  const block = turn?.turn
  // Un'azione in più (Azione Impetuosa) riapre la sezione dell'azione anche se quella normale è già spesa.
  const extraActions = block?.extra_actions ?? 0
  const used: Record<Bucket, boolean> = {
    action: !!block?.action_used && extraActions === 0, bonus_action: !!block?.bonus_used, reaction: !!block?.reaction_used,
  }
  const setBlock = (b: TurnBlock) =>
    qc.setQueryData(['turn-state', charId], (old: TurnState | undefined) => old && { ...old, turn: b })
  const useSlot = useMutation({
    mutationFn: ({ slot, on = true }: { slot: TurnSlot; on?: boolean }) => api.characters.turnUse(charId, slot, on),
    onSuccess: setBlock,
    onError: () => qc.invalidateQueries({ queryKey: ['turn-state', charId] }),
  })
  const newTurn = useMutation({
    mutationFn: () => api.characters.turnNew(charId),
    // L'inizio del turno può curare (Sopravvissuto): i PF si rileggono.
    onSuccess: (b) => { setBlock(b); qc.invalidateQueries({ queryKey: ['character', charId] }) },
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
  const rollD20 = useD20Roll()
  const skillMutation = useMutation({
    mutationFn: async ({ skill, mode }: { skill: string; mode: RollMode; spendsAttack?: boolean; influence?: boolean }) => {
      const choice = await askRollOptions(charId, { roll: 'skill', skill })
      return { result: await api.characters.rollSkill(charId, skill, d20Arg(mode, await rollD20(mode), choice)), skill }
    },
    onSuccess: ({ result, skill }, { spendsAttack, influence }) => {
      if (spendsAttack) useSlot.mutate({ slot: 'attack' })
      if (influence) setInfluenceRolled(true)
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
    mutationFn: async ({ ability, uses, amount, allyId }: { ability: Ability; uses: number; amount?: number; allyId?: number }) => {
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
        const params = allyId !== undefined ? { ...choices, target_character_id: allyId } : choices
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
      if (res?.received) toast.info(t('character.turn.use_received', { name: res.received.name, n: res.received.healed }))
      // Il dado tirato dal privilegio (Parole Taglienti: il valore da sottrarre al tiro dell'altro) si dice subito.
      if (res?.rolls?.length) toast.info(t('character.turn.use_rolled'), { description: `${res.rolls.join(' + ')} = ${res.rolls.reduce((a, b) => a + b, 0)}` })
      // Un valore per un altro (PF temporanei di Incoraggiamento, dado del Colpo del Comandante) e gli esiti in chiave.
      if (res?.given != null) toast.info(t('character.turn.use_given', { n: res.given }))
      if (res?.temp_hp != null) toast.info(t('character.turn.use_temp_hp', { n: res.temp_hp }))
      if (res?.message) toast.info(res.message[i18n.language?.startsWith('en') ? 'en' : 'it'])
      for (const note of res?.notes ?? []) if (USE_NOTES.includes(note)) toast.info(t(`character.turn.use_notes.${note}`))
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
      setAllyPick(null)
    },
  })
  /** «Usa» di un privilegio: se dà lo stato a un alleato e alla serata siede qualcun altro, prima chiede a chi. */
  const triggerAbility = async (args: { ability: Ability; uses: number; amount?: number }) => {
    if (args.ability.use_panel === 'preserve_life' || args.ability.use_panel === 'weapon_bond' || args.ability.use_panel === 'wild_magic') {
      setPanel(args.ability)
      return
    }
    // Un privilegio che dà un effetto a un alleato, o una cui modalità scelta è rivolta a un altro (Imposizione delle Mani).
    const mode = useChoices[args.ability.id]?.mode
    if (args.ability.gives_to_ally || (mode && args.ability.ally_modes?.includes(mode))) {
      const allies = await api.characters.sessionAllies(charId).catch(() => [])
      if (allies.length > 0) {
        setAllyPick({ ...args, allies })
        return
      }
    }
    abilityUse.mutate(args)
  }

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
  const lang = i18n.language?.startsWith('en') ? 'en' : 'it'
  // Lama Assetata: con l'arma del patto in mano gli attacchi sono quelli del privilegio
  const pactInHand = char.items?.some((i) => i.is_equipped && i.item_metadata?.pact_weapon)
  const attacks = (pactInHand ? turn?.attacks_allowed_pact : undefined) ?? turn?.attacks_allowed ?? char.attacks_per_action ?? 1
  const stdActions = standardActionsFor(char.rules_edition)
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
            hideTotal >= 15 ? (
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
    let label = e.label
    if (e.kind === 'weapon') {
      const crimson = `${BTN} bg-dnd-crimson/10 text-dnd-crimson-bright border-dnd-crimson/30`
      if (e.id === 'unarmed') {
        label = t('character.turn.unarmed')
        extra = (
          <>
            <p className="text-xs text-dnd-text-muted">{t('character.turn.unarmed_desc', { damage: unarmedDamageDice(c.classes, c.rules_edition, c.items) })}</p>
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
        if (item) extra = <WeaponChoiceRow item={item} char={c} choice={choiceOf(choices, itemId)} onChange={(ch) => setChoice(itemId, ch)} />
      }
    } else if (e.kind === 'spell') {
      const spell = c.spells.find((s) => String(s.id) === e.id)
      if (spell) {
        control = (
          <RollButton onRoll={(mode) => castFlow.beginCast(spell, mode)} pending={castFlow.isSpellPending(spell.id)}
            ariaLabel={`${t('character.turn.cast')} ${label}`}
            className={`${BTN} bg-dnd-arcane/10 text-dnd-arcane-bright border-dnd-arcane/30`}>
            <Sparkles size={14} />{t('character.turn.cast')}
          </RollButton>
        )
      }
    } else {
      const ab = c.abilities.find((a) => String(a.id) === e.id)
      if (ab && (ab.max_uses ?? 0) > 0) {
        const left = ab.uses ?? 0
        const pickable = !!(ab.has_on_use && ab.choose_amount)
        const floor = ab.min_amount ?? 1
        const cap = Math.max(floor, Math.min(left, ab.max_amount ?? left))
        const amount = Math.min(Math.max(amounts[ab.id] ?? floor, floor), cap)
        label = `${e.label} (${left}/${ab.max_uses})`
        if (pickable && left > 0) extra = (
          <>
            {renderToggles(ab)}
            <div className="pt-2"><AmountStepper value={amount} min={floor} max={cap} onChange={(n) => setAmounts((a) => ({ ...a, [ab.id]: n }))} /></div>
          </>
        )
        else if (left > 0) extra = renderToggles(ab)
        // Una riserva a catalogo (`is_pool`, dal server: Incanalare Divinità) mostra solo il contatore, l'uso passa dai privilegi
        // che la spendono. Le righe automatiche di classe (Secondo Vento...) e quelle a mano conservano il «Usa».
        if (!ab.is_pool || ab.has_on_use) control = (
          <Button size="sm" variant="secondary" disabled={left < (ab.min_amount ?? 1) || missingChoice(ab)}
            loading={abilityUse.isPending && abilityUse.variables?.ability.id === ab.id}
            onClick={() => triggerAbility({ ability: ab, uses: Math.max(0, left - 1), amount: pickable ? amount : undefined })}>
            {left < (ab.min_amount ?? 1) ? t('character.turn.no_uses') : t('character.turn.use')}
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
            <Button size="sm" variant="secondary" disabled={missingChoice(ab) || short}
              loading={abilityUse.isPending && abilityUse.variables?.ability.id === ab.id}
              onClick={() => triggerAbility({ ability: ab, uses: 0, amount: pickable ? amount : undefined })}>
              {short ? t('character.turn.no_uses') : t('character.turn.use')}
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
        {/* Una sezione usata si richiude: in vista resta solo ciò che si può ancora fare. */}
        {!isUsed && sectionBody(title, entries)}
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
          ) : (
            <Button size="sm" variant="ghost" icon={<Clock size={14} />} loading={tick.isPending} onClick={() => tick.mutate()}>
              {t('character.turn.end_round')}
            </Button>
          )}
          <Button size="sm" variant="secondary" icon={<RotateCcw size={14} />} loading={newTurn.isPending} disabled={busy} onClick={() => newTurn.mutate()}>
            {t('character.turn.new_turn')}
          </Button>
        </div>
      </div>

      {(block?.start_heal ?? []).map((n) => (
        <p key={n.feature_key} role="status" data-testid="start-heal" className="px-1 text-sm font-body text-dnd-gold-bright">
          {t('character.turn.start_heal', { name: n.name[lang], amount: n.amount })}
        </p>
      ))}

      <ActiveStatesBar char={char} />

      {char.computed?.incapacitated && (
        <p role="status" className="px-1 text-sm font-body text-dnd-crimson-bright">
          {t(char.computed.surprised ? 'character.turn.surprised' : 'character.turn.incapacitated')}
        </p>
      )}

      {exitEntries.length > 0 && (
        <section data-testid="turn-surprise-exit">
          <h2 className={`flex min-h-11 items-center border-b border-dnd-border pl-1 ${LEDGER_TITLE}`}>{t('character.turn.surprised_exit')}</h2>
          <ul className="divide-y divide-dnd-border/60 border-b border-dnd-border/60">
            {exitEntries.map((e) => renderEntry(e, char))}
          </ul>
        </section>
      )}

      {/* `fieldset disabled` spegne ogni pulsante delle azioni. */}
      <fieldset disabled={!!char.computed?.incapacitated}
        className={`min-w-0 space-y-3 ${char.computed?.incapacitated ? '[&_button]:opacity-50' : ''}`}>
      {/* Sempre aperta: un attacco può servire anche fuori dall'azione (opportunità, altra mano). */}
      <section>
        <h2 className={`flex min-h-11 items-center border-b border-dnd-border pl-1 ${LEDGER_TITLE}`}>{t('character.turn.section_attacks')}</h2>
        <ul className="divide-y divide-dnd-border/60 border-b border-dnd-border/60">
          {withoutExit(groups.attacks).map((e) => renderEntry(e, char))}
        </ul>
      </section>

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
      {castFlow.elements}
      {panel && char && (panel.use_panel === 'weapon_bond'
        ? <WeaponBondSheet char={char} onClose={() => setPanel(null)} />
        : panel.use_panel === 'wild_magic'
          ? <WildMagicSheet char={char} onClose={() => setPanel(null)} />
          : <PreserveLifeSheet char={char} onClose={() => setPanel(null)} />)}
      {allyPick && (
        <AllyTargetSheet title={allyPick.ability.name} die={allyPick.ability.feature_key === 'bard.bardic_inspiration'} allies={allyPick.allies} pending={abilityUse.isPending} onClose={() => setAllyPick(null)}
          onPick={(allyId) => abilityUse.mutate({ ability: allyPick.ability, uses: allyPick.uses, amount: allyPick.amount, ...(allyId === null ? {} : { allyId }) })} />
      )}
      {targetKey && <TargetEffectSheet charId={charId} effectKey={targetKey} onClose={() => setTargetKey(null)} />}
    </Layout>
  )
}

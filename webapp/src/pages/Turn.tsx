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
import GiveInspirationRow from '@/components/character/GiveInspirationRow'
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
const ABILITY_USE_ERRORS = ['turn_slot_used', 'no_uses', 'feature_not_usable']
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
  const choices = useWeaponChoices((s) => s.choices)
  const setChoice = useWeaponChoices((s) => s.setChoice)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })
  const { data: turn } = useTurnState(charId, true)

  // Lo stato del turno vive sul server: sopravvive a ricarica e cambio pagina.
  const block = turn?.turn
  const used: Record<Bucket, boolean> = {
    action: !!block?.action_used, bonus_action: !!block?.bonus_used, reaction: !!block?.reaction_used,
  }
  const setBlock = (b: TurnBlock) =>
    qc.setQueryData(['turn-state', charId], (old: TurnState | undefined) => old && { ...old, turn: b })
  const useSlot = useMutation({
    mutationFn: ({ slot, on = true }: { slot: TurnSlot; on?: boolean }) => api.characters.turnUse(charId, slot, on),
    onSuccess: setBlock,
    onError: () => qc.invalidateQueries({ queryKey: ['turn-state', charId] }),
  })
  const newTurn = useMutation({ mutationFn: () => api.characters.turnNew(charId), onSuccess: setBlock })
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
    mutationFn: async ({ ability, uses }: { ability: Ability; uses: number }) => {
      if (ability.has_on_use && ability.feature_key) await api.characters.featureUse(charId, ability.feature_key)
      else await api.abilities.update(charId, ability.id, { uses })
    },
    // Il server rifiuta ciò che la pagina non aveva ancora visto (slot già speso, usi finiti): si dice, mai il messaggio tecnico.
    onError: (err) => {
      const code = err instanceof ApiError ? (err.detail as { code?: string } | null)?.code : undefined
      toast.error(t(`character.turn.use_errors.${code && ABILITY_USE_ERRORS.includes(code) ? code : 'default'}`))
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      qc.invalidateQueries({ queryKey: ['turn-state', charId] })
    },
  })

  if (!char) {
    return (
      <Layout title={t('character.turn.title')} backTo={`/char/${charId}`} group="combat" page="turn">
        <ActionsSkeleton />
      </Layout>
    )
  }

  const groups = groupForTurn(char)
  // Ultima prova di Furtività, salvata dal server (anche dopo un ritiro o un dado in più).
  const lastRoll = block?.last_roll
  const hideTotal = lastRoll?.roll === 'skill' && lastRoll.skill === 'stealth' ? lastRoll.total : null
  // Stesso tiro per Influenzare: il totale è quello del server, che segue le opzioni scelte dopo il tiro.
  const influenceSkills = standardActionsFor(char.rules_edition).find((s) => s.id === 'influence')?.skills ?? []
  const influenceTotal = influenceRolled && lastRoll?.roll === 'skill' && influenceSkills.includes(lastRoll.skill ?? '') ? lastRoll.total : null
  const lang = i18n.language?.startsWith('en') ? 'en' : 'it'
  const attacks = turn?.attacks_allowed ?? char.attacks_per_action ?? 1
  const stdActions = standardActionsFor(char.rules_edition)
  // Richieste in serie dallo stesso dispositivo: il server fa read-modify-write sul JSON.
  const busy = useSlot.isPending || newTurn.isPending

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
        label = `${e.label} (${left}/${ab.max_uses})`
        control = (
          <Button size="sm" variant="secondary" disabled={left <= 0}
            loading={abilityUse.isPending && abilityUse.variables?.ability.id === ab.id}
            onClick={() => abilityUse.mutate({ ability: ab, uses: Math.max(0, left - 1) })}>
            {left <= 0 ? t('character.turn.no_uses') : t('character.turn.use')}
          </Button>
        )
      } else if (ab && isUnlimitedFeature(ab)) {
        label = `${e.label} (${t('character.abilities.unlimited')})`
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
          {t('character.turn.attacks_made', { made: block?.attacks_made ?? 0, n: attacks })}
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

      <ActiveStatesBar char={char} />

      {char.computed?.incapacitated && (
        <p role="status" className="px-1 text-sm font-body text-dnd-crimson-bright">
          {t(char.computed.surprised ? 'character.turn.surprised' : 'character.turn.incapacitated')}
        </p>
      )}

      {/* `fieldset disabled` spegne ogni pulsante delle azioni. */}
      <fieldset disabled={!!char.computed?.incapacitated}
        className={`min-w-0 space-y-3 ${char.computed?.incapacitated ? '[&_button]:opacity-50' : ''}`}>
      {/* Sempre aperta: un attacco può servire anche fuori dall'azione (opportunità, altra mano). */}
      <section>
        <h2 className={`flex min-h-11 items-center border-b border-dnd-border pl-1 ${LEDGER_TITLE}`}>{t('character.turn.section_attacks')}</h2>
        <ul className="divide-y divide-dnd-border/60 border-b border-dnd-border/60">
          {groups.attacks.map((e) => renderEntry(e, char))}
        </ul>
      </section>

      {BUCKETS.map((b) => (
        <div key={b}>{section(t(`character.turn.section_${b}`), groups[b], b)}</div>
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
            {sectionBody(t('character.turn.section_other'), groups.other)}
          </fieldset>
        )}
      </section>

      <GiveInspirationRow char={char} />

      {skillRoll && (
        <RollResultModal result={skillRoll.result} title={t(`character.skills.${skillRoll.skill}`)}
          afterRoll={{ charId, query: { roll: 'skill', skill: skillRoll.skill } }}
          onClose={() => setSkillRoll(null)} />
      )}
      {weaponFlow.elements}
      {castFlow.elements}
    </Layout>
  )
}

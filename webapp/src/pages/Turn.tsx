import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { ChevronDown, Clock, RotateCcw, Sparkles, Target } from 'lucide-react'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import RollButton from '@/components/ui/RollButton'
import WeaponChoiceRow from '@/components/WeaponChoiceRow'
import ActionsSkeleton from '@/components/skeletons/ActionsSkeleton'
import { useWeaponAttackFlow } from '@/hooks/useWeaponAttackFlow'
import { useTickRound } from '@/hooks/useTickRound'
import { useTurnState } from '@/hooks/useTurnState'
import { useCastFlow } from '@/pages/spells/useCastFlow'
import { useWeaponChoices, choiceOf } from '@/store/weaponChoiceStore'
import { groupForTurn, type TurnEntry } from '@/lib/turnGrouping'
import { STANDARD_ACTIONS } from '@/data/standardActions'
import type { CharacterFull } from '@/types'

type Bucket = 'action' | 'bonus_action' | 'reaction'
const BUCKETS: Bucket[] = ['action', 'bonus_action', 'reaction']
const NONE_USED: Record<Bucket, boolean> = { action: false, bonus_action: false, reaction: false }
const BTN = 'flex items-center gap-1 text-sm font-medium px-4 h-11 rounded-lg border active:scale-95 transition-transform'

export default function Turn() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const [used, setUsed] = useState(NONE_USED)
  const [otherOpen, setOtherOpen] = useState(false)
  const choices = useWeaponChoices((s) => s.choices)
  const setChoice = useWeaponChoices((s) => s.setChoice)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })
  const { data: session } = useQuery({ queryKey: ['session-me'], queryFn: () => api.sessions.me() })
  const { data: turn } = useTurnState(charId, session?.status === 'active')

  // Un nuovo turno (false -> true) azzera gli indicatori "usata".
  const wasMyTurn = useRef(false)
  const isMyTurn = !!turn?.is_my_turn
  useEffect(() => {
    if (isMyTurn && !wasMyTurn.current) setUsed(NONE_USED)
    wasMyTurn.current = isMyTurn
  }, [isMyTurn])

  const weaponFlow = useWeaponAttackFlow(charId, char)
  const castFlow = useCastFlow(charId, char)
  const tick = useTickRound(charId)

  const abilityUse = useMutation({
    mutationFn: ({ abilityId, uses }: { abilityId: number; uses: number }) =>
      api.abilities.update(charId, abilityId, { uses }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['character', charId] }),
  })

  if (!char) {
    return (
      <Layout title={t('character.turn.title')} backTo={`/char/${charId}`} group="combat" page="turn">
        <ActionsSkeleton />
      </Layout>
    )
  }

  const groups = groupForTurn(char)
  const lang = i18n.language?.startsWith('en') ? 'en' : 'it'
  const attacks = char.attacks_per_action ?? 1

  const renderEntry = (e: TurnEntry, c: CharacterFull) => {
    const key = `${e.kind}:${e.id}`
    if (e.kind === 'standard') {
      const std = STANDARD_ACTIONS.find((s) => s.id === e.id)
      return (
        <li key={key} className="py-2">
          <p className="font-cinzel text-dnd-gold">{std?.[lang].name ?? e.label}</p>
          <p className="text-xs text-dnd-text-muted">{std?.[lang].desc}</p>
        </li>
      )
    }
    let control: ReactNode = null
    let extra: ReactNode = null
    let label = e.label
    if (e.kind === 'weapon') {
      const crimson = `${BTN} bg-dnd-crimson/20 text-dnd-crimson-bright border-dnd-crimson/30`
      if (e.id === 'unarmed') {
        label = t('character.turn.unarmed')
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
        if (item) extra = <WeaponChoiceRow item={item} choice={choiceOf(choices, itemId)} onChange={(ch) => setChoice(itemId, ch)} />
      }
    } else if (e.kind === 'spell') {
      const spell = c.spells.find((s) => String(s.id) === e.id)
      if (spell) {
        control = (
          <RollButton onRoll={(mode) => castFlow.beginCast(spell, mode)} pending={castFlow.isSpellPending(spell.id)}
            ariaLabel={`${t('character.turn.cast')} ${label}`}
            className={`${BTN} bg-dnd-arcane/20 text-dnd-arcane-bright border-dnd-arcane/30`}>
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
            loading={abilityUse.isPending && abilityUse.variables?.abilityId === ab.id}
            onClick={() => abilityUse.mutate({ abilityId: ab.id, uses: Math.max(0, left - 1) })}>
            {left <= 0 ? t('character.turn.no_uses') : t('character.turn.use')}
          </Button>
        )
      }
    }
    return (
      <li key={key} className="py-2">
        <div className="flex items-center gap-3">
          <span className="flex-1 min-w-0 truncate">{label}</span>
          {control}
        </div>
        {extra}
      </li>
    )
  }

  const section = (title: string, entries: TurnEntry[], bucket?: Bucket) => (
    <Surface variant="elevated" className={bucket && used[bucket] ? 'opacity-60' : ''}>
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-cinzel uppercase tracking-widest text-xs text-dnd-gold-bright">{title}</h2>
        {bucket && (
          <Pressable
            aria-pressed={used[bucket]}
            aria-label={`${t('character.turn.mark_used')}: ${title}`}
            onClick={() => setUsed((u) => ({ ...u, [bucket]: !u[bucket] }))}
            className={`min-h-11 px-3 rounded-lg border text-xs font-medium ${
              used[bucket]
                ? 'bg-dnd-gold/20 border-dnd-gold-dim text-dnd-gold-bright'
                : 'bg-dnd-chip-bg border-dnd-border text-dnd-text-muted'}`}
          >
            {t('character.turn.used')}
          </Pressable>
        )}
      </div>
      {entries.length === 0
        ? <p className="text-sm text-dnd-text-muted py-2">{t('character.turn.empty')}</p>
        : <ul className="divide-y divide-dnd-border/40">{entries.map((e) => renderEntry(e, char))}</ul>}
    </Surface>
  )

  return (
    <Layout title={t('character.turn.title')} backTo={`/char/${charId}`} group="combat" page="turn">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <p className="text-sm text-dnd-text font-body tabular-nums">
          {t('character.turn.attacks_per_action', { n: attacks })}
          {turn?.in_encounter && turn.round != null && (
            <span className="ml-3 text-dnd-text-muted">{t('character.turn.round', { n: turn.round })}</span>
          )}
        </p>
        <div className="flex gap-2">
          {turn?.in_encounter ? (
            <p className="self-center text-xs text-dnd-text-muted font-body">{t('character.conditions.duration.in_encounter')}</p>
          ) : (
            <Button size="sm" variant="ghost" icon={<Clock size={14} />} loading={tick.isPending} onClick={() => tick.mutate()}>
              {t('character.turn.end_round')}
            </Button>
          )}
          <Button size="sm" variant="secondary" icon={<RotateCcw size={14} />} onClick={() => setUsed(NONE_USED)}>
            {t('character.turn.new_turn')}
          </Button>
        </div>
      </div>

      {BUCKETS.map((b) => (
        <div key={b}>{section(t(`character.turn.section_${b}`), groups[b], b)}</div>
      ))}

      <Pressable
        aria-expanded={otherOpen}
        onClick={() => setOtherOpen((o) => !o)}
        className="w-full min-h-11 flex items-center justify-between px-3 rounded-xl bg-dnd-surface border border-dnd-border text-dnd-text-muted"
      >
        <span className="font-cinzel uppercase tracking-widest text-xs">{t('character.turn.section_other')}</span>
        <ChevronDown size={16} className={otherOpen ? 'rotate-180' : ''} />
      </Pressable>
      {otherOpen && section(t('character.turn.section_other'), groups.other)}

      {weaponFlow.elements}
      {castFlow.elements}
    </Layout>
  )
}

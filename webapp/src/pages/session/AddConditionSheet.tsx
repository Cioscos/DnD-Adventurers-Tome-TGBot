import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { Minus, Plus } from 'lucide-react'
import Sheet from '@/components/ui/Sheet'
import SelectSheet from '@/components/ui/SelectSheet'
import ChipSelect from '@/components/ui/ChipSelect'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import IconButton from '@/components/ui/IconButton'
import SwitchToggle from '@/components/ui/SwitchToggle'
import { api, ApiError } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { formatCondition } from '@/lib/conditions'
import type { CharacterLiveSnapshot, CombatantLive, EncounterLive, GmConditionApply } from '@/types'

export const STANDARD_CONDITIONS = [
  'blinded', 'charmed', 'deafened', 'frightened', 'grappled',
  'incapacitated', 'invisible', 'paralyzed', 'petrified', 'poisoned',
  'prone', 'restrained', 'stunned', 'unconscious',
] as const
const ABILITIES = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']
const K = 'session.combat.cond'

type Duration = 'none' | 'rounds' | 'start' | 'end'

interface Props {
  sessionId: number
  encounter: EncounterLive
  target: CombatantLive
  liveCharacters: CharacterLiveSnapshot[]
  onClose: () => void
}

export default function AddConditionSheet({ sessionId, encounter, target, liveCharacters, onClose }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const snapOf = (c?: CombatantLive) =>
    c?.kind === 'pc' ? liveCharacters.find((s) => s.id === c.character_id) : undefined
  const targetConds = (target.kind === 'pc' ? snapOf(target)?.conditions : target.conditions) ?? {}
  const currentExhaustion = Number(targetConds.exhaustion) || 0

  const [slug, setSlug] = useState('')
  const [level, setLevel] = useState(Math.max(1, currentExhaustion))
  const [duration, setDuration] = useState<Duration>('none')
  const [rounds, setRounds] = useState('1')
  const [of, setOf] = useState<'target' | 'source'>('target')
  const [ability, setAbility] = useState('none')
  const [dc, setDc] = useState('')
  const [saveEdge, setSaveEdge] = useState<'start' | 'end'>('end')
  const [sourceId, setSourceId] = useState('none')
  const [conc, setConc] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const source = encounter.combatants.find((c) => String(c.id) === sourceId)
  const showConc = Boolean(snapOf(source)?.is_concentrating)
  const isExhaustion = slug === 'exhaustion'
  const anchor = of === 'source' && source ? 'source' : 'owner'

  const conditionOptions = [
    ...STANDARD_CONDITIONS.map((s) => ({ value: s, label: formatCondition(s, true, t) })),
    { value: 'exhaustion', label: t('character.conditions.exhaustion_condition') },
    ...Object.keys(targetConds)
      .filter((k) => k.startsWith('custom:') && targetConds[k])
      .map((k) => ({ value: k, label: k.slice('custom:'.length) })),
  ]
  const sourceOptions = [
    { value: 'none', label: t(`${K}.source_none`) },
    ...encounter.combatants
      .filter((c) => c.id !== target.id)
      .map((c) => ({ value: String(c.id), label: c.name })),
  ]

  const roundsN = Number(rounds)
  const dcN = Number(dc)
  const valid = slug !== '' && (isExhaustion || (
    (duration !== 'rounds' || (Number.isInteger(roundsN) && roundsN >= 1 && roundsN <= 100))
    && (ability === 'none' || (Number.isInteger(dcN) && dcN >= 1 && dcN <= 40))
  ))

  const buildBody = (): GmConditionApply => {
    if (isExhaustion) return { slug, value: level }
    const body: GmConditionApply = { slug }
    if (duration === 'rounds') body.expiry = { anchor: 'owner', edge: 'start', count: roundsN }
    else if (duration !== 'none') body.expiry = { anchor, edge: duration, count: 1 }
    if (ability !== 'none') body.save = { ability, dc: dcN, edge: saveEdge }
    if (source) body.source_combatant_id = source.id
    body.ends_with_concentration = showConc && conc
    return body
  }

  const mutation = useMutation({
    mutationFn: (body: GmConditionApply) => api.sessions.encounter.applyCondition(sessionId, target.id, body),
    onSuccess: () => {
      haptic.success()
      qc.invalidateQueries({ queryKey: ['session-live', sessionId] })
      onClose()
    },
    onError: (err) => {
      haptic.error()
      const code = err instanceof ApiError && err.status === 422
        ? (err.detail as { code?: string } | null)?.code
        : undefined
      if (code === 'source_not_concentrating') setError(t(`${K}.source_not_concentrating`))
      else toast.error(t('session.combat.action_failed'))
    },
  })

  return (
    <Sheet open onClose={onClose} title={`${t('session.combat.add_condition')} · ${target.name}`} zClassName="z-[60]">
      <div className="p-5 space-y-4">
        <SelectSheet
          label={t(`${K}.condition`)}
          options={conditionOptions}
          value={slug}
          onChange={(v) => { setSlug(v); setError(null) }}
          placeholder={t(`${K}.pick`)}
          zClassName="z-[70]"
        />

        {isExhaustion && (
          <div className="flex items-center gap-3">
            <p className="flex-1 text-xs uppercase tracking-wider text-dnd-gold-dim font-cinzel">
              {t('character.conditions.exhaustion_level')}
            </p>
            <IconButton
              icon={<Minus size={16} />} aria-label="-" variant="secondary"
              disabled={level <= 1} onClick={() => setLevel((l) => l - 1)}
            />
            <span className="w-6 text-center font-mono tabular-nums text-lg text-dnd-text">{level}</span>
            <IconButton
              icon={<Plus size={16} />} aria-label="+" variant="secondary"
              disabled={level >= 6} onClick={() => setLevel((l) => l + 1)}
            />
          </div>
        )}

        {slug !== '' && !isExhaustion && (
          <>
            <SelectSheet
              label={t(`${K}.source`)}
              options={sourceOptions}
              value={sourceId}
              onChange={(v) => { setSourceId(v); setError(null) }}
              zClassName="z-[70]"
            />
            {showConc && (
              <SwitchToggle checked={conc} onChange={setConc} label={t(`${K}.concentration`)} />
            )}

            <ChipSelect
              label={t(`${K}.duration`)}
              columns={2}
              value={duration}
              onChange={(v) => setDuration(v as Duration)}
              options={(['none', 'rounds', 'start', 'end'] as const).map((d) => ({
                value: d, label: t(`${K}.dur_${d}`),
              }))}
            />
            {duration === 'rounds' && (
              <Input
                label={t(`${K}.rounds_label`)} type="number" inputMode="numeric"
                min={1} max={100} value={rounds} onChange={setRounds} className="font-mono"
              />
            )}
            {(duration === 'start' || duration === 'end') && (
              <ChipSelect
                label={t(`${K}.of_label`)}
                columns={2}
                value={anchor === 'source' ? 'source' : 'target'}
                onChange={(v) => setOf(v as 'target' | 'source')}
                options={[
                  { value: 'target', label: t(`${K}.of_target`) },
                  { value: 'source', label: t(`${K}.of_source`), disabled: !source },
                ]}
              />
            )}

            <ChipSelect
              label={t(`${K}.save`)}
              columns={4}
              value={ability}
              onChange={setAbility}
              options={[
                { value: 'none', label: t(`${K}.save_none`) },
                ...ABILITIES.map((a) => ({ value: a, label: t(`character.ability.${a}_short`) })),
              ]}
            />
            {ability !== 'none' && (
              <div className="flex gap-2 items-end">
                <div className="w-24 shrink-0">
                  <Input
                    label={t(`${K}.save_dc`)} type="number" inputMode="numeric"
                    min={1} max={40} value={dc} onChange={setDc} className="text-center font-mono"
                  />
                </div>
                <ChipSelect
                  className="flex-1"
                  columns={2}
                  value={saveEdge}
                  onChange={(v) => setSaveEdge(v as 'start' | 'end')}
                  options={[
                    { value: 'start', label: t(`${K}.save_edge_start`) },
                    { value: 'end', label: t(`${K}.save_edge_end`) },
                  ]}
                />
              </div>
            )}
          </>
        )}

        {error && <p role="alert" className="text-sm text-dnd-crimson-bright">{error}</p>}

        <Button
          fullWidth
          disabled={!valid}
          loading={mutation.isPending}
          onClick={() => { setError(null); mutation.mutate(buildBody()) }}
        >
          {t(`${K}.submit`)}
        </Button>
      </div>
    </Sheet>
  )
}

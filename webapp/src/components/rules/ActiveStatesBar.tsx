import { useTranslation } from 'react-i18next'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { GiLightningTrio } from 'react-icons/gi'
import { api } from '@/api/client'
import Button from '@/components/ui/Button'
import { notifyMutationError } from '@/lib/mutationError'
import { bonusSpentOnReturn } from '@/lib/formReturn'
import { formatRounds } from '@/lib/spellDuration'
import { useToast } from '@/hooks/useToast'
import type { CharacterFull } from '@/types'

type StateRow = NonNullable<CharacterFull['active_states']>[number]

/** I numeri che uno stato porta con sé e che il giocatore deve poter leggere: CD del TS, GS, danno fisso, esito. */
function stateFacts(s: StateRow, t: (k: string, o?: Record<string, unknown>) => string, charId: number): string[] {
  const d = (s.data ?? {}) as Record<string, unknown>
  const out: string[] = []
  const clock = s.key.startsWith('spell_cast:')
  if (clock || s.key.startsWith('spell:')) {
    // Effetto di un incantesimo: lo scandisce l'orologio del lanciatore (`spell_cast:`), qui si legge da chi viene e quanto dura.
    if (clock) out.push(t('character.turn.state_cast_by_you'))
    else if (typeof d.caster_name === 'string' && d.caster_id !== charId) out.push(t('character.turn.state_from', { name: d.caster_name }))
    const dur = (clock ? (d.state_data as { duration?: unknown } | undefined)?.duration : d.duration) as
      { rounds?: number | null; concentration?: boolean; until_rest?: boolean } | undefined
    if (dur?.until_rest) out.push(t('character.turn.state_until_rest'))
    else if (dur?.concentration) out.push(t('character.turn.state_while_concentrating'))
    else if (dur?.rounds) out.push(formatRounds(t, dur.rounds))
  }
  if (typeof d.dc === 'number') {
    out.push(t('character.turn.state_dc', { dc: d.dc, save: typeof d.save === 'string' ? t(`common.abilities.${d.save}`) : '' }))
  }
  const skill = d.skill ?? (d.choices as { skill?: unknown } | undefined)?.skill  // gli incantesimi tengono la scelta in `choices`
  if (typeof skill === 'string') out.push(t(`character.skills.${skill}`))
  if (typeof d.damage_type === 'string') out.push(t(`character.inventory.damage_types.dmg_${d.damage_type}`))
  if (d.maximized === true) out.push(t('character.turn.state_maximized'))
  if (typeof d.cr === 'string') out.push(t('character.turn.state_cr', { cr: d.cr }))
  if (typeof d.attack_bonus === 'number') out.push(t('character.turn.state_attack_bonus', { n: d.attack_bonus }))
  if (typeof d.bonus === 'number') out.push(t('character.turn.state_bonus', { n: d.bonus }))
  if (typeof d.range_m === 'number') out.push(t('character.turn.state_radius', { n: d.range_m }))
  if (typeof d.radius_m === 'number') out.push(t('character.turn.state_radius', { n: d.radius_m }))
  if (typeof d.radius_km === 'number') out.push(t('character.turn.state_radius_km', { n: String(d.radius_km).replace('.', ',') }))
  if (typeof d.ac_bonus === 'number') out.push(t('character.turn.state_ac_bonus', { n: d.ac_bonus }))
  if (typeof d.stealth_bonus === 'number') out.push(t('character.turn.state_stealth_bonus', { n: d.stealth_bonus }))
  if (typeof d.fly_ft === 'number') out.push(t('character.turn.state_fly', { n: Math.round(d.fly_ft * 0.3) }))
  if (typeof d.start_heal === 'number') out.push(t('character.turn.state_start_heal', { n: d.start_heal }))
  if (typeof d.start_damage === 'number') out.push(t('character.turn.state_start_damage', { n: d.start_damage }))
  if (typeof d.hp === 'number' && typeof d.max === 'number') out.push(t('character.turn.state_ward', { hp: d.hp, max: d.max }))
  if (typeof d.object === 'string') out.push(d.object)
  if (typeof d.uses === 'number') out.push(t('character.turn.state_uses', { n: d.uses }))
  for (const k of ['option', 'benefit', 'intelligence'] as const) {
    if (typeof d[k] === 'string') out.push(t(`character.turn.state_option.${d[k]}`))
  }
  if (d.until === 'next_turn_end') out.push(t('character.turn.state_until_next_turn_end'))
  if (typeof d.duplicates === 'number') out.push(t('character.turn.state_duplicates', { n: d.duplicates }))
  if (s.key === 'divine_intervention') {
    out.push(t(d.success ? 'character.turn.divine_success' : 'character.turn.divine_failure', { roll: d.roll ?? '-', level: d.level }))
  }
  if (s.key === 'greater_divine_intervention' && Array.isArray(d.roll)) {
    out.push(t('character.turn.wish_lock', { roll: d.roll.join('+'), n: d.rests_left }))
  }
  return out
}

/** Stati attivi dei privilegi (Ira...) con i round rimasti e la chiusura a mano. Niente se non ce n'è nessuno. */
export default function ActiveStatesBar({ char }: { char: CharacterFull }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const end = useMutation({
    mutationFn: (key: string) => api.characters.endActiveState(char.id, key),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', char.id] })
      qc.invalidateQueries({ queryKey: ['companions', char.id] })  // chiudere la Forma Selvatica la chiude anche nei compagni
    },
    onError: (err) => {
      if (bonusSpentOnReturn(err)) toast.error(t('character.extras.return_bonus_used'))
      else notifyMutationError()
    },
  })
  // Dado di Ispirazione in Combattimento alla CA: in reazione, il valore da sommare lo dice il server.
  const acBoost = useMutation({
    mutationFn: () => api.characters.bardicDieAc(char.id),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['character', char.id] })
      qc.invalidateQueries({ queryKey: ['turn-state', char.id] })
      toast.info(t('character.turn.bardic_die_ac_result'), { description: `+${res.roll}` })
    },
    onError: () => notifyMutationError(),
  })
  // Prolungare l'Ira con un TS imposto non costa l'azione bonus: il bottone sta qui, fuori dalla sezione che si richiude.
  const extend = useMutation({
    mutationFn: (featureKey: string) => api.characters.featureUse(char.id, featureKey, 1, { extend_via: 'save' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', char.id] })
      qc.invalidateQueries({ queryKey: ['turn-state', char.id] })
      toast.info(t('character.turn.extend_rage_done'))
    },
    onError: () => notifyMutationError(),
  })
  // I segni interni di un privilegio (il Canto di Riposo già ricevuto) non sono del giocatore: né si vedono né si chiudono.
  const states = (char.active_states ?? []).filter((s) => !s.data?.internal)
  if (states.length === 0) return null
  return (
    <ul className="mt-3 flex flex-col gap-2">
      {states.map((s) => {
        // Il dado ricevuto non ha una riga sulla scheda di chi lo riceve: il nome salvato è nella lingua del bardo, si traduce qui.
        const name = s.key === 'bardic_die' ? t('character.turn.bardic_die_name')
          : char.abilities.find((a) => a.feature_key === s.feature_key)?.name ?? s.name ?? t('character.turn.state_generic')
        // Privilegi che agiscono su altri (Lupo, Orso, Attacco Irruento): il testo sta sotto lo stato, il GM li applica (D1).
        const others = ((s.data?.others as string[] | undefined) ?? [])
          .map((k) => char.abilities.find((a) => a.feature_key === k))
          .filter((a): a is NonNullable<typeof a> => !!a)
        const facts = stateFacts(s, t, char.id)
        // Lo decide il server: la scelta di prolungamento c'è solo finché l'Ira si può prolungare (non dal 15°, non per le altre classi).
        const canExtend = !!s.feature_key && !!char.abilities.find((a) => a.feature_key === s.feature_key)?.use_choices?.some((x) => x.key === 'extend_via')
        return (
          <li key={s.key} className="flex flex-wrap items-center gap-2 px-3 py-2 rounded-xl border border-dnd-gold-dim/50 bg-dnd-gold/10">
            <GiLightningTrio size={16} aria-hidden className="shrink-0 text-dnd-gold-bright" />
            <div className="flex-1 min-w-[9rem] text-sm font-body text-dnd-text break-words">
              <p>
                {name}
                {typeof s.data?.die === 'number' && (
                  <span className="ml-2 font-mono text-dnd-text-muted">d{s.data.die}</span>
                )}
                {s.rounds_left != null && (
                  <span className="ml-2 text-dnd-text-muted tabular-nums">{s.rounds_left > 10 ? formatRounds(t, s.rounds_left) : t('character.turn.state_rounds_left', { n: s.rounds_left })}</span>
                )}
              </p>
              {facts.length > 0 && <p className="mt-0.5 text-xs text-dnd-text-muted tabular-nums">{facts.join(' · ')}</p>}
              {others.map((a) => (
                <p key={a.id} className="mt-0.5 text-xs text-dnd-text-muted">{a.name}: {a.description}</p>
              ))}
            </div>
            {s.key === 'bardic_die' && s.data?.combat === true && (
              <Button size="sm" variant="secondary" className="min-h-11 shrink-0"
                loading={acBoost.isPending} onClick={() => acBoost.mutate()}>
                {t('character.turn.bardic_die_ac')}
              </Button>
            )}
            {canExtend && (
              <Button size="sm" variant="secondary" className="min-h-11 shrink-0"
                loading={extend.isPending} onClick={() => extend.mutate(s.feature_key as string)}>
                {t('character.turn.extend_rage_save')}
              </Button>
            )}
            {/* L'interdizione e la Saturazione Magica le chiude solo il riposo lungo: il server rifiuta, qui non si offre */}
            {s.data?.locked !== true && (
              <Button size="sm" variant="secondary" className="min-h-11 shrink-0"
                loading={end.isPending && end.variables === s.key} onClick={() => end.mutate(s.key)}>
                {t('character.turn.end_state')}
              </Button>
            )}
          </li>
        )
      })}
    </ul>
  )
}

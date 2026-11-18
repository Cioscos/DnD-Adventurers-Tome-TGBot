import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import SwitchToggle from '@/components/ui/SwitchToggle'
import RestPreviewList from '@/components/character/RestPreviewList'
import SongOfRestToggle from '@/components/character/SongOfRestToggle'
import NaturalRecoveryPicker, { ArcaneRecoveryPicker } from '@/components/character/NaturalRecoveryPicker'
import MemorizeSpellPicker from '@/components/character/MemorizeSpellPicker'
import SorcerousRestorationPicker from '@/components/character/SorcerousRestorationPicker'
import TomeReopenToggle from '@/components/character/TomeReopenToggle'
import RestResistancePicker from '@/components/character/RestResistancePicker'
import RestAllyTempPicker from '@/components/character/RestAllyTempPicker'
import HitDiceModal from '@/pages/hp/HitDiceModal'
import HitDiceResultDialog from '@/pages/hp/HitDiceResultDialog'
import { restNeedsHp } from '@/lib/restRules'
import { hpIsFull } from '@/lib/quickActions'
import type { RestState } from '@/hooks/useRest'
import type { CharacterFull } from '@/types'

/** Le domande del riposo (breve: dadi vita e scelte; lungo: conferma, «troppo presto»), per `useRest`. */
export default function RestDialogs({ char, rest }: { char: CharacterFull; rest: RestState }) {
  const { t } = useTranslation()
  const is2024 = char.rules_edition === '2024'
  const { restMutation, hitDieMutation, startRest } = rest
  const longBlocked = restNeedsHp(char, 'long')
  const shortBlocked = restNeedsHp(char, 'short')
  // Stessa query dell'anteprima (cache condivisa): «troppo presto» si sa già nel primo modale, non dopo un 409.
  const { data: longPreview } = useQuery({
    queryKey: ['rest-preview', char.id, 'long'],
    queryFn: () => api.characters.restPreview(char.id, 'long'),
    enabled: rest.confirmLongRest && !longBlocked,
    gcTime: 0,
  })
  const longTooSoon = rest.confirmLongRest && !!longPreview?.too_soon
  const tooSoonHours = is2024 ? 16 : 24
  const elapsed = longPreview?.hours_since_long_rest
  const tooSoonText = elapsed != null
    ? t('character.quick_actions.rest_too_soon_elapsed', { elapsed, hours: tooSoonHours })
    : t('character.quick_actions.rest_too_soon_body', { hours: tooSoonHours })
  // Anteprima dei PF dai dadi vita già tirati (dado + COS, minimo 0/1 per edizione; il server tiene conto anche di Tenace e Canto)
  const hpMax = char.computed?.hp_max_effective ?? char.hit_points + (char.hp_max_homebrew_modifier ?? 0)
  const con = char.ability_scores?.find((a) => a.name === 'constitution')?.modifier ?? 0
  const rolled = Object.values(rest.pendingDice).flat()
  const hpGain = Math.min(Math.max(0, hpMax - char.current_hit_points), rolled.reduce((n, r) => n + Math.max(is2024 ? 1 : 0, r + con), 0))

  const interruptedToggle = (hint: string) => (
    <div className="text-left">
      <SwitchToggle
        checked={rest.interrupted}
        onChange={rest.setInterrupted}
        label={t('character.quick_actions.rest_interrupted')}
        hint={hint}
      />
    </div>
  )

  return (
    <>
      <ConfirmSheet
        open={rest.confirmLongRest}
        onClose={rest.cancelLongRest}
        title={t('character.quick_actions.confirm_long_rest_title')}
        body={
          <div className="space-y-3">
            <p>{t('character.quick_actions.confirm_long_rest_body')}</p>
            {longTooSoon && (
              <p data-testid="rest-too-soon" className="text-sm text-dnd-amber font-body">
                {tooSoonText}
              </p>
            )}
            {rest.confirmLongRest && (longBlocked
              ? <p className="text-sm text-dnd-crimson-bright font-body">{t('character.quick_actions.rest_needs_hp')}</p>
              : <RestPreviewList charId={char.id} restType="long" />)}
            <TomeReopenToggle char={char} value={rest.reopenTome} onChange={rest.setReopenTome} />
            <RestResistancePicker char={char} value={rest.resistance} onChange={rest.setResistance} />
            <RestAllyTempPicker char={char} value={rest.tempAllies} onChange={rest.setTempAllies} />
            {interruptedToggle(t(is2024
              ? 'character.quick_actions.rest_interrupted_long_2024'
              : 'character.quick_actions.rest_interrupted_long_2014'))}
            {!is2024 && (
              <div className="text-left">
                <SwitchToggle
                  checked={rest.ateAndDrank}
                  onChange={rest.setAteAndDrank}
                  label={t('character.quick_actions.rest_ate_and_drank')}
                  hint={t('character.quick_actions.rest_ate_and_drank_hint')}
                />
              </div>
            )}
          </div>
        }
        confirmLabel={t(longTooSoon ? 'character.quick_actions.rest_anyway' : 'character.quick_actions.rest_long')}
        confirmVariant="primary"
        loading={restMutation.isPending}
        confirmDisabled={longBlocked}
        onConfirm={() => startRest({ restType: 'long', confirmEarly: longTooSoon || undefined })}
      />

      <ConfirmSheet
        open={rest.tooSoon}
        onClose={() => { rest.setTooSoon(false); rest.cancelLongRest() }}
        title={t('character.quick_actions.rest_too_soon_title')}
        body={<p>{tooSoonText}</p>}
        confirmLabel={t('character.quick_actions.rest_anyway')}
        confirmVariant="primary"
        loading={restMutation.isPending}
        onConfirm={() => startRest({ restType: 'long', confirmEarly: true })}
      />

      {rest.shortRestOpen && (
        <HitDiceModal
          classes={char.classes ?? []}
          onSpend={(classId, count) => hitDieMutation.mutate({ classId, count })}
          onConfirmRest={() => startRest({ restType: 'short' })}
          restBlocked={shortBlocked}
          pendingRolls={rest.pendingDice}
          hpFull={hpIsFull(char)}
          preview={
            <>
              {rolled.length > 0 && !shortBlocked && (
                <p data-testid="rest-hp-gain" className="text-sm text-dnd-emerald-bright font-body text-left tabular-nums">
                  {t('character.quick_actions.rest_hp_gain', { n: hpGain, hp: char.current_hit_points + hpGain, max: hpMax })}
                </p>
              )}
              {shortBlocked
                ? <p className="text-sm text-dnd-crimson-bright font-body text-left">{t('character.quick_actions.rest_needs_hp')}</p>
                : <RestPreviewList charId={char.id} restType="short" />}
              <SongOfRestToggle char={char} />
              <NaturalRecoveryPicker char={char} value={rest.recovery} onChange={rest.setRecovery} />
              <ArcaneRecoveryPicker char={char} value={rest.arcane} onChange={rest.setArcane} />
              <SorcerousRestorationPicker char={char} value={rest.restoration} onChange={rest.setRestoration} />
              <MemorizeSpellPicker char={char} onChange={rest.setMemorize} />
              <RestResistancePicker char={char} value={rest.resistance} onChange={rest.setResistance} />
              <RestAllyTempPicker char={char} value={rest.tempAllies} onChange={rest.setTempAllies} />
              {is2024 && interruptedToggle(t('character.quick_actions.rest_interrupted_short_2024'))}
            </>
          }
          onClose={rest.closeShort}
          isPending={hitDieMutation.isPending}
          pendingClassId={hitDieMutation.isPending ? hitDieMutation.variables?.classId : undefined}
          restPending={restMutation.isPending}
        />
      )}

      {rest.hitDieResult && (
        <HitDiceResultDialog result={rest.hitDieResult} onClose={() => rest.setHitDieResult(null)} />
      )}
    </>
  )
}

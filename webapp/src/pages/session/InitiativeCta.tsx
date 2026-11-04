import { askRollOptions, refreshAfterOptions } from '@/lib/rollOptions'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { GiPerspectiveDiceSixFacesRandom as Dices } from 'react-icons/gi'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { useD20Roll, d20Arg, type RollMode } from '@/hooks/useD20Roll'
import AfterRollOptions from '@/components/rules/AfterRollOptions'
import RollButton from '@/components/ui/RollButton'
import { useRollNoteLabels } from '@/hooks/useRollNoteLabels'
import type { CombatantLive } from '@/types'

interface Props {
  sessionId: number
  combatant: CombatantLive
}

export default function InitiativeCta({ sessionId, combatant }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const rollD20 = useD20Roll()
  const noteLabels = useRollNoteLabels(combatant.character_id ?? undefined)

  const rollMutation = useMutation({
    mutationFn: async (mode: RollMode) => {
      const choice = combatant.character_id == null
        ? undefined
        : await askRollOptions(combatant.character_id, { roll: 'initiative' })
      return api.sessions.encounter.rollInitiative(sessionId, combatant.id, d20Arg(mode, await rollD20(mode), choice))
    },
    onSuccess: (live) => {
      haptic.success()
      if (live.initiative_roll?.notes.length) toast.info(noteLabels(live.initiative_roll.notes).join(' · '))
      if (combatant.character_id != null) refreshAfterOptions(qc, combatant.character_id, live.initiative_roll?.option_result)
      qc.invalidateQueries({ queryKey: ['session-live', sessionId] })
    },
    onError: () => {
      haptic.error()
      toast.error(t('session.combat.roll_failed'))
    },
  })

  if (combatant.initiative !== null) {
    return (
      <div>
        <p className="text-center text-sm font-mono tabular-nums text-dnd-gold-bright">
          {combatant.initiative_die !== null
            ? t('session.combat.rolled_detail', {
                die: combatant.initiative_die,
                mod: combatant.initiative_mod,
                total: combatant.initiative,
              })
            : t('session.combat.rolled_total', { total: combatant.initiative })}
        </p>
        <p className="text-center text-xs text-dnd-text-muted font-body italic mt-1">
          {t('session.combat.waiting_others')}
        </p>
        {/* Solo il tiro appena fatto è l'ultimo: riaperta più tardi la riga non ha senso. */}
        {rollMutation.isSuccess && combatant.character_id != null && (
          <div className="mt-3">
            <AfterRollOptions
              charId={combatant.character_id}
              query={{ roll: 'initiative' }}
              rollToken={rollMutation.data}
              onResult={() => qc.invalidateQueries({ queryKey: ['session-live', sessionId] })}
            />
          </div>
        )}
      </div>
    )
  }

  return (
    <div>
      <RollButton
        onRoll={(mode) => rollMutation.mutate(mode)}
        pending={rollMutation.isPending}
        ariaLabel={t('session.combat.roll_initiative')}
        className="w-full min-h-[48px] px-4 py-3 rounded-xl flex items-center justify-center gap-2 text-sm font-bold bg-dnd-gold text-dnd-ink"
      >
        <Dices size={18} />
        {t('session.combat.roll_initiative')}
      </RollButton>
    </div>
  )
}

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { GiPerspectiveDiceSixFacesRandom as Dices } from 'react-icons/gi'
import Surface from '@/components/ui/Surface'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { useD20Roll, d20Arg, type RollMode } from '@/hooks/useD20Roll'
import RollButton from '@/components/ui/RollButton'
import type { CombatantLive } from '@/types'

interface Props {
  sessionId: number
  combatant: CombatantLive
}

export default function InitiativeCta({ sessionId, combatant }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const rollD20 = useD20Roll()

  const rollMutation = useMutation({
    mutationFn: async (mode: RollMode) =>
      api.sessions.encounter.rollInitiative(sessionId, combatant.id, d20Arg(mode, await rollD20(mode))),
    onSuccess: () => {
      haptic.success()
      qc.invalidateQueries({ queryKey: ['session-live', sessionId] })
    },
    onError: () => {
      haptic.error()
      toast.error(t('session.combat.roll_failed'))
    },
  })

  if (combatant.initiative !== null) {
    return (
      <Surface variant="elevated">
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
      </Surface>
    )
  }

  return (
    <Surface variant="ember" ornamented>
      <p className="text-center text-xs uppercase tracking-widest text-dnd-gold-dim font-cinzel mb-2">
        {t('session.combat.initiative')}
      </p>
      <RollButton
        onRoll={(mode) => rollMutation.mutate(mode)}
        pending={rollMutation.isPending}
        ariaLabel={t('session.combat.roll_initiative')}
        className="w-full min-h-[48px] px-4 py-3 rounded-xl flex items-center justify-center gap-2 text-sm font-bold bg-gradient-gold text-dnd-ink shadow-engrave"
      >
        <Dices size={18} />
        {t('session.combat.roll_initiative')}
      </RollButton>
    </Surface>
  )
}

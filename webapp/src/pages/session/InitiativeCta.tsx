import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { GiPerspectiveDiceSixFacesRandom as Dices } from 'react-icons/gi'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { useDiceAnimation } from '@/dice/useDiceAnimation'
import { useDiceSettings } from '@/store/diceSettings'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import type { CombatantLive } from '@/types'

interface Props {
  sessionId: number
  combatant: CombatantLive
}

export default function InitiativeCta({ sessionId, combatant }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const dice = useDiceAnimation()
  const animate3d = useDiceSettings((s) => s.animate3d)
  const reducedMotion = useReducedMotion()

  const rollMutation = useMutation({
    mutationFn: async () => {
      let die: number | undefined
      if (animate3d && !reducedMotion) {
        const detected = await dice.playAndCollect([{ kind: 'd20', count: 1 }])
        die = detected[0]?.value
      }
      return api.sessions.encounter.rollInitiative(sessionId, combatant.id, die)
    },
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
      <Button
        variant="primary"
        size="md"
        fullWidth
        icon={<Dices size={18} />}
        loading={rollMutation.isPending}
        onClick={() => rollMutation.mutate()}
      >
        {t('session.combat.roll_initiative')}
      </Button>
    </Surface>
  )
}

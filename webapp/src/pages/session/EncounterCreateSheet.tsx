import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import Sheet from '@/components/ui/Sheet'
import Pressable from '@/components/ui/Pressable'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import type { EncounterMode } from '@/types'

interface Props {
  sessionId: number
  onClose: () => void
}

export default function EncounterCreateSheet({ sessionId, onClose }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()

  const createMutation = useMutation({
    mutationFn: (mode: EncounterMode) => api.sessions.encounter.create(sessionId, mode),
    onSuccess: () => {
      haptic.success()
      qc.invalidateQueries({ queryKey: ['session-live', sessionId] })
      onClose()
    },
    onError: () => {
      haptic.error()
      toast.error(t('session.combat.action_failed'))
    },
  })

  const modes: Array<{ mode: EncounterMode; label: string; desc: string }> = [
    { mode: 'light', label: t('session.combat.mode_light'), desc: t('session.combat.mode_light_desc') },
    { mode: 'full', label: t('session.combat.mode_full'), desc: t('session.combat.mode_full_desc') },
  ]

  return (
    <Sheet open onClose={onClose} title={t('session.combat.mode_title')}>
      <div className="p-1 space-y-3">
        {modes.map(({ mode, label, desc }) => (
          <Pressable
            key={mode}
            disabled={createMutation.isPending && createMutation.variables !== mode}
            pending={createMutation.isPending && createMutation.variables === mode}
            onClick={() => createMutation.mutate(mode)}
            className="w-full min-h-[48px] text-left rounded-lg border border-dnd-border bg-dnd-surface
                       p-3 hover:border-dnd-gold-bright active:opacity-80 disabled:opacity-40
                       transition-colors"
          >
            <p className="font-display font-bold text-dnd-gold-bright">{label}</p>
            <p className="text-xs text-dnd-text-muted font-body mt-0.5">{desc}</p>
          </Pressable>
        ))}
      </div>
    </Sheet>
  )
}

import { useTranslation } from 'react-i18next'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { GiPawPrint } from 'react-icons/gi'
import { api } from '@/api/client'
import Button from '@/components/ui/Button'
import { notifyMutationError } from '@/lib/mutationError'
import type { ActiveForm } from '@/types'

/** "In forma di <nome>" with the one-tap exit from Wild Shape. */
export default function ActiveFormBanner({ charId, form }: { charId: number; form: ActiveForm }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const end = useMutation({
    mutationFn: () => api.companions.deactivate(charId, form.companion_id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      qc.invalidateQueries({ queryKey: ['companions', charId] })
    },
    onError: () => notifyMutationError(),
  })
  return (
    <div className="mt-3 flex items-center gap-2 px-3 py-2 rounded-xl border border-dnd-emerald/50 bg-dnd-emerald/10">
      <GiPawPrint size={16} aria-hidden className="shrink-0 text-dnd-emerald-bright" />
      <p className="flex-1 min-w-0 text-sm font-body text-dnd-text break-words">
        {t('character.extras.in_form_of', { name: form.name })}
      </p>
      <Button size="sm" variant="secondary" className="min-h-11 shrink-0" loading={end.isPending} onClick={() => end.mutate()}>
        {t('character.extras.end_form')}
      </Button>
    </div>
  )
}

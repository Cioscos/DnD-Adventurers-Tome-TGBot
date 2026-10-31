import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Plus } from 'lucide-react'
import { api, ApiError } from '@/api/client'
import Layout from '@/components/Layout'
import Button from '@/components/ui/Button'
import EmptyState from '@/components/ui/EmptyState'
import ActionsSkeleton from '@/components/skeletons/ActionsSkeleton'
import CompanionCard from '@/pages/extras/CompanionCard'
import CompanionForm from '@/pages/extras/CompanionForm'
import { KINDS } from '@/lib/companionRules'
import { useToast } from '@/hooks/useToast'
import { notifyMutationError } from '@/lib/mutationError'
import { haptic } from '@/auth/telegram'
import type { CompanionPayload } from '@/types'

export default function Extras() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const [adding, setAdding] = useState(false)

  const { data: char } = useQuery({ queryKey: ['character', charId], queryFn: () => api.characters.get(charId) })
  const { data: companions } = useQuery({ queryKey: ['companions', charId], queryFn: () => api.companions.list(charId) })

  const create = useMutation({
    mutationFn: (body: CompanionPayload) => api.companions.create(charId, body),
    onSuccess: () => { haptic.success(); setAdding(false); qc.invalidateQueries({ queryKey: ['companions', charId] }) },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 422 && err.detail === 'companion_limit') toast.error(t('character.extras.limit'))
      else notifyMutationError()
    },
  })

  const title = t('character.extras.title')
  if (!char || !companions) {
    return <Layout title={title} backTo={`/char/${charId}`} group="character" page="extras"><ActionsSkeleton /></Layout>
  }

  const druid = char.classes.find((c) => c.class_name.toLowerCase() === 'druid')
  const druidLevel = druid?.level ?? 0
  const isMoon = /moon|luna/i.test(druid?.subclass ?? '')
  const ws = char.abilities.find((a) => a.feature_key === 'druid.wild_shape')
  const wsUses = ws ? ws.uses ?? 0 : null

  return (
    <Layout title={title} backTo={`/char/${charId}`} group="character" page="extras">
      <div className="p-4 space-y-4">
        <Button fullWidth className="min-h-11" icon={<Plus size={16} />} onClick={() => setAdding(true)}>
          {t('character.extras.add')}
        </Button>
        {companions.length === 0 && <EmptyState title={t('character.extras.empty')} />}
        {KINDS.map((kind) => {
          const rows = companions.filter((c) => c.kind === kind)
          if (rows.length === 0) return null
          return (
            <section key={kind} className="space-y-2">
              <h2 className="text-xs font-cinzel uppercase tracking-[0.25em] text-dnd-gold-dim">
                {t(`character.extras.kinds.${kind}`)}
              </h2>
              {rows.map((c) => <CompanionCard key={c.id} charId={charId} comp={c} wildShapeUses={wsUses} />)}
            </section>
          )
        })}
      </div>
      {adding && (
        <CompanionForm druidLevel={druidLevel} isMoon={isMoon} pending={create.isPending}
          onSubmit={(b) => create.mutate(b)} onClose={() => setAdding(false)} />
      )}
    </Layout>
  )
}

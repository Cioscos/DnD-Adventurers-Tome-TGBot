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
import { classKey } from '@/lib/classProgression'
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
      else if (err instanceof ApiError && err.status === 422 && err.detail === 'known_forms_limit') toast.error(t('character.extras.known_forms_limit'))
      else if (err instanceof ApiError && err.status === 422 && (err.detail === 'companion_exists' || err.detail === 'feature_unavailable')) toast.error(t(`character.extras.beast.form_errors.${err.detail}`))
      else notifyMutationError()
    },
  })

  const title = t('character.extras.title')
  if (!char || !companions) {
    return <Layout title={title} backTo={`/char/${charId}`} group="character" page="extras"><ActionsSkeleton /></Layout>
  }

  const druid = char.classes.find((c) => classKey(c.class_name) === 'druid')
  const isBeastMaster = char.abilities.some((a) => a.feature_key === 'ranger.rangers_companion')
  const hasPactOfTheChain = char.abilities.some((a) => a.feature_key === 'warlock.pact_of_the_chain')
  const druidLevel = druid?.level ?? 0
  const isMoon = druid?.subclass_key === 'moon'
  const edition = char.rules_edition ?? '2014'
  const ws = char.abilities.find((a) => a.feature_key === 'druid.wild_shape')
  const wsUses = ws && ws.max_uses != null ? ws.uses ?? 0 : null // illimitata: come senza contatore
  // Circolo della Luna: gli slot con cui curare la forma (un livello per volta, quanti ne restano)
  const healSlots = char.abilities.some((a) => a.feature_key === 'druid.combat_wild_shape')
    ? [...new Set(char.spell_slots.filter((s) => s.available > 0).map((s) => s.level))].sort((a, b) => a - b)
      .map((level) => ({ level, left: char.spell_slots.filter((s) => s.level === level).reduce((n, s) => n + s.available, 0) }))
    : null

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
              {rows.map((c) => <CompanionCard key={c.id} charId={charId} comp={c} wildShapeUses={wsUses}
                formHasNoHp={edition === '2024' && druidLevel > 0} healSlots={healSlots} />)}
            </section>
          )
        })}
      </div>
      {adding && (
        <CompanionForm druidLevel={druidLevel} isMoon={isMoon} edition={edition} isBeastMaster={isBeastMaster} hasPactOfTheChain={hasPactOfTheChain} pending={create.isPending}
          onSubmit={(b) => create.mutate(b)} onClose={() => setAdding(false)} />
      )}
    </Layout>
  )
}

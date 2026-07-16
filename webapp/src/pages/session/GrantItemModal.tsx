import { useCallback, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { GiCrown as Crown } from 'react-icons/gi'
import { Check, User } from 'lucide-react'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import ItemForm from '@/pages/inventory/ItemForm'
import { buildItemMetadata, type ItemFormData } from '@/pages/inventory/itemMetadata'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import type { SessionParticipant } from '@/types'

interface GrantItemModalProps {
  sessionId: number
  participants: SessionParticipant[]
  gmUserId: number | null
  onClose: () => void
}

export default function GrantItemModal({
  sessionId,
  participants,
  gmUserId,
  onClose,
}: GrantItemModalProps) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [step, setStep] = useState<'form' | 'recipients'>('form')
  const [pendingForm, setPendingForm] = useState<ItemFormData | null>(null)
  const [selected, setSelected] = useState<Set<number>>(new Set())

  const players = participants.filter(
    (p) => p.role === 'player' && p.user_id !== gmUserId,
  )

  const toggle = (uid: number) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(uid)) next.delete(uid)
      else next.add(uid)
      return next
    })
  }

  const grantMutation = useMutation({
    mutationFn: () => {
      if (!pendingForm) throw new Error('no item')
      return api.sessions.grantItem(sessionId, {
        recipient_user_ids: Array.from(selected),
        item: {
          name: pendingForm.name.trim(),
          description: pendingForm.description.trim() || undefined,
          weight: Number(pendingForm.weight) || 0,
          quantity: Number(pendingForm.quantity) || 1,
          item_type: pendingForm.item_type,
          item_metadata: buildItemMetadata(pendingForm),
          is_equipped: false,
        },
      })
    },
    onSuccess: () => {
      haptic.success()
      qc.invalidateQueries({ queryKey: ['session-live', sessionId] })
      qc.invalidateQueries({ queryKey: ['session-feed'] })
      onClose()
    },
    onError: () => haptic.error(),
  })

  const handleFormSubmit = useCallback((data: ItemFormData) => {
    setPendingForm(data)
    setStep('recipients')
  }, [])

  if (step === 'form') {
    return (
      <ItemForm
        initialData={null}
        onSubmit={handleFormSubmit}
        onCancel={onClose}
        isPending={false}
      />
    )
  }

  return (
    <Sheet open onClose={onClose} title={t('session.grant_item.recipients_label')}>
      <div className="p-1 space-y-3">
        <p className="text-xs text-dnd-text-muted font-body italic">
          {pendingForm?.name} · ×{pendingForm?.quantity || 1}
        </p>

        {players.length === 0 ? (
          <p className="text-sm text-dnd-text-muted text-center py-4">
            {t('session.grant_item.no_players')}
          </p>
        ) : (
          <div className="space-y-1.5">
            {players.map((p) => {
              const checked = selected.has(p.user_id)
              return (
                <Pressable
                  key={p.user_id}
                  onClick={() => toggle(p.user_id)}
                  aria-pressed={checked}
                  className={`w-full min-h-[48px] flex items-center gap-3 px-3 py-2.5 rounded-lg border text-left transition-colors
                    ${checked ? 'border-dnd-gold bg-dnd-surface-raised' : 'border-dnd-border bg-dnd-surface'}`}
                >
                  <span
                    className={`w-5 h-5 shrink-0 inline-flex items-center justify-center rounded border
                      ${checked
                        ? 'bg-dnd-gold border-dnd-gold text-dnd-ink'
                        : 'border-dnd-border-strong text-transparent'}`}
                    aria-hidden
                  >
                    <Check size={14} />
                  </span>
                  <User size={14} className="text-dnd-text-muted shrink-0" />
                  <span className="font-body text-sm text-dnd-text truncate flex-1">
                    {p.display_name ?? `#${p.user_id}`}
                  </span>
                  {p.user_id === gmUserId && (
                    <Crown size={12} className="text-dnd-gold-bright" />
                  )}
                </Pressable>
              )
            })}
          </div>
        )}

        <div className="flex gap-2 pt-2">
          <Button
            variant="secondary"
            fullWidth
            onClick={() => setStep('form')}
            disabled={grantMutation.isPending}
          >
            {t('common.back')}
          </Button>
          <Button
            variant="primary"
            fullWidth
            haptic="success"
            onClick={() => grantMutation.mutate()}
            disabled={selected.size === 0}
            loading={grantMutation.isPending}
          >
            {t('session.grant_item.confirm')}
          </Button>
        </div>
      </div>
    </Sheet>
  )
}

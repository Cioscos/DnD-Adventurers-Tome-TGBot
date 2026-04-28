import { useCallback, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { GiCrown as Crown } from 'react-icons/gi'
import { User } from 'lucide-react'
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
    <div
      className="fixed inset-0 bg-black/60 flex items-end z-50 p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="w-full rounded-2xl bg-dnd-surface-elevated p-4 space-y-3 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold font-cinzel text-dnd-gold">
            {t('session.grant_item.recipients_label')}
          </h3>
          <button
            onClick={onClose}
            className="text-dnd-text-secondary text-sm"
            aria-label={t('common.cancel')}
          >
            &#x2715;
          </button>
        </div>

        <p className="text-xs text-dnd-text-muted font-body italic">
          {pendingForm?.name} · ×{pendingForm?.quantity || 1}
        </p>

        {players.length === 0 ? (
          <p className="text-sm text-dnd-text-muted text-center py-4">
            {t('session.grant_item.no_players', { defaultValue: 'Nessun giocatore in sessione' })}
          </p>
        ) : (
          <div className="space-y-1.5">
            {players.map((p) => {
              const checked = selected.has(p.user_id)
              return (
                <label
                  key={p.user_id}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg border cursor-pointer transition-colors
                    ${checked ? 'border-dnd-gold bg-dnd-surface-raised' : 'border-dnd-border bg-dnd-surface'}`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggle(p.user_id)}
                    className="w-4 h-4 accent-dnd-gold"
                  />
                  <User size={14} className="text-dnd-text-muted shrink-0" />
                  <span className="font-body text-sm text-dnd-text truncate flex-1">
                    {p.display_name ?? `#${p.user_id}`}
                  </span>
                  {p.user_id === gmUserId && (
                    <Crown size={12} className="text-dnd-gold-bright" />
                  )}
                </label>
              )
            })}
          </div>
        )}

        <div className="flex gap-2 pt-2 border-t border-dnd-gold-dim/10">
          <button
            type="button"
            onClick={() => setStep('form')}
            disabled={grantMutation.isPending}
            className="flex-1 px-3 py-2 rounded-md bg-dnd-surface border border-dnd-border text-sm
                       active:opacity-60 disabled:opacity-40"
          >
            {t('common.back')}
          </button>
          <button
            type="button"
            onClick={() => grantMutation.mutate()}
            disabled={selected.size === 0 || grantMutation.isPending}
            className="flex-1 px-3 py-2 rounded-md bg-gradient-to-r from-dnd-gold-deep to-dnd-gold-bright
                       text-black font-cinzel font-bold uppercase tracking-widest text-xs
                       active:opacity-80 disabled:opacity-40"
          >
            {t('session.grant_item.confirm', { defaultValue: 'Consegna' })}
          </button>
        </div>
      </div>
    </div>
  )
}

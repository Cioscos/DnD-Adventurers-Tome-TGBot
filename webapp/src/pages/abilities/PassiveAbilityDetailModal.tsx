import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import { api } from '@/api/client'
import type { Ability } from '@/types'

interface PassiveAbilityDetailModalProps {
  ability: Ability
  /** Se presente e l'abilita e' un talento, mostra "Rimuovi talento". */
  charId?: number
  onClose: () => void
}

export default function PassiveAbilityDetailModal({
  ability,
  charId,
  onClose,
}: PassiveAbilityDetailModalProps) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [confirming, setConfirming] = useState(false)
  const isFeat = charId != null && (ability.feature_key ?? '').startsWith('feat.')

  const remove = useMutation({
    mutationFn: () => api.choices.removeFeat(charId as number, ability.id),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      qc.invalidateQueries({ queryKey: ['homebrew-rules', charId] })
      onClose()
    },
  })

  return (
    <Sheet open onClose={onClose} title={ability.name} centered>
      <div className="p-5 space-y-4">
        {ability.description ? (
          <p className="text-sm text-dnd-text font-body leading-relaxed whitespace-pre-line">
            {ability.description}
          </p>
        ) : (
          <p className="text-sm italic text-dnd-text-muted font-body">
            {t('character.abilities.detail.no_description')}
          </p>
        )}
        {isFeat && confirming && (
          <p className="text-xs text-dnd-text-muted font-body">
            {t('character.level_choice.remove_warning')}
          </p>
        )}
        {isFeat && (
          <Button
            variant="secondary"
            fullWidth
            loading={remove.isPending}
            onClick={() => (confirming ? remove.mutate() : setConfirming(true))}
          >
            {confirming ? t('character.level_choice.remove_confirm') : t('character.level_choice.remove')}
          </Button>
        )}
        <Button variant="secondary" fullWidth onClick={onClose}>
          {t('common.close')}
        </Button>
      </div>
    </Sheet>
  )
}

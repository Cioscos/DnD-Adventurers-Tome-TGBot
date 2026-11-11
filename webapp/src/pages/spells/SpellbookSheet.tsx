import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api, ApiError, type SpellCopyMode } from '@/api/client'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import { haptic } from '@/auth/telegram'
import { useToast } from '@/hooks/useToast'
import { notifyMutationError } from '@/lib/mutationError'
import type { Spell } from '@/types'
import { bookModes } from '@/lib/spellbook'

export default function SpellbookSheet({ charId, spell, open, onClose }: {
  charId: number
  spell: Spell
  open: boolean
  onClose: () => void
}) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const modes = bookModes(spell)
  const [picked, setPicked] = useState<SpellCopyMode | null>(null)
  const mode = picked && modes.includes(picked) ? picked : modes[0]

  const cost = useQuery({
    queryKey: ['spellbook-cost', charId, spell.level, spell.school ?? null, mode],
    queryFn: () => api.spells.spellbookCost(charId, spell.level, spell.school ?? null, mode),
    enabled: open && !!mode,
  })

  const copy = useMutation({
    mutationFn: () => api.spells.copyToBook(charId, spell.id, mode),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      qc.invalidateQueries({ queryKey: ['spells', charId] })
      haptic.success()
      toast.success(t('character.spells.book.done', { name: spell.name }))
      onClose()
    },
    onError: (err) => {
      const detail = err instanceof ApiError ? err.detail : null
      const code = typeof detail === 'string' ? detail : (detail as { code?: string } | null)?.code
      if (code === 'insufficient_funds') toast.error(t('character.spells.insufficient_funds'))
      else if (code && ['not_a_wizard_spell', 'already_in_spellbook', 'already_in_backup', 'not_prepared', 'spell_above_slots'].includes(code)) {
        toast.error(t(code === 'spell_above_slots' ? 'character.spells.spell_above_slots' : `character.spells.book.${code}`))
      } else notifyMutationError(err)
    },
  })

  return (
    <Sheet open={open} onClose={onClose} title={t('character.spells.book.title')}>
      <div className="p-5 space-y-4 text-left">
        <p className="font-cinzel text-sm text-dnd-text">{spell.name}</p>
        {modes.length > 1 && (
          <div role="radiogroup" aria-label={t('character.spells.book.mode')} className="flex flex-col gap-2">
            {modes.map((m) => (
              <Pressable
                key={m}
                role="radio"
                aria-checked={m === mode}
                onClick={() => setPicked(m)}
                className={`min-h-11 px-3 rounded-xl border text-sm text-left ${
                  m === mode ? 'border-dnd-gold/70 text-dnd-gold-bright' : 'border-dnd-border text-dnd-text'}`}
              >
                {t(`character.spells.book.mode_${m}`)}
              </Pressable>
            ))}
          </div>
        )}
        {mode && (
          <p data-testid="book-cost" className="text-sm font-mono tabular-nums text-dnd-text">
            {cost.data
              ? <>{t('character.spells.book.cost', { hours: cost.data.hours, gold: cost.data.gold })}
                {cost.data.halved && <span className="ml-2 text-xs text-dnd-text-muted">{t('character.spells.book.halved')}</span>}</>
              : '…'}
          </p>
        )}
        <Button variant="primary" fullWidth disabled={!mode || !cost.data} loading={copy.isPending} onClick={() => copy.mutate()}>
          {t('character.spells.book.confirm')}
        </Button>
      </div>
    </Sheet>
  )
}

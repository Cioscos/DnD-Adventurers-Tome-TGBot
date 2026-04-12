import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import type { CharacterSummary } from '@/types'
import HPBar from '@/components/HPBar'
import Card from '@/components/Card'
import { haptic, telegramConfirm } from '@/auth/telegram'

export default function CharacterSelect() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)

  const { data: characters = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['characters'],
    queryFn: () => api.characters.list(),
  })

  const createMutation = useMutation({
    mutationFn: (name: string) => api.characters.create(name),
    onSuccess: (char) => {
      qc.invalidateQueries({ queryKey: ['characters'] })
      setNewName('')
      setCreating(false)
      haptic.success()
      navigate(`/char/${char.id}`)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.characters.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['characters'] })
      haptic.success()
    },
  })

  const handleCreate = () => {
    const name = newName.trim()
    if (!name) return
    createMutation.mutate(name)
  }

  const handleDelete = (char: CharacterSummary) => {
    telegramConfirm(
      t('character.select.delete_confirm', { name: char.name }),
      (confirmed) => {
        if (confirmed) deleteMutation.mutate(char.id)
      }
    )
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-[var(--tg-theme-hint-color)]">{t('common.loading')}</p>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4 p-4">
        <p className="text-red-400">{t('common.error')}</p>
        <button
          onClick={() => refetch()}
          className="px-4 py-2 rounded-xl bg-[var(--tg-theme-button-color)] text-[var(--tg-theme-button-text-color)]"
        >
          {t('common.retry')}
        </button>
      </div>
    )
  }

  return (
    <div className="min-h-screen p-4 space-y-4">
      <h1 className="text-2xl font-bold pt-2">⚔️ {t('character.select.title')}</h1>

      {/* Character list */}
      {characters.length === 0 ? (
        <p className="text-[var(--tg-theme-hint-color)] text-center py-8">
          {t('character.select.empty')}
        </p>
      ) : (
        <div className="space-y-3">
          {characters.map((char) => (
            <Card key={char.id} onClick={() => navigate(`/char/${char.id}`)}>
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold truncate">{char.name}</span>
                    {char.is_party_active && (
                      <span className="text-xs px-1.5 py-0.5 rounded-full bg-green-500/20 text-green-400">
                        Party
                      </span>
                    )}
                    {char.heroic_inspiration && <span title="Ispirazione">✨</span>}
                  </div>
                  <p className="text-sm text-[var(--tg-theme-hint-color)] mt-0.5">
                    {char.class_summary}
                    {char.race ? ` · ${char.race}` : ''}
                  </p>
                  {/* HP bar */}
                  <div className="mt-2 flex items-center gap-2">
                    <span className="text-xs text-[var(--tg-theme-hint-color)] w-20">
                      ❤️ {char.current_hit_points}/{char.hit_points}
                    </span>
                    <div className="flex-1">
                      <HPBar
                        current={char.current_hit_points}
                        max={char.hit_points}
                        temp={char.temp_hp}
                        size="sm"
                      />
                    </div>
                    <span className="text-xs text-[var(--tg-theme-hint-color)] w-12 text-right">
                      🛡️ {char.ac}
                    </span>
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    handleDelete(char)
                  }}
                  className="p-2 rounded-lg text-red-400 active:opacity-60 shrink-0"
                  aria-label="Elimina"
                >
                  🗑️
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* New character form */}
      {creating ? (
        <Card>
          <p className="font-medium mb-3">{t('character.select.new')}</p>
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
            placeholder="Nome del personaggio..."
            autoFocus
            className="w-full bg-white/10 rounded-xl px-3 py-2 text-sm outline-none
                       focus:ring-2 focus:ring-[var(--tg-theme-button-color)]"
          />
          <div className="flex gap-2 mt-3">
            <button
              onClick={handleCreate}
              disabled={!newName.trim() || createMutation.isPending}
              className="flex-1 py-2 rounded-xl bg-[var(--tg-theme-button-color)]
                         text-[var(--tg-theme-button-text-color)] font-medium
                         disabled:opacity-40"
            >
              {createMutation.isPending ? '...' : t('common.confirm')}
            </button>
            <button
              onClick={() => { setCreating(false); setNewName('') }}
              className="flex-1 py-2 rounded-xl bg-white/10 font-medium"
            >
              {t('common.cancel')}
            </button>
          </div>
        </Card>
      ) : (
        <button
          onClick={() => setCreating(true)}
          className="w-full py-3 rounded-2xl bg-[var(--tg-theme-button-color)]
                     text-[var(--tg-theme-button-text-color)] font-semibold
                     active:opacity-80 transition-opacity"
        >
          + {t('character.select.new')}
        </button>
      )}
    </div>
  )
}

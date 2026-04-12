import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import type { CharacterSummary } from '@/types'
import HPBar from '@/components/HPBar'
import Card from '@/components/Card'
import { haptic, telegramConfirm } from '@/auth/telegram'

const DND_CLASSES = [
  { name: 'Barbaro',   hit_die: 12, spellcasting_ability: null },
  { name: 'Bardo',     hit_die: 8,  spellcasting_ability: 'charisma' },
  { name: 'Chierico',  hit_die: 8,  spellcasting_ability: 'wisdom' },
  { name: 'Druido',    hit_die: 8,  spellcasting_ability: 'wisdom' },
  { name: 'Guerriero', hit_die: 10, spellcasting_ability: null },
  { name: 'Ladro',     hit_die: 8,  spellcasting_ability: null },
  { name: 'Mago',      hit_die: 6,  spellcasting_ability: 'intelligence' },
  { name: 'Monaco',    hit_die: 8,  spellcasting_ability: null },
  { name: 'Paladino',  hit_die: 10, spellcasting_ability: 'charisma' },
  { name: 'Ranger',    hit_die: 10, spellcasting_ability: 'wisdom' },
  { name: 'Stregone',  hit_die: 6,  spellcasting_ability: 'charisma' },
  { name: 'Warlock',   hit_die: 8,  spellcasting_ability: 'charisma' },
] as const

type SelectedClass = {
  class_name: string
  hit_die: number
  spellcasting_ability: string | null
}

type Step = 'name' | 'class'

export default function CharacterSelect() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()

  // wizard state
  const [step, setStep] = useState<Step>('name')
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)
  const [showCustom, setShowCustom] = useState(false)
  const [customName, setCustomName] = useState('')
  const [customHitDie, setCustomHitDie] = useState<number>(8)

  const { data: characters = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['characters'],
    queryFn: () => api.characters.list(),
  })

  const createMutation = useMutation({
    mutationFn: async ({ name, cls }: { name: string; cls: SelectedClass | null }) => {
      const char = await api.characters.create(name)
      if (cls) {
        await api.classes.add(char.id, {
          class_name: cls.class_name,
          level: 1,
          hit_die: cls.hit_die,
          spellcasting_ability: cls.spellcasting_ability ?? undefined,
        })
      }
      return char
    },
    onSuccess: (char) => {
      qc.invalidateQueries({ queryKey: ['characters'] })
      resetWizard()
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

  const resetWizard = () => {
    setCreating(false)
    setStep('name')
    setNewName('')
    setShowCustom(false)
    setCustomName('')
    setCustomHitDie(8)
  }

  const handleNameNext = () => {
    if (!newName.trim()) return
    setStep('class')
  }

  const handleCreate = (cls: SelectedClass | null) => {
    createMutation.mutate({ name: newName.trim(), cls })
  }

  const handleCustomCreate = () => {
    if (!customName.trim()) return
    handleCreate({ class_name: customName.trim(), hit_die: customHitDie, spellcasting_ability: null })
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

      {/* Creation wizard */}
      {creating ? (
        <Card>
          {step === 'name' ? (
            <>
              <p className="font-medium mb-3">{t('character.create.step_name')}</p>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleNameNext()}
                placeholder="Nome del personaggio..."
                autoFocus
                className="w-full bg-white/10 rounded-xl px-3 py-2 text-sm outline-none
                           focus:ring-2 focus:ring-[var(--tg-theme-button-color)]"
              />
              <div className="flex gap-2 mt-3">
                <button
                  onClick={handleNameNext}
                  disabled={!newName.trim()}
                  className="flex-1 py-2 rounded-xl bg-[var(--tg-theme-button-color)]
                             text-[var(--tg-theme-button-text-color)] font-medium
                             disabled:opacity-40"
                >
                  {t('common.confirm')} →
                </button>
                <button
                  onClick={resetWizard}
                  className="flex-1 py-2 rounded-xl bg-white/10 font-medium"
                >
                  {t('common.cancel')}
                </button>
              </div>
            </>
          ) : (
            <>
              <div className="flex items-center gap-2 mb-3">
                <button onClick={() => setStep('name')} className="text-[var(--tg-theme-hint-color)] active:opacity-60">
                  ←
                </button>
                <p className="font-medium">{t('character.create.step_class')}</p>
              </div>

              {!showCustom ? (
                <>
                  <div className="grid grid-cols-3 gap-2 mb-3">
                    {DND_CLASSES.map((cls) => (
                      <button
                        key={cls.name}
                        onClick={() => handleCreate({ class_name: cls.name, hit_die: cls.hit_die, spellcasting_ability: cls.spellcasting_ability })}
                        disabled={createMutation.isPending}
                        className="flex flex-col items-center py-2 px-1 rounded-xl
                                   bg-white/10 active:opacity-70 disabled:opacity-40
                                   text-center"
                      >
                        <span className="text-sm font-semibold">{cls.name}</span>
                        <span className="text-xs text-[var(--tg-theme-hint-color)]">d{cls.hit_die}</span>
                      </button>
                    ))}
                    <button
                      onClick={() => setShowCustom(true)}
                      className="flex flex-col items-center py-2 px-1 rounded-xl
                                 bg-white/10 active:opacity-70 text-center"
                    >
                      <span className="text-sm font-semibold">✏️</span>
                      <span className="text-xs text-[var(--tg-theme-hint-color)]">{t('character.create.custom_class')}</span>
                    </button>
                  </div>

                  <button
                    onClick={() => handleCreate(null)}
                    disabled={createMutation.isPending}
                    className="w-full py-2 text-sm text-[var(--tg-theme-hint-color)] underline disabled:opacity-40"
                  >
                    {t('character.create.skip_class')}
                  </button>
                </>
              ) : (
                <>
                  <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">{t('character.create.custom_class_name')}</p>
                  <input
                    type="text"
                    value={customName}
                    onChange={(e) => setCustomName(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleCustomCreate()}
                    placeholder="Es. Artificer"
                    autoFocus
                    className="w-full bg-white/10 rounded-xl px-3 py-2 text-sm outline-none
                               focus:ring-2 focus:ring-[var(--tg-theme-button-color)] mb-3"
                  />
                  <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">{t('character.create.hit_die')}</p>
                  <div className="flex gap-2 mb-3">
                    {[6, 8, 10, 12].map((d) => (
                      <button
                        key={d}
                        onClick={() => setCustomHitDie(d)}
                        className={`flex-1 py-2 rounded-xl font-bold text-sm transition-all
                          ${customHitDie === d
                            ? 'bg-[var(--tg-theme-button-color)] text-[var(--tg-theme-button-text-color)]'
                            : 'bg-white/10'}`}
                      >
                        d{d}
                      </button>
                    ))}
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={handleCustomCreate}
                      disabled={!customName.trim() || createMutation.isPending}
                      className="flex-1 py-2 rounded-xl bg-[var(--tg-theme-button-color)]
                                 text-[var(--tg-theme-button-text-color)] font-medium disabled:opacity-40"
                    >
                      {createMutation.isPending ? '...' : t('common.confirm')}
                    </button>
                    <button
                      onClick={() => setShowCustom(false)}
                      className="flex-1 py-2 rounded-xl bg-white/10 font-medium"
                    >
                      {t('common.back')}
                    </button>
                  </div>
                </>
              )}
            </>
          )}
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

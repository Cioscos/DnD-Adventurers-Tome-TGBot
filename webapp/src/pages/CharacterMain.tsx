import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import HPBar from '@/components/HPBar'
import Card from '@/components/Card'
import { haptic } from '@/auth/telegram'

const MENU_ITEMS = [
  { key: 'hp',         emoji: '❤️',  path: 'hp' },
  { key: 'ac',         emoji: '🛡️',  path: 'ac' },
  { key: 'stats',      emoji: '💪',  path: 'stats' },
  { key: 'skills',     emoji: '🎯',  path: 'skills' },
  { key: 'saves',      emoji: '🎲',  path: 'saves' },
  { key: 'spells',     emoji: '✨',  path: 'spells' },
  { key: 'slots',      emoji: '🔮',  path: 'slots' },
  { key: 'inventory',  emoji: '🎒',  path: 'inventory' },
  { key: 'currency',   emoji: '💰',  path: 'currency' },
  { key: 'abilities',  emoji: '⚡',  path: 'abilities' },
  { key: 'class',      emoji: '📜',  path: 'class' },
  { key: 'xp',         emoji: '⭐',  path: 'xp' },
  { key: 'conditions', emoji: '🌀',  path: 'conditions' },
  { key: 'death_saves',emoji: '💀',  path: 'hp' },   // redirects to HP page which has death saves
  { key: 'dice',       emoji: '🎲',  path: 'dice' },
  { key: 'notes',      emoji: '📝',  path: 'notes' },
  { key: 'maps',       emoji: '🗺️',  path: 'maps' },
  { key: 'history',    emoji: '📖',  path: 'history' },
  { key: 'identity',   emoji: '👤',  path: 'identity' },
  { key: 'settings',   emoji: '⚙️',  path: 'settings' },
]

export default function CharacterMain() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const navigate = useNavigate()
  const { t } = useTranslation()
  const qc = useQueryClient()

  const { data: char, isLoading, isError } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
    enabled: !!charId,
  })

  const inspirationMutation = useMutation({
    mutationFn: (value: boolean) => api.characters.updateInspiration(charId, value),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.light()
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-[var(--tg-theme-hint-color)]">{t('common.loading')}</p>
      </div>
    )
  }

  if (isError || !char) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4 p-4">
        <p className="text-red-400">{t('common.error')}</p>
        <button onClick={() => navigate('/')} className="underline">
          {t('common.back')}
        </button>
      </div>
    )
  }

  const hpPct = char.hit_points > 0
    ? Math.round((char.current_hit_points / char.hit_points) * 100)
    : 0

  return (
    <div className="min-h-screen p-4 space-y-4">
      {/* Header bar */}
      <div className="flex items-center gap-2 pt-1">
        <button onClick={() => navigate('/')} className="p-1 active:opacity-60">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M15.41 16.59L10.83 12l4.58-4.59L14 6l-6 6 6 6z" />
          </svg>
        </button>
        <h1 className="text-xl font-bold truncate flex-1">{char.name}</h1>
        <button
          onClick={() => inspirationMutation.mutate(!char.heroic_inspiration)}
          title={char.heroic_inspiration ? t('character.inspiration.tap_to_spend') : t('character.inspiration.tap_to_grant')}
          className={`text-xl transition-opacity active:opacity-60 ${char.heroic_inspiration ? 'opacity-100' : 'opacity-25'}`}
        >
          ✨
        </button>
        {char.is_party_active && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-green-500/20 text-green-400">
            Party
          </span>
        )}
      </div>

      {/* Quick stats card */}
      <Card>
        <div className="flex justify-between items-start mb-3">
          <div>
            <p className="text-sm text-[var(--tg-theme-hint-color)]">{char.class_summary}</p>
            {char.race && (
              <p className="text-xs text-[var(--tg-theme-hint-color)]">{char.race}</p>
            )}
          </div>
          <div className="text-right">
            <span className="text-2xl font-bold">{char.ac}</span>
            <p className="text-xs text-[var(--tg-theme-hint-color)]">CA</p>
          </div>
        </div>

        {/* HP */}
        <div className="mb-1 flex items-center justify-between text-sm">
          <span>
            ❤️ {char.current_hit_points}/{char.hit_points}
            {char.temp_hp > 0 && (
              <span className="text-blue-400 ml-1">(+{char.temp_hp} temp)</span>
            )}
          </span>
          <span className="text-[var(--tg-theme-hint-color)]">{hpPct}%</span>
        </div>
        <HPBar current={char.current_hit_points} max={char.hit_points} temp={char.temp_hp} />

        {/* XP + Speed */}
        <div className="flex gap-4 mt-3 text-sm text-[var(--tg-theme-hint-color)]">
          <span>⭐ {char.experience_points} XP</span>
          <span>💨 {char.speed}ft</span>
          {char.concentrating_spell_id && (
            <span className="text-purple-400">🔮 Concentrazione</span>
          )}
        </div>
      </Card>

      {/* Ability scores row */}
      {char.ability_scores.length > 0 && (
        <Card className="!p-3">
          <div className="grid grid-cols-6 gap-1 text-center">
            {char.ability_scores.map((score) => (
              <div key={score.name} className="flex flex-col items-center">
                <span className="text-xs text-[var(--tg-theme-hint-color)] uppercase">
                  {score.name.slice(0, 3)}
                </span>
                <span className="text-lg font-bold leading-tight">{score.value}</span>
                <span className="text-xs text-[var(--tg-theme-hint-color)]">
                  {score.modifier >= 0 ? '+' : ''}{score.modifier}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Menu grid */}
      <div className="grid grid-cols-3 gap-2">
        {MENU_ITEMS.map((item) => (
          <button
            key={item.key}
            onClick={() => navigate(`/char/${charId}/${item.path}`)}
            className="flex flex-col items-center gap-1 p-3 rounded-2xl
                       bg-[var(--tg-theme-secondary-bg-color)]
                       active:opacity-70 transition-opacity"
          >
            <span className="text-2xl">{item.emoji}</span>
            <span className="text-xs text-center leading-tight">
              {t(`character.menu.${item.key}`)}
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}

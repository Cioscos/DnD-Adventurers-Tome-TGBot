import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import HPBar from '@/components/HPBar'
import Card from '@/components/Card'
import SectionHeader from '@/components/SectionHeader'
import Skeleton from '@/components/Skeleton'
import { haptic } from '@/auth/telegram'
import {
  Heart, Shield, ShieldAlert, Sparkles, Gem,
  BarChart3, Target, Zap, Swords, Coins,
  User, Scroll, Star, CircleDot, Dices,
  NotebookPen, Map, BookOpen, ChevronLeft, Settings,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

type MenuItem = {
  key: string
  icon: LucideIcon
  path: string
}

type MenuSection = {
  labelKey: string
  items: MenuItem[]
}

const MENU_SECTIONS: MenuSection[] = [
  {
    labelKey: 'character.menu.sections.combat',
    items: [
      { key: 'hp',    icon: Heart,       path: 'hp' },
      { key: 'ac',    icon: Shield,      path: 'ac' },
      { key: 'saves', icon: ShieldAlert, path: 'saves' },
    ],
  },
  {
    labelKey: 'character.menu.sections.magic',
    items: [
      { key: 'spells', icon: Sparkles, path: 'spells' },
      { key: 'slots',  icon: Gem,      path: 'slots' },
    ],
  },
  {
    labelKey: 'character.menu.sections.skills',
    items: [
      { key: 'stats',     icon: BarChart3, path: 'stats' },
      { key: 'skills',    icon: Target,    path: 'skills' },
      { key: 'abilities', icon: Zap,       path: 'abilities' },
    ],
  },
  {
    labelKey: 'character.menu.sections.equipment',
    items: [
      { key: 'inventory', icon: Swords, path: 'inventory' },
      { key: 'currency',  icon: Coins,  path: 'currency' },
    ],
  },
  {
    labelKey: 'character.menu.sections.character',
    items: [
      { key: 'identity',   icon: User,      path: 'identity' },
      { key: 'class',      icon: Scroll,    path: 'class' },
      { key: 'xp',         icon: Star,      path: 'xp' },
      { key: 'conditions', icon: CircleDot, path: 'conditions' },
    ],
  },
  {
    labelKey: 'character.menu.sections.tools',
    items: [
      { key: 'dice',    icon: Dices,       path: 'dice' },
      { key: 'notes',   icon: NotebookPen, path: 'notes' },
      { key: 'maps',    icon: Map,         path: 'maps' },
      { key: 'history', icon: BookOpen,    path: 'history' },
    ],
  },
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
      <div className="min-h-screen p-4 space-y-4 pb-safe animate-fade-in">
        <Skeleton.Line width="180px" height="24px" />
        <Skeleton.Rect height="180px" />
        <Skeleton.Rect height="60px" delay={100} />
        <Skeleton.Rect height="200px" delay={200} />
      </div>
    )
  }

  if (isError || !char) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4 p-4">
        <p className="text-[var(--dnd-danger)]">{t('common.error')}</p>
        <button onClick={() => navigate('/')} className="underline text-dnd-gold">
          {t('common.back')}
        </button>
      </div>
    )
  }

  const hpPct = char.hit_points > 0
    ? Math.round((char.current_hit_points / char.hit_points) * 100)
    : 0

  return (
    <div className="min-h-screen p-4 space-y-4 pb-safe animate-fade-in">
      {/* Header bar */}
      <div className="flex items-center gap-2 pt-1">
        <button onClick={() => navigate('/')} className="p-1 active:opacity-60">
          <ChevronLeft size={20} className="text-dnd-gold" />
        </button>
        <h1 className="text-xl font-bold font-cinzel text-dnd-gold truncate flex-1">
          {char.name}
        </h1>
        <button
          onClick={() => inspirationMutation.mutate(!char.heroic_inspiration)}
          title={char.heroic_inspiration ? t('character.inspiration.tap_to_spend') : t('character.inspiration.tap_to_grant')}
          className={`transition-opacity active:opacity-60 ${char.heroic_inspiration ? 'animate-shimmer' : 'opacity-25'}`}
        >
          <Sparkles size={22} className="text-dnd-gold" />
        </button>
        <button
          onClick={() => navigate(`/char/${charId}/settings`)}
          className="p-1 active:opacity-60 transition-opacity"
          aria-label="Settings"
        >
          <Settings size={20} className="text-dnd-gold" />
        </button>
        {char.is_party_active && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-dnd-success/20 text-dnd-success-text">
            Party
          </span>
        )}
      </div>

      {/* Hero card */}
      <Card variant="elevated">
        <div className="flex justify-between items-start mb-3">
          <div>
            <p className="text-sm text-dnd-text-secondary">{char.class_summary}</p>
            {char.race && (
              <p className="text-xs text-dnd-text-secondary">{char.race}</p>
            )}
          </div>
          <div className="text-right">
            <span className="text-2xl font-black">{char.ac}</span>
            <p className="text-xs text-dnd-gold-dim">CA</p>
          </div>
        </div>

        <div className="mb-1 flex items-center justify-between text-sm">
          <span>
            ❤️ {char.current_hit_points}/{char.hit_points}
            {char.temp_hp > 0 && (
              <span className="text-dnd-info ml-1">(+{char.temp_hp} temp)</span>
            )}
          </span>
          <span className="text-dnd-text-secondary">{hpPct}%</span>
        </div>
        <HPBar current={char.current_hit_points} max={char.hit_points} temp={char.temp_hp} />

        <div className="flex gap-4 mt-3 text-sm text-dnd-text-secondary">
          <span>⭐ {char.experience_points} XP</span>
          <span>💨 {char.speed}ft</span>
        </div>

        {char.concentrating_spell_id && (() => {
          const spell = char.spells?.find(s => s.id === char.concentrating_spell_id)
          return (
            <div className="mt-2">
              <span className="text-xs px-2 py-0.5 rounded-full bg-dnd-arcane/20 text-dnd-arcane-text">
                🔮 {spell?.name ?? t('character.spells.concentration')}
              </span>
            </div>
          )
        })()}

        {char.abilities?.filter(a => a.is_passive).length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {char.abilities.filter(a => a.is_passive).map(a => (
              <span key={a.id} className="text-xs px-2 py-0.5 rounded-full bg-[var(--dnd-gold-glow)] text-dnd-gold">
                ⚡ {a.name}
              </span>
            ))}
          </div>
        )}

        {char.conditions && Object.entries(char.conditions).filter(([, v]) => v).length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {Object.entries(char.conditions).filter(([, v]) => v).map(([key, val]) => (
              <span key={key} className="text-xs px-2 py-0.5 rounded-full bg-dnd-danger/20 text-[var(--dnd-danger)]">
                🌀 {t(`character.conditions.${key}`)}
                {typeof val === 'number' && val > 1 ? ` (${val})` : ''}
              </span>
            ))}
          </div>
        )}
      </Card>

      {/* Ability scores */}
      {char.ability_scores.length > 0 && (
        <Card variant="elevated" className="!p-3">
          <div className="grid grid-cols-6 gap-1 text-center">
            {char.ability_scores.map((score) => (
              <div key={score.name} className="flex flex-col items-center bg-dnd-surface rounded-lg p-1 border border-dnd-gold-dim/30">
                <span className="text-[0.6rem] text-dnd-gold-dim uppercase tracking-wide">
                  {score.name.slice(0, 3)}
                </span>
                <span className="text-lg font-black leading-tight">{score.value}</span>
                <span className="text-xs text-dnd-text-secondary">
                  {score.modifier >= 0 ? '+' : ''}{score.modifier}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Menu grid — grouped */}
      {MENU_SECTIONS.map((section) => (
        <div key={section.labelKey}>
          <SectionHeader>{t(section.labelKey)}</SectionHeader>
          <div className="grid grid-cols-3 gap-2">
            {section.items.map((item) => {
              const Icon = item.icon
              return (
                <button
                  key={item.key}
                  onClick={() => {
                    haptic.light()
                    navigate(`/char/${charId}/${item.path}`)
                  }}
                  className="flex flex-col items-center gap-1 p-3 rounded-2xl
                             bg-dnd-surface border border-transparent
                             active:border-dnd-gold-dim active:shadow-dnd-glow active:scale-95
                             transition-all duration-150"
                >
                  <Icon size={24} className="text-dnd-gold" strokeWidth={2} />
                  <span className="text-xs text-dnd-text-secondary text-center leading-tight">
                    {t(`character.menu.${item.key}`)}
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}

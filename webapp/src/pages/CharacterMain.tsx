import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import {
  Heart, Shield, ShieldAlert, Sparkles, Gem,
  BarChart3, Target, Zap, Swords, Coins,
  User, Scroll, Star, CircleDot, Dices,
  NotebookPen, Map, BookOpen, ChevronLeft, Settings, FlaskConical,
  Footprints,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { api } from '@/api/client'
import HPGauge from '@/components/ui/HPGauge'
import HeroXPBar from '@/components/ui/HeroXPBar'
import Surface from '@/components/ui/Surface'
import SectionDivider from '@/components/ui/SectionDivider'
import StatPill from '@/components/ui/StatPill'
import Reveal from '@/components/ui/Reveal'
import Skeleton from '@/components/ui/Skeleton'
import { ShieldEmblem } from '@/components/ui/Ornament'
import { haptic } from '@/auth/telegram'
import { spring, stagger } from '@/styles/motion'
import { formatCondition, CONDITION_ICONS } from '@/lib/conditions'
import ConditionDetailModal from '@/pages/conditions/ConditionDetailModal'
import PassiveAbilityDetailModal from '@/pages/abilities/PassiveAbilityDetailModal'
import type { Ability } from '@/types'

type MenuItem = {
  key: string
  icon: LucideIcon
  path: string
  tone?: 'gold' | 'crimson' | 'arcane' | 'cobalt' | 'emerald' | 'amber'
}

type MenuSection = {
  labelKey: string
  icon: LucideIcon
  items: MenuItem[]
}

const MENU_SECTIONS: MenuSection[] = [
  {
    labelKey: 'character.menu.sections.combat',
    icon: Swords,
    items: [
      { key: 'hp',    icon: Heart,       path: 'hp',    tone: 'crimson' },
      { key: 'ac',    icon: Shield,      path: 'ac',    tone: 'gold' },
      { key: 'saves', icon: ShieldAlert, path: 'saves', tone: 'cobalt' },
    ],
  },
  {
    labelKey: 'character.menu.sections.magic',
    icon: Sparkles,
    items: [
      { key: 'spells', icon: Sparkles, path: 'spells', tone: 'arcane' },
      { key: 'slots',  icon: Gem,      path: 'slots',  tone: 'arcane' },
    ],
  },
  {
    labelKey: 'character.menu.sections.skills',
    icon: Target,
    items: [
      { key: 'stats',     icon: BarChart3, path: 'stats',     tone: 'gold' },
      { key: 'skills',    icon: Target,    path: 'skills',    tone: 'cobalt' },
      { key: 'abilities', icon: Zap,       path: 'abilities', tone: 'amber' },
    ],
  },
  {
    labelKey: 'character.menu.sections.equipment',
    icon: Coins,
    items: [
      { key: 'inventory', icon: Swords, path: 'inventory', tone: 'gold' },
      { key: 'currency',  icon: Coins,  path: 'currency',  tone: 'amber' },
    ],
  },
  {
    labelKey: 'character.menu.sections.character',
    icon: User,
    items: [
      { key: 'identity',   icon: User,      path: 'identity',   tone: 'gold' },
      { key: 'class',      icon: Scroll,    path: 'class',      tone: 'gold' },
      { key: 'xp',         icon: Star,      path: 'xp',         tone: 'amber' },
      { key: 'conditions', icon: CircleDot, path: 'conditions', tone: 'crimson' },
    ],
  },
  {
    labelKey: 'character.menu.sections.tools',
    icon: FlaskConical,
    items: [
      { key: 'dice',    icon: Dices,       path: 'dice',    tone: 'gold' },
      { key: 'notes',   icon: NotebookPen, path: 'notes',   tone: 'emerald' },
      { key: 'maps',    icon: Map,         path: 'maps',    tone: 'cobalt' },
      { key: 'history', icon: BookOpen,    path: 'history', tone: 'amber' },
    ],
  },
]

const ABILITY_COLORS: Record<string, string> = {
  strength: 'from-[var(--dnd-crimson-deep)]/30 to-transparent border-dnd-crimson/30 text-[var(--dnd-crimson-bright)]',
  dexterity: 'from-[var(--dnd-emerald-deep)]/30 to-transparent border-dnd-emerald/30 text-[var(--dnd-emerald-bright)]',
  constitution: 'from-[var(--dnd-amber)]/30 to-transparent border-dnd-amber/30 text-[var(--dnd-amber)]',
  intelligence: 'from-[var(--dnd-cobalt-deep)]/30 to-transparent border-dnd-cobalt/30 text-[var(--dnd-cobalt-bright)]',
  wisdom: 'from-[var(--dnd-arcane-deep)]/30 to-transparent border-dnd-arcane/30 text-[var(--dnd-arcane-bright)]',
  charisma: 'from-[var(--dnd-gold-deep)]/40 to-transparent border-dnd-gold/30 text-dnd-gold-bright',
}

function toneIconClass(tone?: MenuItem['tone']): string {
  switch (tone) {
    case 'crimson': return 'text-[var(--dnd-crimson-bright)]'
    case 'arcane': return 'text-dnd-arcane-bright'
    case 'cobalt': return 'text-[var(--dnd-cobalt-bright)]'
    case 'emerald': return 'text-[var(--dnd-emerald-bright)]'
    case 'amber': return 'text-[var(--dnd-amber)]'
    case 'gold':
    default: return 'text-dnd-gold-bright'
  }
}

export default function CharacterMain() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const navigate = useNavigate()
  const { t } = useTranslation()
  const qc = useQueryClient()

  const [detailCondKey, setDetailCondKey] = useState<string | null>(null)
  const [detailAbility, setDetailAbility] = useState<Ability | null>(null)

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
      <div className="min-h-screen p-4 space-y-4 pb-safe pt-safe">
        <Skeleton.Line width="180px" height="28px" />
        <Skeleton.Rect height="200px" />
        <Skeleton.Rect height="72px" delay={100} />
        <Skeleton.Rect height="240px" delay={200} />
      </div>
    )
  }

  if (isError || !char) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4 p-4">
        <p className="text-[var(--dnd-crimson-bright)] font-body">{t('common.error')}</p>
        <button onClick={() => navigate('/')} className="underline text-dnd-gold font-cinzel">
          {t('common.back')}
        </button>
      </div>
    )
  }

  const hpPct = char.hit_points > 0
    ? Math.round((char.current_hit_points / char.hit_points) * 100)
    : 0

  const passiveAbilities = char.abilities?.filter(a => a.is_passive) ?? []
  const activeConditions = char.conditions
    ? Object.entries(char.conditions).filter(([, v]) => v)
    : []

  return (
    <div
      className="w-full flex flex-col"
      style={{ height: 'var(--tg-vh, 100vh)' }}
    >
      {/* Header bar */}
      <m.header
        className="shrink-0 z-20 flex items-center gap-2 px-4 py-3 pt-safe
                   bg-dnd-surface-raised/95 backdrop-blur-sm border-b border-dnd-gold-dim/40 shadow-parchment-md"
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={spring.drift}
      >
        <m.button
          onClick={() => navigate('/')}
          className="w-9 h-9 flex items-center justify-center rounded-full bg-dnd-surface border border-dnd-gold-dim/30"
          whileTap={{ scale: 0.9 }}
          aria-label={t('common.back')}
        >
          <ChevronLeft size={20} className="text-dnd-gold-bright" />
        </m.button>

        <h1 className="text-xl font-display font-bold text-dnd-gold-bright truncate flex-1"
            style={{ textShadow: '0 1px 4px var(--dnd-gold-glow)' }}>
          {char.name}
        </h1>

        {/* Inspiration toggle */}
        <m.button
          onClick={() => inspirationMutation.mutate(!char.heroic_inspiration)}
          title={char.heroic_inspiration ? t('character.inspiration.tap_to_spend') : t('character.inspiration.tap_to_grant')}
          className={`w-9 h-9 flex items-center justify-center rounded-full transition-all
            ${char.heroic_inspiration
              ? 'bg-dnd-gold/15 border border-dnd-gold animate-shimmer'
              : 'bg-transparent border border-dashed border-dnd-gold-dim/40 opacity-50'}`}
          whileTap={{ scale: 0.9 }}
          aria-label="Heroic Inspiration"
        >
          <Sparkles size={18} className="text-dnd-gold" />
        </m.button>

        <m.button
          onClick={() => navigate(`/char/${charId}/settings`)}
          className="w-9 h-9 flex items-center justify-center rounded-full bg-dnd-surface border border-dnd-gold-dim/30"
          whileTap={{ scale: 0.9 }}
          aria-label={t('character.menu.settings')}
        >
          <Settings size={18} className="text-dnd-gold-bright" />
        </m.button>
      </m.header>

      <div className="flex-1 overflow-y-auto p-4 space-y-4 pb-safe">
        {/* Hero card with shared layoutId from CharacterSelect */}
        <Surface
          variant="tome"
          ornamented
          layoutId={`char-hero-${charId}`}
          className="relative overflow-hidden"
        >
          <div>
            <p className="text-sm text-dnd-text-muted font-body italic mb-0.5">{char.class_summary}</p>
            {char.race && (
              <p className="text-xs text-dnd-text-faint font-body">{char.race}</p>
            )}
          </div>

          {/* Bars column on the left (HP + XP stacked) — AC shield on the right,
              vertically centered between them via flex items-center. */}
          <div className="mt-4 flex items-center gap-3">
            <div className="flex-1 min-w-0">
              {/* HP row */}
              <div>
                <div className="flex items-center justify-between text-sm mb-1.5">
                  <span className="inline-flex items-center gap-1.5 font-mono">
                    <Heart size={14} className="text-[var(--dnd-crimson-bright)]" />
                    <span className="text-dnd-text font-bold">
                      {char.current_hit_points}/{char.hit_points}
                    </span>
                    {char.temp_hp > 0 && (
                      <span className="text-[var(--dnd-cobalt-bright)]">(+{char.temp_hp} temp)</span>
                    )}
                  </span>
                  <span className="text-dnd-text-faint font-mono text-xs">{hpPct}%</span>
                </div>
                <HPGauge
                  current={char.current_hit_points}
                  max={char.hit_points}
                  temp={char.temp_hp}
                  size="md"
                  segmented
                />
              </div>

              {/* XP bar — stesso flex-1 → stessa larghezza della HP bar */}
              <HeroXPBar
                currentXP={char.experience_points}
                totalClassLevel={char.total_level}
                onLevelUpReady={() => navigate(`/char/${charId}/xp`)}
              />
            </div>

            {/* AC shield — right-aligned con i bar, centrato verticalmente fra HP e XP */}
            <div className="shrink-0 relative opacity-90 pointer-events-none">
              <ShieldEmblem size={90} />
              <span className="absolute inset-0 flex flex-col items-center justify-center pb-1">
                <span className="text-2xl font-display font-black text-dnd-gold-bright leading-none"
                      style={{ textShadow: '0 1px 3px rgba(0,0,0,0.6)' }}>
                  {char.ac}
                </span>
                <span className="text-[9px] font-cinzel uppercase tracking-widest text-dnd-gold-dim leading-none mt-0.5">
                  {t('character.ac.short', { defaultValue: 'CA' })}
                </span>
              </span>
            </div>
          </div>

          {/* Concentration banner */}
          {char.concentrating_spell_id && (() => {
            const spell = char.spells?.find(s => s.id === char.concentrating_spell_id)
            return (
              <m.button
                onClick={() => navigate(`/char/${charId}/spells`)}
                className="mt-3 w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl
                           bg-gradient-arcane-mist border border-dnd-arcane/50 text-dnd-arcane-bright
                           text-xs font-cinzel uppercase tracking-wider"
                whileTap={{ scale: 0.98 }}
              >
                <FlaskConical size={14} />
                {spell?.name ?? t('character.spells.concentration')}
              </m.button>
            )
          })()}

          {/* Passive abilities — chip invariate, tap apre modale descrizione */}
          {passiveAbilities.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3 overflow-x-auto scrollbar-hide max-h-14">
              {passiveAbilities.map(a => (
                <StatPill
                  key={a.id}
                  icon={<Zap size={10} />}
                  value={a.name}
                  tone="gold"
                  size="sm"
                  onClick={() => setDetailAbility(a)}
                />
              ))}
            </div>
          )}

          {/* Active conditions — icon-only, tap apre ConditionDetailModal */}
          {activeConditions.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2 overflow-x-auto scrollbar-hide max-h-14 pr-16">
              {activeConditions.map(([key, val]) => {
                const Icon = CONDITION_ICONS[key] ?? CircleDot
                return (
                  <StatPill
                    key={key}
                    icon={<Icon size={14} />}
                    value={formatCondition(key, val, t)}
                    tone="crimson"
                    size="sm"
                    iconOnly
                    onClick={() => setDetailCondKey(key)}
                  />
                )
              })}
            </div>
          )}

          {/* Velocità — icon-only floating bottom-right, tap rivela valore */}
          <StatPill
            icon={<Footprints size={14} />}
            value={`${char.speed} ft`}
            tone="emerald"
            size="sm"
            iconOnly
            revealOnTap
            aria-label={`${t('character.identity.speed', { defaultValue: 'Speed' })}: ${char.speed} ft`}
            className="absolute bottom-3 right-3"
          />
        </Surface>

        {/* Ability scores */}
        {char.ability_scores.length > 0 && (
          <Surface variant="elevated" className="!p-2.5">
            <m.div
              className="grid grid-cols-6 gap-1.5 text-center"
              initial="initial"
              animate="animate"
              variants={{
                initial: {},
                animate: { transition: { staggerChildren: 0.04, delayChildren: 0.1 } },
              }}
            >
              {char.ability_scores.map((score) => {
                const key = score.name.toLowerCase()
                const colorCls = ABILITY_COLORS[key] ?? ABILITY_COLORS.charisma
                const modStr = `${score.modifier >= 0 ? '+' : ''}${score.modifier}`
                return (
                  <m.button
                    key={score.name}
                    type="button"
                    onClick={() => {
                      haptic.light()
                      navigate(`/char/${charId}/stats`)
                    }}
                    aria-label={`${score.name}: ${score.value}, mod ${modStr}`}
                    className={`flex flex-col items-center rounded-lg p-1.5 border bg-gradient-to-b cursor-pointer hover:border-dnd-gold transition-colors ${colorCls}`}
                    variants={{ initial: { opacity: 0, y: 8 }, animate: { opacity: 1, y: 0 } }}
                    transition={spring.snappy}
                    whileTap={{ scale: 0.95 }}
                  >
                    <span className="text-[9px] font-cinzel uppercase tracking-widest opacity-80">
                      {score.name.slice(0, 3)}
                    </span>
                    <span className="text-xl font-display font-black leading-none mt-0.5">{score.value}</span>
                    <span className="text-[11px] font-mono font-bold mt-0.5 px-1.5 py-0.5 rounded-full bg-black/25">
                      {modStr}
                    </span>
                  </m.button>
                )
              })}
            </m.div>
          </Surface>
        )}

        {/* Menu grid — grouped */}
        {MENU_SECTIONS.map((section, sIdx) => {
          const SectionIcon = section.icon
          return (
            <m.div
              key={section.labelKey}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ ...spring.drift, delay: 0.3 + sIdx * 0.06 }}
            >
              <SectionDivider icon={<SectionIcon size={11} />} align="center">
                {t(section.labelKey)}
              </SectionDivider>
              <Reveal.Stagger stagger={stagger.listTight} delay={0} className="grid grid-cols-3 gap-2">
                {section.items.map((item) => {
                  const Icon = item.icon
                  return (
                    <Reveal.Item key={item.key}>
                      <m.button
                        onClick={() => {
                          haptic.light()
                          navigate(`/char/${charId}/${item.path}`)
                        }}
                        className="w-full flex flex-col items-center gap-1.5 px-2 py-3 rounded-2xl
                                   bg-dnd-surface border border-dnd-border
                                   hover:border-dnd-gold/60 hover:shadow-halo-gold
                                   transition-[box-shadow,border-color] duration-200"
                        whileTap={{ scale: 0.93 }}
                      >
                        <Icon size={22} strokeWidth={2} className={toneIconClass(item.tone)} />
                        <span className="text-[11px] text-dnd-text-muted font-body text-center leading-tight">
                          {t(`character.menu.${item.key}`)}
                        </span>
                      </m.button>
                    </Reveal.Item>
                  )
                })}
              </Reveal.Stagger>
            </m.div>
          )
        })}
      </div>

      {/* Modals */}
      {detailCondKey !== null && (
        <ConditionDetailModal
          condKey={detailCondKey}
          exhaustionLevel={
            typeof (char.conditions as Record<string, unknown>)?.['exhaustion'] === 'number'
              ? ((char.conditions as Record<string, unknown>)['exhaustion'] as number)
              : 0
          }
          onClose={() => setDetailCondKey(null)}
        />
      )}
      {detailAbility !== null && (
        <PassiveAbilityDetailModal
          ability={detailAbility}
          onClose={() => setDetailAbility(null)}
        />
      )}
    </div>
  )
}

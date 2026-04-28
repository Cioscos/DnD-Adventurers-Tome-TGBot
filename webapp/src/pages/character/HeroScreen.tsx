import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { CircleDot } from 'lucide-react'
import {
  GiHeartPlus, GiLightningTrio, GiPotionBall, GiBootPrints,
} from 'react-icons/gi'
import HPGauge from '@/components/ui/HPGauge'
import HeroXPBar from '@/components/ui/HeroXPBar'
import Surface from '@/components/ui/Surface'
import StatPill from '@/components/ui/StatPill'
import { ShieldEmblem } from '@/components/ui/Ornament'
import { haptic } from '@/auth/telegram'
import { spring } from '@/styles/motion'
import { formatCondition, CONDITION_ICONS } from '@/lib/conditions'
import ConditionDetailModal from '@/pages/conditions/ConditionDetailModal'
import PassiveAbilityDetailModal from '@/pages/abilities/PassiveAbilityDetailModal'
import SpellSlotsSummary from '@/components/character/SpellSlotsSummary'
import ProgressionPreview from '@/components/character/ProgressionPreview'
import ClassTabs from '@/components/character/ClassTabs'
import type { Ability, CharacterFull } from '@/types'

const ABILITY_COLORS: Record<string, string> = {
  strength: 'from-[var(--dnd-crimson-deep)]/30 to-transparent border-dnd-crimson/30 text-[var(--dnd-crimson-bright)]',
  dexterity: 'from-[var(--dnd-emerald-deep)]/30 to-transparent border-dnd-emerald/30 text-[var(--dnd-emerald-bright)]',
  constitution: 'from-[var(--dnd-amber)]/30 to-transparent border-dnd-amber/30 text-[var(--dnd-amber)]',
  intelligence: 'from-[var(--dnd-cobalt-deep)]/30 to-transparent border-dnd-cobalt/30 text-[var(--dnd-cobalt-bright)]',
  wisdom: 'from-[var(--dnd-arcane-deep)]/30 to-transparent border-dnd-arcane/30 text-[var(--dnd-arcane-bright)]',
  charisma: 'from-[var(--dnd-gold-deep)]/40 to-transparent border-dnd-gold/30 text-dnd-gold-bright',
}

interface Props {
  char: CharacterFull
}

function pickDefaultClass(char: CharacterFull): string {
  const classes = char.classes ?? []
  if (classes.length === 0) return ''
  if (classes.length === 1) return classes[0].class_name
  // Multi-class fallback: alphabetic. (No reliable history field on CharacterFull.)
  return [...classes].sort((a, b) => a.class_name.localeCompare(b.class_name))[0].class_name
}

export default function HeroScreen({ char }: Props) {
  const navigate = useNavigate()
  const { t } = useTranslation()

  const [detailCondKey, setDetailCondKey] = useState<string | null>(null)
  const [detailAbility, setDetailAbility] = useState<Ability | null>(null)
  const [selectedClass, setSelectedClass] = useState<string>(() => pickDefaultClass(char))

  useEffect(() => {
    if (!(char.classes ?? []).some((c) => c.class_name === selectedClass)) {
      setSelectedClass(pickDefaultClass(char))
    }
  }, [char.classes, selectedClass])

  const hpPct = char.hit_points > 0
    ? Math.round((char.current_hit_points / char.hit_points) * 100)
    : 0

  const passiveAbilities = char.abilities?.filter((a) => a.is_passive) ?? []
  const activeConditions = char.conditions
    ? Object.entries(char.conditions).filter(([, v]) => v)
    : []

  const currentClassEntry = char.classes?.find((c) => c.class_name === selectedClass)
  const currentClassLevel = currentClassEntry?.level ?? 1

  return (
    <div className="p-4 space-y-3 pb-safe">
      {/* Hero card */}
      <Surface
        variant="tome"
        ornamented
        layoutId={`char-hero-${char.id}`}
        className="relative overflow-hidden"
      >
        <m.button
          type="button"
          onClick={() => { haptic.light(); navigate(`/char/${char.id}/identity`) }}
          whileTap={{ scale: 0.99 }}
          className="block w-full text-left"
          aria-label={t('character.identity.title', { defaultValue: 'Identity' })}
        >
          <p className="text-sm text-dnd-text-muted font-body italic mb-0.5">{char.class_summary}</p>
          {char.race && (
            <p className="text-xs text-dnd-text-faint font-body">{char.race}</p>
          )}
        </m.button>

        <div className="mt-4 flex items-center gap-3">
          <div className="flex-1 min-w-0">
            <m.button
              type="button"
              onClick={() => { haptic.light(); navigate(`/char/${char.id}/hp`) }}
              whileTap={{ scale: 0.99 }}
              className="w-full text-left"
              aria-label={t('character.hp.title', { defaultValue: 'Hit Points' })}
            >
              <div className="flex items-center justify-between text-sm mb-1.5">
                <span className="inline-flex items-center gap-1.5 font-mono">
                  <GiHeartPlus size={14} className="text-[var(--dnd-crimson-bright)]" />
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
            </m.button>

            <HeroXPBar
              currentXP={char.experience_points}
              totalClassLevel={char.total_level}
              onLevelUpReady={() => navigate(`/char/${char.id}/xp`)}
            />
          </div>

          <m.button
            type="button"
            onClick={() => { haptic.light(); navigate(`/char/${char.id}/ac`) }}
            whileTap={{ scale: 0.95 }}
            className="shrink-0 relative opacity-90"
            aria-label={t('character.ac.title', { defaultValue: 'Armor Class' })}
          >
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
          </m.button>
        </div>

        {char.concentrating_spell_id && (() => {
          const spell = char.spells?.find((s) => s.id === char.concentrating_spell_id)
          return (
            <m.button
              onClick={() => navigate(`/char/${char.id}/spells`)}
              className="mt-3 w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl
                         bg-gradient-arcane-mist border border-dnd-arcane/50 text-dnd-arcane-bright
                         text-xs font-cinzel uppercase tracking-wider"
              whileTap={{ scale: 0.98 }}
            >
              <GiPotionBall size={14} />
              {spell?.name ?? t('character.spells.concentration')}
            </m.button>
          )
        })()}

        {passiveAbilities.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-3 overflow-x-auto scrollbar-hide max-h-14">
            {passiveAbilities.map((a) => (
              <StatPill
                key={a.id}
                icon={<GiLightningTrio size={10} />}
                value={a.name}
                tone="gold"
                size="sm"
                onClick={() => setDetailAbility(a)}
              />
            ))}
          </div>
        )}

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

        <StatPill
          icon={<GiBootPrints size={14} />}
          value={`${char.speed} ft`}
          tone="emerald"
          size="sm"
          iconOnly
          revealOnTap
          aria-label={`${t('character.identity.speed', { defaultValue: 'Speed' })}: ${char.speed} ft`}
          className="absolute bottom-3 right-3"
        />

        {/* Ability scores anchored at the bottom of the hero card */}
        {char.ability_scores.length > 0 && (
          <div className="mt-4 pt-3 border-t border-dnd-gold-dim/30">
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
                    onClick={() => { haptic.light(); navigate(`/char/${char.id}/stats`) }}
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
          </div>
        )}
      </Surface>

      {/* Spell slots summary */}
      {char.spell_slots && <SpellSlotsSummary slots={char.spell_slots} />}

      {/* Class progression preview */}
      {char.classes && char.classes.length > 0 && (
        <div>
          <ClassTabs
            classes={char.classes}
            selected={selectedClass}
            onSelect={setSelectedClass}
          />
          <ProgressionPreview
            className={selectedClass}
            currentLevel={currentClassLevel}
          />
        </div>
      )}

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

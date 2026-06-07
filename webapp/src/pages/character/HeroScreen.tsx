import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { CircleDot } from 'lucide-react'
import {
  GiHeartPlus, GiKnapsack, GiLightningTrio, GiPotionBall,
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
import type { Ability, CharacterFull } from '@/types'
import { useUnitSettings, formatWeightValue, weightUnitLabel } from '@/store/unitSettings'

// Canonical D&D 5e ordering — STR/DEX/CON/INT/WIS/CHA — used wherever ability
// scores are surfaced to players. Backend returns alphabetical (cha/con/...).
const DND_ABILITY_ORDER = [
  'strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma',
]

interface Props {
  char: CharacterFull
}

export default function HeroScreen({ char }: Props) {
  const navigate = useNavigate()
  const { t } = useTranslation()

  const [detailCondKey, setDetailCondKey] = useState<string | null>(null)
  const [detailAbility, setDetailAbility] = useState<Ability | null>(null)

  const hpMax = char.hit_points + (char.hp_max_homebrew_modifier ?? 0)
  const acTotal = char.ac + (char.ac_breakdown?.homebrew ?? 0)
  const unitSystem = useUnitSettings((s) => s.system)
  const weightLabel = formatWeightValue(char.encumbrance, unitSystem)
  const overloaded = char.encumbrance > char.carry_capacity

  const hpPct = hpMax > 0
    ? Math.round((char.current_hit_points / hpMax) * 100)
    : 0

  const passiveAbilities = char.abilities?.filter((a) => a.is_passive) ?? []
  const activeConditions = char.conditions
    ? Object.entries(char.conditions).filter(([, v]) => v)
    : []

  return (
    <div className="@container p-4 space-y-3 pb-safe">
      {/* Hero card */}
      <Surface
        variant="tome"
        ornamented
        className="relative overflow-hidden"
      >
        <m.button
          type="button"
          onClick={() => { haptic.light(); navigate(`/char/${char.id}/identity`) }}
          whileTap={{ scale: 0.99 }}
          className="block w-full text-left pr-14"
          aria-label={t('character.identity.title', { defaultValue: 'Identity' })}
        >
          <p className="text-sm text-dnd-text-muted font-body italic mb-0.5">{char.class_summary}</p>
          {char.race && (
            <p className="text-xs text-dnd-text-muted font-body">{char.race}</p>
          )}
        </m.button>

        <m.button
          type="button"
          onClick={() => { haptic.light(); navigate(`/char/${char.id}/inventory`) }}
          whileTap={{ scale: 0.95 }}
          aria-label={t('character.inventory.weight_badge_aria', { n: weightLabel })}
          className={`absolute top-1 right-1 z-[3] flex flex-col items-center justify-center gap-0.5 min-w-[44px] min-h-[44px] px-2 py-1 rounded-xl bg-dnd-bg ${overloaded ? 'border border-[var(--dnd-amber)]' : 'border border-dnd-gold-dim'}`}
        >
          <GiKnapsack
            size={20}
            aria-hidden="true"
            className={overloaded ? 'text-[var(--dnd-amber)]' : 'text-dnd-gold-bright'}
          />
          <span className={`text-[11px] font-mono font-bold tabular-nums leading-none ${overloaded ? 'text-[var(--dnd-amber)]' : 'text-dnd-text'}`}>
            {weightLabel}
          </span>
          <span className="text-[10px] font-mono text-dnd-text-muted leading-none">
            {weightUnitLabel(unitSystem)}
          </span>
        </m.button>

        <div className="mt-4 flex items-center gap-3 @max-[300px]:flex-col @max-[300px]:items-stretch">
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
                    {char.current_hit_points}/{hpMax}
                  </span>
                  {char.temp_hp > 0 && (
                    <span className="text-[var(--dnd-cobalt-bright)]">(+{char.temp_hp} temp)</span>
                  )}
                </span>
                <span className="text-dnd-text-muted font-mono text-xs">{hpPct}%</span>
              </div>
              <HPGauge
                current={char.current_hit_points}
                max={hpMax}
                temp={char.temp_hp}
                size="md"
                segmented
              />
            </m.button>

            <m.button
              type="button"
              onClick={() => { haptic.light(); navigate(`/char/${char.id}/xp`) }}
              whileTap={{ scale: 0.99 }}
              className="w-full text-left mt-1"
              aria-label={t('character.xp.title', { defaultValue: 'Experience' })}
            >
              <HeroXPBar
                currentXP={char.experience_points}
                totalClassLevel={char.total_level}
                suppressHalo={hpPct > 0 && hpPct <= 25}
              />
            </m.button>
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
                    style={{ textShadow: '0 1px 3px rgba(var(--dnd-shadow-color), 0.6)' }}>
                {acTotal}
              </span>
              <span className="text-[11px] font-cinzel uppercase tracking-wide text-dnd-gold-dim leading-none mt-0.5">
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
              className="mt-3 w-full min-h-[44px] flex items-center justify-center gap-2 px-3 py-2 rounded-xl
                         bg-gradient-arcane-mist border border-dnd-arcane/50 text-dnd-arcane-bright"
              whileTap={{ scale: 0.98 }}
            >
              <GiPotionBall size={14} aria-hidden />
              <span className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-arcane-bright/80">
                {t('character.spells.concentration')}
              </span>
              {spell?.name && (
                <span className="font-body italic text-sm text-dnd-arcane-bright">
                  {spell.name}
                </span>
              )}
            </m.button>
          )
        })()}

        {passiveAbilities.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-3">
            {passiveAbilities.map((a) => (
              <StatPill
                key={a.id}
                icon={<GiLightningTrio size={10} />}
                value={a.name}
                tone="gold"
                size="sm"
                expandHitArea
                onClick={() => setDetailAbility(a)}
              />
            ))}
          </div>
        )}

        {activeConditions.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-3">
            {activeConditions.map(([key, val]) => {
              const Icon = CONDITION_ICONS[key] ?? CircleDot
              return (
                <StatPill
                  key={key}
                  icon={<Icon size={14} />}
                  value={formatCondition(key, val, t)}
                  tone="crimson"
                  size="sm"
                  expandHitArea
                  onClick={() => setDetailCondKey(key)}
                />
              )
            })}
          </div>
        )}

        {/* Ability scores anchored at the bottom of the hero card */}
        {char.ability_scores.length > 0 && (
          <div className="mt-4 pt-3 border-t border-dnd-gold-dim/30">
            <m.div
              className="grid grid-cols-6 @max-[300px]:grid-cols-3 gap-1.5 text-center"
              initial="initial"
              animate="animate"
              variants={{
                initial: {},
                animate: { transition: { staggerChildren: 0.04, delayChildren: 0.1 } },
              }}
            >
              {[...char.ability_scores]
                .sort((a, b) => DND_ABILITY_ORDER.indexOf(a.name) - DND_ABILITY_ORDER.indexOf(b.name))
                .map((score) => {
                const modStr = `${score.modifier >= 0 ? '+' : ''}${score.modifier}`
                const shortLabel = t(`character.ability.${score.name}_short`, {
                  defaultValue: score.name.slice(0, 3).toUpperCase(),
                })
                return (
                  <m.button
                    key={score.name}
                    type="button"
                    onClick={() => { haptic.light(); navigate(`/char/${char.id}/stats`) }}
                    aria-label={`${shortLabel}: ${score.value}, mod ${modStr}`}
                    className="flex flex-col items-center rounded-lg p-1.5 border bg-dnd-surface-raised border-dnd-border text-dnd-text cursor-pointer hover:border-dnd-gold transition-colors"
                    variants={{ initial: { opacity: 0, y: 8 }, animate: { opacity: 1, y: 0 } }}
                    transition={spring.snappy}
                    whileTap={{ scale: 0.95 }}
                  >
                    <span className="text-[11px] font-cinzel uppercase tracking-wider opacity-80">
                      {shortLabel}
                    </span>
                    <span className="text-xl font-mono font-bold tabular-nums leading-none mt-0.5">{score.value}</span>
                    <span className="text-[11px] font-mono font-bold mt-0.5 px-1.5 py-0.5 rounded-full bg-[rgba(13,10,8,0.25)]">
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

import { askRollOptions, refreshAfterOptions } from '@/lib/rollOptions'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { classSummary } from '@/lib/classLabel'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { m } from 'framer-motion'
import { CircleDot, HeartPulse, SlidersHorizontal } from 'lucide-react'
import {
  GiCheckedShield, GiFlame, GiHeartPlus, GiKnapsack, GiLightningTrio,
  GiPotionBall, GiSkullCrossedBones,
} from 'react-icons/gi'
import HPGauge from '@/components/ui/HPGauge'
import HeroXPBar from '@/components/ui/HeroXPBar'
import Surface from '@/components/ui/Surface'
import StatPill from '@/components/ui/StatPill'
import { ShieldEmblem } from '@/components/ui/Ornament'
import Pressable from '@/components/ui/Pressable'
import { haptic } from '@/auth/telegram'
import { spring } from '@/styles/motion'
import { formatCondition, CONDITION_ICONS } from '@/lib/conditions'
import { damageTypeLabel } from '@/lib/damageModifier'
import ConditionDetailModal from '@/pages/conditions/ConditionDetailModal'
import PassiveAbilityDetailModal from '@/pages/abilities/PassiveAbilityDetailModal'
import SpellSlotsSummary from '@/components/character/SpellSlotsSummary'
import HeroStatsSection from '@/components/character/HeroStatsSection'
import PendingChoicesBadge from '@/components/character/PendingChoicesBadge'
import YourTurnBanner from '@/components/character/YourTurnBanner'
import QuickActions from '@/components/character/QuickActions'
import ActiveFormBanner from '@/components/character/ActiveFormBanner'
import ActiveStatesBar from '@/components/rules/ActiveStatesBar'
import HpQuickSheet from '@/components/character/HpQuickSheet'
import HeroLayoutSheet from '@/components/character/HeroLayoutSheet'
import { DeathSaveTracker } from '@/pages/hp/DeathSaves'
import DeathSaveResultDialog from '@/pages/hp/DeathSaveResultDialog'
import { api, type DeathSaveRollResult } from '@/api/client'
import { useD20Roll, d20Arg, type RollMode } from '@/hooks/useD20Roll'
import { useIsFirstValue } from '@/hooks/useIsFirstValue'
import { isConcentrating, concentrationLabel } from '@/lib/concentration'
import { readHeroLayout, type HeroSectionKey } from '@/lib/heroLayout'
import { hpNumeralTone } from '@/lib/hpTone'
import type { Ability, CharacterFull } from '@/types'
import { useUnitSettings, formatWeightValue, weightUnitLabel } from '@/store/unitSettings'

// Canonical D&D 5e ordering — STR/DEX/CON/INT/WIS/CHA — used wherever ability
// scores are surfaced to players. Backend returns alphabetical (cha/con/...).
const DND_ABILITY_ORDER = [
  'strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma',
]

// Stessa mappatura icona/tono del menu Identità (dove i valori si editano).
const DMG_MODIFIER_GROUPS = [
  { key: 'resistances', tone: 'cobalt', Icon: GiCheckedShield },
  { key: 'immunities', tone: 'gold', Icon: GiLightningTrio },
  { key: 'vulnerabilities', tone: 'crimson', Icon: GiFlame },
] as const

interface Props {
  char: CharacterFull
}

export default function HeroScreen({ char }: Props) {
  const navigate = useNavigate()
  const { t } = useTranslation()

  const [detailCondKey, setDetailCondKey] = useState<string | null>(null)
  const [detailAbility, setDetailAbility] = useState<Ability | null>(null)
  const [hpSheetOpen, setHpSheetOpen] = useState(false)
  const [layoutSheetOpen, setLayoutSheetOpen] = useState(false)
  const [deathRollResult, setDeathRollResult] = useState<DeathSaveRollResult | null>(null)

  const qc = useQueryClient()
  const rollD20 = useD20Roll()
  const deathRollMutation = useMutation({
    mutationFn: async (mode: RollMode) => {
      const choice = await askRollOptions(char.id, { roll: 'death_save' })
      return api.characters.rollDeathSave(char.id, d20Arg(mode, await rollD20(mode), choice))
    },
    onSuccess: (result) => {
      setDeathRollResult(result)
      qc.invalidateQueries({ queryKey: ['character', char.id] })
      refreshAfterOptions(qc, char.id, result.option_result)
      haptic.success()
    },
  })

  // Stessa definizione della pagina HP: a 0 PF stabile o da morto non si tira.
  const deathSaves = char.death_saves ?? { successes: 0, failures: 0, stable: false }
  const atZero = char.current_hit_points === 0
  const isDying = atZero && !deathSaves.stable && !char.is_dead

  const form = char.active_form ?? null
  // In forma selvatica la barra PF e la CA mostrano quelle della forma.
  // Nel 2024 la forma non ha PF propri: barra e PF temporanei restano quelli del personaggio.
  const ownForm = form?.own_hp === false ? null : form
  const hpMax = ownForm ? ownForm.max_hp : char.computed?.hp_max_effective ?? char.hit_points + (char.hp_max_homebrew_modifier ?? 0)
  const hpCurrent = ownForm ? ownForm.current_hp : char.current_hit_points
  const tempHp = ownForm ? ownForm.temp_hp : char.temp_hp
  const acTotal = form ? form.armor_class : char.ac + (char.ac_breakdown?.homebrew ?? 0) + (char.ac_breakdown?.items ?? 0)
  const unitSystem = useUnitSettings((s) => s.system)
  const encumbranceTotal = char.encumbrance_total ?? char.encumbrance
  const weightLabel = formatWeightValue(encumbranceTotal, unitSystem)
  const overloaded = encumbranceTotal > char.carry_capacity

  const hpPct = hpMax > 0
    ? Math.round((hpCurrent / hpMax) * 100)
    : 0
  // Pop del numero solo quando cambia, non all'ingresso nell'hub.
  const isFirstHp = useIsFirstValue(hpCurrent)

  const passiveAbilities = char.abilities?.filter((a) => a.is_passive) ?? []
  const activeConditions = char.conditions
    ? Object.entries(char.conditions).filter(([, v]) => v)
    : []

  const damageModifiers = (char.damage_modifiers ?? {}) as Record<string, string[]>
  const damageBadges = DMG_MODIFIER_GROUPS.flatMap(({ key, tone, Icon }) =>
    (damageModifiers[key] ?? []).map((raw) => ({ id: `${key}-${raw}`, group: key, tone, Icon, value: damageTypeLabel(t, raw) })),
  )

  const layout = readHeroLayout(char.settings as Record<string, unknown> | undefined)

  return (
    <div className="@container p-4 space-y-3 pb-safe">
      <YourTurnBanner charId={char.id} />
      <PendingChoicesBadge char={char} />
      {/* Hero card */}
      <Surface
        variant={isDying ? 'ember' : 'tome'}
        ornamented
        className="relative overflow-hidden"
      >
        <Pressable
          type="button"
          onClick={() => { haptic.light(); navigate(`/char/${char.id}/identity`) }}
          whileTap={{ scale: 0.99 }}
          /* Reserve the second (race) line's height even when no race is set, so the
             AC shield row below stays clear of the absolutely-positioned bag button. */
          className="block w-full text-left pr-14 min-h-[44px]"
          aria-label={t('character.identity.title', { defaultValue: 'Identity' })}
        >
          <p className="text-sm text-dnd-text-muted font-body italic mb-0.5">{classSummary(t, char.classes ?? [])}</p>
          {char.race && (
            <p className="text-xs text-dnd-text-muted font-body">{char.race}</p>
          )}
        </Pressable>

        <Pressable
          type="button"
          onClick={() => { haptic.light(); navigate(`/char/${char.id}/inventory`) }}
          whileTap={{ scale: 0.95 }}
          aria-label={t('character.inventory.weight_badge_aria', { n: weightLabel })}
          className={`absolute top-1 right-1 z-[3] flex flex-col items-center justify-center gap-0.5 min-w-[44px] min-h-[44px] px-2 py-1 rounded-xl bg-dnd-bg ${overloaded ? 'border border-dnd-amber' : 'border border-dnd-gold-dim'}`}
        >
          <GiKnapsack
            size={20}
            aria-hidden="true"
            className={overloaded ? 'text-dnd-amber' : 'text-dnd-gold-bright'}
          />
          <span className={`text-xs font-mono font-bold tabular-nums leading-none ${overloaded ? 'text-dnd-amber' : 'text-dnd-text'}`}>
            {weightLabel}
          </span>
          <span className="text-xs font-mono text-dnd-text-muted leading-none">
            {weightUnitLabel(unitSystem)}
          </span>
        </Pressable>

        {char.is_dead && (
          <Pressable
            type="button"
            onClick={() => { haptic.light(); navigate(`/char/${char.id}/hp`) }}
            whileTap={{ scale: 0.98 }}
            aria-label={t('character.death_saves.dead_title')}
            className="mt-3 w-full min-h-[44px] flex items-center justify-center gap-2 px-3 py-2 rounded-xl
                       bg-[rgba(179,58,58,0.12)] border border-dnd-crimson/50 text-dnd-crimson-bright"
          >
            <GiSkullCrossedBones size={16} aria-hidden />
            <span className="text-xs font-cinzel uppercase tracking-widest font-bold">
              {t('character.death_saves.dead_title')}
            </span>
            <span className="font-body italic text-sm">
              {t('character.death_saves.revive')}
            </span>
          </Pressable>
        )}

        {form && <ActiveFormBanner charId={char.id} form={form} />}
        <ActiveStatesBar char={char} />

        <div className="mt-4 flex items-center gap-3 @max-[300px]:flex-col @max-[300px]:items-stretch">
          <div className="flex-1 min-w-0">
            <Pressable
              type="button"
              onClick={() => {
                haptic.light()
                if (char.is_dead) navigate(`/char/${char.id}/hp`)
                else setHpSheetOpen(true)
              }}
              whileTap={{ scale: 0.99 }}
              className="w-full min-h-[44px] text-left"
              aria-label={t('character.hp.title', { defaultValue: 'Hit Points' })}
            >
              <div className="flex flex-wrap items-baseline gap-x-1.5 mb-2">
                <GiHeartPlus size={16} aria-hidden className="self-center shrink-0 text-dnd-crimson-bright" />
                <m.span
                  key={hpCurrent}
                  initial={isFirstHp ? false : { scale: 0.85, opacity: 0.4 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={spring.elastic}
                  data-testid="hero-hp-current"
                  className={`font-display font-black leading-none text-[3.5rem] ${hpNumeralTone(hpPct)}`}
                >
                  {hpCurrent}
                </m.span>
                <span className="font-mono text-base tabular-nums text-dnd-text-muted">/{hpMax}</span>
                {tempHp > 0 && (
                  <span className="font-mono text-sm tabular-nums whitespace-nowrap text-dnd-cobalt-bright">(+{tempHp} temp)</span>
                )}
              </div>
              <HPGauge
                current={hpCurrent}
                max={hpMax}
                temp={tempHp}
                size="md"
                segmented
              />
            </Pressable>

            <Pressable
              type="button"
              onClick={() => { haptic.light(); navigate(`/char/${char.id}/xp`) }}
              whileTap={{ scale: 0.99 }}
              className="w-full min-h-[44px] flex flex-col justify-center text-left"
              aria-label={t('character.xp.title', { defaultValue: 'Experience' })}
            >
              <HeroXPBar
                currentXP={char.experience_points}
                totalClassLevel={char.total_level}
                milestone={char.settings?.advancement === 'milestone'}
                suppressHalo={hpPct <= 25}
              />
            </Pressable>
          </div>

          <Pressable
            type="button"
            onClick={() => { haptic.light(); navigate(`/char/${char.id}/ac`) }}
            whileTap={{ scale: 0.95 }}
            className="shrink-0 relative"
            aria-label={t('character.ac.title', { defaultValue: 'Armor Class' })}
          >
            <ShieldEmblem size={104} />
            <span className="absolute inset-0 flex flex-col items-center justify-center pb-1">
              <span className="text-4xl font-display font-black text-dnd-gold-bright leading-none"
                    style={{ textShadow: '0 1px 3px rgba(var(--dnd-shadow-color), 0.6)' }}>
                {acTotal}
              </span>
              <span className="text-xs font-cinzel uppercase tracking-wide text-dnd-gold-dim leading-none mt-0.5">
                {t('character.ac.short', { defaultValue: 'CA' })}
              </span>
            </span>
          </Pressable>
        </div>

        {isDying && (
          <div className="mt-4 flex flex-col gap-4">
            <p className="flex items-center justify-center gap-2 font-display font-bold text-base tracking-wide text-dnd-crimson-bright">
              <GiSkullCrossedBones size={18} aria-hidden />
              {t('character.death_saves.title')}
            </p>
            <DeathSaveTracker
              deathSaves={deathSaves}
              onRoll={(mode) => deathRollMutation.mutate(mode)}
              isRolling={deathRollMutation.isPending}
            />
          </div>
        )}

        {atZero && deathSaves.stable && !char.is_dead && (
          <p className="mt-3 flex items-center justify-center gap-1.5 rounded-lg px-3 py-1.5
                        text-xs font-cinzel font-bold uppercase tracking-wider
                        bg-dnd-cobalt/10 border border-dnd-cobalt/40 text-dnd-cobalt-bright">
            <HeartPulse size={13} aria-hidden />
            {t('character.death_saves.stabilized_badge')}
          </p>
        )}

        {isConcentrating(char) && (() => {
          const spellName = concentrationLabel(char)
          return (
            <Pressable
              onClick={() => navigate(`/char/${char.id}/spells`)}
              className="mt-3 w-full min-h-[44px] flex items-center justify-center gap-2 px-3 py-2 rounded-xl
                         bg-gradient-arcane-mist border border-dnd-arcane/50 text-dnd-arcane-bright"
              whileTap={{ scale: 0.98 }}
            >
              <GiPotionBall size={14} aria-hidden />
              <span className="text-xs font-cinzel uppercase tracking-widest text-dnd-arcane-bright/80">
                {t('character.spells.concentration')}
              </span>
              {spellName && (
                <span className="font-body italic text-sm text-dnd-arcane-bright">
                  {spellName}
                </span>
              )}
            </Pressable>
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
                  value={formatCondition(key, val, t, char.rules_edition)}
                  tone="crimson"
                  size="sm"
                  expandHitArea
                  onClick={() => setDetailCondKey(key)}
                />
              )
            })}
          </div>
        )}

        {/* Resistenze / immunità / vulnerabilità — si editano in Identità */}
        {damageBadges.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-3">
            {damageBadges.map((b) => (
              <StatPill
                key={b.id}
                icon={<b.Icon size={10} />}
                label={t(`character.identity.${b.group}_short`)}
                value={b.value}
                tone={b.tone}
                size="sm"
                expandHitArea
                aria-label={`${t(`character.identity.${b.group}`)}: ${b.value}`}
                onClick={() => { haptic.light(); navigate(`/char/${char.id}/identity`) }}
              />
            ))}
          </div>
        )}

        {/* Ability scores anchored at the bottom of the hero card */}
        {char.ability_scores.length > 0 && (
          <div className="mt-4 pt-3 border-t border-dnd-gold-dim/30">
            <m.div
              className="grid grid-cols-6 @max-[300px]:grid-cols-3 divide-x divide-dnd-border/60 text-center"
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
                  <Pressable
                    key={score.name}
                    type="button"
                    onClick={() => { haptic.light(); navigate(`/char/${char.id}/stats`) }}
                    aria-label={`${shortLabel}: ${score.value}, mod ${modStr}`}
                    className="flex flex-col items-center py-1 text-dnd-text cursor-pointer hover:bg-dnd-surface/60 transition-colors"
                    variants={{ initial: { opacity: 0, y: 8 }, animate: { opacity: 1, y: 0 } }}
                    transition={spring.snappy}
                    whileTap={{ scale: 0.95 }}
                  >
                    <span className="text-xs font-cinzel uppercase tracking-wider text-dnd-text-muted">
                      {shortLabel}
                    </span>
                    {/* Il modificatore è il numero che si tira: guida lui, il punteggio accompagna. */}
                    <span className="text-xl font-mono font-bold tabular-nums leading-none mt-0.5">{modStr}</span>
                    <span className="text-xs font-mono tabular-nums mt-1 text-dnd-text-muted">
                      {score.value}
                    </span>
                  </Pressable>
                )
              })}
            </m.div>
          </div>
        )}
      </Surface>

      {/* Sezioni sotto la hero card: ordine e visibilità da settings.hero_layout */}
      {layout.order.map((key: HeroSectionKey) => {
        if (layout.hidden.includes(key)) return null
        if (key === 'slots') return char.spell_slots
          ? <SpellSlotsSummary key={key} slots={char.spell_slots} />
          : null
        if (key === 'stats') return <HeroStatsSection key={key} char={char} />
        return <QuickActions key={key} char={char} />
      })}

      {/* Personalizzazione layout (spec 2026-07-17) */}
      <Pressable
        type="button"
        onClick={() => { haptic.light(); setLayoutSheetOpen(true) }}
        whileTap={{ scale: 0.98 }}
        className="w-full min-h-[44px] flex items-center justify-center gap-2 rounded-xl
                   text-dnd-text-faint hover:text-dnd-gold-dim transition-colors"
      >
        <SlidersHorizontal size={13} aria-hidden />
        <span className="text-xs font-cinzel uppercase tracking-widest">
          {t('character.hero.customize')}
        </span>
      </Pressable>

      {/* Modals */}
      {detailCondKey !== null && (
        <ConditionDetailModal
          condKey={detailCondKey}
          exhaustionLevel={
            typeof (char.conditions as Record<string, unknown>)?.['exhaustion'] === 'number'
              ? ((char.conditions as Record<string, unknown>)['exhaustion'] as number)
              : 0
          }
          edition={char.rules_edition}
          onClose={() => setDetailCondKey(null)}
        />
      )}
      {detailAbility !== null && (
        <PassiveAbilityDetailModal
          ability={detailAbility}
          charId={char.id}
          onClose={() => setDetailAbility(null)}
        />
      )}
      {deathRollResult && (
        <DeathSaveResultDialog result={deathRollResult} onClose={() => setDeathRollResult(null)} afterRoll={{ charId: char.id }} />
      )}
      <HpQuickSheet char={char} open={hpSheetOpen} onClose={() => setHpSheetOpen(false)} />
      <HeroLayoutSheet char={char} open={layoutSheetOpen} onClose={() => setLayoutSheetOpen(false)} />
    </div>
  )
}

import { useState, Fragment } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Check, Eye } from 'lucide-react'
import {
  GiPerspectiveDiceSixFacesRandom as Dices, GiPolarStar as Star,
} from 'react-icons/gi'
import { api, ApiError } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import SectionDivider from '@/components/ui/SectionDivider'
import StatPill from '@/components/ui/StatPill'
import Sheet from '@/components/ui/Sheet'
import ScrollArea from '@/components/ScrollArea'
import RollResultModal, { type RollResult } from '@/components/RollResultModal'
import { haptic } from '@/auth/telegram'
import { useToast } from '@/hooks/useToast'
import { useLongPress } from '@/hooks/useLongPress'
import { useDiceAnimation } from '@/dice/useDiceAnimation'
import { useDiceSettings } from '@/store/diceSettings'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import { profBonus } from '@/lib/dnd'
import HomebrewBreakdownRow from '@/components/homebrew/HomebrewBreakdownRow'
import SkillsSkeleton from '@/components/skeletons/SkillsSkeleton'

const SKILLS: { key: string; ability: string }[] = [
  { key: 'acrobatics',     ability: 'dexterity' },
  { key: 'animal_handling', ability: 'wisdom' },
  { key: 'arcana',         ability: 'intelligence' },
  { key: 'athletics',      ability: 'strength' },
  { key: 'deception',      ability: 'charisma' },
  { key: 'history',        ability: 'intelligence' },
  { key: 'insight',        ability: 'wisdom' },
  { key: 'intimidation',   ability: 'charisma' },
  { key: 'investigation',  ability: 'intelligence' },
  { key: 'medicine',       ability: 'wisdom' },
  { key: 'nature',         ability: 'intelligence' },
  { key: 'perception',     ability: 'wisdom' },
  { key: 'performance',    ability: 'charisma' },
  { key: 'persuasion',     ability: 'charisma' },
  { key: 'religion',       ability: 'intelligence' },
  { key: 'sleight_of_hand', ability: 'dexterity' },
  { key: 'stealth',        ability: 'dexterity' },
  { key: 'survival',       ability: 'wisdom' },
]

const ABILITY_GROUPS: string[] = ['strength', 'dexterity', 'intelligence', 'wisdom', 'charisma']

type ProfLevel = false | true | 'expert'

function getLevel(val: unknown): ProfLevel {
  if (val === 'expert') return 'expert'
  if (val === true || val === 1) return true
  return false
}

function nextLevel(current: ProfLevel): ProfLevel {
  if (current === false) return true
  if (current === true) return 'expert'
  return false
}

interface SkillRowProps {
  skillKey: string
  label: string
  level: ProfLevel
  bonus: number
  idx: number
  rollPending: boolean
  onTap: () => void
  onLongPress: () => void
  onRoll: () => void
  rollAriaLabel: string
}

function SkillRow({
  skillKey,
  label,
  level,
  bonus,
  idx,
  rollPending,
  onTap,
  onLongPress,
  onRoll,
  rollAriaLabel,
}: SkillRowProps) {
  const [pressProgress, setPressProgress] = useState(0)
  const longPress = useLongPress({
    thresholdMs: 500,
    onClick: onTap,
    onLongPress,
    onProgress: setPressProgress,
  })
  const isExpert = level === 'expert'
  const isProficient = level === true
  const hasMark = isExpert || isProficient

  // Circumference of an r=20 circle (the ring radius below).
  const RING_CIRC = 2 * Math.PI * 20
  const ringActive = pressProgress > 0 && pressProgress < 1

  return (
    <m.div
      key={skillKey}
      initial={{ opacity: 0, x: -4 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: idx * 0.02, duration: 0.18 }}
      className={`flex items-center gap-2 px-3 py-2 rounded-xl border transition-colors
        ${isExpert
          ? 'bg-gradient-to-r from-[var(--dnd-arcane-deep)]/30 to-[var(--dnd-gold-deep)]/20 border-dnd-arcane/40'
          : isProficient
            ? 'bg-dnd-surface-raised border-dnd-gold/30'
            : 'bg-dnd-surface border-dnd-border'}`}
    >
      <div
        {...longPress}
        className="flex items-center gap-2 flex-1 min-w-0 select-none cursor-pointer"
      >
        <div className="relative w-11 h-11 rounded-full flex items-center justify-center shrink-0">
          {/* Halo-as-Signal progress ring during long-press hold */}
          {ringActive && (
            <svg
              className="absolute inset-0 w-11 h-11 pointer-events-none"
              viewBox="0 0 44 44"
              aria-hidden="true"
            >
              <circle
                cx="22"
                cy="22"
                r="20"
                fill="none"
                stroke="var(--dnd-gold-bright)"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeDasharray={`${pressProgress * RING_CIRC} ${RING_CIRC}`}
                transform="rotate(-90 22 22)"
                style={{ filter: 'drop-shadow(0 0 3px var(--dnd-gold-glow))' }}
              />
            </svg>
          )}
          {isExpert ? (
            <div className="relative w-5 h-5 rounded-full bg-gradient-to-br from-dnd-arcane-bright to-dnd-gold-bright border-2 border-dnd-gold-bright flex items-center justify-center shadow-[0_0_6px_var(--dnd-gold-glow)]">
              <Star size={10} className="text-dnd-ink" fill="currentColor" strokeWidth={1} />
            </div>
          ) : isProficient ? (
            <div className="w-5 h-5 rounded-full bg-dnd-gold border-2 border-dnd-gold-bright flex items-center justify-center shadow-[0_0_4px_var(--dnd-gold-glow)]">
              <Check size={11} className="text-dnd-ink" strokeWidth={3} />
            </div>
          ) : (
            <div className="w-5 h-5 rounded-full border-2 border-dnd-border" />
          )}
        </div>
        <span
          className="flex-1 text-left text-sm font-body font-medium truncate"
          title={label}
        >
          {label}
        </span>
        <span className={`text-sm font-mono font-bold w-10 text-right shrink-0 tabular-nums
          ${hasMark
            ? 'text-dnd-gold-bright'
            : bonus >= 0 ? 'text-dnd-text' : 'text-[var(--dnd-crimson-bright)]'}`}>
          {bonus >= 0 ? '+' : ''}{bonus}
        </span>
      </div>
      <m.button
        onClick={onRoll}
        disabled={rollPending}
        className="shrink-0 w-11 h-11 rounded-xl bg-dnd-chip-bg border border-dnd-gold-dim/40 flex items-center justify-center text-dnd-gold disabled:opacity-30"
        whileTap={{ scale: 0.88 }}
        aria-label={rollAriaLabel}
      >
        <Dices size={16} />
      </m.button>
    </m.div>
  )
}

export default function Skills() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const dice = useDiceAnimation()
  const animate3d = useDiceSettings((s) => s.animate3d)
  const reducedMotion = useReducedMotion()
  type RollState = {
    result: RollResult
    skillName: string
    wasRerolled: boolean
  }
  const [rollState, setRollState] = useState<RollState | null>(null)
  const [picker, setPicker] = useState<string | null>(null)
  const toast = useToast()

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const mutation = useMutation({
    mutationFn: (skills: Record<string, unknown>) =>
      api.characters.updateSkills(charId, skills),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.light()
    },
    onError: () => haptic.error(),
  })

  const rollMutation = useMutation({
    mutationFn: async (skillName: string) => {
      const useAnimation = animate3d && !reducedMotion
      let die: number | undefined
      if (useAnimation) {
        const detected = await dice.playAndCollect([{ kind: 'd20', count: 1 }])
        die = detected[0]?.value
      }
      const result = await api.characters.rollSkill(charId, skillName, die)
      return { result, skillName }
    },
    onSuccess: ({ result, skillName }) => {
      // The backend returns the raw skill key (e.g. "athletics") as the roll
      // description; it's redundant with the localized modal title and would
      // surface an untranslated EN key, so drop it.
      setRollState({ result: { ...result, description: undefined }, skillName, wasRerolled: false })
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const rerollMutation = useMutation({
    mutationFn: async (skillName: string) => {
      const useAnimation = animate3d && !reducedMotion
      let die: number | undefined
      if (useAnimation) {
        const detected = await dice.playAndCollect([{ kind: 'd20', count: 1 }])
        die = detected[0]?.value
      }
      return api.characters.rollSkill(charId, skillName, die, true)
    },
    onSuccess: (result) => {
      setRollState((prev) => prev && { ...prev, result: { ...result, description: undefined }, wasRerolled: true })
      qc.invalidateQueries({ queryKey: ['character', charId] })
      haptic.success()
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) {
        toast.error(t('character.inspiration.unavailable_error'))
        qc.invalidateQueries({ queryKey: ['character', charId] })
      } else {
        haptic.error()
      }
    },
  })

  if (!char) {
    return (
      <Layout title={t('character.skills.title')} backTo={`/char/${charId}`} group="skills" page="skills">
        <SkillsSkeleton />
      </Layout>
    )
  }

  const skills: Record<string, unknown> = (char.skills as Record<string, unknown>) ?? {}
  const pb = profBonus(char.total_level || 1)
  const abilityModifier = (abilityName: string) => {
    const score = char.ability_scores.find((s) => s.name === abilityName)
    return score?.modifier ?? 0
  }

  const toggle = (key: string) => {
    const current = getLevel(skills[key])
    const next = nextLevel(current)
    mutation.mutate({ [key]: next })
  }

  const perceptionMod = abilityModifier('wisdom')
  const perceptionLevel = getLevel(skills['perception'])
  const perceptionHb = char.skills_homebrew_modifiers?.['perception'] ?? 0
  const perceptionBonus = perceptionMod + (perceptionLevel === 'expert' ? 2 * pb : perceptionLevel ? pb : 0) + perceptionHb
  const passivePerception = 10 + perceptionBonus

  return (
    <Layout title={t('character.skills.title')} backTo={`/char/${charId}`} group="skills" page="skills">
      {/* Sticky stats strip — prof bonus + passive perception stay visible on long scroll. */}
      <div className="sticky top-0 z-10 -mx-4 px-4 pt-2 pb-2 bg-dnd-bg/95 backdrop-blur-sm">
        <Surface variant="elevated" className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim">
              {t('character.skills.prof_bonus')}
            </p>
            <StatPill tone="gold" size="sm" value={`+${pb}`} />
          </div>
          <div className="flex items-center gap-2">
            <Eye size={14} className="text-dnd-arcane-bright" />
            <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim">
              {t('character.skills.passive_perception')}
            </p>
            <StatPill tone="arcane" size="sm" value={passivePerception} />
          </div>
        </Surface>
      </div>

      <ScrollArea>
        <div className="space-y-4">
          {ABILITY_GROUPS.map((ability) => {
            const groupSkills = SKILLS.filter((s) => s.ability === ability)
            if (groupSkills.length === 0) return null

            return (
              <div key={ability}>
                <SectionDivider>
                  {t(`character.stats.${ability}`)}
                </SectionDivider>

                <div className="space-y-1.5">
                  {groupSkills.map((skill, idx) => {
                    const level = getLevel(skills[skill.key])
                    const abilMod = abilityModifier(skill.ability)
                    const bonus = abilMod + (level === 'expert' ? 2 * pb : level ? pb : 0) + (char.skills_homebrew_modifiers?.[skill.key] ?? 0)

                    const isRollingThis = rollMutation.isPending && rollMutation.variables === skill.key
                    return (
                      <Fragment key={skill.key}>
                        <SkillRow
                          skillKey={skill.key}
                          label={t(`character.skills.${skill.key}`)}
                          level={level}
                          bonus={bonus}
                          idx={idx}
                          rollPending={isRollingThis}
                          onTap={() => toggle(skill.key)}
                          onLongPress={() => {
                            haptic.medium()
                            setPicker(skill.key)
                          }}
                          onRoll={() => rollMutation.mutate(skill.key)}
                          rollAriaLabel={t('character.skills.roll')}
                        />
                        <HomebrewBreakdownRow
                          value={char.skills_homebrew_modifiers?.[skill.key] ?? 0}
                          label={t('character.skills.homebrew_label')}
                        />
                      </Fragment>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      </ScrollArea>

      {rollState && (
        <RollResultModal
          result={rollState.result}
          title={t(`character.skills.${rollState.skillName}`)}
          inspirationAvailable={Boolean(char.heroic_inspiration)}
          isRerolling={rerollMutation.isPending}
          wasRerolled={rollState.wasRerolled}
          onInspirationReroll={() => rerollMutation.mutate(rollState.skillName)}
          onClose={() => setRollState(null)}
        />
      )}

      <Sheet
        open={picker !== null}
        onClose={() => setPicker(null)}
        title={t('character.skills.picker_title')}
      >
        <div className="p-4 space-y-2">
          {picker !== null && (() => {
            // Compute bonus breakdown for the currently-targeted skill so the user
            // understands what each proficiency level will produce.
            const skill = SKILLS.find((s) => s.key === picker)
            if (!skill) return null
            const abilMod = abilityModifier(skill.ability)
            const lvl = getLevel(skills[picker])
            const profMul = lvl === 'expert' ? 2 : lvl ? 1 : 0
            const profPart = profMul * pb
            const pickerHb = char.skills_homebrew_modifiers?.[picker] ?? 0
            const total = abilMod + profPart + pickerHb
            const abilLabel = t(`character.ability.${skill.ability}_short`, { defaultValue: skill.ability })
            return (
              <p className="text-[11px] font-body text-dnd-text-faint mb-3">
                {t('character.skills.breakdown', {
                  total: `${total >= 0 ? '+' : ''}${total}`,
                  abilMod: `${abilMod >= 0 ? '+' : ''}${abilMod}`,
                  ability: abilLabel,
                  prof: `${profMul === 0 ? '+0' : profMul === 1 ? `+${pb}` : `+${pb * 2}`}`,
                  defaultValue: 'Bonus attuale: {{total}} = {{abilMod}} {{ability}} {{prof}} comp',
                })}
              </p>
            )
          })()}
          {([
            { value: false as ProfLevel, label: t('common.none') },
            { value: true as ProfLevel, label: t('character.skills.proficient') },
            { value: 'expert' as ProfLevel, label: t('character.skills.expert') },
          ]).map(({ value, label }) => {
            const isCurrent = picker !== null && getLevel(skills[picker]) === value
            return (
              <button
                key={String(value)}
                type="button"
                onClick={() => {
                  if (picker) mutation.mutate({ [picker]: value })
                  setPicker(null)
                }}
                className={`w-full min-h-[44px] px-4 py-2.5 rounded-xl border text-sm font-body text-left transition-colors flex items-center justify-between ${
                  isCurrent
                    ? 'bg-dnd-gold/15 border-dnd-gold text-dnd-gold-bright'
                    : 'bg-dnd-surface border-dnd-border text-dnd-text hover:bg-dnd-surface-raised'
                }`}
              >
                <span>{label}</span>
                {isCurrent && <Check size={14} className="text-dnd-gold-bright" />}
              </button>
            )
          })}
        </div>
      </Sheet>
    </Layout>
  )
}

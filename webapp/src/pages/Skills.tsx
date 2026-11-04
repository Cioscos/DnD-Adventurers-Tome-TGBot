import { askRollOptions, refreshAfterOptions } from '@/lib/rollOptions'
import { useState, Fragment } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Check } from 'lucide-react'
import { GiPerspectiveDiceSixFacesRandom as Dices } from 'react-icons/gi'
import { api, ApiError } from '@/api/client'
import Layout from '@/components/Layout'
import ProficiencyMark from '@/components/ui/ProficiencyMark'
import Sheet from '@/components/ui/Sheet'
import Pressable from '@/components/ui/Pressable'
import ScrollArea from '@/components/ScrollArea'
import RollResultModal, { type RollResult } from '@/components/RollResultModal'
import { haptic } from '@/auth/telegram'
import { useToast } from '@/hooks/useToast'
import { useLongPress } from '@/hooks/useLongPress'
import { useDiceAnimation } from '@/dice/useDiceAnimation'
import { useDiceSettings } from '@/store/diceSettings'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import type { CharacterFull } from '@/types'
import { useD20Roll, d20Arg, type RollMode } from '@/hooks/useD20Roll'
import RollButton from '@/components/ui/RollButton'
import RollNoteEditor from '@/components/character/RollNoteEditor'
import { rollNoteOf } from '@/lib/settings'
import { profBonus } from '@/lib/dnd'
import HomebrewBreakdownRow from '@/components/homebrew/HomebrewBreakdownRow'
import SkillsSkeleton from '@/components/skeletons/SkillsSkeleton'
import { LEDGER_LABEL, LEDGER_TITLE } from '@/styles/ledger'

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
  half?: boolean
  idx: number
  rollPending: boolean
  onTap: () => void
  onLongPress: () => void
  onRoll: (mode: RollMode) => void
  rollAriaLabel: string
  char: CharacterFull
}

function SkillRow({
  skillKey,
  label,
  level,
  bonus,
  half = false,
  idx,
  rollPending,
  onTap,
  onLongPress,
  onRoll,
  rollAriaLabel,
  char,
}: SkillRowProps) {
  const [pressProgress, setPressProgress] = useState(0)
  const longPress = useLongPress({
    thresholdMs: 500,
    onClick: onTap,
    onLongPress,
    onProgress: setPressProgress,
  })
  const hasMark = level !== false

  // Circumference of an r=20 circle (the ring radius below).
  const RING_CIRC = 2 * Math.PI * 20
  const ringActive = pressProgress > 0 && pressProgress < 1

  return (
    <m.div
      key={skillKey}
      initial={{ opacity: 0, x: -4 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: idx * 0.02, duration: 0.18 }}
      className="flex flex-wrap items-center gap-2 max-xs:gap-1 py-1"
    >
      <div
        {...longPress}
        className="flex items-center gap-2 max-xs:gap-1 flex-1 min-w-0 select-none cursor-pointer"
      >
        <div className="relative w-11 max-xs:w-7 h-11 rounded-full flex items-center justify-center shrink-0">
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
          <ProficiencyMark level={level} half={half} />
        </div>
        <span
          className="flex-1 min-w-0 text-left text-sm font-body font-medium truncate max-xs:whitespace-normal max-xs:line-clamp-2 max-xs:leading-tight"
          title={label}
        >
          {label}
        </span>
        <span className={`text-sm font-mono font-bold w-10 max-xs:w-8 text-right shrink-0 tabular-nums
          ${hasMark
            ? 'text-dnd-gold-bright'
            : bonus >= 0 ? 'text-dnd-text' : 'text-dnd-crimson-bright'}`}>
          {bonus >= 0 ? '+' : ''}{bonus}
        </span>
      </div>
      <RollNoteEditor char={char} noteKey={`skill.${skillKey}`} label={label} />
      <RollButton
        onRoll={onRoll}
        pending={rollPending}
        className="relative shrink-0 w-11 h-11 flex items-center justify-center text-dnd-gold active:scale-90 transition-transform"
        ariaLabel={rollAriaLabel}
      >
        <Dices size={18} />
      </RollButton>
      {rollNoteOf(char, `skill.${skillKey}`) && (
        <p className="basis-full pl-1 pb-1 text-xs text-dnd-text-muted font-body italic">{rollNoteOf(char, `skill.${skillKey}`)}</p>
      )}
    </m.div>
  )
}

export default function Skills() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const dice = useDiceAnimation()
  const rollD20 = useD20Roll()
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
  })

  const rollMutation = useMutation({
    mutationFn: async ({ skillName, mode }: { skillName: string; mode: RollMode }) => {
      const choice = await askRollOptions(charId, { roll: 'skill', skill: skillName })
      const result = await api.characters.rollSkill(charId, skillName, d20Arg(mode, await rollD20(mode), choice))
      return { result, skillName }
    },
    onSuccess: ({ result, skillName }) => {
      // The backend returns the raw skill key (e.g. "athletics") as the roll
      // description; it's redundant with the localized modal title and would
      // surface an untranslated EN key, so drop it.
      setRollState({ result: { ...result, description: undefined }, skillName, wasRerolled: false })
      refreshAfterOptions(qc, charId, result.option_result)
      haptic.success()
    },
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

  // Totali dal server (stessa funzione del tiro); il calcolo locale resta solo come ripiego.
  const localBonus = (key: string, ability: string) => {
    const level = getLevel(skills[key])
    return abilityModifier(ability) + (level === 'expert' ? 2 * pb : level ? pb : 0) + (char.skills_homebrew_modifiers?.[key] ?? 0)
  }
  const passiveOf = (key: string, ability: string) => char.passives?.[key] ?? 10 + localBonus(key, ability)
  const passiveRow = [
    { key: 'perception', ability: 'wisdom' },
    { key: 'insight', ability: 'wisdom' },
    { key: 'investigation', ability: 'intelligence' },
  ]

  return (
    <Layout title={t('character.skills.title')} backTo={`/char/${charId}`} group="skills" page="skills">
      {/* Sticky stats strip — prof bonus + passive perception stay visible on long scroll.
          -top-4 compensa il p-4 del contenitore di scroll del Layout (stesso pattern di
          Inventory/Spells): con top-0 la barra si fermava 16px sotto il bordo e il
          contenuto scorreva visibile sopra il pannello blurrato. */}
      <div className="sticky top-[calc(var(--crumb-offset,0px)-1rem)] z-10 -mx-4 px-4 pt-2 pb-2 bg-dnd-bg border-b border-dnd-border">
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5">
          {[
            { key: 'prof_bonus', value: `+${pb}` },
            ...passiveRow.map(({ key, ability }) => ({ key: `passive_${key}`, value: String(passiveOf(key, ability)) })),
          ].map(({ key, value }) => (
            <div key={key} className="flex min-w-0 items-center justify-between gap-2 px-1">
              <dt className={LEDGER_LABEL}>{t(`character.skills.${key}`)}</dt>
              <dd className="font-mono text-base font-bold tabular-nums text-dnd-text">{value}</dd>
            </div>
          ))}
        </dl>
      </div>

      <ScrollArea>
        <div className="space-y-5">
          {ABILITY_GROUPS.map((ability) => {
            const groupSkills = SKILLS.filter((s) => s.ability === ability)
            if (groupSkills.length === 0) return null

            return (
              <div key={ability}>
                <h2 className={`pb-1 pl-1 ${LEDGER_TITLE}`}>
                  {t(`character.stats.${ability}`)}
                </h2>

                <div className="border-y border-dnd-border divide-y divide-dnd-border/60">
                  {groupSkills.map((skill, idx) => {
                    const level = getLevel(skills[skill.key])
                    const abilMod = abilityModifier(skill.ability)
                    const bonus = char.skill_bonuses?.[skill.key] ?? abilMod + (level === 'expert' ? 2 * pb : level ? pb : 0) + (char.skills_homebrew_modifiers?.[skill.key] ?? 0)

                    const isRollingThis = rollMutation.isPending && rollMutation.variables?.skillName === skill.key
                    return (
                      <Fragment key={skill.key}>
                        <SkillRow
                          skillKey={skill.key}
                          label={t(`character.skills.${skill.key}`)}
                          level={level}
                          bonus={bonus}
                          half={Boolean(char.jack_of_all_trades) && !level}
                          idx={idx}
                          rollPending={isRollingThis}
                          onTap={() => toggle(skill.key)}
                          onLongPress={() => {
                            haptic.medium()
                            setPicker(skill.key)
                          }}
                          onRoll={(mode) => rollMutation.mutate({ skillName: skill.key, mode })}
                          rollAriaLabel={t('character.skills.roll')}
                          char={char}
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
          note={rollNoteOf(char, `skill.${rollState.skillName}`)}
          inspirationAvailable={Boolean(char.heroic_inspiration)}
          isRerolling={rerollMutation.isPending}
          wasRerolled={rollState.wasRerolled}
          onInspirationReroll={() => rerollMutation.mutate(rollState.skillName)}
          afterRoll={{ charId, query: { roll: 'skill', skill: rollState.skillName } }}
          onClose={() => setRollState(null)}
        />
      )}

      <Sheet
        open={picker !== null}
        onClose={() => setPicker(null)}
        title={t('character.skills.picker_title')}
      >
        <div className="p-5 space-y-2">
          {picker !== null && (() => {
            // Compute bonus breakdown for the currently-targeted skill so the user
            // understands what each proficiency level will produce.
            const skill = SKILLS.find((s) => s.key === picker)
            if (!skill) return null
            const abilMod = abilityModifier(skill.ability)
            const lvl = getLevel(skills[picker])
            const profMul = lvl === 'expert' ? 2 : lvl ? 1 : 0
            // Jack of All Trades: half proficiency (rounded down) on unproficient skills, as the server does.
            const profPart = lvl ? profMul * pb : (char.jack_of_all_trades ? Math.floor(pb / 2) : 0)
            const pickerHb = char.skills_homebrew_modifiers?.[picker] ?? 0
            const total = char.skill_bonuses?.[picker] ?? abilMod + profPart + pickerHb
            const abilLabel = t(`character.ability.${skill.ability}_short`, { defaultValue: skill.ability })
            return (
              <p className="text-xs font-body text-dnd-text-faint mb-3">
                {t('character.skills.breakdown', {
                  total: `${total >= 0 ? '+' : ''}${total}`,
                  abilMod: `${abilMod >= 0 ? '+' : ''}${abilMod}`,
                  ability: abilLabel,
                  prof: `+${profPart}`,
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
            // `mutation` is also shared with the long-press toggle() cycle, but both
            // call sites send the same single-key {[skillKey]: level} shape, so this
            // stays a correct (if practically invisible, since the Sheet closes
            // synchronously on click) P4 scoping.
            const isPendingThis = mutation.isPending && picker !== null && mutation.variables?.[picker] === value
            return (
              <Pressable
                key={String(value)}
                onClick={() => {
                  if (picker) mutation.mutate({ [picker]: value })
                  setPicker(null)
                }}
                pending={isPendingThis}
                className={`w-full min-h-[44px] px-4 py-2.5 rounded-xl border text-sm font-body text-left transition-colors flex items-center justify-between ${
                  isCurrent
                    ? 'bg-dnd-gold/15 border-dnd-gold text-dnd-gold-bright'
                    : 'bg-dnd-surface border-dnd-border text-dnd-text hover:bg-dnd-surface-raised'
                }`}
              >
                <span>{label}</span>
                {isCurrent && <Check size={14} className="text-dnd-gold-bright" />}
              </Pressable>
            )
          })}
        </div>
      </Sheet>
    </Layout>
  )
}

import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Check, Eye } from 'lucide-react'
import {
  GiPerspectiveDiceSixFacesRandom as Dices, GiPolarStar as Star,
} from 'react-icons/gi'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import SectionDivider from '@/components/ui/SectionDivider'
import StatPill from '@/components/ui/StatPill'
import ScrollArea from '@/components/ScrollArea'
import RollResultModal, { type RollResult } from '@/components/RollResultModal'
import { haptic } from '@/auth/telegram'
import { useDiceAnimation } from '@/dice/useDiceAnimation'

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

function profBonus(level: number) {
  return Math.floor((level - 1) / 4) + 2
}

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

export default function Skills() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const dice = useDiceAnimation()
  const [rollResult, setRollResult] = useState<{ result: RollResult; title: string } | null>(null)

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
    mutationFn: (skillName: string) => api.characters.rollSkill(charId, skillName),
    onSuccess: async (result, skillName) => {
      await dice.play({ groups: [{ kind: 'd20', results: [result.die] }] })
      setRollResult({
        result,
        title: t(`character.skills.${skillName}`),
      })
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  if (!char) return null

  const skills: Record<string, unknown> = (char.skills as Record<string, unknown>) ?? {}
  const pb = profBonus(char.total_level || 1)
  const abilityModifier = (abilityName: string) => {
    const score = char.ability_scores.find((s) => s.name === abilityName)
    return score?.modifier ?? 0
  }

  const toggle = (key: string) => {
    const current = getLevel(skills[key])
    const next = nextLevel(current)
    mutation.mutate({ ...skills, [key]: next })
  }

  const perceptionMod = abilityModifier('wisdom')
  const perceptionLevel = getLevel(skills['perception'])
  const perceptionBonus = perceptionMod + (perceptionLevel === 'expert' ? 2 * pb : perceptionLevel ? pb : 0)
  const passivePerception = 10 + perceptionBonus

  return (
    <Layout title={t('character.skills.title')} backTo={`/char/${charId}`} group="skills" page="skills">
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
                    const bonus = abilMod + (level === 'expert' ? 2 * pb : level ? pb : 0)
                    const isExpert = level === 'expert'
                    const isProficient = level === true
                    const hasMark = isExpert || isProficient

                    return (
                      <m.div
                        key={skill.key}
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
                        {/* Proficiency toggle */}
                        <m.button
                          onClick={() => toggle(skill.key)}
                          className="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
                          whileTap={{ scale: 0.85 }}
                          aria-label="Proficiency"
                        >
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
                        </m.button>

                        {/* Name */}
                        <button
                          onClick={() => toggle(skill.key)}
                          className="flex-1 text-left text-sm font-body font-medium"
                        >
                          {t(`character.skills.${skill.key}`)}
                        </button>

                        {/* Bonus */}
                        <span className={`text-sm font-mono font-bold w-10 text-right shrink-0 tabular-nums
                          ${hasMark
                            ? 'text-dnd-gold-bright'
                            : bonus >= 0 ? 'text-dnd-text' : 'text-[var(--dnd-crimson-bright)]'}`}>
                          {bonus >= 0 ? '+' : ''}{bonus}
                        </span>

                        {/* Roll */}
                        <m.button
                          onClick={() => rollMutation.mutate(skill.key)}
                          disabled={rollMutation.isPending}
                          className="shrink-0 w-9 h-9 rounded-xl bg-dnd-chip-bg border border-dnd-gold-dim/40 flex items-center justify-center text-dnd-gold disabled:opacity-30"
                          whileTap={{ scale: 0.88 }}
                          aria-label={t('character.skills.roll')}
                        >
                          <Dices size={15} />
                        </m.button>
                      </m.div>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      </ScrollArea>

      {rollResult && (
        <RollResultModal
          result={rollResult.result}
          title={rollResult.title}
          onClose={() => setRollResult(null)}
        />
      )}
    </Layout>
  )
}

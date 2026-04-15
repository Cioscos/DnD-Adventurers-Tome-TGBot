import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import ScrollArea from '@/components/ScrollArea'
import RollResultModal, { type RollResult } from '@/components/RollResultModal'
import { haptic } from '@/auth/telegram'

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

const ABILITY_GROUPS: { ability: string; emoji: string }[] = [
  { ability: 'strength',     emoji: '💪' },
  { ability: 'dexterity',    emoji: '🤸' },
  { ability: 'intelligence', emoji: '🧠' },
  { ability: 'wisdom',       emoji: '🦉' },
  { ability: 'charisma',     emoji: '✨' },
]

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
    onSuccess: (result, skillName) => {
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

  // passive perception
  const perceptionMod = abilityModifier('wisdom')
  const perceptionLevel = getLevel(skills['perception'])
  const perceptionBonus = perceptionMod + (perceptionLevel === 'expert' ? 2 * pb : perceptionLevel ? pb : 0)
  const passivePerception = 10 + perceptionBonus

  return (
    <Layout title={t('character.skills.title')} backTo={`/char/${charId}`} group="skills" page="skills">
      <Card>
        <div className="flex justify-between items-center">
          <p className="text-sm text-dnd-text-secondary">
            {t('character.skills.prof_bonus')}: <span className="font-bold text-white">+{pb}</span>
          </p>
          <p className="text-sm text-dnd-text-secondary">
            {t('character.skills.passive_perception')}: <span className="font-bold text-white">{passivePerception}</span>
          </p>
        </div>
      </Card>

      <ScrollArea>
        <div className="space-y-4">
          {ABILITY_GROUPS.map((group) => {
            const groupSkills = SKILLS.filter((s) => s.ability === group.ability)
            if (groupSkills.length === 0) return null

            return (
              <div key={group.ability}>
                {/* Section header */}
                <div className="flex items-center gap-2 px-1 mb-1.5">
                  <span className="text-base leading-none">{group.emoji}</span>
                  <span className="text-xs font-semibold uppercase tracking-wider text-dnd-text-secondary">
                    {t(`character.stats.${group.ability}`)}
                  </span>
                  <div className="flex-1 h-px bg-dnd-surface" />
                </div>

                <div className="space-y-1">
                  {groupSkills.map((skill) => {
                    const level = getLevel(skills[skill.key])
                    const abilMod = abilityModifier(skill.ability)
                    const bonus = abilMod + (level === 'expert' ? 2 * pb : level ? pb : 0)
                    const isExpert = level === 'expert'
                    const isProficient = level === true

                    return (
                      <div
                        key={skill.key}
                        className="flex items-center gap-2 px-3 py-2.5 rounded-xl
                                   bg-dnd-surface"
                      >
                        {/* Proficiency toggle */}
                        <button
                          onClick={() => toggle(skill.key)}
                          className={`w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0
                            ${isExpert
                              ? 'bg-yellow-500 border-yellow-500'
                              : isProficient
                                ? 'bg-dnd-gold border-dnd-gold'
                                : 'border-white/30'}`}
                        >
                          {isExpert && <span className="text-[10px] text-white font-bold leading-none">★</span>}
                          {isProficient && <span className="text-[10px] text-white font-bold leading-none">✓</span>}
                        </button>

                        {/* Name */}
                        <button
                          onClick={() => toggle(skill.key)}
                          className="flex-1 text-left text-sm font-medium active:opacity-70"
                        >
                          {t(`character.skills.${skill.key}`)}
                        </button>

                        {/* Bonus */}
                        <span className={`text-sm font-bold w-8 text-right shrink-0 tabular-nums
                          ${bonus >= 0 ? 'text-[#2ecc71]' : 'text-[var(--dnd-danger)]'}`}>
                          {bonus >= 0 ? '+' : ''}{bonus}
                        </span>

                        {/* Roll button */}
                        <button
                          onClick={() => rollMutation.mutate(skill.key)}
                          disabled={rollMutation.isPending}
                          className="shrink-0 w-9 h-9 rounded-xl
                                     bg-dnd-gold/15
                                     flex items-center justify-center text-base
                                     active:bg-dnd-gold/30
                                     active:opacity-60 disabled:opacity-30
                                     transition-colors"
                          title={t('character.skills.roll')}
                        >
                          🎲
                        </button>
                      </div>
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

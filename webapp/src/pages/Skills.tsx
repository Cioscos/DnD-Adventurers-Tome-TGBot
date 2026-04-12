import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
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

function profBonus(level: number) {
  return Math.floor((level - 1) / 4) + 2
}

export default function Skills() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const mutation = useMutation({
    mutationFn: (skills: Record<string, boolean>) =>
      api.characters.updateSkills(charId, skills),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.light()
    },
    onError: () => haptic.error(),
  })

  if (!char) return null

  const skills: Record<string, boolean> = (char.skills as Record<string, boolean>) ?? {}
  const pb = profBonus(char.total_level || 1)
  const abilityModifier = (abilityName: string) => {
    const score = char.ability_scores.find((s) => s.name === abilityName)
    return score?.modifier ?? 0
  }

  const toggle = (key: string) => {
    const current = skills[key] ?? false
    mutation.mutate({ ...skills, [key]: !current })
  }

  return (
    <Layout title={t('character.skills.title')} backTo={`/char/${charId}`}>
      <Card>
        <p className="text-sm text-[var(--tg-theme-hint-color)]">
          {t('character.skills.prof_bonus')}: <span className="font-bold text-white">+{pb}</span>
        </p>
      </Card>

      <div className="space-y-1">
        {SKILLS.map((skill) => {
          const isProficient = skills[skill.key] ?? false
          const abilMod = abilityModifier(skill.ability)
          const total = abilMod + (isProficient ? pb : 0)

          return (
            <button
              key={skill.key}
              onClick={() => toggle(skill.key)}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-xl
                         bg-[var(--tg-theme-secondary-bg-color)] active:opacity-70"
            >
              <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0
                ${isProficient ? 'bg-[var(--tg-theme-button-color)] border-[var(--tg-theme-button-color)]' : 'border-white/30'}`}
              >
                {isProficient && <span className="text-xs text-white font-bold">✓</span>}
              </div>
              <span className="flex-1 text-left text-sm font-medium">
                {t(`character.skills.${skill.key}`)}
              </span>
              <span className="text-xs text-[var(--tg-theme-hint-color)] uppercase shrink-0">
                {skill.ability.slice(0, 3)}
              </span>
              <span className={`text-sm font-bold w-8 text-right shrink-0 ${total >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {total >= 0 ? '+' : ''}{total}
              </span>
            </button>
          )
        })}
      </div>
    </Layout>
  )
}

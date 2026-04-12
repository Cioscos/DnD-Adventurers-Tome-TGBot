import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import { haptic } from '@/auth/telegram'

const ABILITIES = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']

function profBonus(level: number) {
  return Math.floor((level - 1) / 4) + 2
}

export default function SavingThrows() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const mutation = useMutation({
    mutationFn: (saving_throws: Record<string, boolean>) =>
      api.characters.updateSavingThrows(charId, saving_throws),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.light()
    },
    onError: () => haptic.error(),
  })

  if (!char) return null

  const saves: Record<string, boolean> = (char.saving_throws as Record<string, boolean>) ?? {}
  const pb = profBonus(char.total_level || 1)

  const toggle = (ability: string) => {
    const current = saves[ability] ?? false
    mutation.mutate({ ...saves, [ability]: !current })
  }

  return (
    <Layout title={t('character.saves.title')} backTo={`/char/${charId}`}>
      <Card>
        <p className="text-sm text-[var(--tg-theme-hint-color)]">
          {t('character.skills.prof_bonus')}: <span className="font-bold text-white">+{pb}</span>
        </p>
      </Card>

      <div className="space-y-1">
        {ABILITIES.map((ability) => {
          const isProficient = saves[ability] ?? false
          const score = char.ability_scores.find((s) => s.name === ability)
          const abilMod = score?.modifier ?? 0
          const total = abilMod + (isProficient ? pb : 0)

          return (
            <button
              key={ability}
              onClick={() => toggle(ability)}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-xl
                         bg-[var(--tg-theme-secondary-bg-color)] active:opacity-70"
            >
              <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0
                ${isProficient ? 'bg-[var(--tg-theme-button-color)] border-[var(--tg-theme-button-color)]' : 'border-white/30'}`}
              >
                {isProficient && <span className="text-xs text-white font-bold">✓</span>}
              </div>
              <span className="flex-1 text-left font-medium">
                {t(`character.stats.${ability}`)}
              </span>
              <span className={`text-sm font-bold w-8 text-right ${total >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {total >= 0 ? '+' : ''}{total}
              </span>
            </button>
          )
        })}
      </div>
    </Layout>
  )
}

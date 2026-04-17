import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Check, ShieldAlert } from 'lucide-react'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import StatPill from '@/components/ui/StatPill'
import Reveal from '@/components/ui/Reveal'
import DiceIcon from '@/components/ui/DiceIcon'
import RollResultModal, { type RollResult } from '@/components/RollResultModal'
import { haptic } from '@/auth/telegram'
import { stagger } from '@/styles/motion'

const ABILITIES = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma'] as const

const ABILITY_TONE: Record<string, 'crimson' | 'emerald' | 'amber' | 'cobalt' | 'arcane' | 'gold'> = {
  strength: 'crimson',
  dexterity: 'emerald',
  constitution: 'amber',
  intelligence: 'cobalt',
  wisdom: 'arcane',
  charisma: 'gold',
}

function profBonus(level: number) {
  return Math.floor((level - 1) / 4) + 2
}

export default function SavingThrows() {
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
    mutationFn: (saving_throws: Record<string, boolean>) =>
      api.characters.updateSavingThrows(charId, saving_throws),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.light()
    },
    onError: () => haptic.error(),
  })

  const rollMutation = useMutation({
    mutationFn: (ability: string) => api.characters.rollSavingThrow(charId, ability),
    onSuccess: (result, ability) => {
      setRollResult({
        result,
        title: `${t('character.saves.title')} — ${t(`character.stats.${ability}`)}`,
      })
      haptic.success()
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
    <Layout title={t('character.saves.title')} backTo={`/char/${charId}`} group="combat" page="saves">
      <Surface variant="elevated" className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-dnd-gold">
          <ShieldAlert size={16} />
          <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim">
            {t('character.skills.prof_bonus')}
          </p>
        </div>
        <StatPill tone="gold" value={`+${pb}`} />
      </Surface>

      <Reveal.Stagger stagger={stagger.list} className="grid grid-cols-2 gap-2">
        {ABILITIES.map((ability) => {
          const isProficient = saves[ability] ?? false
          const score = char.ability_scores.find((s) => s.name === ability)
          const abilMod = score?.modifier ?? 0
          const total = abilMod + (isProficient ? pb : 0)
          const tone = ABILITY_TONE[ability]

          return (
            <Reveal.Item key={ability}>
              <Surface
                variant={isProficient ? 'elevated' : 'flat'}
                interactive
                onClick={() => rollMutation.mutate(ability)}
                className={`relative !p-3 text-center
                  ${isProficient ? 'border-dnd-gold/50 shadow-halo-gold' : ''}`}
              >
                {/* Top row: proficiency toggle (left) + dice hint (right) */}
                <div className="flex items-center justify-between -mx-1 -mt-1 mb-2">
                  <m.button
                    onClick={(e) => {
                      e.stopPropagation()
                      toggle(ability)
                    }}
                    className="w-10 h-10 flex items-center justify-center rounded-full"
                    whileTap={{ scale: 0.85 }}
                    aria-label="Proficiency"
                  >
                    <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center transition-colors
                      ${isProficient
                        ? 'bg-dnd-gold border-dnd-gold-bright shadow-[0_0_6px_var(--dnd-gold-glow)]'
                        : 'border-dnd-border'}`}>
                      {isProficient && <Check size={12} className="text-dnd-ink" strokeWidth={3} />}
                    </div>
                  </m.button>
                  <DiceIcon sides={20} size={28} className="text-dnd-gold/80 mr-0.5" />
                </div>

                <p className="text-[10px] font-cinzel uppercase tracking-[0.25em] text-dnd-text-muted">
                  {t(`character.stats.${ability}`)}
                </p>
                <p className={`text-4xl font-display font-black leading-none mt-1.5 mb-1 ${
                  tone === 'crimson' ? 'text-[var(--dnd-crimson-bright)]'
                  : tone === 'emerald' ? 'text-[var(--dnd-emerald-bright)]'
                  : tone === 'amber' ? 'text-[var(--dnd-amber)]'
                  : tone === 'cobalt' ? 'text-[var(--dnd-cobalt-bright)]'
                  : tone === 'arcane' ? 'text-dnd-arcane-bright'
                  : 'text-dnd-gold-bright'
                }`}>
                  {total >= 0 ? '+' : ''}{total}
                </p>
                <p className="text-[10px] text-dnd-text-faint font-mono">
                  {abilMod >= 0 ? '+' : ''}{abilMod}{isProficient ? ` +${pb}` : ''}
                </p>
              </Surface>
            </Reveal.Item>
          )
        })}
      </Reveal.Stagger>

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

import { useState, Fragment } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Check } from 'lucide-react'
import { GiShieldEchoes as ShieldAlert } from 'react-icons/gi'
import { api, ApiError } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import StatPill from '@/components/ui/StatPill'
import Reveal from '@/components/ui/Reveal'
import Pressable from '@/components/ui/Pressable'
import DiceIcon from '@/components/ui/DiceIcon'
import RollResultModal, { type RollResult } from '@/components/RollResultModal'
import { haptic } from '@/auth/telegram'
import { stagger } from '@/styles/motion'
import { useDiceAnimation } from '@/dice/useDiceAnimation'
import { useDiceSettings } from '@/store/diceSettings'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import { useToast } from '@/hooks/useToast'
import { profBonus } from '@/lib/dnd'
import HomebrewBreakdownRow from '@/components/homebrew/HomebrewBreakdownRow'
import SavingThrowsSkeleton from '@/components/skeletons/SavingThrowsSkeleton'

const ABILITIES = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma'] as const

type RollState = {
  result: RollResult
  title: string
  ability: string
  wasRerolled: boolean
}

export default function SavingThrows() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const dice = useDiceAnimation()
  const animate3d = useDiceSettings((s) => s.animate3d)
  const reducedMotion = useReducedMotion()
  const toast = useToast()
  const [rollState, setRollState] = useState<RollState | null>(null)

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
    mutationFn: async (ability: string) => {
      const useAnimation = animate3d && !reducedMotion
      let die: number | undefined
      if (useAnimation) {
        const detected = await dice.playAndCollect([{ kind: 'd20', count: 1 }])
        die = detected[0]?.value
      }
      const result = await api.characters.rollSavingThrow(charId, ability, die)
      return { result, ability }
    },
    onSuccess: ({ result, ability }) => {
      setRollState({
        // description è la chiave raw dell'ability ("intelligence"): il titolo
        // localizzato la copre già, mostrarla duplicherebbe in inglese grezzo.
        result: { ...result, description: undefined },
        ability,
        title: `${t('character.saves.title')}: ${t(`character.stats.${ability}`)}`,
        wasRerolled: false,
      })
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const rerollMutation = useMutation({
    mutationFn: async (ability: string) => {
      const useAnimation = animate3d && !reducedMotion
      let die: number | undefined
      if (useAnimation) {
        const detected = await dice.playAndCollect([{ kind: 'd20', count: 1 }])
        die = detected[0]?.value
      }
      return api.characters.rollSavingThrow(charId, ability, die, true)
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
      <Layout title={t('character.saves.title')} backTo={`/char/${charId}`} group="combat" page="saves">
        <SavingThrowsSkeleton />
      </Layout>
    )
  }

  const saves: Record<string, boolean> = (char.saving_throws as Record<string, boolean>) ?? {}
  const pb = profBonus(char.total_level || 1)

  const toggle = (ability: string) => {
    const current = saves[ability] ?? false
    mutation.mutate({ ...saves, [ability]: !current })
  }

  // `mutation` has a single call site (toggle, above) always sending a full
  // saves-shaped object with exactly one key flipped — diffing against the
  // current `saves` reliably recovers which ability is in flight (P4).
  const pendingAbility = mutation.isPending
    ? ABILITIES.find((a) => mutation.variables?.[a] !== saves[a])
    : undefined

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

      <Reveal.Stagger stagger={stagger.list} className="flex flex-col gap-1.5">
        {ABILITIES.map((ability) => {
          const isProficient = saves[ability] ?? false
          const score = char.ability_scores.find((s) => s.name === ability)
          const abilMod = score?.modifier ?? 0
          const total = abilMod + (isProficient ? pb : 0) + (char.saves_homebrew_modifiers?.[ability] ?? 0)

          return (
            <Fragment key={ability}>
              <Reveal.Item>
                <Surface
                  variant={isProficient ? 'elevated' : 'flat'}
                  interactive
                  onClick={() => rollMutation.mutate(ability)}
                  className={`relative !p-2 cursor-pointer
                    ${isProficient ? 'border-dnd-gold/50' : ''}`}
                >
                  <div className="flex items-center gap-3 min-h-[44px]">
                    <Pressable
                      onClick={(e) => {
                        e.stopPropagation()
                        toggle(ability)
                      }}
                      pending={pendingAbility === ability}
                      spinnerSize={12}
                      className="w-11 h-11 flex items-center justify-center rounded-full shrink-0"
                      whileTap={{ scale: 0.85 }}
                      aria-label="Proficiency"
                    >
                      <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center transition-colors
                        ${isProficient
                          ? 'bg-dnd-gold border-dnd-gold-bright shadow-[0_0_6px_var(--dnd-gold-glow)]'
                          : 'border-dnd-border'}`}>
                        {isProficient && <Check size={12} className="text-dnd-ink" strokeWidth={3} />}
                      </div>
                    </Pressable>

                    <div className="flex-1 min-w-0">
                      <p
                        className="text-xs font-cinzel uppercase tracking-[0.18em] text-dnd-text leading-tight"
                        title={t(`character.stats.${ability}`)}
                      >
                        {t(`character.stats.${ability}`)}
                      </p>
                      <p className="text-[10px] text-dnd-text-faint font-mono leading-tight mt-0.5">
                        {abilMod >= 0 ? '+' : ''}{abilMod}
                        {isProficient ? ` +${pb} ${t('character.saves.ts_short')}` : ''}
                      </p>
                    </div>

                    {/* Negativo in crimson come in Skills: stesso vocabolario. */}
                    <p className={`text-3xl font-mono font-bold leading-none tabular-nums ${total >= 0 ? 'text-dnd-text' : 'text-dnd-crimson-bright'}`}>
                      {total >= 0 ? '+' : ''}{total}
                    </p>
                    <DiceIcon sides={20} size={24} className="text-dnd-gold/80 shrink-0" />
                  </div>
                </Surface>
              </Reveal.Item>
              <HomebrewBreakdownRow
                value={char.saves_homebrew_modifiers?.[ability] ?? 0}
                label={t('character.saves.homebrew_label')}
              />
            </Fragment>
          )
        })}
      </Reveal.Stagger>

      {rollState && (
        <RollResultModal
          result={rollState.result}
          title={rollState.title}
          inspirationAvailable={Boolean(char.heroic_inspiration)}
          isRerolling={rerollMutation.isPending}
          wasRerolled={rollState.wasRerolled}
          onInspirationReroll={() => rerollMutation.mutate(rollState.ability)}
          onClose={() => setRollState(null)}
        />
      )}
    </Layout>
  )
}

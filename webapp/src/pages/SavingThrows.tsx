import { canRerollInspiration, askRollOptions, refreshAfterOptions } from '@/lib/rollOptions'
import { useState, Fragment } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api, ApiError } from '@/api/client'
import Layout from '@/components/Layout'
import ProficiencyMark from '@/components/ui/ProficiencyMark'
import Reveal from '@/components/ui/Reveal'
import Pressable from '@/components/ui/Pressable'
import DiceIcon from '@/components/ui/DiceIcon'
import RollResultModal, { type RollResult } from '@/components/RollResultModal'
import { haptic } from '@/auth/telegram'
import { stagger } from '@/styles/motion'
import { LEDGER_LABEL } from '@/styles/ledger'
import { useDiceAnimation } from '@/dice/useDiceAnimation'
import { useDiceSettings } from '@/store/diceSettings'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import { useToast } from '@/hooks/useToast'
import { useD20Roll, d20Arg, type RollMode } from '@/hooks/useD20Roll'
import RollModeToggle from '@/components/ui/RollModeToggle'
import Sheet from '@/components/ui/Sheet'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import RollNoteEditor from '@/components/character/RollNoteEditor'
import { rollNoteOf } from '@/lib/settings'
import { profBonus } from '@/lib/dnd'
import HomebrewBreakdownRow from '@/components/homebrew/HomebrewBreakdownRow'
import SavingThrowsSkeleton from '@/components/skeletons/SavingThrowsSkeleton'

const ABILITIES = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma'] as const

type RollState = {
  result: RollResult
  title: string
  ability: string
  wasRerolled: boolean
  /** CD detta dal master: l'esito dice riuscito o fallito (L8). */
  dc?: number
}

export default function SavingThrows() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const dice = useDiceAnimation()
  const rollD20 = useD20Roll()
  const animate3d = useDiceSettings((s) => s.animate3d)
  const reducedMotion = useReducedMotion()
  const toast = useToast()
  const [rollState, setRollState] = useState<RollState | null>(null)
  // L8: tocco sulla riga, prima del tiro CD (facoltativa) e Normale / Vantaggio / Svantaggio, poi le opzioni e il d20.
  const [prep, setPrep] = useState<{ ability: string; mode: RollMode; dc: string } | null>(null)

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
  })

  const rollMutation = useMutation({
    mutationFn: async ({ ability, mode }: { ability: string; mode: RollMode; dc?: number }) => {
      const choice = await askRollOptions(charId, { roll: 'save', ability })
      const result = await api.characters.rollSavingThrow(charId, ability, d20Arg(mode, await rollD20(mode, choice), choice))
      return { result, ability }
    },
    onSuccess: ({ result, ability }, { dc }) => {
      refreshAfterOptions(qc, charId, result.option_result)
      setRollState({
        // description è la chiave raw dell'ability ("intelligence"): il titolo
        // localizzato la copre già, mostrarla duplicherebbe in inglese grezzo.
        result: { ...result, description: undefined },
        ability,
        title: `${t('character.saves.title')}: ${t(`character.stats.${ability}`)}`,
        wasRerolled: false,
        dc,
      })
      haptic.success()
    },
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
    mutation.mutate({ [ability]: !current })  // solo quella toccata: il server unisce, due tocchi ravvicinati restano entrambi
  }

  // `mutation` has a single call site (toggle, above) sending only the flipped key: that key is the ability in flight.
  const pendingAbility = mutation.isPending ? Object.keys(mutation.variables ?? {})[0] : undefined

  return (
    <Layout title={t('character.saves.title')} backTo={`/char/${charId}`} group="combat" page="saves">
      <div className="flex min-h-[48px] items-center justify-between gap-3 px-1">
        <p className={LEDGER_LABEL}>{t('character.skills.prof_bonus')}</p>
        <span data-testid="pb" className="font-mono text-lg font-bold tabular-nums text-dnd-text">+{pb}</span>
      </div>

      <Reveal.Stagger stagger={stagger.list} className="border-y border-dnd-border divide-y divide-dnd-border/60">
        {ABILITIES.map((ability) => {
          const isProficient = saves[ability] ?? false
          const score = char.ability_scores.find((s) => s.name === ability)
          const abilMod = score?.modifier ?? 0
          const total = abilMod + (isProficient ? pb : 0) + (char.saves_homebrew_modifiers?.[ability] ?? 0) + (char.saves_items_modifiers?.[ability] ?? 0) + (char.computed?.save_flat?.[ability] ?? 0)

          return (
            <Fragment key={ability}>
              <Reveal.Item>
                <div
                  onClick={() => setPrep({ ability, mode: 'normal', dc: '' })}
                  className="cursor-pointer py-1 hover:bg-dnd-surface/60 transition-colors"
                >
                  <div className="flex items-center gap-1.5 min-h-[44px]">
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
                      <ProficiencyMark level={isProficient} />
                    </Pressable>

                    <div className="flex-1 min-w-0">
                      <p
                        className={`truncate ${LEDGER_LABEL}`}
                        title={t(`character.stats.${ability}`)}
                      >
                        {/* Sotto 375px il nome intero non sta accanto al totale: sigla */}
                        <span className="max-xs:hidden">{t(`character.stats.${ability}`)}</span>
                        <span className="xs:hidden">{t(`character.ability.${ability}_short`)}</span>
                      </p>
                      <p className="text-xs text-dnd-text-muted font-mono tabular-nums leading-tight mt-0.5">
                        {abilMod >= 0 ? '+' : ''}{abilMod}
                        {isProficient ? ` +${pb} ${t('character.saves.ts_short')}` : ''}
                      </p>
                    </div>

                    {/* Negativo in crimson come in Skills: stesso vocabolario. */}
                    <p className={`shrink-0 text-2xl font-mono font-bold leading-none tabular-nums ${total < 0 ? 'text-dnd-crimson-bright' : isProficient ? 'text-dnd-gold-bright' : 'text-dnd-text'}`}>
                      {total >= 0 ? '+' : ''}{total}
                    </p>
                    <span onClick={(e) => e.stopPropagation()} className="shrink-0">
                      <RollNoteEditor char={char} noteKey={`save.${ability}`} label={t(`character.stats.${ability}`)} />
                    </span>
                    <Pressable
                      onClick={(e) => {
                        e.stopPropagation()
                        setPrep({ ability, mode: 'normal', dc: '' })
                      }}
                      pending={rollMutation.isPending && rollMutation.variables?.ability === ability}
                      aria-label={t('character.skills.roll')}
                      className="w-11 h-11 flex items-center justify-center shrink-0"
                    >
                      <DiceIcon sides={20} size={28} className="text-dnd-gold" />
                    </Pressable>
                  </div>
                  {rollNoteOf(char, `save.${ability}`) && (
                    <p className="text-xs text-dnd-text-muted font-body italic pl-14 pb-1">{rollNoteOf(char, `save.${ability}`)}</p>
                  )}
                </div>
              </Reveal.Item>
              <HomebrewBreakdownRow
                value={char.saves_homebrew_modifiers?.[ability] ?? 0}
                label={t('character.saves.homebrew_label')}
              />
            </Fragment>
          )
        })}
      </Reveal.Stagger>

      {prep && (
        <Sheet open onClose={() => setPrep(null)} title={`${t('character.saves.title')}: ${t(`character.stats.${prep.ability}`)}`}>
          <div className="p-5 space-y-4">
            <Input
              type="number"
              label={t('character.saves.dc_label')}
              value={prep.dc}
              onChange={(dc) => setPrep({ ...prep, dc })}
              placeholder={t('character.saves.dc_placeholder')}
              min={1}
              max={40}
              inputMode="numeric"
              commitOnBlur={false}
            />
            <RollModeToggle mode={prep.mode} onChange={(mode) => setPrep({ ...prep, mode })} />
            <Button
              size="lg"
              fullWidth
              onClick={() => {
                const dc = parseInt(prep.dc, 10)
                setPrep(null)
                rollMutation.mutate({ ability: prep.ability, mode: prep.mode, dc: dc > 0 ? dc : undefined })
              }}
            >
              {t('pendingSaves.roll')}
            </Button>
          </div>
        </Sheet>
      )}

      {rollState && (
        <RollResultModal
          result={rollState.result}
          title={rollState.title}
          note={rollNoteOf(char, `save.${rollState.ability}`)}
          inspirationAvailable={canRerollInspiration(char)}
          isRerolling={rerollMutation.isPending}
          wasRerolled={rollState.wasRerolled}
          onInspirationReroll={() => rerollMutation.mutate(rollState.ability)}
          afterRoll={{ charId, query: { roll: 'save', ability: rollState.ability } }}
          dc={rollState.dc}
          onClose={() => setRollState(null)}
        />
      )}
    </Layout>
  )
}

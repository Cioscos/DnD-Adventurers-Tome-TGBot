import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { BarChart3 } from 'lucide-react'
import { GiShieldEchoes, GiArcheryTarget } from 'react-icons/gi'
import Surface from '@/components/ui/Surface'
import SectionDivider from '@/components/ui/SectionDivider'
import Pressable from '@/components/ui/Pressable'
import HomebrewBreakdownRow from '@/components/homebrew/HomebrewBreakdownRow'
import RollResultModal, { type RollResult } from '@/components/RollResultModal'
import { haptic } from '@/auth/telegram'
import { profBonus } from '@/lib/dnd'
import { useUnitSettings, formatLength } from '@/store/unitSettings'
import { useD20Roll, type RollMode } from '@/hooks/useD20Roll'
import RollButton from '@/components/ui/RollButton'
import { api } from '@/api/client'
import type { CharacterFull } from '@/types'

// Canonical D&D 5e ability order (mirrors the local const in HeroScreen.tsx /
// SavingThrows.tsx — kept local on purpose, the repo does not centralize it).
const ABILITY_ORDER = [
  'strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma',
]

type SkillLvl = false | true | 'expert'

// Same proficiency coercion used by Skills.tsx (values can be boolean, 1, or 'expert').
function skillLevel(val: unknown): SkillLvl {
  if (val === 'expert') return 'expert'
  if (val === true || val === 1) return true
  return false
}

interface Props {
  char: CharacterFull
}

export default function HeroStatsSection({ char }: Props) {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const unitSystem = useUnitSettings((s) => s.system)

  const go = (path: string) => {
    haptic.light()
    navigate(`/char/${char.id}/${path}`)
  }

  const abilityMod = (name: string) =>
    char.ability_scores.find((s) => s.name === name)?.modifier ?? 0

  const sign = (v: number) => `${v >= 0 ? '+' : ''}${v}`

  const pb = profBonus(char.total_level ?? 1)
  const dexMod = abilityMod('dexterity')
  const initBonus = char.initiative_bonus ?? dexMod

  // Passive perception — identical formula to Skills.tsx.
  const skills = (char.skills as Record<string, unknown>) ?? {}
  const percLvl = skillLevel(skills['perception'])
  const percHb = char.skills_homebrew_modifiers?.['perception'] ?? 0
  const passivePerception =
    10 + abilityMod('wisdom') + (percLvl === 'expert' ? 2 * pb : percLvl ? pb : 0) + percHb

  const speedTotal = (char.speed ?? 30) + (char.speed_homebrew_modifier ?? 0) + (char.speed_items_modifier ?? 0)
  const speedLabel = formatLength(speedTotal, unitSystem)

  // Proficient saving throws with their total bonus (same math as SavingThrows.tsx).
  const saves = (char.saving_throws as Record<string, boolean>) ?? {}
  const profSaves = ABILITY_ORDER.filter((a) => saves[a]).map((a) => ({
    key: a,
    label: t(`character.ability.${a}_short`, { defaultValue: a.slice(0, 3).toUpperCase() }),
    bonus: abilityMod(a) + pb + (char.saves_homebrew_modifiers?.[a] ?? 0),
  }))

  // Skill proficiency counts (only keys actually set on the character).
  let profCount = 0
  let expertCount = 0
  for (const v of Object.values(skills)) {
    const lvl = skillLevel(v)
    if (lvl === 'expert') expertCount += 1
    else if (lvl === true) profCount += 1
  }
  const totalSkillProf = profCount + expertCount

  const qc = useQueryClient()
  const rollD20 = useD20Roll()
  const [initResult, setInitResult] = useState<RollResult | null>(null)

  const initiativeMutation = useMutation({
    mutationFn: async (mode: RollMode) => {
      // Il client tira (con animazione 3D se attiva), il BE persiste nello storico.
      const n = mode === 'normal' ? 1 : 2
      const faces = (await rollD20(mode)) ?? Array.from({ length: n }, () => 1 + Math.floor(Math.random() * 20))
      const value = mode === 'advantage' ? Math.max(...faces) : mode === 'disadvantage' ? Math.min(...faces) : faces[0]
      const keep = mode === 'advantage' ? 'kh1' : mode === 'disadvantage' ? 'kl1' : ''
      const notation = `${n}d20${keep}${initBonus >= 0 ? '+' : ''}${initBonus}`
      await api.dice.result(char.id, {
        rolls: faces.map((v) => ({ kind: 'd20' as const, value: v })),
        modifier: initBonus,
        notation,
        label: t('character.hero.initiative'),
        mode,
      })
      return { value, faces, mode }
    },
    onSuccess: ({ value, faces, mode }) => {
      qc.invalidateQueries({ queryKey: ['character', char.id] })
      qc.invalidateQueries({ queryKey: ['dice-history', char.id] })
      qc.invalidateQueries({ queryKey: ['history', char.id] })
      setInitResult({
        die: value,
        dice: faces,
        mode,
        bonus: initBonus,
        total: value + initBonus,
        is_critical: value === 20,
        is_fumble: value === 1,
      })
      haptic.success()
    },
  })

  const cells = [
    {
      key: 'init',
      label: t('character.hero.initiative'),
      value: sign(initBonus),
      path: 'stats',
    },
    {
      key: 'pb',
      label: t('character.skills.prof_bonus'),
      value: sign(pb),
      path: 'class',
    },
    {
      key: 'pp',
      label: t('character.skills.passive_perception'),
      value: String(passivePerception),
      path: 'skills',
    },
    {
      key: 'speed',
      label: t('character.identity.speed'),
      value: speedLabel,
      path: 'identity',
    },
  ]

  return (
    <div>
      <SectionDivider align="center" icon={<BarChart3 size={11} />}>
        {t('character.hero.stats_section')}
      </SectionDivider>

      {/* Combat-number cells — 2×2 grid, full names above, mono value below. */}
      <div className="grid grid-cols-2 gap-1.5">
        {cells.map((c) => {
          const cellClass = `flex flex-col items-center justify-center min-h-[68px] rounded-lg p-2 border
                       bg-dnd-surface-raised border-dnd-border text-dnd-text
                       hover:border-dnd-gold transition-colors`
          const body = (
            <>
              <span className="flex items-center justify-center text-center min-h-[2.2em] px-0.5
                               text-xs font-cinzel uppercase tracking-wide leading-tight opacity-80">
                {c.label}
              </span>
              <span className="text-2xl font-mono font-bold tabular-nums leading-none mt-1">
                {c.value}
              </span>
            </>
          )
          return c.key === 'init' ? (
            <RollButton
              key={c.key}
              onRoll={(mode) => { haptic.medium(); initiativeMutation.mutate(mode) }}
              pending={initiativeMutation.isPending}
              ariaLabel={`${c.label}: ${c.value}`}
              className={cellClass}
            >
              {body}
            </RollButton>
          ) : (
            <Pressable
              key={c.key}
              type="button"
              onClick={() => go(c.path)}
              aria-label={`${c.label}: ${c.value}`}
              className={cellClass}
              whileTap={{ scale: 0.95 }}
            >
              {body}
            </Pressable>
          )
        })}
      </div>

      {/* Speed folds its homebrew modifier into the total above; surface an
          attribution row (like AC/HP) so an altered speed isn't unexplained (#34). */}
      {(char.speed_homebrew_modifier ?? 0) !== 0 && (
        <div className="mt-1.5 rounded-lg border border-dnd-border bg-dnd-surface-raised">
          <HomebrewBreakdownRow
            value={char.speed_homebrew_modifier ?? 0}
            label={t('character.hero.speed_homebrew_label')}
            display={`${(char.speed_homebrew_modifier ?? 0) > 0 ? '+' : ''}${formatLength(char.speed_homebrew_modifier ?? 0, unitSystem)}`}
          />
        </div>
      )}

      {(char.speed_items_modifier ?? 0) !== 0 && (
        <div className="mt-1.5 rounded-lg border border-dnd-border bg-dnd-surface-raised">
          <HomebrewBreakdownRow
            value={char.speed_items_modifier ?? 0}
            label={t('character.hero.speed_items_label')}
            display={`${(char.speed_items_modifier ?? 0) > 0 ? '+' : ''}${formatLength(char.speed_items_modifier ?? 0, unitSystem)}`}
          />
        </div>
      )}

      {/* Saves / Skills summary cards. */}
      <div className="grid grid-cols-2 gap-2 mt-2">
        <Surface variant="elevated" interactive onClick={() => go('saves')} className="!p-3 min-h-[56px]">
          <div className="flex items-center gap-1.5 mb-1.5">
            <GiShieldEchoes size={13} className="text-dnd-gold-bright shrink-0" />
            <span className="text-xs font-cinzel font-bold uppercase tracking-widest text-dnd-gold truncate">
              {t('character.saves.title')}
            </span>
          </div>
          {profSaves.length > 0 ? (
            <div className="flex flex-wrap gap-x-2 gap-y-0.5">
              {profSaves.map((s) => (
                <span key={s.key} className="text-xs text-dnd-text">
                  <span className="font-cinzel uppercase tracking-wide text-dnd-text-muted">{s.label}</span>{' '}
                  <span className="font-mono font-bold tabular-nums">{sign(s.bonus)}</span>
                </span>
              ))}
            </div>
          ) : (
            <span className="text-xs font-body text-dnd-text-faint">{t('character.hero.none_m')}</span>
          )}
        </Surface>

        <Surface variant="elevated" interactive onClick={() => go('skills')} className="!p-3 min-h-[56px]">
          <div className="flex items-center gap-1.5 mb-1.5">
            <GiArcheryTarget size={13} className="text-dnd-gold-bright shrink-0" />
            <span className="text-xs font-cinzel font-bold uppercase tracking-widest text-dnd-gold truncate">
              {t('character.skills.title')}
            </span>
          </div>
          {totalSkillProf > 0 ? (
            <div className="text-xs font-body text-dnd-text">
              <span className="font-mono font-bold tabular-nums">{totalSkillProf}</span>{' '}
              {t('character.hero.proficient_label', { count: totalSkillProf })}
              {expertCount > 0 && (
                <span className="text-dnd-text-muted">
                  {' · '}
                  <span className="font-mono font-bold tabular-nums">{expertCount}</span>{' '}
                  {t('character.hero.expert_label', { count: expertCount })}
                </span>
              )}
            </div>
          ) : (
            <span className="text-xs font-body text-dnd-text-faint">{t('character.hero.none_f')}</span>
          )}
        </Surface>
      </div>

      {initResult && (
        <RollResultModal
          result={initResult}
          title={t('character.hero.initiative')}
          onClose={() => setInitResult(null)}
        />
      )}
    </div>
  )
}

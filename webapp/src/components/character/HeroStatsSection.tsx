import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { BarChart3 } from 'lucide-react'
import { GiShieldEchoes, GiArcheryTarget } from 'react-icons/gi'
import Surface from '@/components/ui/Surface'
import SectionDivider from '@/components/ui/SectionDivider'
import Pressable from '@/components/ui/Pressable'
import HomebrewBreakdownRow from '@/components/homebrew/HomebrewBreakdownRow'
import { haptic } from '@/auth/telegram'
import { profBonus } from '@/lib/dnd'
import { useUnitSettings, formatLength } from '@/store/unitSettings'
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

  // Passive perception — identical formula to Skills.tsx.
  const skills = (char.skills as Record<string, unknown>) ?? {}
  const percLvl = skillLevel(skills['perception'])
  const percHb = char.skills_homebrew_modifiers?.['perception'] ?? 0
  const passivePerception =
    10 + abilityMod('wisdom') + (percLvl === 'expert' ? 2 * pb : percLvl ? pb : 0) + percHb

  const speedTotal = (char.speed ?? 30) + (char.speed_homebrew_modifier ?? 0)
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

  const cells = [
    {
      key: 'init',
      label: t('character.hero.initiative'),
      value: sign(dexMod),
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
        {cells.map((c) => (
          <Pressable
            key={c.key}
            type="button"
            onClick={() => go(c.path)}
            aria-label={`${c.label}: ${c.value}`}
            className="flex flex-col items-center justify-center min-h-[68px] rounded-lg p-2 border
                       bg-dnd-surface-raised border-dnd-border text-dnd-text
                       hover:border-dnd-gold transition-colors"
            whileTap={{ scale: 0.95 }}
          >
            <span className="flex items-center justify-center text-center min-h-[2.2em] px-0.5
                             text-[11px] font-cinzel uppercase tracking-wide leading-tight opacity-80">
              {c.label}
            </span>
            <span className="text-2xl font-mono font-bold tabular-nums leading-none mt-1">
              {c.value}
            </span>
          </Pressable>
        ))}
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

      {/* Saves / Skills summary cards. */}
      <div className="grid grid-cols-2 gap-2 mt-2">
        <Surface variant="elevated" interactive onClick={() => go('saves')} className="!p-3 min-h-[56px]">
          <div className="flex items-center gap-1.5 mb-1.5">
            <GiShieldEchoes size={13} className="text-dnd-gold-bright shrink-0" />
            <span className="text-[10px] font-cinzel font-bold uppercase tracking-widest text-dnd-gold truncate">
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
            <span className="text-[10px] font-cinzel font-bold uppercase tracking-widest text-dnd-gold truncate">
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
    </div>
  )
}

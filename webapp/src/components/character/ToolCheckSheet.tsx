import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Pressable from '@/components/ui/Pressable'
import RollButton from '@/components/ui/RollButton'
import SwitchToggle from '@/components/ui/SwitchToggle'
import DiceIcon from '@/components/ui/DiceIcon'
import type { RollMode } from '@/api/client'
import { toolLabel, type ToolLevel, type ToolSpec } from '@/lib/tools'

const ABILITIES = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma'] as const

/** Prova con strumento: caratteristica (preselezionata nel 2024), abilità usata solo nel 2024, Maestria. */
export default function ToolCheckSheet({
  tool,
  level,
  edition,
  skillKeys,
  pending,
  expertPending,
  onRoll,
  onToggleExpert,
  onClose,
}: {
  tool: ToolSpec | null
  level: ToolLevel
  edition: string
  skillKeys: string[]
  pending: boolean
  expertPending: boolean
  onRoll: (ability: string, skill: string | null, mode: RollMode) => void
  onToggleExpert: () => void
  onClose: () => void
}) {
  const { t, i18n } = useTranslation()
  return (
    <Sheet open={tool !== null} onClose={onClose} title={tool ? toolLabel(tool.key, i18n.language) : ''}>
      {tool && (
        <Body key={tool.key} tool={tool} level={level} edition={edition} skillKeys={skillKeys} pending={pending}
              expertPending={expertPending} onRoll={onRoll} onToggleExpert={onToggleExpert} t={t} />
      )}
    </Sheet>
  )
}

function Body({ tool, level, edition, skillKeys, pending, expertPending, onRoll, onToggleExpert, t }: {
  tool: ToolSpec; level: ToolLevel; edition: string; skillKeys: string[]; pending: boolean; expertPending: boolean
  onRoll: (ability: string, skill: string | null, mode: RollMode) => void; onToggleExpert: () => void
  t: (k: string, o?: Record<string, unknown>) => string
}) {
  const is2024 = edition === '2024'
  const [ability, setAbility] = useState<string | null>(is2024 ? tool.ability : null)
  const [skill, setSkill] = useState('')
  const expert = level === 'expert'
  return (
    <div className="p-5 space-y-4">
      <div>
        <p className="mb-2 text-xs font-body text-dnd-text-muted">{t('character.tools.ability')}</p>
        <div className="grid grid-cols-3 gap-2">
          {ABILITIES.map((a) => (
            <Pressable
              key={a}
              type="button"
              aria-pressed={ability === a}
              onClick={() => setAbility(a)}
              className={`min-h-[44px] px-2 rounded-xl border text-sm font-body transition-colors ${
                ability === a
                  ? 'bg-dnd-gold/15 border-dnd-gold text-dnd-gold-bright'
                  : 'bg-dnd-surface border-dnd-border text-dnd-text'
              }`}
            >
              {t(`character.stats.${a}`)}
            </Pressable>
          ))}
        </div>
      </div>

      {is2024 && (
        <label className="block">
          <span className="mb-2 block text-xs font-body text-dnd-text-muted">{t('character.tools.skill')}</span>
          <select
            aria-label={t('character.tools.skill')}
            value={skill}
            onChange={(e) => setSkill(e.target.value)}
            className="w-full min-h-[44px] rounded-xl border border-dnd-border bg-dnd-surface px-3 text-sm font-body text-dnd-text"
          >
            <option value="">{t('character.tools.skill_none')}</option>
            {skillKeys.map((k) => <option key={k} value={k}>{t(`character.skills.${k}`)}</option>)}
          </select>
          <span className="mt-1 block text-xs font-body text-dnd-text-faint">{t('character.tools.skill_hint')}</span>
        </label>
      )}

      <SwitchToggle
        checked={expert}
        onChange={onToggleExpert}
        label={t('character.tools.expert')}
        aria-label={t('character.tools.expert')}
        pending={expertPending}
      />

      <RollButton
        ariaLabel={t('character.tools.roll')}
        disabled={ability === null}
        pending={pending}
        onRoll={(mode) => ability && onRoll(ability, skill || null, mode)}
        className="w-full min-h-[48px] px-4 py-3 rounded-xl flex items-center justify-center gap-2 font-body font-semibold bg-dnd-gold text-dnd-ink"
      >
        <DiceIcon sides={20} size={20} />
        {t('character.tools.roll')}
      </RollButton>
    </div>
  )
}

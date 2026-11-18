import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { askRollOptions } from '@/lib/rollOptions'
import { conditionLabel } from '@/lib/conditions'
import { api, type RollMode } from '@/api/client'
import { useD20Roll, d20Arg } from '@/hooks/useD20Roll'
import { notifyMutationError } from '@/lib/mutationError'
import { haptic } from '@/auth/telegram'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import FilterChip from '@/components/ui/FilterChip'
import RollModeToggle from '@/components/ui/RollModeToggle'
import RollNotes from '@/components/rules/RollNotes'
import { D20Breakdown } from '@/components/RollResultModal'

type Skill = 'athletics' | 'acrobatics'

/** U36: liberarsi da Trattenuto/Afferrato con un'azione: prova di Atletica o Acrobazia contro la CD dell'effetto. */
export default function EscapeSheet({ charId, slug, dc, onClose }: { charId: number; slug: string; dc: number; onClose: () => void }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const rollD20 = useD20Roll()
  const [mode, setMode] = useState<RollMode>('normal')
  const [skill, setSkill] = useState<Skill>('athletics')
  const cond = conditionLabel(slug, t)

  const roll = useMutation({
    mutationFn: async () => {
      const choice = await askRollOptions(charId, { roll: 'skill', skill })
      return api.characters.escapeCondition(charId, slug, skill, d20Arg(mode, await rollD20(mode, choice), choice))
    },
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      qc.invalidateQueries({ queryKey: ['turn-state', charId] })
      if (res.escaped) haptic.success()
      else haptic.warning()
    },
    onError: notifyMutationError,
  })
  const res = roll.data

  return (
    <Sheet open onClose={onClose} title={t('character.conditions.effect.escape_title', { condition: cond })}>
      <div className="p-5 space-y-4">
        <p className="text-sm font-body text-dnd-text-muted tabular-nums">{t('character.conditions.effect.escape_line', { dc })}</p>
        {!res ? (
          <>
            <div className="flex flex-wrap gap-2">
              {(['athletics', 'acrobatics'] as const).map((s) => (
                <FilterChip key={s} label={t(`character.skills.${s}`)} selected={skill === s} onToggle={() => setSkill(s)} />
              ))}
            </div>
            <RollModeToggle mode={mode} onChange={setMode} />
            <Button size="lg" fullWidth loading={roll.isPending} onClick={() => roll.mutate()}>
              {t('character.conditions.effect.escape_roll')}
            </Button>
          </>
        ) : (
          <div className="space-y-3">
            <p className="text-center font-display text-3xl font-black tabular-nums text-dnd-gold-bright">
              {t('pendingSaves.total_vs_dc', { total: res.roll.total, dc: res.dc })}
            </p>
            <D20Breakdown roll={res.roll} className="text-center" />
            <p className={`text-center font-display font-bold ${res.escaped ? 'text-dnd-emerald-bright' : 'text-dnd-crimson-bright'}`}>
              {t(res.escaped ? 'character.conditions.effect.escape_ok' : 'character.conditions.effect.escape_fail', { condition: cond })}
            </p>
            <RollNotes notes={res.roll.notes} autoFail={res.roll.auto_fail} className="text-center" charId={charId} optionResult={res.roll.option_result} />
            <Button size="lg" fullWidth variant="secondary" onClick={onClose}>
              {t('pendingSaves.ok')}
            </Button>
          </div>
        )}
      </div>
    </Sheet>
  )
}

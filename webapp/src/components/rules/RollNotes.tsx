import { uiLang } from '@/lib/lang'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import Button from '@/components/ui/Button'
import TargetEffectSheet from '@/components/rules/TargetEffectSheet'
import { useRollNoteLabels } from '@/hooks/useRollNoteLabels'
import type { OptionResult } from '@/api/client'

type Props = { notes?: string[]; autoFail?: boolean; className?: string; charId?: number; optionResult?: OptionResult }

/** Perché il tiro ha quel modo o quel bonus: condizioni, armatura, privilegi. */
export default function RollNotes({ notes = [], autoFail = false, className = '', charId, optionResult }: Props) {
  const { t, i18n } = useTranslation()
  const [targetKey, setTargetKey] = useState<string | null>(null)
  const extra = optionResult?.extra_rolls ?? []
  const separate = optionResult?.separate_rolls ?? []
  const effects = optionResult?.effects ?? []
  const second = optionResult?.second_total
  const targets = charId != null ? (optionResult?.targets ?? []) : []
  if (notes.length === 0 && !autoFail && extra.length === 0 && separate.length === 0 && effects.length === 0 && second == null && targets.length === 0) return null
  const lang = uiLang(i18n.language)
  return (
    <>
      {(notes.length > 0 || autoFail) && <Line notes={notes} autoFail={autoFail} className={className} charId={charId} />}
      {extra.length > 0 && <ExtraDice testId="roll-option-dice" label="extra_dice" sources={dieSources(optionResult?.keys ?? [], t)} rolls={extra} types={optionResult!.extra_types} total={optionResult!.extra_total} className={className} />}
      {second != null && (
        <span className={`block text-xs font-mono tabular-nums text-dnd-text-muted ${className}`}>
          {t('character.roll_options.second_attack', { die: optionResult!.second_die, total: second })}
        </span>
      )}
      {separate.length > 0 && <ExtraDice testId="roll-option-separate" label="separate_dice" rolls={separate} types={separate.map(() => optionResult!.separate_type)} total={optionResult!.separate_total ?? 0} className={className} />}
      {effects.map((e) => (
        <span key={e.it} className={`block text-xs font-body text-dnd-text ${className}`}>{e[lang]}</span>
      ))}
      {targets.map((key) => (
        <Button key={key} variant="secondary" size="sm" className="mt-2" onClick={() => setTargetKey(key)}>
          {t('character.target_effect.open')}
        </Button>
      ))}
      {targetKey && charId != null && <TargetEffectSheet charId={charId} effectKey={targetKey} onClose={() => setTargetKey(null)} />}
    </>
  )
}

/** Da dove vengono i dadi extra: l'incantesimo (Benedizione, Guida) o l'ispirazione che li ha dati. */
function dieSources(keys: string[], t: (k: string, o?: Record<string, unknown>) => string): string[] {
  return keys.filter((k) => k.endsWith(':add')).map((k) => {
    const [kind, name] = k.split(':')
    if (kind === 'spell') return t(`character.roll_notes.spell.${name}`, { defaultValue: '' })
    return kind === 'bardic_die' ? t('character.roll_notes.option.bardic_die_add', { defaultValue: '' }) : ''
  }).filter(Boolean)
}

function ExtraDice({ testId, label, sources = [], rolls, types, total, className }: { testId: string; label: string; sources?: string[]; rolls: number[]; types?: (string | null | undefined)[]; total: number; className: string }) {
  const { t } = useTranslation()
  // ogni dado col suo tipo di danno (radiante, fuoco...): un dado extra non è del tipo dell'arma
  const typed = rolls.map((r, i) => (types?.[i] ? `${r} ${t(`character.inventory.damage_types.dmg_${types[i]}`, { defaultValue: types[i] })}` : String(r)))
  return (
    <span data-testid={testId} className={`block text-xs font-mono tabular-nums text-dnd-text-muted ${className}`}>
      {t(`character.roll_options.${label}`)}{sources.length > 0 && ` (${sources.join(', ')})`}: [{typed.join(', ')}] = {total}
    </span>
  )
}

function Line({ notes, autoFail, className, charId }: Required<Omit<Props, 'charId' | 'optionResult'>> & Pick<Props, 'charId'>) {
  const { t } = useTranslation()
  const labels = useRollNoteLabels(charId)
  const parts = [...(autoFail ? [t('character.roll_notes.auto_fail')] : []), ...labels(notes)]
  return (
    <span data-testid="roll-notes" className={`block text-xs font-body text-dnd-amber ${className}`}>
      {parts.join(' · ')}
    </span>
  )
}

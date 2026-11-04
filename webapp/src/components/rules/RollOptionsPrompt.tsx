import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { RollOption } from '@/api/client'
import { usePromptStore, type PromptRequest } from '@/lib/rollOptions'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import Sheet from '@/components/ui/Sheet'
import SwitchToggle from '@/components/ui/SwitchToggle'

/** Da montare una volta sola: ogni flusso di tiro passa da `askRollOptions`. */
export function RollOptionsHost() {
  const request = usePromptStore((s) => s.request)
  return request ? <RollOptionsPrompt key={request.options.map((o) => o.key).join()} request={request} /> : null
}

function RollOptionsPrompt({ request }: { request: PromptRequest }) {
  const { t } = useTranslation()
  const { options, phase, context, answer } = request
  // Sempre tutto spento: una conferma non è mai silenziosa.
  const [chosen, setChosen] = useState<string[]>([])
  const [slots, setSlots] = useState<Record<string, number>>({})

  const setOn = (option: RollOption, on: boolean) => {
    if (on) {
      setChosen((c) => [...c, option.key])
      const lowest = option.input_options[0]?.level
      if (lowest !== undefined) setSlots((s) => ({ [option.key]: lowest, ...s }))
    } else {
      // Spegne anche chi dipende da questa opzione.
      setChosen((c) => c.filter((k) => k !== option.key && options.find((o) => o.key === k)?.needs !== option.key))
    }
  }

  const confirm = () => answer({
    options: chosen,
    option_inputs: Object.fromEntries(
      chosen.filter((k) => slots[k] !== undefined).map((k) => [k, { slot_level: slots[k] }]),
    ),
  })
  const close = (outcome: 'miss' | 'reroll') => answer({ options: [], option_inputs: {}, outcome })

  return (
    <Sheet open onClose={() => undefined} dismissible={false} zClassName="z-[70]" title={t(`character.roll_options.title_${phase}`)}>
      <div className="p-5 space-y-3">
        {context?.summary && (
          <p className="text-sm text-dnd-text font-mono tabular-nums text-center" data-testid="roll-options-summary">
            {context.summary}
          </p>
        )}
        {options.map((option) => (
          <OptionRow
            key={option.key}
            option={option}
            on={chosen.includes(option.key)}
            blocked={!!option.needs && !chosen.includes(option.needs)}
            slot={slots[option.key]}
            onToggle={(on) => setOn(option, on)}
            onSlot={(level) => setSlots((s) => ({ ...s, [option.key]: level }))}
          />
        ))}
        {context?.canReroll && (
          <Button variant="arcane" fullWidth onClick={() => close('reroll')}>
            {t('character.roll_options.reroll')}
          </Button>
        )}
        <div className="flex gap-2">
          {phase === 'after_hit' && (
            <Button variant="secondary" fullWidth onClick={() => close('miss')}>
              {t('character.roll_options.miss')}
            </Button>
          )}
          <Button variant="primary" fullWidth onClick={confirm}>
            {t(`character.roll_options.${{ before: 'roll', after_hit: 'damage', damage_in: 'apply' }[phase]}`)}
          </Button>
        </div>
      </div>
    </Sheet>
  )
}

function OptionRow({ option, on, blocked, slot, onToggle, onSlot }: {
  option: RollOption
  on: boolean
  blocked: boolean
  slot?: number
  onToggle: (on: boolean) => void
  onSlot: (level: number) => void
}) {
  const { t } = useTranslation()
  const hints = [
    option.dice,
    option.bonus ? `${option.bonus > 0 ? '+' : ''}${option.bonus}` : null,
    option.mode ? t(`common.roll_mode.${option.mode}`) : null,
    option.auto_fail ? t('character.roll_notes.auto_fail') : null,
    option.multiplier !== null ? `×${option.multiplier}` : null,
    option.slot ? t(`character.roll_options.slot_${option.slot}`) : null,
    option.once_per_turn ? t('character.roll_options.once_per_turn') : null,
    option.cost?.feature_key ? t('character.roll_options.uses', { count: option.cost.amount }) : null,
  ].filter(Boolean)
  return (
    <div className="rounded-xl border border-dnd-border bg-dnd-surface/80 p-3 space-y-2">
      <SwitchToggle
        checked={on}
        onChange={onToggle}
        disabled={blocked}
        aria-label={option.label}
        label={option.label}
        hint={hints.length > 0 ? hints.join(' · ') : undefined}
      />
      {on && option.input_options.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {option.input_options.map((choice) => (
            <Pressable
              key={choice.level}
              type="button"
              aria-pressed={slot === choice.level}
              onClick={() => onSlot(choice.level)}
              className={`min-h-11 min-w-11 px-3 rounded-lg border font-mono tabular-nums text-sm
                ${slot === choice.level
                  ? 'border-dnd-gold/70 text-dnd-gold-bright shadow-halo-gold'
                  : 'border-dnd-border text-dnd-text'}`}
            >
              {t('character.roll_options.slot_choice', { level: choice.level, available: choice.available })}
              {choice.dice ? ` · ${choice.dice}` : ''}
            </Pressable>
          ))}
        </div>
      )}
    </div>
  )
}

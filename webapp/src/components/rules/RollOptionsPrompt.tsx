import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import type { RollOption } from '@/api/client'
import { optionHints, useAttackLimitStore, useCastConfirmStore, usePromptStore, type PromptRequest } from '@/lib/rollOptions'
import { AfterRollButton } from '@/components/rules/AfterRollOptions'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import Sheet from '@/components/ui/Sheet'
import SwitchToggle from '@/components/ui/SwitchToggle'

/** Da montare una volta sola: ogni flusso di tiro passa da `askRollOptions`. */
export function RollOptionsHost() {
  const request = usePromptStore((s) => s.request)
  const limit = useAttackLimitStore((s) => s.request)
  const castConfirm = useCastConfirmStore((s) => s.request)
  return (
    <>
      {request && <RollOptionsPrompt key={[...request.options, ...request.afterRoll].map((o) => o.key).join()} request={request} />}
      {limit && <AttackLimitPrompt {...limit} />}
      {castConfirm && <CastConfirmPrompt {...castConfirm} />}
    </>
  )
}

function AttackLimitPrompt({ made, allowed, answer }: { made: number; allowed: number; answer: (go: boolean) => void }) {
  const { t } = useTranslation()
  return (
    <Sheet open onClose={() => answer(false)} zClassName="z-[70]" title={t('character.attack.limit_title')}>
      <div className="p-5 space-y-3">
        <p className="text-sm font-body text-dnd-text">{t('character.attack.limit_text', { made, allowed })}</p>
        <div className="flex gap-2">
          <Button variant="secondary" fullWidth onClick={() => answer(false)}>{t('character.attack.limit_cancel')}</Button>
          <Button variant="primary" fullWidth onClick={() => answer(true)}>{t('character.attack.limit_confirm')}</Button>
        </div>
      </div>
    </Sheet>
  )
}

function CastConfirmPrompt({ code, answer }: { code: string; answer: (go: boolean) => void }) {
  const { t } = useTranslation()
  return (
    <Sheet open onClose={() => answer(false)} zClassName="z-[70]" title={t(`character.spells.cast_confirm.${code}_title`)}>
      <div className="p-5 space-y-3">
        <p className="text-sm font-body text-dnd-text">{t(`character.spells.cast_confirm.${code}_body`)}</p>
        <div className="flex gap-2">
          <Button variant="secondary" fullWidth onClick={() => answer(false)}>{t('common.cancel')}</Button>
          <Button variant="primary" fullWidth onClick={() => answer(true)}>{t('character.spells.cast_anyway')}</Button>
        </div>
      </div>
    </Sheet>
  )
}

function RollOptionsPrompt({ request }: { request: PromptRequest }) {
  const { t } = useTranslation()
  const { charId, options, afterRoll, phase, context, answer } = request
  // Sempre tutto spento: una conferma non è mai silenziosa.
  const [chosen, setChosen] = useState<string[]>([])
  const [slots, setSlots] = useState<Record<string, number>>({})
  const [allyOf, setAllyOf] = useState<Record<string, number>>({})  // opzione -> PG della serata che riceve i PF temporanei

  // Spegne un'opzione e chi dipende da lei.
  const without = (keys: string[], gone: string) =>
    keys.filter((k) => k !== gone && options.find((o) => o.key === k)?.needs !== gone)

  const setOn = (option: RollOption, on: boolean) => {
    if (on) {
      // Un gruppo ammette `group_max` opzioni insieme (default una): oltre il limite cade la più vecchia.
      const mates = options.filter((o) => o.group && o.group === option.group && o.key !== option.key).map((o) => o.key)
      const limit = option.group_max ?? 1
      setChosen((c) => {
        const on = c.filter((k) => mates.includes(k))
        return [...on.slice(0, Math.max(0, on.length - (limit - 1))).reduce(without, c), option.key]
      })
      const lowest = option.input_options[0]?.level ?? option.saved_dice?.[0]
      if (lowest !== undefined) setSlots((s) => ({ [option.key]: lowest, ...s }))
    } else {
      setChosen((c) => without(c, option.key))
    }
  }

  const confirm = () => answer({
    options: chosen,
    option_inputs: {
      ...Object.fromEntries(
        chosen.filter((k) => slots[k] !== undefined).map((k) => [
          k, options.find((o) => o.key === k)?.saved_dice?.length ? { die: slots[k] } : { slot_level: slots[k] },
        ]),
      ),
      ...Object.fromEntries(chosen.filter((k) => allyOf[k] !== undefined).map((k) => [k, { target_character_id: allyOf[k] }])),
    },
  })
  // «Mancato» arma anche le opzioni che scattano con ogni mancato (Attacchi Studiati), senza il danno di Graze.
  const close = (outcome: 'miss' | 'reroll') => answer({
    options: [], option_inputs: {}, outcome, ...(outcome === 'miss' ? { after_option: afterRoll.find((o) => o.on_miss) } : {}),
  })

  return (
    <Sheet open onClose={() => undefined} dismissible={false} zClassName="z-[70]" title={t(context?.cast ? 'character.roll_options.title_cast' : `character.roll_options.title_${phase}`)}>
      <div className="p-5 space-y-3">
        {context?.summary && (
          <p className="text-sm text-dnd-text font-mono tabular-nums text-center" data-testid="roll-options-summary">
            {context.summary}
          </p>
        )}
        {afterRoll.map((option) => (
          <AfterRollButton
            key={option.key}
            option={option}
            onClick={() => answer({ options: [], option_inputs: {}, outcome: 'after_roll', after_option: option })}
          />
        ))}
        {options.map((option) => (
          <OptionRow
            key={option.key}
            option={option}
            on={chosen.includes(option.key)}
            blocked={!!option.needs && !chosen.includes(option.needs)}
            slot={slots[option.key]}
            charId={charId}
            ally={allyOf[option.key]}
            onAlly={(id) => setAllyOf((a) => { const { [option.key]: _gone, ...rest } = a; return id === undefined ? rest : { ...rest, [option.key]: id } })}
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
          {!context?.fumble && (
            <Button variant="primary" fullWidth onClick={confirm}>
              {t(context?.cast ? 'character.roll_options.cast' : `character.roll_options.${{ before: 'roll', after_hit: 'damage', damage_in: 'apply' }[phase]}`)}
            </Button>
          )}
        </div>
      </div>
    </Sheet>
  )
}

function OptionRow({ option, on, blocked, slot, charId, ally, onAlly, onToggle, onSlot }: {
  option: RollOption
  on: boolean
  blocked: boolean
  slot?: number
  charId: number
  ally?: number
  onAlly: (id: number | undefined) => void
  onToggle: (on: boolean) => void
  onSlot: (level: number) => void
}) {
  const { t } = useTranslation()
  const hints = optionHints(option, t)
  const { data: allies = [] } = useQuery({
    queryKey: ['session-allies', charId], queryFn: () => api.characters.sessionAllies(charId), enabled: on && !!option.gives_to_ally,
  })
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
              {t(option.requires_input === 'recover' ? 'character.roll_options.slot_recover_choice' : 'character.roll_options.slot_choice', { level: choice.level, available: choice.available })}
              {choice.dice ? ` · ${choice.dice}` : ''}
            </Pressable>
          ))}
        </div>
      )}
      {on && !!option.gives_to_ally && allies.length > 0 && (
        <div className="space-y-2" data-testid="option-ally">
          <p className="text-xs font-cinzel uppercase tracking-wider text-dnd-text-muted">{t('character.roll_options.ally_pick')}</p>
          <div className="flex flex-wrap gap-2">
            {allies.map((a) => (
              <Pressable
                key={a.id}
                type="button"
                aria-pressed={ally === a.id}
                onClick={() => onAlly(ally === a.id ? undefined : a.id)}
                className={`min-h-11 min-w-11 px-3 rounded-lg border text-sm break-words
                  ${ally === a.id ? 'border-dnd-gold/70 text-dnd-gold-bright shadow-halo-gold' : 'border-dnd-border text-dnd-text'}`}
              >
                {a.name}
              </Pressable>
            ))}
          </div>
        </div>
      )}
      {on && !!option.saved_dice?.length && (
        <div className="flex flex-wrap gap-2">
          {option.saved_dice.map((die, i) => (
            <Pressable
              key={`${die}-${i}`}
              type="button"
              aria-pressed={slot === die}
              onClick={() => onSlot(die)}
              className={`min-h-11 min-w-11 px-3 rounded-lg border font-mono tabular-nums text-sm
                ${slot === die
                  ? 'border-dnd-gold/70 text-dnd-gold-bright shadow-halo-gold'
                  : 'border-dnd-border text-dnd-text'}`}
            >
              {die}
            </Pressable>
          ))}
        </div>
      )}
    </div>
  )
}

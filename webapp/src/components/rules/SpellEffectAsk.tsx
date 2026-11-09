import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import AllyTargetSheet from '@/components/rules/AllyTargetSheet'
import type { SpellEffectInfo } from '@/types'

export type SpellEffectPick = { targets?: number[]; choices?: Record<string, string> }

/** Le scelte e i bersagli di un incantesimo con effetto (catalogo): prima le opzioni, poi a chi va, fra te e i personaggi seduti alla serata.
 *  Un effetto solo su di sé non apre il foglio dei bersagli (`targets` assente = te stesso). */
export default function SpellEffectAsk({ charId, title, effect, slotLevel, onConfirm, onClose }: {
  charId: number
  title: string
  effect: SpellEffectInfo
  slotLevel: number
  onConfirm: (pick: SpellEffectPick) => void
  onClose: () => void
}) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language?.startsWith('en') ? 'en' : 'it'
  const [picked, setPicked] = useState<Record<string, string>>({})
  const [choosing, setChoosing] = useState(effect.choices.length > 0)
  const targeted = effect.target_kind !== 'self'
  const { data: allies = [] } = useQuery({ queryKey: ['session-allies', charId], queryFn: () => api.characters.sessionAllies(charId), enabled: targeted && !choosing })
  const choices = effect.choices.length > 0 ? picked : undefined

  if (choosing) {
    const ready = effect.choices.every((c) => picked[c.key])
    return (
      <Sheet open onClose={onClose} title={title} zClassName="z-[60]">
        <div className="flex flex-col gap-2 px-4 pb-4">
          {effect.choices.map((c) => (
            <div key={c.key} className="flex flex-col gap-2">
              <p className="text-xs font-cinzel uppercase tracking-wider text-dnd-text-muted">{c.label[lang]}</p>
              {c.options.map((o) => (
                <Button key={o} variant={picked[c.key] === o ? 'primary' : 'secondary'} className="justify-start break-words text-left"
                  onClick={() => setPicked((p) => ({ ...p, [c.key]: o }))}>{o}</Button>
              ))}
            </div>
          ))}
          <Button variant="primary" disabled={!ready} onClick={() => (targeted ? setChoosing(false) : onConfirm({ choices }))}>
            {t(targeted ? 'character.spells.effect_next' : 'character.spells.effect_confirm')}
          </Button>
        </div>
      </Sheet>
    )
  }
  const list = [{ id: charId, name: t('character.turn.removal_self') }, ...allies.filter((a) => a.id !== charId && !a.dead)]
  return (
    <AllyTargetSheet
      title={title}
      allies={list}
      max={effect.max_targets_by_slot[String(slotLevel)] ?? 1}
      onPick={(id) => onConfirm({ targets: id == null ? [] : [id], choices })}
      onPickMany={(ids) => onConfirm({ targets: ids, choices })}
      onClose={onClose}
    />
  )
}

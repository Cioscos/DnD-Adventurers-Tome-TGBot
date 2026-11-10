import { SELECTED_CLASSES } from '@/lib/selection'
import { uiLang } from '@/lib/lang'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import AllyTargetSheet from '@/components/rules/AllyTargetSheet'
import { optionLabel } from '@/lib/spellChoice'
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
  const lang = uiLang(i18n.language)
  const [picked, setPicked] = useState<Record<string, string>>({})
  const [choosing, setChoosing] = useState(effect.choices.length > 0)
  const targeted = effect.target_kind !== 'self' && effect.target_kind !== 'aura' // l'aura è del lanciatore: nessun bersaglio
  const { data: allies = [] } = useQuery({ queryKey: ['session-allies', charId], queryFn: () => api.characters.sessionAllies(charId), enabled: targeted && !choosing })
  // Arma Magica e Arma Elementale: dopo il bersaglio si sceglie fra le sue armi non magiche
  const [picking, setWeaponFor] = useState<number | null>(null)
  // Randello Incantato: l'arma è la tua (nessun bersaglio) e si sceglie fra i tipi dell'incantesimo
  const selfWeapon = !targeted && !!effect.weapon_choice && !choosing
  const weaponFor = picking ?? (selfWeapon ? charId : null)
  const kinds = effect.weapon_kinds?.length ? effect.weapon_kinds : undefined
  const { data: weapons = [] } = useQuery({ queryKey: ['ally-weapons', charId, weaponFor, kinds], queryFn: () => api.characters.allyWeapons(charId, weaponFor as number, kinds), enabled: weaponFor != null })
  const choices = effect.choices.length > 0 ? picked : undefined
  const pickTargets = (targets: number[]) => (effect.weapon_choice && targets.length === 1 ? setWeaponFor(targets[0]) : onConfirm({ targets, choices }))

  if (choosing) {
    const ready = effect.choices.every((c) => picked[c.key])
    return (
      <Sheet open onClose={onClose} title={title} zClassName="z-[60]">
        <div className="flex flex-col gap-2 px-4 pb-4 pt-3">
          {effect.choices.map((c) => (
            <div key={c.key} className="flex flex-col gap-2">
              <p className="text-xs font-cinzel uppercase tracking-wider text-dnd-text-muted">{c.label[lang]}</p>
              {c.options.map((o) => (
                <Button key={o} variant="secondary" className={`!justify-start break-words text-left ${picked[c.key] === o ? SELECTED_CLASSES : ''}`}
                  onClick={() => setPicked((p) => ({ ...p, [c.key]: o }))}>{optionLabel(t, c.key, o)}</Button>
              ))}
            </div>
          ))}
          <Button variant="primary" disabled={!ready} onClick={() => (targeted || effect.weapon_choice ? setChoosing(false) : onConfirm({ choices }))}>
            {t(targeted || effect.weapon_choice ? 'character.spells.effect_next' : 'character.spells.effect_confirm')}
          </Button>
        </div>
      </Sheet>
    )
  }
  if (weaponFor != null) {
    return (
      <Sheet open onClose={onClose} title={title} zClassName="z-[60]">
        <div className="flex flex-col gap-2 px-4 pb-4 pt-3">
          <p className="text-xs font-cinzel uppercase tracking-wider text-dnd-text-muted">{t('character.spells.effect_weapon')}</p>
          {weapons.length === 0 && <p className="text-sm text-dnd-text-muted">{t('character.spells.effect_no_weapons')}</p>}
          {weapons.map((w) => (
            <Button key={w.id} variant="secondary" fullWidth className="!justify-start break-words text-left"
              onClick={() => onConfirm({ targets: selfWeapon ? undefined : [weaponFor], choices: { ...picked, item_id: String(w.id) } })}>{w.name}</Button>
          ))}
          <Button variant="ghost" fullWidth onClick={() => (selfWeapon ? onClose() : setWeaponFor(null))}>{t('common.back')}</Button>
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
      onPick={(id) => pickTargets(id == null ? [] : [id])}
      onPickMany={pickTargets}
      onClose={onClose}
    />
  )
}

import { useTranslation } from 'react-i18next'
import Pressable from '@/components/ui/Pressable'
import { weaponOptions, type WeaponChoice } from '@/lib/weaponOptions'

type Item = { item_metadata?: Record<string, unknown> | null }

/** Compact pre-attack choice (one/two hands, melee/thrown); renders nothing when the weapon has no options. */
export default function WeaponChoiceRow({
  item, choice, onChange,
}: { item: Item; choice: WeaponChoice; onChange: (c: WeaponChoice) => void }) {
  const { t } = useTranslation()
  const { versatile, thrown } = weaponOptions(item)
  if (!versatile && !thrown) return null

  const seg = (active: boolean) =>
    `flex-1 min-h-11 px-3 text-xs font-medium rounded-lg border transition-colors ${
      active
        ? 'bg-dnd-gold/20 text-dnd-gold-bright border-dnd-gold-dim'
        : 'bg-dnd-chip-bg text-dnd-text-muted border-dnd-border'
    }`
  return (
    <div className="flex flex-wrap gap-2 mt-2">
      {versatile && (
        <div className="flex flex-1 gap-1 min-w-[10rem]">
          <Pressable className={seg(choice.grip === 'one')} aria-pressed={choice.grip === 'one'}
            onClick={() => onChange({ ...choice, grip: 'one' })}>{t('character.attack.grip_one')}</Pressable>
          <Pressable className={seg(choice.grip === 'two')} aria-pressed={choice.grip === 'two'}
            onClick={() => onChange({ ...choice, grip: 'two' })}>{t('character.attack.grip_two')}</Pressable>
        </div>
      )}
      {thrown && (
        <div className="flex flex-1 gap-1 min-w-[10rem]">
          <Pressable className={seg(choice.attack_mode === 'melee')} aria-pressed={choice.attack_mode === 'melee'}
            onClick={() => onChange({ ...choice, attack_mode: 'melee' })}>{t('character.attack.mode_melee')}</Pressable>
          <Pressable className={seg(choice.attack_mode === 'thrown')} aria-pressed={choice.attack_mode === 'thrown'}
            onClick={() => onChange({ ...choice, attack_mode: 'thrown' })}>{t('character.attack.mode_thrown')}</Pressable>
        </div>
      )}
    </div>
  )
}

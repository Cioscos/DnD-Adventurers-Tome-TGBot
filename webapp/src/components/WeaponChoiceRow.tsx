import { useTranslation } from 'react-i18next'
import Pressable from '@/components/ui/Pressable'
import { bestAbility, weaponOptions, type ChoiceChar, type WeaponChoice } from '@/lib/weaponOptions'

type Item = { id?: number; item_metadata?: Record<string, unknown> | null }

/** Compact pre-attack choice (hands, melee/thrown/other hand, ability); renders nothing when the weapon has no options. */
export default function WeaponChoiceRow({
  item, char, choice, onChange,
}: { item: Item; char?: ChoiceChar; choice: WeaponChoice; onChange: (c: WeaponChoice) => void }) {
  const { t } = useTranslation()
  const { versatile, thrown, offhand, ability } = weaponOptions(item, char)
  if (!versatile && !thrown && !offhand && !ability) return null

  const seg = (active: boolean) =>
    `flex-1 min-h-11 px-3 text-xs font-medium rounded-lg border transition-colors ${
      active
        ? 'bg-dnd-gold/20 text-dnd-gold-bright border-dnd-gold-dim'
        : 'bg-dnd-chip-bg text-dnd-text-muted border-dnd-border'
    }`
  const mode = (value: WeaponChoice['attack_mode'], label: string) => (
    <Pressable className={seg(choice.attack_mode === value)} aria-pressed={choice.attack_mode === value}
      onClick={() => onChange({ ...choice, attack_mode: value })}>{t(label)}</Pressable>
  )
  const current = choice.ability ?? bestAbility(char)
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
      {(thrown || offhand) && (
        <div className="flex flex-1 gap-1 min-w-[10rem]">
          {mode('melee', 'character.attack.mode_melee')}
          {thrown && mode('thrown', 'character.attack.mode_thrown')}
          {offhand && mode('offhand', 'character.attack.offhand')}
        </div>
      )}
      {ability && (
        <div className="flex flex-1 gap-1 min-w-[10rem]">
          {(['strength', 'dexterity'] as const).map((a) => (
            <Pressable key={a} className={seg(current === a)} aria-pressed={current === a}
              onClick={() => onChange({ ...choice, ability: a })}>{t(`character.attack.ability_${a}`)}</Pressable>
          ))}
        </div>
      )}
    </div>
  )
}

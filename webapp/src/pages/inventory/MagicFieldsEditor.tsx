import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Plus, X } from 'lucide-react'
import ChipSelect from '@/components/ui/ChipSelect'
import Input from '@/components/ui/Input'
import Pressable from '@/components/ui/Pressable'
import SwitchToggle from '@/components/ui/SwitchToggle'
import {
  RARITIES, BONUS_TARGETS, RECHARGES, CHARGE_AMOUNT_RE,
  type ItemBonus, type GrantedSpell, type Recharge, type Rarity,
} from '@/lib/itemMagic'
import type { ItemFormData } from './itemMetadata'

const labelCls = 'block text-xs uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim'
const fieldCls =
  'min-h-[44px] bg-dnd-surface border border-dnd-border rounded-md px-2 py-1 text-sm font-mono ' +
  'placeholder:text-dnd-text-faint focus:border-dnd-gold/60 focus:outline-none'

/** Numero intero con bozza testuale: svuotare il campo non rimette uno "0" a forza. */
function NumField({ value, onChange, min, max, label, className = '' }: {
  value: number; onChange: (n: number) => void; min: number; max: number; label: string; className?: string
}) {
  const [draft, setDraft] = useState<string | null>(null)
  return (
    <input
      type="number"
      inputMode="numeric"
      aria-label={label}
      title={label}
      placeholder="0"
      min={min}
      max={max}
      value={draft ?? String(value)}
      onChange={(e) => {
        setDraft(e.target.value)
        const n = parseInt(e.target.value, 10)
        onChange(Number.isNaN(n) ? min : Math.min(max, Math.max(min, n)))
      }}
      onBlur={() => setDraft(null)}
      className={`${fieldCls} text-center ${className}`}
    />
  )
}

interface Props {
  form: ItemFormData
  onChange: (patch: Partial<ItemFormData>) => void
}

export default function MagicFieldsEditor({ form, onChange }: Props) {
  const { t } = useTranslation()
  const m = (k: string) => t(`character.inventory.magic.${k}`)
  const { charges } = form

  const setBonus = (i: number, patch: Partial<ItemBonus>) =>
    onChange({ bonuses: form.bonuses.map((b, j) => (j === i ? { ...b, ...patch } : b)) })
  const setSpell = (i: number, patch: Partial<GrantedSpell>) =>
    onChange({ granted_spells: form.granted_spells.map((g, j) => (j === i ? { ...g, ...patch } : g)) })

  return (
    <div className="space-y-3 rounded-xl border border-dnd-border p-3">
      <SwitchToggle
        checked={form.is_magic}
        onChange={(v) => onChange({ is_magic: v })}
        label={m('is_magic')}
        aria-label={m('is_magic')}
      />

      {form.is_magic && (
        <>
          <ChipSelect
            label={m('rarity_label')}
            options={[
              { value: '', label: m('rarity_none') },
              ...RARITIES.map((r) => ({ value: r, label: t(`character.inventory.magic.rarity.${r}`) })),
            ]}
            value={form.rarity}
            onChange={(v) => onChange({ rarity: v as '' | Rarity })}
            columns={3}
          />

          <Input
            label={m('cost_gp')}
            type="number"
            inputMode="decimal"
            min={0}
            value={form.cost_gp}
            onChange={(v) => onChange({ cost_gp: v })}
            placeholder="0"
          />

          <SwitchToggle
            checked={form.requires_attunement}
            onChange={(v) => onChange({ requires_attunement: v, attuned: v ? form.attuned : false })}
            label={m('requires_attunement')}
            aria-label={m('requires_attunement')}
          />

          {/* Bonus */}
          <div className="space-y-2">
            <p className={labelCls}>{m('bonuses')}</p>
            {form.bonuses.map((b, i) => (
              <div key={i} className="flex items-center gap-2">
                <select
                  aria-label={m('bonus_target')}
                  value={b.target}
                  onChange={(e) => setBonus(i, { target: e.target.value })}
                  className={`${fieldCls} flex-1 min-w-0`}
                >
                  {BONUS_TARGETS.map((tg) => (
                    <option key={tg} value={tg}>{t(`character.inventory.magic.targets.${tg}`)}</option>
                  ))}
                </select>
                <NumField
                  label={m('bonus_value')} value={b.value} min={-10} max={10} className="w-16"
                  onChange={(n) => setBonus(i, { value: n })}
                />
                <Pressable
                  onClick={() => onChange({ bonuses: form.bonuses.filter((_, j) => j !== i) })}
                  className="shrink-0 min-h-[44px] min-w-[44px] flex items-center justify-center text-dnd-text-muted"
                  aria-label={m('remove')}
                >
                  <X size={16} />
                </Pressable>
              </div>
            ))}
            <Pressable
              onClick={() => onChange({ bonuses: [...form.bonuses, { target: 'ac', value: 1 }] })}
              className="inline-flex items-center gap-1 min-h-[44px] text-xs text-dnd-gold-bright px-2"
            >
              <Plus size={14} /> {m('add_bonus')}
            </Pressable>
          </div>

          {/* Cariche */}
          <div className="space-y-2">
            <SwitchToggle
              checked={!!charges}
              onChange={(v) =>
                onChange({
                  charges: v ? { max: 1, current: 1, recharge: 'none', recharge_amount: 'all' } : null,
                  ...(v ? {} : { granted_spells: form.granted_spells.map((g) => ({ ...g, charges_cost: 0 })) }),
                })}
              label={m('has_charges')}
              aria-label={m('has_charges')}
            />
            {charges && (
              <>
                <div className="flex gap-2">
                  <label className="flex-1 text-xs text-dnd-text-muted">
                    {m('charges_max')}
                    <NumField
                      label={m('charges_max')} value={charges.max} min={1} max={100} className="w-full"
                      onChange={(n) => onChange({ charges: { ...charges, max: n, current: Math.min(charges.current, n) } })}
                    />
                  </label>
                  <label className="flex-1 text-xs text-dnd-text-muted">
                    {m('charges_current')}
                    <NumField
                      label={m('charges_current')} value={charges.current} min={0} max={charges.max} className="w-full"
                      onChange={(n) => onChange({ charges: { ...charges, current: n } })}
                    />
                  </label>
                </div>
                <ChipSelect
                  label={m('recharge_label')}
                  options={RECHARGES.map((r) => ({ value: r, label: t(`character.inventory.magic.recharge.${r}`) }))}
                  value={charges.recharge}
                  onChange={(v) => onChange({ charges: { ...charges, recharge: v as Recharge } })}
                  columns={2}
                />
                {charges.recharge !== 'none' && (
                  <Input
                    label={m('recharge_amount')}
                    value={charges.recharge_amount}
                    onChange={(v) => onChange({ charges: { ...charges, recharge_amount: v } })}
                    placeholder="all / 1d6+1"
                    error={CHARGE_AMOUNT_RE.test(charges.recharge_amount.trim()) ? undefined : m('recharge_amount_invalid')}
                  />
                )}
              </>
            )}
          </div>

          {/* Incantesimi concessi */}
          <div className="space-y-2">
            <p className={labelCls}>{m('granted_spells')}</p>
            {form.granted_spells.map((g, i) => (
              <div key={i} className="rounded-xl border border-dnd-border p-3 space-y-2">
                <div className="flex items-center gap-2">
                  <input
                    aria-label={m('spell_name')}
                    placeholder={m('spell_name')}
                    value={g.name}
                    onChange={(e) => setSpell(i, { name: e.target.value })}
                    className={`${fieldCls} flex-1 min-w-0 font-body`}
                  />
                  <Pressable
                    onClick={() => onChange({ granted_spells: form.granted_spells.filter((_, j) => j !== i) })}
                    className="shrink-0 min-h-[44px] min-w-[44px] flex items-center justify-center text-dnd-text-muted"
                    aria-label={m('remove')}
                  >
                    <X size={16} />
                  </Pressable>
                </div>
                <div className="flex gap-2">
                  <label className="flex-1 text-xs text-dnd-text-muted">
                    {m('spell_level')}
                    <NumField label={m('spell_level')} value={g.level} min={0} max={9} className="w-full"
                      onChange={(n) => setSpell(i, { level: n })} />
                  </label>
                  <label className="flex-1 text-xs text-dnd-text-muted">
                    {m('spell_cost')}
                    <NumField label={m('spell_cost')} value={g.charges_cost} min={0} max={charges?.max ?? 0} className="w-full"
                      onChange={(n) => setSpell(i, { charges_cost: n })} />
                  </label>
                </div>
                <SwitchToggle
                  checked={g.is_concentration}
                  onChange={(v) => setSpell(i, { is_concentration: v })}
                  label={m('spell_concentration')}
                  aria-label={m('spell_concentration')}
                />
              </div>
            ))}
            <Pressable
              onClick={() => onChange({
                granted_spells: [...form.granted_spells, { name: '', level: 1, charges_cost: 0, is_concentration: false }],
              })}
              className="inline-flex items-center gap-1 min-h-[44px] text-xs text-dnd-gold-bright px-2"
            >
              <Plus size={14} /> {m('add_spell')}
            </Pressable>
          </div>
        </>
      )}
    </div>
  )
}

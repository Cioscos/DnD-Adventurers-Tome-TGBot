import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BookOpen } from 'lucide-react'
import Sheet from '@/components/ui/Sheet'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import ChipSelect from '@/components/ui/ChipSelect'
import CatalogPicker from '@/components/catalog/CatalogPicker'
import { localized, type Lang, type MonsterEntry } from '@/lib/srd/catalog'
import { KINDS, familiarWarning, formatCr, monsterToStatblock, wildShapeWarning, wildShapeMaxCr } from '@/lib/companionRules'
import type { CompanionKind, CompanionPayload } from '@/types'

const DICE = /^\d+d\d+([+-]\d+)?$/i

interface Props {
  druidLevel: number
  isMoon: boolean
  pending?: boolean
  onSubmit: (body: CompanionPayload) => void
  onClose: () => void
}

/** Creation sheet: pick a monster from the SRD catalogue or type the stats by hand. Warnings are advisory. */
export default function CompanionForm({ druidLevel, isMoon, pending, onSubmit, onClose }: Props) {
  const { t, i18n } = useTranslation()
  const lang: Lang = i18n.language?.startsWith('en') ? 'en' : 'it'
  const [kind, setKind] = useState<CompanionKind>('familiar')
  const [name, setName] = useState('')
  const [hp, setHp] = useState('')
  const [ac, setAc] = useState('')
  const [atkName, setAtkName] = useState('')
  const [atkBonus, setAtkBonus] = useState('')
  const [atkDice, setAtkDice] = useState('')
  const [notes, setNotes] = useState('')
  const [entry, setEntry] = useState<MonsterEntry | null>(null)
  const [picking, setPicking] = useState(false)

  const warnKey = !entry ? null
    : kind === 'familiar' ? familiarWarning(entry)
      : kind === 'wild_shape' ? wildShapeWarning(entry, druidLevel, isMoon) : null

  const pick = (e: MonsterEntry) => {
    setEntry(e)
    setName(localized(e.name, lang).text)
    setHp(String(e.hit_points))
    setAc(String(e.armor_class))
    setPicking(false)
  }

  const manualAttack = atkName.trim() && atkBonus !== '' && DICE.test(atkDice.trim())
  const submit = () => {
    const base = { kind, name: name.trim(), max_hp: Number(hp) || 0, armor_class: Number(ac) || 10, notes: notes.trim() || null }
    if (entry) {
      onSubmit({ ...base, srd_index: entry.index, statblock: monsterToStatblock(entry, lang) })
    } else {
      onSubmit({
        ...base,
        statblock: manualAttack
          ? { actions: [{ name: atkName.trim(), attack_bonus: Number(atkBonus), damage_dice: atkDice.trim() }] }
          : {},
      })
    }
  }

  return (
    <>
      <Sheet open onClose={onClose} title={t('character.extras.add')}>
        <div className="p-5 space-y-3">
          <ChipSelect
            label={t('character.extras.kind')}
            options={KINDS.map((k) => ({ value: k, label: t(`character.extras.kinds.${k}`) }))}
            value={kind}
            onChange={(v) => setKind(v as CompanionKind)}
            columns={2}
          />
          <Button variant="secondary" fullWidth className="min-h-11" icon={<BookOpen size={16} />} onClick={() => setPicking(true)}>
            {t('character.extras.from_catalog')}
          </Button>
          {entry && (
            <p className="text-xs text-dnd-text-muted font-body">
              {localized(entry.name, lang).text} · {t('character.extras.cr')} {formatCr(entry.challenge_rating)}
            </p>
          )}
          {warnKey && (
            <p role="status" className="text-sm font-body px-3 py-2 rounded-xl border border-dnd-amber/50 bg-dnd-amber/10 text-dnd-amber">
              {t(warnKey, { cr: formatCr(wildShapeMaxCr(druidLevel, isMoon)) })}
            </p>
          )}
          <Input label={t('character.extras.name')} value={name} onChange={setName} />
          <div className="grid grid-cols-2 gap-3">
            <Input label={t('character.extras.hp')} type="number" inputMode="numeric" min={0} value={hp} onChange={setHp} />
            <Input label={t('character.extras.ac')} type="number" inputMode="numeric" min={0} value={ac} onChange={setAc} />
          </div>
          {!entry && (
            <div className="grid grid-cols-3 gap-3">
              <Input label={t('character.extras.attack')} value={atkName} onChange={setAtkName} />
              <Input label={t('character.extras.to_hit')} type="number" inputMode="numeric" value={atkBonus} onChange={setAtkBonus} />
              <Input label={t('character.extras.damage')} value={atkDice} onChange={setAtkDice} placeholder="1d6+2" />
            </div>
          )}
          <Input label={t('character.extras.notes')} variant="textarea" value={notes} onChange={setNotes} />
          <Button fullWidth size="lg" loading={pending} disabled={!name.trim()} onClick={submit}>
            {t('common.add')}
          </Button>
        </div>
      </Sheet>
      {picking && <CatalogPicker kind="monsters" onPick={pick} onClose={() => setPicking(false)} />}
    </>
  )
}

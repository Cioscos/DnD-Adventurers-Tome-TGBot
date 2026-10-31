import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BookOpen } from 'lucide-react'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import Pressable from '@/components/ui/Pressable'
import CatalogPicker from '@/components/catalog/CatalogPicker'
import { localized, type Lang } from '@/lib/srd/catalog'
import type { RaceEntry, SubraceEntry } from '@/lib/species'
import { formatLength, useUnitSettings } from '@/store/unitSettings'

export interface SpeciesChoice { race: RaceEntry | null; sub: SubraceEntry | null }

interface Props {
  choice: SpeciesChoice
  onChoice: (c: SpeciesChoice) => void
  /** Free-text species (used only when no catalogue race is picked). */
  freeText: string
  onFreeText: (v: string) => void
}

const ABBR: Record<string, string> = {
  str: 'strength', dex: 'dexterity', con: 'constitution', int: 'intelligence', wis: 'wisdom', cha: 'charisma',
}

export default function SpeciesStep({ choice, onChoice, freeText, onFreeText }: Props) {
  const { t, i18n } = useTranslation()
  const lang: Lang = i18n.language?.startsWith('en') ? 'en' : 'it'
  const unit = useUnitSettings((s) => s.system)
  const [picking, setPicking] = useState(false)
  const { race, sub } = choice
  const bonuses: Record<string, number> = { ...race?.ability_bonuses }
  for (const [k, v] of Object.entries(sub?.ability_bonuses ?? {})) bonuses[k] = (bonuses[k] ?? 0) + v

  return (
    <div className="space-y-3">
      <p className="text-xs text-dnd-text-faint font-body italic text-center">{t('character.create.species_hint')}</p>
      <Button variant="secondary" fullWidth icon={<BookOpen size={16} />} onClick={() => setPicking(true)}>
        {race ? localized(race.name, lang).text : t('character.create.species_pick')}
      </Button>

      {race && race.subraces.length > 0 && (
        <div className="flex flex-wrap gap-2" role="group" aria-label={t('character.create.subrace')}>
          {[null, ...race.subraces].map((s) => (
            <Pressable
              key={s?.index ?? 'none'}
              onClick={() => onChoice({ race, sub: s })}
              className={`min-h-[44px] px-3 rounded-xl border text-[13px] font-display font-bold
                ${(sub?.index ?? null) === (s?.index ?? null)
                  ? '!border-dnd-gold shadow-halo-gold text-dnd-gold-bright' : 'border-dnd-border text-dnd-text'}`}
            >
              {s ? localized(s.name, lang).text : t('character.create.subrace_none')}
            </Pressable>
          ))}
        </div>
      )}

      {race && (
        <div className="rounded-xl border border-dnd-border bg-dnd-surface p-3 text-sm font-body space-y-1">
          <p className="tabular-nums">
            {t('character.create.species_speed')}: {formatLength(sub?.speed_ft ?? race.speed_ft, unit)}
          </p>
          {Object.keys(bonuses).length > 0 && (
            <p>{Object.entries(bonuses).map(([k, v]) => `${t(`common.abilities.${ABBR[k] ?? k}`)} +${v}`).join(' · ')}</p>
          )}
          {[...race.senses, ...(sub?.senses ?? [])].map((s) => (
            <p key={s.type} className="tabular-nums">
              {t(`character.create.sense_${s.type}`)} {formatLength(s.range_ft, unit)}
            </p>
          ))}
          <p className="text-dnd-text-muted">
            {[...race.traits, ...(sub?.traits ?? [])].map((tr) => localized(tr.name, lang).text).join(', ')}
          </p>
          <Pressable
            onClick={() => onChoice({ race: null, sub: null })}
            className="min-h-[44px] text-[12px] text-dnd-gold-dim underline underline-offset-2"
          >
            {t('character.create.species_clear')}
          </Pressable>
        </div>
      )}

      {!race && (
        <Input
          label={t('character.create.species_free')}
          value={freeText}
          onChange={onFreeText}
          placeholder={t('character.identity.placeholder_race')}
        />
      )}

      {picking && (
        <CatalogPicker
          kind="races"
          onClose={() => setPicking(false)}
          onPick={(e) => { onChoice({ race: e as unknown as RaceEntry, sub: null }); setPicking(false) }}
        />
      )}
    </div>
  )
}

import { uiLang } from '@/lib/lang'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BookOpen } from 'lucide-react'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import Pressable from '@/components/ui/Pressable'
import CatalogPicker from '@/components/catalog/CatalogPicker'
import { localized, type Lang } from '@/lib/srd/catalog'
import SpeciesChoices from '@/components/character/SpeciesChoices'
import { raceBonuses, type RaceEntry, type Species2024Entry, type SubraceEntry } from '@/lib/species'
import { formatLength, useUnitSettings } from '@/store/unitSettings'

/** `sub`: null = «altra sottorazza», da completare a mano; undefined = non ancora scelta (2014 pag. 17: dove la razza ne ha, è obbligatoria).
 *  `picks`: le caratteristiche a scelta che prendono +1 (Mezzelfo, 2014 pag. 39). */
export interface SpeciesChoice { race: RaceEntry | null; sub: SubraceEntry | null | undefined; picks?: string[] }
export interface Species24State { entry: Species2024Entry | null; options: Record<string, string> }

interface Props {
  choice: SpeciesChoice
  onChoice: (c: SpeciesChoice) => void
  /** Free-text species (used only when no catalogue race is picked). */
  freeText: string
  onFreeText: (v: string) => void
  /** 2024: catalogo species-2024 con le sue scelte al posto di razza/sottorazza. */
  edition?: '2014' | '2024'
  species24?: Species24State
  onSpecies24?: (s: Species24State) => void
  /** Abilità già date da classe e background: non sceglibili come abilità della specie. */
  takenSkills?: string[]
  /** Talento d'Origine non ripetibile del background: non sceglibile per Versatile. */
  takenFeats?: string[]
}

const ABBR: Record<string, string> = {
  str: 'strength', dex: 'dexterity', con: 'constitution', int: 'intelligence', wis: 'wisdom', cha: 'charisma',
}

/** Tratti di lignaggio/eredità/stirpe (chiave `<scelta>_..._<opzione>`) di opzioni non scelte: nascosti. */
function visibleTraits(e: Species2024Entry, options: Record<string, string>) {
  return e.traits.filter((tr) => !e.choices.some((c) => c.options.some((o) =>
    o.key !== options[c.key] && tr.key.startsWith(`${c.key}_`) && tr.key.endsWith(`_${o.key}`))))
}

/** Velocità della specie: speed_ft è la base della scheda, il +5 di Goliath ed Elfo dei boschi (PHB 2024 pag. 192, 190)
 *  è un modificatore del motore (core/rules/catalog/species_2024.py), qui ripetuto per mostrarlo prima della creazione. */
function speciesSpeed(e: Species2024Entry, options: Record<string, string>): number {
  return e.speed_ft + (e.key === '2024_goliath' || (e.key === '2024_elf' && options.lineage === 'wood') ? 5 : 0)
}

export default function SpeciesStep({ choice, onChoice, freeText, onFreeText, edition = '2014', species24, onSpecies24, takenSkills, takenFeats }: Props) {
  const { t, i18n } = useTranslation()
  const lang: Lang = uiLang(i18n.language)
  const unit = useUnitSettings((s) => s.system)
  const [picking, setPicking] = useState(false)
  const { race, sub, picks = [] } = choice
  const toPick = race?.ability_choices ?? 0
  const e24 = edition === '2024' ? species24?.entry ?? null : null
  const bonuses = raceBonuses(race, sub, picks)

  return (
    <div className="space-y-3">
      <p className="text-xs text-dnd-text-faint font-body italic text-center">{t('character.create.species_hint')}</p>
      <Button variant="secondary" fullWidth icon={<BookOpen size={16} />} onClick={() => setPicking(true)}>
        {e24 ? localized(e24.name, lang).text : race && edition === '2014' ? localized(race.name, lang).text : t('character.create.species_pick')}
      </Button>

      {e24 && species24 && onSpecies24 && (
        <>
          <SpeciesChoices species={e24} value={species24.options} onChange={(options) => onSpecies24({ entry: e24, options })} takenSkills={takenSkills} takenFeats={takenFeats} />
          <div className="rounded-xl border border-dnd-border bg-dnd-surface p-3 text-sm font-body space-y-1">
            <p className="tabular-nums">
              {t('character.create.species_speed')}: {formatLength(speciesSpeed(e24, species24.options), unit)}
            </p>
            <p className="text-dnd-text-muted">
              {visibleTraits(e24, species24.options).map((tr) => tr.name[lang]).join(', ')}
            </p>
            <Pressable
              onClick={() => onSpecies24({ entry: null, options: {} })}
              className="min-h-[44px] text-xs text-dnd-gold-dim underline underline-offset-2"
            >
              {t('character.create.species_clear')}
            </Pressable>
          </div>
        </>
      )}

      {edition === '2014' && race && race.subraces.length > 0 && (
        <div className="flex flex-wrap gap-2" role="group" aria-label={t('character.create.subrace')}>
          {[null, ...race.subraces].map((s) => (
            <Pressable
              key={s?.index ?? 'none'}
              onClick={() => onChoice({ ...choice, sub: s })}
              className={`min-h-[44px] px-3 rounded-xl border text-sm font-body font-semibold
                ${sub !== undefined && (sub?.index ?? null) === (s?.index ?? null)
                  ? '!border-dnd-gold bg-dnd-gold/20 text-dnd-gold-bright' : 'border-dnd-border text-dnd-text'}`}
            >
              {s ? localized(s.name, lang).text : t('character.create.subrace_other')}
            </Pressable>
          ))}
        </div>
      )}

      {edition === '2014' && race && toPick > 0 && (
        <div role="group" aria-label={t('character.create.ability_choices', { n: picks.length, max: toPick })}>
          <p className="mb-1.5 text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim tabular-nums">
            {t('character.create.ability_choices', { n: picks.length, max: toPick })}
          </p>
          <div className="flex flex-wrap gap-2">
            {Object.keys(ABBR).filter((k) => !(k in race.ability_bonuses)).map((k) => (
              <Pressable
                key={k}
                aria-pressed={picks.includes(k)}
                disabled={!picks.includes(k) && picks.length >= toPick}
                onClick={() => onChoice({ ...choice, picks: picks.includes(k) ? picks.filter((p) => p !== k) : [...picks, k] })}
                className={`min-h-[44px] px-3 rounded-xl border text-sm font-body font-semibold
                  ${picks.includes(k) ? '!border-dnd-gold bg-dnd-gold/20 text-dnd-gold-bright' : 'border-dnd-border text-dnd-text'} disabled:opacity-40`}
              >
                {t(`common.abilities.${ABBR[k]}`)} +1
              </Pressable>
            ))}
          </div>
        </div>
      )}

      {edition === '2014' && race && (
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
            className="min-h-[44px] text-xs text-dnd-gold-dim underline underline-offset-2"
          >
            {t('character.create.species_clear')}
          </Pressable>
        </div>
      )}

      {!(edition === '2024' ? e24 : race) && (
        <Input
          label={t('character.create.species_free')}
          value={freeText}
          onChange={onFreeText}
          placeholder={t('character.identity.placeholder_race')}
        />
      )}

      {picking && edition === '2014' && (
        <CatalogPicker
          kind="races"
          onClose={() => setPicking(false)}
          onPick={(e) => { onChoice({ race: e as unknown as RaceEntry, sub: undefined }); setPicking(false) }}
        />
      )}
      {picking && edition === '2024' && (
        <CatalogPicker
          kind="species-2024"
          onClose={() => setPicking(false)}
          onPick={(e) => { onSpecies24?.({ entry: e, options: {} }); setPicking(false) }}
        />
      )}
    </div>
  )
}

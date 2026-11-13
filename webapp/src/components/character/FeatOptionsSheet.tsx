import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Pressable from '@/components/ui/Pressable'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { WEAPON_KINDS } from '@/data/weaponMastery'
import { profBonus } from '@/lib/dnd'
import { featByKey } from '@/lib/feats'
import { uiLang } from '@/lib/lang'
import { SKILL_KEYS } from '@/lib/species'
import { loadSpellCatalog, localized, spellToForm, type SpellEntry } from '@/lib/srd/catalog'
import { useUnitSettings } from '@/store/unitSettings'
import type { Ability, CharacterFull } from '@/types'

interface Props {
  char: CharacterFull
  ability: Ability
  open: boolean
  onClose: () => void
}

const FIELD = 'w-full min-h-[44px] px-3 rounded-xl bg-dnd-surface border border-dnd-border text-sm font-body text-dnd-text'
const LISTS = ['cleric', 'druid', 'wizard'] as const
// Talenti 2014 con una lista di classe: la caratteristica viene dalla classe (specchio di `_LIST_ABILITY`)
const LISTS_2014 = ['bard', 'cleric', 'druid', 'sorcerer', 'warlock', 'wizard'] as const
const CASTING = ['intelligence', 'wisdom', 'charisma'] as const

// Specchi di api/services/choices.py e core/rules/catalog/feats_2024.py
const SKILL_CHOICES: Record<string, readonly string[]> = {
  '2024_keen_mind': ['arcana', 'history', 'investigation', 'nature', 'religion'],
  '2024_observant': ['insight', 'investigation', 'perception'],
}
const ADEPT_TYPES = ['acid', 'cold', 'fire', 'lightning', 'thunder'] as const
const ENERGY_TYPES = ['acid', 'cold', 'fire', 'lightning', 'necrotic', 'poison', 'psychic', 'radiant', 'thunder'] as const
const TOUCHED_SCHOOLS: Record<string, readonly string[]> = {
  '2024_fey_touched': ['divination', 'enchantment'],
  '2024_shadow_touched': ['illusion', 'necromancy'],
}

const chip = (on: boolean) =>
  `min-h-[44px] px-3 rounded-xl border text-sm font-body ${on ? 'bg-dnd-gold/15 border-dnd-gold text-dnd-gold-bright' : 'border-dnd-border text-dnd-text'}`

/** Aggiunge o toglie `value` da `list`, al massimo `max` voci. */
const toggled = <T,>(list: T[], value: T, max: number): T[] =>
  list.includes(value) ? list.filter((v) => v !== value) : list.length < max ? [...list, value] : list

/** «Completa talento»: le scelte proprie di un talento (abilità, strumenti, tipi di danno, arma, incantesimi), una volta sola. */
export default function FeatOptionsSheet({ char, ability, open, onClose }: Props) {
  const { t, i18n } = useTranslation()
  const lang = uiLang(i18n.language)
  const unitSystem = useUnitSettings((s) => s.system)
  const qc = useQueryClient()
  const key = (ability.feature_key ?? '').slice('feat.'.length)
  const feat = featByKey(key)
  const needs = feat?.needs ?? []
  const is2014 = !key.startsWith('2024_')
  const [picks, setPicks] = useState<string[]>([])
  const [tool, setTool] = useState('')
  const [texts, setTexts] = useState(['', '', ''])
  const [list, setList] = useState('')
  const [stat, setStat] = useState('')
  const [chosen, setChosen] = useState<SpellEntry[]>([])
  const [catalog, setCatalog] = useState<SpellEntry[]>([])
  const [skill, setSkill] = useState('')
  const [expertise, setExpertise] = useState('')
  const [types, setTypes] = useState<string[]>([])
  const [weapon, setWeapon] = useState('')
  const [many, setMany] = useState<string[]>([]) // manovre o armi

  const has = (n: string) => needs.includes(n)
  const needsSpells = has('list') || has('spell') || has('rituals')
  useEffect(() => {
    if (open && needsSpells) void loadSpellCatalog(char.rules_edition === '2024' ? '2024' : '2014').then(setCatalog)
  }, [open, needsSpells, char.rules_edition])

  const addTool = () => {
    const name = tool.trim()
    if (name && !picks.includes(`tool:${name}`)) setPicks(toggled(picks, `tool:${name}`, 3))
    setTool('')
  }
  const toggleSpell = (e: SpellEntry, max: number) => {
    const on = chosen.some((c) => c.index === e.index)
    const sameLevel = chosen.filter((c) => c.level === e.level).length
    if (on) setChosen(chosen.filter((c) => c.index !== e.index))
    else if (sameLevel < max) setChosen([...chosen, e])
  }

  const textKey = needs.find((n) => n === 'tools' || n === 'instruments' || n === 'languages')
  const ritualCount = has('list') ? 2 : profBonus(char.total_level ?? 1)
  const manyKey = needs.find((n) => n === 'maneuvers' || n === 'weapons')
  const manyCount = manyKey === 'weapons' ? 4 : 2
  const manyOptions = manyKey === 'maneuvers' ? (feat?.choices ?? []).map((c) => ({ key: c.key, label: c.name[lang] }))
    : WEAPON_KINDS.map((w) => ({ key: w.key, label: lang === 'en' ? w.en : w.it }))
  const cantripCount = has('spell') ? 2 : 1
  const typeCount = has('damage_types') ? 2 : 1
  const typeOptions = has('damage_types') ? ENERGY_TYPES : ADEPT_TYPES
  const skillOptions = SKILL_CHOICES[key] ?? SKILL_KEYS
  const skillLevel = (s: string) => (char.skills as Record<string, unknown> | undefined)?.[s]
  const proficient = (s: string) => !!skillLevel(s)
  const expert = (s: string) => skillLevel(s) === 'expert' // già con Maestria: il server rifiuta la scelta
  const expertiseOptions = (has('skill') ? SKILL_KEYS.filter((s) => proficient(s) || s === skill) : SKILL_KEYS).filter((s) => !expert(s))

  const ready = has('picks') ? picks.length === 3
    : textKey ? texts.every((x) => x.trim()) && new Set(texts.map((x) => x.trim().toLowerCase())).size === 3
      : manyKey ? many.length === manyCount
      : has('list') && has('rituals') ? !!list && chosen.length === 2
      : has('list') ? !!list && (is2014 || !!stat) && chosen.filter((c) => c.level === 0).length === cantripCount
        && chosen.filter((c) => c.level === 1).length === (has('spell') ? 1 : 0)
        : has('rituals') ? chosen.length === ritualCount
          : has('spell') ? chosen.length === 1
            : has('weapon_mastery') ? !!weapon
              : (!has('skill') || !!skill) && (!has('expertise') || !!expertise)
                && (!(has('damage_type') || has('damage_types')) || types.length === typeCount)

  const spellPayload = () => [...chosen].sort((a, b) => a.level - b.level).map((e) => {
    const f = spellToForm(e, lang, unitSystem)
    return {
      name: f.name ?? e.index, level: e.level, description: f.description || undefined, casting_time: f.casting_time || undefined,
      range_area: f.range_area || undefined, components: f.components || undefined, duration: f.duration || undefined,
      is_concentration: e.concentration, is_ritual: e.ritual, higher_level: f.higher_level || undefined,
      attack_save: f.attack_save || undefined, damage_dice: f.damage_dice || undefined, damage_type: f.damage_type || undefined,
      school: e.school, srd_index: e.index, higher_levels_dice: f.higher_levels_dice || undefined,
    }
  })

  const payload = (): { options: Record<string, string | string[]>; spells: ReturnType<typeof spellPayload> } => {
    if (has('picks')) return { options: { picks }, spells: [] }
    if (textKey) return { options: { [textKey]: texts.map((x) => x.trim()) }, spells: [] }
    if (manyKey) return { options: { [manyKey]: many }, spells: [] }
    if (has('list')) return { options: is2014 ? { list } : { list, ability: stat }, spells: spellPayload() }
    if (has('spell') || has('rituals')) return { options: {}, spells: spellPayload() }
    if (has('weapon_mastery')) return { options: { weapon_mastery: [weapon] }, spells: [] }
    const options: Record<string, string | string[]> = {}
    if (has('skill')) options.skill = skill
    if (has('expertise')) options.expertise = expertise
    if (has('damage_type')) options.damage_type = types[0]
    if (has('damage_types')) options.damage_types = types
    return { options, spells: [] }
  }

  const mutation = useMutation({
    mutationFn: () => api.feats.complete(char.id, ability.id, payload()),
    onSuccess: (updated) => {
      qc.setQueryData(['character', char.id], updated)
      haptic.success()
      onClose()
    },
    onError: () => haptic.error(),
  })

  const ofList = (level: number) => catalog.filter((e) => e.level === level && (e.classes ?? []).includes(list)
    && (!has('rituals') || e.ritual) && (has('spell') || has('rituals') || e.attack_type === 'ATK'))
  const spellChips = (entries: SpellEntry[], max: number) => (
    <div className="flex flex-wrap gap-2">
      {entries.map((e) => {
        const on = chosen.some((c) => c.index === e.index)
        return (
          <Pressable key={e.index} onClick={() => toggleSpell(e, max)} aria-pressed={on} className={chip(on)}>
            {localized(e.name, lang).text}
          </Pressable>
        )
      })}
    </div>
  )
  const hint = (text: string) => <p className="text-xs font-body text-dnd-text-muted">{text}</p>

  return (
    <Sheet open={open} onClose={onClose} title={t('character.feats.complete_title', { name: ability.name })}>
      <div className="p-5 space-y-3">
        {has('picks') && (
          <>
            {hint(t('character.feats.picks_hint', { n: 3 - picks.length }))}
            <div className="flex flex-wrap gap-2">
              {SKILL_KEYS.map((s) => (
                <Pressable key={s} onClick={() => setPicks(toggled(picks, s, 3))} aria-pressed={picks.includes(s)} className={chip(picks.includes(s))}>
                  {t(`character.skills.${s}`)}
                </Pressable>
              ))}
              {picks.filter((p) => p.startsWith('tool:')).map((p) => (
                <Pressable key={p} onClick={() => setPicks(toggled(picks, p, 3))} aria-pressed className={chip(true)}>{p.slice(5)}</Pressable>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                type="text" value={tool} maxLength={50} onChange={(e) => setTool(e.target.value)}
                aria-label={t('character.feats.tool_name')} placeholder={t('character.feats.tool_name')} className={FIELD}
              />
              <Pressable onClick={addTool} disabled={!tool.trim() || picks.length >= 3} className={`${chip(false)} shrink-0 disabled:opacity-40`}>
                {t('character.feats.tool_add')}
              </Pressable>
            </div>
          </>
        )}

        {textKey && texts.map((value, i) => (
          <input
            key={i} type="text" value={value} maxLength={50}
            onChange={(e) => setTexts(texts.map((x, j) => (j === i ? e.target.value : x)))}
            aria-label={t(`character.feats.${textKey}_name`, { n: i + 1 })}
            placeholder={t(`character.feats.${textKey}_name`, { n: i + 1 })}
            className={FIELD}
          />
        ))}

        {has('skill') && (
          <>
            {hint(t(has('expertise') ? 'character.feats.skill_new_hint' : 'character.feats.skill_hint'))}
            <div className="flex flex-wrap gap-2">
              {skillOptions.filter((s) => !expert(s) && (!has('expertise') || !proficient(s))).map((s) => (
                <Pressable key={s} onClick={() => setSkill(skill === s ? '' : s)} aria-pressed={skill === s} className={chip(skill === s)}>
                  {t(`character.skills.${s}`)}
                </Pressable>
              ))}
            </div>
          </>
        )}

        {has('expertise') && (
          <>
            {hint(t('character.feats.expertise_hint'))}
            <div className="flex flex-wrap gap-2">
              {expertiseOptions.map((s) => (
                <Pressable key={s} onClick={() => setExpertise(expertise === s ? '' : s)} aria-pressed={expertise === s} className={chip(expertise === s)}>
                  {t(`character.skills.${s}`)}
                </Pressable>
              ))}
            </div>
          </>
        )}

        {(has('damage_type') || has('damage_types')) && (
          <>
            {hint(t('character.feats.damage_type_hint', { count: typeCount }))}
            <div className="flex flex-wrap gap-2">
              {typeOptions.map((d) => (
                <Pressable key={d} onClick={() => setTypes(toggled(types, d, typeCount))} aria-pressed={types.includes(d)} className={chip(types.includes(d))}>
                  {t(`character.inventory.damage_types.dmg_${d}`)}
                </Pressable>
              ))}
            </div>
          </>
        )}

        {manyKey && (
          <>
            {hint(t(`character.feats.${manyKey}_hint`, { n: manyCount - many.length }))}
            <div className="flex flex-wrap gap-2">
              {manyOptions.map((o) => (
                <Pressable key={o.key} onClick={() => setMany(toggled(many, o.key, manyCount))} aria-pressed={many.includes(o.key)} className={chip(many.includes(o.key))}>
                  {o.label}
                </Pressable>
              ))}
            </div>
          </>
        )}

        {has('weapon_mastery') && (
          <select value={weapon} onChange={(e) => setWeapon(e.target.value)} aria-label={t('character.feats.weapon')} className={FIELD}>
            <option value="">{t('character.feats.weapon')}</option>
            {WEAPON_KINDS.map((w) => <option key={w.key} value={w.key}>{lang === 'en' ? w.en : w.it}</option>)}
          </select>
        )}

        {has('list') && (
          <>
            <select value={list} onChange={(e) => { setList(e.target.value); setChosen([]) }} aria-label={t('character.feats.mi_list')} className={FIELD}>
              <option value="">{t('character.feats.mi_list')}</option>
              {(is2014 ? LISTS_2014 : LISTS).map((l) => <option key={l} value={l}>{t(`dnd.classes.${l}`)}</option>)}
            </select>
            {!is2014 && <select value={stat} onChange={(e) => setStat(e.target.value)} aria-label={t('character.feats.mi_ability')} className={FIELD}>
              <option value="">{t('character.feats.mi_ability')}</option>
              {CASTING.map((a) => <option key={a} value={a}>{t(`common.abilities.${a}`)}</option>)}
            </select>}
            {list && has('rituals') && (
              <>
                {hint(t('character.feats.rituals_hint', { n: ritualCount - chosen.length }))}
                {spellChips(ofList(1), ritualCount)}
              </>
            )}
            {list && !has('rituals') && (has('spell') ? [0, 1] : [0]).map((level) => (
              <div key={level} className="space-y-2">
                {hint(t(level === 1 ? 'character.feats.mi_spell' : has('spell') ? 'character.feats.mi_cantrips' : 'character.feats.sniper_cantrip'))}
                {spellChips(ofList(level), level === 0 ? cantripCount : 1)}
              </div>
            ))}
          </>
        )}

        {has('spell') && !has('list') && (
          <>
            {hint(t('character.feats.touched_hint'))}
            {spellChips(catalog.filter((e) => e.level === 1 && (TOUCHED_SCHOOLS[key] ?? []).includes(e.school)), 1)}
          </>
        )}

        {has('rituals') && !has('list') && (
          <>
            {hint(t('character.feats.rituals_hint', { n: ritualCount - chosen.length }))}
            {spellChips(catalog.filter((e) => e.level === 1 && e.ritual), ritualCount)}
          </>
        )}

        {mutation.isError && (
          <p className="text-xs font-body text-dnd-crimson-bright">{t('character.level_choice.error')}</p>
        )}
        <Pressable
          onClick={() => mutation.mutate()}
          disabled={!ready}
          pending={mutation.isPending}
          className="w-full min-h-[44px] rounded-xl bg-dnd-gold/15 border border-dnd-gold text-sm font-body text-dnd-gold-bright disabled:opacity-40"
        >
          {t('character.feats.complete_confirm')}
        </Pressable>
      </div>
    </Sheet>
  )
}

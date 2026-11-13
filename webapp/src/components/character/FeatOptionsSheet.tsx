import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Pressable from '@/components/ui/Pressable'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { FEATS_2024 } from '@/lib/feats'
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
const CASTING = ['intelligence', 'wisdom', 'charisma'] as const

const chip = (on: boolean) =>
  `min-h-[44px] px-3 rounded-xl border text-sm font-body ${on ? 'bg-dnd-gold/15 border-dnd-gold text-dnd-gold-bright' : 'border-dnd-border text-dnd-text'}`

/** «Completa talento»: le scelte proprie di un talento (Abile, Artigiano, Musicista, Iniziato alla magia), una volta sola. */
export default function FeatOptionsSheet({ char, ability, open, onClose }: Props) {
  const { t, i18n } = useTranslation()
  const lang = uiLang(i18n.language)
  const unitSystem = useUnitSettings((s) => s.system)
  const qc = useQueryClient()
  const key = (ability.feature_key ?? '').slice('feat.'.length)
  const needs = FEATS_2024.find((f) => f.key === key)?.needs ?? []
  const [picks, setPicks] = useState<string[]>([])
  const [tool, setTool] = useState('')
  const [texts, setTexts] = useState(['', '', ''])
  const [list, setList] = useState('')
  const [stat, setStat] = useState('')
  const [chosen, setChosen] = useState<SpellEntry[]>([])
  const [catalog, setCatalog] = useState<SpellEntry[]>([])

  const needsSpells = needs.includes('list')
  useEffect(() => {
    if (open && needsSpells) void loadSpellCatalog(char.rules_edition === '2024' ? '2024' : '2014').then(setCatalog)
  }, [open, needsSpells, char.rules_edition])

  const toggle = (value: string) =>
    setPicks(picks.includes(value) ? picks.filter((p) => p !== value) : picks.length < 3 ? [...picks, value] : picks)
  const addTool = () => {
    const name = tool.trim()
    if (name && !picks.includes(`tool:${name}`)) toggle(`tool:${name}`)
    setTool('')
  }
  const toggleSpell = (e: SpellEntry) => {
    const on = chosen.some((c) => c.index === e.index)
    const sameLevel = chosen.filter((c) => c.level === e.level).length
    if (on) setChosen(chosen.filter((c) => c.index !== e.index))
    else if (sameLevel < (e.level === 0 ? 2 : 1)) setChosen([...chosen, e])
  }

  const textKey = needs.find((n) => n === 'tools' || n === 'instruments')
  const ready = needs.includes('picks') ? picks.length === 3
    : textKey ? texts.every((x) => x.trim()) && new Set(texts.map((x) => x.trim().toLowerCase())).size === 3
      : !!list && !!stat && chosen.filter((c) => c.level === 0).length === 2 && chosen.filter((c) => c.level === 1).length === 1

  const mutation = useMutation({
    mutationFn: () => {
      if (needs.includes('picks')) return api.feats.complete(char.id, ability.id, { options: { picks }, spells: [] })
      if (textKey) return api.feats.complete(char.id, ability.id, { options: { [textKey]: texts.map((x) => x.trim()) }, spells: [] })
      const spells = [...chosen].sort((a, b) => a.level - b.level).map((e) => {
        const f = spellToForm(e, lang, unitSystem)
        return {
          name: f.name ?? e.index, level: e.level, description: f.description || undefined, casting_time: f.casting_time || undefined,
          range_area: f.range_area || undefined, components: f.components || undefined, duration: f.duration || undefined,
          is_concentration: e.concentration, is_ritual: e.ritual, higher_level: f.higher_level || undefined,
          attack_save: f.attack_save || undefined, damage_dice: f.damage_dice || undefined, damage_type: f.damage_type || undefined,
          school: e.school, srd_index: e.index, higher_levels_dice: f.higher_levels_dice || undefined,
        }
      })
      return api.feats.complete(char.id, ability.id, { options: { list, ability: stat }, spells })
    },
    onSuccess: (updated) => {
      qc.setQueryData(['character', char.id], updated)
      haptic.success()
      onClose()
    },
    onError: () => haptic.error(),
  })

  const ofList = (level: number) => catalog.filter((e) => e.level === level && (e.classes ?? []).includes(list))

  return (
    <Sheet open={open} onClose={onClose} title={t('character.feats.complete_title', { name: ability.name })}>
      <div className="p-5 space-y-3">
        {needs.includes('picks') && (
          <>
            <p className="text-xs font-body text-dnd-text-muted">{t('character.feats.picks_hint', { n: 3 - picks.length })}</p>
            <div className="flex flex-wrap gap-2">
              {SKILL_KEYS.map((s) => (
                <Pressable key={s} onClick={() => toggle(s)} aria-pressed={picks.includes(s)} className={chip(picks.includes(s))}>
                  {t(`character.skills.${s}`)}
                </Pressable>
              ))}
              {picks.filter((p) => p.startsWith('tool:')).map((p) => (
                <Pressable key={p} onClick={() => toggle(p)} aria-pressed className={chip(true)}>{p.slice(5)}</Pressable>
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

        {needs.includes('list') && (
          <>
            <select value={list} onChange={(e) => { setList(e.target.value); setChosen([]) }} aria-label={t('character.feats.mi_list')} className={FIELD}>
              <option value="">{t('character.feats.mi_list')}</option>
              {LISTS.map((l) => <option key={l} value={l}>{t(`dnd.classes.${l}`)}</option>)}
            </select>
            <select value={stat} onChange={(e) => setStat(e.target.value)} aria-label={t('character.feats.mi_ability')} className={FIELD}>
              <option value="">{t('character.feats.mi_ability')}</option>
              {CASTING.map((a) => <option key={a} value={a}>{t(`common.abilities.${a}`)}</option>)}
            </select>
            {list && [0, 1].map((level) => (
              <div key={level} className="space-y-2">
                <p className="text-xs font-body text-dnd-text-muted">
                  {t(level === 0 ? 'character.feats.mi_cantrips' : 'character.feats.mi_spell')}
                </p>
                <div className="flex flex-wrap gap-2">
                  {ofList(level).map((e) => {
                    const on = chosen.some((c) => c.index === e.index)
                    return (
                      <Pressable key={e.index} onClick={() => toggleSpell(e)} aria-pressed={on} className={chip(on)}>
                        {localized(e.name, lang).text}
                      </Pressable>
                    )
                  })}
                </div>
              </div>
            ))}
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

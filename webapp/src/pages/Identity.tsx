import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import { haptic } from '@/auth/telegram'

type DamageModifiers = {
  resistances: string[]
  immunities: string[]
  vulnerabilities: string[]
}

type Draft = {
  name: string; race: string; gender: string; background: string
  alignment: string; speed: string
  personality_traits: string; ideals: string; bonds: string; flaws: string
  languages: string; general_proficiencies: string
  damageModifiers: DamageModifiers
}

export default function Identity() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [draft, setDraft] = useState<Draft | null>(null)
  const [dmgInputs, setDmgInputs] = useState({ resistances: '', immunities: '', vulnerabilities: '' })

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  useEffect(() => {
    if (char && !draft) {
      const personality = (char.personality as Record<string, string>) ?? {}
      const raw = (char.damage_modifiers as Record<string, string[]>) ?? {}
      setDraft({
        name: char.name ?? '',
        race: char.race ?? '',
        gender: char.gender ?? '',
        background: char.background ?? '',
        alignment: char.alignment ?? '',
        speed: String(char.speed ?? 30),
        personality_traits: personality.traits ?? '',
        ideals: personality.ideals ?? '',
        bonds: personality.bonds ?? '',
        flaws: personality.flaws ?? '',
        languages: (char.languages as string[] ?? []).join(', '),
        general_proficiencies: (char.general_proficiencies as string[] ?? []).join(', '),
        damageModifiers: {
          resistances: raw.resistances ?? [],
          immunities: raw.immunities ?? [],
          vulnerabilities: raw.vulnerabilities ?? [],
        },
      })
    }
  }, [char])

  const mutation = useMutation({
    mutationFn: () => {
      if (!draft) throw new Error('No draft')
      return api.characters.update(charId, {
        name: draft.name.trim(),
        race: draft.race.trim() || null,
        gender: draft.gender.trim() || null,
        background: draft.background.trim() || null,
        alignment: draft.alignment.trim() || null,
        speed: Number(draft.speed) || 30,
        personality: {
          traits: draft.personality_traits.trim(),
          ideals: draft.ideals.trim(),
          bonds: draft.bonds.trim(),
          flaws: draft.flaws.trim(),
        },
        languages: draft.languages.split(',').map((s) => s.trim()).filter(Boolean),
        general_proficiencies: draft.general_proficiencies.split(',').map((s) => s.trim()).filter(Boolean),
        damage_modifiers: draft.damageModifiers,
      })
    },
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  if (!char || !draft) return null

  const set = (key: keyof Draft) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setDraft((d) => d ? { ...d, [key]: e.target.value } : d)

  const inputClass = 'w-full bg-white/10 rounded-xl px-3 py-2 outline-none focus:ring-2 focus:ring-[var(--tg-theme-button-color)]'
  const taClass = inputClass + ' resize-none'

  const addDmgModifier = (type: keyof DamageModifiers) => {
    const val = dmgInputs[type].trim()
    if (!val) return
    setDraft((d) => {
      if (!d) return d
      const current = d.damageModifiers[type]
      if (current.includes(val)) return d
      return { ...d, damageModifiers: { ...d.damageModifiers, [type]: [...current, val] } }
    })
    setDmgInputs((prev) => ({ ...prev, [type]: '' }))
  }

  const removeDmgModifier = (type: keyof DamageModifiers, val: string) => {
    setDraft((d) => {
      if (!d) return d
      return {
        ...d,
        damageModifiers: {
          ...d.damageModifiers,
          [type]: d.damageModifiers[type].filter((v) => v !== val),
        },
      }
    })
  }

  const dmgSections: { key: keyof DamageModifiers; label: string }[] = [
    { key: 'resistances', label: t('character.identity.resistances') },
    { key: 'immunities', label: t('character.identity.immunities') },
    { key: 'vulnerabilities', label: t('character.identity.vulnerabilities') },
  ]

  return (
    <Layout title={t('character.identity.title')} backTo={`/char/${charId}`}>
      <Card>
        <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">{t('character.identity.name')}</p>
        <input type="text" value={draft.name} onChange={set('name')} className={inputClass} />
      </Card>

      <div className="grid grid-cols-2 gap-2">
        <Card>
          <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">{t('character.identity.race')}</p>
          <input type="text" value={draft.race} onChange={set('race')} placeholder="—" className={inputClass} />
        </Card>
        <Card>
          <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">{t('character.identity.gender')}</p>
          <input type="text" value={draft.gender} onChange={set('gender')} placeholder="—" className={inputClass} />
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <Card>
          <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">{t('character.identity.background')}</p>
          <input type="text" value={draft.background} onChange={set('background')} placeholder="—" className={inputClass} />
        </Card>
        <Card>
          <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">{t('character.identity.alignment')}</p>
          <input type="text" value={draft.alignment} onChange={set('alignment')} placeholder="—" className={inputClass} />
        </Card>
      </div>

      <Card>
        <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">{t('character.identity.speed')}</p>
        <input type="number" min="0" value={draft.speed} onChange={set('speed')} className={inputClass} />
      </Card>

      {[
        { key: 'personality_traits' as const, label: t('character.identity.personality') },
        { key: 'ideals' as const, label: t('character.identity.ideals') },
        { key: 'bonds' as const, label: t('character.identity.bonds') },
        { key: 'flaws' as const, label: t('character.identity.flaws') },
      ].map(({ key, label }) => (
        <Card key={key}>
          <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">{label}</p>
          <textarea value={draft[key]} onChange={set(key)} rows={2} placeholder="—" className={taClass} />
        </Card>
      ))}

      <Card>
        <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">
          {t('character.identity.languages')} <span className="text-[var(--tg-theme-hint-color)]">(separati da virgola)</span>
        </p>
        <input type="text" value={draft.languages} onChange={set('languages')} placeholder="Comune, Elfico..." className={inputClass} />
      </Card>

      <Card>
        <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">
          {t('character.identity.proficiencies')} <span className="text-[var(--tg-theme-hint-color)]">(separati da virgola)</span>
        </p>
        <input type="text" value={draft.general_proficiencies} onChange={set('general_proficiencies')} placeholder="Armature leggere, Spade..." className={inputClass} />
      </Card>

      {/* Damage Modifiers */}
      <Card>
        <p className="font-medium mb-3">{t('character.identity.damage_modifiers')}</p>
        <div className="space-y-4">
          {dmgSections.map(({ key, label }) => (
            <div key={key}>
              <p className="text-xs text-[var(--tg-theme-hint-color)] mb-2">{label}</p>
              <div className="flex flex-wrap gap-1 mb-2">
                {draft.damageModifiers[key].map((val) => (
                  <span
                    key={val}
                    className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-white/10 text-sm"
                  >
                    {val}
                    <button
                      onClick={() => removeDmgModifier(key, val)}
                      className="text-red-400 hover:text-red-300 leading-none"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={dmgInputs[key]}
                  onChange={(e) => setDmgInputs((prev) => ({ ...prev, [key]: e.target.value }))}
                  onKeyDown={(e) => e.key === 'Enter' && addDmgModifier(key)}
                  placeholder={t('character.identity.damage_type_placeholder')}
                  className="flex-1 bg-white/10 rounded-xl px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--tg-theme-button-color)]"
                />
                <button
                  onClick={() => addDmgModifier(key)}
                  className="px-3 py-2 rounded-xl bg-[var(--tg-theme-button-color)] text-[var(--tg-theme-button-text-color)] font-bold"
                >
                  +
                </button>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <button
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
        className="w-full py-3 rounded-2xl bg-[var(--tg-theme-button-color)]
                   text-[var(--tg-theme-button-text-color)] font-semibold
                   disabled:opacity-40 active:opacity-80"
      >
        {mutation.isPending ? '...' : t('common.save')}
      </button>
    </Layout>
  )
}

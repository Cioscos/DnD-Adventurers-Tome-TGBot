import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import DndInput from '@/components/DndInput'
import DndButton from '@/components/DndButton'
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

  const set = (key: keyof Draft) => (v: string) =>
    setDraft((d) => d ? { ...d, [key]: v } : d)

  const setTA = (key: keyof Draft) => (e: React.ChangeEvent<HTMLTextAreaElement>) =>
    setDraft((d) => d ? { ...d, [key]: e.target.value } : d)

  const taClass = 'w-full px-3 py-3 min-h-[48px] rounded-xl bg-dnd-surface text-dnd-text border border-transparent outline-none transition-all duration-150 placeholder:text-dnd-text-secondary/50 focus:border-dnd-gold-dim focus:shadow-[0_0_0_2px_var(--dnd-gold-glow)] resize-none'

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
    <Layout title={t('character.identity.title')} backTo={`/char/${charId}`} group="character" page="identity">
      <Card>
        <DndInput label={t('character.identity.name')} value={draft.name} onChange={set('name')} />
      </Card>

      <div className="grid grid-cols-2 gap-2">
        <Card>
          <DndInput label={t('character.identity.race')} value={draft.race} onChange={set('race')} placeholder={t('character.identity.placeholder_race')} />
        </Card>
        <Card>
          <DndInput label={t('character.identity.gender')} value={draft.gender} onChange={set('gender')} placeholder={t('character.identity.placeholder_gender')} />
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <Card>
          <DndInput label={t('character.identity.background')} value={draft.background} onChange={set('background')} placeholder={t('character.identity.placeholder_background')} />
        </Card>
        <Card>
          <DndInput label={t('character.identity.alignment')} value={draft.alignment} onChange={set('alignment')} placeholder={t('character.identity.placeholder_alignment')} />
        </Card>
      </div>

      <Card>
        <DndInput label={t('character.identity.speed')} type="number" min={0} value={draft.speed} onChange={set('speed')} />
      </Card>

      {[
        { key: 'personality_traits' as const, label: t('character.identity.personality') },
        { key: 'ideals' as const, label: t('character.identity.ideals') },
        { key: 'bonds' as const, label: t('character.identity.bonds') },
        { key: 'flaws' as const, label: t('character.identity.flaws') },
      ].map(({ key, label }) => (
        <Card key={key}>
          <p className="block text-[11px] uppercase tracking-wider mb-1 font-medium text-dnd-gold-dim">{label}</p>
          <textarea value={draft[key] as string} onChange={setTA(key)} rows={2} placeholder={t(`character.identity.placeholder_${key}`)} className={taClass} />
        </Card>
      ))}

      <Card>
        <DndInput
          label={`${t('character.identity.languages')} (separati da virgola)`}
          value={draft.languages}
          onChange={set('languages')}
          placeholder="Comune, Elfico..."
        />
      </Card>

      <Card>
        <DndInput
          label={`${t('character.identity.proficiencies')} (separati da virgola)`}
          value={draft.general_proficiencies}
          onChange={set('general_proficiencies')}
          placeholder="Armature leggere, Spade..."
        />
      </Card>

      {/* Damage Modifiers */}
      <Card>
        <p className="font-medium mb-3">{t('character.identity.damage_modifiers')}</p>
        <div className="space-y-4">
          {dmgSections.map(({ key, label }) => (
            <div key={key}>
              <p className="text-xs text-dnd-text-secondary mb-2">{label}</p>
              <div className="flex flex-wrap gap-1 mb-2">
                {draft.damageModifiers[key].map((val) => (
                  <span
                    key={val}
                    className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-dnd-surface text-sm"
                  >
                    {val}
                    <button
                      onClick={() => removeDmgModifier(key, val)}
                      className="text-[var(--dnd-danger)] hover:opacity-70 leading-none"
                    >
                      &times;
                    </button>
                  </span>
                ))}
              </div>
              <div className="flex gap-2">
                <DndInput
                  value={dmgInputs[key]}
                  onChange={(v) => setDmgInputs((prev) => ({ ...prev, [key]: v }))}
                  placeholder={t('character.identity.damage_type_placeholder')}
                  className="flex-1"
                />
                <DndButton
                  onClick={() => addDmgModifier(key)}
                  className="px-3"
                >
                  +
                </DndButton>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <DndButton
        onClick={() => mutation.mutate()}
        loading={mutation.isPending}
        className="w-full"
      >
        {t('common.save')}
      </DndButton>
    </Layout>
  )
}

import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { User, Globe2, Feather, Save, Plus, X, Shield, Zap, Flame, Lock } from 'lucide-react'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import SectionDivider from '@/components/ui/SectionDivider'
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

const DMG_TONES: Record<keyof DamageModifiers, { bg: string; text: string; border: string; icon: typeof Shield }> = {
  resistances: { bg: 'bg-[var(--dnd-cobalt)]/15', text: 'text-[var(--dnd-cobalt-bright)]', border: 'border-dnd-cobalt/40', icon: Shield },
  immunities: { bg: 'bg-[var(--dnd-gold)]/15', text: 'text-dnd-gold-bright', border: 'border-dnd-gold/40', icon: Zap },
  vulnerabilities: { bg: 'bg-[var(--dnd-crimson)]/15', text: 'text-[var(--dnd-crimson-bright)]', border: 'border-dnd-crimson/40', icon: Flame },
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

  const personalitySections = [
    { key: 'personality_traits' as const, label: t('character.identity.personality') },
    { key: 'ideals' as const, label: t('character.identity.ideals') },
    { key: 'bonds' as const, label: t('character.identity.bonds') },
    { key: 'flaws' as const, label: t('character.identity.flaws') },
  ]

  return (
    <Layout title={t('character.identity.title')} backTo={`/char/${charId}`} group="character" page="identity">
      {/* Hero name */}
      <Surface variant="tome" ornamented>
        <Input
          label={t('character.identity.name')}
          value={draft.name}
          onChange={set('name')}
          className="[&_input]:text-xl [&_input]:font-display [&_input]:font-bold"
        />
      </Surface>

      {/* Physicality section */}
      <SectionDivider icon={<User size={11} />} align="center">
        {t('character.identity.physicality', { defaultValue: 'Fisicità' })}
      </SectionDivider>

      <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
        <Surface variant="elevated" className="!p-3">
          <Input label={t('character.identity.race')} value={draft.race} onChange={set('race')} placeholder={t('character.identity.placeholder_race')} />
        </Surface>
        <Surface variant="elevated" className="!p-3">
          <Input label={t('character.identity.gender')} value={draft.gender} onChange={set('gender')} placeholder={t('character.identity.placeholder_gender')} />
        </Surface>
        <Surface variant="elevated" className="!p-3">
          <Input label={t('character.identity.alignment')} value={draft.alignment} onChange={set('alignment')} placeholder={t('character.identity.placeholder_alignment')} />
        </Surface>
      </div>

      <Surface variant="elevated" className="!p-3 md:max-w-xs">
        <Input label={t('character.identity.speed')} type="number" min={0} value={draft.speed} onChange={set('speed')} inputMode="numeric" />
      </Surface>

      {/* Personality section */}
      <SectionDivider icon={<Feather size={11} />} align="center">
        {t('character.identity.personality', { defaultValue: 'Personalità' })}
      </SectionDivider>

      {/* Lock badge — immediately after SectionDivider */}
      <div className="flex items-center justify-center gap-1 -mt-2 mb-3 text-dnd-gold-dim">
        <Lock size={10} />
        <span className="text-[10px] font-cinzel uppercase tracking-wider">
          {t('character.identity.private_badge')}
        </span>
      </div>

      {/* Background — first private item */}
      <Surface variant="parchment" className="!pt-5 !px-4 !pb-4 relative mb-3">
        <span className="absolute -top-2.5 left-4 px-2 bg-dnd-surface-raised text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim rounded">
          {t('character.identity.background')}
        </span>
        <Input
          value={draft.background}
          onChange={set('background')}
          placeholder={t('character.identity.placeholder_background')}
          className="[&_input]:!border-transparent [&_input]:!bg-transparent"
        />
      </Surface>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mt-3">
        {personalitySections.map(({ key, label }) => (
          <Surface key={key} variant="parchment" className="!pt-5 !px-4 !pb-4 relative">
            <span className="absolute -top-2.5 left-4 px-2 bg-dnd-surface-raised text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim rounded">
              {label}
            </span>
            <Input
              variant="textarea"
              value={draft[key] as string}
              onChange={set(key)}
              rows={3}
              placeholder={t(`character.identity.placeholder_${key}`)}
              className="[&_textarea]:!border-transparent [&_textarea]:!bg-transparent [&_textarea]:italic"
            />
          </Surface>
        ))}
      </div>

      {/* Culture */}
      <SectionDivider icon={<Globe2 size={11} />} align="center">
        {t('character.identity.culture', { defaultValue: 'Cultura' })}
      </SectionDivider>

      <Surface variant="elevated">
        <Input
          label={`${t('character.identity.languages')} (separati da virgola)`}
          value={draft.languages}
          onChange={set('languages')}
          placeholder="Comune, Elfico..."
        />
      </Surface>
      <Surface variant="elevated">
        <Input
          label={`${t('character.identity.proficiencies')} (separati da virgola)`}
          value={draft.general_proficiencies}
          onChange={set('general_proficiencies')}
          placeholder="Armature leggere, Spade..."
        />
      </Surface>

      {/* Damage Modifiers */}
      <SectionDivider icon={<Shield size={11} />} align="center">
        {t('character.identity.damage_modifiers')}
      </SectionDivider>

      <Surface variant="elevated">
        <div className="space-y-4">
          {(Object.keys(DMG_TONES) as Array<keyof DamageModifiers>).map((key) => {
            const tone = DMG_TONES[key]
            const ToneIcon = tone.icon
            return (
              <div key={key}>
                <div className="flex items-center gap-2 mb-2">
                  <ToneIcon size={12} className={tone.text} />
                  <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim">
                    {t(`character.identity.${key}`)}
                  </p>
                </div>
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {draft.damageModifiers[key].map((val) => (
                    <m.span
                      key={val}
                      className={`inline-flex items-center gap-1 px-2 py-1 rounded-full border text-xs font-body ${tone.bg} ${tone.text} ${tone.border}`}
                      initial={{ opacity: 0, scale: 0.8 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.8 }}
                    >
                      {val}
                      <m.button
                        onClick={() => removeDmgModifier(key, val)}
                        className="hover:opacity-60"
                        whileTap={{ scale: 0.8 }}
                        aria-label="Remove"
                      >
                        <X size={11} />
                      </m.button>
                    </m.span>
                  ))}
                </div>
                <div className="flex gap-2 items-end">
                  <Input
                    value={dmgInputs[key]}
                    onChange={(v) => setDmgInputs((prev) => ({ ...prev, [key]: v }))}
                    placeholder={t('character.identity.damage_type_placeholder')}
                    onCommit={() => addDmgModifier(key)}
                    className="flex-1"
                  />
                  <Button variant="secondary" size="md" onClick={() => addDmgModifier(key)} icon={<Plus size={14} />} />
                </div>
              </div>
            )
          })}
        </div>
      </Surface>

      <Button
        variant="primary"
        size="lg"
        fullWidth
        onClick={() => mutation.mutate()}
        loading={mutation.isPending}
        icon={<Save size={18} />}
        haptic="success"
      >
        {t('common.save')}
      </Button>
    </Layout>
  )
}

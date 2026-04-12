import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import { haptic } from '@/auth/telegram'

type Draft = {
  name: string; race: string; gender: string; background: string
  alignment: string; speed: string
  personality_traits: string; ideals: string; bonds: string; flaws: string
  languages: string; general_proficiencies: string
}

export default function Identity() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [draft, setDraft] = useState<Draft | null>(null)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  useEffect(() => {
    if (char && !draft) {
      const personality = (char.personality as Record<string, string>) ?? {}
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

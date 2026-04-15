import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import DndButton from '@/components/DndButton'
import { haptic } from '@/auth/telegram'
import { useCharacterStore } from '@/store/characterStore'

export default function Settings() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const { locale, setLocale } = useCharacterStore()

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const updateMutation = useMutation({
    mutationFn: (settings: Record<string, unknown>) =>
      api.characters.update(charId, { settings }),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.success()
    },
  })

  const partyMutation = useMutation({
    mutationFn: (is_party_active: boolean) =>
      api.characters.update(charId, { is_party_active }),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      qc.invalidateQueries({ queryKey: ['characters'] })
      haptic.success()
    },
  })

  if (!char) return null

  const settings = (char.settings as Record<string, unknown>) ?? {}
  const slotsMode = (settings.spell_slots_mode as string) ?? 'auto'

  const toggleLanguage = () => {
    const newLang = locale === 'it' ? 'en' : 'it'
    setLocale(newLang)
    i18n.changeLanguage(newLang)
  }

  return (
    <Layout title={t('character.settings.title')} backTo={`/char/${charId}`}>
      <Card>
        <p className="font-medium mb-3">{t('character.settings.spell_slots_mode')}</p>
        <div className="flex gap-2">
          {(['auto', 'manual'] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => updateMutation.mutate({ ...settings, spell_slots_mode: mode })}
              className={`flex-1 py-2 rounded-xl text-sm font-medium transition-all
                ${slotsMode === mode
                  ? 'bg-dnd-gold text-dnd-bg'
                  : 'bg-dnd-surface'}`}
            >
              {t(`character.settings.mode_${mode}`)}
            </button>
          ))}
        </div>
      </Card>

      <Card>
        <div className="flex items-center justify-between">
          <p className="font-medium">{t('character.settings.language')}</p>
          <DndButton variant="secondary" onClick={toggleLanguage}>
            {locale === 'it' ? '🇮🇹 Italiano' : '🇬🇧 English'}
          </DndButton>
        </div>
      </Card>

      <Card>
        <div className="flex items-center justify-between gap-3">
          <div className="flex-1">
            <p className="font-medium">🎯 {t('character.settings.party_active')}</p>
            <p className="text-xs text-dnd-text-secondary mt-0.5">
              {t('character.settings.party_active_hint')}
            </p>
          </div>
          <button
            onClick={() => partyMutation.mutate(!char.is_party_active)}
            disabled={partyMutation.isPending}
            className={`relative w-12 h-6 rounded-full transition-colors shrink-0 disabled:opacity-40
              ${char.is_party_active ? 'bg-green-500' : 'bg-white/20'}`}
          >
            <span
              className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform
                ${char.is_party_active ? 'translate-x-6' : 'translate-x-0.5'}`}
            />
          </button>
        </div>
      </Card>
    </Layout>
  )
}

import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
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
                  ? 'bg-[var(--tg-theme-button-color)] text-[var(--tg-theme-button-text-color)]'
                  : 'bg-white/10'}`}
            >
              {t(`character.settings.mode_${mode}`)}
            </button>
          ))}
        </div>
      </Card>

      <Card>
        <div className="flex items-center justify-between">
          <p className="font-medium">{t('character.settings.language')}</p>
          <button
            onClick={toggleLanguage}
            className="px-4 py-2 rounded-xl bg-white/10 font-medium"
          >
            {locale === 'it' ? '🇮🇹 Italiano' : '🇬🇧 English'}
          </button>
        </div>
      </Card>
    </Layout>
  )
}

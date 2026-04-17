import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Settings2, Languages, Users, Sparkles, Gem, Dices } from 'lucide-react'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import SectionDivider from '@/components/ui/SectionDivider'
import { haptic } from '@/auth/telegram'
import { useCharacterStore } from '@/store/characterStore'
import { useDiceSettings } from '@/store/diceSettings'
import { spring } from '@/styles/motion'

export default function Settings() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const { locale, setLocale } = useCharacterStore()
  const animate3d = useDiceSettings((s) => s.animate3d)
  const setAnimate3d = useDiceSettings((s) => s.setAnimate3d)

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
      <SectionDivider icon={<Gem size={11} />} align="center">
        {t('character.settings.spell_slots_mode')}
      </SectionDivider>

      <Surface variant="elevated">
        <div className="flex items-start gap-3 mb-3">
          <Sparkles size={16} className="text-dnd-arcane-bright shrink-0 mt-0.5" />
          <p className="text-xs text-dnd-text-muted font-body italic flex-1">
            {t('character.settings.spell_slots_hint', { defaultValue: 'Auto = dedotto da classi e livello; Manual = controllo manuale' })}
          </p>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {(['auto', 'manual'] as const).map((mode) => (
            <m.button
              key={mode}
              onClick={() => updateMutation.mutate({ ...settings, spell_slots_mode: mode })}
              className={`min-h-[44px] rounded-xl font-cinzel text-xs uppercase tracking-widest transition-colors
                ${slotsMode === mode
                  ? 'bg-gradient-gold text-dnd-ink shadow-engrave'
                  : 'bg-dnd-surface border border-dnd-border text-dnd-text-muted'}`}
              whileTap={{ scale: 0.96 }}
              transition={spring.press}
            >
              {t(`character.settings.mode_${mode}`)}
            </m.button>
          ))}
        </div>
      </Surface>

      <SectionDivider icon={<Settings2 size={11} />} align="center">
        {t('character.settings.preferences', { defaultValue: 'Preferenze' })}
      </SectionDivider>

      <Surface variant="elevated">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Languages size={16} className="text-dnd-gold-bright" />
            <p className="font-display font-bold text-dnd-gold-bright">
              {t('character.settings.language')}
            </p>
          </div>
          <Button variant="secondary" size="sm" onClick={toggleLanguage}>
            {locale === 'it' ? '🇮🇹 Italiano' : '🇬🇧 English'}
          </Button>
        </div>
      </Surface>

      <Surface variant="elevated">
        <div className="flex items-center justify-between gap-3">
          <div className="flex-1 flex items-start gap-2">
            <Users size={16} className="text-[var(--dnd-emerald-bright)] shrink-0 mt-0.5" />
            <div>
              <p className="font-display font-bold text-dnd-gold-bright">
                {t('character.settings.party_active')}
              </p>
              <p className="text-xs text-dnd-text-muted mt-0.5 font-body italic">
                {t('character.settings.party_active_hint')}
              </p>
            </div>
          </div>
          <m.button
            onClick={() => partyMutation.mutate(!char.is_party_active)}
            disabled={partyMutation.isPending}
            className={`relative w-12 h-7 rounded-full transition-colors shrink-0 disabled:opacity-40 border
              ${char.is_party_active
                ? 'bg-gradient-to-r from-dnd-emerald-deep to-dnd-emerald-bright border-dnd-emerald-bright shadow-[0_0_8px_rgba(63,166,106,0.4)]'
                : 'bg-dnd-surface border-dnd-border'}`}
            whileTap={{ scale: 0.92 }}
          >
            <m.span
              className="absolute top-0.5 w-5 h-5 rounded-full bg-dnd-parchment shadow-parchment-md"
              animate={{ x: char.is_party_active ? 24 : 2 }}
              transition={spring.snappy}
            />
          </m.button>
        </div>
      </Surface>

      <Surface variant="elevated">
        <div className="flex items-center justify-between gap-3">
          <div className="flex-1 flex items-start gap-2">
            <Dices size={16} className="text-dnd-gold-bright shrink-0 mt-0.5" />
            <div>
              <p className="font-display font-bold text-dnd-gold-bright">
                {t('character.settings.dice_3d')}
              </p>
              <p className="text-xs text-dnd-text-muted mt-0.5 font-body italic">
                {t('character.settings.dice_3d_hint')}
              </p>
            </div>
          </div>
          <m.button
            onClick={() => {
              setAnimate3d(!animate3d)
              haptic.light()
            }}
            className={`relative w-12 h-7 rounded-full transition-colors shrink-0 border
              ${animate3d
                ? 'bg-gradient-to-r from-dnd-gold-dim to-dnd-gold-bright border-dnd-gold-bright shadow-[0_0_8px_rgba(212,170,90,0.4)]'
                : 'bg-dnd-surface border-dnd-border'}`}
            whileTap={{ scale: 0.92 }}
          >
            <m.span
              className="absolute top-0.5 w-5 h-5 rounded-full bg-dnd-parchment shadow-parchment-md"
              animate={{ x: animate3d ? 24 : 2 }}
              transition={spring.snappy}
            />
          </m.button>
        </div>
      </Surface>
    </Layout>
  )
}

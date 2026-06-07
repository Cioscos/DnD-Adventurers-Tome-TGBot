import { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { ChevronLeft, Settings } from 'lucide-react'
import { GiSparkles } from 'react-icons/gi'
import { api } from '@/api/client'
import { spring } from '@/styles/motion'
import { haptic } from '@/auth/telegram'
import Skeleton from '@/components/ui/Skeleton'
import InSessionBanner from '@/components/ui/InSessionBanner'
import { useCharacterStore } from '@/store/characterStore'
import CharacterSwiper from '@/components/character/CharacterSwiper'
import HeroScreen from '@/pages/character/HeroScreen'
import EquipmentScreen from '@/pages/character/EquipmentScreen'
import MenuScreen from '@/pages/character/MenuScreen'

export default function CharacterMain() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const navigate = useNavigate()
  const { t } = useTranslation()
  const qc = useQueryClient()
  const setActiveCharId = useCharacterStore((s) => s.setActiveCharId)

  useEffect(() => {
    if (!Number.isNaN(charId)) setActiveCharId(charId)
  }, [charId, setActiveCharId])

  const { data: char, isLoading, isError } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
    enabled: !!charId,
  })

  const inspirationMutation = useMutation({
    mutationFn: (value: boolean) => api.characters.updateInspiration(charId, value),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.light()
    },
  })

  if (isLoading) {
    return (
      <div className="min-h-screen p-4 space-y-4 pb-safe pt-safe">
        <Skeleton.Line width="180px" height="28px" />
        <Skeleton.Rect height="200px" />
        <Skeleton.Rect height="72px" delay={100} />
        <Skeleton.Rect height="240px" delay={200} />
      </div>
    )
  }

  if (isError || !char) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4 p-4">
        <p className="text-[var(--dnd-crimson-bright)] font-body">{t('common.error')}</p>
        <button onClick={() => navigate('/')} className="underline text-dnd-gold font-cinzel">
          {t('common.back')}
        </button>
      </div>
    )
  }

  return (
    <div
      className="w-full flex flex-col"
      style={{ height: 'var(--tg-vh, 100vh)' }}
    >
      <m.header
        className="shrink-0 z-20 flex items-center gap-2 px-4 py-3 pt-safe
                   bg-dnd-surface-raised border-b border-dnd-gold-dim/40 shadow-parchment-md"
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={spring.drift}
      >
        <m.button
          onClick={() => navigate('/')}
          className="w-11 h-11 flex items-center justify-center rounded-full bg-dnd-surface border border-dnd-gold-dim/30"
          whileTap={{ scale: 0.9 }}
          aria-label={t('common.back')}
        >
          <ChevronLeft size={20} className="text-dnd-gold-bright" />
        </m.button>

        <h1 className="text-xl font-display font-bold text-dnd-gold-bright truncate flex-1 flex items-center gap-2 min-w-0"
            style={{ textShadow: '0 1px 4px var(--dnd-gold-glow)' }}>
          <span className="truncate">{char.name}</span>
          {char.concentrating_spell_id && (
            <m.button
              type="button"
              onClick={() => {
                haptic.light()
                navigate(`/char/${charId}/spells?focus=${char.concentrating_spell_id}`)
              }}
              whileTap={{ scale: 0.9 }}
              title={t('character.spells.concentration_active', { defaultValue: 'Concentrazione attiva' })}
              aria-label={t('character.spells.concentration_active', { defaultValue: 'Concentrazione attiva' })}
              className="shrink-0 inline-flex items-center justify-center w-6 h-6 rounded-full bg-[var(--dnd-arcane-deep)]/50 border border-dnd-arcane-bright text-dnd-arcane-bright font-cinzel font-black text-[10px] shadow-halo-arcane animate-pulse"
            >
              C
            </m.button>
          )}
        </h1>

        <m.button
          onClick={() => inspirationMutation.mutate(!char.heroic_inspiration)}
          title={char.heroic_inspiration
            ? t('character.inspiration.tap_to_spend')
            : t('character.inspiration.tap_to_grant')}
          className={`relative h-11 px-2.5 flex items-center justify-center gap-1.5 rounded-full transition-all
            ${char.heroic_inspiration
              ? 'bg-dnd-gold/20 border border-dnd-gold shadow-halo-gold'
              : 'bg-dnd-surface border border-dnd-gold-dim/60'}`}
          whileTap={{ scale: 0.9 }}
          aria-label={t('character.inspiration.aria')}
        >
          <GiSparkles
            size={16}
            className={char.heroic_inspiration ? 'text-dnd-gold-bright' : 'text-dnd-gold-dim'}
          />
          <span
            className={`text-[10px] font-cinzel font-bold uppercase tracking-wider leading-none ${
              char.heroic_inspiration ? 'text-dnd-gold-bright' : 'text-dnd-text-muted'
            }`}
          >
            {char.heroic_inspiration ? t('character.inspiration.on') : t('character.inspiration.off')}
          </span>
        </m.button>

        <m.button
          onClick={() => navigate(`/char/${charId}/settings`)}
          className="w-11 h-11 flex items-center justify-center rounded-full bg-dnd-surface border border-dnd-gold-dim/30"
          whileTap={{ scale: 0.9 }}
          aria-label={t('character.menu.settings')}
        >
          <Settings size={18} className="text-dnd-gold-bright" />
        </m.button>
      </m.header>

      <InSessionBanner charId={charId} />

      <CharacterSwiper
        hero={<HeroScreen char={char} />}
        equipment={<EquipmentScreen char={char} />}
        menu={<MenuScreen charId={charId} />}
      />
    </div>
  )
}

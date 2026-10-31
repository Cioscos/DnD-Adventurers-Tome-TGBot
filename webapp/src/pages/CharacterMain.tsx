import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { ChevronLeft, RefreshCw, Search, Settings, UserX } from 'lucide-react'
import { GiSparkles } from 'react-icons/gi'
import { api, ApiError } from '@/api/client'
import { spring } from '@/styles/motion'
import { haptic } from '@/auth/telegram'
import EmptyState from '@/components/ui/EmptyState'
import Skeleton from '@/components/ui/Skeleton'
import InSessionBanner from '@/components/ui/InSessionBanner'
import OfflineNotice from '@/components/ui/OfflineNotice'
import Pressable from '@/components/ui/Pressable'
import PageHelp from '@/components/PageHelp'
import { useCharacterStore } from '@/store/characterStore'
import CharacterSwiper from '@/components/character/CharacterSwiper'
import SearchOverlay from '@/components/SearchOverlay'
import HeroScreen from '@/pages/character/HeroScreen'
import EquipmentScreen from '@/pages/character/EquipmentScreen'
import MenuScreen from '@/pages/character/MenuScreen'
import { usePageBack } from '@/hooks/useOverlayDismiss'
import { isConcentrating } from '@/lib/concentration'

export default function CharacterMain() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const navigate = useNavigate()
  const { t } = useTranslation()
  const qc = useQueryClient()
  const setActiveCharId = useCharacterStore((s) => s.setActiveCharId)
  const [searchOpen, setSearchOpen] = useState(false)
  // Back hardware/BackButton di Telegram: dal hub si torna alla lista personaggi.
  usePageBack(() => navigate('/'))

  useEffect(() => {
    if (!Number.isNaN(charId)) setActiveCharId(charId)
  }, [charId, setActiveCharId])

  // Stessa politica del guard condiviso nel Layout (audit FE 2026-06-11, #10):
  // 404/403 non si ritentano, gli altri errori sì.
  const charQuery = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
    enabled: !!charId,
    retry: (failureCount, err) =>
      !(err instanceof ApiError && (err.status === 404 || err.status === 403)) && failureCount < 3,
  })
  const { data: char, isLoading, error, refetch } = charQuery
  const charNotFound = error instanceof ApiError
    && (error.status === 404 || error.status === 403)

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

  // Un refetch fallito con una copia in cache non è un errore da schermata piena:
  // la scheda resta, segnalata da OfflineNotice. Il 404/403 invece la sconfessa.
  if (charNotFound || !char) {
    return (
      <div className="min-h-screen flex flex-col justify-center p-4 pt-safe pb-safe">
        {charNotFound ? (
          <EmptyState
            icon={<UserX size={28} />}
            title={t('layout.char_error.not_found')}
            hint={t('layout.char_error.not_found_hint')}
            action={{
              label: t('layout.char_error.back_to_list'),
              onClick: () => navigate('/'),
            }}
          />
        ) : (
          <EmptyState
            icon={<RefreshCw size={28} />}
            title={t('layout.char_error.generic')}
            action={{
              label: t('layout.char_error.retry'),
              onClick: () => refetch(),
            }}
          />
        )}
      </div>
    )
  }

  return (
    <div
      className="w-full flex flex-col"
      style={{ height: 'var(--tg-vh, 100vh)' }}
    >
      {/* Audit FE 2026-06-11, #V1: l'header è l'unica riga dove vive il nome —
          ogni px conta. Controlli a 40px (≥40 ok per azioni non distruttive),
          gap e padding compatti, pill ispirazione impilato (icona sopra,
          stato sotto) come il badge peso della hero card. */}
      <m.header
        className="shrink-0 z-20 flex items-center gap-1.5 px-3 py-3 pt-safe
                   bg-dnd-surface-raised border-b border-dnd-gold-dim/40 shadow-parchment-md"
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={spring.drift}
      >
        <Pressable
          onClick={() => navigate('/')}
          className="w-11 h-11 shrink-0 flex items-center justify-center rounded-full bg-dnd-surface border border-dnd-gold-dim/30"
          whileTap={{ scale: 0.9 }}
          aria-label={t('common.back')}
        >
          <ChevronLeft size={20} className="text-dnd-gold-bright" />
        </Pressable>

        {/* Sotto 375px le tre azioni lasciano ~100px al nome: due righe più piccole invece di "Kael Vent…" */}
        <h1 className="text-xl max-xs:text-base max-xs:leading-tight font-display font-bold text-dnd-gold-bright truncate max-xs:whitespace-normal flex-1 flex items-center gap-2 min-w-0"
            style={{ textShadow: '0 1px 4px var(--dnd-gold-glow)' }}>
          <span className="truncate max-xs:whitespace-normal max-xs:line-clamp-2 max-xs:break-words">{char.name}</span>
          {isConcentrating(char) && (
            <Pressable
              type="button"
              onClick={() => {
                haptic.light()
                navigate(`/char/${charId}/spells${char.concentrating_spell_id ? `?focus=${char.concentrating_spell_id}` : ''}`)
              }}
              whileTap={{ scale: 0.9 }}
              title={t('character.spells.concentration_active', { defaultValue: 'Concentrazione attiva' })}
              aria-label={t('character.spells.concentration_active', { defaultValue: 'Concentrazione attiva' })}
              className="shrink-0 inline-flex items-center justify-center w-6 h-6 rounded-full bg-dnd-arcane-deep/50 border border-dnd-arcane-bright text-dnd-arcane-bright font-cinzel font-black text-xs shadow-halo-arcane animate-pulse"
            >
              C
            </Pressable>
          )}
        </h1>

        <Pressable
          onClick={() => {
            haptic.light()
            setSearchOpen(true)
          }}
          className="w-10 h-10 shrink-0 flex items-center justify-center rounded-full bg-dnd-surface border border-dnd-gold-dim/30"
          whileTap={{ scale: 0.9 }}
          aria-label={t('character.search.title')}
        >
          <Search size={18} className="text-dnd-gold-bright" />
        </Pressable>

        <Pressable
          onClick={() => inspirationMutation.mutate(!char.heroic_inspiration)}
          pending={inspirationMutation.isPending}
          title={char.heroic_inspiration
            ? t('character.inspiration.tap_to_spend')
            : t('character.inspiration.tap_to_grant')}
          className={`relative h-10 min-w-[42px] shrink-0 px-1.5 flex flex-col items-center justify-center gap-0.5 rounded-xl transition-all
            ${char.heroic_inspiration
              ? 'bg-dnd-gold/20 border border-dnd-gold shadow-halo-gold'
              : 'bg-dnd-surface border border-dnd-gold-dim/60'}`}
          whileTap={{ scale: 0.9 }}
          aria-label={t('character.inspiration.aria')}
        >
          <GiSparkles
            size={14}
            className={char.heroic_inspiration ? 'text-dnd-gold-bright' : 'text-dnd-gold-dim'}
          />
          <span
            className={`text-xs font-cinzel font-bold uppercase tracking-wider leading-none ${
              char.heroic_inspiration ? 'text-dnd-gold-bright' : 'text-dnd-text-muted'
            }`}
          >
            {char.heroic_inspiration ? t('character.inspiration.on') : t('character.inspiration.off')}
          </span>
        </Pressable>

        <Pressable
          onClick={() => navigate(`/char/${charId}/settings`)}
          className="w-10 h-10 shrink-0 flex items-center justify-center rounded-full bg-dnd-surface border border-dnd-gold-dim/30"
          whileTap={{ scale: 0.9 }}
          aria-label={t('character.menu.settings')}
        >
          <Settings size={18} className="text-dnd-gold-bright" />
        </Pressable>
        <PageHelp helpKey="character" title={char.name} className="w-10 h-10" />
      </m.header>

      <InSessionBanner charId={charId} />

      <OfflineNotice query={charQuery} className="shrink-0 mx-3 mt-2" />

      <CharacterSwiper
        hero={<HeroScreen char={char} />}
        equipment={<EquipmentScreen char={char} />}
        menu={<MenuScreen char={char} />}
      />

      <SearchOverlay char={char} open={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  )
}

import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { SearchX, Wand2, Backpack, Sparkles, StickyNote } from 'lucide-react'
import { GiCrystalBall } from 'react-icons/gi'
import Sheet from '@/components/ui/Sheet'
import Input from '@/components/ui/Input'
import Pressable from '@/components/ui/Pressable'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import {
  searchCharacter,
  MIN_QUERY_LENGTH,
  type SearchResult,
  type SearchResultType,
} from '@/lib/characterSearch'
import type { CharacterFull } from '@/types'

const TYPE_ORDER: readonly SearchResultType[] = ['spell', 'item', 'ability', 'resource', 'note']

const TYPE_ICONS: Record<SearchResultType, React.ReactNode> = {
  spell: <Wand2 size={14} />,
  item: <Backpack size={14} />,
  ability: <Sparkles size={14} />,
  // Stessa icona di CustomResourceCounter: vocabolario coerente.
  resource: <GiCrystalBall size={14} />,
  note: <StickyNote size={14} />,
}

interface SearchOverlayProps {
  char: CharacterFull
  open: boolean
  onClose: () => void
}

export default function SearchOverlay({ char, open, onClose }: SearchOverlayProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')

  // Le risorse homebrew non sono in CharacterFull: stessa query key della
  // pagina Abilità (dedupe in cache), fetch solo a overlay aperto.
  const { data: resources } = useQuery({
    queryKey: ['homebrew-resources', char.id],
    queryFn: () => api.homebrew.listResources(char.id),
    enabled: open,
  })

  const results = useMemo(
    () => searchCharacter(char, query, resources ?? []),
    [char, query, resources],
  )
  const grouped = useMemo(
    () =>
      TYPE_ORDER.flatMap((type) => {
        const ofType = results.filter((r) => r.type === type)
        return ofType.length > 0 ? [{ type, results: ofType }] : []
      }),
    [results],
  )

  const subtitle = (r: SearchResult): string | null => {
    if (r.meta?.spellLevel !== undefined) {
      return r.meta.spellLevel === 0
        ? t('character.search.cantrip')
        : t('character.search.spell_level', { level: r.meta.spellLevel })
    }
    if (r.meta?.quantity !== undefined) return `×${r.meta.quantity}`
    if (r.meta?.resourceCurrent !== undefined) {
      return `${r.meta.resourceCurrent}/${r.meta.resourceMax}`
    }
    return null
  }

  const openResult = (r: SearchResult) => {
    haptic.light()
    onClose()
    setQuery('')
    navigate(r.route)
  }

  const close = () => {
    setQuery('')
    onClose()
  }

  const tooShort = query.trim().length < MIN_QUERY_LENGTH

  return (
    <Sheet open={open} onClose={close} title={t('character.search.title')}>
      <div className="space-y-3">
        <Input
          value={query}
          onChange={setQuery}
          placeholder={t('character.search.placeholder')}
          inputMode="search"
        />

        {tooShort ? (
          <p className="text-xs text-dnd-text-muted font-body italic text-center py-4">
            {t('character.search.hint')}
          </p>
        ) : grouped.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-6 text-dnd-text-muted">
            <SearchX size={24} />
            <p className="text-sm font-body italic">{t('character.search.no_results')}</p>
          </div>
        ) : (
          <div className="space-y-3 max-h-[55vh] overflow-y-auto scrollbar-hide">
            {grouped.map(({ type, results: ofType }) => (
              <div key={type}>
                <p className="font-cinzel text-[10px] uppercase tracking-widest text-dnd-gold-dim mb-1 px-1">
                  {t(`character.search.type_${type}`)}
                </p>
                <div className="space-y-1">
                  {ofType.map((r) => (
                    <Pressable
                      key={r.id}
                      type="button"
                      onClick={() => openResult(r)}
                      className="w-full min-h-[44px] flex items-center gap-2 px-3 py-2 rounded-xl
                                 bg-dnd-surface border border-dnd-border text-left"
                    >
                      <span className="text-dnd-gold shrink-0">{TYPE_ICONS[r.type]}</span>
                      <span className="flex-1 min-w-0 truncate text-sm text-dnd-text font-body">
                        {r.title}
                      </span>
                      {subtitle(r) && (
                        <span className="shrink-0 text-xs text-dnd-text-muted tabular-nums">
                          {subtitle(r)}
                        </span>
                      )}
                    </Pressable>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Sheet>
  )
}

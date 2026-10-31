import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Search } from 'lucide-react'
import Sheet from '@/components/ui/Sheet'
import Input from '@/components/ui/Input'
import Pressable from '@/components/ui/Pressable'
import Button from '@/components/ui/Button'
import {
  loadCatalog, localized, searchCatalog,
  type CatalogEntry, type CatalogKind, type Lang, type SpellEntry,
} from '@/lib/srd/catalog'

interface CatalogPickerProps<K extends CatalogKind> {
  kind: K
  onPick: (entry: CatalogEntry<K>) => void
  onClose: () => void
  filters?: (entry: CatalogEntry<K>) => boolean
}

// Progressive rendering instead of a virtual list: the 800-row monster catalogue
// stays light because only PAGE rows are mounted until the user asks for more.
const PAGE = 100

export default function CatalogPicker<K extends CatalogKind>({
  kind, onPick, onClose, filters,
}: CatalogPickerProps<K>) {
  const { t, i18n } = useTranslation()
  const lang: Lang = i18n.language?.startsWith('en') ? 'en' : 'it'
  const [entries, setEntries] = useState<CatalogEntry<K>[]>([])
  const [loaded, setLoaded] = useState(false)
  const [query, setQuery] = useState('')
  const [limit, setLimit] = useState(PAGE)

  useEffect(() => {
    let alive = true
    // A failed chunk (stale client after a deploy) shows the empty state instead of a blank sheet.
    loadCatalog(kind)
      .then((e) => { if (alive) setEntries(e) })
      .catch(() => {})
      .finally(() => { if (alive) setLoaded(true) })
    return () => { alive = false }
  }, [kind])

  const rows = useMemo(() => {
    const base = filters ? entries.filter(filters) : entries
    return searchCatalog(base, query, lang)
  }, [entries, filters, query, lang])

  return (
    <Sheet open onClose={onClose} title={t('catalog.title')} zClassName="z-[60]" className="h-[90dvh]">
      <div className="p-5 space-y-3">
        <Input
          type="search"
          value={query}
          onChange={(v) => { setQuery(v); setLimit(PAGE) }}
          placeholder={t('catalog.search')}
          leadingIcon={<Search size={16} />}
          enterKeyHint="search"
          autoFocus
        />
        {loaded && rows.length === 0 && (
          <p className="text-sm text-dnd-text-muted font-body italic text-center py-6">{t('catalog.empty')}</p>
        )}
        <ul className="space-y-1.5">
          {rows.slice(0, limit).map((e) => {
            const name = localized(e.name, lang)
            const spell = kind === 'spells' ? (e as unknown as SpellEntry) : null
            return (
              <li key={e.index}>
                <Pressable
                  onClick={() => onPick(e)}
                  className="w-full min-h-[44px] px-3 py-2 rounded-xl bg-dnd-surface-raised border border-dnd-border text-left flex items-center gap-2"
                >
                  <span className="flex-1 min-w-0">
                    <span className="block font-body text-sm text-dnd-text break-words">{name.text}</span>
                    {spell && (
                      <span className="block text-xs text-dnd-text-muted">
                        {spell.level === 0 ? t('character.spells.cantrip') : t('character.spells.filters.level_n', { level: spell.level })}
                        {' · '}{t(`character.spells.schools.${spell.school}`, { defaultValue: spell.school })}
                      </span>
                    )}
                  </span>
                  {name.fallback && (
                    <span className="shrink-0 text-xs font-bold px-1.5 py-0.5 rounded bg-dnd-surface border border-dnd-border text-dnd-text-muted">
                      {t('catalog.en_badge')}
                    </span>
                  )}
                </Pressable>
              </li>
            )
          })}
        </ul>
        {rows.length > limit && (
          <Button variant="secondary" fullWidth onClick={() => setLimit((l) => l + PAGE)}>
            {t('catalog.show_more', { count: rows.length - limit })}
          </Button>
        )}
      </div>
    </Sheet>
  )
}

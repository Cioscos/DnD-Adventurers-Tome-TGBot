import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { Sparkles, Wrench, Bug, ScrollText } from 'lucide-react'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Pressable from '@/components/ui/Pressable'
import EmptyState from '@/components/ui/EmptyState'
import ExpandChevron from '@/components/ui/ExpandChevron'
import { haptic } from '@/auth/telegram'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import { changelog, localizedLines, localizedTitle, type ChangelogEntry } from '@/lib/version'

type CategoryKey = 'added' | 'improved' | 'fixed'

const CATEGORIES: { key: CategoryKey; Icon: typeof Sparkles }[] = [
  { key: 'added', Icon: Sparkles },
  { key: 'improved', Icon: Wrench },
  { key: 'fixed', Icon: Bug },
]

function EntryCard({ entry, isCurrent, defaultOpen }: { entry: ChangelogEntry; isCurrent: boolean; defaultOpen: boolean }) {
  const { t, i18n } = useTranslation()
  const reduceMotion = useReducedMotion()
  const [open, setOpen] = useState(defaultOpen)

  const lang = i18n.language
  const title = localizedTitle(entry, lang)

  const sections = CATEGORIES
    .map(({ key, Icon }) => ({ key, Icon, lines: localizedLines(entry[key], lang) }))
    .filter((s) => s.lines.length > 0)

  return (
    <Surface variant="elevated">
      <Pressable
        type="button"
        onClick={() => { haptic.light(); setOpen((o) => !o) }}
        className="w-full flex items-center gap-3 text-left"
        aria-expanded={open}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono tabular-nums text-base font-semibold text-dnd-gold-bright">
              v{entry.version}
            </span>
            {isCurrent && (
              <span className="text-[10px] font-cinzel uppercase tracking-wider px-2 py-0.5 rounded-full bg-dnd-gold/20 text-dnd-gold-bright border border-dnd-gold/40 shrink-0">
                {t('changelog.current')}
              </span>
            )}
          </div>
          {title && (
            <p className="mt-0.5 font-display text-dnd-text break-words">{title}</p>
          )}
          <p className="mt-0.5 text-xs font-mono tabular-nums text-dnd-text-faint">{entry.date}</p>
        </div>
        <ExpandChevron open={open} size={20} className="text-dnd-gold-dim" />
      </Pressable>

      <AnimatePresence initial={false}>
        {open && (
          <m.div
            key="body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: reduceMotion ? 0 : 0.22, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden"
          >
            <div className="pt-4 space-y-4">
              {sections.map(({ key, Icon, lines }) => (
                <div key={key}>
                  <div className="flex items-center gap-2 mb-1.5">
                    <Icon size={14} className="text-dnd-gold-dim shrink-0" />
                    <span className="text-[11px] font-cinzel uppercase tracking-widest text-dnd-gold-dim">
                      {t(`changelog.sections.${key}`)}
                    </span>
                  </div>
                  <ul className="space-y-1.5 pl-1">
                    {lines.map((line, i) => (
                      <li key={i} className="flex gap-2 text-sm font-body text-dnd-text leading-snug">
                        <span className="text-dnd-gold-dim/60 shrink-0 mt-0.5">◈</span>
                        <span className="min-w-0">{line}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </m.div>
        )}
      </AnimatePresence>
    </Surface>
  )
}

export default function Changelog() {
  const { t } = useTranslation()

  return (
    <Layout title={t('changelog.title')} backTo="/">
      {changelog.length === 0 ? (
        <EmptyState icon={<ScrollText size={32} />} title={t('changelog.empty')} />
      ) : (
        <div className="space-y-3">
          {changelog.map((entry, idx) => (
            <EntryCard key={entry.version} entry={entry} isCurrent={idx === 0} defaultOpen={idx === 0} />
          ))}
        </div>
      )}
    </Layout>
  )
}

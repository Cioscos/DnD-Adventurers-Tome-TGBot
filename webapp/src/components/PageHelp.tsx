import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { CircleHelp } from 'lucide-react'
import Sheet from '@/components/ui/Sheet'
import Pressable from '@/components/ui/Pressable'

interface HelpContent {
  summary: string
  sections: { title: string; items: string[] }[]
}

/** Pulsante "?" dell'header: apre la guida della pagina da `help.<helpKey>` (it/en). */
export default function PageHelp({ helpKey, title, className = 'w-11 h-11' }: { helpKey: string; title: string; className?: string }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  // Guida assente → t restituisce la chiave (stringa), non l'oggetto: niente pulsante.
  const help = t(`help.${helpKey}`, { returnObjects: true }) as HelpContent | string
  if (typeof help !== 'object') return null
  const content = open ? help : null

  return (
    <>
      <Pressable
        onClick={() => setOpen(true)}
        className={`${className} shrink-0 flex items-center justify-center rounded-full bg-dnd-surface border border-dnd-gold-dim/30`}
        aria-label={t('help.open')}
        whileTap={{ scale: 0.9 }}
        whileHover={{ boxShadow: 'var(--halo-gold)' }}
      >
        <CircleHelp size={20} className="text-dnd-gold-bright" />
      </Pressable>
      <Sheet open={open} onClose={() => setOpen(false)} title={t('help.title', { page: title })}>
        {content && (
          <div className="px-5 py-4 space-y-5 font-body text-dnd-text">
            <p className="text-sm leading-relaxed text-dnd-text-muted">{content.summary}</p>
            {content.sections.map((s) => (
              <section key={s.title} className="space-y-2">
                <h3 className="font-display font-bold text-dnd-gold-bright">{s.title}</h3>
                <ul className="list-disc pl-5 space-y-1.5 text-sm leading-relaxed marker:text-dnd-gold-dim">
                  {s.items.map((item) => <li key={item}>{item}</li>)}
                </ul>
              </section>
            ))}
          </div>
        )}
      </Sheet>
    </>
  )
}

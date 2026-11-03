import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Skeleton from '@/components/ui/Skeleton'
import { api } from '@/api/client'
import { renderInlineMarkdown } from '@/lib/inlineMarkdown'
import type { LoreRead } from '@/types'

interface Props {
  open: boolean
  campaignId: number
  /** null con open=true: voce non trovata (nascosta o eliminata) oppure ancora in caricamento. */
  lore: LoreRead | null
  loading?: boolean
  onClose: () => void
}

export default function LoreViewModal({ open, campaignId, lore, loading = false, onClose }: Props) {
  const { t } = useTranslation()
  return (
    <Sheet open={open} onClose={onClose} title={lore?.title ?? t('campaign.lore.title')}>
      <div className="p-5 space-y-4">
        {!lore ? (
          loading ? (
            <Skeleton.Rect height="96px" />
          ) : (
            <p className="text-sm text-dnd-text-muted font-body italic text-center">{t('campaign.lore.unavailable')}</p>
          )
        ) : (
          <>
            {lore.tags.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {lore.tags.map((tag) => (
                  <span
                    key={tag}
                    className="text-xs font-cinzel uppercase tracking-wider px-1.5 py-px rounded-full bg-dnd-chip-bg text-dnd-gold-dim border border-dnd-border"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}
            {lore.has_image && (
              <img
                src={api.lore.imageUrl(campaignId, lore.id)}
                alt={lore.title}
                className="w-full max-h-[50vh] object-contain rounded-lg border border-dnd-border"
              />
            )}
            {lore.has_audio && <audio controls className="w-full" src={api.lore.audioUrl(campaignId, lore.id)} />}
            <div className="text-sm text-dnd-text whitespace-pre-wrap break-words leading-relaxed">
              {renderInlineMarkdown(lore.body)}
            </div>
          </>
        )}
      </div>
    </Sheet>
  )
}

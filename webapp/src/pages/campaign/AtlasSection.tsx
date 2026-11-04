import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Plus } from 'lucide-react'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import SectionDivider from '@/components/ui/SectionDivider'
import Skeleton from '@/components/ui/Skeleton'
import MapUploadSheet from '@/pages/campaign/MapUploadSheet'
import { api } from '@/api/client'

/** Atlante della campagna: elenco delle mappe; il master vede anche quelle nascoste e può caricarne. */
export default function AtlasSection({ campaignId, isGm }: { campaignId: number; isGm: boolean }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [uploading, setUploading] = useState(false)
  const { data: maps = [], isLoading } = useQuery({
    queryKey: ['atlas-maps', campaignId],
    queryFn: () => api.atlas.maps(campaignId),
  })

  return (
    <div id="atlas">
      <SectionDivider>{t('atlas.title')}</SectionDivider>
      {isGm && (
        <div className="mb-2">
          <Button variant="secondary" size="sm" icon={<Plus size={14} />} onClick={() => setUploading(true)}>
            {t('atlas.upload')}
          </Button>
        </div>
      )}
      {isLoading ? (
        <Skeleton.Rect height="72px" />
      ) : maps.length === 0 ? (
        <p className="text-sm text-dnd-text-muted italic">{t(isGm ? 'atlas.empty_gm' : 'atlas.empty_player')}</p>
      ) : (
        <div className="space-y-2" data-testid="atlas-list">
          {maps.map((m) => (
            <div key={m.id} className="border-b border-dnd-border/60 px-1 py-2">
              <Pressable onClick={() => navigate(`/campaign/${campaignId}/atlas/${m.id}`)} className="block w-full min-h-[44px] text-left">
                <p className="font-body font-semibold text-sm text-dnd-text break-words">
                  {m.name}
                  {isGm && !m.revealed && (
                    <span className="ml-2 align-middle inline-block rounded-full border border-dnd-border-strong px-2 py-0.5 text-xs font-cinzel uppercase tracking-wider text-dnd-text-muted">
                      {t('atlas.hidden')}
                    </span>
                  )}
                </p>
                <p className="text-xs text-dnd-text-muted font-body">{t('atlas.markers', { count: m.marker_count })}</p>
              </Pressable>
            </div>
          ))}
        </div>
      )}
      <MapUploadSheet open={uploading} campaignId={campaignId} onClose={() => setUploading(false)} />
    </div>
  )
}

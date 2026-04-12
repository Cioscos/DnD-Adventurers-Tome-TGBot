import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import { haptic } from '@/auth/telegram'

export default function Maps() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null)
  const [expanded, setExpanded] = useState<number | null>(null)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const deleteMutation = useMutation({
    mutationFn: (mapId: number) => api.maps.remove(charId, mapId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      setDeleteTarget(null)
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  if (!char) return null

  const maps = char.maps ?? []

  // Group by zone
  const zones = maps.reduce<Record<string, typeof maps>>((acc, m) => {
    if (!acc[m.zone_name]) acc[m.zone_name] = []
    acc[m.zone_name].push(m)
    return acc
  }, {})

  return (
    <Layout title={t('character.maps.title')} backTo={`/char/${charId}`}>
      <Card>
        <p className="text-sm text-[var(--tg-theme-hint-color)] text-center">
          🗺️ {t('character.maps.upload_hint')}
        </p>
      </Card>

      {maps.length === 0 ? (
        <Card>
          <p className="text-center text-[var(--tg-theme-hint-color)]">{t('common.none')}</p>
        </Card>
      ) : (
        Object.entries(zones).map(([zone, zoneMaps]) => (
          <div key={zone}>
            <p className="text-sm font-semibold text-[var(--tg-theme-hint-color)] px-1 mb-1">
              📍 {zone}
            </p>
            {zoneMaps.map((m) => (
              <Card key={m.id} className="mb-2">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">{m.file_type.toUpperCase()}</span>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setExpanded(expanded === m.id ? null : m.id)}
                      className="text-xs text-[var(--tg-theme-link-color)]"
                    >
                      {expanded === m.id ? t('common.close') : 'Apri'}
                    </button>
                    <button
                      onClick={() => setDeleteTarget(m.id)}
                      className="text-xs text-red-400"
                    >
                      {t('common.delete')}
                    </button>
                  </div>
                </div>

                {expanded === m.id && (
                  <img
                    src={api.maps.fileUrl(charId, m.id)}
                    alt={zone}
                    className="w-full rounded-lg"
                    loading="lazy"
                  />
                )}
              </Card>
            ))}
          </div>
        ))
      )}

      {deleteTarget !== null && (
        <div className="fixed inset-0 bg-black/60 flex items-end z-50 p-4">
          <Card className="w-full">
            <p className="text-sm text-center mb-3">
              {t('character.maps.delete_confirm', {
                zone: maps.find((m) => m.id === deleteTarget)?.zone_name ?? '',
              })}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => deleteMutation.mutate(deleteTarget)}
                className="flex-1 py-2 rounded-xl bg-red-500/80 text-white font-medium"
              >
                {t('common.delete')}
              </button>
              <button
                onClick={() => setDeleteTarget(null)}
                className="flex-1 py-2 rounded-xl bg-white/10 font-medium"
              >
                {t('common.cancel')}
              </button>
            </div>
          </Card>
        </div>
      )}
    </Layout>
  )
}

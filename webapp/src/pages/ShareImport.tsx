import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Gift, Mic, UserPlus, Users } from 'lucide-react'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import Skeleton from '@/components/ui/Skeleton'
import { api, ApiError } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { useToast } from '@/hooks/useToast'
import { useCharacterStore } from '@/store/characterStore'

/** Landing del deep link shr_<token>: anteprima + scelta del PG di destinazione. */
export default function ShareImport() {
  const { token = '' } = useParams<{ token: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const lastCharId = useCharacterStore((s) => s.lastCharId)
  const [selectedCharId, setSelectedCharId] = useState<number | null>(null)

  const shareQuery = useQuery({
    queryKey: ['share-preview', token],
    queryFn: () => api.share.get(token),
    retry: false,
  })

  const { data: characters = [], isLoading: charsLoading } = useQuery({
    queryKey: ['characters'],
    queryFn: () => api.characters.list(),
  })

  // Preselezione: scelta esplicita > ultimo PG usato (se esiste ancora) > unico PG
  const effectiveCharId =
    selectedCharId
    ?? (characters.some((c) => c.id === lastCharId) ? lastCharId : null)
    ?? (characters.length === 1 ? characters[0].id : null)

  const importMutation = useMutation({
    mutationFn: () => api.share.import(token, effectiveCharId!),
    onSuccess: (res) => {
      haptic.success()
      qc.invalidateQueries({ queryKey: ['character', res.char_id] })
      qc.invalidateQueries({ queryKey: ['notes', res.char_id] })
      toast.success(t('share.import.success', { title: res.title }))
      navigate(
        res.kind === 'item' ? `/char/${res.char_id}/inventory` : `/char/${res.char_id}/notes`,
        { replace: true },
      )
    },
    onError: (err) => {
      haptic.error()
      const gone = err instanceof ApiError && err.status === 410
      toast.error(gone ? t('share.import.expired') : t('share.import.error'))
    },
  })

  if (shareQuery.isLoading || charsLoading) {
    return (
      <Layout title={t('share.import.title')} backTo="/">
        <Skeleton.Rect height="120px" />
      </Layout>
    )
  }

  // Scaduta / inesistente: stato dedicato, mai un errore generico — il
  // bottone nel messaggio Telegram resta per sempre.
  if (shareQuery.isError || !shareQuery.data) {
    const status = shareQuery.error instanceof ApiError ? shareQuery.error.status : 0
    return (
      <Layout title={t('share.import.title')} backTo="/">
        <Surface variant="ember" className="text-center space-y-3">
          <p className="text-dnd-text text-sm font-body">
            {status === 410 ? t('share.import.expired') : t('share.import.not_found')}
          </p>
          <Button variant="primary" fullWidth onClick={() => navigate('/', { replace: true })}>
            {t('share.import.go_home')}
          </Button>
        </Surface>
      </Layout>
    )
  }

  const preview = shareQuery.data
  const hasCharacters = characters.length > 0

  return (
    <Layout title={t('share.import.title')} backTo="/">
      <Surface variant="elevated">
        <div className="flex items-center gap-2 mb-2">
          {preview.is_voice ? (
            <Mic size={16} className="text-dnd-gold-bright shrink-0" />
          ) : (
            <Gift size={16} className="text-dnd-gold-bright shrink-0" />
          )}
          <p className="font-display font-bold text-dnd-gold-bright min-w-0 truncate">
            {preview.title}
          </p>
        </div>
        <p className="text-xs text-dnd-text-muted font-body italic mb-1">
          {t('share.import.from', { name: preview.sender_char_name })}
        </p>
        {preview.is_voice ? (
          <p className="text-sm text-dnd-text-muted font-body">
            {t('share.import.voice_note')}
          </p>
        ) : preview.description ? (
          <p className="text-sm text-dnd-text-muted font-body whitespace-pre-wrap line-clamp-4">
            {preview.description}
          </p>
        ) : null}
        {preview.kind === 'item' && (preview.quantity ?? 1) > 1 && (
          <p className="text-xs text-dnd-text-faint font-mono tabular-nums mt-1">
            ×{preview.quantity}
          </p>
        )}
      </Surface>

      <Surface variant="elevated">
        <div className="flex items-center gap-2 mb-3">
          <Users size={16} className="text-dnd-gold-bright" />
          <p className="font-display font-bold text-dnd-gold-bright text-sm">
            {t('share.import.pick_character')}
          </p>
        </div>

        {!hasCharacters ? (
          <div className="space-y-3">
            <p className="text-sm text-dnd-text-muted font-body italic">
              {t('share.import.needs_character')}
            </p>
            <Button
              variant="primary"
              fullWidth
              icon={<UserPlus size={16} />}
              onClick={() => navigate('/')}
            >
              {t('session.create_first_character')}
            </Button>
          </div>
        ) : (
          <div className="space-y-2">
            {characters.map((c) => (
              <Pressable
                key={c.id}
                onClick={() => setSelectedCharId(c.id)}
                className={`w-full text-left px-3 py-2.5 rounded-lg border transition-colors
                  ${effectiveCharId === c.id
                    ? 'bg-gradient-gold text-dnd-ink border-dnd-gold shadow-engrave'
                    : 'bg-dnd-surface border-dnd-border text-dnd-text hover:border-dnd-gold-dim'}`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-display font-bold">{c.name}</span>
                  <span className="text-xs opacity-80 font-body">
                    {c.class_summary || t('character.select.new')}
                  </span>
                </div>
              </Pressable>
            ))}
          </div>
        )}
      </Surface>

      {hasCharacters && (
        <Button
          variant="primary"
          size="lg"
          fullWidth
          disabled={effectiveCharId === null || importMutation.isPending}
          loading={importMutation.isPending}
          onClick={() => importMutation.mutate()}
        >
          {t('share.import.add_button', {
            name: characters.find((c) => c.id === effectiveCharId)?.name ?? '',
          })}
        </Button>
      )}
    </Layout>
  )
}

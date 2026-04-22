import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Hash, Users } from 'lucide-react'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import Skeleton from '@/components/ui/Skeleton'
import { api, ApiError } from '@/api/client'
import { haptic } from '@/auth/telegram'

export default function SessionJoin() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [code, setCode] = useState('')
  const [selectedCharId, setSelectedCharId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const { data: characters = [], isLoading } = useQuery({
    queryKey: ['characters'],
    queryFn: () => api.characters.list(),
  })

  const autoChar = useMemo(
    () => (characters.length === 1 ? characters[0] : null),
    [characters],
  )

  const effectiveCharId = selectedCharId ?? autoChar?.id ?? null

  const canJoin = code.trim().length === 6 && effectiveCharId !== null

  const joinMutation = useMutation({
    mutationFn: () => {
      if (!effectiveCharId) throw new Error('no-char')
      return api.sessions.join(code.trim().toUpperCase(), effectiveCharId)
    },
    onSuccess: (session) => {
      qc.setQueryData(['session-me'], session)
      haptic.success()
      navigate(`/session/${session.id}`)
    },
    onError: (err) => {
      haptic.error()
      if (err instanceof ApiError) {
        setError(err.detail)
      } else {
        setError(t('common.error'))
      }
    },
  })

  const submit = () => {
    setError(null)
    if (!canJoin) return  // UI already prevents this via disabled button
    joinMutation.mutate()
  }

  if (isLoading) {
    return (
      <Layout title={t('session.join_player')} backTo="/session">
        <Skeleton.Rect height="120px" />
      </Layout>
    )
  }

  return (
    <Layout title={t('session.join_player')} backTo="/session">
      <Surface variant="elevated">
        <Input
          label={t('session.code_label')}
          value={code}
          onChange={(v) => setCode(v.toUpperCase().slice(0, 6))}
          placeholder={t('session.code_placeholder')}
          leadingIcon={<Hash size={16} />}
        />
      </Surface>

      <Surface variant="elevated">
        <div className="flex items-center gap-2 mb-3">
          <Users size={16} className="text-dnd-gold-bright" />
          <p className="font-display font-bold text-dnd-gold-bright text-sm">
            {t('session.select_character')}
          </p>
        </div>

        {autoChar ? (
          <p className="text-sm text-dnd-text font-body">
            {t('session.single_char_auto', { name: autoChar.name })}
          </p>
        ) : (
          <div className="space-y-2">
            {characters.map((c) => (
              <button
                key={c.id}
                onClick={() => setSelectedCharId(c.id)}
                className={`w-full text-left px-3 py-2.5 rounded-lg border transition-colors
                  ${selectedCharId === c.id
                    ? 'bg-gradient-gold text-dnd-ink border-dnd-gold shadow-engrave'
                    : 'bg-dnd-surface border-dnd-border text-dnd-text hover:border-dnd-gold-dim'}`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-display font-bold">{c.name}</span>
                  <span className="text-xs opacity-80 font-body">
                    {c.class_summary || t('character.select.new')}
                  </span>
                </div>
              </button>
            ))}
          </div>
        )}
      </Surface>

      {error && (
        <p className="text-[var(--dnd-crimson-bright)] text-sm font-body text-center">
          {error}
        </p>
      )}

      <Button
        variant="primary"
        size="lg"
        fullWidth
        disabled={!canJoin || joinMutation.isPending}
        loading={joinMutation.isPending}
        onClick={submit}
      >
        {t('session.join_button')}
      </Button>
    </Layout>
  )
}

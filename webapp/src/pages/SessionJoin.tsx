import { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Hash, Users, ClipboardCheck, Check } from 'lucide-react'
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
  // Prefill dal deep link d'invito (t.me/<bot>?startapp=join_<CODE>): qui il
  // valore arriva da un gesto esplicito dell'utente, non è un default arbitrario.
  const [searchParams] = useSearchParams()
  const [code, setCode] = useState((searchParams.get('code') ?? '').toUpperCase())
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
        setError(typeof err.detail === 'string' ? err.detail : t('common.error'))
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
          onChange={(v) => setCode(v.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 6))}
          placeholder={t('session.code_placeholder')}
          leadingIcon={<Hash size={16} />}
          inputMode="text"
        />
        <div className="mt-2 flex items-center justify-between gap-2">
          <span className="text-[10px] font-mono tabular-nums text-dnd-text-faint">
            {t('session.code_format_hint', { count: code.length })}
          </span>
          <div className="flex items-center gap-2">
            {code.length === 6 && /^[A-Z0-9]{6}$/.test(code) && (
              <Check size={14} className="text-[var(--dnd-emerald-bright)]" />
            )}
            <button
              type="button"
              onClick={async () => {
                try {
                  const text = await navigator.clipboard.readText()
                  setCode(text.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 6))
                  haptic.light()
                } catch {
                  /* clipboard read can fail (permission denied / unsupported) — silent */
                }
              }}
              className="inline-flex items-center gap-1 min-h-[44px] px-3 rounded-full bg-dnd-chip-bg border border-dnd-gold-dim/40 text-dnd-gold-bright text-[10px] font-cinzel uppercase tracking-widest"
            >
              <ClipboardCheck size={12} />
              {t('common.paste')}
            </button>
          </div>
        </div>
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
        <Surface variant="ember" className="text-center">
          <p className="text-[var(--dnd-crimson-bright)] text-sm font-body">
            {error}
          </p>
        </Surface>
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

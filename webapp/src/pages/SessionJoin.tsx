import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Hash, Users, ClipboardCheck, Check, UserPlus } from 'lucide-react'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import Skeleton from '@/components/ui/Skeleton'
import Pressable from '@/components/ui/Pressable'
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

  const { data: characters = [], isLoading: charsLoading } = useQuery({
    queryKey: ['characters'],
    queryFn: () => api.characters.list(),
  })

  // Sessione attiva del viewer. Vincolo BE: si può stare in UNA sola sessione
  // alla volta (un join mentre se ne ha già una → 409). Serve per: (a) portare
  // chi è già dentro direttamente nella stanza invece di rifargli il join, e
  // (b) evitare un auto-join che fallirebbe se è in un'altra sessione.
  const { data: activeSession, isLoading: sessionLoading } = useQuery({
    queryKey: ['session-me'],
    queryFn: () => api.sessions.me(),
  })

  const isLoading = charsLoading || sessionLoading

  const autoChar = useMemo(
    () => (characters.length === 1 ? characters[0] : null),
    [characters],
  )

  const effectiveCharId = selectedCharId ?? autoChar?.id ?? null
  const normalizedCode = code.trim().toUpperCase()
  const canJoin = normalizedCode.length === 6 && effectiveCharId !== null

  const joinMutation = useMutation({
    mutationFn: () => {
      if (!effectiveCharId) throw new Error('no-char')
      return api.sessions.join(normalizedCode, effectiveCharId)
    },
    onSuccess: (session) => {
      qc.setQueryData(['session-me'], session)
      haptic.success()
      navigate(`/session/${session.id}`, { replace: true })
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
  // `mutate` è un riferimento stabile (TanStack): può stare nelle deps
  // dell'effetto senza farlo ri-scattare a ogni render.
  const join = joinMutation.mutate

  // Sto già in una sessione che è proprio quella dell'invito (o sono arrivato
  // senza codice): entro diretto. Se invece è UN'ALTRA sessione, non posso
  // unirmi a questa (darebbe 409) → messaggio bloccante.
  const enteringActive =
    !!activeSession && (normalizedCode.length !== 6 || activeSession.code === normalizedCode)
  const inAnotherSession =
    !!activeSession && normalizedCode.length === 6 && activeSession.code !== normalizedCode

  // Auto-join: arrivo dal deep-link (codice valido), non sono in nessuna
  // sessione e ho ESATTAMENTE un personaggio → entro subito, senza tap.
  const shouldAutoJoin =
    !activeSession && !!autoChar && normalizedCode.length === 6 && !error
  const autoJoinedRef = useRef(false)

  useEffect(() => {
    if (isLoading) return
    if (activeSession) {
      if (enteringActive) navigate(`/session/${activeSession.id}`, { replace: true })
      return
    }
    if (shouldAutoJoin && !autoJoinedRef.current) {
      autoJoinedRef.current = true
      join()
    }
  }, [isLoading, activeSession, enteringActive, shouldAutoJoin, navigate, join])

  if (isLoading) {
    return (
      <Layout title={t('session.join_player')} backTo="/session">
        <Skeleton.Rect height="120px" />
      </Layout>
    )
  }

  // Redirect verso la sessione attiva in volo, oppure auto-join in corso:
  // schermata d'attesa dedicata, niente flash del form.
  if (enteringActive || shouldAutoJoin) {
    return (
      <Layout title={t('session.join_player')} backTo="/session">
        <Surface variant="elevated" className="text-center">
          <p className="text-sm text-dnd-text font-body">{t('session.joining')}</p>
        </Surface>
      </Layout>
    )
  }

  // Già in un'altra sessione attiva: non posso unirmi a questa.
  if (inAnotherSession) {
    return (
      <Layout title={t('session.join_player')} backTo="/session">
        <Surface variant="ember" className="text-center space-y-3">
          <p className="text-dnd-text text-sm font-body">{t('session.already_in_other')}</p>
          <Button
            variant="primary"
            fullWidth
            onClick={() => navigate(`/session/${activeSession!.id}`, { replace: true })}
          >
            {t('session.resume')}
          </Button>
        </Surface>
      </Layout>
    )
  }

  const submit = () => {
    setError(null)
    if (!canJoin) return  // UI already prevents this via disabled button
    joinMutation.mutate()
  }

  const hasCharacters = characters.length > 0

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
              <Check size={14} className="text-dnd-emerald-bright" />
            )}
            <Pressable
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
            </Pressable>
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

        {!hasCharacters ? (
          <div className="space-y-3">
            <p className="text-sm text-dnd-text-muted font-body italic">
              {t('session.join_needs_character')}
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
        ) : autoChar ? (
          <p className="text-sm text-dnd-text font-body">
            {t('session.single_char_auto', { name: autoChar.name })}
          </p>
        ) : (
          <div className="space-y-2">
            {characters.map((c) => (
              <Pressable
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
              </Pressable>
            ))}
          </div>
        )}
      </Surface>

      {error && (
        <Surface variant="ember" className="text-center">
          <p className="text-dnd-crimson-bright text-sm font-body">
            {error}
          </p>
        </Surface>
      )}

      {hasCharacters && (
        <Button
          variant="primary"
          size="lg"
          fullWidth
          disabled={!canJoin}
          loading={joinMutation.isPending}
          onClick={submit}
        >
          {t('session.join_button')}
        </Button>
      )}
    </Layout>
  )
}

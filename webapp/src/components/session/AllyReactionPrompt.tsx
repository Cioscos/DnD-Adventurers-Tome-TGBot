import { useRef } from 'react'
import { useMatch } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { api, ApiError, type ReactionPrompt } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { apiErrorCode, notifyMutationError } from '@/lib/mutationError'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'

const POLL_MS = 3_000

/** Poller del donatore: ogni 3 s chiede se un compagno ha un danno su cui può reagire. È anche il segnale di
 *  presenza per il server, quindi gira solo con la serata attiva e l'app in primo piano. */
export default function AllyReactionPrompt({ charId }: { charId: number }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const { data: session } = useQuery({ queryKey: ['session-me'], queryFn: () => api.sessions.me() })
  const inEvening = session?.status === 'active' && (session.participants?.some((p) => p.character_id === charId) ?? false)
  const key = ['reaction-prompts', charId]

  const { data: prompts = [] } = useQuery({
    queryKey: key,
    queryFn: () => api.allyReactions.prompts(charId),
    enabled: inEvening,
    refetchInterval: POLL_MS,
  })
  // Un poll già partito può riportare una richiesta a cui ho appena risposto: la si ignora.
  const answered = useRef(new Set<number>())
  const prompt: ReactionPrompt | undefined = prompts.find((p) => !answered.current.has(p.request_id))
  const drop = (id: number) => {
    answered.current.add(id)
    qc.setQueryData<ReactionPrompt[]>(key, (all) => (all ?? []).filter((p) => p.request_id !== id))
  }

  const answer = useMutation({
    mutationFn: ({ id, use }: { id: number; use: boolean }) => api.allyReactions.answer(charId, id, use),
    onSuccess: (r, { id, use }) => {
      drop(id)
      if (!use) return
      haptic.success()
      toast.success(t('allyReaction.used', { n: r.reduction }))
      qc.invalidateQueries({ queryKey: ['character', charId] })
    },
    onError: (err, { id }) => {
      drop(id)
      if (apiErrorCode(err) === 'turn_slot_used') notifyMutationError(err)
      else if (err instanceof ApiError && (err.status === 409 || err.status === 404)) toast.error(t('allyReaction.closed'))
      else notifyMutationError(err)
    },
  })

  const question = prompt?.feature_key === 'bard.cutting_words'
    ? t('allyReaction.question_cutting_words')
    : t('allyReaction.question_interception', { name: prompt?.receiver_name })

  return (
    <Sheet open={!!prompt} onClose={() => {}} dismissible={false} zClassName="z-[60]" title={t('allyReaction.title')}>
      {prompt && (
        <div className="flex flex-col gap-4 p-5">
          <p className="break-words text-base font-body text-dnd-text">
            {t('allyReaction.hit', { name: prompt.receiver_name, damage: prompt.damage })}
            {prompt.damage_type ? ` ${t('allyReaction.of_type', { type: t(`character.inventory.damage_types.dmg_${prompt.damage_type}`, { defaultValue: prompt.damage_type }) })}` : ''}
          </p>
          <p className="break-words text-sm font-body text-dnd-text-muted">
            {t(`allyReaction.feature.${prompt.feature_key === 'bard.cutting_words' ? 'cutting_words' : 'interception'}`, { dice: prompt.dice })}
          </p>
          <p className="break-words text-base font-body text-dnd-gold-bright">{question}</p>
          <div className="flex gap-3">
            <Button variant="secondary" className="min-h-11 flex-1" disabled={answer.isPending}
              onClick={() => answer.mutate({ id: prompt.request_id, use: false })}>
              {t('allyReaction.leave')}
            </Button>
            <Button variant="primary" className="min-h-11 flex-1" loading={answer.isPending}
              onClick={() => answer.mutate({ id: prompt.request_id, use: true })}>
              {t('allyReaction.use')}
            </Button>
          </div>
        </div>
      )}
    </Sheet>
  )
}

/** Montato una volta in App: copre la scheda, le sue sottopagine e la pagina della serata (anche lo scontro). */
export function AllyReactionHost() {
  const charMatch = useMatch('/char/:id/*')
  const sessionMatch = useMatch('/session/:id/*')
  const onSession = !charMatch && !!sessionMatch && !!Number(sessionMatch.params.id)
  // Sulla serata il personaggio è quello dell'utente seduto in quella serata (dati già in cache).
  const { data: me } = useQuery({ queryKey: ['auth-me'], queryFn: () => api.me(), staleTime: Infinity, enabled: onSession })
  const { data: session } = useQuery({ queryKey: ['session-me'], queryFn: () => api.sessions.me(), enabled: onSession })
  const sessionCharId = onSession && me
    ? session?.participants?.find((p) => p.user_id === me.user_id)?.character_id
    : undefined
  const charId = Number(charMatch?.params.id) || sessionCharId
  return charId ? <AllyReactionPrompt charId={charId} /> : null
}

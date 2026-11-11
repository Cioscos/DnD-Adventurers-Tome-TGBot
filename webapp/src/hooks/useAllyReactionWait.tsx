import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'
import { api, type OptionResult, type WaitingDonor } from '@/api/client'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'

const POLL_MS = 2_000

/** Una riga per alleato che ha ridotto il danno ("Aldo: 7 in meno (Intercettazione)"), null se nessuno. */
export function allyReductionText(t: TFunction, result?: OptionResult): string | null {
  const lines = (result?.allies ?? []).map((a) => t('allyReaction.reduced', {
    name: a.name, reduction: a.reduction,
    feature: t(`allyReaction.feature_name.${a.feature_key === 'bard.cutting_words' ? 'cutting_words' : 'interception'}`),
  }))
  return lines.length ? lines.join(' · ') : null
}

type Pending = { requestId: number; waiting: WaitingDonor[] }

/** Prima di applicare un danno: apre la richiesta di reazione degli alleati e, se qualcuno può reagire, aspetta.
 *  `wait` risolve con l'id della richiesta chiusa (da passare al PATCH PF) o null se nessuno poteva reagire.
 *  Un errore di rete sulla richiesta non blocca il danno: si prosegue come se non ci fosse nessuno. */
export function useAllyReactionWait(charId: number) {
  const { t } = useTranslation()
  const [pending, setPending] = useState<Pending | null>(null)
  const finish = useRef<((id: number | null) => void) | null>(null)

  const done = useCallback((id: number | null) => {
    setPending(null)
    finish.current?.(id)
    finish.current = null
  }, [])

  const wait = useCallback(async (damage: number, damageType?: string | null): Promise<number | null> => {
    let opened
    try {
      opened = await api.allyReactions.open(charId, damage, damageType)
    } catch {
      return null
    }
    if (opened.request_id == null) return null
    const requestId = opened.request_id
    return new Promise<number | null>((resolve) => {
      finish.current = resolve
      setPending({ requestId, waiting: opened.waiting })
    })
  }, [charId])

  const requestId = pending?.requestId
  useEffect(() => {
    if (requestId == null) return
    const timer = setInterval(async () => {
      try {
        const r = await api.allyReactions.read(charId, requestId)
        if (r.status === 'closed') done(requestId)
        else setPending({ requestId, waiting: r.waiting })
      } catch { /* si riprova al prossimo giro: il server chiude da solo dopo 30 s */ }
    }, POLL_MS)
    return () => clearInterval(timer)
  }, [charId, requestId, done])

  const skip = async () => {
    if (!pending) return
    try { await api.allyReactions.close(charId, pending.requestId) } catch { /* il PATCH decide: la richiesta scade comunque */ }
    done(pending.requestId)
  }

  const elements = (
    <Sheet open={!!pending} onClose={() => {}} dismissible={false} zClassName="z-[60]" title={t('allyReaction.wait_title')}>
      <div className="flex flex-col gap-4 p-5">
        <p className="break-words text-base font-body text-dnd-text">
          {t('allyReaction.waiting_for', { names: (pending?.waiting ?? []).map((w) => w.name).join(', ') })}
        </p>
        <Button variant="secondary" fullWidth className="min-h-11" onClick={skip}>
          {t('allyReaction.apply_now')}
        </Button>
      </div>
    </Sheet>
  )
  return { wait, elements }
}

import { apiErrorCode } from '@/lib/mutationError'

/** PATCH dei PF con la richiesta di reazione degli alleati chiusa. Se il server non la accetta più
 *  (409 `request_unusable`: scaduta e rimborsata mentre il ricevente sceglieva) il danno non si perde:
 *  si ripete senza `ally_reaction_id`, per intero, e `onLost` avvisa il giocatore. */
export async function sendWithAllyReaction<B extends object, T>(
  allyId: number | null,
  body: B | undefined,
  send: (body: (B & { ally_reaction_id?: number }) | undefined) => Promise<T>,
  onLost: () => void,
): Promise<T> {
  if (allyId == null) return send(body)
  try {
    return await send({ ...body, ally_reaction_id: allyId } as B & { ally_reaction_id: number })
  } catch (err) {
    if (apiErrorCode(err) !== 'request_unusable') throw err
    onLost()
    return send(body)
  }
}

import type { ReactNode } from 'react'
import { useIsRestoring } from '@tanstack/react-query'

/** Durante il ripristino della cache le query sono 'pending' ma non in caricamento
 *  (isLoading false): le pagine mostrerebbero per un frame lo stato vuoto o l'errore. */
export default function RestoreGate({ children }: { children: ReactNode }) {
  return useIsRestoring() ? null : <>{children}</>
}

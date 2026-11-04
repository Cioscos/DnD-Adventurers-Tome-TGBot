import { useState } from 'react'

/** L'esito mostrato: un ritocco vale per il tiro da cui parte, un nuovo tiro del genitore lo sostituisce. */
export function useRetouched<T>(rolled: T): [T, (to: T) => void] {
  const [retouched, setRetouched] = useState<{ from: T; to: T } | null>(null)
  return [retouched && retouched.from === rolled ? retouched.to : rolled, (to) => setRetouched({ from: rolled, to })]
}

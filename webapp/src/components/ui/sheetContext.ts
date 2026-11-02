import { createContext } from 'react'

/** Dentro uno Sheet: false mentre entra, true a ingresso finito. null = fuori da uno Sheet. */
export const SheetEnteredContext = createContext<boolean | null>(null)

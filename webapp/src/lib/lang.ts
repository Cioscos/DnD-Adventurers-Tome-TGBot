/** La lingua dei testi nostri (`it`/`en`) dalla lingua di i18next: tutto ciò che non è inglese è italiano. */
export const uiLang = (language?: string | null): 'it' | 'en' => (language?.startsWith('en') ? 'en' : 'it')

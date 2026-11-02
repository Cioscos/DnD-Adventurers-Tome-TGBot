import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { getLanguageCode } from './auth/telegram'

const lng = getLanguageCode().startsWith('it') ? 'it' : 'en'

// Solo la lingua attiva: i due JSON insieme (~420 KB) erano metà dell'entry.
// La lingua non cambia a runtime, quindi l'altra non serve mai.
const load = lng === 'it' ? () => import('./locales/it.json') : () => import('./locales/en.json')

/** Risolta quando le traduzioni sono pronte: main.tsx monta React solo dopo. */
// Se il chunk non arriva (rete del tavolo) si monta comunque, con le chiavi grezze,
// invece di lasciare la schermata bianca.
export const i18nReady = load().catch(() => ({ default: {} })).then((m) =>
  i18n.use(initReactI18next).init({
    resources: { [lng]: { translation: m.default } },
    lng,
    fallbackLng: lng,
    interpolation: { escapeValue: false },
  }),
)

export default i18n

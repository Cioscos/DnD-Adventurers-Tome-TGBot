import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import it from './locales/it.json'
import en from './locales/en.json'
import { getLanguageCode } from './auth/telegram'

const lng = getLanguageCode().startsWith('it') ? 'it' : 'en'

i18n.use(initReactI18next).init({
  resources: {
    it: { translation: it },
    en: { translation: en },
  },
  lng,
  fallbackLng: 'it',
  interpolation: { escapeValue: false },
})

export default i18n

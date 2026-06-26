import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES } from './i18n'

const STORAGE_KEY = 'rht.lang'
const HTML_LANG_KEY = 'rht.htmlLang'

const LanguageContext = createContext({
  lang: DEFAULT_LANGUAGE,
  setLang: () => {},
  toggle: () => {},
})

/** Read the persisted language (or fall back to <html lang>, then 'en'). */
function readInitialLang() {
  if (typeof window === 'undefined') return DEFAULT_LANGUAGE
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored && SUPPORTED_LANGUAGES.includes(stored)) return stored
  } catch (_e) {
    // Ignore storage errors (e.g. private browsing).
  }
  const htmlLang = (document.documentElement.lang || '').toLowerCase().slice(0, 2)
  if (SUPPORTED_LANGUAGES.includes(htmlLang)) return htmlLang
  return DEFAULT_LANGUAGE
}

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(readInitialLang)

  // Persist + sync <html lang> so screen readers and CSS `:lang()` selectors work.
  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, lang)
      window.localStorage.setItem(HTML_LANG_KEY, lang)
    } catch (_e) {
      // Ignore.
    }
    document.documentElement.lang = lang
    document.documentElement.setAttribute('data-lang', lang)
  }, [lang])

  const setLang = useCallback((next) => {
    if (!SUPPORTED_LANGUAGES.includes(next)) return
    setLangState(next)
  }, [])

  const toggle = useCallback(() => {
    setLangState((prev) => (prev === 'en' ? 'bn' : 'en'))
  }, [])

  const value = useMemo(() => ({ lang, setLang, toggle }), [lang, setLang, toggle])

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useLanguage() {
  return useContext(LanguageContext)
}

export { LanguageContext }
import { useCallback, useEffect, useMemo, useState } from 'react'
import { DICT, I18nContext, interpolate } from './i18n'

const STORE_KEY = 'cybra:lang'

function initialLang() {
  try {
    const saved = window.localStorage.getItem(STORE_KEY)
    if (saved === 'ru' || saved === 'en') return saved
  } catch {
    /* приватный режим */
  }
  // Браузер на английском получает английский по умолчанию, все остальные —
  // русский: русский остаётся языком по умолчанию, как и было.
  const nav = (navigator.language || 'ru').toLowerCase()
  return nav.startsWith('ru') ? 'ru' : nav.startsWith('en') ? 'en' : 'ru'
}

export function I18nProvider({ children }) {
  const [lang, setLang] = useState(initialLang)

  useEffect(() => {
    try {
      window.localStorage.setItem(STORE_KEY, lang)
    } catch {
      /* не повод ломать страницу */
    }
    document.documentElement.lang = lang
  }, [lang])

  const t = useCallback(
    (text, params) => {
      const dict = DICT[lang] || DICT.ru
      const value = dict[text] ?? text
      return interpolate(value, params)
    },
    [lang],
  )

  const value = useMemo(() => ({ lang, setLang, t }), [lang, t])
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export { useI18n } from './i18n'

import { useEffect, useRef, useState } from 'react'
import { LANGS } from '../i18n'
import { useI18n } from '../i18n-context'
import { Translate } from '../icons'

/** Переключатель языка: слева от колокольчика, как просил пользователь.
 *
 *  Показывает текущий код (RU / EN) и открывает список языков. Выбор
 *  сохраняется в localStorage, поэтому не сбрасывается на каждой странице. */
export default function LanguageSwitcher() {
  const { lang, setLang, t } = useI18n()
  const [open, setOpen] = useState(false)
  const wrap = useRef(null)

  useEffect(() => {
    function onDown(event) {
      if (wrap.current && !wrap.current.contains(event.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [])

  const current = LANGS.find((item) => item.code === lang) || LANGS[0]

  return (
    <div style={{ position: 'relative' }} ref={wrap}>
      <button
        className="icon-btn lang-btn"
        aria-label={t('Язык интерфейса')}
        aria-haspopup="listbox"
        aria-expanded={open}
        title={t('Язык интерфейса')}
        onClick={() => setOpen((value) => !value)}
      >
        <Translate size={15} weight="bold" />
        <span className="lang-code">{current.short}</span>
      </button>

      {open ? (
        <div className="popover" role="listbox" style={{ minWidth: 170 }}>
          {LANGS.map((item) => (
            <button
              key={item.code}
              className={`popover-item${item.code === lang ? ' is-current' : ''}`}
              role="option"
              aria-selected={item.code === lang}
              onClick={() => {
                setLang(item.code)
                setOpen(false)
              }}
            >
              <span>{item.label}</span>
              <span className="dim mono-sm">{item.short}</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}

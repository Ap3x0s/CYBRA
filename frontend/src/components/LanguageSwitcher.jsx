import { useEffect, useRef } from 'react'
import { LANGS } from '../i18n'
import { useI18n } from '../i18n-context'
import { Translate } from '../icons'

/** Переключатель языка: слева от колокольчика.
 *
 *  Состояние открытия контролируется снаружи (Topbar), потому что иначе
 *  меню языка было независимым от поповеров колокольчика и профиля: клик по
 *  второму оставлял первый открытым — на экране оказывались два меню разом,
 *  а Escape закрывал только те, что знал Topbar. */
export default function LanguageSwitcher({ open = false, onToggle }) {
  const { lang, setLang, t } = useI18n()
  const wrap = useRef(null)

  useEffect(() => {
    function onDown(event) {
      if (wrap.current && !wrap.current.contains(event.target)) {
        if (open) onToggle(false)
      }
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [open, onToggle])

  const current = LANGS.find((item) => item.code === lang) || LANGS[0]

  return (
    <div style={{ position: 'relative' }} ref={wrap}>
      <button
        className={`icon-btn lang-btn${open ? ' is-open' : ''}`}
        aria-label={t('Язык интерфейса')}
        aria-haspopup="listbox"
        aria-expanded={open}
        title={t('Язык интерфейса')}
        onClick={() => onToggle(!open)}
      >
        <Translate size={15} weight="bold" />
        <span className="lang-code">{current.short}</span>
      </button>

      {open ? (
        <div className="popover popover-lang" role="listbox" aria-label={t('Язык интерфейса')}>
          {LANGS.map((item) => {
            const isCurrent = item.code === lang
            return (
              <button
                key={item.code}
                className={`popover-item${isCurrent ? ' is-current' : ''}`}
                role="option"
                aria-selected={isCurrent}
                onClick={() => {
                  setLang(item.code)
                  onToggle(false)
                }}
              >
                <span>{item.label}</span>
                <span className="mono-sm">{item.short}</span>
              </button>
            )
          })}
        </div>
      ) : null}
    </div>
  )
}

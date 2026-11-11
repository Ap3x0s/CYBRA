import { useEffect, useRef } from 'react'
import { useI18n } from '../i18n-context'
import { MagnifyingGlass, X } from '../icons'

/** Поиск внутри страницы: строка в шапке раздела.
 *
 *  Живёт на самой странице, а не в верхней полосе: поиск по прогонам ищет
 *  только прогоны, поиск по моделям — только модели, и держать общий
 *  глобальный фильтр стало неверно. Плюс место под него освободилось именно
 *  там, где у страниц уже есть шапка с заголовком.
 *
 *  Значение контролируется снаружи (useState страницы), поэтому сохранение
 *  в URL или сброс остаются за вызывающей стороной. */
export default function PageSearch({
  value,
  onChange,
  placeholder,
  autoFocus = false,
  width = 320,
}) {
  const { t } = useI18n()
  const inputRef = useRef(null)

  // Ctrl/Cmd+K — привычный вход в поиск. Работает только пока страница
  // смонтирована, поэтому на других экранах ничего не перехватывает.
  useEffect(() => {
    function onKey(event) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        inputRef.current?.focus()
        inputRef.current?.select()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    if (autoFocus) inputRef.current?.focus()
  }, [autoFocus])

  return (
    <div className="page-search" style={{ width }}>
      <MagnifyingGlass size={15} weight="bold" className="page-search-icon" />
      <input
        ref={inputRef}
        className="page-search-input"
        type="search"
        value={value}
        placeholder={t(placeholder)}
        aria-label={t(placeholder)}
        title={t('Поиск (Ctrl+K)')}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') {
            onChange('')
            event.currentTarget.blur()
          }
        }}
      />
      {value ? (
        <button
          type="button"
          className="page-search-clear"
          onClick={() => {
            onChange('')
            inputRef.current?.focus()
          }}
          aria-label={t('Очистить')}
        >
          <X size={12} weight="bold" />
        </button>
      ) : null}
    </div>
  )
}

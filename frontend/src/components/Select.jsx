import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { CaretDown } from '../icons'
import { useI18n } from '../i18n-context'

/** Выпадающий список в стиле CYBRA.
 *
 *  Заменяет нативный <select>, потому что его раскрытый список рисует ОС:
 *  на Windows это системный прямоугольник с синей подсветкой, который не
 *  подчиняется теме и выбивается из интерфейса. Список здесь — обычный DOM,
 *  поэтому он в нашем стиле, следует за темой и одинаков на всех платформах.
 *
 *  Доступность сохранена: role=listbox, aria-expanded, aria-activedescendant,
 *  управление с клавиатуры (↑↓, Enter, Space, Escape, Home/End) и ввод первых
 *  букв. Фокус остаётся на кнопке, поэтому Tab ведёт себя предсказуемо.
 *
 *  options: [{ value, label, disabled? }]
 */
export default function Select({
  value,
  onChange,
  options = [],
  placeholder = '—',
  width,
  id,
  disabled = false,
  className = '',
  ariaLabel,
}) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const [dropUp, setDropUp] = useState(false)
  const wrap = useRef(null)
  const list = useRef(null)
  const button = useRef(null)

  const items = options || []
  const current = items.find((item) => String(item.value) === String(value))
  const currentLabel = current ? t(current.label) : placeholder

  const indexOfValue = () => {
    const i = items.findIndex((item) => String(item.value) === String(value))
    return i < 0 ? 0 : i
  }

  // Открытие: активным делаем текущий выбор.
  useEffect(() => {
    if (open) setActive(indexOfValue())
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  // Закрытие по клику снаружи.
  useEffect(() => {
    if (!open) return undefined
    function onDown(event) {
      if (wrap.current && !wrap.current.contains(event.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [open])

  // Направление раскрытия: если снизу мало места, список идёт вверх.
  useLayoutEffect(() => {
    if (!open || !wrap.current) return
    const rect = wrap.current.getBoundingClientRect()
    const spaceBelow = window.innerHeight - rect.bottom
    setDropUp(spaceBelow < 240 && rect.top > spaceBelow)
  }, [open])

  // Активный пункт всегда в зоне видимости при навигации с клавиатуры.
  useEffect(() => {
    if (!open || !list.current) return
    const node = list.current.querySelector('[data-active="true"]')
    if (node) node.scrollIntoView({ block: 'nearest' })
  }, [open, active])

  function commit(index) {
    const item = items[index]
    if (!item || item.disabled) return
    onChange?.(item.value)
    setOpen(false)
    button.current?.focus()
  }

  function onKeyDown(event) {
    if (disabled) return
    const key = event.key

    if (!open) {
      if (key === 'ArrowDown' || key === 'ArrowUp' || key === 'Enter' || key === ' ') {
        event.preventDefault()
        setOpen(true)
      }
      return
    }

    if (key === 'Escape') {
      event.preventDefault()
      setOpen(false)
      return
    }
    if (key === 'Enter' || key === ' ') {
      event.preventDefault()
      commit(active)
      return
    }
    if (key === 'Home') {
      event.preventDefault()
      setActive(0)
      return
    }
    if (key === 'End') {
      event.preventDefault()
      setActive(items.length - 1)
      return
    }
    if (key === 'ArrowDown') {
      event.preventDefault()
      setActive((i) => Math.min(i + 1, items.length - 1))
      return
    }
    if (key === 'ArrowUp') {
      event.preventDefault()
      setActive((i) => Math.max(i - 1, 0))
      return
    }
    if (key === 'Tab') {
      setOpen(false)
      return
    }

    // Быстрый переход по первой букве.
    if (key.length === 1 && /\S/.test(key)) {
      const needle = key.toLowerCase()
      const from = active + 1
      const ordered = [...items.slice(from), ...items.slice(0, from)]
      const hit = ordered.find(
        (item) => !item.disabled && t(item.label).toLowerCase().startsWith(needle),
      )
      if (hit) {
        event.preventDefault()
        setActive(items.indexOf(hit))
      }
    }
  }

  return (
    <div
      className={`cy-select${open ? ' is-open' : ''}${disabled ? ' is-disabled' : ''} ${className}`}
      ref={wrap}
      style={width ? { width } : undefined}
    >
      <button
        type="button"
        id={id}
        ref={button}
        className="cy-select-trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={ariaLabel}
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        onKeyDown={onKeyDown}
      >
        <span className={`cy-select-value${current ? '' : ' is-placeholder'}`}>
          {currentLabel}
        </span>
        <CaretDown size={11} weight="bold" className="cy-select-caret" />
      </button>

      {open ? (
        <ul
          className={`cy-select-menu${dropUp ? ' is-up' : ''}`}
          role="listbox"
          ref={list}
          aria-labelledby={id}
        >
          {items.map((item, index) => {
            const isSelected = String(item.value) === String(value)
            const isActive = index === active
            return (
              <li
                key={String(item.value)}
                role="option"
                aria-selected={isSelected}
                aria-disabled={item.disabled || undefined}
                data-active={isActive || undefined}
                className={`cy-select-option${isSelected ? ' is-selected' : ''}`
                  + `${isActive ? ' is-active' : ''}`
                  + `${item.disabled ? ' is-disabled' : ''}`}
                onMouseEnter={() => setActive(index)}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => commit(index)}
              >
                <span className="cy-select-option-label">{t(item.label)}</span>
                {isSelected ? <span className="cy-select-check" aria-hidden="true">✓</span> : null}
              </li>
            )
          })}
        </ul>
      ) : null}
    </div>
  )
}

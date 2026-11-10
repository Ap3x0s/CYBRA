import { useEffect, useRef, useState } from 'react'
import { createField } from '../field'

/** Фон приложения: ASCII-поле из референса sdk-hub/demo.
 *
 *  Раньше здесь был собственный «дождь» из символов. Пользователь указал на
 *  D:\\projects\\sdk-hub\\demo и попросил взять поле оттуда как есть, без
 *  эффектов от мыши (клики, след, звук) — они в референсе не были нужны.
 *
 *  Сам рендер живёт в ../field.js — переносе createTexture. Здесь только
 *  монтирование канваса и переключатель. Выбор запоминается: решение
 *  «мне фон мешает» не должно сбрасываться на каждой странице. */

const STORE_KEY = 'cybra:field'

function initialEnabled() {
  try {
    return window.localStorage.getItem(STORE_KEY) !== 'off'
  } catch {
    return true
  }
}

export default function AnimatedBackdrop() {
  const [enabled, setEnabled] = useState(initialEnabled)
  const host = useRef(null)

  useEffect(() => {
    try {
      window.localStorage.setItem(STORE_KEY, enabled ? 'on' : 'off')
    } catch {
      /* приватный режим — не повод ломать страницу */
    }
  }, [enabled])

  useEffect(() => {
    if (!enabled || !host.current) return undefined

    const field = createField(host.current, {
      // мельче ячейка → мельче глиф; на телефоне клеток втрое меньше
      cells: window.innerWidth < 720 ? 4200 : 15000,
      dark: true,
    })

    return () => {
      if (field) field.destroy()
      host.current?.replaceChildren()
    }
  }, [enabled])

  return (
    <div className="backdrop" aria-hidden="true">
      {enabled ? <div ref={host} className="backdrop-field" /> : null}
      <button
        className="backdrop-toggle"
        onClick={() => setEnabled((value) => !value)}
        title={enabled ? 'Остановить фоновую анимацию' : 'Включить фоновую анимацию'}
      >
        {enabled ? 'остановить фон' : 'включить фон'}
      </button>
    </div>
  )
}

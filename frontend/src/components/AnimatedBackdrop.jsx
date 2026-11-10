import { useEffect, useRef, useState } from 'react'
import { createField } from '../field'

/** Фон приложения: ASCII-поле из референса sdk-hub/demo.
 *
 *  Раньше здесь был собственный «дождь» из символов. Пользователь указал на
 *  D:\\projects\\sdk-hub\\demo и попросил взять поле оттуда как есть, без
 *  эффектов от мыши (клики, след, звук) — они в референсе не были нужны.
 *
 *  Сам рендер живёт в ../field.js — переносе createTexture. Здесь только
 *  монтирование канваса.
 *
 *  Кнопки «остановить фон» нет: в референсе её нет, и это фон, а не элемент
 *  управления. Выключить поле можно через localStorage (cybra:field = 'off') —
 *  так делают scripts/audit_layout.py и scripts/bench_field.py, которым
 *  анимация мешает мерить вёрстку. */

const STORE_KEY = 'cybra:field'

function initialEnabled() {
  try {
    return window.localStorage.getItem(STORE_KEY) !== 'off'
  } catch {
    return true
  }
}

export default function AnimatedBackdrop() {
  const [enabled] = useState(initialEnabled)
  const host = useRef(null)

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
    </div>
  )
}

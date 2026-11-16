/** Верхняя полоса: логотип, меню, уведомления, профиль.
 *
 *  Поиска здесь больше нет: он переехал на страницы «Прогоны» и «Модели», где
 *  ищет свои данные. Общий фильтр в шапке был неверен — он применялся только к
 *  списку прогонов, а на остальных экранах просто занимал место.
 *
 *  Правила поведения, закреплённые замером:
 *
 *  1. Открыт максимум ОДИН поповер. Раньше меню языка жило своим состоянием
 *     внутри LanguageSwitcher, поэтому клик по колокольчику оставлял его
 *     открытым — на экране было два меню, а Escape закрывал не всё.
 *
 *  2. Escape закрывает любой поповер. */
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth, can } from '../auth'
import { useApi } from '../hooks'
import { useI18n } from '../i18n-context'
import LanguageSwitcher from '../components/LanguageSwitcher'
import TopNav from '../components/TopNav'
import markUrl from '../assets/cybra-mark.png'
import wordmarkUrl from '../assets/cybra-wordmark.png'
import {
  ArrowSquareOut, Bell, CaretDown, SignOut, UserCircle,
} from '../icons'

export default function Topbar() {
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const runs = useApi(() => api.runs(50))
  const { t } = useI18n()
  const [panel, setPanel] = useState(null) // 'bell' | 'account' | 'lang' | null
  const wrapRef = useRef(null)
  // Снимок id уведомлений, которые человек уже видел. Хранится в localStorage,
  // чтобы индикатор не загорался заново при каждой перезагрузке страницы:
  // «непрочитано» — это свойство события, а не сессии браузера.
  const [seenIds, setSeenIds] = useState(() => {
    try {
      const raw = window.localStorage.getItem('cybra.seen-alerts')
      return raw ? new Set(JSON.parse(raw)) : new Set()
    } catch {
      return new Set()
    }
  })

  const initials = (user?.display_name || user?.email || 'AD').slice(0, 2).toUpperCase()
  const name = user?.display_name || user?.email || ''

  useEffect(() => {
    function onKey(event) {
      if (event.key === 'Escape') setPanel(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    function onDown(event) {
      if (wrapRef.current && !wrapRef.current.contains(event.target)) {
        setPanel(null)
      }
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [])

  const alerts = (runs.data || []).filter((run) =>
    ['PARTIAL', 'ERROR', 'CANCELLED'].includes(run.status),
  )

  // Новые — те, что появились после прошлого открытия меню.
  const freshAlerts = alerts.filter((run) => !seenIds.has(run.id))
  const hasFresh = freshAlerts.length > 0

  /** Запомнить текущий набор как просмотренный и погасить индикатор. */
  function markAlertsSeen() {
    const ids = new Set(alerts.map((run) => run.id))
    setSeenIds(ids)
    try {
      window.localStorage.setItem('cybra.seen-alerts', JSON.stringify([...ids]))
    } catch {
      // Приватный режим или запрещённое хранилище: индикатор просто не
      // запомнится между перезагрузками, но интерфейс продолжит работать.
    }
  }

  /** Единственная точка переключения поповеров — гарантирует «один за раз». */
  function togglePanel(which) {
    setPanel((current) => (current === which ? null : which))
  }

  return (
    <div className="topbar" ref={wrapRef}>
      <div className="topbar-brand">
        {/* Фирменный знак и надпись — растровые ассеты из docs/brand,
            обрезанные по альфе и сохранённые в 3x (см. scripts/prep_brand_assets.py).
            Картинка, а не инлайн-SVG: логотип объёмный, с градиентами
            металла, — трассировка в SVG потеряла бы эти переходы и дала бы
            ступенчатые края. Знак и надпись лежат отдельными файлами, чтобы
            их можно было позиционировать независимо.

            draggable=false обязателен: user-select в CSS запрещает выделение
            текста, но не перетаскивание картинки — в Chrome это отдельный
            механизм, и без атрибута лого утаскивается курсором. */}
        <img
          className="brand-logo"
          src={markUrl}
          alt=""
          aria-hidden="true"
          draggable="false"
        />
        <div className="brand-text">
          <img
            className="brand-wordmark-img"
            src={wordmarkUrl}
            alt="CYBRA"
            draggable="false"
          />
          <div className="brand-sub">security console</div>
        </div>
      </div>

      <div className="topbar-center">
        <div className="topbar-center-inner">
          <TopNav />
        </div>
      </div>

      <div className="topbar-actions">
        <LanguageSwitcher
          open={panel === 'lang'}
          onToggle={(next) => setPanel(next ? 'lang' : null)}
        />

        <div style={{ position: 'relative' }}>
          <button
            className={`icon-btn bell-btn${panel === 'bell' ? ' is-open' : ''}`}
            aria-label={
              t('Уведомления')
              + (hasFresh ? `: ${t('новых')} ${freshAlerts.length}` : '')
            }
            aria-expanded={panel === 'bell'}
            onClick={() => {
              togglePanel('bell')
              // Отметку ставим при открытии, а не при закрытии: иначе значок
              // остаётся белым, пока меню открыто, и человек не понимает,
              // прочитал он уведомление или нет.
              if (panel !== 'bell') markAlertsSeen()
            }}
          >
            {/* Значок всегда янтарный — это его штатный цвет. Признак
                непрочитанного — только белая точка в углу: обводка и
                свечение перетягивали внимание с самой точки. */}
            <Bell size={18} weight="bold" />
            {hasFresh ? <span className="fresh-badge" aria-hidden="true" /> : null}
          </button>

          {panel === 'bell' ? (
            <div className="popover" role="menu">
              <div className="popover-head">
                <span>{t('Незавершённые прогоны')}</span>
                <span className={`popover-count${alerts.length ? ' is-active' : ''}`}>
                  {alerts.length}
                </span>
              </div>
              {alerts.length === 0 ? (
                /* Пустое состояние объясняет, что здесь появится: без этого
                   меню выглядело как незаконченная заготовка. */
                <div className="popover-blank">
                  <span className="popover-blank-ico">
                    <Bell size={17} weight="bold" />
                  </span>
                  <span className="popover-blank-title">
                    {t('Нет незавершённых прогонов')}
                  </span>
                  <span className="popover-blank-hint">
                    {t('Здесь появятся прогоны со статусом PARTIAL, ERROR или CANCELLED.')}
                  </span>
                </div>
              ) : (
                alerts.slice(0, 6).map((run) => (
                  <button
                    key={run.id}
                    className="popover-item"
                    onClick={() => {
                      setPanel(null)
                      navigate(`/runs/${run.id}`)
                    }}
                  >
                    <span className="popover-label">{run.label}</span>
                    <span className={`pill ${run.status === 'ERROR' ? 'bad' : 'warn'}`}>
                      {run.status}
                    </span>
                  </button>
                ))
              )}
            </div>
          ) : null}
        </div>

        <div style={{ position: 'relative' }}>
          <button
            className={`profile-btn${panel === 'account' ? ' is-open' : ''}`}
            aria-label={t('Аккаунт')}
            aria-expanded={panel === 'account'}
            onClick={() => togglePanel('account')}
          >
            <span className="avatar">{initials}</span>
            {/* Роль убрана из кнопки: она дублировала строку ниже в меню и
                растягивала капсулу по высоте. */}
            <span className="profile-name">{name}</span>
            <CaretDown size={11} weight="bold" className="profile-caret" />
          </button>

          {panel === 'account' ? (
            <div className="popover popover-account" role="menu">
              <div className="account-head">
                <span className="avatar avatar-lg">{initials}</span>
                <span className="account-text">
                  <span className="account-name">{name}</span>
                  <span className="account-mail">{user?.email}</span>
                  <span className="account-role">{user?.role}</span>
                </span>
              </div>
              <div className="popover-sep" />
              <button
                className="popover-item"
                onClick={() => {
                  setPanel(null)
                  navigate('/settings')
                }}
              >
                <span className="popover-row">
                  <UserCircle size={14} weight="bold" />
                  {t('Настройки')} и {t('пароль')}
                </span>
              </button>
              {can(user, 'operator') ? (
                <button
                  className="popover-item"
                  onClick={() => {
                    setPanel(null)
                    navigate('/runs/new')
                  }}
                >
                  <span className="popover-row">
                    <ArrowSquareOut size={14} weight="bold" />
                    {t('Новый прогон')}
                  </span>
                </button>
              ) : null}
              {/* Разделитель перед «Выйти» убран: он визуально разрывал
                  меню профиля на две несвязанные части. Между блоком
                  личности и действиями разделитель остаётся — там он
                  осмыслен, а здесь действие «выйти» такое же, как
                  остальные. */}
              <button className="popover-item danger" onClick={logout}>
                <span className="popover-row">
                  <SignOut size={14} weight="bold" />
                  {t('Выйти')}
                </span>
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}

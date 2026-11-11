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

  /** Единственная точка переключения поповеров — гарантирует «один за раз». */
  function togglePanel(which) {
    setPanel((current) => (current === which ? null : which))
  }

  return (
    <div className="topbar" ref={wrapRef}>
      <div className="topbar-brand">
        <div className="brand-mark">CY</div>
        <div>
          <div className="brand-name">CYBRA</div>
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
            className={`icon-btn${panel === 'bell' ? ' is-open' : ''}`}
            aria-label={t('Уведомления') + (alerts.length ? `: ${alerts.length}` : '')}
            aria-expanded={panel === 'bell'}
            onClick={() => togglePanel('bell')}
          >
            <Bell size={15} weight="bold" />
            {alerts.length ? <span className="dot" /> : null}
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
            <span className="profile-meta">
              <span className="profile-name">{name}</span>
              <span className="profile-role">{user?.role}</span>
            </span>
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
              <div className="popover-sep" />
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

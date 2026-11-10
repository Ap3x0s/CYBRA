/** Верхняя полоса: логотип, меню с поиском, уведомления, профиль.
 *
 *  Структура слева направо: бренд (прижат к левому краю), центральная группа
 *  «меню + поиск» (центрируется по полосе), правая группа «язык, колокольчик,
 *  профиль».
 *
 *  Поиск стоит справа от меню и раскрывается ВПРАВО: его левая кромка не
 *  двигается, поэтому это читается как выдвижение, а не как прыжок. Когда он
 *  раскрыт, подписи меню схлопываются в иконки, чтобы полоса не отнимала у
 *  них ширину и не резала слова.
 *
 *  Каждый элемент что-то делает: поиск фильтрует прогоны (⌘K наводит фокус),
 *  колокольчик показывает незавершённые прогоны, профиль открывает меню. */
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth, can } from '../auth'
import { useApi } from '../hooks'
import { useI18n } from '../i18n-context'
import LanguageSwitcher from '../components/LanguageSwitcher'
import TopNav from '../components/TopNav'
import {
  ArrowSquareOut, Bell, CaretDown, MagnifyingGlass, SignOut, UserCircle, X,
} from '../icons'

export default function Topbar({ query, onQuery }) {
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const runs = useApi(() => api.runs(50))
  const { t } = useI18n()
  const [panel, setPanel] = useState(null) // 'bell' | 'account' | null
  const [searchOpen, setSearchOpen] = useState(false)
  const inputRef = useRef(null)
  const wrapRef = useRef(null)

  const initials = (user?.display_name || user?.email || 'AD').slice(0, 2).toUpperCase()
  const name = user?.display_name || user?.email || ''

  useEffect(() => {
    function onKey(event) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setSearchOpen(true)
        setTimeout(() => inputRef.current?.focus(), 190)
      }
      if (event.key === 'Escape') {
        setPanel(null)
        setSearchOpen(false)
        inputRef.current?.blur()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    function onDown(event) {
      if (wrapRef.current && !wrapRef.current.contains(event.target)) {
        setPanel(null)
        setSearchOpen(false)
      }
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [])

  const alerts = (runs.data || []).filter((run) =>
    ['PARTIAL', 'ERROR', 'CANCELLED'].includes(run.status),
  )

  function submit(event) {
    if (event.key === 'Enter' && query) navigate('/runs')
  }

  function toggleSearch() {
    if (searchOpen) {
      setSearchOpen(false)
    } else {
      setSearchOpen(true)
      setTimeout(() => inputRef.current?.focus(), 190)
    }
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
          <TopNav compact={searchOpen} />

        <div className={`search-box${searchOpen ? ' is-open' : ''}`}>
          <button
            className="search-toggle"
            onClick={toggleSearch}
            aria-label={t('Поиск')}
            aria-expanded={searchOpen}
          >
            <MagnifyingGlass size={15} weight="bold" />
          </button>
          <input
            ref={inputRef}
            placeholder={t('Поиск по прогонам, моделям, инструментам…')}
            value={query}
            onChange={(event) => onQuery(event.target.value)}
            onKeyDown={submit}
            aria-label={t('Поиск')}
            tabIndex={searchOpen ? 0 : -1}
          />
          {searchOpen && query ? (
            <button className="search-clear" onClick={() => onQuery('')} aria-label={t('Очистить')}>
              <X size={12} weight="bold" />
            </button>
          ) : null}
        </div>
        </div>
      </div>

      <div className="topbar-actions">
        <LanguageSwitcher />

        <div style={{ position: 'relative' }}>
          <button
            className="icon-btn"
            aria-label={t('Уведомления') + (alerts.length ? `: ${alerts.length}` : '')}
            aria-expanded={panel === 'bell'}
            onClick={() => setPanel(panel === 'bell' ? null : 'bell')}
          >
            <Bell size={15} weight="bold" />
            {alerts.length ? <span className="dot" /> : null}
          </button>

          {panel === 'bell' ? (
            <div className="popover" role="menu">
              <div className="popover-head">
                {t('Незавершённые прогоны')}
                <span className="dim mono-sm">{alerts.length}</span>
              </div>
              {alerts.length === 0 ? (
                <div className="popover-empty">{t('Нет незавершённых прогонов')}.</div>
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
                    <span>{run.label}</span>
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
            onClick={() => setPanel(panel === 'account' ? null : 'account')}
          >
            <span className="avatar">{initials}</span>
            <span className="profile-meta">
              <span className="profile-name">{name}</span>
              <span className="profile-role">{user?.role}</span>
            </span>
            <CaretDown size={11} weight="bold" className="profile-caret" />
          </button>

          {panel === 'account' ? (
            <div className="popover" role="menu" style={{ minWidth: 264 }}>
              <div className="account-head">
                <span className="avatar avatar-lg">{initials}</span>
                <span className="account-text">
                  <span className="account-name">{name}</span>
                  <span className="account-mail">{user?.email}</span>
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
              <button className="popover-item" onClick={logout}>
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

/** Верхняя полоса: логотип, меню, поиск, уведомления, профиль.
 *
 *  Структура слева направо: бренд, центральная группа «меню + поиск» (центр
 *  полосы), правая группа «язык, колокольчик, профиль».
 *
 *  ПРАВИЛА ПОВЕДЕНИЯ, которые здесь закреплены замером:
 *
 *  1. Открыт максимум ОДИН поповер. Раньше язык жил своим состоянием внутри
 *     LanguageSwitcher, поэтому клик по колокольчику оставлял меню языка
 *     открытым — на экране было два меню, а Escape закрывал не всё.
 *
 *  2. Escape закрывает любой поповер и поиск, но НЕ стирает введённый запрос:
 *     пользователь мог свернуть поиск, чтобы посмотреть результаты.
 *
 *  3. Закрытие поиска СБРАСЫВАЕТ фильтр. Раньше запрос оставался в состоянии
 *     App и продолжал фильтровать список при невидимом поиске — на экране
 *     были пустые «Прогоны» без видимой причины.
 *
 *  4. Поиск с непустым запросом не схлопывается в иконку, пока его не
 *     очистят: иначе активный фильтр становится невидимым. */
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
  const [panel, setPanel] = useState(null) // 'bell' | 'account' | 'lang' | null
  const [searchOpen, setSearchOpen] = useState(false)
  const inputRef = useRef(null)
  const wrapRef = useRef(null)

  const initials = (user?.display_name || user?.email || 'AD').slice(0, 2).toUpperCase()
  const name = user?.display_name || user?.email || ''

  useEffect(() => {
    function onKey(event) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setPanel(null)
        setSearchOpen(true)
        setTimeout(() => inputRef.current?.focus(), 190)
      }
      if (event.key === 'Escape') {
        setPanel(null)
        closeSearch()
        inputRef.current?.blur()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // query в зависимостях обязателен: без него замыкание держит значение из
    // первого рендера (пустую строку), и closeSearch() не снимал фильтр —
    // поиск визуально закрывался, а список оставался отфильтрованным.
  }, [query, onQuery])

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

  /** Закрыть поиск и снять фильтр: пустой список без видимого поиска
   *  выглядит как поломка, а не как отфильтрованный результат. */
  function closeSearch() {
    setSearchOpen(false)
    if (query) onQuery('')
  }

  function submit(event) {
    if (event.key === 'Enter' && query) navigate('/runs')
  }

  function toggleSearch() {
    if (searchOpen) {
      closeSearch()
    } else {
      setPanel(null)
      setSearchOpen(true)
      setTimeout(() => inputRef.current?.focus(), 190)
    }
  }

  /** Единственная точка переключения поповеров — гарантирует «один за раз». */
  function togglePanel(which) {
    setPanel((current) => (current === which ? null : which))
    if (!searchOpen) return
    closeSearch()
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
        <div className={`topbar-center-inner${searchOpen ? ' is-searching' : ''}`}>
          <TopNav />

          <div className={`search-box${searchOpen ? ' is-open' : ''}`}>
            <button
              className="search-toggle"
              onClick={toggleSearch}
              aria-label={searchOpen ? t('Свернуть поиск') : t('Поиск')}
              aria-expanded={searchOpen}
              title={t('Поиск (Ctrl+K)')}
            >
              <MagnifyingGlass size={15} weight="bold" />
            </button>
            <input
              ref={inputRef}
              placeholder={t('Поиск по прогонам…')}
              value={query}
              onChange={(event) => onQuery(event.target.value)}
              onKeyDown={submit}
              aria-label={t('Поиск')}
              tabIndex={searchOpen ? 0 : -1}
            />
            {searchOpen && query ? (
              <button
                className="search-clear"
                onClick={() => {
                  onQuery('')
                  inputRef.current?.focus()
                }}
                aria-label={t('Очистить')}
              >
                <X size={12} weight="bold" />
              </button>
            ) : null}
          </div>
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

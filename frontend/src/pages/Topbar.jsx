import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth, can } from '../auth'
import { useApi } from '../hooks'
import { ArrowSquareOut, Bell, MagnifyingGlass, SignOut, UserCircle, X } from '../icons'

/** Sticky top bar: search, notifications, account menu.
 *
 *  Every control here does something. A decorative bell and a dead "⌘K" badge
 *  are worse than no control at all, so each one is wired:
 *    - the search field is focused by ⌘K / Ctrl+K and filters the runs list;
 *    - the bell opens a list of runs that ended without COMPLETE;
 *    - the avatar opens account actions. */
export default function Topbar({ query, onQuery }) {
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const runs = useApi(() => api.runs(50))
  const [panel, setPanel] = useState(null) // 'bell' | 'account' | null
  const inputRef = useRef(null)
  const wrapRef = useRef(null)

  const initials = (user?.display_name || user?.email || 'AD').slice(0, 2).toUpperCase()

  // ⌘K / Ctrl+K focuses the search field, which is what the badge promises.
  useEffect(() => {
    function onKey(event) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        inputRef.current?.focus()
      }
      if (event.key === 'Escape') {
        setPanel(null)
        inputRef.current?.blur()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // Close popovers on an outside click.
  useEffect(() => {
    function onDown(event) {
      if (wrapRef.current && !wrapRef.current.contains(event.target)) setPanel(null)
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

  return (
    <div className="topbar" ref={wrapRef}>
      <div className="search-box">
        <MagnifyingGlass size={15} weight="bold" />
        <input
          ref={inputRef}
          placeholder="Поиск по прогонам, моделям, инструментам…"
          value={query}
          onChange={(event) => onQuery(event.target.value)}
          onKeyDown={submit}
          aria-label="Поиск"
        />
        {query ? (
          <button
            className="icon-btn"
            style={{ width: 22, height: 22, border: 0, background: 'transparent' }}
            onClick={() => onQuery('')}
            aria-label="Очистить"
          >
            <X size={13} weight="bold" />
          </button>
        ) : (
          <span className="kbd" title="Фокус на поиске">⌘K</span>
        )}
      </div>

      <div className="topbar-actions">
        <div style={{ position: 'relative' }}>
          <button
            className="icon-btn"
            aria-label={`Уведомления${alerts.length ? `: ${alerts.length}` : ''}`}
            aria-expanded={panel === 'bell'}
            onClick={() => setPanel(panel === 'bell' ? null : 'bell')}
          >
            <Bell size={15} weight="bold" />
            {alerts.length ? <span className="dot" /> : null}
          </button>

          {panel === 'bell' ? (
            <div className="popover" role="menu">
              <div className="popover-head">
                Незавершённые прогоны
                <span className="dim mono-sm">{alerts.length}</span>
              </div>
              {alerts.length === 0 ? (
                <div className="popover-empty">
                  Все прогоны завершились полно. Предупреждать не о чем.
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
            className="avatar"
            aria-label="Аккаунт"
            aria-expanded={panel === 'account'}
            onClick={() => setPanel(panel === 'account' ? null : 'account')}
          >
            {initials}
          </button>

          {panel === 'account' ? (
            <div className="popover" role="menu" style={{ minWidth: 240 }}>
              <div className="popover-head" style={{ display: 'block' }}>
                <div>{user?.display_name || 'Администратор'}</div>
                <div className="dim mono-sm" style={{ fontWeight: 400 }}>{user?.email}</div>
                <div className="dim" style={{ fontSize: 11, marginTop: 2 }}>
                  роль: {user?.role}
                </div>
              </div>
              <button
                className="popover-item"
                onClick={() => {
                  setPanel(null)
                  navigate('/settings')
                }}
              >
                <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <UserCircle size={14} weight="bold" />
                  Настройки и пароль
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
                  <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <ArrowSquareOut size={14} weight="bold" />
                    Новый прогон
                  </span>
                </button>
              ) : null}
              <button className="popover-item" onClick={logout}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <SignOut size={14} weight="bold" />
                  Выйти
                </span>
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}

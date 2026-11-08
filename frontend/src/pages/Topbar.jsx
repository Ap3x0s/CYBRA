import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { Bell, MagnifyingGlass, X } from '../icons'

/** Sticky top bar: global search entry point, notifications, account mark.
 *
 *  Search is a real control, not decoration: it filters by run label, model or
 *  tool from any screen via the runs list, which is where the data lives. */
export default function Topbar({ query, onQuery }) {
  const navigate = useNavigate()
  const { user } = useAuth()
  const initials = (user?.display_name || user?.email || 'AD').slice(0, 2).toUpperCase()

  function onKeyDown(event) {
    if (event.key === 'Enter' && query) {
      navigate('/runs')
    }
  }

  return (
    <div className="topbar">
      <div className="search-box">
        <MagnifyingGlass size={15} weight="bold" />
        <input
          placeholder="Поиск по прогонам, моделям, инструментам…"
          value={query}
          onChange={(event) => onQuery(event.target.value)}
          onKeyDown={onKeyDown}
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
          <span className="kbd">⌘K</span>
        )}
      </div>

      <div className="topbar-actions">
        <button className="icon-btn" aria-label="Уведомления">
          <Bell size={15} weight="bold" />
        </button>
        <div className="avatar" title={user?.email}>
          {initials}
        </div>
      </div>
    </div>
  )
}

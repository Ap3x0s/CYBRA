import { NavLink } from 'react-router-dom'
import { can, useAuth } from '../auth'
import {
  ChartLineUp, Database, Gear, ListChecks, SignOut, Stack, UserCircle,
} from '../icons'

const ITEMS = [
  { to: '/', label: 'Обзор', Icon: Stack, end: true },
  { to: '/runs', label: 'Прогоны', Icon: ListChecks },
  { to: '/datasets', label: 'Датасеты', Icon: Database },
  { to: '/models', label: 'Модели', Icon: ChartLineUp },
  { to: '/metrics', label: 'Метрики', Icon: UserCircle },
]

const ADMIN_ITEMS = [{ to: '/settings', label: 'Настройки', Icon: Gear }]

export default function Sidebar() {
  const { user, logout } = useAuth()

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">CY</div>
        <div>
          <div className="brand-name">CYBRA</div>
          <div className="brand-sub">security console</div>
        </div>
      </div>

      <nav className="nav">
        <div className="nav-label">Работа</div>
        {ITEMS.map(({ to, label, Icon, end }) => (
          <NavLink key={to} to={to} end={end}>
            <Icon size={16} weight="regular" />
            {label}
          </NavLink>
        ))}
        {can(user, 'admin') ? (
          <>
            <div className="nav-label" style={{ marginTop: 14 }}>
              Админ
            </div>
            {ADMIN_ITEMS.map(({ to, label, Icon }) => (
              <NavLink key={to} to={to}>
                <Icon size={16} weight="regular" />
                {label}
              </NavLink>
            ))}
          </>
        ) : null}
      </nav>

      <div style={{ marginTop: 'auto', padding: '0 6px' }}>
        <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 2 }}>
          {user?.display_name || user?.email}
        </div>
        <div
          className="dim"
          style={{
            fontSize: 10.5,
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            marginBottom: 10,
          }}
        >
          {user?.role}
        </div>
        <button className="btn ghost small" style={{ width: '100%' }} onClick={logout}>
          <SignOut size={14} weight="bold" />
          Выйти
        </button>
      </div>
    </aside>
  )
}

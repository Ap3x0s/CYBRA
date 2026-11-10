import { NavLink } from 'react-router-dom'
import { can, useAuth } from '../auth'
import {
  ChartLineUp, Circuitry, Database, Gear, ListChecks, SignOut, SquaresFour,
} from '../icons'
import { useI18n } from '../i18n-context'

// The icons are read as a sentence: what you look at, what you run, what it
// runs against, and how you measure. 'Модели' used to carry a line chart and
// 'Метрики' a person — the chart belonged to the metrics screen, and the
// person collided with the account avatar in the top bar.
const ITEMS = [
  { to: '/', label: 'Обзор', Icon: SquaresFour, end: true },
  { to: '/runs', label: 'Прогоны', Icon: ListChecks },
  { to: '/datasets', label: 'Датасеты', Icon: Database },
  { to: '/models', label: 'Модели', Icon: Circuitry },
  { to: '/metrics', label: 'Метрики', Icon: ChartLineUp },
]

const ADMIN_ITEMS = [{ to: '/settings', label: 'Настройки', Icon: Gear }]

export default function Sidebar() {
  const { t } = useI18n()
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
        <div className="nav-label">{t("Работа")}</div>
        {ITEMS.map(({ to, label, Icon, end }) => (
          <NavLink key={to} to={to} end={end}>
            <Icon size={16} weight="regular" />
            {t(label)}
          </NavLink>
        ))}
        {can(user, 'admin') ? (
          <>
            <div className="nav-label" style={{ marginTop: 14 }}>
              {t("Админ")}
            </div>
            {ADMIN_ITEMS.map(({ to, label, Icon }) => (
              <NavLink key={to} to={to}>
                <Icon size={16} weight="regular" />
                {t(label)}
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
          {t(user?.role)}
        </div>
        <button className="btn ghost small" style={{ width: '100%' }} onClick={logout}>
          <SignOut size={14} weight="bold" />
          {t("Выйти")}
        </button>
      </div>
    </aside>
  )
}

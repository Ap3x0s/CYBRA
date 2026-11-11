/** Горизонтальная навигация с иконками.
 *
 *  Подпись видна, пока поиск закрыт. Когда поиск раскрывается, подписи
 *  уезжают влево и схлопываются — остаются только значки. Ширина анимируется
 *  через max-width, поэтому пункты «сжимаются», а не исчезают скачком. */
import { NavLink } from 'react-router-dom'
import { can, useAuth } from '../auth'
import { useI18n } from '../i18n-context'
import {
  ChartLineUp, Circuitry, Database, Gear, ListChecks, SquaresFour,
} from '../icons'

const ITEMS = [
  { to: '/', key: 'Обзор', Icon: SquaresFour, end: true },
  { to: '/runs', key: 'Прогоны', Icon: ListChecks },
  { to: '/datasets', key: 'Датасеты', Icon: Database },
  { to: '/models', key: 'Модели', Icon: Circuitry },
  { to: '/metrics', key: 'Метрики', Icon: ChartLineUp },
]

const ADMIN = { to: '/settings', key: 'Настройки', Icon: Gear }

export default function TopNav() {
  const { user } = useAuth()
  const { t } = useI18n()

  const render = (item) => (
    <NavLink key={item.to} to={item.to} end={item.end} data-label={t(item.key)}>
      <item.Icon size={16} weight="regular" />
      <span className="topnav-label">{t(item.key)}</span>
    </NavLink>
  )

  return (
    <nav className="topnav">
      {ITEMS.map(render)}
      {can(user, 'admin') ? render(ADMIN) : null}
    </nav>
  )
}

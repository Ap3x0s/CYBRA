/** Горизонтальная навигация с иконками.
 *
 *  Иконки заданы семантическими именами и живут в AppIcon — там же они
 *  окрашиваются в акцентный цвет и там же выбирается источник (Phosphor или
 *  кастомный SVG). Компонент не знает, откуда картинка, поэтому набор можно
 *  менять в одном месте.
 *
 *  Подписи статичны: видны всегда, независимо от состояния поиска и ширины
 *  экрана. */
import { NavLink } from 'react-router-dom'
import { can, useAuth } from '../auth'
import { useI18n } from '../i18n-context'
import AppIcon from './AppIcon'

const ITEMS = [
  { to: '/', key: 'Обзор', icon: 'overview', end: true },
  { to: '/runs', key: 'Прогоны', icon: 'runs' },
  { to: '/datasets', key: 'Датасеты', icon: 'datasets' },
  { to: '/models', key: 'Модели', icon: 'models' },
  { to: '/metrics', key: 'Метрики', icon: 'metrics' },
]

const ADMIN = { to: '/settings', key: 'Настройки', icon: 'settings' }

export default function TopNav() {
  const { user } = useAuth()
  const { t } = useI18n()

  const render = (item) => (
    <NavLink key={item.to} to={item.to} end={item.end} data-label={t(item.key)}>
      <AppIcon name={item.icon} size={18} />
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

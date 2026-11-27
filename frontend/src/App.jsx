import { Navigate, Route, Routes } from 'react-router-dom'
import { can, useAuth } from './auth'
import { Loading } from './components'
import AnimatedBackdrop from './components/AnimatedBackdrop'
import { useI18n } from './i18n-context'
import Datasets from './pages/Datasets'
import Dashboard from './pages/Dashboard'
import Login from './pages/Login'
import Metrics from './pages/Metrics'
import Models from './pages/Models'
import NewRun from './pages/NewRun'
import RunDetail from './pages/RunDetail'
import RunReport from './pages/RunReport'
import Runs from './pages/Runs'
import Settings from './pages/Settings'
import Topbar from './pages/Topbar'

function Protected({ children }) {
  const { user, ready } = useAuth()
  const { t } = useI18n()
  if (!ready) return <Loading label={t('Проверка сессии…')} />
  if (!user) return <Navigate to="/login" replace />
  return children
}

function Admin({ children }) {
  const { user } = useAuth()
  if (!can(user, 'admin')) return <Navigate to="/" replace />
  return children
}

/** Кому вообще есть что делать в «Настройках».
 *
 * Два случая: админ (управление пользователями) и любой, у кого есть
 * локальный пароль (смена своего). У учётки из Keycloak пароля в нашей
 * базе нет — ей там нечего делать, и форма только вводила бы в
 * заблуждение.
 *
 * Проверка не про безопасность — сервер откажет и без неё. Она про
 * честность интерфейса: не показывать дверь, которая не открывается.
 */
function CanSeeSettings({ children }) {
  const { user } = useAuth()
  if (can(user, 'admin') || user?.has_password) return children
  return <Navigate to="/" replace />
}

export default function App() {
  const { user, ready } = useAuth()
  const { t } = useI18n()

  if (!ready) return <Loading label={t('Проверка сессии…')} />

  return (
    <Routes>
      <Route
        path="/login"
        element={user ? <Navigate to="/" replace /> : <Login />}
      />
      <Route
        path="/runs/:id/report"
        element={
          <Protected>
            <RunReport />
          </Protected>
        }
      />
      <Route
        path="*"
        element={
          <Protected>
            <AnimatedBackdrop />
            <div className="shell">
              <div style={{ minWidth: 0 }}>
                <Topbar />
                <main className="main">
                  <Routes>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/runs" element={<Runs />} />
                    <Route path="/runs/new" element={<NewRun />} />
                    <Route path="/runs/:id" element={<RunDetail />} />
                    <Route path="/datasets" element={<Datasets />} />
                    <Route path="/models" element={<Models />} />
                    <Route path="/metrics" element={<Metrics />} />
                    {/* «Настройки» — не админский маршрут.
                    
                        Здесь смена СВОЕГО пароля и список инструментов
                        окружения. Это нужно каждому, у кого есть локальный
                        пароль, — включая оператора. Управление
                        пользователями внутри страницы закрыто отдельно
                        (`can(user, 'admin')`), его видит только админ.
                    
                        Раньше маршрут был обёрнут в <Admin>, и оператор,
                        у которого пароль есть, не мог его сменить: пункт
                        меню вёл на страницу, а та молча возвращала на
                        главную. */}
                    <Route
                      path="/settings"
                      element={
                        <CanSeeSettings>
                          <Settings />
                        </CanSeeSettings>
                      }
                    />
                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Routes>
                </main>
              </div>
            </div>
          </Protected>
        }
      />
    </Routes>
  )
}

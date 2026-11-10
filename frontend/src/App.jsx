import { useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { can, useAuth } from './auth'
import { Loading } from './components'
import AnimatedBackdrop from './components/AnimatedBackdrop'
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
  if (!ready) return <Loading label="Проверка сессии…" />
  if (!user) return <Navigate to="/login" replace />
  return children
}

function Admin({ children }) {
  const { user } = useAuth()
  if (!can(user, 'admin')) return <Navigate to="/" replace />
  return children
}

export default function App() {
  const { user, ready } = useAuth()
  // Search lives at the shell level so the top bar keeps its value while the
  // user moves between screens.
  const [query, setQuery] = useState('')

  if (!ready) return <Loading label="Проверка сессии…" />

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
                <Topbar query={query} onQuery={setQuery} />
                <main className="main">
                  <Routes>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/runs" element={<Runs query={query} />} />
                    <Route path="/runs/new" element={<NewRun />} />
                    <Route path="/runs/:id" element={<RunDetail />} />
                    <Route path="/datasets" element={<Datasets />} />
                    <Route path="/models" element={<Models />} />
                    <Route path="/metrics" element={<Metrics />} />
                    <Route
                      path="/settings"
                      element={
                        <Admin>
                          <Settings />
                        </Admin>
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

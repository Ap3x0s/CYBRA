import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AuthProvider } from './auth'
import { I18nProvider } from './i18n-context'
// SL UI Library component styles (vendored, MIT). Imported before the app sheet
// so the app's tokens and overrides win where the two touch.
import './sl-ui/sl-ui.css'
import './styles.css'
import './topbar-bar.css'
import './page-search.css'
import './select.css'

// Agentation is a development aid, not a product feature, and ships under the
// PolyForm Shield licence, which is not an open-source licence. It is therefore
// mounted only in dev builds behind both an env flag and import.meta.env.DEV,
// so it cannot reach a production bundle or a Docker image.
const Agentation =
  import.meta.env.DEV && import.meta.env.VITE_AGENTATION === '1'
    ? React.lazy(() =>
        import('agentation').then((module) => ({ default: module.Agentation })),
      )
    : null

// Without an endpoint the toolbar only writes to localStorage and the agent
// never sees the annotations. The local MCP server listens on 4747 by default.
const AGENTATION_ENDPOINT =
  import.meta.env.VITE_AGENTATION_ENDPOINT || 'http://localhost:4747'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <I18nProvider>
          <App />
          {Agentation ? (
            <React.Suspense fallback={null}>
              <Agentation endpoint={AGENTATION_ENDPOINT} appName="CYBRA" />
            </React.Suspense>
          ) : null}
        </I18nProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
)

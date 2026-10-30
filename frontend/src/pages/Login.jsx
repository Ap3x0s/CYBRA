import { useState } from 'react'
import { useAuth } from '../auth'
import { ErrorBox } from '../components'
import { ShieldCheck } from '../icons'
import { SlTextField } from '../sl-ui/react'

export default function Login() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email.trim(), password)
    } catch (problem) {
      setError(problem)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-wrap">
      <div className="login-card">
        <div className="brand" style={{ padding: 0, marginBottom: 22 }}>
          <div className="brand-mark">CY</div>
          <div>
            <div className="brand-name">CYBRA</div>
            <div className="brand-sub">LLM security console</div>
          </div>
        </div>

        <h1 style={{ fontSize: 20, marginBottom: 6 }}>Вход в консоль</h1>
        <p className="muted" style={{ fontSize: 13, marginTop: 0, marginBottom: 22 }}>
          Прогон бенчмарков безопасности моделей и отчёты для ИБ.
        </p>

        <ErrorBox error={error} />

        <form onSubmit={onSubmit}>
          <div style={{ marginBottom: 16 }}>
            <SlTextField
              label="Email"
              type="email"
              value={email}
              onChange={setEmail}
              help="Логин администратора печатается при первом старте сервера."
            />
          </div>
          <div style={{ marginBottom: 20 }}>
            <SlTextField
              label="Пароль"
              type="password"
              value={password}
              onChange={setPassword}
            />
          </div>
          <button className="btn primary" type="submit" style={{ width: '100%' }} disabled={busy}>
            <ShieldCheck size={16} weight="bold" />
            {busy ? 'Проверка…' : 'Войти'}
          </button>
        </form>
      </div>
    </div>
  )
}

import { useState } from 'react'
import { useAuth } from '../auth'
import { ErrorBox } from '../components'
import { SlTextField } from '../sl-ui/react'
import { useI18n } from '../i18n-context'
import markUrl from '../assets/cybra-mark.png'
import wordmarkUrl from '../assets/cybra-wordmark.png'

export default function Login() {
  const { login } = useAuth()
  const { t } = useI18n()
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
        {/* Шапка карточки по центру: логотип, заголовок и подзаголовок как
            одна композиция. Раньше фирменный знак был прижат влево, а под
            ним шёл текст тоже слева — карточка читалась перекошенной. */}
        <header className="login-head">
          <div className="brand brand-login">
            <img className="brand-logo-lg" src={markUrl} alt="" aria-hidden="true" />
            <div className="brand-text-lg">
              <img className="brand-word-img-lg" src={wordmarkUrl} alt="CYBRA" />
              <div className="brand-sub">cybersecurity benchmarks</div>
            </div>
          </div>

          <h1>{t('Вход в консоль')}</h1>
          <p className="login-lead">
            {t('Прогон бенчмарков безопасности моделей и отчёты для ИБ.')}
          </p>
        </header>

        <ErrorBox error={error} />

        <form onSubmit={onSubmit}>
          <div style={{ marginBottom: 16 }}>
            <SlTextField
              label={t('Email')}
              type="email"
              value={email}
              onChange={setEmail}
              help={t('Логин администратора печатается при первом старте сервера.')}
            />
          </div>
          <div style={{ marginBottom: 20 }}>
            <SlTextField
              label={t('Пароль')}
              type="password"
              value={password}
              onChange={setPassword}
            />
          </div>
          {/* Стрелка убрана по просьбе заказчика: кнопка с текстом и без
              значка выглядит спокойнее и не отвлекает от формы. */}
          <button className="btn primary login-submit" type="submit" disabled={busy}>
            {busy ? t('Проверка…') : t('Войти')}
          </button>
        </form>
      </div>
    </div>
  )
}

import { useEffect, useState } from 'react'
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
  const [sso, setSso] = useState(null)

  // Узнаём, настроен ли вход через корпоративный аккаунт.
  //
  // Почему через API, а не константой в сборке: фронтенд один и тот же
  // образ, а Keycloak есть не у всех. Если рисовать кнопку всегда, на
  // стендах без провайдера она ведёт в 404 — то есть выглядит поломкой
  // приложения, а не отсутствием настройки.
  useEffect(() => {
    let alive = true
    fetch('/api/v1/auth/oidc/enabled')
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (alive && data && data.enabled) setSso(data)
      })
      .catch(() => {
        /* Провайдер не настроен или недоступен — просто не показываем кнопку */
      })
    return () => {
      alive = false
    }
  }, [])

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

        {sso ? (
          <div className="login-sso">
            {/* Обычная ссылка, а не fetch: это переход браузера в Keycloak,
                а не запрос к API. fetch не покажет страницу провайдера и не
                уведёт на другой домен — вход бы просто не начался. */}
            <a className="btn sso-btn" href="/api/v1/auth/oidc/login">
              {t('Войти через корпоративный аккаунт')}
            </a>
            <p className="login-sso-hint">
              {t('Пароль вводится на стороне провайдера и нашему приложению не передаётся.')}
            </p>
            <div className="login-divider">
              <span>{t('или локальная учётная запись')}</span>
            </div>
          </div>
        ) : null}

        <ErrorBox error={error} />

        <form onSubmit={onSubmit}>
          <div className="login-field">
            <SlTextField
              label={t('Email')}
              type="email"
              value={email}
              onChange={setEmail}
              help={t('Логин администратора печатается при первом старте сервера.')}
            />
          </div>
          <div className="login-field login-field--last">
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

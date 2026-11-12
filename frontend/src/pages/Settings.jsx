import { useState } from 'react'
import { api } from '../api'
import { can, useAuth } from '../auth'
import { Banner, ErrorBox, Field, Pill, formatDate } from '../components'
import { PageSkeleton } from '../components/Skeletons'
import { useApi } from '../hooks'
import { useI18n } from '../i18n-context'
import Select from '../components/Select'

export default function Settings() {
  const { user } = useAuth()
  const { t } = useI18n()
  const users = useApi(() => (can(user, 'admin') ? api.users() : Promise.resolve([])))
  const caps = useApi(() => api.capabilities())

  const [error, setError] = useState(null)
  const [notice, setNotice] = useState('')
  const [form, setForm] = useState({ email: '', password: '', display_name: '', role: 'operator' })
  const [pwd, setPwd] = useState({ current_password: '', new_password: '' })

  if (users.loading || caps.loading) return <PageSkeleton variant="default" />

  async function createUser(event) {
    event.preventDefault()
    setError(null)
    try {
      await api.createUser(form)
      setNotice(t('Пользователь {email} создан', { email: form.email }))
      setForm({ email: '', password: '', display_name: '', role: 'operator' })
      users.reload()
    } catch (problem) {
      setError(problem)
    }
  }

  async function changePassword(event) {
    event.preventDefault()
    setError(null)
    try {
      await api.changePassword(pwd.current_password, pwd.new_password)
      setNotice(t('Пароль изменён'))
      setPwd({ current_password: '', new_password: '' })
    } catch (problem) {
      setError(problem)
    }
  }

  return (
    <div className="fade-in">
      <div className="page-head">
        <div>
          <h1>{t("Настройки")}</h1>
          <p>{t("Пользователи, пароль и состояние окружения.")}</p>
        </div>
      </div>

      <ErrorBox error={error} />
      {notice ? <Banner>{notice}</Banner> : null}

      <div className="grid grid-2">
        <div className="card">
          <h2 style={{ marginBottom: 14 }}>{t("Сменить свой пароль")}</h2>
          <form onSubmit={changePassword}>
            <Field label={t("Текущий пароль")}>
              <input
                className="input"
                type="password"
                value={pwd.current_password}
                onChange={(event) => setPwd((c) => ({ ...c, current_password: event.target.value }))}
                required
              />
            </Field>
            <Field label={t("Новый пароль")} help={t("Минимум 10 символов.")}>
              <input
                className="input"
                type="password"
                value={pwd.new_password}
                onChange={(event) => setPwd((c) => ({ ...c, new_password: event.target.value }))}
                minLength={10}
                required
              />
            </Field>
            <button className="btn primary">{t("Изменить пароль")}</button>
          </form>
        </div>

        <div className="card">
          <h2 style={{ marginBottom: 14 }}>{t("Окружение")}</h2>
          <table className="data">
            <thead>
              <tr>
                <th>{t("Инструмент")}</th>
                <th>{t("Тип")}</th>
                <th>{t("Статус")}</th>
                <th>{t("Версия")}</th>
              </tr>
            </thead>
            <tbody>
              {(caps.data || []).map((item) => (
                <tr key={item.tool}>
                  <td>{item.name}</td>
                  <td className="dim">{item.kind}</td>
                  <td>
                    <Pill tone={item.available ? 'ok' : 'warn'}>
                      {item.available ? t('готов') : t('не установлен')}
                    </Pill>
                  </td>
                  <td className="dim mono-sm">{item.version || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="banner" style={{ marginTop: 14, marginBottom: 0 }}>
            {t("Тяжёлые инструменты (garak, PyRIT, promptfoo, AgentDojo) не входят в exe-сборку. Установка:")} <span className="mono-sm">cybra setup --tools garak pyrit</span>
          </div>
        </div>
      </div>

      {can(user, 'admin') ? (
        <div style={{ display: 'grid', gap: 16, marginTop: 16 }}>
          <div className="card">
            <h2 style={{ marginBottom: 14 }}>{t("Новый пользователь")}</h2>
            <form onSubmit={createUser}>
              <div className="row">
                <Field label="Email">
                  <input
                    className="input"
                    type="email"
                    value={form.email}
                    onChange={(event) => setForm((c) => ({ ...c, email: event.target.value }))}
                    required
                  />
                </Field>
                <Field label={t("Имя")}>
                  <input
                    className="input"
                    value={form.display_name}
                    onChange={(event) => setForm((c) => ({ ...c, display_name: event.target.value }))}
                  />
                </Field>
                <Field label={t("Роль")}>
                  <Select
                    value={form.role}
                    onChange={(v) => setForm((c) => ({ ...c, role: v }))}
                    options={[
                      { value: 'viewer', label: `viewer — ${t('только просмотр')}` },
                      { value: 'operator', label: `operator — ${t('запуск прогонов')}` },
                      { value: 'admin', label: `admin — ${t('полный доступ')}` },
                    ]}
                  />
                </Field>
                <Field label={t("Пароль")} help={t("Минимум 10 символов.")}>
                  <input
                    className="input"
                    type="password"
                    value={form.password}
                    onChange={(event) => setForm((c) => ({ ...c, password: event.target.value }))}
                    minLength={10}
                    required
                  />
                </Field>
              </div>
              <button className="btn primary">{t("Создать")}</button>
            </form>
          </div>

          <div className="card">
            <h2 style={{ marginBottom: 14 }}>{t("Пользователи")}</h2>
            <table className="data">
              <thead>
                <tr>
                  <th>Email</th>
                  <th>{t("Имя")}</th>
                  <th>{t("Роль")}</th>
                  <th>{t("Активен")}</th>
                  <th>{t("Был вход")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(users.data || []).map((item) => (
                  <tr key={item.id}>
                    <td>{item.email}</td>
                    <td className="muted">{item.display_name}</td>
                    <td>
                      <Select
                        width={130}
                        value={item.role}
                        onChange={async (v) => {
                          await api.updateUser(item.id, { role: v })
                          users.reload()
                        }}
                        options={[
                          { value: 'viewer', label: 'viewer' },
                          { value: 'operator', label: 'operator' },
                          { value: 'admin', label: 'admin' },
                        ]}
                      />
                    </td>
                    <td>
                      <Pill tone={item.is_active ? 'ok' : 'idle'}>
                        {item.is_active ? t('да') : t('нет')}
                      </Pill>
                    </td>
                    <td className="dim">{formatDate(item.last_login_at)}</td>
                    <td>
                      {item.id !== user.id ? (
                        <button
                          className="btn ghost small"
                          onClick={async () => {
                            await api.updateUser(item.id, { is_active: !item.is_active })
                            users.reload()
                          }}
                        >
                          {item.is_active ? t('Отключить') : t('Включить')}
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  )
}

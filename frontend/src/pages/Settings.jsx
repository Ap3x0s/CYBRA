import { useState } from 'react'
import { api } from '../api'
import { can, useAuth } from '../auth'
import { Banner, ErrorBox, Field, Loading, Pill, formatDate } from '../components'
import { useApi } from '../hooks'

export default function Settings() {
  const { user } = useAuth()
  const users = useApi(() => (can(user, 'admin') ? api.users() : Promise.resolve([])))
  const caps = useApi(() => api.capabilities())

  const [error, setError] = useState(null)
  const [notice, setNotice] = useState('')
  const [form, setForm] = useState({ email: '', password: '', display_name: '', role: 'operator' })
  const [pwd, setPwd] = useState({ current_password: '', new_password: '' })

  if (users.loading || caps.loading) return <Loading />

  async function createUser(event) {
    event.preventDefault()
    setError(null)
    try {
      await api.createUser(form)
      setNotice(`Пользователь ${form.email} создан`)
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
      setNotice('Пароль изменён')
      setPwd({ current_password: '', new_password: '' })
    } catch (problem) {
      setError(problem)
    }
  }

  return (
    <div className="fade-in">
      <div className="page-head">
        <div>
          <h1>Настройки</h1>
          <p>Пользователи, пароль и состояние окружения.</p>
        </div>
      </div>

      <ErrorBox error={error} />
      {notice ? <Banner>{notice}</Banner> : null}

      <div className="grid grid-2">
        <div className="card">
          <h2 style={{ marginBottom: 14 }}>Сменить свой пароль</h2>
          <form onSubmit={changePassword}>
            <Field label="Текущий пароль">
              <input
                className="input"
                type="password"
                value={pwd.current_password}
                onChange={(event) => setPwd((c) => ({ ...c, current_password: event.target.value }))}
                required
              />
            </Field>
            <Field label="Новый пароль" help="Минимум 10 символов.">
              <input
                className="input"
                type="password"
                value={pwd.new_password}
                onChange={(event) => setPwd((c) => ({ ...c, new_password: event.target.value }))}
                minLength={10}
                required
              />
            </Field>
            <button className="btn primary">Изменить пароль</button>
          </form>
        </div>

        <div className="card">
          <h2 style={{ marginBottom: 14 }}>Окружение</h2>
          <table className="data">
            <thead>
              <tr>
                <th>Инструмент</th>
                <th>Тип</th>
                <th>Статус</th>
                <th>Версия</th>
              </tr>
            </thead>
            <tbody>
              {(caps.data || []).map((item) => (
                <tr key={item.tool}>
                  <td>{item.name}</td>
                  <td className="dim">{item.kind}</td>
                  <td>
                    <Pill tone={item.available ? 'ok' : 'warn'}>
                      {item.available ? 'готов' : 'не установлен'}
                    </Pill>
                  </td>
                  <td className="dim mono-sm">{item.version || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="banner" style={{ marginTop: 14, marginBottom: 0 }}>
            Тяжёлые инструменты (garak, PyRIT, promptfoo, AgentDojo) не входят в exe-сборку.
            Установка: <span className="mono-sm">cybra setup --tools garak pyrit</span>
          </div>
        </div>
      </div>

      {can(user, 'admin') ? (
        <>
          <div className="card">
            <h2 style={{ marginBottom: 14 }}>Новый пользователь</h2>
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
                <Field label="Имя">
                  <input
                    className="input"
                    value={form.display_name}
                    onChange={(event) => setForm((c) => ({ ...c, display_name: event.target.value }))}
                  />
                </Field>
                <Field label="Роль">
                  <select
                    className="select"
                    value={form.role}
                    onChange={(event) => setForm((c) => ({ ...c, role: event.target.value }))}
                  >
                    <option value="viewer">viewer — только просмотр</option>
                    <option value="operator">operator — запуск прогонов</option>
                    <option value="admin">admin — полный доступ</option>
                  </select>
                </Field>
                <Field label="Пароль" help="Минимум 10 символов.">
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
              <button className="btn primary">Создать</button>
            </form>
          </div>

          <div className="card">
            <h2 style={{ marginBottom: 14 }}>Пользователи</h2>
            <table className="data">
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Имя</th>
                  <th>Роль</th>
                  <th>Активен</th>
                  <th>Был вход</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(users.data || []).map((item) => (
                  <tr key={item.id}>
                    <td>{item.email}</td>
                    <td className="muted">{item.display_name}</td>
                    <td>
                      <select
                        className="select"
                        style={{ width: 130, padding: '4px 8px' }}
                        value={item.role}
                        onChange={async (event) => {
                          await api.updateUser(item.id, { role: event.target.value })
                          users.reload()
                        }}
                      >
                        <option value="viewer">viewer</option>
                        <option value="operator">operator</option>
                        <option value="admin">admin</option>
                      </select>
                    </td>
                    <td>
                      <Pill tone={item.is_active ? 'ok' : 'idle'}>
                        {item.is_active ? 'да' : 'нет'}
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
                          {item.is_active ? 'Отключить' : 'Включить'}
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </div>
  )
}

import { useState } from 'react'
import { api } from '../api'
import { can, useAuth } from '../auth'
import { Banner, ErrorBox, Field, Loading, Pill } from '../components'
import { useApi } from '../hooks'

export default function Models() {
  const { user } = useAuth()
  const endpoints = useApi(() => api.endpoints())
  const targets = useApi(() => api.targets())

  const [showEndpoint, setShowEndpoint] = useState(false)
  const [showTarget, setShowTarget] = useState(false)
  const [error, setError] = useState(null)
  const [probe, setProbe] = useState({})

  if (endpoints.loading || targets.loading) return <Loading />

  async function runProbe(id) {
    setProbe((current) => ({ ...current, [id]: { busy: true } }))
    try {
      const result = await api.probeEndpoint(id)
      setProbe((current) => ({ ...current, [id]: result }))
    } catch (problem) {
      setProbe((current) => ({ ...current, [id]: { ok: false, detail: problem.message } }))
    }
  }

  return (
    <div className="fade-in">
      <div className="page-head">
        <div>
          <h1>Модели и эндпоинты</h1>
          <p>
            Эндпоинт — это OpenAI-совместимый сервер (LiteLLM, OpenWebUI, vLLM). Модель — конкретный
            ID за этим сервером; у каждой модели свои переключатели совместимости.
          </p>
        </div>
        {can(user, 'operator') ? (
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn ghost" onClick={() => setShowEndpoint((value) => !value)}>
              + Эндпоинт
            </button>
            <button className="btn primary" onClick={() => setShowTarget((value) => !value)}>
              + Модель
            </button>
          </div>
        ) : null}
      </div>

      <ErrorBox error={error} />

      {showEndpoint && can(user, 'operator') ? (
        <EndpointForm
          onDone={() => {
            setShowEndpoint(false)
            endpoints.reload()
          }}
          onError={setError}
        />
      ) : null}

      {showTarget && can(user, 'operator') ? (
        <TargetForm
          endpoints={endpoints.data || []}
          onDone={() => {
            setShowTarget(false)
            targets.reload()
          }}
          onError={setError}
        />
      ) : null}

      <div className="card">
        <div className="card-head">
          <h2>Эндпоинты</h2>
          <span className="dim mono-sm">{(endpoints.data || []).length}</span>
        </div>
        {(endpoints.data || []).length === 0 ? (
          <div className="empty">Эндпоинтов нет. Добавьте первый — например свой LiteLLM или OpenWebUI.</div>
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>Название</th>
                <th>URL</th>
                <th>Ключ</th>
                <th>TLS</th>
                <th>Проверка</th>
              </tr>
            </thead>
            <tbody>
              {(endpoints.data || []).map((endpoint) => (
                <tr key={endpoint.id}>
                  <td>{endpoint.name}</td>
                  <td className="mono-sm dim">{endpoint.chat_url || endpoint.base_url + '/chat/completions'}</td>
                  <td>
                    {endpoint.has_secret ? (
                      <Pill tone="ok">задан …{endpoint.secret_hint}</Pill>
                    ) : (
                      <Pill tone="idle">без ключа</Pill>
                    )}
                  </td>
                  <td className="dim">{endpoint.verify_tls ? 'проверяется' : 'отключена'}</td>
                  <td>
                    <button className="btn ghost small" onClick={() => runProbe(endpoint.id)}>
                      {probe[endpoint.id]?.busy ? 'Проверка…' : 'Проверить связь'}
                    </button>
                    {probe[endpoint.id] && !probe[endpoint.id].busy ? (
                      <div
                        className="mono-sm"
                        style={{ marginTop: 6, color: probe[endpoint.id].ok ? 'var(--accent)' : 'var(--danger)' }}
                      >
                        {probe[endpoint.id].ok ? 'связь есть' : probe[endpoint.id].detail}
                      </div>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <div className="card-head">
          <h2>Модели</h2>
          <span className="dim mono-sm">{(targets.data || []).length}</span>
        </div>
        {(targets.data || []).length === 0 ? (
          <div className="empty">Моделей нет. Добавьте ID модели, доступный на эндпоинте.</div>
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>Модель</th>
                <th>ID</th>
                <th>Эндпоинт</th>
                <th>Группа</th>
                <th>Совместимость</th>
                {can(user, 'operator') ? <th /> : null}
              </tr>
            </thead>
            <tbody>
              {(targets.data || []).map((target) => (
                <tr key={target.id}>
                  <td>{target.label || target.model_id}</td>
                  <td className="mono-sm dim">{target.model_id}</td>
                  <td className="muted">{target.endpoint_name}</td>
                  <td className="dim">{target.group_name || '—'}</td>
                  <td className="dim mono-sm" style={{ fontSize: 11 }}>
                    {target.token_parameter}
                    {target.temperature === null ? ' · temp:omit' : ''}
                    {target.developer_as_system ? ' · dev→sys' : ''}
                    {(target.drop_params || []).length
                      ? ` · drop:${target.drop_params.join(',')}`
                      : ''}
                  </td>
                  {can(user, 'operator') ? (
                    <td>
                      <button
                        className="btn ghost small"
                        onClick={async () => {
                          await api.deleteTarget(target.id)
                          targets.reload()
                        }}
                      >
                        Удалить
                      </button>
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

function EndpointForm({ onDone, onError }) {
  const [form, setForm] = useState({
    name: '',
    base_url: 'http://localhost:4000/v1',
    chat_url: '',
    api_key: '',
    verify_tls: true,
    notes: '',
  })
  const [busy, setBusy] = useState(false)

  const update = (key) => (event) => {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value
    setForm((current) => ({ ...current, [key]: value }))
  }

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    try {
      await api.createEndpoint(form)
      onDone()
    } catch (problem) {
      onError(problem)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card" onSubmit={submit}>
      <div className="card-head">
        <h2>Новый эндпоинт</h2>
      </div>
      <div className="row">
        <Field label="Название">
          <input className="input" value={form.name} onChange={update('name')} required />
        </Field>
        <Field label="Base URL" help="Без /chat/completions — он добавится сам.">
          <input className="input" value={form.base_url} onChange={update('base_url')} required />
        </Field>
      </div>
      <div className="row">
        <Field label="Полный URL метода" help="Необязательно. Приоритетнее base URL.">
          <input className="input" value={form.chat_url} onChange={update('chat_url')} placeholder="http://host/v1/chat/completions" />
        </Field>
        <Field label="API-ключ" help="Шифруется; в ответах API не показывается.">
          <input className="input" type="password" value={form.api_key} onChange={update('api_key')} autoComplete="off" />
        </Field>
      </div>
      <label className="checkbox" style={{ marginBottom: 14 }}>
        <input type="checkbox" checked={form.verify_tls} onChange={update('verify_tls')} />
        Проверять TLS-сертификат
      </label>
      <button className="btn primary" disabled={busy}>
        {busy ? 'Сохранение…' : 'Добавить эндпоинт'}
      </button>
    </form>
  )
}

function TargetForm({ endpoints, onDone, onError }) {
  const [form, setForm] = useState({
    endpoint_id: endpoints[0]?.id || '',
    model_id: '',
    label: '',
    group_name: '',
    temperature: 0,
    token_parameter: 'max_tokens',
    developer_as_system: false,
  })
  const [busy, setBusy] = useState(false)

  const update = (key) => (event) => {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value
    setForm((current) => ({ ...current, [key]: value }))
  }

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    try {
      await api.createTarget({
        ...form,
        endpoint_id: Number(form.endpoint_id),
        temperature: Number(form.temperature),
      })
      onDone()
    } catch (problem) {
      onError(problem)
    } finally {
      setBusy(false)
    }
  }

  if (endpoints.length === 0) return <Banner tone="warn">Сначала добавьте эндпоинт.</Banner>

  return (
    <form className="card" onSubmit={submit}>
      <div className="card-head">
        <h2>Новая модель</h2>
      </div>
      <div className="row">
        <Field label="Эндпоинт">
          <select className="select" value={form.endpoint_id} onChange={update('endpoint_id')}>
            {endpoints.map((endpoint) => (
              <option key={endpoint.id} value={endpoint.id}>
                {endpoint.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="ID модели" help="Именно то имя, которое принимает сервер.">
          <input className="input" value={form.model_id} onChange={update('model_id')} required />
        </Field>
      </div>
      <div className="row">
        <Field label="Отображаемое имя">
          <input className="input" value={form.label} onChange={update('label')} />
        </Field>
        <Field label="Группа" help="Для сравнения пула моделей в графиках.">
          <input className="input" value={form.group_name} onChange={update('group_name')} />
        </Field>
        <Field label="Параметр лимита">
          <select className="select" value={form.token_parameter} onChange={update('token_parameter')}>
            <option value="max_tokens">max_tokens</option>
            <option value="max_completion_tokens">max_completion_tokens</option>
          </select>
        </Field>
      </div>
      <label className="checkbox" style={{ marginBottom: 14 }}>
        <input type="checkbox" checked={form.developer_as_system} onChange={update('developer_as_system')} />
        Заменять роль developer на system (фиксируется в manifest)
      </label>
      <button className="btn primary" disabled={busy}>
        {busy ? 'Сохранение…' : 'Добавить модель'}
      </button>
    </form>
  )
}

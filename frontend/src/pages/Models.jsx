import { useState } from 'react'
import { api } from '../api'
import { can, useAuth } from '../auth'
import { Banner, ErrorBox, Field, Pill } from '../components'
import PageSearch from '../components/PageSearch'
import { PageSkeleton } from '../components/Skeletons'
import { useApi } from '../hooks'
import { useI18n } from '../i18n-context'

export default function Models() {
  const { user } = useAuth()
  const { t } = useI18n()
  const endpoints = useApi(() => api.endpoints())
  const targets = useApi(() => api.targets())

  // Поиск на странице фильтрует оба списка: и эндпоинты, и модели. Раньше
  // общий поиск в шапке сюда вообще не доходил — на этой странице он был
  // мёртвой кнопкой.
  const [query, setQuery] = useState('')

  const [showEndpoint, setShowEndpoint] = useState(false)
  const [showTarget, setShowTarget] = useState(false)
  const [error, setError] = useState(null)
  const [probe, setProbe] = useState({})

  if (endpoints.loading || targets.loading) return <PageSkeleton variant="dashboard" />

  const needle = query.trim().toLowerCase()
  const matches = (...fields) =>
    !needle || fields.filter(Boolean).join(' ').toLowerCase().includes(needle)

  const endpointList = (endpoints.data || []).filter((endpoint) =>
    matches(endpoint.name, endpoint.base_url, endpoint.chat_url),
  )
  const targetList = (targets.data || []).filter((target) =>
    matches(target.label, target.model_id, target.endpoint_name, target.group_name),
  )

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
          <h1>{t("Модели и эндпоинты")}</h1>
          <p>
            {t("Эндпоинт — это OpenAI-совместимый сервер (LiteLLM, OpenWebUI, vLLM). Модель — конкретный ID за этим сервером; у каждой модели свои переключатели совместимости.")}
          </p>
        </div>
        {can(user, 'operator') ? (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <PageSearch
              value={query}
              onChange={setQuery}
              placeholder="Поиск по моделям…"
              width={260}
            />
            <button className="btn ghost" onClick={() => setShowEndpoint((value) => !value)}>
              + {t('Эндпоинт')}
            </button>
            <button className="btn primary" onClick={() => setShowTarget((value) => !value)}>
              + {t('Модель')}
            </button>
          </div>
        ) : (
          <PageSearch
            value={query}
            onChange={setQuery}
            placeholder="Поиск по моделям…"
            width={260}
          />
        )}
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
          <h2>{t("Эндпоинты")}</h2>
          <span className="dim mono-sm">
            {needle ? `${endpointList.length} / ${(endpoints.data || []).length}`
                    : endpointList.length}
          </span>
        </div>
        {endpointList.length === 0 ? (
          needle ? (
            <div className="empty">{t("Ничего не найдено по запросу")} «{query.trim()}».</div>
          ) : (
            <div className="empty">{t("Эндпоинтов нет. Добавьте первый — например свой LiteLLM или OpenWebUI.")}</div>
          )
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>{t("Название")}</th>
                <th>URL</th>
                <th>{t("Ключ")}</th>
                <th>TLS</th>
                <th>{t("Проверка")}</th>
              </tr>
            </thead>
            <tbody>
              {endpointList.map((endpoint) => (
                <tr key={endpoint.id}>
                  <td>{endpoint.name}</td>
                  <td className="mono-sm dim">{endpoint.chat_url || endpoint.base_url + '/chat/completions'}</td>
                  <td>
                    {endpoint.has_secret ? (
                      <Pill tone="ok">{t('задан')} …{endpoint.secret_hint}</Pill>
                    ) : (
                      <Pill tone="idle">{t("без ключа")}</Pill>
                    )}
                  </td>
                  <td className="dim">{endpoint.verify_tls ? t('проверяется') : t('отключена')}</td>
                  <td>
                    <button className="btn ghost small" onClick={() => runProbe(endpoint.id)}>
                      {probe[endpoint.id]?.busy ? t('Проверка…') : t('Проверить связь')}
                    </button>
                    {probe[endpoint.id] && !probe[endpoint.id].busy ? (
                      <div
                        className="mono-sm"
                        style={{ marginTop: 6, color: probe[endpoint.id].ok ? 'var(--accent)' : 'var(--danger)' }}
                      >
                        {probe[endpoint.id].ok ? t('связь есть') : probe[endpoint.id].detail}
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
          <h2>{t("Модели")}</h2>
          <span className="dim mono-sm">
            {needle ? `${targetList.length} / ${(targets.data || []).length}`
                    : targetList.length}
          </span>
        </div>
        {targetList.length === 0 ? (
          needle ? (
            <div className="empty">{t("Ничего не найдено по запросу")} «{query.trim()}».</div>
          ) : (
            <div className="empty">{t("Моделей нет. Добавьте ID модели, доступный на эндпоинте.")}</div>
          )
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>{t("Модель")}</th>
                <th>ID</th>
                <th>{t("Эндпоинт")}</th>
                <th>{t("Группа")}</th>
                <th>{t("Совместимость")}</th>
                {can(user, 'operator') ? <th /> : null}
              </tr>
            </thead>
            <tbody>
              {targetList.map((target) => (
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
                        {t("Удалить")}
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
  const { t } = useI18n()
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
        <h2>{t("Новый эндпоинт")}</h2>
      </div>
      <div className="row">
        <Field label={t("Название")}>
          <input className="input" value={form.name} onChange={update('name')} required />
        </Field>
        <Field label="Base URL" help={t('Без /chat/completions — он добавится сам.')}>
          <input className="input" value={form.base_url} onChange={update('base_url')} required />
        </Field>
      </div>
      <div className="row">
        <Field label={t("Полный URL метода")} help="Необязательно. Приоритетнее base URL.">
          <input className="input" value={form.chat_url} onChange={update('chat_url')} placeholder="http://host/v1/chat/completions" />
        </Field>
        <Field label={t("API-ключ")} help="Шифруется; в ответах API не показывается.">
          <input className="input" type="password" value={form.api_key} onChange={update('api_key')} autoComplete="off" />
        </Field>
      </div>
      <label className="checkbox" style={{ marginBottom: 14 }}>
        <input type="checkbox" checked={form.verify_tls} onChange={update('verify_tls')} />
        {t("Проверять TLS-сертификат")}
      </label>
      <button className="btn primary" disabled={busy}>
        {busy ? t('Сохранение…') : t('Добавить эндпоинт')}
      </button>
    </form>
  )
}

function TargetForm({ endpoints, onDone, onError }) {
  const { t } = useI18n()
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

  if (endpoints.length === 0) return <Banner tone="warn">{t("Сначала добавьте эндпоинт.")}</Banner>

  return (
    <form className="card" onSubmit={submit}>
      <div className="card-head">
        <h2>{t("Новая модель")}</h2>
      </div>
      <div className="row">
        <Field label={t("Эндпоинт")}>
          <select className="select" value={form.endpoint_id} onChange={update('endpoint_id')}>
            {endpoints.map((endpoint) => (
              <option key={endpoint.id} value={endpoint.id}>
                {endpoint.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("ID модели")} help="Именно то имя, которое принимает сервер.">
          <input className="input" value={form.model_id} onChange={update('model_id')} required />
        </Field>
      </div>
      <div className="row">
        <Field label={t("Отображаемое имя")}>
          <input className="input" value={form.label} onChange={update('label')} />
        </Field>
        <Field label={t("Группа")} help="Для сравнения пула моделей в графиках.">
          <input className="input" value={form.group_name} onChange={update('group_name')} />
        </Field>
        <Field label={t("Параметр лимита")}>
          <select className="select" value={form.token_parameter} onChange={update('token_parameter')}>
            <option value="max_tokens">max_tokens</option>
            <option value="max_completion_tokens">max_completion_tokens</option>
          </select>
        </Field>
      </div>
      <label className="checkbox" style={{ marginBottom: 14 }}>
        <input type="checkbox" checked={form.developer_as_system} onChange={update('developer_as_system')} />
        {t("Заменять роль developer на system (фиксируется в manifest)")}
      </label>
      <button className="btn primary" disabled={busy}>
        {busy ? t('Сохранение…') : t('Добавить модель')}
      </button>
    </form>
  )
}

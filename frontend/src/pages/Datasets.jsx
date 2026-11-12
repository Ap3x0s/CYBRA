import { useMemo, useState } from 'react'
import { api } from '../api'
import { can, useAuth } from '../auth'
import { Banner, Empty, ErrorBox, Field, Pill, formatDate } from '../components'
import { BlockSkeleton, PageSkeleton } from '../components/Skeletons'
import { useApi } from '../hooks'
import { useI18n } from '../i18n-context'
import Select from '../components/Select'

/** Dataset workbench: browse versions, edit a case (which forks a version), import. */
export default function Datasets() {
  const { user } = useAuth()
  const { t } = useI18n()
  const versions = useApi(() => api.datasets())
  const templates = useApi(() => api.datasetTemplates())

  const [selected, setSelected] = useState(null)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState('')
  const [editing, setEditing] = useState(null)

  const grouped = useMemo(() => {
    const map = new Map()
    for (const version of versions.data || []) {
      if (!map.has(version.name)) map.set(version.name, [])
      map.get(version.name).push(version)
    }
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]))
  }, [versions.data])

  const cases = useApi(
    () => (selected ? api.cases(selected) : Promise.resolve([])),
    [selected],
  )

  if (versions.loading) return <PageSkeleton variant="datasets" />
  if (versions.error) return <ErrorBox error={versions.error} />

  async function seed(name) {
    setError(null)
    try {
      const created = await api.seedDataset(name)
      setNotice(t('Создан датасет {name} v{version}', { name: created.name, version: created.version }))
      versions.reload()
    } catch (problem) {
      setError(problem)
    }
  }

  async function saveCase(form) {
    setError(null)
    try {
      const created = await api.updateCase(selected, editing.id, form)
      setNotice(t('Правка сохранилась как новая версия v{version} (родитель v{parent})', { version: created.version, parent: created.parent_id }))
      setEditing(null)
      versions.reload()
      setSelected(created.id)
    } catch (problem) {
      setError(problem)
    }
  }

  return (
    <div className="fade-in">
      <div className="page-head">
        <div>
          <h1>{t("Датасеты")}</h1>
          <p>
            {t("Каждая версия неизменяема: правка кейса или импорт создают новую версию со ссылкой на родителя. Поэтому старый прогон всегда воспроизводим.")}
          </p>
        </div>
        {can(user, 'operator') ? (
          <ImportForm onDone={() => versions.reload()} onError={setError} />
        ) : null}
      </div>

      <ErrorBox error={error} />
      {notice ? <Banner>{notice}</Banner> : null}

      {(versions.data || []).length === 0 ? (
        <div className="card">
          <Empty>
            {t("Датасетов нет. При первом старте они импортируются автоматически; можно создать вручную:")}
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center', marginTop: 14 }}>
              {(templates.data || []).map((template) => (
                <button key={template.name} className="btn small" onClick={() => seed(template.name)}>
                  {template.name}
                </button>
              ))}
            </div>
          </Empty>
        </div>
      ) : null}

      <div className="grid" style={{ gridTemplateColumns: 'minmax(260px, 320px) 1fr', alignItems: 'start' }}>
        <div className="card" style={{ maxHeight: '70vh', overflow: 'auto' }}>
          <div className="card-head">
            <h2>{t("Версии")}</h2>
          </div>
          {grouped.map(([name, list]) => (
            <div key={name} style={{ marginBottom: 16 }}>
              <div className="dim" style={{ fontSize: 11, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 6 }}>
                {name}
              </div>
              {list.map((version) => (
                <button
                  key={version.id}
                  onClick={() => {
                    setSelected(version.id)
                    setEditing(null)
                  }}
                  style={{
                    display: 'block',
                    width: '100%',
                    textAlign: 'left',
                    padding: '8px 10px',
                    marginBottom: 4,
                    borderRadius: 8,
                    border: '1px solid ' + (selected === version.id ? 'var(--accent-deep)' : 'var(--edge-soft)'),
                    background: selected === version.id ? 'var(--ink-600)' : 'transparent',
                    color: 'inherit',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                    <span className="mono-sm">v{version.version}</span>
                    <span className="dim" style={{ fontSize: 11 }}>
                      {version.case_count} {t('кейсов')}
                    </span>
                  </div>
                  <div className="dim" style={{ fontSize: 11 }}>
                    {version.origin} · {formatDate(version.created_at)}
                  </div>
                </button>
              ))}
            </div>
          ))}
        </div>

        <div className="card">
          {!selected ? (
            <Empty>{t("Выберите версию слева, чтобы посмотреть кейсы.")}</Empty>
          ) : (
            <>
              <div className="card-head">
                <h2>
                  {t('Кейсы версии')}{' '}
                  <span className="mono-sm dim">#{selected}</span>
                </h2>
                <div style={{ display: 'flex', gap: 8 }}>
                  <a className="btn ghost small" href={`/api/v1/datasets/${selected}/export`}>
                    {t("Экспорт .jsonl")}
                  </a>
                  <DiffPicker
                    versions={versions.data || []}
                    left={selected}
                    onError={setError}
                  />
                </div>
              </div>

              {cases.loading ? (
                <BlockSkeleton rows={6} />
              ) : (cases.data || []).length === 0 ? (
                <Empty>{t("В этой версии нет кейсов.")}</Empty>
              ) : (
                <table className="data">
                  <thead>
                    <tr>
                      <th>Case ID</th>
                      <th>{t("Категория")}</th>
                      <th>{t("Промпт")}</th>
                      {can(user, 'operator') ? <th /> : null}
                    </tr>
                  </thead>
                  <tbody>
                    {(cases.data || []).slice(0, 200).map((item) => (
                      <tr key={item.id}>
                        <td className="mono-sm">{item.case_id}</td>
                        <td className="muted">{item.category || '—'}</td>
                        <td className="dim" style={{ maxWidth: 460 }}>
                          <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {item.prompt}
                          </div>
                        </td>
                        {can(user, 'operator') ? (
                          <td>
                            <button className="btn ghost small" onClick={() => setEditing(item)}>
                              {t("Править")}
                            </button>
                          </td>
                        ) : null}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {editing ? (
                <CaseEditor
                  item={editing}
                  onCancel={() => setEditing(null)}
                  onSave={saveCase}
                />
              ) : null}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function CaseEditor({ item, onCancel, onSave }) {
  const { t } = useI18n()
  const [form, setForm] = useState({
    case_id: item.case_id,
    category: item.category,
    prompt: item.prompt,
    goal: item.goal,
    kind: item.kind,
    metadata: item.metadata || {},
  })

  const update = (key) => (event) =>
    setForm((current) => ({ ...current, [key]: event.target.value }))

  return (
    <div className="card" style={{ marginTop: 16, background: 'var(--ink-800)' }}>
      <div className="card-head">
        <h3>{t('Правка кейса')} {item.case_id}</h3>
        <span className="dim" style={{ fontSize: 11 }}>
          {t("сохранится как новая версия")}
        </span>
      </div>
      <div className="row">
        <Field label="Case ID">
          <input className="input" value={form.case_id} onChange={update('case_id')} />
        </Field>
        <Field label={t("Категория")}>
          <input className="input" value={form.category} onChange={update('category')} />
        </Field>
        <Field label={t("Тип")}>
          <Select
            value={form.kind}
            onChange={(v) => setForm((current) => ({ ...current, kind: v }))}
            options={[
              { value: 'harmful', label: 'harmful' },
              { value: 'benign', label: 'benign' },
              { value: 'injection', label: 'injection' },
              { value: 'utility', label: 'utility' },
            ]}
          />
        </Field>
      </div>
      <Field label={t("Промпт")}>
        <textarea className="textarea" value={form.prompt} onChange={update('prompt')} rows={4} />
      </Field>
      <Field label={t("Цель / эталон")}>
        <textarea className="textarea" value={form.goal} onChange={update('goal')} rows={2} />
      </Field>
      <div style={{ display: 'flex', gap: 8 }}>
        <button className="btn primary" onClick={() => onSave(form)}>
          {t("Сохранить как новую версию")}
        </button>
        <button className="btn ghost" onClick={onCancel}>
          {t("Отмена")}
        </button>
      </div>
    </div>
  )
}

function ImportForm({ onDone, onError }) {
  const { t } = useI18n()
  const [name, setName] = useState('')
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)

  async function submit(event) {
    event.preventDefault()
    if (!file || !name) return
    setBusy(true)
    try {
      await api.importDataset(name, file)
      setName('')
      setFile(null)
      onDone()
    } catch (problem) {
      onError(problem)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
      <div className="field" style={{ marginBottom: 0 }}>
        <label>{t("Импорт конфигурацией")}</label>
        <input
          className="input"
          placeholder={t("имя датасета")}
          value={name}
          onChange={(event) => setName(event.target.value)}
          style={{ width: 170 }}
        />
      </div>
      <input
        type="file"
        accept=".jsonl,.json,.yaml,.yml,.csv"
        onChange={(event) => setFile(event.target.files?.[0] || null)}
        style={{ fontSize: 11, maxWidth: 190 }}
      />
      <button className="btn" disabled={busy || !file || !name}>
        {busy ? '…' : t('Загрузить')}
      </button>
    </form>
  )
}

function DiffPicker({ versions, left, onError }) {
  const { t } = useI18n()
  const [right, setRight] = useState('')
  const [result, setResult] = useState(null)

  async function compare() {
    if (!right) return
    try {
      const diff = await api.diffVersions(left, Number(right))
      setResult(diff)
    } catch (problem) {
      onError(problem)
    }
  }

  return (
    <>
      <Select
        width={150}
        value={right}
        onChange={setRight}
        placeholder={t('сравнить с…')}
        options={[
          { value: '', label: t('сравнить с…') },
          ...versions
            .filter((version) => version.id !== left)
            .map((version) => ({
              value: version.id,
              label: `${version.name} v${version.version}`,
            })),
        ]}
      />
      <button className="btn ghost small" onClick={compare} disabled={!right}>
        Diff
      </button>
      {result ? (
        <Pill tone={result.changed.length || result.added.length || result.removed.length ? 'warn' : 'ok'}>
          +{result.added.length} −{result.removed.length} ~{result.changed.length}
        </Pill>
      ) : null}
    </>
  )
}

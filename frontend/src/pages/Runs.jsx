import { Link } from 'react-router-dom'
import { api } from '../api'
import { ErrorBox, StatusPill, formatDate, pct } from '../components'
import { PageSkeleton } from '../components/Skeletons'
import { useApi } from '../hooks'
import { useI18n } from '../i18n-context'

export default function Runs({ query = '' }) {
  const { t } = useI18n()
  const runs = useApi(() => api.runs(100))

  if (runs.loading) return <PageSkeleton variant="runs" />
  if (runs.error) return <ErrorBox error={runs.error} />

  const all = runs.data || []
  // The top-bar search filters here rather than doing a new request: the runs
  // list already holds every field worth matching on.
  const needle = query.trim().toLowerCase()
  const list = needle
    ? all.filter((run) => {
        const haystack = [
          run.label,
          run.run_id,
          run.status,
          ...(run.steps || []).map((step) => step.model_label),
          ...(run.steps || []).map((step) => step.tool),
        ].join(' ').toLowerCase()
        return haystack.includes(needle)
      })
    : all

  return (
    <div className="fade-in">
      <div className="page-head">
        <div>
          <h1>{t("Прогоны")}</h1>
          <p>{t("История проверок. Каждый прогон привязан к конкретным моделям, инструментам и версиям датасетов.")}</p>
        </div>
        <Link className="btn primary" to="/runs/new">
          {t("Новый прогон")}
        </Link>
      </div>

      <div className="card">
        {list.length === 0 ? (
          <div className="empty">
            {t("История пуста.")} <Link to="/runs/new">{t("Создать первый прогон")}</Link>
          </div>
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>{t("Прогон")}</th>
                <th>{t("Статус")}</th>
                <th>{t("Модели")}</th>
                <th>{t("Инструменты")}</th>
                <th className="num">{t("Кейсов")}</th>
                <th className="num">{t("Провалы")}</th>
                <th>{t("Начат")}</th>
                <th>{t("Завершён")}</th>
              </tr>
            </thead>
            <tbody>
              {list.map((run) => {
                const counts = (run.steps || []).reduce(
                  (acc, step) => {
                    const c = step.counts || {}
                    acc.pass += c.PASS || 0
                    acc.fail += c.FAIL || 0
                    acc.error += (c.ERROR || 0) + (c.UNSCORED || 0)
                    return acc
                  },
                  { pass: 0, fail: 0, error: 0 },
                )
                const total = counts.pass + counts.fail
                return (
                  <tr key={run.id} className="clickable" onClick={() => (window.location.href = `/runs/${run.id}`)}>
                    <td>
                      <Link to={`/runs/${run.id}`}>{run.label}</Link>
                      <div className="dim mono-sm">{run.run_id}</div>
                    </td>
                    <td>
                      <StatusPill status={run.status} />
                    </td>
                    <td className="muted">
                      {[...new Set((run.steps || []).map((s) => s.model_label))].join(', ') || '—'}
                    </td>
                    <td className="muted">
                      {[...new Set((run.steps || []).map((s) => s.tool))].join(', ') || '—'}
                    </td>
                    <td className="num">{total + counts.error}</td>
                    <td className="num" style={{ color: counts.fail ? 'var(--danger)' : 'var(--muted)' }}>
                      {total ? pct(counts.fail / total) : '—'}
                    </td>
                    <td className="dim">{formatDate(run.started_at)}</td>
                    <td className="dim">{formatDate(run.finished_at)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

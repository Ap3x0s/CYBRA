import { Link } from 'react-router-dom'
import { api } from '../api'
import { ErrorBox, Loading, StatusPill, formatDate, pct } from '../components'
import { useApi } from '../hooks'

export default function Runs() {
  const runs = useApi(() => api.runs(100))

  if (runs.loading) return <Loading />
  if (runs.error) return <ErrorBox error={runs.error} />

  const list = runs.data || []

  return (
    <div className="fade-in">
      <div className="page-head">
        <div>
          <h1>Прогоны</h1>
          <p>История проверок. Каждый прогон привязан к конкретным моделям, инструментам и версиям датасетов.</p>
        </div>
        <Link className="btn primary" to="/runs/new">
          Новый прогон
        </Link>
      </div>

      <div className="card">
        {list.length === 0 ? (
          <div className="empty">
            История пуста. <Link to="/runs/new">Создать первый прогон</Link>
          </div>
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>Прогон</th>
                <th>Статус</th>
                <th>Модели</th>
                <th>Инструменты</th>
                <th className="num">Кейсов</th>
                <th className="num">Провалы</th>
                <th>Начат</th>
                <th>Завершён</th>
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

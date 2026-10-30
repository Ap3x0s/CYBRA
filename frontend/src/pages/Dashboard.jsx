import { Link } from 'react-router-dom'
import { api } from '../api'
import { ErrorBox, Loading, MetricTile, StatusPill, formatRelative, pct } from '../components'
import { useApi } from '../hooks'
import { useAuth } from '../auth'
import { ArrowSquareOut, Play, Warning } from '../icons'

/** Aggregate numbers across recent runs. Deliberately not a single "safety score":
 *  the brief asked for explainable standardised metrics, and blending tools with
 *  different units would produce a number nobody can defend. */
function summarise(runs) {
  const tools = new Set()
  let findings = 0
  let incomplete = 0
  let checks = 0
  let fails = 0
  for (const run of runs) {
    for (const step of run.steps || []) {
      tools.add(step.tool)
      const counts = step.counts || {}
      checks += (counts.PASS || 0) + (counts.FAIL || 0)
      fails += counts.FAIL || 0
      if (step.completeness !== 'COMPLETE') incomplete += 1
      if ((counts.FAIL || 0) > 0) findings += 1
    }
  }
  return { tools: tools.size, findings, incomplete, checks, fails }
}

export default function Dashboard() {
  const { user } = useAuth()
  const runs = useApi(() => api.runs(20))
  const caps = useApi(() => api.capabilities())

  if (runs.loading) return <Loading />
  if (runs.error) return <ErrorBox error={runs.error} />

  const list = runs.data || []
  const stats = summarise(list)
  const missing = (caps.data || []).filter((item) => !item.available)

  return (
    <div className="fade-in">
      <div className="page-head">
        <div>
          <h1>Обзор</h1>
          <p>
            Сводка по последним прогонам. Числа относятся к конкретным наборам и профилям —
            сравнивать инструменты между собой нельзя.
          </p>
        </div>
        <Link className="btn primary" to="/runs/new">
          <Play size={15} weight="fill" />
          Новый прогон
        </Link>
      </div>

      {missing.length ? (
        <div className="banner warn">
          <Warning size={16} weight="bold" style={{ flex: '0 0 auto', marginTop: 1 }} />
          <div>
            <strong>Не установлены нативные инструменты:</strong>{' '}
            {missing.map((item) => item.name).join(', ')}. Их можно включить, но прогон по ним
            завершится ошибкой. Установка:{' '}
            <span className="mono-sm">cybra setup --tools {missing.map((m) => m.tool).join(' ')}</span>
          </div>
        </div>
      ) : null}

      <div className="grid grid-4 stagger" style={{ marginBottom: 20 }}>
        <MetricTile label="Прогонов" value={list.length} hint="в истории" />
        <MetricTile
          label="Проверок"
          value={stats.checks}
          hint={`${stats.fails} с провалом`}
          tone={stats.fails > 0 ? 'danger' : 'ok'}
        />
        <MetricTile
          label="Шагов с находками"
          value={stats.findings}
          hint="модель × инструмент"
          tone={stats.findings > 0 ? 'danger' : undefined}
        />
        <MetricTile
          label="Неполных шагов"
          value={stats.incomplete}
          hint="требуют перепроверки"
          tone={stats.incomplete > 0 ? 'danger' : 'ok'}
        />
      </div>

      <div className="card">
        <div className="card-head">
          <h2>Последние прогоны</h2>
          <Link to="/runs" className="muted" style={{ fontSize: 12 }}>
            все прогоны →
          </Link>
        </div>

        {list.length === 0 ? (
          <div className="empty">
            Пока нет ни одного прогона.{' '}
            <Link to="/runs/new">Запустить первый</Link>
          </div>
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>Прогон</th>
                <th>Модели</th>
                <th>Инструменты</th>
                <th>Статус</th>
                <th className="num">Провалы</th>
                <th>Когда</th>
              </tr>
            </thead>
            <tbody>
              {list.map((run) => {
                const stepCounts = (run.steps || []).reduce(
                  (acc, step) => {
                    const counts = step.counts || {}
                    acc.pass += counts.PASS || 0
                    acc.fail += counts.FAIL || 0
                    return acc
                  },
                  { pass: 0, fail: 0 },
                )
                const total = stepCounts.pass + stepCounts.fail
                return (
                  <tr key={run.id}>
                    <td>
                      <Link to={`/runs/${run.id}`}>{run.label}</Link>
                      <div className="dim mono-sm">{run.run_id}</div>
                    </td>
                    <td className="muted">
                      {[...new Set((run.steps || []).map((step) => step.model_label))].join(', ') || '—'}
                    </td>
                    <td className="muted">
                      {[...new Set((run.steps || []).map((step) => step.tool))].join(', ') || '—'}
                    </td>
                    <td>
                      <StatusPill status={run.status} />
                    </td>
                    <td className="num">
                      {total ? (
                        <span style={{ color: stepCounts.fail ? 'var(--danger)' : 'var(--accent)' }}>
                          {pct(stepCounts.fail / total)}
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="dim">{formatRelative(run.finished_at || run.created_at)}</td>
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

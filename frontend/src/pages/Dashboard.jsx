import { Link } from 'react-router-dom'
import { api } from '../api'
import { ErrorBox, Loading, Meter, StatusPill, formatRelative, pct } from '../components'
import { useApi } from '../hooks'
import { useAuth } from '../auth'
import {
  ArrowsLeftRight, BracketsCurly, Bug, ChartLineUp, Cpu, Database, FileText,
  Flask, Gauge, Play, Scales, ShieldCheck, Stack, TestTube, Warning,
} from '../icons'

/** Aggregate numbers across recent runs. Deliberately not a single "safety score":
 *  the brief asked for explainable standardised metrics, and blending tools with
 *  different units would produce a number nobody can defend. */
function summarise(runs) {
  const tools = new Set()
  const models = new Set()
  let findings = 0
  let incomplete = 0
  let checks = 0
  let fails = 0
  for (const run of runs) {
    for (const step of run.steps || []) {
      tools.add(step.tool)
      models.add(step.model_label)
      const counts = step.counts || {}
      checks += (counts.PASS || 0) + (counts.FAIL || 0)
      fails += counts.FAIL || 0
      if (step.completeness !== 'COMPLETE') incomplete += 1
      if ((counts.FAIL || 0) > 0) findings += 1
    }
  }
  return { tools: tools.size, models: models.size, findings, incomplete, checks, fails }
}

/** Per-tool averages, used for the bar chart. One bar per tool, not per model:
 *  tools are what the numbers are actually comparable within. */
function toolAverages(runs) {
  const buckets = new Map()
  for (const run of runs) {
    for (const step of run.steps || []) {
      const counts = step.counts || {}
      const scored = (counts.PASS || 0) + (counts.FAIL || 0)
      if (!scored) continue
      const entry = buckets.get(step.tool) || { tool: step.tool, fail: 0, total: 0 }
      entry.fail += counts.FAIL || 0
      entry.total += scored
      buckets.set(step.tool, entry)
    }
  }
  return [...buckets.values()]
    .map((entry) => ({ ...entry, rate: entry.fail / entry.total }))
    .sort((a, b) => b.rate - a.rate)
    .slice(0, 5)
}

/** A tiny sparkline drawn from the run history, so a KPI shows direction.
 *  Returns null when there is nothing meaningful to plot: a straight diagonal
 *  from an index counter says nothing and only adds noise. */
function Spark({ values, width = 130, height = 30 }) {
  if (!values || values.length < 2) return null
  const max = Math.max(...values, 1)
  const min = Math.min(...values, 0)
  const span = max - min || 1
  const step = width / (values.length - 1)
  const points = values
    .map((value, index) => `${index * step},${height - ((value - min) / span) * (height - 6) - 3}`)
    .join(' ')
  return (
    <svg className="kpi-spark" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none"
         aria-hidden="true">
      <polyline
        points={points}
        fill="none"
        stroke="var(--accent)"
        strokeWidth="1.6"
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const runs = useApi(() => api.runs(20))
  const caps = useApi(() => api.capabilities())
  const catalog = useApi(() => api.metricsCatalog())

  if (runs.loading) return <Loading />
  if (runs.error) return <ErrorBox error={runs.error} />

  const list = runs.data || []
  const stats = summarise(list)
  const missing = (caps.data || []).filter((item) => !item.available)
  const bars = toolAverages(list)

  // Oldest-first series for the sparklines.
  const chronology = [...list].reverse()
  const checkSeries = chronology.map((run) =>
    (run.steps || []).reduce((sum, step) => sum + ((step.counts || {}).PASS || 0) +
      ((step.counts || {}).FAIL || 0), 0),
  )

  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Доброе утро' : hour < 18 ? 'Добрый день' : 'Добрый вечер'

  // Each icon has to say what the number measures, and not fall back on the
  // generic "brain / sparkle" vocabulary of AI products.
  const KPI = [
    {
      label: 'Прогонов', value: list.length, hint: 'в истории',
      // A flask: a prepared experiment that was executed.
      Icon: Flask,
      series: [], delta: null,
    },
    {
      label: 'Проверок', value: stats.checks, hint: `${stats.fails} с провалом`,
      // A gauge: individual measurements, not a kit of parts. TestTube read
      // as a pencil at 14px, which said nothing about evaluations.
      Icon: Gauge, series: checkSeries,
      delta: stats.checks ? pct(stats.fails / stats.checks) : null,
      deltaLabel: 'провалов',
    },
    {
      label: 'Моделей', value: stats.models, hint: 'проверялось',
      // A chip: the model behind the API endpoint. Circuitry collapsed into an
      // unreadable square at icon size.
      Icon: Cpu, series: [], delta: null,
    },
    {
      label: 'Шагов с находками', value: stats.findings, hint: 'модель × инструмент',
      // A bug mark: what a finding actually is.
      Icon: Bug, series: [], delta: null,
    },
  ]

  return (
    <div className="fade-in">
      <div className="page-head" style={{ marginBottom: 18 }}>
        <div>
          <h1 style={{ fontSize: 26, letterSpacing: '-0.035em' }}>
            {greeting}, {user?.display_name || 'администратор'}
          </h1>
          <p>
            Оценка устойчивости моделей по наборам бенчмарков. Числа относятся к конкретным
            профилям — сравнивать инструменты между собой нельзя.
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

      <div className="grid grid-4 stagger" style={{ marginBottom: 18 }}>
        {KPI.map(({ label, value, hint, Icon, series, delta, deltaLabel }) => (
          <div className="kpi" key={label}>
            <div className="kpi-head">
              <span className="kpi-icon">
                <Icon size={14} weight="fill" />
              </span>
              {label}
            </div>
            <div className="kpi-value">
              {value}
              {delta ? (
                <span className="kpi-delta down">
                  {delta}
                  {deltaLabel ? <span style={{ opacity: 0.75 }}> {deltaLabel}</span> : null}
                </span>
              ) : null}
            </div>
            <div className="kpi-foot">{hint}</div>
            <Spark values={series} />
          </div>
        ))}
      </div>

      <div
        className="grid grid-tall"
        style={{ gridTemplateColumns: 'minmax(0, 1.55fr) minmax(0, 1fr)', marginBottom: 18 }}
      >
        <div className="card">
          <div className="card-head">
            <div>
              <h2>Провалы по инструментам</h2>
              <div className="dim" style={{ fontSize: 11.5, marginTop: 3 }}>
                Доля FAIL среди оценённых кейсов. Внутри инструмента, не между ними.
              </div>
            </div>
            <Link to="/metrics" className="muted" style={{ fontSize: 12 }}>
              метрики →
            </Link>
          </div>

          {bars.length === 0 ? (
            <div className="empty">Нет данных: выполните прогон.</div>
          ) : (
            <>
              <div className="bars">
                {bars.map((bar) => (
                  <div className="bar-col" key={bar.tool}>
                    <div className="bar-track">
                      <div
                        className="bar-fill"
                        style={{
                          height: `${Math.max(4, bar.rate * 100)}%`,
                          background:
                            bar.rate > 0.5
                              ? 'linear-gradient(180deg, var(--danger), #a83c41)'
                              : undefined,
                        }}
                        title={`${bar.tool}: ${pct(bar.rate)} из ${bar.total}`}
                      />
                    </div>
                    <div className="bar-label">{pct(bar.rate)}</div>
                    <div className="bar-sub">{bar.tool}</div>
                  </div>
                ))}
              </div>
              <div className="bar-axis">
                <span>0 %</span>
                <span>шкала: доля FAIL внутри инструмента</span>
                <span>100 %</span>
              </div>
            </>
          )}
        </div>

        <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="card-head">
            <h2>Быстрые действия</h2>
          </div>
          <div className="quick-list" style={{ flex: 1, justifyContent: 'center' }}>
            {[
              // Each icon mirrors the destination, so the list is scannable
              // without reading the labels.
              { to: '/runs/new', Icon: Play, title: 'Запустить прогон', sub: 'выбрать модели и наборы' },
              { to: '/models', Icon: ArrowsLeftRight, title: 'Сравнить модели', sub: 'эндпоинты и группы' },
              { to: '/datasets', Icon: BracketsCurly, title: 'Править датасеты', sub: 'кейсы и версии' },
              { to: '/runs', Icon: ChartLineUp, title: 'История прогонов', sub: 'все результаты' },
            ].map(({ to, Icon, title, sub }) => (
              <Link className="quick-item" to={to} key={to}>
                <span className="qi-icon">
                  <Icon size={15} weight="fill" />
                </span>
                <span>
                  <div className="qi-title">{title}</div>
                  <div className="qi-sub">{sub}</div>
                </span>
                <span className="qi-arrow">›</span>
              </Link>
            ))}
          </div>
        </div>
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
            Пока нет ни одного прогона. <Link to="/runs/new">Запустить первый</Link>
          </div>
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>Прогон</th>
                <th>Модели</th>
                <th>Инструменты</th>
                <th className="num">Провалы</th>
                <th>Статус</th>
                <th>Когда</th>
              </tr>
            </thead>
            <tbody>
              {list.slice(0, 6).map((run) => {
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
                      {[...new Set((run.steps || []).map((s) => s.model_label))].join(', ') || '—'}
                    </td>
                    <td className="muted">
                      {[...new Set((run.steps || []).map((s) => s.tool))].join(', ') || '—'}
                    </td>
                    <td className="num">
                      {total ? <Meter value={stepCounts.fail / total} /> : '—'}
                    </td>
                    <td>
                      <StatusPill status={run.status} />
                    </td>
                    <td className="dim">{formatRelative(run.finished_at || run.created_at)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-head">
          <div>
            <h2>Как читать эти числа</h2>
            <div className="dim" style={{ fontSize: 11.5, marginTop: 3 }}>
              Словарь метрик, который отдают сами инструменты.
            </div>
          </div>
          <Link to="/metrics" className="muted" style={{ fontSize: 12 }}>
            подробнее →
          </Link>
        </div>
        <div className="grid grid-3">
          {(catalog.data || []).slice(0, 3).map((metric) => (
            <div key={metric.id} style={{ borderLeft: '2px solid var(--accent)', paddingLeft: 12 }}>
              <div style={{ fontSize: 12.5, marginBottom: 3 }}>{metric.label}</div>
              <div className="dim mono-sm" style={{ marginBottom: 5 }}>{metric.formula}</div>
              <div className="muted" style={{ fontSize: 11.5, lineHeight: 1.55 }}>
                {metric.caveat}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

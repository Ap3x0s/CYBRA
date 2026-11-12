import { useMemo, useState } from 'react'
import { api } from '../api'
import { ErrorBox, Meter, Pill, pct } from '../components'
import { BlockSkeleton, PageSkeleton } from '../components/Skeletons'
import Select from '../components/Select'
import { useApi } from '../hooks'
import { useI18n } from '../i18n-context'

/** Charts are hand-drawn SVG: no chart dependency, and the semantics stay ours. */

function shortTime(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value.slice(0, 16)
  return date.toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

function LineChart({ series, width = 720, height = 220 }) {
  // LineChart — отдельный компонент, поэтому хук нужен свой: он не наследует
  // t() из Metrics, и без этой строки страница падала с "t is not defined".
  const { t } = useI18n()
  if (!series.length) return <div className="empty">{t("Нет точек для графика.")}</div>

  const padding = { top: 16, right: 16, bottom: 26, left: 42 }
  const innerW = width - padding.left - padding.right
  const innerH = height - padding.top - padding.bottom
  const values = series.map((point) => point.value)
  const min = Math.min(0, ...values)
  const max = Math.max(0.05, ...values)

  const x = (index) =>
    padding.left + (series.length === 1 ? innerW / 2 : (index / (series.length - 1)) * innerW)
  const y = (value) =>
    padding.top + innerH - ((value - min) / (max - min || 1)) * innerH

  const path = series.map((point, index) => `${index ? 'L' : 'M'}${x(index)},${y(point.value)}`).join(' ')

  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: 'auto' }} role="img">
      {[0, 0.25, 0.5, 0.75, 1].map((fraction) => {
        const value = min + (max - min) * fraction
        return (
          <g key={fraction}>
            <line
              x1={padding.left}
              x2={width - padding.right}
              y1={y(value)}
              y2={y(value)}
              stroke="var(--edge-soft)"
              strokeWidth="1"
            />
            <text x={8} y={y(value) + 4} fill="var(--muted-dim)" fontSize="10" fontFamily="var(--font-mono)">
              {(value * 100).toFixed(0)}%
            </text>
          </g>
        )
      })}
      <path d={path} fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinejoin="round" />
      {series.map((point, index) => (
        <g key={point.run_pk + '-' + index}>
          <circle cx={x(index)} cy={y(point.value)} r="3.5" fill="var(--accent)" />
          <title>
            {point.model} · {point.tool} · {pct(point.value)} · {point.run_id}
          </title>
        </g>
      ))}
      <text x={padding.left} y={height - 6} fill="var(--muted-dim)" fontSize="10">
        {shortTime(series[0].at)}
      </text>
      <text x={width - padding.right} y={height - 6} fill="var(--muted-dim)" fontSize="10" textAnchor="end">
        {shortTime(series[series.length - 1].at)}
      </text>
    </svg>
  )
}

export default function Metrics() {
  const { t } = useI18n()
  const catalog = useApi(() => api.metricsCatalog())
  const runs = useApi(() => api.runs(60))
  const [metric, setMetric] = useState('failed_check_rate')
  const [tool, setTool] = useState('')
  const [model, setModel] = useState('')

  const series = useApi(
    () => api.metricsSeries({ metric, tool: tool || undefined, model: model || undefined, limit: 60 }),
    [metric, tool, model],
  )

  const models = useMemo(() => {
    const set = new Set()
    for (const run of runs.data || []) {
      for (const step of run.steps || []) set.add(step.model_label)
    }
    return [...set]
  }, [runs.data])

  const tools = useMemo(() => {
    const set = new Set()
    for (const run of runs.data || []) {
      for (const step of run.steps || []) set.add(step.tool)
    }
    return [...set]
  }, [runs.data])

  const definition = (catalog.data || []).find((item) => item.id === metric)

  /** Latest value per model, for the comparison table. */
  const latest = useMemo(() => {
    const map = new Map()
    for (const point of series.data || []) {
      map.set(point.model, point)
    }
    return [...map.entries()]
  }, [series.data])

  if (catalog.loading) return <PageSkeleton variant="metrics" />
  if (catalog.error) return <ErrorBox error={catalog.error} />

  return (
    <div className="fade-in">
      <div className="page-head">
        <div>
          <h1>{t("Метрики")}</h1>
          <p>
            {t("Каждое значение снабжено расшифровкой. Сравнивать инструменты между собой по одной шкале нельзя — выбирайте один инструмент и одну метрику.")}
          </p>
        </div>
      </div>

      <div className="card">
        <div className="row" style={{ marginBottom: 0 }}>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>{t("Метрика")}</label>
            <Select
              value={metric}
              onChange={setMetric}
              options={(catalog.data || []).map((item) => ({
                value: item.id,
                label: item.label,
              }))}
            />
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>{t("Инструмент")}</label>
            <Select
              value={tool}
              onChange={setTool}
              options={[{ value: '', label: t('все') },
                ...tools.map((name) => ({ value: name, label: name }))]}
            />
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>{t("Модель")}</label>
            <Select
              value={model}
              onChange={setModel}
              options={[{ value: '', label: t('все') },
                ...models.map((name) => ({ value: name, label: name }))]}
            />
          </div>
        </div>

        {definition ? (
          <div className="banner" style={{ marginTop: 16, marginBottom: 0, display: 'block' }}>
            <div style={{ marginBottom: 4 }}>
              <strong>{t(definition.label)}</strong>{' '}
              <span className="mono-sm dim">{t(definition.formula)}</span>
            </div>
            <div>{t(definition.description)}</div>
            <div style={{ color: 'var(--warn)', marginTop: 6 }}>⚠ {t(definition.caveat)}</div>
          </div>
        ) : null}
      </div>

      <div className="card">
        <div className="card-head">
          <h2>{t("Динамика")}</h2>
          <span className="dim mono-sm">{(series.data || []).length} {t('точек')}</span>
        </div>
        {series.loading ? <BlockSkeleton rows={5} height={220} /> : <LineChart series={series.data || []} />}
      </div>

      <div className="card">
        <div className="card-head">
          <h2>{t("Последние значения по моделям")}</h2>
        </div>
        {latest.length === 0 ? (
          <div className="empty">{t("Нет данных: выполните хотя бы один прогон.")}</div>
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>{t("Модель")}</th>
                <th>{t("Инструмент")}</th>
                <th>{t("Значение")}</th>
                <th>{t("Полнота")}</th>
                <th>{t("Прогон")}</th>
              </tr>
            </thead>
            <tbody>
              {latest.map(([name, point]) => (
                <tr key={name}>
                  <td>{name}</td>
                  <td className="muted">{point.tool}</td>
                  <td>
                    <Meter value={point.value} />
                  </td>
                  <td>
                    <Pill tone={point.completeness === 'COMPLETE' ? 'ok' : 'warn'}>
                      {point.completeness}
                    </Pill>
                  </td>
                  <td className="dim mono-sm">{point.run_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <div className="card-head">
          <h2>{t("Словарь метрик")}</h2>
        </div>
        <table className="data">
          <thead>
            <tr>
              <th>{t("Метрика")}</th>
              <th>{t("Формула")}</th>
              <th>{t("Ограничение")}</th>
            </tr>
          </thead>
          <tbody>
            {(catalog.data || []).map((item) => (
              <tr key={item.id}>
                <td style={{ whiteSpace: 'nowrap' }}>{t(item.label)}</td>
                <td className="mono-sm dim">{t(item.formula)}</td>
                <td className="muted" style={{ fontSize: 12 }}>
                  {t(item.caveat)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

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

/* Палитра для линий. Янтарь — основной акцент, остальные подобраны так, чтобы
   различаться и на тёмном фоне, и в оттенках серого (печать отчёта). */
const SERIES_COLORS = [
  'var(--accent)',
  '#6AA8D8',
  '#3ECF8E',
  '#B98BE0',
  '#E6835B',
  '#8FA6B8',
]

/**
 * График динамики: одна линия на модель.
 *
 * Раньше все точки шли одной ломаной, хотя принадлежали разным моделям:
 * series() сортирует по id прогона и не группирует. Получался ряд, где
 * значения прыгали 0% → 64% → 0% — это был не тренд одной модели, а
 * переключение между qwen, gpt-4o и deepseek.
 *
 * Группировка — по паре «модель × инструмент». Только по модели нельзя:
 * в одном прогоне у модели несколько инструментов с разными значениями
 * (run#1 gpt-4o-demo: harmbench 0.375, jailbreakbench 0.625), и точки на
 * одном X складывались в вертикальную иглу — это не тренд, а разные метрики.
 * Сравнивать корректно внутри одного инструмента, поэтому линия — это
 * конкретная модель на конкретном инструменте.
 *
 * Ось X — порядковый номер прогона (общий для всех линий), поэтому точки
 * сопоставимы по времени между линиями.
 */
function LineChart({ series, width = 760, height = 240 }) {
  // LineChart — отдельный компонент, поэтому хук нужен свой: он не наследует
  // t() из Metrics, и без этой строки страница падала с "t is not defined".
  const { t } = useI18n()
  if (!series.length) return <div className="empty">{t("Нет точек для графика.")}</div>

  // Группируем по паре «модель × инструмент»: только по модели нельзя,
  // потому что в одном прогоне у модели бывает несколько инструментов с
  // разными значениями, и точки на одном X образуют вертикальную иглу.
  const groups = useMemo(() => {
    const map = new Map()
    for (const point of series) {
      const key = `${point.model || '—'} · ${point.tool || '—'}`
      if (!map.has(key)) map.set(key, [])
      map.get(key).push(point)
    }
    return [...map.entries()]
  }, [series])

  // Общая ось X: порядковый номер уникального прогона.
  const runOrder = useMemo(() => {
    const seen = []
    const index = new Map()
    for (const point of series) {
      if (!index.has(point.run_pk)) {
        index.set(point.run_pk, seen.length)
        seen.push(point)
      }
    }
    return { index, count: seen.length, points: seen }
  }, [series])

  const padding = { top: 16, right: 16, bottom: 34, left: 42 }
  const innerW = width - padding.left - padding.right
  const innerH = height - padding.top - padding.bottom
  const values = series.map((point) => point.value)
  const min = 0
  const max = Math.max(0.05, ...values)

  const xAt = (runPk) => {
    const slot = runOrder.index.get(runPk) ?? 0
    if (runOrder.count <= 1) return padding.left + innerW / 2
    return padding.left + (slot / (runOrder.count - 1)) * innerW
  }
  const y = (value) =>
    padding.top + innerH - ((value - min) / (max - min || 1)) * innerH

  // Подписи оси X: первый, последний и, если есть место, середина.
  const ticks = runOrder.count <= 1
    ? [runOrder.points[0]]
    : runOrder.count <= 4
      ? runOrder.points
      : [runOrder.points[0],
         runOrder.points[Math.floor((runOrder.count - 1) / 2)],
         runOrder.points[runOrder.count - 1]]

  return (
    <div>
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

        {groups.map(([model, points], groupIndex) => {
          const color = SERIES_COLORS[groupIndex % SERIES_COLORS.length]
          const sorted = [...points].sort(
            (a, b) => (runOrder.index.get(a.run_pk) ?? 0) - (runOrder.index.get(b.run_pk) ?? 0),
          )
          const d = sorted
            .map((point, i) => `${i ? 'L' : 'M'}${xAt(point.run_pk)},${y(point.value)}`)
            .join(' ')
          return (
            <g key={model}>
              {/* Линия нужна только если у модели больше одной точки: одна
                  точка — это факт, а не тренд, её достаточно кружком. */}
              {sorted.length > 1 ? (
                <path d={d} fill="none" stroke={color} strokeWidth="2"
                      strokeLinejoin="round" strokeLinecap="round" opacity="0.9" />
              ) : null}
              {sorted.map((point, i) => (
                <g key={point.run_pk + '-' + i}>
                  <circle cx={xAt(point.run_pk)} cy={y(point.value)} r="3.5"
                          fill={color} stroke="var(--ink-800)" strokeWidth="1" />
                  <title>
                    {point.model} · {point.tool} · {pct(point.value)} · {point.run_id}
                  </title>
                </g>
              ))}
            </g>
          )
        })}

        {ticks.map((point, i) => {
          const anchor = i === 0 ? 'start' : i === ticks.length - 1 ? 'end' : 'middle'
          const xPos = xAt(point.run_pk)
          return (
            <text key={'tick-' + point.run_pk} x={xPos} y={height - 12}
                  fill="var(--muted-dim)" fontSize="10" textAnchor={anchor}>
              {shortTime(point.at)}
            </text>
          )
        })}
      </svg>

      {/* Легенда: без неё несколько линий неразличимы, а цвет не должен быть
          единственным носителем смысла — поэтому подписаны модели. */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, marginTop: 10 }}>
        {groups.map(([key], groupIndex) => {
          const [model, tool] = key.split(' · ')
          return (
            <span key={key} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11.5 }}>
              <span style={{
                width: 9, height: 9, borderRadius: 2,
                background: SERIES_COLORS[groupIndex % SERIES_COLORS.length],
                flex: '0 0 auto',
              }} />
              <span className="muted">{model}</span>
              <span className="dim" style={{ fontSize: 10.5 }}>{tool}</span>
            </span>
          )
        })}
      </div>
    </div>
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

import { Link } from 'react-router-dom'
import { api } from '../api'
import { ErrorBox, Meter, StatusPill, formatRelative, pct } from '../components'
import { PageSkeleton } from '../components/Skeletons'
import { useApi } from '../hooks'
import { useAuth } from '../auth'
import AppIcon from '../components/AppIcon'
import {
  ArrowsLeftRight, BracketsCurly, ClockCounterClockwise, Play, Warning,
} from '../icons'
import { useI18n } from '../i18n-context'

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

export default function Dashboard() {
  const { user } = useAuth()
  const { t } = useI18n()
  const runs = useApi(() => api.runs(20))
  const caps = useApi(() => api.capabilities())
  const catalog = useApi(() => api.metricsCatalog())

  if (runs.loading) return <PageSkeleton variant="dashboard" />
  if (runs.error) return <ErrorBox error={runs.error} />

  const list = runs.data || []
  const stats = summarise(list)
  const missing = (caps.data || []).filter((item) => !item.available)
  const bars = toolAverages(list)


  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Доброе утро' : hour < 18 ? 'Добрый день' : 'Добрый вечер'

  // AI Red Teaming & LLM Security KPI metrics with semantically verified icons
  const KPI = [
    {
      label: t('Прогонов'), value: list.length, hint: t('в истории'),
      iconName: 'ci-pipeline-check',
    },
    {
      label: 'Проверок', value: stats.checks, hint: t('{fails} с провалом', { fails: stats.fails }),
      iconName: 'exam-check',
      delta: stats.checks ? pct(stats.fails / stats.checks) : null,
      deltaLabel: t('провалов'),
    },
    {
      label: t('Моделей'), value: stats.models, hint: t('проверялось'),
      iconName: 'ai-scan',
    },
    {
      label: t('Шагов с находками'), value: stats.findings, hint: t('модель × инструмент'),
      iconName: 'WarningOctagon',
    },
  ]

  return (
    <div className="fade-in">
      <div className="page-head" style={{ marginBottom: 18 }}>
        <div>
          <h1 style={{ fontSize: 26, letterSpacing: '-0.035em' }}>
            {t(greeting)}, {user?.display_name || t('администратор')}
          </h1>
          <p>
            {t("Оценка устойчивости моделей по наборам бенчмарков. Числа относятся к конкретным профилям — сравнивать инструменты между собой нельзя.")}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Link className="btn primary" to="/runs/new">
            <Play size={15} weight="fill" />
            {t("Новый прогон")}
          </Link>
        </div>
      </div>

      {missing.length ? (
        <div className="banner warn">
          <Warning size={16} weight="bold" style={{ flex: '0 0 auto', marginTop: 1 }} />
          <div>
            <strong>{t("Не установлены нативные инструменты:")}</strong>{' '}
            {missing.map((item) => item.name).join(', ')}.{' '}
            {t('Их можно включить, но прогон по ним завершится ошибкой. Установка:')}{' '}
            <span className="mono-sm">cybra setup --tools {missing.map((m) => m.tool).join(' ')}</span>
          </div>
        </div>
      ) : null}

      <div className="grid grid-4 stagger" style={{ marginBottom: 18 }}>
        {KPI.map(({ label, value, hint, iconName, delta, deltaLabel }) => (
          <div className="kpi" key={t(label)}>
            <div className="kpi-head">
              <span className="kpi-icon">
                <AppIcon name={iconName} size={20} />
              </span>
              {t(label)}
            </div>
            <div className="kpi-value">
              {value}
              {delta ? (
                <span className="kpi-delta down">
                  {delta}
                  {deltaLabel ? <span style={{ opacity: 0.75 }}> {t(deltaLabel)}</span> : null}
                </span>
              ) : null}
            </div>
            <div className="kpi-foot">{t(hint)}</div>
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
              <h2>{t("Провалы по инструментам")}</h2>
              <div className="dim" style={{ fontSize: 11.5, marginTop: 3 }}>
                {t("Доля FAIL среди оценённых кейсов. Внутри инструмента, не между ними.")}
              </div>
            </div>
            <Link to="/metrics" className="muted" style={{ fontSize: 12 }}>
              {t('метрики →')}
            </Link>
          </div>

          {bars.length === 0 ? (
            <div className="empty">{t("Нет данных: выполните прогон.")}</div>
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
                        title={t('{tool}: {rate} из {total}', { tool: bar.tool, rate: pct(bar.rate), total: bar.total })}
                      />
                    </div>
                    <div className="bar-label">{pct(bar.rate)}</div>
                    <div className="bar-sub">{bar.tool}</div>
                  </div>
                ))}
              </div>
              <div className="bar-axis">
                <span>0 %</span>
                <span>{t('шкала: доля FAIL внутри инструмента')}</span>
                <span>100 %</span>
              </div>
            </>
          )}
        </div>

        <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="card-head">
            <h2>{t("Быстрые действия")}</h2>
          </div>
          <div className="quick-list" style={{ flex: 1, justifyContent: 'center' }}>
            {[
              // Each icon mirrors the destination, so the list is scannable
              // without reading the labels. Оптические сдвиги (Play,
              // ClockCounterClockwise) живут в AppIcon: там они в процентах,
              // поэтому верны при любом размере.
              { to: '/runs/new', Icon: Play, title: t('Запустить прогон'), sub: t('выбрать модели и наборы') },
              { to: '/models', Icon: ArrowsLeftRight, title: t('Сравнить модели'), sub: t('эндпоинты и группы') },
              { to: '/datasets', Icon: BracketsCurly, title: t('Править датасеты'), sub: t('кейсы и версии') },
              { to: '/runs', Icon: ClockCounterClockwise, title: t('История прогонов'), sub: t('все результаты') },
            ].map(({ to, Icon, title, sub }) => (
              <Link className="quick-item" to={to} key={to}>
                <span className="qi-icon">
                  <AppIcon icon={Icon} size={20} adjust />
                </span>
                <span>
                  <div className="qi-title">{t(title)}</div>
                  <div className="qi-sub">{t(sub)}</div>
                </span>
                <span className="qi-arrow">›</span>
              </Link>
            ))}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <h2>{t("Последние прогоны")}</h2>
          <Link to="/runs" className="muted" style={{ fontSize: 12 }}>
            {t("все прогоны →")}
          </Link>
        </div>

        {list.length === 0 ? (
          <div className="empty">
            {t("Пока нет ни одного прогона.")} <Link to="/runs/new">{t("Запустить первый")}</Link>
          </div>
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>{t("Прогон")}</th>
                <th>{t("Модели")}</th>
                <th>{t("Инструменты")}</th>
                <th className="num">{t("Провалы")}</th>
                <th>{t("Статус")}</th>
                <th>{t('Когда')}</th>
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
                    <td className="dim">{formatRelative(run.finished_at || run.created_at, t)}</td>
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
            <h2>{t("Как читать эти числа")}</h2>
            <div className="dim" style={{ fontSize: 11.5, marginTop: 3 }}>
              {t("Словарь метрик, который отдают сами инструменты.")}
            </div>
          </div>
          <Link to="/metrics" className="muted" style={{ fontSize: 12 }}>
            {t("подробнее →")}
          </Link>
        </div>
        <div className="grid grid-3">
          {(catalog.data || []).slice(0, 3).map((metric) => (
            <div key={metric.id} style={{ borderLeft: '2px solid var(--accent)', paddingLeft: 12 }}>
              <div style={{ fontSize: 12.5, marginBottom: 3 }}>{t(metric.label)}</div>
              <div className="dim mono-sm" style={{ marginBottom: 5 }}>{t(metric.formula)}</div>
              <div className="muted" style={{ fontSize: 11.5, lineHeight: 1.55 }}>
                {t(metric.caveat)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

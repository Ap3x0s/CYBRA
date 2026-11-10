import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import {
  Banner, Empty, ErrorBox, MetricTile, Meter, StatusPill, formatDate, pct,
} from '../components'
import { BlockSkeleton, PageSkeleton } from '../components/Skeletons'
import { useApi, usePoll } from '../hooks'
import { useI18n } from '../i18n-context'

const RUNNING = new Set(['PENDING', 'RUNNING'])

export default function RunDetail() {
  const { id } = useParams()
  const { t } = useI18n()
  const run = useApi(() => api.run(id), [id])
  const [expanded, setExpanded] = useState(null)
  const [findings, setFindings] = useState([])
  const [findingsBusy, setFindingsBusy] = useState(false)
  const [cancelError, setCancelError] = useState(null)

  const live = RUNNING.has(run.data?.status)
  const progress = usePoll(() => api.runProgress(id), live, 1500, [id])

  // A live run flips to a final state server-side; pull the imported results
  // once so the table is not left empty after the scan completes.
  const [lastStatus, setLastStatus] = useState(null)
  if (run.data && run.data.status !== lastStatus) {
    if (lastStatus && RUNNING.has(lastStatus) && !RUNNING.has(run.data.status)) {
      run.reload()
    }
    setLastStatus(run.data.status)
  }

  async function loadFindings(stepId, verdict) {
    setExpanded(stepId)
    setFindingsBusy(true)
    try {
      const params = { limit: 300, step_id: stepId }
      if (verdict) params.verdict = verdict
      const rows = await api.runFindings(id, params)
      setFindings(rows)
    } catch (problem) {
      setFindings([])
    } finally {
      setFindingsBusy(false)
    }
  }

  async function cancel() {
    setCancelError(null)
    try {
      await api.cancelRun(id)
    } catch (problem) {
      setCancelError(problem)
    }
  }

  if (run.loading) return <PageSkeleton variant="detail" />
  if (run.error) return <ErrorBox error={run.error} />

  const data = run.data
  const steps = data.steps || []
  const totals = steps.reduce(
    (acc, step) => {
      const counts = step.counts || {}
      acc.pass += counts.PASS || 0
      acc.fail += counts.FAIL || 0
      acc.error += (counts.ERROR || 0) + (counts.UNSCORED || 0) + (counts.SKIPPED || 0)
      return acc
    },
    { pass: 0, fail: 0, error: 0 },
  )
  const total = totals.pass + totals.fail
  const models = [...new Set(steps.map((step) => step.model_label))]

  const stepsByModel = models.map((model) => ({
    model,
    steps: steps.filter((step) => step.model_label === model),
  }))

  return (
    <div className="fade-in">
      <div className="page-head">
        <div>
          <div className="dim mono-sm" style={{ marginBottom: 4 }}>
            {data.run_id} · {data.engine_mode}
          </div>
          <h1>{data.label}</h1>
          <p>
            <StatusPill status={data.status} />{' '}
            <span className="muted" style={{ marginLeft: 8 }}>
              начат {formatDate(data.started_at)} · завершён {formatDate(data.finished_at)}
            </span>
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <a className="btn ghost" href={`/api/v1/runs/${id}/report?fmt=md`}>
            {t("Скачать .md")}
          </a>
          <Link className="btn ghost" to={`/runs/${id}/report`}>
            {t("Отчёт для печати")}
          </Link>
          {live ? (
            <button className="btn danger" onClick={cancel}>
              {t("Отменить")}
            </button>
          ) : (
            <button className="btn ghost" onClick={run.reload}>
              {t("Обновить")}
            </button>
          )}
        </div>
      </div>

      <ErrorBox error={cancelError} />

      {data.engine_mode === 'mock' ? (
        <Banner tone="warn">
          {t("Прогон выполнен в режиме")} <strong>mock</strong>: вердикты синтетические и не являются
          оценкой безопасности какой-либо модели.
        </Banner>
      ) : null}

      {data.error ? <Banner tone="bad">{t('Ошибка движка:')} {data.error}</Banner> : null}

      {live ? (
        <div className="card">
          <div className="card-head">
            <h2>{t("Прогресс")}</h2>
            <span className="dim mono-sm">
              target: {progress?.requests?.target ?? 0} · judge: {progress?.requests?.judge ?? 0}
              {progress?.requests?.elapsed_seconds ? ` · ${progress.requests.elapsed_seconds}s` : ''}
            </span>
          </div>
          <p className="muted" style={{ fontSize: 12.5, marginTop: 0 }}>
            Сейчас: {progress?.current_model || '—'} / {progress?.current_tool || '—'}
          </p>
          <div className="log">
            {(progress?.finished_steps || []).length
              ? progress.finished_steps.map((line) => <div key={line}>✓ {line}</div>)
              : <div>{t("Ожидание первых результатов…")}</div>}
            {(progress?.errors || []).map((line) => (
              <div key={line} style={{ color: 'var(--danger)' }}>
                ! {line}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="grid grid-4 stagger" style={{ margin: '16px 0 20px' }}>
        <MetricTile label={t("Моделей")} value={models.length} />
        <MetricTile label={t("Шагов")} value={steps.length} hint={t("модель × инструмент")} />
        <MetricTile
          label={t("Провалов")}
          value={totals.fail}
          hint={total ? t('из {total} оценённых', { total }) : t('нет данных')}
          tone={totals.fail ? 'danger' : total ? 'ok' : undefined}
        />
        <MetricTile
          label={t("Не оценено")}
          value={totals.error}
          hint="ERROR / UNSCORED / SKIPPED"
          tone={totals.error ? 'danger' : undefined}
        />
      </div>

      {steps.length === 0 && !live ? (
        <Empty>{t("Результаты ещё не импортированы. Нажмите «Обновить».")}</Empty>
      ) : null}

      {stepsByModel.map(({ model, steps: modelSteps }) => (
        <div className="card" key={model}>
          <div className="card-head">
            <h2>{model}</h2>
            <span className="dim mono-sm">{modelSteps.length} {t('инструментов')}</span>
          </div>

          {/* The table has seven columns and a long artifact path; on narrower
              windows it would push out of the card instead of scrolling. */}
          <div style={{ overflowX: 'auto' }}>
          <table className="data">
            <thead>
              <tr>
                <th>{t("Инструмент")}</th>
                <th>{t("Полнота")}</th>
                <th className="num">PASS</th>
                <th className="num">FAIL</th>
                <th className="num">{t("Ошибки")}</th>
                <th>{t("Доля провалов")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {modelSteps.map((step) => {
                const counts = step.counts || {}
                const bad = (counts.ERROR || 0) + (counts.UNSCORED || 0) + (counts.SKIPPED || 0)
                return (
                  <tr key={step.id} className="clickable" onClick={() => loadFindings(step.id)}>
                    <td>{step.tool}</td>
                    <td>
                      <StatusPill status={step.completeness} />
                    </td>
                    <td className="num" style={{ color: 'var(--accent)' }}>
                      {counts.PASS || 0}
                    </td>
                    <td className="num" style={{ color: counts.FAIL ? 'var(--danger)' : 'var(--muted)' }}>
                      {counts.FAIL || 0}
                    </td>
                    <td className="num" style={{ color: bad ? 'var(--warn)' : 'var(--muted)' }}>
                      {bad}
                    </td>
                    <td>
                      {step.failed_check_rate === null ? (
                        <span className="dim">—</span>
                      ) : (
                        <Meter value={step.failed_check_rate} />
                      )}
                    </td>
                    <td className="dim" style={{ fontSize: 11 }}>
                      {step.artifact_dir}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          </div>

          {modelSteps.map((step) =>
            step.error ? (
              <div key={'err' + step.id} className="banner bad" style={{ marginTop: 10 }}>
                {step.tool}: {step.error}
              </div>
            ) : null,
          )}

          {modelSteps.map((step) =>
            step.categories && Object.keys(step.categories).length ? (
              <details key={'cat' + step.id} style={{ marginTop: 12 }}>
                <summary className="muted" style={{ cursor: 'pointer', fontSize: 12.5 }}>
                  {step.tool}: разбивка по категориям
                </summary>
                <table className="data" style={{ marginTop: 8 }}>
                  <thead>
                    <tr>
                      <th>{t("Категория")}</th>
                      <th className="num">PASS</th>
                      <th className="num">FAIL</th>
                      <th className="num">ERROR</th>
                      <th className="num">UNSCORED</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(step.categories).map(([category, bucket]) => (
                      <tr key={category}>
                        <td>{category}</td>
                        <td className="num">{bucket.PASS || 0}</td>
                        <td className="num" style={{ color: bucket.FAIL ? 'var(--danger)' : undefined }}>
                          {bucket.FAIL || 0}
                        </td>
                        <td className="num">{bucket.ERROR || 0}</td>
                        <td className="num">{bucket.UNSCORED || 0}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            ) : null,
          )}
        </div>
      ))}

      {expanded ? (
        <div className="card">
          <div className="card-head">
            <h2>{t("Кейсы")}</h2>
            <button className="btn ghost small" onClick={() => setExpanded(null)}>
              {t("Скрыть")}
            </button>
          </div>
          {findingsBusy ? (
            <BlockSkeleton rows={5} />
          ) : findings.length === 0 ? (
            <Empty>{t("Для этого шага кейсы не сохранены.")}</Empty>
          ) : (
            <table className="data">
              <thead>
                <tr>
                  <th>{t("Кейс")}</th>
                  <th>{t("Категория")}</th>
                  <th>{t("Вердикт")}</th>
                  <th>{t("Ответ (фрагмент)")}</th>
                </tr>
              </thead>
              <tbody>
                {findings.slice(0, 200).map((finding) => (
                  <tr key={finding.id}>
                    <td className="mono-sm">{finding.case_id}</td>
                    <td className="muted">{finding.category}</td>
                    <td>
                      <StatusPill status={finding.verdict} />
                    </td>
                    <td className="dim" style={{ maxWidth: 420 }}>
                      <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {(finding.answer || finding.reason || '').slice(0, 160)}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ) : null}
    </div>
  )
}
